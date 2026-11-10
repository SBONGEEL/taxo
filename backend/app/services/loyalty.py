"""**نقاطُ الولاء** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٤، SPEC §٩٧/١٤) — البيتُ الواحد: القاعدة، والكسب، والمستوى، والاستبدال.

**الكسبُ بكنسٍ لا من مسار الإنهاء** (`sweep` كلَّ عشر دقائق): الرحلاتُ المكتملةُ في آخر يومين بلا صفِّ كسب — **فلا يُمسّ أحرجُ مسارٍ في
المشروع**، والتأخّرُ دقائق. **ولا نقاطَ لملغاةٍ** (المكتملةُ وحدَها) **ولا لمزيّفة**: حسابُ تجربةٍ من أيِّ طرف، أو أجرةٌ صفر، أو رحلةٌ
راكبُها هو كبتنُها.

**والاستبدالُ رصيدٌ في المحفظة** (`loyalty_reward` من TAXO) يُدفع به في الرحلات القادمة — **وقفلُ المحفظة الاستشاريُّ قبل قراءة الرصيد**:
بلاه يقرأ استبدالان الرصيدَ نفسَه فيُصرف مرّتين (`test_loyalty_concurrency.py`). ويُستهلك الأقدمُ أوّلاً.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import Conflict, FeatureDisabled, InvalidInput
from app.models.driver import Driver
from app.models.enums import CountryCode, FeatureKey, RideStatus, WalletTransactionType
from app.models.loyalty import LoyaltyEarning, LoyaltyRule
from app.models.ride import Ride
from app.models.user import User
from app.services import settings_service, test_accounts

#: نافذةُ المستوى — نقاطُ آخر سنة
TIER_WINDOW = timedelta(days=365)
#: نافذةُ الكنس — ما اكتمل في آخر يومين ولم يكسب
SWEEP_WINDOW = timedelta(days=2)


async def enabled(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(session, country, FeatureKey.LOYALTY_ENABLED)


async def rule_for(session: AsyncSession, country: CountryCode) -> LoyaltyRule | None:
    return await session.scalar(select(LoyaltyRule).where(LoyaltyRule.country_code == country))


async def save_rule(session: AsyncSession, country: CountryCode, data: dict) -> tuple[LoyaltyRule, dict]:
    from app.services import pricing

    value = Decimal(str(data["redeem_value"]))
    if pricing.round_money(value, currency_for_country(country)) != value:
        raise InvalidInput("قيمةُ الاستبدال بخانات عملة الدولة")
    if data["gold_threshold"] <= data["silver_threshold"]:
        raise InvalidInput("حدُّ الذهبيّ فوق حدِّ الفضّيّ")
    rule = await rule_for(session, country)
    changes: dict = {}
    if rule is None:
        rule = LoyaltyRule(country_code=country, **data)
        session.add(rule)
        changes = {key: {"from": None, "to": str(val)} for key, val in data.items()}
    else:
        for key, val in data.items():
            if getattr(rule, key) != val:
                changes[key] = {"from": str(getattr(rule, key)), "to": str(val)}
                setattr(rule, key, val)
    await session.flush()
    return rule, changes


def tier_of(rule: LoyaltyRule, year_points: int) -> str:
    if year_points >= rule.gold_threshold:
        return "gold"
    if year_points >= rule.silver_threshold:
        return "silver"
    return "bronze"


def bonus_of(rule: LoyaltyRule, tier: str) -> int:
    return {"gold": rule.gold_bonus_percent, "silver": rule.silver_bonus_percent}.get(tier, 0)


async def year_points(session: AsyncSession, rider_id: uuid.UUID, now: datetime) -> int:
    return int(
        await session.scalar(
            select(func.coalesce(func.sum(LoyaltyEarning.points), 0)).where(
                LoyaltyEarning.rider_id == rider_id, LoyaltyEarning.created_at >= now - TIER_WINDOW
            )
        )
    )


async def balance(session: AsyncSession, rider_id: uuid.UUID, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    return int(
        await session.scalar(
            select(func.coalesce(func.sum(LoyaltyEarning.remaining), 0)).where(
                LoyaltyEarning.rider_id == rider_id, LoyaltyEarning.expires_at > now
            )
        )
    )


async def sweep(session: AsyncSession) -> int:
    """**كسبُ المكتملة** حيث المفتاحُ مشتعلٌ وقاعدةٌ موضوعة — صفٌّ لكلِّ رحلة، والمستوى يزيد ما يُكسب."""
    now = datetime.now(UTC)
    earned = 0
    for rule in (await session.scalars(select(LoyaltyRule))).all():
        country = CountryCode(rule.country_code)
        if not await enabled(session, country):
            continue
        rows = await session.execute(
            select(Ride.id, Ride.rider_id)
            .outerjoin(LoyaltyEarning, LoyaltyEarning.ride_id == Ride.id)
            .outerjoin(Driver, Driver.id == Ride.driver_id)
            .where(
                Ride.country_code == country,
                Ride.status == RideStatus.COMPLETED,
                Ride.completed_at >= now - SWEEP_WINDOW,
                Ride.final_fare > 0,
                LoyaltyEarning.id.is_(None),
                # **لا نقاطَ لمزيّفة**: راكبٌ هو كبتنُ رحلته، أو حسابُ تجربةٍ من أيِّ طرف
                and_(Driver.user_id.is_(None) | (Driver.user_id != Ride.rider_id)),
                test_accounts.real_ride(),
            )
            .limit(2000)
        )
        for ride_id, rider_id in rows.all():
            tier = tier_of(rule, await year_points(session, rider_id, now))
            points = rule.points_per_ride * (100 + bonus_of(rule, tier)) // 100
            session.add(
                LoyaltyEarning(
                    rider_id=rider_id, ride_id=ride_id, points=points, remaining=points,
                    expires_at=now + timedelta(days=rule.expiry_days),
                )
            )
            earned += 1
        await session.commit()
    return earned


@dataclass(frozen=True, slots=True)
class Standing:
    enabled: bool
    currency: str
    points: int
    tier: str
    year_points: int
    next_tier: str | None
    to_next: int | None
    bonus_percent: int
    redeem_points: int | None
    redeem_value: Decimal | None
    #: **كم يساوي رصيدُ النقاط الآن** — كتلٌ كاملةٌ × القيمة، من الخلفية
    redeemable_value: Decimal
    expiry_days: int | None
    #: **أقربُ انتهاء** — النقاطُ والتاريخ
    expiring_points: int
    expiring_at: datetime | None


async def standing(session: AsyncSession, rider: User) -> Standing:
    from app.services import pricing

    country = CountryCode(rider.country_code)
    on = await enabled(session, country)
    rule = await rule_for(session, country)
    currency = str(currency_for_country(country))
    now = datetime.now(UTC)
    if rule is None:
        return Standing(on, currency, 0, "bronze", 0, None, None, 0, None, None, Decimal("0.000"), None, 0, None)
    points = await balance(session, rider.id, now)
    year = await year_points(session, rider.id, now)
    tier = tier_of(rule, year)
    next_tier, to_next = {"bronze": ("silver", rule.silver_threshold - year), "silver": ("gold", rule.gold_threshold - year)}.get(
        tier, (None, None)
    )
    soonest = (
        await session.execute(
            select(LoyaltyEarning.expires_at, func.sum(LoyaltyEarning.remaining))
            .where(LoyaltyEarning.rider_id == rider.id, LoyaltyEarning.expires_at > now, LoyaltyEarning.remaining > 0)
            .group_by(LoyaltyEarning.expires_at)
            .order_by(LoyaltyEarning.expires_at)
            .limit(1)
        )
    ).first()
    return Standing(
        enabled=on, currency=currency, points=points, tier=tier, year_points=year, next_tier=next_tier, to_next=to_next,
        bonus_percent=bonus_of(rule, tier), redeem_points=rule.redeem_points, redeem_value=rule.redeem_value,
        redeemable_value=pricing.as_money(Decimal(points // rule.redeem_points) * rule.redeem_value),
        expiry_days=rule.expiry_days,
        expiring_points=int(soonest[1]) if soonest else 0,
        expiring_at=soonest[0] if soonest else None,
    )


async def _consume(session: AsyncSession, rider_id: uuid.UUID, points: int, now: datetime) -> None:
    rows = await session.scalars(
        select(LoyaltyEarning)
        .where(LoyaltyEarning.rider_id == rider_id, LoyaltyEarning.expires_at > now, LoyaltyEarning.remaining > 0)
        .order_by(LoyaltyEarning.expires_at, LoyaltyEarning.created_at)
    )
    left = points
    for row in rows:
        if left <= 0:
            break
        take = min(row.remaining, left)
        row.remaining -= take
        left -= take
    await session.flush()


async def redeem(session: AsyncSession, rider: User, blocks: int) -> Decimal:
    """**استبدالُ كتلٍ من النقاط رصيداً** — قفلُ المحفظة قبل قراءة الرصيد، والأقدمُ يُستهلك أوّلاً، ثمّ القيد."""
    from app.services import pricing, wallet

    country = CountryCode(rider.country_code)
    if not await enabled(session, country):
        raise FeatureDisabled()
    rule = await rule_for(session, country)
    if rule is None or blocks < 1:
        raise InvalidInput("لا استبدالَ الآن")
    test_accounts.require_real_money(rider)
    await wallet.lock_wallet(session, rider.id)
    now = datetime.now(UTC)
    needed = blocks * rule.redeem_points
    if await balance(session, rider.id, now) < needed:
        raise Conflict("نقاطُك لا تكفي")
    await _consume(session, rider.id, needed, now)
    amount = pricing.as_money(Decimal(blocks) * rule.redeem_value)
    await wallet.record(
        session,
        owner=rider,
        tx_type=WalletTransactionType.LOYALTY_REWARD,
        amount=amount,
        reference=f"loyalty:{needed}",
    )
    return amount
