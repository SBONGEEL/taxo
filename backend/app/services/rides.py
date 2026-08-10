"""منطق الرحلة: الطلب والانتقالات بين الحالات (SPEC القسم 5).

كل تغيير حالة يمر من هنا لا من الراوتر، وكل انتقال يُفحص ضد
`ALLOWED_TRANSITIONS` قبل تنفيذه. الـ commit مسؤولية الراوتر.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.currency import currency_for_country
from app.core.exceptions import (
    InvalidRideTransition,
    NotFound,
    PermissionDenied,
    RideAlreadyActive,
)
from app.models.driver import Driver
from app.models.enums import DriverStatus, RideStatus, UserRole, VehicleCategory
from app.models.ride import (
    ACTIVE_DRIVER_STATUSES,
    ACTIVE_RIDER_STATUSES,
    Ride,
    make_point,
)
from app.models.user import User
from app.services import dispatch, pricing, route, settings_service
from app.services.directions import Coordinates, Route

# آلة الحالات — ما ليس هنا ممنوع (SPEC القسم 5)
ALLOWED_TRANSITIONS: dict[RideStatus, frozenset[RideStatus]] = {
    # لا قبول مباشر من `requested`: التوزيع هو من يعرض الرحلة، وأول ما يفعله
    # نقلها إلى `searching`. القبول بلا عرضٍ سابق ليس له باب في هذه الآلة.
    RideStatus.REQUESTED: frozenset(
        {
            RideStatus.SEARCHING,
            RideStatus.CANCELLED_BY_RIDER,
        }
    ),
    RideStatus.SEARCHING: frozenset(
        {
            RideStatus.ACCEPTED,
            RideStatus.CANCELLED_BY_RIDER,
            RideStatus.NO_DRIVER_FOUND,
        }
    ),
    RideStatus.ACCEPTED: frozenset(
        {
            RideStatus.ARRIVED,
            RideStatus.CANCELLED_BY_RIDER,
            RideStatus.CANCELLED_BY_DRIVER,
        }
    ),
    RideStatus.ARRIVED: frozenset(
        {
            RideStatus.IN_PROGRESS,
            RideStatus.CANCELLED_BY_RIDER,
            RideStatus.CANCELLED_BY_DRIVER,
        }
    ),
    # لا إلغاء بعد بدء الرحلة: الإنهاء هو المخرج الوحيد
    RideStatus.IN_PROGRESS: frozenset({RideStatus.COMPLETED}),
    RideStatus.COMPLETED: frozenset(),
    RideStatus.CANCELLED_BY_RIDER: frozenset(),
    RideStatus.CANCELLED_BY_DRIVER: frozenset(),
    RideStatus.NO_DRIVER_FOUND: frozenset(),
}

_LOAD_DRIVER_CARD = (
    selectinload(Ride.driver).selectinload(Driver.user),
    selectinload(Ride.driver).selectinload(Driver.vehicles),
)


def _now() -> datetime:
    return datetime.now(UTC)


async def _flush_and_reload(session: AsyncSession, ride: Ride) -> Ride:
    """يثبّت التعديل ثم يعيد قراءة الصف.

    خطا العرض والطول قيم محسوبة في القاعدة، وكل UPDATE يُبطلها — فبدون قراءة
    جديدة يحاول ORM تحميلها كسولاً وقت التسلسل ويفشل خارج سياق async.
    """
    await session.flush()
    return await get_ride(session, ride.id)


def _require_transition(ride: Ride, target: RideStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[ride.status]:
        raise InvalidRideTransition(
            f"لا يمكن الانتقال من «{ride.status.value}» إلى «{target.value}»"
        )


# ------------------------------------------------------------------ القراءة


async def get_ride(session: AsyncSession, ride_id: uuid.UUID) -> Ride:
    ride = await session.scalar(
        select(Ride).where(Ride.id == ride_id).options(*_LOAD_DRIVER_CARD)
    )
    if ride is None:
        raise NotFound("الرحلة غير موجودة")
    return ride


async def get_ride_for_user(
    session: AsyncSession, ride_id: uuid.UUID, user: User
) -> Ride:
    """الرحلة بعد التحقق من الملكية — لا IDOR (SPEC القسم 14)."""
    ride = await get_ride(session, ride_id)

    if user.role in (UserRole.ADMIN, UserRole.SUPPORT):
        return ride
    if ride.rider_id == user.id:
        return ride
    if ride.driver is not None and ride.driver.user_id == user.id:
        return ride

    # 404 لا 403: وجود الرحلة نفسه ليس معلومة يستحقها غير أطرافها
    raise NotFound("الرحلة غير موجودة")


async def active_ride_for_user(session: AsyncSession, user: User) -> Ride | None:
    """الرحلة الجارية للمستخدم — عليها يعتمد استرجاع الحالة بعد انقطاع (SPEC القسم 10)."""
    stmt = select(Ride).options(*_LOAD_DRIVER_CARD)

    if user.role == UserRole.DRIVER:
        driver_id = await session.scalar(select(Driver.id).where(Driver.user_id == user.id))
        stmt = stmt.where(
            Ride.driver_id == driver_id, Ride.status.in_(ACTIVE_DRIVER_STATUSES)
        )
    else:
        stmt = stmt.where(
            Ride.rider_id == user.id, Ride.status.in_(ACTIVE_RIDER_STATUSES)
        )

    return await session.scalar(stmt)


async def _rider_has_active_ride(session: AsyncSession, rider_id: uuid.UUID) -> bool:
    return (
        await session.scalar(
            select(Ride.id).where(
                Ride.rider_id == rider_id, Ride.status.in_(ACTIVE_RIDER_STATUSES)
            )
        )
    ) is not None


async def _driver_has_active_ride(session: AsyncSession, driver_id: uuid.UUID) -> bool:
    return (
        await session.scalar(
            select(Ride.id).where(
                Ride.driver_id == driver_id, Ride.status.in_(ACTIVE_DRIVER_STATUSES)
            )
        )
    ) is not None


async def list_rides_for_user(
    session: AsyncSession, user: User, *, limit: int, offset: int
) -> Sequence[Ride]:
    """رحلات المستخدم بدوره: الراكب رحلاته، والكبتن ما أُسند إليه."""
    stmt = select(Ride).options(*_LOAD_DRIVER_CARD)

    if user.role == UserRole.DRIVER:
        driver_id = await session.scalar(select(Driver.id).where(Driver.user_id == user.id))
        stmt = stmt.where(Ride.driver_id == driver_id)
    else:
        stmt = stmt.where(Ride.rider_id == user.id)

    stmt = stmt.order_by(Ride.created_at.desc()).limit(limit).offset(offset)
    return (await session.scalars(stmt)).all()


# ------------------------------------------------------------------- الطلب


async def request_ride(
    session: AsyncSession,
    *,
    rider: User,
    pickup: Coordinates,
    dropoff: Coordinates,
    vehicle_category: VehicleCategory,
    pickup_address: str | None = None,
    dropoff_address: str | None = None,
) -> Ride:
    """ينشئ رحلة بحالة `requested`.

    الإسناد لا يبدأ من هنا: الراوتر يُطلق `dispatch.start` **بعد الـ commit**،
    لأن مهمة التوزيع تقرأ الرحلة من جلسة أخرى فلا ترى ما لم يُثبَّت بعد.
    """
    if await _rider_has_active_ride(session, rider.id):
        raise RideAlreadyActive()

    # السعر يُعاد حسابه هنا ولا يُقرأ من طلب العميل مهما أرسل
    quote = await pricing.estimate(
        session,
        country_code=rider.country_code,
        vehicle_category=vehicle_category,
        pickup=pickup,
        dropoff=dropoff,
    )

    ride = Ride(
        rider_id=rider.id,
        country_code=rider.country_code,
        vehicle_category=vehicle_category,
        pickup_point=make_point(pickup.lat, pickup.lng),
        pickup_address=pickup_address,
        dropoff_point=make_point(dropoff.lat, dropoff.lng),
        dropoff_address=dropoff_address,
        status=RideStatus.REQUESTED,
        distance_km=quote.route.distance_km,
        duration_min=quote.route.duration_min,
        estimated_fare=quote.fare,
        currency=currency_for_country(rider.country_code),
        # تُجمَّد الآن ولا تُمس بعدها مهما تغيّر إعداد العمولة (SPEC القسم 4)
        commission_percent_at_ride=await settings_service.commission_percent_for(
            session, rider.country_code
        ),
    )
    session.add(ride)

    try:
        await session.flush()
    except IntegrityError as exc:
        # الفهرس الجزئي `uq_rides_active_rider` — طلبان متزامنان من نفس الراكب
        await session.rollback()
        raise RideAlreadyActive() from exc

    return ride


# -------------------------------------------------------------- الانتقالات


async def mark_searching(session: AsyncSession, ride: Ride) -> Ride:
    """بداية التوزيع — يستدعيها `services/dispatch.py` وحدها."""
    _require_transition(ride, RideStatus.SEARCHING)
    ride.status = RideStatus.SEARCHING
    return await _flush_and_reload(session, ride)


async def mark_no_driver_found(session: AsyncSession, ride: Ride) -> Ride:
    """نفدت المحاولات أو المهلة بلا قبول (SPEC القسم 5.3)."""
    _require_transition(ride, RideStatus.NO_DRIVER_FOUND)
    ride.status = RideStatus.NO_DRIVER_FOUND
    return await _flush_and_reload(session, ride)


async def accept_ride(
    session: AsyncSession, redis: Redis, ride_id: uuid.UUID, driver: Driver
) -> Ride:
    """قبول الكبتن للرحلة المعروضة عليه.

    لا يقبلها إلا من عُرضت عليه وضمن مهلته — التوزيع يعرضها على واحد في كل
    مرة (SPEC القسم 5.3)، فالقبول من كبتن آخر لا يكون إلا التفافاً على الدور.
    المرحلة 7 تضيف شرط الاشتراك الساري.
    """
    if driver.status != DriverStatus.APPROVED:
        raise PermissionDenied("حساب الكبتن غير معتمد بعد")
    await dispatch.require_offer(redis, ride_id, driver.id)
    if await _driver_has_active_ride(session, driver.id):
        raise RideAlreadyActive("لديك رحلة جارية بالفعل")

    # قفل الصف: كبتنان يضغطان «قبول» في نفس اللحظة لا يفوزان معاً
    ride = await session.scalar(
        select(Ride).where(Ride.id == ride_id).with_for_update()
    )
    if ride is None:
        raise NotFound("الرحلة غير موجودة")

    driver_user = await session.get(User, driver.user_id)
    if driver_user is None or driver_user.country_code != ride.country_code:
        raise PermissionDenied("الرحلة خارج نطاق بلدك")

    _require_transition(ride, RideStatus.ACCEPTED)

    ride.driver_id = driver.id
    ride.status = RideStatus.ACCEPTED
    ride.accepted_at = _now()
    driver.current_ride_id = ride.id

    try:
        return await _flush_and_reload(session, ride)
    except IntegrityError as exc:
        # الفهرس الجزئي `uq_rides_active_driver` — قبولان متزامنان لنفس الكبتن
        await session.rollback()
        raise RideAlreadyActive("لديك رحلة جارية بالفعل") from exc


async def mark_arrived(session: AsyncSession, ride: Ride) -> Ride:
    _require_transition(ride, RideStatus.ARRIVED)
    ride.status = RideStatus.ARRIVED
    ride.arrived_at = _now()
    return await _flush_and_reload(session, ride)


async def start_ride(session: AsyncSession, ride: Ride) -> Ride:
    _require_transition(ride, RideStatus.IN_PROGRESS)
    ride.status = RideStatus.IN_PROGRESS
    ride.started_at = _now()
    return await _flush_and_reload(session, ride)


async def complete_ride(session: AsyncSession, ride: Ride, driver: Driver) -> Ride:
    """إنهاء الرحلة وتثبيت `final_fare` (SPEC القسم 5.7/5.8).

    السعر النهائي = المقدّر، **إلا** أن تنحرف المسافة الفعلية المحسوبة من نقاط
    المسار انحرافاً كبيراً؛ فعندها يُعاد الحساب عليها بنفس تسعيرة الدولة
    والفئة. المدة تبقى المقدّرة: القسم 5.7 يبني إعادة الحساب على **المسافة**
    وحدها، وإقحامُ زمنٍ فعليٍّ لم يطلبه يحمّل الراكبَ ازدحامَ الطريق مرتين.

    غياب النقاط (تطبيقُ كبتنٍ صامت) يُبقي المقدَّر حكماً — لا تخمين لمسافة.
    تحصيل المبلغ نفسه في `services/payments.py` بعد هذه اللحظة.
    """
    _require_transition(ride, RideStatus.COMPLETED)
    ride.status = RideStatus.COMPLETED
    ride.completed_at = _now()

    actual_km = await route.actual_distance_km(session, ride.id)
    ride.actual_distance_km = actual_km
    ride.final_fare = await _final_fare(session, ride, actual_km)

    driver.current_ride_id = None
    return await _flush_and_reload(session, ride)


async def _final_fare(
    session: AsyncSession, ride: Ride, actual_km: Decimal | None
) -> Decimal:
    if actual_km is None or not route.deviates(ride.distance_km, actual_km):
        return ride.estimated_fare

    rule = await pricing.get_rule(session, ride.country_code, ride.vehicle_category)
    fare, _ = pricing.calculate_fare(
        rule, Route(distance_km=actual_km, duration_min=ride.duration_min)
    )
    return fare


async def cancel_ride(
    session: AsyncSession,
    ride: Ride,
    *,
    by_role: UserRole,
    reason: str | None = None,
) -> Ride:
    """إلغاء مجاني قبل القبول، وبرسوم بعده (SPEC القسم 5).

    الرسوم تُثبَّت على الرحلة هنا؛ تحصيلها مع بقية الدفع في المرحلة 6.
    """
    # قفل الصف قبل فحص الانتقال: قبولُ كبتنٍ وقع في هذه اللحظة لا يُدهس
    await session.refresh(ride, with_for_update=True)

    target = (
        RideStatus.CANCELLED_BY_DRIVER
        if by_role == UserRole.DRIVER
        else RideStatus.CANCELLED_BY_RIDER
    )
    _require_transition(ride, target)

    fee = Decimal("0.000")
    # لا رسوم على الكبتن الملغي — الرسم على من ألغى بعد ارتباط الطرفين
    if by_role == UserRole.RIDER and ride.status in (
        RideStatus.ACCEPTED,
        RideStatus.ARRIVED,
    ):
        rule = await pricing.get_rule(session, ride.country_code, ride.vehicle_category)
        fee = pricing.round_money(rule.cancellation_fee)

    ride.status = target
    ride.cancelled_at = _now()
    ride.cancelled_reason = reason
    ride.cancellation_fee = fee

    if ride.driver_id is not None:
        driver = await session.get(Driver, ride.driver_id)
        if driver is not None and driver.current_ride_id == ride.id:
            driver.current_ride_id = None

    return await _flush_and_reload(session, ride)
