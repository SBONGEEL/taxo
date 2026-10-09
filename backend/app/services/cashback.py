"""الاسترداد الأسبوعي (SPEC §٦٣-ج/٨ — تعريفُ المالك في سبتمبر، قرارُه ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

**رحلةٌ كلَّ يومٍ لأسبوعٍ متدحرجٍ يبدأ من أوّل رحلة؛ الجمعةُ لا تُحسب؛ فواتُ يومٍ يُلغيه؛ والاستردادُ ينزل في اليوم الأخير.**
**ومبلغٌ ثابتٌ من اللوحة** (`cashback_amount`، صفرٌ يُخفيها) **من TAXO لا من كبتن**.

**والسلسلةُ تُحدَّث عند إنهاء الرحلة** (`on_ride_completed`، والرحلةُ مقفولة) **بيوم السوق** — فلا دورةَ تحسب، والدورةُ للتذكير وحدَه
(`reminders`). **والقفلُ صفُّ السلسلة** بعد صفِّ الرحلة، ثمّ المحفظة.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cashback import CashbackStreak
from app.models.enums import CountryCode, FeatureKey, RoundingSource, WalletOwnerType, WalletTransactionType
from app.models.ride import Ride
from app.models.service_setting import ServiceSetting
from app.models.user import User
from app.services import rounding, settings_service, wallet
from app.services.pricing import round_money

FRIDAY = 4  # `date.weekday()`
ACTIVE = "active"
WON = "won"
LOST = "lost"

#: ساعاتُ التذكير بتوقيت السوق — **صباحاً ومساءً، وقبل نهاية اليوم بساعتين لمن لم يركب**
MORNING_HOUR = 9
EVENING_HOUR = 19
WARNING_HOUR = 22


async def settings_for(session: AsyncSession, country: CountryCode) -> ServiceSetting | None:
    if not await settings_service.is_feature_enabled(session, country, FeatureKey.WEEKLY_CASHBACK_ENABLED):
        return None
    row = await session.get(ServiceSetting, country)
    if row is None or row.cashback_amount <= 0:
        return None
    return row


def next_required(day: date) -> date:
    """**اليومُ المطلوبُ بعد يوم** — والجمعةُ تُتخطّى: لا تُطلب ولا تقطع."""
    following = day + timedelta(days=1)
    return following + timedelta(days=1) if following.weekday() == FRIDAY else following


async def _active(session: AsyncSession, rider_id: uuid.UUID) -> CashbackStreak | None:
    return await session.scalar(
        select(CashbackStreak)
        .where(CashbackStreak.rider_id == rider_id, CashbackStreak.status == ACTIVE)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def record_day(
    session: AsyncSession, *, rider: User, day: date, row: ServiceSetting
) -> CashbackStreak | None:
    """**يومٌ فيه رحلةٌ مكتملة** — يبدأ سلسلةً أو يمدّها أو يُسقطها ويبدأ غيرَها، وينزل المبلغُ في يومها الأخير."""
    # **راكبُ التجربة لا سلسلةَ له** (SPEC §٦٥-ج/٢): الاستردادُ مالٌ من TAXO بلا مدين — **يُتخطّى صامتاً**، ولا يُبدأ عدٌّ
    # لن يُدفع فلا تذكيرَ يَعِد به (`reminders` تقرأ السلاسلَ القائمة وحدَها). **وهنا لا في المنادي**: هذا البابُ الوحيدُ
    # الذي يكتب سلسلةً ويصرف مبلغَها، وشرطٌ فوقه يُنسى في منادٍ ثانٍ
    if rider.is_test:
        return None
    if day.weekday() == FRIDAY:
        return await _active(session, rider.id)
    streak = await _active(session, rider.id)
    if streak is not None:
        if day <= streak.last_day:
            return streak
        if day != next_required(streak.last_day):
            streak.status = LOST
            await session.flush()
            streak = None
    if streak is None:
        streak = CashbackStreak(
            rider_id=rider.id,
            country_code=rider.country_code,
            started_on=day,
            last_day=day,
            days_done=1,
            days_required=row.cashback_days,
            amount=round_money(row.cashback_amount),
            status=ACTIVE,
        )
        session.add(streak)
        await session.flush()
    else:
        streak.last_day = day
        streak.days_done += 1
    if streak.days_done >= streak.days_required:
        await _win(session, streak, rider)
    await session.flush()
    return streak


async def _win(session: AsyncSession, streak: CashbackStreak, rider: User) -> None:
    """ينزل المبلغُ في اليوم الأخير — **مقرَّباً لحظةَ نزوله** (SPEC §٧٠-ج/٥): المجمَّدُ على السلسلة بدقّته (`amount`)، والنزولُ هو
    المعاملة — سلسلةٌ بدأت قبل الإشعال تُقرَّب إن نزلت بعده، كالرحلة. وفرقُه صفٌّ بمعرّف السلسلة. ومطفأً كما كان حرفاً."""
    streak.status = WON
    streak.won_at = datetime.now(UTC)
    policy = await rounding.policy_for(session, streak.country_code)
    amount = rounding.rounded(streak.amount, policy)
    await rounding.record(
        session,
        country=streak.country_code,
        source=RoundingSource.CASHBACK,
        source_id=streak.id,
        user_id=rider.id,
        precise=streak.amount,
        rounded_amount=amount,
        policy=policy,
    )
    if amount <= 0:
        # **مبلغٌ قُرِّب إلى صفر** (للأدنى، ومبلغٌ دون الوحدة) — لا قيدَ بصفر، والفرقُ مكتوبٌ في السجلّ فوق
        return
    await wallet.lock_wallet(session, rider.id)
    await wallet.record(
        session,
        owner=rider,
        owner_type=WalletOwnerType.RIDER,
        tx_type=WalletTransactionType.CASHBACK,
        amount=amount,
        created_by=None,
        idempotency_key=f"cashback:{streak.id}",
    )


async def on_ride_completed(session: AsyncSession, ride: Ride) -> None:
    """يُنادى من `complete_ride` — **رحلاتُ الطالب أيّاً كانت قناةُ دفعها**."""
    row = await settings_for(session, ride.country_code)
    if row is None:
        return
    rider = await session.get(User, ride.rider_id)
    if rider is None:
        return
    from app.services.stats import _zone

    zone = await _zone(session, ride.country_code)
    day = (ride.completed_at or datetime.now(UTC)).astimezone(zone).date()
    await record_day(session, rider=rider, day=day, row=row)


async def view(session: AsyncSession, rider: User) -> dict:
    """**ما تعرضه الشاشةُ بجانب النار** — الأيامُ الباقيةُ والمبلغُ المنتظَر وهل رُكب اليوم. وسلسلةٌ فاتها يومٌ تُقرأ «لا سلسلة»."""
    row = await settings_for(session, rider.country_code)
    # **ولراكبِ التجربة مطفأةٌ كأنها لم تُشعل** (SPEC §٦٥-ج/٢): السلسلةُ لا تُعدّ له (`on_ride_completed`)، **ونارٌ ترسم
    # وعداً لن يُدفع** هي ما يمنعه §٦٥-ب بعينه: «لا وعدَ باسترداد»
    if row is None or rider.is_test:
        return {"enabled": False}
    from app.services.stats import country_today

    today = await country_today(session, rider.country_code)
    streak = await session.scalar(
        select(CashbackStreak).where(CashbackStreak.rider_id == rider.id, CashbackStreak.status == ACTIVE)
    )
    alive = streak is not None and (today <= next_required(streak.last_day))
    # **المنتظَرُ كما سينزل** — مقرَّباً بإعداد السوق (`_win`)، فلا تَعِد النارُ بغير ما يُقيَّد. ومطفأً كما كان حرفاً
    policy = await rounding.policy_for(session, rider.country_code)
    return {
        "enabled": True,
        "days_required": row.cashback_days if not alive else streak.days_required,
        "days_done": streak.days_done if alive else 0,
        "days_left": (streak.days_required - streak.days_done) if alive else row.cashback_days,
        "amount": rounding.rounded(streak.amount if alive else round_money(row.cashback_amount), policy),
        "rode_today": bool(alive and streak.last_day == today),
        "friday": today.weekday() == FRIDAY,
    }


def due_reminder(streak: CashbackStreak, today: date, hour: int) -> str | None:
    """**أيُّ تذكيرٍ يحين الآن** — `morning` · `evening` · `warning`، أو لا شيء. **والجمعةُ بلا تذكير** (لا تُطلب)."""
    if today.weekday() == FRIDAY or streak.last_day >= today:
        return None
    if next_required(streak.last_day) != today:
        return None
    if hour >= WARNING_HOUR:
        return "warning"
    if hour >= EVENING_HOUR:
        return "evening"
    if hour >= MORNING_HOUR:
        return "morning"
    return None


async def reminders(session: AsyncSession, redis) -> int:
    """التذكيراتُ الثلاثة — **مرّةً لكلِّ (سلسلة، يوم، نوع)** بمفتاحٍ في Redis، **والنصُّ عن الأيام لا عن المال**."""
    from app.services import notifications
    from app.services.stats import _zone

    sent = 0
    rows = list(await session.scalars(select(CashbackStreak).where(CashbackStreak.status == ACTIVE)))
    for streak in rows:
        if await settings_for(session, streak.country_code) is None:
            continue
        zone = await _zone(session, streak.country_code)
        now = datetime.now(UTC).astimezone(zone)
        kind = due_reminder(streak, now.date(), now.hour)
        if kind is None:
            continue
        key = f"cashback:remind:{streak.id}:{now.date().isoformat()}:{kind}"
        if not await redis.set(key, "1", nx=True, ex=60 * 60 * 30):
            continue
        await notifications.publish_cashback_reminder(
            session,
            redis,
            rider_id=streak.rider_id,
            kind=kind,
            days_done=streak.days_done,
            days_left=streak.days_required - streak.days_done,
        )
        sent += 1
    return sent
