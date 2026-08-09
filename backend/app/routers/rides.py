from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep, RiderUser
from app.core.exceptions import PermissionDenied
from app.models.driver import Driver
from app.models.enums import RideStatus, UserRole
from app.models.ride import Ride
from app.schemas.ride import (
    CoordinatesIn,
    RideCancelRequest,
    RideCreateRequest,
    RideEstimateOut,
    RideEstimateRequest,
    RideOut,
)
from app.services import dispatch, pricing, rides as rides_service, tracking
from app.services.directions import Coordinates
from app.ws import events

router = APIRouter(prefix="/rides", tags=["rides"])


def _coords(value: CoordinatesIn) -> Coordinates:
    return Coordinates(lat=value.lat, lng=value.lng)


def _to_out(ride: Ride) -> RideOut:
    return RideOut.from_ride(ride)


async def _assigned_ride(
    session: AsyncSession, ride_id: uuid.UUID, driver: Driver
) -> Ride:
    """رحلة هذا الكبتن هو المُسند إليها — وإلا فلا شأن له بها."""
    ride = await rides_service.get_ride(session, ride_id)
    if ride.driver_id != driver.id:
        raise PermissionDenied("هذه الرحلة ليست مُسندة إليك")
    return ride


# ------------------------------------------------------------------ التسعير


@router.post("/estimate", response_model=RideEstimateOut)
async def estimate_ride(
    payload: RideEstimateRequest, rider: RiderUser, session: DbSession
) -> RideEstimateOut:
    """سعر مقدّر قبل تأكيد الطلب — بلا أي كتابة في القاعدة."""
    quote = await pricing.estimate(
        session,
        country_code=rider.country_code,
        vehicle_category=payload.vehicle_category,
        pickup=_coords(payload.pickup),
        dropoff=_coords(payload.dropoff),
    )
    return RideEstimateOut(
        country_code=quote.country_code,
        vehicle_category=quote.vehicle_category,
        currency=quote.currency,
        distance_km=quote.route.distance_km,
        duration_min=quote.route.duration_min,
        estimated_fare=quote.fare,
        minimum_fare_applied=quote.minimum_fare_applied,
    )


# -------------------------------------------------------------------- الطلب


@router.post("", response_model=RideOut, status_code=status.HTTP_201_CREATED)
async def request_ride(
    payload: RideCreateRequest, rider: RiderUser, session: DbSession
) -> RideOut:
    """يُنشئ الرحلة ويبدأ البحث عن كبتن فوراً (SPEC القسم 5).

    ترجع الرحلة بحالة `requested`؛ انتقالها إلى `searching` ثم إسنادها يصل
    الراكبَ عبر WebSocket، ويمكن استرجاعه في أي وقت من `GET /rides/me/active`.
    """
    ride = await rides_service.request_ride(
        session,
        rider=rider,
        pickup=_coords(payload.pickup),
        dropoff=_coords(payload.dropoff),
        vehicle_category=payload.vehicle_category,
        pickup_address=payload.pickup_address,
        dropoff_address=payload.dropoff_address,
    )
    await session.commit()
    # قراءة جديدة: خطا العرض والطول محسوبان في القاعدة ولا يعودان مع INSERT
    body = _to_out(await rides_service.get_ride(session, ride.id))
    # التوزيع بعد الـ commit وحده (مهمته تقرأ الرحلة من جلسة أخرى) وبعد بناء
    # الرد، فلا تسبق `searching` الجوابَ الذي يقول `requested`
    dispatch.start(ride.id)
    return body


# ------------------------------------------------------------------ القراءة


@router.get("/me", response_model=list[RideOut])
async def list_my_rides(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[RideOut]:
    """سجل الرحلات: للراكب رحلاته، وللكبتن ما أُسند إليه."""
    rides = await rides_service.list_rides_for_user(
        session, user, limit=limit, offset=offset
    )
    return [_to_out(ride) for ride in rides]


@router.get("/me/active", response_model=RideOut | None)
async def get_my_active_ride(user: CurrentUser, session: DbSession) -> RideOut | None:
    """آخر حالة للرحلة الجارية — عليها يعتمد الاسترجاع بعد انقطاع الاتصال."""
    ride = await rides_service.active_ride_for_user(session, user)
    return _to_out(ride) if ride is not None else None


@router.get("/{ride_id}", response_model=RideOut)
async def get_ride(ride_id: uuid.UUID, user: CurrentUser, session: DbSession) -> RideOut:
    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    return _to_out(ride)


# -------------------------------------------------------------- حالات الرحلة


@router.post("/{ride_id}/accept", response_model=RideOut)
async def accept_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    """قبول الطلب المعروض — لا يقبله غير المعروض عليه (SPEC القسم 5.3)."""
    ride = await rides_service.accept_ride(session, redis, ride_id, driver)
    await session.commit()

    # إيقاظ مهمة التوزيع لتتوقف، ثم إعلام الطرفين — كلاهما بعد الـ commit
    await dispatch.notify_accepted(redis, ride_id)
    await dispatch.release_offer(redis, ride_id, driver.id)
    await events.publish_ride_event(redis, ride, events.RideEvent.DRIVER_ASSIGNED)
    return _to_out(ride)


@router.post("/{ride_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> Response:
    """رفض الطلب أو تجاهله قبل انتهاء العدّاد (SPEC القسم 12.3).

    لا يمس حالة الرحلة: ينهي دور هذا الكبتن فقط فينتقل التوزيع للتالي بلا
    انتظار بقية المهلة.
    """
    await dispatch.require_offer(redis, ride_id, driver.id)
    await dispatch.notify_declined(redis, ride_id, driver.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{ride_id}/arrive", response_model=RideOut)
async def mark_arrived(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    ride = await rides_service.mark_arrived(
        session, await _assigned_ride(session, ride_id, driver)
    )
    await session.commit()
    await events.publish_ride_event(redis, ride, events.RideEvent.DRIVER_ARRIVED)
    return _to_out(ride)


@router.post("/{ride_id}/start", response_model=RideOut)
async def start_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    ride = await rides_service.start_ride(
        session, await _assigned_ride(session, ride_id, driver)
    )
    await session.commit()
    # من هنا يُراقَب اتصال الكبتن حتى نهاية الرحلة (SPEC القسم 5)
    tracking.start(ride.id)
    await events.publish_ride_event(redis, ride, events.RideEvent.RIDE_STARTED)
    return _to_out(ride)


@router.post("/{ride_id}/complete", response_model=RideOut)
async def complete_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    ride = await rides_service.complete_ride(
        session, await _assigned_ride(session, ride_id, driver), driver
    )
    await session.commit()
    await tracking.stop(ride.id)
    await events.publish_ride_event(redis, ride, events.RideEvent.RIDE_COMPLETED)
    return _to_out(ride)


@router.post("/{ride_id}/cancel", response_model=RideOut)
async def cancel_ride(
    ride_id: uuid.UUID,
    payload: RideCancelRequest,
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
) -> RideOut:
    """يلغيها الراكب صاحبها أو الكبتن المُسند إليها — لا أحد سواهما.

    الإدارة تقرأ الرحلات لكنها لا تلغيها من هنا؛ الملكية نفسها يفحصها
    `get_ride_for_user`.
    """
    if user.role not in (UserRole.RIDER, UserRole.DRIVER):
        raise PermissionDenied()

    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    was_searching = ride.status == RideStatus.SEARCHING

    ride = await rides_service.cancel_ride(
        session, ride, by_role=user.role, reason=payload.reason
    )
    await session.commit()

    if was_searching:
        # إلغاء أثناء البحث: تتوقف المهمة وتُطوى البطاقة من شاشة المعروض عليه
        await dispatch.stop(ride_id)
        await dispatch.withdraw_offer(session, redis, ride_id)
    await tracking.stop(ride_id)
    await events.publish_ride_event(redis, ride, events.RideEvent.RIDE_CANCELLED)
    return _to_out(ride)
