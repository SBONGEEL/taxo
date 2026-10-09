"""الحجزُ المضمون (SPEC §٦٣-ج/٣، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

**حجزٌ مجدولٌ بعلامة** (`ride_bookings.guaranteed`) وثلاثةُ أشياءَ تزيد عليه:

1. **رسمٌ يحفظه TAXO** لحظةَ الحجز (`hold`): قيدٌ مدينٌ على الراكب بلا دائن، ثمّ **يصل الكبتنَ كاملاً حين تتمّ الرحلةُ معه في وقته**
   (`settle_on_complete`) **أو يُردّ** — ولا كبتنَ، أو تأخّر، أو أُلغي. **وكلُّ حالٍ لم يُقَل فيها شيءٌ يعيده إلى صاحبه.**
2. **كبتنٌ محجوزٌ مسبقاً** (`accept`) **يؤكّد قبل الموعد بساعة** (`confirm`) فتُنشأ الرحلةُ وتُسند إليه مباشرةً، **وبلا ردٍّ** في المهلة
   يُسحب منه بلا عقوبة (`sweep`).
3. **اعتذارُه بعد التأكيد** (`withdraw`): مبلغٌ يساوي الرسمَ من محفظته إلى الراكب **بقدر رصيده** (والباقي يُسجَّل ولا يُحصَّل —
   `APPROVALS-62` §٥-١/١٣)، وإنذار، **واعتذاران في شهرٍ يحجبانه شهراً**. والتقييمُ لا يُمسّ حتى جواب §٦٣-د/٤.

**والأقفالُ في ترتيب `CLAUDE.md`**: صفُّ الحجز (بمنزلة صفِّ الطلب) ثمّ الكبتن ثمّ المحفظة. **ولا قفلَ على الرحلة هنا قبل الحجز**: الرحلةُ
تُنشأ داخل التأكيد بعد قفل الحجز، ومسارُ الإنهاء يقفل الرحلةَ ثمّ يقرأ الحجزَ بقفلٍ بعده — الترتيبُ نفسُه في الاتجاهين.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    Conflict,
    FeatureDisabled,
    InsufficientBalance,
    NotFound,
    PermissionDenied,
    UnconfirmedPaymentBlocked,
)
from app.models.booking import RideBooking
from app.models.driver import Driver
from app.models.driver_warning import WARNING_GUARANTEE_WITHDRAWAL, DriverWarning
from app.models.enums import (
    BookingStatus,
    CountryCode,
    DriverStatus,
    FeatureKey,
    RideStatus,
    RoundingMode,
    RoundingSource,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.ride import Ride
from app.models.service_setting import ServiceSetting
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services import rounding, settings_service, subscriptions, test_accounts, wallet
from app.services.pricing import round_money

#: **لا يُطلب حجزٌ مضمونٌ قبل ساعتين من موعده** — ليتّسع لقبول كبتنٍ وتأكيدِه قبل الموعد بساعة
MIN_LEAD = timedelta(hours=2)

HELD = "held"
PAID = "paid"
REFUNDED = "refunded"


class GuaranteeUnavailable(FeatureDisabled):
    code = "guaranteed_booking_unavailable"
    message = "الحجزُ المضمون غيرُ مفعّلٍ في بلدك"


class GuaranteeTaken(Conflict):
    code = "guarantee_taken"
    message = "قبل هذا الحجزَ كبتنٌ آخر"


class GuaranteeNotYours(Conflict):
    code = "guarantee_not_yours"
    message = "هذا الحجزُ ليس محجوزاً لك"


class GuaranteeBanned(PermissionDenied):
    code = "guarantee_banned"
    message = "أنت محجوبٌ عن الحجوزات المضمونة مؤقّتاً"


def _now() -> datetime:
    return datetime.now(UTC)


async def _reload(session: AsyncSession, booking: RideBooking) -> RideBooking:
    """**يثبّت ثمّ يعيد قراءة الصف** — `pickup_lat`/`lng` أعمدةٌ محسوبةٌ في القاعدة يُبطلها كلُّ تعديل، فقراءتُها بعده تحميلٌ كسولٌ
    خارج سياق async (`MissingGreenlet`) — نفسُ `bookings._flush_and_reload` حرفاً، **وأمسكه أوّلُ تشغيلٍ لهذه الخدمة**.
    """
    await session.flush()
    await session.refresh(booking)
    return booking


async def settings_for(session: AsyncSession, country: CountryCode) -> ServiceSetting | None:
    return await session.get(ServiceSetting, country)


async def fee_for(session: AsyncSession, country: CountryCode) -> Decimal:
    """**الرسمُ إن كانت الخدمةُ متاحةً، وإلا صفر** — المفتاحُ مشتعلٌ **والرسمُ موجب** (صفرٌ يُخفيها)."""
    if not await settings_service.is_feature_enabled(session, country, FeatureKey.GUARANTEED_BOOKING_ENABLED):
        return Decimal("0.000")
    row = await settings_for(session, country)
    return round_money(row.guarantee_fee) if row is not None else Decimal("0.000")


# ------------------------------------------------------------------ الراكب


async def hold(session: AsyncSession, *, booking: RideBooking, rider: User, scheduled_at: datetime) -> None:
    """يحفظ الرسمَ من محفظة الراكب لحظةَ الحجز (§٦٣-د/٢، توصيتي) — **ويُرفض الحجزُ إن لم يكفِ الرصيد**.

    يُنادى من `bookings.create` قبل الـflush، **والقيدُ في المعاملة نفسِها**: حجزٌ بلا رسمٍ محفوظ أو رسمٌ بلا حجزٍ لا يقعان.

    **والرسمُ يُقرَّب هنا مرّةً** (SPEC §٧٠-ج/٥) ويُجمَّد مقرَّباً على الحجز — **فردُّه ووصولُه الكبتنَ وغرامتُه كلُّها من
    المجمَّد**: ما يُردّ يُردّ كما أُخذ بلا تقريبٍ ثانٍ. وصفُّه في السجلّ بمعرّف الحجز.
    """
    precise = await fee_for(session, rider.country_code)
    policy = await rounding.policy_for(session, rider.country_code)
    fee, _ = rounding.round_amount(precise, policy)
    if fee <= 0:
        raise GuaranteeUnavailable()
    if scheduled_at - _now() < MIN_LEAD:
        raise Conflict("الحجزُ المضمون قبل موعده بساعتين على الأقل")
    wallet.require_not_frozen(rider, WalletOwnerType.RIDER)
    await wallet.lock_wallet(session, rider.id)
    balance = await wallet.balance_of(session, rider, declared=WalletOwnerType.RIDER)
    if balance < fee:
        raise InsufficientBalance("رسمُ الضمان يُدفع من محفظتك — اشحنها أولاً")
    booking.guaranteed = True
    booking.guarantee_fee_at_booking = fee
    booking.guarantee_state = HELD
    await session.flush()
    await rounding.record(
        session,
        country=rider.country_code,
        source=RoundingSource.GUARANTEE_HOLD,
        source_id=booking.id,
        user_id=rider.id,
        precise=precise,
        rounded_amount=fee,
        policy=policy,
    )
    await wallet.record(
        session,
        owner=rider,
        owner_type=WalletOwnerType.RIDER,
        tx_type=WalletTransactionType.GUARANTEE_HOLD,
        amount=-fee,
        created_by=rider.id,
        idempotency_key=f"guarantee-hold:{booking.id}",
    )


async def _refund(session: AsyncSession, booking: RideBooking) -> bool:
    """يردّ الرسمَ المحفوظ إلى صاحبه — **مرّةً واحدة** (الحالُ ومفتاحُ التكرار معاً).

    **كما أُخذ بلا تقريبٍ ثانٍ** (SPEC §٧٠-أ/١٠): المجمَّدُ قُرِّب عند الحجز (`hold`)، **وحجزٌ قبل الإشعال يعود بكسوره** — تقريبُ
    ردِّه يغيّر مالاً أُخذ (§٧٠-أ/١١). وكذلك وصولُه الكبتنَ (`settle_on_complete`)."""
    if booking.guarantee_state != HELD:
        return False
    rider = await session.get(User, booking.rider_id)
    assert rider is not None
    await wallet.lock_wallet(session, rider.id)
    await wallet.record(
        session,
        owner=rider,
        owner_type=WalletOwnerType.RIDER,
        tx_type=WalletTransactionType.GUARANTEE_REFUND,
        amount=booking.guarantee_fee_at_booking,
        created_by=None,
        idempotency_key=f"guarantee-refund:{booking.id}",
    )
    booking.guarantee_state = REFUNDED
    await _reload(session, booking)
    return True


async def on_booking_cancelled(session: AsyncSession, booking: RideBooking) -> None:
    """إلغاءُ الراكب حجزَه — **الرسمُ يعود إليه** في كلِّ حال (§٦٣-د/١٢ لم يُجَب: المالُ يعود إلى صاحبه)، ويُفكّ الكبتن."""
    await _refund(session, booking)
    booking.driver_id = None


# ------------------------------------------------------------------ الكبتن


async def _locked(session: AsyncSession, booking_id: uuid.UUID) -> RideBooking:
    row = await session.scalar(
        select(RideBooking)
        .where(RideBooking.id == booking_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or not row.guaranteed:
        raise NotFound("الحجز غير موجود")
    return row


async def _eligible(session: AsyncSession, driver: Driver) -> None:
    if driver.status != DriverStatus.APPROVED:
        raise PermissionDenied("حساب الكبتن غير معتمد بعد")
    if driver.guarantee_banned_until is not None and driver.guarantee_banned_until > _now():
        raise GuaranteeBanned()
    if await subscriptions.current_subscription(session, driver.id) is None:
        raise PermissionDenied("الحجوزاتُ المضمونةُ للكباتن المشتركين")


async def open_offers(session: AsyncSession, *, driver: Driver, user: User) -> list[RideBooking]:
    """«عروضٌ تنتظرك»: حجوزٌ مضمونةٌ في سوقه **وفئةِ مركبته**، بلا كبتن، **في نافذة العرض قبل موعدها** — والأقربُ موعداً أوّلاً."""
    if driver.guarantee_banned_until is not None and driver.guarantee_banned_until > _now():
        return []
    row = await settings_for(session, user.country_code)
    if row is None or await fee_for(session, user.country_code) <= 0:
        return []
    categories = select(Vehicle.category).where(Vehicle.driver_id == driver.id)
    now = _now()
    return list(
        await session.scalars(
            select(RideBooking)
            .join(User, User.id == RideBooking.rider_id)
            .where(
                # **من عالمه وحدَه** (SPEC §٦٥-ج): حجزُ راكبٍ حقيقيٍّ لا يُعرض على كبتن تجربة ولا العكس — سوقٌ يلتقي
                # فيه الطرفان خارج التوزيع، فلا يحرسه شرطُ `dispatch` (و`accept` يسأل ثانيةً)
                User.is_test.is_(user.is_test),
                RideBooking.guaranteed.is_(True),
                RideBooking.status == BookingStatus.PENDING,
                RideBooking.driver_id.is_(None),
                RideBooking.country_code == user.country_code,
                RideBooking.vehicle_category.in_(categories),
                RideBooking.scheduled_at > now,
                RideBooking.scheduled_at <= now + timedelta(hours=row.guarantee_offer_hours),
            )
            .order_by(RideBooking.scheduled_at)
            .limit(50)
        )
    )


async def accept(session: AsyncSession, *, booking_id: uuid.UUID, driver: Driver, user: User) -> RideBooking:
    """**يقبله كبتنٌ واحد** — قفلُ صفِّ الحجز قبل الفحص، فكبتنان معاً ⇒ واحدٌ يفوز والآخرُ «قبله كبتنٌ آخر»."""
    await _eligible(session, driver)
    booking = await _locked(session, booking_id)
    if booking.country_code != user.country_code:
        raise NotFound("الحجز غير موجود")
    # **ولا يُقبل حجزٌ من غير عالمه** (SPEC §٦٥-ج) — القائمةُ تخفيه، وهذا يمنع من التفَّ عليها بمعرّف
    if await test_accounts.is_test_user(session, booking.rider_id) != user.is_test:
        raise NotFound("الحجز غير موجود")
    if booking.status is not BookingStatus.PENDING or booking.scheduled_at <= _now():
        raise Conflict("انتهى هذا الحجز")
    if booking.driver_id is not None:
        if booking.driver_id == driver.id:
            return booking
        raise GuaranteeTaken()
    booking.driver_id = driver.id
    booking.accepted_at = _now()
    booking.confirm_requested_at = None
    booking.confirmed_at = None
    return await _reload(session, booking)


async def withdraw(session: AsyncSession, *, booking_id: uuid.UUID, driver: Driver) -> DriverWarning | None:
    """**قبل «نعم» بلا أثر، وبعدها غرامةٌ وإنذارٌ** (§٦٣-ج/٣) — والحجزُ يعود مفتوحاً لغيره. يعيد الإنذارَ إن وقع."""
    booking = await _locked(session, booking_id)
    if booking.driver_id != driver.id:
        raise GuaranteeNotYours()
    if booking.status is not BookingStatus.PENDING:
        # **بعد «نعم» صارت رحلة**: الاعتذارُ عنها إلغاءُ رحلةٍ مسنَدة، ويمرّ بالحجز نفسِه لتُحسب عقوبتُه
        pass
    confirmed = booking.confirmed_at is not None
    booking.driver_id = None
    booking.accepted_at = None
    booking.confirm_requested_at = None
    booking.confirmed_at = None
    if not confirmed:
        await _reload(session, booking)
        return None
    warning = await _penalize(session, booking=booking, driver=driver)
    await _reload(session, booking)
    return warning


async def _penalize(session: AsyncSession, *, booking: RideBooking, driver: Driver) -> DriverWarning:
    """**الغرامةُ بقدر رصيده** والباقي يُسجَّل (§٥-١/١٣) · الإنذار · **والحجبُ عند العتبة** — بقفل صفِّ الكبتن ثمّ المحفظتين."""
    await session.refresh(driver, with_for_update=True)
    row = await settings_for(session, booking.country_code)
    threshold = row.guarantee_ban_threshold if row is not None else 2
    ban_days = row.guarantee_ban_days if row is not None else 30

    driver_user = await session.get(User, driver.user_id)
    rider = await session.get(User, booking.rider_id)
    assert driver_user is not None and rider is not None
    amount = booking.guarantee_fee_at_booking
    await wallet.lock_wallets(session, driver_user.id, rider.id)
    balance = await wallet.balance_of(session, driver_user, declared=WalletOwnerType.DRIVER)
    capped = round_money(min(max(balance, Decimal(0)), amount))
    # **الغرامةُ تُقرَّب للأدنى دائماً، أيّاً كان اتجاهُ السوق** (SPEC §٧٠-ج/٥): الرسمُ نفسُه مضاعفٌ (قُرِّب عند الحجز)، فلا
    # كسرَ إلا حين **يحدّها رصيدُه** — والرصيدُ هو ما جعلها كسراً. **وللأعلى أو للأقرب يأخذ أكثرَ ممّا يملك** فيرفضه الدفتر
    # (`balance_after >= 0`) أو يُسقط الاعتذار؛ **فللأدنى**: أكبرُ مضاعفٍ لا يتجاوز الرصيد — قاعدةُ المحفظة في الأجرة نفسُها
    # (§٧٠-ج/٤). **والكسرُ يبقى في محفظته**.
    #
    # **ويُكتب في موضعٍ واحد: `penalty_shortfall`** (= الرسم − المنقول) **لا في السجلّ أيضاً** (مراجعةُ المال البند ٩). كان صفٌّ في
    # `money_roundings` (المحدودُ ⇐ المنقول) **والنقصُ معاً يحملان الكسرَ نفسَه** — فمن يجمع ما لم يُحصَّل من الموضعين يعدّه مرّتين.
    # **والنقصُ هو الموضعُ لا السجلّ**: لم يُقرَّب مبلغٌ دفعه أحد (الرسمُ مضاعفٌ وصفُّ تقريبه كُتب عند الحجز)؛ **الكسرُ جزءٌ من غرامةٍ
    # لم تُحصَّل**، بقي في محفظة صاحبه ولم يتحرّك — وهو بعينه ما يعنيه «الباقي يُسجَّل» (§٥-١/١٣) وما يقرؤه كلُّ من يقرأ النقص
    down = rounding.toward(await rounding.policy_for(session, booking.country_code), RoundingMode.DOWN)
    moved, _ = rounding.round_amount(capped, down)
    warning = DriverWarning(
        driver_id=driver.id,
        kind=WARNING_GUARANTEE_WITHDRAWAL,
        booking_id=booking.id,
        penalty_amount=moved,
        penalty_shortfall=round_money(amount - moved),
    )
    session.add(warning)
    await session.flush()
    if moved > 0:
        await wallet.record(
            session,
            owner=driver_user,
            owner_type=WalletOwnerType.DRIVER,
            tx_type=WalletTransactionType.GUARANTEE_PENALTY,
            amount=-moved,
            created_by=driver_user.id,
            idempotency_key=f"guarantee-penalty:{warning.id}",
        )
        await wallet.record(
            session,
            owner=rider,
            owner_type=WalletOwnerType.RIDER,
            tx_type=WalletTransactionType.GUARANTEE_COMPENSATION,
            amount=moved,
            created_by=driver_user.id,
            idempotency_key=f"guarantee-compensation:{warning.id}",
        )
    since = _now() - timedelta(days=ban_days)
    count = await session.scalar(
        select(func.count()).select_from(DriverWarning).where(
            DriverWarning.driver_id == driver.id,
            DriverWarning.kind == WARNING_GUARANTEE_WITHDRAWAL,
            DriverWarning.created_at >= since,
        )
    )
    if count >= threshold:
        driver.guarantee_banned_until = _now() + timedelta(days=ban_days)
    # **ويُنقَص تقييمُه من المرّة الأولى** (§٦٤-د): الإنذارُ نفسُه نجمةٌ في متوسّطه، فيُعاد بناؤه الآن
    from app.services import ratings

    await ratings.refresh_driver_average(session, driver.id)
    await session.flush()
    return warning


def is_late(ride: Ride, booking: RideBooking, late_minutes: int, now: datetime | None = None) -> bool:
    """**تأخّر الكبتن أكثرَ من المهلة عن الموعد** — بوصوله إن وصل، وبالساعة إن لم يصل بعد."""
    deadline = booking.scheduled_at + timedelta(minutes=late_minutes)
    arrived = ride.arrived_at
    if arrived is not None:
        return arrived > deadline
    return (now or _now()) > deadline


async def booking_of_ride(session: AsyncSession, ride: Ride) -> RideBooking | None:
    if ride.scheduled_for is None:
        return None
    return await session.scalar(
        select(RideBooking)
        .where(RideBooking.ride_id == ride.id, RideBooking.guaranteed.is_(True))
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def settle_on_complete(session: AsyncSession, ride: Ride) -> None:
    """**تمّت الرحلةُ مع كبتنها في وقته ⇒ الرسمُ له كاملاً بلا عمولة؛ وإلا يُردّ.** يُنادى من `complete_ride` والرحلةُ مقفولة."""
    booking = await booking_of_ride(session, ride)
    if booking is None or booking.guarantee_state != HELD:
        return
    row = await settings_for(session, ride.country_code)
    late_minutes = row.guarantee_late_minutes if row is not None else 10
    if ride.driver_id != booking.driver_id or is_late(ride, booking, late_minutes):
        await _refund(session, booking)
        return
    driver = await session.get(Driver, ride.driver_id)
    driver_user = await session.get(User, driver.user_id) if driver is not None else None
    if driver_user is None:  # pragma: no cover - رحلةٌ مكتملةٌ بلا كبتن
        await _refund(session, booking)
        return
    await wallet.lock_wallet(session, driver_user.id)
    await wallet.record(
        session,
        owner=driver_user,
        owner_type=WalletOwnerType.DRIVER,
        tx_type=WalletTransactionType.GUARANTEE_FEE,
        amount=booking.guarantee_fee_at_booking,
        ride_id=ride.id,
        created_by=None,
        idempotency_key=f"guarantee-fee:{booking.id}",
    )
    booking.guarantee_state = PAID


async def free_cancel(session: AsyncSession, ride: Ride) -> bool:
    """**إلغاءُ الراكب مجّانيٌّ إن تأخّر الكبتنُ عن المهلة** — ويُردّ الرسم. يعيد `True` إن كان الإلغاءُ مجّانياً لهذا السبب."""
    booking = await booking_of_ride(session, ride)
    if booking is None:
        return False
    row = await settings_for(session, ride.country_code)
    late_minutes = row.guarantee_late_minutes if row is not None else 10
    late = is_late(ride, booking, late_minutes)
    # **وفي كلِّ إلغاءٍ يعود الرسمُ إلى صاحبه** — المتأخّرُ لا يستحقّه، وغيرُ المتأخّر سؤالٌ لم يُجَب (§٥-١/١٢)
    await _refund(session, booking)
    return late


# ------------------------------------------------------------------ التأكيد والدورة


async def confirm(session: AsyncSession, *, booking_id: uuid.UUID, driver: Driver) -> Ride:
    """**«نعم، في الطريق»** — تُنشأ الرحلةُ وتُسند إليه مباشرةً، فيراها في شاشة رحلته ولا يصله طلبٌ غيرُها حتى ينهيها.

    **ولا تأكيدَ قبل نافذته** (الموعدُ ناقصَ دقائق التأكيد): «نعم» قبل يومٍ تحبسه يوماً بلا طلبات. **وضغطتان معاً ⇒ رحلةٌ واحدة**: قفلُ
    صفِّ الحجز، والثانيةُ تجده `dispatched` فتعيد رحلتَه.
    """
    from app.services import bookings as bookings_service
    from app.services import rides as rides_service

    booking = await _locked(session, booking_id)
    if booking.driver_id != driver.id:
        raise GuaranteeNotYours()
    if booking.status is BookingStatus.DISPATCHED and booking.ride_id is not None:
        return await rides_service.get_ride(session, booking.ride_id)
    if booking.status is not BookingStatus.PENDING:
        raise Conflict("انتهى هذا الحجز")
    row = await settings_for(session, booking.country_code)
    confirm_minutes = row.guarantee_confirm_minutes if row is not None else 60
    if _now() < booking.scheduled_at - timedelta(minutes=confirm_minutes):
        raise Conflict(f"التأكيدُ قبل الموعد بـ{confirm_minutes} دقيقة")
    try:
        ride = await bookings_service.create_ride_for(session, booking)
    except UnconfirmedPaymentBlocked as blocked:
        # **منعُ الراكب بدفعٍ لم يُحسم يُقال للكبتن بلغته لا بلغة الراكب** (`design/PAYMENTS-UNCONFIRMED.md` §٧، SPEC §٦٤-ج —
        # مراجعةُ ٢٠٢٦-١٠-٠٧): كان يصله ردُّ الراكب حرفاً — «لا يمكن طلبُ رحلةٍ جديدةٍ…» — **وفي جسمه معرّفا دفعةِ رحلةٍ أخرى
        # للراكب**. فيُقال له ما يخصّه، **بلا معرّفٍ من مال غيره**؛ والحجزُ يبقى كما هو — دورةُ التنفيذ تحكم فيه عند موعده
        raise Conflict("لا يمكن تأكيدُ هذا الحجز الآن — على الراكب دفعٌ لم يُحسم بعد") from blocked
    ride = await rides_service.take_reserved(session, ride.id, driver)
    booking.ride_id = ride.id
    booking.status = BookingStatus.DISPATCHED
    booking.confirmed_at = _now()
    await session.flush()
    return ride


async def due_confirmations(session: AsyncSession) -> list[uuid.UUID]:
    """محجوزةٌ لكبتنٍ لم يُسأل بعد، **ودخلت نافذةَ التأكيد** — يُسأل «هل أنت في الطريق؟»."""
    return list(
        await session.scalars(
            select(RideBooking.id)
            .join(ServiceSetting, ServiceSetting.country_code == RideBooking.country_code)
            .where(
                RideBooking.guaranteed.is_(True),
                RideBooking.status == BookingStatus.PENDING,
                RideBooking.driver_id.is_not(None),
                RideBooking.confirm_requested_at.is_(None),
                RideBooking.scheduled_at
                <= func.now() + func.make_interval(0, 0, 0, 0, 0, ServiceSetting.guarantee_confirm_minutes),
            )
            .limit(100)
        )
    )


async def expired_confirmations(session: AsyncSession) -> list[uuid.UUID]:
    """سُئل ولم يُجب في المهلة — **يُسحب منه بلا عقوبة** ويعود الحجزُ مفتوحاً."""
    return list(
        await session.scalars(
            select(RideBooking.id)
            .join(ServiceSetting, ServiceSetting.country_code == RideBooking.country_code)
            .where(
                RideBooking.guaranteed.is_(True),
                RideBooking.status == BookingStatus.PENDING,
                RideBooking.driver_id.is_not(None),
                RideBooking.confirmed_at.is_(None),
                RideBooking.confirm_requested_at.is_not(None),
                RideBooking.confirm_requested_at
                <= func.now() - func.make_interval(0, 0, 0, 0, 0, ServiceSetting.guarantee_confirm_window_minutes),
            )
            .limit(100)
        )
    )


async def ask(session: AsyncSession, booking_id: uuid.UUID) -> RideBooking | None:
    booking = await _locked(session, booking_id)
    if booking.driver_id is None or booking.confirm_requested_at is not None or booking.status is not BookingStatus.PENDING:
        return None
    booking.confirm_requested_at = _now()
    return await _reload(session, booking)


async def drop_unanswered(session: AsyncSession, booking_id: uuid.UUID) -> tuple[RideBooking, uuid.UUID] | None:
    """يعيد الحجزَ والكبتنَ الذي سُحب منه — أو `None` إن أجاب بين الاختيار والقفل."""
    booking = await _locked(session, booking_id)
    if (
        booking.driver_id is None
        or booking.confirmed_at is not None
        or booking.confirm_requested_at is None
        or booking.status is not BookingStatus.PENDING
    ):
        return None
    dropped = booking.driver_id
    booking.driver_id = None
    booking.accepted_at = None
    booking.confirm_requested_at = None
    return await _reload(session, booking), dropped


async def on_execute_without_captain(session: AsyncSession, booking: RideBooking) -> bool:
    """**حلّ موعدُ التنفيذ ولا كبتنَ أكّد** — يُردّ الرسمُ ويمضي الحجزُ رحلةً مجدولةً عاديّة. يعيد `True` إن رُدّ."""
    if not booking.guaranteed:
        return False
    booking.driver_id = None
    booking.accepted_at = None
    booking.confirm_requested_at = None
    refunded = await _refund(session, booking)
    await _reload(session, booking)
    return refunded


async def on_driver_cancelled(session: AsyncSession, ride: Ride, driver: Driver) -> DriverWarning | None:
    """**الكبتنُ يلغي رحلةَ حجزٍ مضمونٍ أكّده** — اعتذارٌ بعد التأكيد بعقوبته، **ويعود الحجزُ مفتوحاً** لغيره أو للتنفيذ العاديّ."""
    booking = await booking_of_ride(session, ride)
    if booking is None or booking.driver_id != driver.id or booking.confirmed_at is None:
        return None
    booking.status = BookingStatus.PENDING
    booking.ride_id = None
    booking.driver_id = None
    booking.accepted_at = None
    booking.confirm_requested_at = None
    booking.confirmed_at = None
    return await _penalize(session, booking=booking, driver=driver)


async def cancel_cost(
    session: AsyncSession, *, ride_id: uuid.UUID, driver: Driver
) -> tuple[RideBooking | None, ServiceSetting | None, CountryCode]:
    """**ما يكلّفه الكبتنَ إلغاءُ رحلته الآن** — يُقرأ في ورقة الإلغاء قبل «تأكيد الإلغاء» (الشكلُ الثالثَ عشر: **مالٌ يخرج من جيبه
    ولا يظهر على شاشة**). حجزٌ مضمونٌ أكّده هو ⇒ الحجزُ ورسمُه؛ وإلا `None`.

    **قراءةٌ بلا قفل**: لا تغيّر حالاً، **والإلغاءُ نفسُه يعيد الفحصَ تحت قفله** (`on_driver_cancelled`) — فما تقوله الورقةُ
    وصفٌ لحظةَ فتحها لا وعد. **ورحلةُ غيره ٤٠٤** (لا IDOR) كما في كلِّ بابٍ يمسّ رحلة."""
    ride = await session.get(Ride, ride_id)
    if ride is None or ride.driver_id != driver.id:
        raise NotFound("الرحلة غير موجودة")
    booking = await session.scalar(
        select(RideBooking).where(
            RideBooking.ride_id == ride.id,
            RideBooking.guaranteed.is_(True),
            RideBooking.driver_id == driver.id,
            RideBooking.confirmed_at.is_not(None),
        )
    )
    return booking, await settings_for(session, ride.country_code), ride.country_code


async def sweep(session: AsyncSession, redis: Redis) -> dict[str, int]:
    """**الدورةُ كلَّ دقيقة**: يُسأل من دخل نافذةَ التأكيد، ويُسحب من انقضت مهلتُه بلا ردّ — **كلُّ حجزٍ في معاملته** فلا يُسقط
    واحدٌ ما بعده، **والإشعارُ بعد الـcommit** (صندوقُ الوارد لا يكتب ما لم يقع)."""
    from app.services import notifications

    asked = dropped = 0
    for booking_id in await due_confirmations(session):
        booking = await ask(session, booking_id)
        if booking is None:
            await session.rollback()
            continue
        driver = await session.get(Driver, booking.driver_id)
        assert driver is not None
        driver_user_id = driver.user_id
        await session.commit()
        await notifications.publish_guarantee_confirm_request(
            session, redis, driver_user_id=driver_user_id, booking_id=booking_id
        )
        asked += 1
    for booking_id in await expired_confirmations(session):
        result = await drop_unanswered(session, booking_id)
        if result is None:
            await session.rollback()
            continue
        booking, driver_id = result
        rider_id = booking.rider_id
        driver = await session.get(Driver, driver_id)
        assert driver is not None
        driver_user_id = driver.user_id
        await session.commit()
        await notifications.publish_guarantee_dropped(
            session, redis, driver_user_id=driver_user_id, booking_id=booking_id
        )
        await notifications.publish_guarantee_reopened(session, redis, rider_id=rider_id, booking_id=booking_id)
        dropped += 1
    return {"asked": asked, "dropped": dropped}
