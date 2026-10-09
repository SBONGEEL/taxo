"""اشتراكُ الراكب — المشوارُ الثابت (SPEC §٦٣-ج/٦، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

**أربعةُ أبوابٍ للمال، وكلٌّ بمفتاح تكرار:**

1. **الشراء** (`purchase`): «السعرُ المجمَّد × عددُ الرحلات» من المحفظة مقدّماً (`commute_prepay`) — المالُ عند TAXO.
2. **كلُّ رحلةٍ تكتمل** (`settle_ride`): دفعةُ `commute` بسعرها المجمَّد تُسوّى فوراً **من المحفوظ** — فيقبض الكبتنُ ويُقتطع منه ما
   يُقتطع من أيِّ أجرة، ولا يدفع الراكبُ عند الوصول. **والحافزُ** إن ضبطه المالك (`commute_incentive`) من TAXO للكبتن المعتمد.
3. **ما لم يُستعمل** (`settle_unused`): عند نهاية الشهر أو الإلغاء، **كلُّ رحلةٍ لم تكتمل تعود بسعرها رصيداً لا نقداً** (`commute_credit`).

**والرحلاتُ تُولَّد حجوزاً** (`generate_for`) لليوم التالي بيوم السوق — فتمرّ بمنفّذ الحجوزات القائم، **والكبتنُ المعتمدُ يأخذها مباشرةً**
إن كان متاحاً (`take_for_approved`)، وإلا تُعرض على الجميع.

**والأقفالُ في ترتيب `CLAUDE.md`**: صفُّ الاشتراك (بمنزلة الطلب) ثمّ الكبتن ثمّ المحفظة.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, FeatureDisabled, InsufficientBalance, InvalidInput, NotFound
from app.models.booking import RideBooking
from app.models.driver import Driver
from app.models.enums import (
    BookingStatus,
    CountryCode,
    DriverStatus,
    FeatureKey,
    GenderPreference,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentStatus,
    RideStatus,
    RoundingSource,
    VehicleCategory,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.payment import Payment
from app.models.ride import Ride, make_point
from app.models.rider_subscription import ACTIVE, CANCELLED, ENDED, RiderSubscription
from app.models.service_setting import ServiceSetting
from app.models.user import User
from app.services import pricing, rounding, settings_service, test_accounts, wallet
from app.services.directions import Coordinates
from app.services.pricing import round_money


class CommuteUnavailable(FeatureDisabled):
    code = "rider_subscription_unavailable"
    message = "اشتراكُ المشوار الثابت غيرُ مفعّلٍ في بلدك"


@dataclass(frozen=True, slots=True)
class Plan:
    pickup: Coordinates
    dropoff: Coordinates
    pickup_address: str | None
    dropoff_address: str | None
    weekdays: int
    go_time: time
    return_time: time | None
    starts_on: date


@dataclass(frozen=True, slots=True)
class Quote:
    discount_percent: Decimal
    price_per_ride: Decimal
    rides_total: int
    total: Decimal
    ends_on: date
    #: **الشهرُ بالسعر الدقيق قبل تقريبه** (SPEC §٧٠-ج/٥) — يُكتب فرقُه في السجلّ عند الشراء، ولا يُعرض
    precise_total: Decimal | None = None
    rounding_policy: rounding.RoundingPolicy = rounding.DISABLED


async def settings_for(session: AsyncSession, country: CountryCode) -> ServiceSetting | None:
    if not await settings_service.is_feature_enabled(session, country, FeatureKey.RIDER_SUBSCRIPTION_ENABLED):
        return None
    row = await session.get(ServiceSetting, country)
    if row is None or row.commute_discount_percent <= 0:
        return None
    return row


def _month_end(start: date) -> date:
    """**شهرٌ من يوم البدء** — اليومُ نفسُه من الشهر التالي ناقصَ يوم، وآخرُ الشهر حين لا يوجد ذلك اليوم."""
    year, month = (start.year + (start.month // 12), start.month % 12 + 1)
    for day in (start.day, 30, 29, 28):
        try:
            return date(year, month, day) - timedelta(days=1)
        except ValueError:
            continue
    raise AssertionError("unreachable")


def ride_days(plan_weekdays: int, starts_on: date, ends_on: date, suspended: set[date] | None = None) -> list[date]:
    days = []
    current = starts_on
    while current <= ends_on:
        if plan_weekdays & (1 << current.weekday()) and current not in (suspended or set()):
            days.append(current)
        current += timedelta(days=1)
    return days


async def quote(session: AsyncSession, *, rider: User, plan: Plan) -> Quote:
    """**السعرُ يُحسب في الخلفية وحدَها** (§14): تقديرُ الطريق بسعر الاقتصادي × (١ − الخصم)، مجمَّداً للشهر كلِّه."""
    row = await settings_for(session, rider.country_code)
    if row is None:
        raise CommuteUnavailable()
    if not 1 <= plan.weekdays <= 127:
        raise InvalidInput("اختر يوماً واحداً على الأقل")
    from app.services.stats import country_today

    if plan.starts_on <= await country_today(session, rider.country_code):
        raise InvalidInput("يبدأ الاشتراكُ من الغد على الأقل")
    estimate = await pricing.estimate(
        session,
        country_code=rider.country_code,
        vehicle_category=VehicleCategory.ECONOMY,
        pickup=plan.pickup,
        dropoff=plan.dropoff,
    )
    base = pricing.discountable(estimate.fare, estimate.captain_fees)
    precise_per_ride = round_money(base * (Decimal(100) - row.commute_discount_percent) / 100)
    # **الخصمُ أوّلاً ثمّ يُقرَّب سعرُ الرحلة مرّةً** (SPEC §٧٠-أ/١٠ و§٧٠-ج/٥) — فالشهرُ مضاعفٌ بالبناء، **وكلُّ رحلةٍ تُدفع
    # للكبتن بسعرها المقرَّب** (`settle_ride`)، **وما لم يُستعمل يعود به** (`settle_unused`) بلا تقريبٍ ثانٍ. ومطفأً كما كان
    policy = await rounding.policy_for(session, rider.country_code)
    per_ride = rounding.rounded(precise_per_ride, policy)
    ends_on = _month_end(plan.starts_on)
    legs = 2 if plan.return_time is not None else 1
    rides_total = len(ride_days(plan.weekdays, plan.starts_on, ends_on)) * legs
    if rides_total == 0 or per_ride <= 0:
        raise InvalidInput("لا رحلاتَ في هذا الشهر بالأيام المختارة")
    return Quote(
        discount_percent=row.commute_discount_percent,
        price_per_ride=per_ride,
        rides_total=rides_total,
        total=round_money(per_ride * rides_total),
        ends_on=ends_on,
        precise_total=round_money(precise_per_ride * rides_total),
        rounding_policy=policy,
    )


async def purchase(session: AsyncSession, *, rider: User, plan: Plan) -> RiderSubscription:
    """**المالُ قبل الصفّ**: لا اشتراكَ لم يصل مالُه (قاعدةُ `driver_subscriptions`) — والقيدُ والصفُّ في معاملةٍ واحدة."""
    priced = await quote(session, rider=rider, plan=plan)
    wallet.require_not_frozen(rider, WalletOwnerType.RIDER)
    await wallet.lock_wallet(session, rider.id)
    balance = await wallet.balance_of(session, rider, declared=WalletOwnerType.RIDER)
    if balance < priced.total:
        raise InsufficientBalance("رصيدُك لا يغطّي الشهر — اشحن محفظتك أولاً")
    row = RiderSubscription(
        rider_id=rider.id,
        country_code=rider.country_code,
        pickup_lat=plan.pickup.lat,
        pickup_lng=plan.pickup.lng,
        pickup_address=plan.pickup_address,
        dropoff_lat=plan.dropoff.lat,
        dropoff_lng=plan.dropoff.lng,
        dropoff_address=plan.dropoff_address,
        weekdays=plan.weekdays,
        go_time=plan.go_time,
        return_time=plan.return_time,
        starts_on=plan.starts_on,
        ends_on=priced.ends_on,
        discount_percent=priced.discount_percent,
        price_per_ride=priced.price_per_ride,
        rides_total=priced.rides_total,
        amount_paid=priced.total,
        suspended_days=[],
        status=ACTIVE,
    )
    session.add(row)
    await session.flush()
    # **فرقُ الشهر كلِّه صفٌّ واحد** — ما دفعه الراكبُ فعلاً ناقصَ ما كان يدفعه بالسعر الدقيق
    if priced.precise_total is not None:
        await rounding.record(
            session,
            country=rider.country_code,
            source=RoundingSource.COMMUTE_PRICE,
            source_id=row.id,
            user_id=rider.id,
            precise=priced.precise_total,
            rounded_amount=priced.total,
            policy=priced.rounding_policy,
        )
    await wallet.record(
        session,
        owner=rider,
        owner_type=WalletOwnerType.RIDER,
        tx_type=WalletTransactionType.COMMUTE_PREPAY,
        amount=-priced.total,
        created_by=rider.id,
        idempotency_key=f"commute-prepay:{row.id}",
    )
    return row


async def locked(session: AsyncSession, subscription_id: uuid.UUID) -> RiderSubscription:
    row = await session.scalar(
        select(RiderSubscription)
        .where(RiderSubscription.id == subscription_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFound("الاشتراك غير موجود")
    return row


async def suspend(session: AsyncSession, *, subscription_id: uuid.UUID, rider: User, day: date) -> RiderSubscription:
    """**يومٌ يُعلَّق لا تُولَّد رحلتاه، ويُرحَّل إلى ما بعد آخر يوم** — بحدٍّ من اللوحة لكلِّ اشتراك."""
    row = await locked(session, subscription_id)
    if row.rider_id != rider.id or row.status != ACTIVE:
        raise NotFound("الاشتراك غير موجود")
    settings = await session.get(ServiceSetting, row.country_code)
    cap = settings.commute_max_suspend_days if settings is not None else 4
    days = {date.fromisoformat(d) for d in row.suspended_days}
    from app.services.stats import country_today

    if day <= await country_today(session, row.country_code):
        raise InvalidInput("يُعلَّق يومٌ قادمٌ لا يومُ اليوم")
    if day in days or not (row.weekdays & (1 << day.weekday())) or not row.starts_on <= day <= row.ends_on:
        raise InvalidInput("هذا اليومُ ليس من أيام مشوارك")
    if len(days) >= cap:
        raise Conflict(f"أقصى التعليق {cap} أيام")
    days.add(day)
    row.suspended_days = sorted(d.isoformat() for d in days)
    # **يُرحَّل إلى أوّل يومٍ من أيامه بعد آخر يوم** — فلا يخسر الراكبُ رحلةً دفعها
    extended = row.ends_on + timedelta(days=1)
    while not (row.weekdays & (1 << extended.weekday())):
        extended += timedelta(days=1)
    row.ends_on = extended
    await session.flush()
    return row


async def completed_rides(session: AsyncSession, subscription_id: uuid.UUID) -> int:
    return await session.scalar(
        select(func.count()).select_from(Ride).where(Ride.commute_id == subscription_id, Ride.status == RideStatus.COMPLETED)
    ) or 0


async def settle_unused(session: AsyncSession, row: RiderSubscription, *, status: str) -> Decimal:
    """**ما لم يُستعمل يعود رصيداً لا نقداً** (§٦٣-د/١٠، توصيتي) — **مرّةً واحدة** (`settled_at` ومفتاحُ التكرار معاً)."""
    if row.settled_at is not None:
        return Decimal("0.000")
    used = await completed_rides(session, row.id)
    unused = max(row.rides_total - used, 0)
    # **يُردّ كما دُفع ولا يُقرَّب ثانيةً** (SPEC §٧٠-أ/١٠): السعرُ المجمَّدُ قُرِّب عند الشراء (`quote`) فالرصيدُ مضاعفٌ بالبناء؛
    # **وشهرٌ اشتُري قبل الإشعال يعود بكسوره** — تقريبُ ردِّه يغيّر مالاً دُفع (§٧٠-أ/١١)
    credit = round_money(row.price_per_ride * unused)
    row.status = status
    row.settled_at = datetime.now().astimezone()
    if credit > 0:
        rider = await session.get(User, row.rider_id)
        assert rider is not None
        await wallet.lock_wallet(session, rider.id)
        await wallet.record(
            session,
            owner=rider,
            owner_type=WalletOwnerType.RIDER,
            tx_type=WalletTransactionType.COMMUTE_CREDIT,
            amount=credit,
            created_by=None,
            idempotency_key=f"commute-credit:{row.id}",
        )
    await session.flush()
    return credit


async def cancel(session: AsyncSession, *, subscription_id: uuid.UUID, rider: User) -> Decimal:
    """إلغاءُ الراكب — **حجوزُه القادمةُ تُلغى، وما لم يُستعمل يعود رصيداً**."""
    row = await locked(session, subscription_id)
    if row.rider_id != rider.id or row.status != ACTIVE:
        raise NotFound("الاشتراك غير موجود")
    pending = await session.scalars(
        select(RideBooking).where(RideBooking.commute_id == row.id, RideBooking.status == BookingStatus.PENDING).with_for_update()
    )
    for booking in pending:
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_by = rider.id
        booking.cancelled_at = datetime.now().astimezone()
    return await settle_unused(session, row, status=CANCELLED)


# ------------------------------------------------------------------ التوليد والتنفيذ


async def generate_for(session: AsyncSession, row: RiderSubscription, day: date) -> int:
    """حجزا يومٍ واحد (ذهابٌ وعودةٌ إن وُجدت) — **ويتجاهل ما وُلّد قبلُ** (الفهرسُ الفريدُ على الاشتراك والموعد)."""
    if row.status != ACTIVE or not row.starts_on <= day <= row.ends_on:
        return 0
    if not (row.weekdays & (1 << day.weekday())) or day.isoformat() in row.suspended_days:
        return 0
    from app.services.stats import _zone

    zone = await _zone(session, row.country_code)
    made = 0
    legs = [(row.go_time, False)] + ([(row.return_time, True)] if row.return_time is not None else [])
    for at, back in legs:
        scheduled = datetime.combine(day, at, tzinfo=zone)
        exists = await session.scalar(
            select(RideBooking.id).where(RideBooking.commute_id == row.id, RideBooking.scheduled_at == scheduled)
        )
        if exists is not None:
            continue
        start = (row.dropoff_lat, row.dropoff_lng, row.dropoff_address) if back else (row.pickup_lat, row.pickup_lng, row.pickup_address)
        end = (row.pickup_lat, row.pickup_lng, row.pickup_address) if back else (row.dropoff_lat, row.dropoff_lng, row.dropoff_address)
        session.add(
            RideBooking(
                rider_id=row.rider_id,
                country_code=row.country_code,
                pickup_point=make_point(start[0], start[1]),
                pickup_address=start[2],
                dropoff_point=make_point(end[0], end[1]),
                dropoff_address=end[2],
                vehicle_category=VehicleCategory.ECONOMY,
                gender_preference=GenderPreference.ANY,
                scheduled_at=scheduled,
                status=BookingStatus.PENDING,
                estimated_fare_at_booking=row.price_per_ride,
                commute_id=row.id,
            )
        )
        made += 1
    await session.flush()
    return made


async def run_daily(session: AsyncSession) -> dict[str, int]:
    """**الدورةُ اليوميّة**: حجوزُ الغد لكلِّ اشتراكٍ قائم، **وتسويةُ ما انتهى** — كلُّ اشتراكٍ في معاملته."""
    from app.services.stats import country_today

    generated = settled = 0
    rows = list(await session.scalars(select(RiderSubscription.id).where(RiderSubscription.status == ACTIVE)))
    for subscription_id in rows:
        row = await locked(session, subscription_id)
        today = await country_today(session, row.country_code)
        if row.ends_on < today:
            await settle_unused(session, row, status=ENDED)
            settled += 1
        else:
            generated += await generate_for(session, row, today + timedelta(days=1))
        await session.commit()
    return {"generated": generated, "settled": settled}


async def on_ride_created(session: AsyncSession, ride: Ride, booking: RideBooking) -> Ride | None:
    """**رحلةُ اليوم من الاشتراك**: سعرُها المجمَّد مكانَ التقدير (لا ذروةَ ولا مسافةَ فعليّة)، **والكبتنُ المعتمدُ يأخذها مباشرةً إن كان
    متاحاً** — معتمداً مشتركاً متصلاً بلا رحلة. يعيد الرحلةَ مسنَدةً، أو `None` فتُعرض على الجميع."""
    from app.services import rides as rides_service
    from app.services import subscriptions

    row = await session.get(RiderSubscription, booking.commute_id)
    if row is None:
        return None
    ride.commute_id = row.id
    ride.estimated_fare = row.price_per_ride
    ride.fare_lines = [pricing.FareLine("commute", row.price_per_ride).as_json()]
    ride.captain_fees_at_ride = Decimal("0.000")
    ride.facility_id = None
    await session.flush()
    if row.driver_id is None:
        return None
    driver = await session.get(Driver, row.driver_id)
    if (
        driver is None
        or driver.status != DriverStatus.APPROVED
        or not driver.is_online
        or driver.current_ride_id is not None
        or await subscriptions.current_subscription(session, driver.id) is None
    ):
        return None
    return await rides_service.take_reserved(session, ride.id, driver)


async def ride_price_difference(session: AsyncSession, ride: Ride) -> Decimal:
    """**فرقُ تقريب سعر الرحلة الواحدة** — سعرُها المقرَّب (`price_per_ride`) ناقصَ الدقيق (مراجعةُ المال البند ٥).

    **يُقرأ من صفِّ الشهر في السجلّ** (`commute_price`: فرقُ الشهر = فرقُ الرحلة × عددِها حرفاً، فالقسمةُ تامّة) — فلا عمودَ
    ثانٍ يحمل الدقيق. **ومنه يُخرج وعاءُ العمولة الفرقَ** (`payments._commission_amount`): العمولةُ على السعر المسعَّر `7.200`
    لا على المقرَّب `7.000` (§٧٠-ج/٧). **وصفرٌ بلا صفّ** — شهرٌ اشتُري مطفأً، أو سعرُه مضاعفٌ أصلاً، فالوعاءُ كما كان حرفاً.
    """
    row = await session.get(RiderSubscription, ride.commute_id) if ride.commute_id is not None else None
    if row is None or row.rides_total <= 0:
        return Decimal("0.000")
    month = await rounding.difference_of(session, RoundingSource.COMMUTE_PRICE, row.id)
    if month == 0:
        return Decimal("0.000")
    return round_money(month / row.rides_total)


async def settle_ride(session: AsyncSession, ride: Ride) -> None:
    """**رحلةٌ من الاشتراك اكتملت ⇒ تُدفع من المحفوظ** بقناة `commute` — ويقبض الكبتنُ سعرَها المجمَّد وعليه العمولة؛ **والحافزُ** إن
    ضبطه المالكُ للكبتن المعتمد. يُنادى من `complete_ride` والرحلةُ مقفولة."""
    from app.services import payments

    if ride.commute_id is None or ride.final_fare is None or ride.final_fare <= 0:
        return
    rider = await session.get(User, ride.rider_id)
    assert rider is not None
    payment = Payment(
        ride_id=ride.id,
        method=PaymentMethod.COMMUTE,
        amount=ride.final_fare,
        currency=ride.currency,
        status=PaymentStatus.PENDING,
        idempotency_key=f"commute:{ride.id}",
    )
    session.add(payment)
    await session.flush()
    await payments.settle(
        session, payment=payment, ride=ride, rider=rider, confirmed_by=PaymentConfirmedBy.SYSTEM, actor_id=None
    )
    row = await session.get(RiderSubscription, ride.commute_id)
    settings = await session.get(ServiceSetting, ride.country_code)
    precise_incentive = round_money(settings.commute_captain_incentive) if settings is not None else Decimal(0)
    # **الحافزُ مالٌ يقبضه الكبتنُ فيُقرَّب** (SPEC §٧٠-ج/٥)، وفرقُه صفٌّ بمعرّف الرحلة حين يُدفع. ومطفأً كما كان
    policy = await rounding.policy_for(session, ride.country_code)
    incentive = rounding.rounded(precise_incentive, policy)
    if row is not None and incentive > 0 and ride.driver_id is not None and ride.driver_id == row.driver_id:
        driver = await session.get(Driver, ride.driver_id)
        driver_user = await session.get(User, driver.user_id) if driver is not None else None
        # **كبتنُ التجربة لا حافزَ له** (SPEC §٦٥-ج/٢): الحافزُ مالٌ من TAXO بلا مدين — **يُتخطّى صامتاً**، والأجرةُ نفسُها
        # (`settle` فوق) مالُ الراكب المحفوظ فتمضي كما هي
        if driver_user is not None and not driver_user.is_test:
            await wallet.lock_wallet(session, driver_user.id)
            await wallet.record(
                session,
                owner=driver_user,
                owner_type=WalletOwnerType.DRIVER,
                tx_type=WalletTransactionType.COMMUTE_INCENTIVE,
                amount=incentive,
                ride_id=ride.id,
                created_by=None,
                idempotency_key=f"commute-incentive:{ride.id}",
            )
            await rounding.record(
                session,
                country=ride.country_code,
                source=RoundingSource.COMMUTE_INCENTIVE,
                source_id=ride.id,
                user_id=driver_user.id,
                precise=precise_incentive,
                rounded_amount=incentive,
                policy=policy,
            )


# ------------------------------------------------------------------ الكبتن المعتمد


async def open_offers(session: AsyncSession, *, driver: Driver, user: User) -> list[RiderSubscription]:
    """اشتراكاتٌ قائمةٌ بلا كبتنٍ معتمد في سوقه — **والأقربُ بدءاً أوّلاً**.

    **ومن عالمه وحدَه** (SPEC §٦٥-ج): مشوارُ راكبٍ حقيقيٍّ لا يُعرض على كبتن تجربة، ومشوارُ راكبِ التجربة لا يُعرض على
    كبتنٍ حقيقيّ — **وهذا سوقٌ يلتقي فيه الطرفان خارج التوزيع**، فلا يحرسه شرطُ `dispatch` (و`approve` يسأل ثانيةً).
    """
    if await settings_for(session, user.country_code) is None:
        return []
    return list(
        await session.scalars(
            select(RiderSubscription)
            .join(User, User.id == RiderSubscription.rider_id)
            .where(
                User.is_test.is_(user.is_test),
                RiderSubscription.status == ACTIVE,
                RiderSubscription.driver_id.is_(None),
                RiderSubscription.country_code == user.country_code,
            )
            .order_by(RiderSubscription.starts_on)
            .limit(50)
        )
    )


async def approve(session: AsyncSession, *, subscription_id: uuid.UUID, driver: Driver) -> RiderSubscription:
    """**يصير معتمداً بقبوله** — قفلُ الاشتراك قبل الفحص، فكبتنان معاً ⇒ واحد."""
    from app.services import subscriptions

    if driver.status != DriverStatus.APPROVED:
        raise Conflict("حساب الكبتن غير معتمد بعد")
    if await subscriptions.current_subscription(session, driver.id) is None:
        raise Conflict("المشاويرُ الثابتةُ للكباتن المشتركين")
    row = await locked(session, subscription_id)
    if row.status != ACTIVE:
        raise NotFound("الاشتراك غير موجود")
    # **ولا يُعتمد مشوارٌ من غير عالمه** (SPEC §٦٥-ج) — القائمةُ تخفيه، وهذا يمنع من التفَّ عليها بمعرّفٍ مكتوبٍ بيد.
    # **و«غير موجود»** لا «غير مسموح»: مشوارُ العالم الآخر لا وجودَ له لمن ليس منه
    if await test_accounts.is_test_user(session, row.rider_id) != await test_accounts.is_test_driver(
        session, driver.id
    ):
        raise NotFound("الاشتراك غير موجود")
    if row.driver_id is not None and row.driver_id != driver.id:
        raise Conflict("اعتمد هذا المشوارَ كبتنٌ آخر")
    row.driver_id = driver.id
    await session.flush()
    return row


async def release(session: AsyncSession, *, subscription_id: uuid.UUID, by_rider: User | None = None, driver: Driver | None = None) -> RiderSubscription:
    """**فكُّ الكبتن المعتمد** — من الراكب (يستبدله) أو من الكبتن نفسِه؛ فيعود الاشتراكُ مفتوحاً."""
    row = await locked(session, subscription_id)
    if by_rider is not None and row.rider_id != by_rider.id:
        raise NotFound("الاشتراك غير موجود")
    if driver is not None and row.driver_id != driver.id:
        raise NotFound("الاشتراك غير موجود")
    row.driver_id = None
    await session.flush()
    return row
