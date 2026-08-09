from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentDriver, CurrentUser, DbSession, RiderUser
from app.core.exceptions import PermissionDenied
from app.models.driver import Driver
from app.models.enums import UserRole
from app.models.ride import Ride
from app.schemas.ride import (
    CoordinatesIn,
    RideCancelRequest,
    RideCreateRequest,
    RideDriverOut,
    RideEstimateOut,
    RideEstimateRequest,
    RideOut,
    RideVehicleOut,
)
from app.services import pricing, rides as rides_service
from app.services.directions import Coordinates

router = APIRouter(prefix="/rides", tags=["rides"])


def _coords(value: CoordinatesIn) -> Coordinates:
    return Coordinates(lat=value.lat, lng=value.lng)


def _driver_card(ride: Ride) -> RideDriverOut | None:
    """بيانات الكبتن للراكب — تتطلب تحميل العلاقات مسبقاً (selectinload)."""
    if ride.driver is None:
        return None

    vehicles = ride.driver.vehicles
    return RideDriverOut(
        id=ride.driver.id,
        name=ride.driver.user.name,
        rating_avg=ride.driver.rating_avg,
        vehicle=RideVehicleOut.model_validate(vehicles[0]) if vehicles else None,
    )


def _to_out(ride: Ride) -> RideOut:
    return RideOut(
        id=ride.id,
        rider_id=ride.rider_id,
        status=ride.status,
        country_code=ride.country_code,
        vehicle_category=ride.vehicle_category,
        currency=ride.currency,
        pickup=CoordinatesIn(lat=ride.pickup_lat, lng=ride.pickup_lng),
        pickup_address=ride.pickup_address,
        dropoff=CoordinatesIn(lat=ride.dropoff_lat, lng=ride.dropoff_lng),
        dropoff_address=ride.dropoff_address,
        distance_km=ride.distance_km,
        duration_min=ride.duration_min,
        estimated_fare=ride.estimated_fare,
        final_fare=ride.final_fare,
        cancellation_fee=ride.cancellation_fee,
        commission_percent_at_ride=ride.commission_percent_at_ride,
        cancelled_reason=ride.cancelled_reason,
        driver=_driver_card(ride),
        created_at=ride.created_at,
        accepted_at=ride.accepted_at,
        arrived_at=ride.arrived_at,
        started_at=ride.started_at,
        completed_at=ride.completed_at,
        cancelled_at=ride.cancelled_at,
    )


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
    return _to_out(await rides_service.get_ride(session, ride.id))


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
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession
) -> RideOut:
    ride = await rides_service.accept_ride(session, ride_id, driver)
    await session.commit()
    return _to_out(ride)


@router.post("/{ride_id}/arrive", response_model=RideOut)
async def mark_arrived(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession
) -> RideOut:
    ride = await rides_service.mark_arrived(
        session, await _assigned_ride(session, ride_id, driver)
    )
    await session.commit()
    return _to_out(ride)


@router.post("/{ride_id}/start", response_model=RideOut)
async def start_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession
) -> RideOut:
    ride = await rides_service.start_ride(
        session, await _assigned_ride(session, ride_id, driver)
    )
    await session.commit()
    return _to_out(ride)


@router.post("/{ride_id}/complete", response_model=RideOut)
async def complete_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession
) -> RideOut:
    ride = await rides_service.complete_ride(
        session, await _assigned_ride(session, ride_id, driver), driver
    )
    await session.commit()
    return _to_out(ride)


@router.post("/{ride_id}/cancel", response_model=RideOut)
async def cancel_ride(
    ride_id: uuid.UUID,
    payload: RideCancelRequest,
    user: CurrentUser,
    session: DbSession,
) -> RideOut:
    """يلغيها الراكب صاحبها أو الكبتن المُسند إليها — لا أحد سواهما.

    الإدارة تقرأ الرحلات لكنها لا تلغيها من هنا؛ الملكية نفسها يفحصها
    `get_ride_for_user`.
    """
    if user.role not in (UserRole.RIDER, UserRole.DRIVER):
        raise PermissionDenied()

    ride = await rides_service.cancel_ride(
        session,
        await rides_service.get_ride_for_user(session, ride_id, user),
        by_role=user.role,
        reason=payload.reason,
    )
    await session.commit()
    return _to_out(ride)
