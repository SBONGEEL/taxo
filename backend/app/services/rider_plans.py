"""**اشتراكاتُ الركّاب** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٣، SPEC §٩٧/١٣) — البيتُ الواحد: الخطط، والشراء، والخصمُ عند الإنهاء.

**الشراءُ من المحفظة** (وتُشحن بكلِّ وسائل الدفع القائمة): **قفلُ المحفظة الاستشاريُّ أوّلاً** ثمّ فحصُ «أله اشتراكٌ سارٍ؟» ثمّ القيدُ
ثمّ الصفّ — **بلا القفل قبل الفحص يقرأ نقران «لا اشتراك» معاً فيُقتطع الثمنُ مرّتين** (`test_rider_plans_concurrency.py`). والقفلُ
يُعاد أخذُه في `wallet.record` (أقفالُ Postgres الاستشاريّةُ تُعاد في المعاملة نفسِها).

**والخصمُ عند الإنهاء** (`apply_on_completion`، من `rides.complete_ride`): بعد الأجرة النهائية، **تحت قفل صفِّ الاشتراك** — وموضعُه في
ترتيب الأقفال **بعد صفِّ الرحلة وقبل صفِّ الدفعة** كصفِّ الكوبون — فيُقرأ ما خُصم في الثلاثين يوماً ويُكتب صفُّ الخصم متسلسلين، **فلا
يتجاوز إنهاءان متزامنان الحدَّ الشهريّ**. **ولا يجتمع مع كوبونٍ ولا مع خصم المشاركة**: الراكبُ اختار ذاك صراحةً.

- **TAXO تتحمّله**: صفُّ دفعةٍ بقناة `promo` معلَّقٌ يسوّيه الإنهاء (آليةُ الكوبون حرفاً) — الكبتنُ يقبض كأن لا خصم.
- **الكبتنُ يتحمّله**: الأجرةُ تنقص بسطر «خصم الاشتراك» (سالب) — فيقبض أقلَّ وتُحسب العمولةُ على ما بقي.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import Conflict, FeatureDisabled, InvalidInput, NotFound
from app.models.enums import CountryCode, FeatureKey, PaymentMethod, PaymentStatus, RiderPlanBearer, WalletTransactionType
from app.models.payment import Payment
from app.models.ride import Ride
from app.models.rider_plan import RiderPlan, RiderPlanSubscription, RiderPlanUse
from app.models.user import User
from app.services import settings_service

#: **نافذةُ الحدّ الشهريّ** — ثلاثون يوماً من بداية الاشتراك، كتلةً بعد كتلة
MONTH = timedelta(days=30)
#: **التجديدُ المبكّر** — يُسمح بالشراء في الأيام الثلاثة الأخيرة، ويبدأ الجديدُ من نهاية الحاليّ
RENEW_WINDOW = timedelta(days=3)


async def enabled(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(session, country, FeatureKey.RIDER_PLANS_ENABLED)


def _precise(country: CountryCode, *values: Decimal) -> None:
    from app.services import pricing

    currency = currency_for_country(country)
    for value in values:
        if pricing.round_money(value, currency) != value:
            raise InvalidInput("المبلغُ بخانات عملة الدولة")


async def create_plan(session: AsyncSession, *, country: CountryCode, actor: User, data: dict) -> RiderPlan:
    _precise(country, data["price"], data["per_ride_cap"], data["monthly_cap"])
    if data["monthly_cap"] < data["per_ride_cap"]:
        raise InvalidInput("حدُّ الشهر لا يقلّ عن حدِّ الرحلة")
    plan = RiderPlan(country_code=country, created_by=actor.id, **data)
    session.add(plan)
    await session.flush()
    return plan


async def plans_for(session: AsyncSession, country: CountryCode, *, active_only: bool) -> list[RiderPlan]:
    query = select(RiderPlan).where(RiderPlan.country_code == country)
    if active_only:
        query = query.where(RiderPlan.is_active.is_(True))
    return list((await session.scalars(query.order_by(RiderPlan.price))).all())


async def current(session: AsyncSession, rider_id: uuid.UUID, now: datetime | None = None) -> RiderPlanSubscription | None:
    """**الاشتراكُ الساري الآن** — أو `None`. والتجديدُ المبكّرُ يكتب صفّاً يبدأ بعد هذا فلا يتداخلان."""
    now = now or datetime.now(UTC)
    return await session.scalar(
        select(RiderPlanSubscription)
        .where(RiderPlanSubscription.rider_id == rider_id, RiderPlanSubscription.starts_at <= now, RiderPlanSubscription.ends_at > now)
        .order_by(RiderPlanSubscription.starts_at)
        .limit(1)
    )


async def _latest_end(session: AsyncSession, rider_id: uuid.UUID, now: datetime) -> datetime | None:
    return await session.scalar(
        select(func.max(RiderPlanSubscription.ends_at)).where(
            RiderPlanSubscription.rider_id == rider_id, RiderPlanSubscription.ends_at > now
        )
    )


async def purchase(session: AsyncSession, *, rider: User, plan_id: uuid.UUID) -> RiderPlanSubscription:
    """**شراءٌ من المحفظة** — القفلُ قبل الفحص، والصفُّ بعد القيد."""
    from app.services import wallet

    if not await enabled(session, rider.country_code):
        raise FeatureDisabled()
    plan = await session.get(RiderPlan, plan_id)
    if plan is None or not plan.is_active or plan.country_code != rider.country_code:
        raise NotFound("الخطّةُ غيرُ متاحة")
    await wallet.lock_wallet(session, rider.id)
    now = datetime.now(UTC)
    latest = await _latest_end(session, rider.id, now)
    if latest is not None and latest - now > RENEW_WINDOW:
        raise Conflict("اشتراكُك سارٍ — يُجدَّد في أيّامه الثلاثة الأخيرة")
    starts = latest or now
    subscription = RiderPlanSubscription(
        rider_id=rider.id,
        plan_id=plan.id,
        starts_at=starts,
        ends_at=starts + timedelta(days=plan.days),
        price_paid=plan.price,
        discount_percent=plan.discount_percent,
        per_ride_cap=plan.per_ride_cap,
        monthly_cap=plan.monthly_cap,
        bearer=plan.bearer,
    )
    session.add(subscription)
    await session.flush()
    await wallet.record(
        session,
        owner=rider,
        tx_type=WalletTransactionType.RIDER_PLAN_PAYMENT,
        amount=-plan.price,
        reference=f"plan:{plan.id}",
        idempotency_key=f"plan-sub:{subscription.id}",
    )
    return subscription


def month_start(subscription: RiderPlanSubscription, now: datetime) -> datetime:
    blocks = int((now - subscription.starts_at) / MONTH) if now > subscription.starts_at else 0
    return subscription.starts_at + blocks * MONTH


async def used(session: AsyncSession, subscription_id: uuid.UUID, since: datetime | None = None) -> Decimal:
    query = select(func.coalesce(func.sum(RiderPlanUse.amount), 0)).where(RiderPlanUse.subscription_id == subscription_id)
    if since is not None:
        query = query.where(RiderPlanUse.created_at >= since)
    return Decimal(await session.scalar(query))


async def take_discount(
    session: AsyncSession, *, subscription_id: uuid.UUID, ride_id: uuid.UUID, base: Decimal, currency: str
) -> Decimal:
    """**الخصمُ لهذه الرحلة وصفُّه** — تحت قفل صفِّ الاشتراك. والمبلغ: النسبةُ على ما يُخصم منه، بحدِّ الرحلة وما بقي من حدِّ الشهر."""
    from app.services import pricing

    subscription = (
        await session.execute(
            select(RiderPlanSubscription)
            .where(RiderPlanSubscription.id == subscription_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    now = datetime.now(UTC)
    left = subscription.monthly_cap - await used(session, subscription.id, month_start(subscription, now))
    amount = pricing.round_money(
        min(base * subscription.discount_percent / Decimal(100), subscription.per_ride_cap, max(left, Decimal(0))), currency
    )
    if amount <= 0:
        return Decimal(0)
    session.add(RiderPlanUse(subscription_id=subscription.id, ride_id=ride_id, amount=amount))
    await session.flush()
    return amount


async def apply_on_completion(session: AsyncSession, ride: Ride) -> Payment | None:
    """**خصمُ الاشتراك لحظةَ الإنهاء** — بعد الأجرة النهائية وقبل الكوبون والتقريب. يعيد صفَّ دفعةٍ معلَّقاً حين تتحمّله TAXO."""
    from app.services import pricing

    if ride.final_fare is None or ride.promo_code_id is not None or ride.share_discount_percent_at_ride > 0:
        return None
    subscription = await current(session, ride.rider_id)
    if subscription is None:
        return None
    base = pricing.discountable(ride.final_fare, ride.captain_fees_at_ride)
    amount = await take_discount(
        session, subscription_id=subscription.id, ride_id=ride.id, base=base, currency=ride.currency
    )
    if amount <= 0:
        return None
    if subscription.bearer == RiderPlanBearer.CAPTAIN.value:
        ride.final_fare = pricing.round_money(ride.final_fare - amount, ride.currency)
        if ride.fare_lines is not None:
            ride.fare_lines = [*ride.fare_lines, pricing.FareLine("plan_discount", -amount).as_json()]
        return None
    payment = Payment(
        ride_id=ride.id,
        method=PaymentMethod.PROMO,
        amount=amount,
        currency=ride.currency,
        status=PaymentStatus.PENDING,
        # مفتاحٌ مشتقٌّ من الرحلة: إنهاءٌ يُعاد لا يخلق خصمين
        idempotency_key=f"plan:{ride.id}",
    )
    session.add(payment)
    await session.flush()
    return payment
