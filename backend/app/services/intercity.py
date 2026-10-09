"""بين المدن (SPEC §٦٣-ج/٧، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوق، والمالكُ يتحقّق من القانون قبل إشعاله**.

**الكبتنُ سيّدُ نفسه**: يعلن رحلتَه (`post_trip`) بالمقاعد وأقلِّ عددٍ ينطلق به، **ويلغيها قبل المهلة بلا أثر** (`cancel_trip`) فيُردّ
للركاب كاملاً؛ **وعند المهلة إن لم يبلغ المحجوزُ حدَّه تُلغى وحدَها بالردّ نفسِه** (`sweep`)؛ **وبعدها لا يلغي من التطبيق** (§٥-١/١٥).

**والمال**: المقعدُ من المحفظة يحفظه TAXO (`intercity_hold`) **ويُردّ كاملاً** عند الإلغاء (`intercity_refund`)، **ويصل الكبتنَ عند الإنهاء**
(`intercity_earning`) **وعليه العمولةُ بنسبته المجمَّدة لحظةَ الإعلان** بقيد `commission` القائم؛ **والسيارةُ كاملةً نقداً في يده** وعمولتُها
دَينٌ كعمولة رحلات النقد — **ونطاقُ السوق «غيرُ النقدية» يعفيها**.

**والأقفالُ في ترتيب `CLAUDE.md`**: صفُّ الرحلة أوّلاً (بمنزلة الرحلة) ثمّ الحجز ثمّ الكبتن ثمّ المحفظة.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import Conflict, FeatureDisabled, InsufficientBalance, InvalidInput, NotFound, PermissionDenied
from app.models.commission import CommissionSetting
from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import (
    CommissionAppliesTo,
    CountryCode,
    DriverDebtSource,
    DriverDebtStatus,
    DriverStatus,
    FeatureKey,
    RoundingSource,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.intercity import IntercityBooking, IntercityPermit, IntercityRoute, IntercityTrip
from app.models.service_setting import ServiceSetting
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services import debts, rounding, settings_service, test_accounts, wallet
from app.services.pricing import round_money

MIN_VEHICLE_YEAR = 2015
MIN_SEATS = 4


class IntercityUnavailable(FeatureDisabled):
    code = "intercity_unavailable"
    message = "رحلاتُ بين المدن غيرُ مفعّلةٍ في بلدك"


class NoPermit(PermissionDenied):
    code = "intercity_permit_required"
    message = "رحلاتُ بين المدن بتصريحٍ بعد فحص مركبتك — راجع الدعم"


def _now() -> datetime:
    return datetime.now(UTC)


async def require_enabled(session: AsyncSession, country: CountryCode) -> None:
    if not await settings_service.is_feature_enabled(session, country, FeatureKey.INTERCITY_ENABLED):
        raise IntercityUnavailable()


async def deadline_hours(session: AsyncSession, country: CountryCode) -> int:
    row = await session.get(ServiceSetting, country)
    return row.intercity_cancel_deadline_hours if row is not None else 2


# ------------------------------------------------------------------ اللوحة: التصريح


async def grant_permit(
    session: AsyncSession, *, admin: User, driver_id: uuid.UUID, vehicle_id: uuid.UUID, seats: int, insurance_expires_on: date
) -> IntercityPermit:
    """**بعد فحص المركبة** (نصُّ المالك): ٢٠١٥ فأحدث · ٤ مقاعد · تأمينٌ سارٍ — **يُفحص هنا لا في الواجهة**."""
    vehicle = await session.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.driver_id != driver_id:
        raise NotFound("المركبة غير موجودة")
    if (vehicle.year or 0) < MIN_VEHICLE_YEAR:
        raise InvalidInput(f"مركبةٌ من {MIN_VEHICLE_YEAR} فأحدث")
    if seats < MIN_SEATS:
        raise InvalidInput(f"{MIN_SEATS} مقاعد على الأقل")
    if insurance_expires_on <= date.today():
        raise InvalidInput("التأمينُ منتهٍ — يُمنح التصريحُ بتأمينٍ سارٍ")
    permit = IntercityPermit(
        driver_id=driver_id, vehicle_id=vehicle_id, seats=seats, insurance_expires_on=insurance_expires_on, granted_by=admin.id
    )
    session.add(permit)
    await session.flush()
    return permit


async def valid_permit(session: AsyncSession, driver_id: uuid.UUID) -> IntercityPermit | None:
    """**ساريٌ وغيرُ مسحوب** — والتأمينُ المنتهي يُسقطه وحدَه بلا مهمّة."""
    return await session.scalar(
        select(IntercityPermit)
        .where(
            IntercityPermit.driver_id == driver_id,
            IntercityPermit.revoked_at.is_(None),
            IntercityPermit.insurance_expires_on >= date.today(),
        )
        .order_by(IntercityPermit.insurance_expires_on.desc())
        .limit(1)
    )


# ------------------------------------------------------------------ الكبتن


async def post_trip(
    session: AsyncSession, *, driver: Driver, user: User, route_id: uuid.UUID, departs_at: datetime, seats: int, min_seats: int
) -> IntercityTrip:
    await require_enabled(session, user.country_code)
    if driver.status != DriverStatus.APPROVED:
        raise PermissionDenied("حساب الكبتن غير معتمد بعد")
    permit = await valid_permit(session, driver.id)
    if permit is None:
        raise NoPermit()
    route = await session.get(IntercityRoute, route_id)
    if route is None or not route.is_active or route.country_code != user.country_code:
        raise NotFound("المسار غير موجود")
    if not 1 <= seats <= permit.seats or not 1 <= min_seats <= seats:
        raise InvalidInput(f"المقاعدُ من 1 إلى {permit.seats}، وأقلُّ ما تنطلق به لا يزيد عليها")
    hours = await deadline_hours(session, user.country_code)
    if departs_at <= _now() + timedelta(hours=hours):
        raise InvalidInput(f"تُعلَن الرحلةُ قبل موعدها بأكثرَ من {hours} ساعة")
    trip = IntercityTrip(
        route_id=route.id,
        driver_id=driver.id,
        departs_at=departs_at,
        seats_offered=seats,
        min_seats=min_seats,
        price_car_at_trip=route.price_car,
        price_seat_at_trip=route.price_seat,
        commission_percent_at_trip=await settings_service.commission_percent_of_driver(session, driver, user.country_code),
        status="open",
    )
    session.add(trip)
    await session.flush()
    return trip


async def locked_trip(session: AsyncSession, trip_id: uuid.UUID) -> IntercityTrip:
    row = await session.scalar(
        select(IntercityTrip).where(IntercityTrip.id == trip_id).with_for_update().execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFound("الرحلة غير موجودة")
    return row


async def booked_seats(session: AsyncSession, trip_id: uuid.UUID) -> int:
    return await session.scalar(
        select(func.coalesce(func.sum(IntercityBooking.seats), 0)).where(
            IntercityBooking.trip_id == trip_id, IntercityBooking.status == "booked"
        )
    ) or 0


async def _refund_all(session: AsyncSession, trip: IntercityTrip) -> list[uuid.UUID]:
    """**كلُّ حجزٍ يُردّ كاملاً** — المقعدُ من المحفظة يعود إليها، والسيارةُ النقديّةُ لم يُدفع عنها شيء."""
    riders = []
    rows = list(
        await session.scalars(
            select(IntercityBooking).where(IntercityBooking.trip_id == trip.id, IntercityBooking.status == "booked").with_for_update()
        )
    )
    for booking in rows:
        await _refund(session, booking)
        riders.append(booking.rider_id)
    return riders


async def _refund(session: AsyncSession, booking: IntercityBooking) -> None:
    if booking.payment == "wallet":
        rider = await session.get(User, booking.rider_id)
        assert rider is not None
        await wallet.lock_wallet(session, rider.id)
        await wallet.record(
            session,
            owner=rider,
            owner_type=WalletOwnerType.RIDER,
            tx_type=WalletTransactionType.INTERCITY_REFUND,
            amount=booking.amount,
            created_by=None,
            idempotency_key=f"intercity-refund:{booking.id}",
        )
        booking.status = "refunded"
    else:
        booking.status = "cancelled"
    booking.cancelled_at = _now()


async def cancel_trip(session: AsyncSession, *, trip_id: uuid.UUID, driver: Driver) -> list[uuid.UUID]:
    """**قبل المهلة بلا أثرٍ عليه، ويُردّ للركاب كاملاً** — وبعدها لا يُلغى من التطبيق (§٥-١/١٥ حتى جوابه)."""
    trip = await locked_trip(session, trip_id)
    if trip.driver_id != driver.id:
        raise NotFound("الرحلة غير موجودة")
    if trip.status != "open":
        raise Conflict("الرحلةُ ليست مفتوحة")
    route = await session.get(IntercityRoute, trip.route_id)
    hours = await deadline_hours(session, route.country_code)
    if _now() > trip.departs_at - timedelta(hours=hours):
        raise Conflict(f"فات موعدُ الإلغاء ({hours} ساعة قبل الانطلاق) — راجع الدعم")
    riders = await _refund_all(session, trip)
    trip.status = "cancelled"
    trip.cancelled_at = _now()
    trip.cancel_reason = "driver"
    await session.flush()
    return riders


async def depart(session: AsyncSession, *, trip_id: uuid.UUID, driver: Driver) -> IntercityTrip:
    trip = await locked_trip(session, trip_id)
    if trip.driver_id != driver.id:
        raise NotFound("الرحلة غير موجودة")
    if trip.status != "open":
        raise Conflict("الرحلةُ ليست مفتوحة")
    if await booked_seats(session, trip.id) < 1:
        raise Conflict("لا حجزَ على الرحلة")
    trip.status = "departed"
    trip.departed_at = _now()
    await session.flush()
    return trip


async def _booking_differences(session: AsyncSession, booking_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    """**فرقُ تقريب كلِّ حجزٍ من السجلّ** (`intercity_booking`) — وحجزٌ بلا صفٍّ غائبٌ عن القاموس (فرقُه صفر)."""
    if not booking_ids:
        return {}
    from app.models.rounding import MoneyRounding

    rows = await session.execute(
        select(MoneyRounding.source_id, MoneyRounding.difference).where(
            MoneyRounding.source_kind == RoundingSource.INTERCITY_BOOKING.value,
            MoneyRounding.source_id.in_(booking_ids),
        )
    )
    return {source_id: difference for source_id, difference in rows}


async def complete(session: AsyncSession, *, trip_id: uuid.UUID, driver: Driver) -> Decimal:
    """**يصل الكبتنَ مالُ المقاعد المحفوظ وعليه العمولة؛ والنقدُ في يده وعمولتُه دَين** — مرّةً واحدة (الحالُ ومفاتيحُ التكرار)."""
    trip = await locked_trip(session, trip_id)
    if trip.driver_id != driver.id:
        raise NotFound("الرحلة غير موجودة")
    if trip.status != "departed":
        raise Conflict("الرحلةُ لم تنطلق بعد")
    route = await session.get(IntercityRoute, trip.route_id)
    rows = list(
        await session.scalars(
            select(IntercityBooking).where(IntercityBooking.trip_id == trip.id, IntercityBooking.status == "booked").with_for_update()
        )
    )
    held = round_money(sum((b.amount for b in rows if b.payment == "wallet"), Decimal(0)))
    cash = round_money(sum((b.amount for b in rows if b.payment == "cash"), Decimal(0)))
    # **والعمولةُ على المسعَّر لا على المقرَّب** (SPEC §٧٠-ج/٤ و/٧، مراجعةُ المال البند ٤): الكبتنُ يقبض ما دفعه الركّابُ مقرَّباً،
    # **وفرقُ تقريب كلِّ حجزٍ له أو عليه** — فيُطرح من وعاء العمولة، **المحفظةُ وحدَها والنقدُ وحدَه**. ومن السجلّ لا من عمودٍ ثانٍ؛
    # **وبلا صفٍّ (مطفأٌ أو مضاعفٌ أصلاً) الوعاءُ هو المبلغُ حرفاً كما كان**
    differences = await _booking_differences(session, [b.id for b in rows])

    def _priced(total: Decimal, channel: str) -> Decimal:
        return round_money(
            total - sum((differences.get(b.id, Decimal(0)) for b in rows if b.payment == channel), Decimal(0))
        )

    held_priced, cash_priced = _priced(held, "wallet"), _priced(cash, "cash")
    for booking in rows:
        booking.status = "completed"
    trip.status = "completed"
    trip.completed_at = _now()

    await session.refresh(driver, with_for_update=True)
    driver_user = await session.get(User, driver.user_id)
    assert driver_user is not None
    percent = trip.commission_percent_at_trip
    applies = await session.scalar(
        select(CommissionSetting.applies_to).where(CommissionSetting.country_code == route.country_code)
    )
    if held > 0:
        await wallet.lock_wallet(session, driver_user.id)
        await wallet.record(
            session,
            owner=driver_user,
            owner_type=WalletOwnerType.DRIVER,
            tx_type=WalletTransactionType.INTERCITY_EARNING,
            amount=held,
            created_by=driver_user.id,
            idempotency_key=f"intercity-earning:{trip.id}",
        )
        commission = round_money(held_priced * percent / 100) if applies is not None else Decimal(0)
        if commission > 0:
            await wallet.record(
                session,
                owner=driver_user,
                owner_type=WalletOwnerType.DRIVER,
                tx_type=WalletTransactionType.COMMISSION,
                amount=-commission,
                created_by=driver_user.id,
                idempotency_key=f"intercity-commission:{trip.id}",
            )
    if cash > 0 and applies is not None and applies != CommissionAppliesTo.CASHLESS_RIDES:
        owed = round_money(cash_priced * percent / 100)
        if owed > 0:
            session.add(
                DriverDebt(
                    driver_id=driver.id,
                    country_code=route.country_code,
                    source=DriverDebtSource.INTERCITY_COMMISSION,
                    amount=owed,
                    collected=Decimal("0"),
                    currency=currency_for_country(route.country_code),
                    status=DriverDebtStatus.OUTSTANDING,
                )
            )
            await session.flush()
            await debts.refresh_block(session, driver=driver, country=route.country_code)
    await session.flush()
    return held


# ------------------------------------------------------------------ الراكب


@dataclass(frozen=True, slots=True)
class Booked:
    booking: IntercityBooking
    trip: IntercityTrip


async def book(
    session: AsyncSession, *, rider: User, trip_id: uuid.UUID, seats: int, whole_car: bool
) -> IntercityBooking:
    """**قفلُ الرحلة قبل عدِّ مقاعدها** — حجزان معاً على آخر مقعدٍ لا يفوزان معاً. **والمقعدُ من المحفظة، والسيارةُ نقداً** (§٦٣-د/٨)."""
    await require_enabled(session, rider.country_code)
    trip = await locked_trip(session, trip_id)
    route = await session.get(IntercityRoute, trip.route_id)
    if trip.status != "open" or route.country_code != rider.country_code or trip.departs_at <= _now():
        raise Conflict("الرحلةُ ليست متاحةً للحجز")
    # **ولا مقعدَ في رحلةٍ من غير عالمه** (SPEC §٦٥-ج) — القائمةُ تخفيها، وهذا يمنع من التفَّ عليها بمعرّف؛ **والنصُّ نصُّ
    # الرحلة غير المتاحة** فلا يُعرف منه أن وراءها حسابَ تجربة
    if await test_accounts.is_test_driver(session, trip.driver_id) != rider.is_test:
        raise Conflict("الرحلةُ ليست متاحةً للحجز")
    taken = await booked_seats(session, trip.id)
    if whole_car:
        if taken > 0:
            raise Conflict("حُجزت مقاعدُ في هذه الرحلة — احجز مقعداً")
        seats, precise, payment = trip.seats_offered, trip.price_car_at_trip, "cash"
    else:
        if not 1 <= seats <= trip.seats_offered - taken:
            raise Conflict(f"المتاح {trip.seats_offered - taken} مقعداً")
        precise, payment = round_money(trip.price_seat_at_trip * seats), "wallet"
    # **ما يدفعه الراكبُ يُقرَّب مرّةً على مجموعه** (SPEC §٧٠-ج/٥) — المقاعدُ × السعر ثمّ التقريب، لا كلُّ مقعدٍ وحدَه؛ **والسيارةُ
    # النقديّةُ كذلك** (نقدٌ في يد الكبتن). **وردُّه وأجرُ الكبتن منه بعينه** (`_refund` · `complete`) بلا تقريبٍ ثانٍ، والعمولةُ
    # عليه بدقّتها (§٧٠-ج/٧). ومطفأً كما كان حرفاً
    policy = await rounding.policy_for(session, rider.country_code)
    amount = rounding.rounded(precise, policy)
    booking = IntercityBooking(trip_id=trip.id, rider_id=rider.id, seats=seats, whole_car=whole_car, amount=amount, payment=payment)
    session.add(booking)
    await session.flush()
    await rounding.record(
        session,
        country=rider.country_code,
        source=RoundingSource.INTERCITY_BOOKING,
        source_id=booking.id,
        user_id=rider.id,
        precise=precise,
        rounded_amount=amount,
        policy=policy,
    )
    if payment == "wallet":
        wallet.require_not_frozen(rider, WalletOwnerType.RIDER)
        await wallet.lock_wallet(session, rider.id)
        balance = await wallet.balance_of(session, rider, declared=WalletOwnerType.RIDER)
        if balance < amount:
            raise InsufficientBalance("رصيدُك لا يغطّي المقاعد — اشحن محفظتك أولاً")
        await wallet.record(
            session,
            owner=rider,
            owner_type=WalletOwnerType.RIDER,
            tx_type=WalletTransactionType.INTERCITY_HOLD,
            amount=-amount,
            created_by=rider.id,
            idempotency_key=f"intercity-hold:{booking.id}",
        )
    return booking


async def cancel_booking(session: AsyncSession, *, booking_id: uuid.UUID, rider: User) -> IntercityBooking:
    """**قبل الانطلاق يعود المالُ كاملاً** — لم يُقل غيرُه (§٥-١/١٤ حتى جوابه). والقفلُ: الرحلةُ ثمّ الحجز."""
    booking = await session.get(IntercityBooking, booking_id)
    if booking is None or booking.rider_id != rider.id:
        raise NotFound("الحجز غير موجود")
    trip = await locked_trip(session, booking.trip_id)
    booking = await session.scalar(
        select(IntercityBooking).where(IntercityBooking.id == booking_id).with_for_update().execution_options(populate_existing=True)
    )
    if booking.status != "booked" or trip.status != "open":
        raise Conflict("لا يُلغى هذا الحجزُ الآن")
    await _refund(session, booking)
    await session.flush()
    return booking


async def sweep(session: AsyncSession) -> dict[str, int]:
    """**عند المهلة: رحلةٌ لم يبلغ محجوزُها حدَّها الأدنى تُلغى وحدَها بالردّ الكامل** — كلُّ رحلةٍ في معاملتها."""
    cancelled = 0
    candidates = list(
        await session.scalars(select(IntercityTrip.id).where(IntercityTrip.status == "open", IntercityTrip.departs_at > _now()))
    )
    for trip_id in candidates:
        trip = await locked_trip(session, trip_id)
        route = await session.get(IntercityRoute, trip.route_id)
        hours = await deadline_hours(session, route.country_code)
        if trip.status != "open" or _now() < trip.departs_at - timedelta(hours=hours):
            await session.rollback()
            continue
        if await booked_seats(session, trip.id) >= trip.min_seats:
            await session.rollback()
            continue
        await _refund_all(session, trip)
        trip.status = "cancelled"
        trip.cancelled_at = _now()
        trip.cancel_reason = "min_seats"
        await session.commit()
        cancelled += 1
    return {"cancelled": cancelled}
