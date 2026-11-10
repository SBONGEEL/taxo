"""**أهدافُ الكبتن ومكافآتُها** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٦، SPEC §٩٧/١٦).

* **التقدّمُ يُقاس حيّاً** — رحلاتُ الكبتن المكتملة بين `starts_at` و`ends_at` (لا عمودَ يراكمه).
* **الصرفُ بكاتبٍ واحد** (`award`) تحت **قفل صفِّ الهدف** ثمّ قفل المحفظة: يقرأ المصروفَ من صفوف المكافآت ويرفض ما يتجاوز السقف،
  وصفُّ المكافأة فريدٌ لكلِّ هدفٍ وكبتن، والقيدُ بمفتاح عدمِ تكرار. **بلا القفل** يقرأ صرفان متزامنان المصروفَ نفسَه فيتجاوزان
  السقف (`test_driver_goals_concurrency.py`).
* **ترتيبُ الأقفال**: صفُّ الهدف ثمّ قفلُ المحفظة الاستشاريّ — لا صفَّ رحلةٍ ولا دفعٍ في المسار، فلا يتقاطع مع ترتيب `CLAUDE.md`.
* **والمفتاحُ مطفأً** (`driver_goals_enabled`) لا يُصرف شيءٌ ولا يُرى هدف.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country, is_precise
from app.core.exceptions import InvalidInput, NotFound
from app.models.driver import Driver
from app.models.driver_goal import DriverGoal, DriverGoalAward
from app.models.enums import CountryCode, FeatureKey, RideStatus, WalletOwnerType, WalletTransactionType
from app.models.ride import Ride
from app.models.user import User
from app.services import notifications, settings_service, wallet

#: **«اقتربت»** عند ٨٠٪ من الهدف — إشعارٌ واحدٌ لكلِّ هدفٍ وكبتن
NEAR_SHARE = 0.8
#: **هدفٌ انتهى يُكنس يوماً بعده** — رحلةٌ اكتملت في آخر دقيقةٍ تُحسب ولو تأخّر الكنس
GRACE = timedelta(days=1)


async def enabled(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(session, country, FeatureKey.DRIVER_GOALS_ENABLED)


def _check_amounts(country: CountryCode, reward: Decimal, cap: Decimal) -> None:
    currency = currency_for_country(country)
    for value in (reward, cap):
        if not is_precise(value, currency):
            raise InvalidInput("المبلغُ بخانات عملة الدولة", field="reward_amount")
    if cap < reward:
        raise InvalidInput("سقفُ الميزانيّة لا يقلّ عن مكافأةٍ واحدة", field="budget_cap")


async def create(session: AsyncSession, *, country: CountryCode, actor: User, data: dict) -> DriverGoal:
    _check_amounts(country, data["reward_amount"], data["budget_cap"])
    if data["ends_at"] <= data["starts_at"]:
        raise InvalidInput("النهايةُ بعد البداية", field="ends_at")
    goal = DriverGoal(country_code=country, created_by=actor.id, **data)
    session.add(goal)
    await session.flush()
    return goal


async def locked(session: AsyncSession, goal_id: uuid.UUID) -> DriverGoal:
    goal = (
        await session.execute(
            select(DriverGoal).where(DriverGoal.id == goal_id).with_for_update().execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if goal is None:
        raise NotFound("الهدفُ غيرُ موجود")
    return goal


async def spent(session: AsyncSession, goal_id: uuid.UUID) -> tuple[Decimal, int]:
    row = (
        await session.execute(
            select(func.coalesce(func.sum(DriverGoalAward.amount), 0), func.count()).where(DriverGoalAward.goal_id == goal_id)
        )
    ).one()
    return Decimal(row[0]), int(row[1])


def _done_query(goal: DriverGoal, now: datetime):
    end = min(now, goal.ends_at)
    return (
        select(Ride.driver_id, func.count())
        .where(
            Ride.country_code == goal.country_code,
            Ride.status == RideStatus.COMPLETED,
            Ride.driver_id.is_not(None),
            Ride.completed_at >= goal.starts_at,
            Ride.completed_at <= end,
        )
        .group_by(Ride.driver_id)
    )


async def progress(session: AsyncSession, goal: DriverGoal, driver_id: uuid.UUID, now: datetime | None = None) -> int:
    query = _done_query(goal, now or datetime.now(UTC)).where(Ride.driver_id == driver_id)
    row = (await session.execute(query)).first()
    return int(row[1]) if row else 0


async def award(session: AsyncSession, redis: Redis | None, *, goal_id: uuid.UUID, driver_id: uuid.UUID) -> bool:
    """**الصرفُ الواحد** — تحت قفل الهدف: لا مرّتين، ولا فوق السقف، ولا لهدفٍ أُوقف. ويُلتزم هنا."""
    goal = await locked(session, goal_id)
    if not goal.is_active or not await enabled(session, goal.country_code):
        await session.rollback()
        return False
    exists = await session.scalar(
        select(DriverGoalAward.id).where(DriverGoalAward.goal_id == goal_id, DriverGoalAward.driver_id == driver_id)
    )
    total, _count = await spent(session, goal_id)
    if exists is not None or total + goal.reward_amount > goal.budget_cap:
        await session.rollback()
        return False
    driver = await session.get(Driver, driver_id)
    owner = await session.get(User, driver.user_id) if driver else None
    if owner is None:
        await session.rollback()
        return False
    session.add(DriverGoalAward(goal_id=goal_id, driver_id=driver_id, amount=goal.reward_amount, reference=f"goal:{goal_id}"))
    await session.flush()
    await wallet.record(
        session,
        owner=owner,
        owner_type=WalletOwnerType.DRIVER,
        tx_type=WalletTransactionType.GOAL_REWARD,
        amount=goal.reward_amount,
        reference=f"goal:{goal_id}",
        # **المفتاحُ ٦٤ حرفاً على الأكثر** — بصمةُ الهدف والكبتن معاً لا المعرّفان نصّاً
        idempotency_key="goal:" + hashlib.sha256(f"{goal_id}:{driver_id}".encode()).hexdigest()[:48],
    )
    await session.commit()
    if redis is not None:
        await notifications.publish_goal_event(session, redis, user_id=owner.id, event="reward")
        await session.commit()
    return True


async def sweep(session: AsyncSession, redis: Redis, *, now: datetime | None = None) -> tuple[int, int]:
    """**الكنسُ الدوريّ** — يصرف لمن بلغ، وينبّه من اقترب مرّةً. ويعيد (صُرف، نُبِّه)."""
    now = now or datetime.now(UTC)
    goals = (
        await session.scalars(
            select(DriverGoal).where(DriverGoal.is_active.is_(True), DriverGoal.starts_at <= now, DriverGoal.ends_at >= now - GRACE)
        )
    ).all()
    paid = nudged = 0
    for goal in goals:
        if not await enabled(session, goal.country_code):
            continue
        goal_id, target, ends_at = goal.id, goal.target, goal.ends_at
        rows = (await session.execute(_done_query(goal, now))).all()
        awarded = set(
            await session.scalars(select(DriverGoalAward.driver_id).where(DriverGoalAward.goal_id == goal_id))
        )
        near_at = max(1, math.ceil(target * NEAR_SHARE))
        for driver_id, done in rows:
            if done >= target and driver_id not in awarded:
                if await award(session, redis, goal_id=goal_id, driver_id=driver_id):
                    paid += 1
            elif near_at <= done < target and now <= ends_at:
                if await redis.set(f"goal:near:{goal_id}:{driver_id}", "1", nx=True, ex=40 * 86400):
                    driver = await session.get(Driver, driver_id)
                    if driver is not None:
                        await notifications.publish_goal_event(session, redis, user_id=driver.user_id, event="near")
                        await session.commit()
                        nudged += 1
    return paid, nudged


@dataclass(frozen=True)
class MyGoal:
    id: uuid.UUID
    title: str
    description: str | None
    target: int
    done: int
    reward_amount: Decimal
    starts_at: datetime
    ends_at: datetime
    rewarded: bool


async def mine(session: AsyncSession, driver: Driver, country: CountryCode, now: datetime | None = None) -> tuple[bool, list[MyGoal]]:
    now = now or datetime.now(UTC)
    if not await enabled(session, country):
        return False, []
    goals = (
        await session.scalars(
            select(DriverGoal)
            .where(DriverGoal.country_code == country, DriverGoal.is_active.is_(True), DriverGoal.ends_at >= now - GRACE, DriverGoal.starts_at <= now)
            .order_by(DriverGoal.ends_at)
        )
    ).all()
    out = []
    for goal in goals:
        rewarded = (
            await session.scalar(
                select(DriverGoalAward.id).where(DriverGoalAward.goal_id == goal.id, DriverGoalAward.driver_id == driver.id)
            )
        ) is not None
        out.append(
            MyGoal(goal.id, goal.title, goal.description, goal.target, await progress(session, goal, driver.id, now),
                   goal.reward_amount, goal.starts_at, goal.ends_at, rewarded)
        )
    return True, out
