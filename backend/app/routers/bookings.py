"""الرحلات المجدولة — مسارُ الراكب (SPEC القسم 5.11، المرحلة 12-ط).

راوترٌ رقيق: يحلّ من له الحق ويستدعي `services/bookings.py`، والقواعدُ هناك.

**ولا مسارَ «نفّذ الآن»**: التنفيذُ ساعةٌ لا زرّ. ومن أراد رحلةً الآن يطلبها من
`POST /rides` — وزرٌّ يُنفّذ حجزاً قبل موعده يعني بابين يُنشئان رحلةً من حجزٍ
واحد، وسباقاً بينهما على نفس الصف.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.core.deps import DbSession, RiderUser
from app.models.booking import RideBooking
from app.models.ride import Ride
from app.schemas.booking import BookingCreate, BookingOut
from app.services import bookings as bookings_service
from app.services.directions import Coordinates

router = APIRouter(prefix="/me/bookings", tags=["bookings"])


async def _out(session, booking: RideBooking) -> BookingOut:
    """الحجزُ ومعه **حالُ رحلته مقروءةً من الرحلة** لا من عمودٍ ثانٍ."""
    ride_status = (
        await session.scalar(select(Ride.status).where(Ride.id == booking.ride_id))
        if booking.ride_id is not None
        else None
    )
    return BookingOut(
        **{
            field: getattr(booking, field)
            for field in (
                "id",
                "status",
                "scheduled_at",
                "vehicle_category",
                "gender_preference",
                "payment_method_hint",
                "pickup_lat",
                "pickup_lng",
                "pickup_address",
                "dropoff_lat",
                "dropoff_lng",
                "dropoff_address",
                "estimated_fare_at_booking",
                "ride_id",
                "cancelled_at",
                "created_at",
            )
        },
        ride_status=ride_status,
        currency=currency_for_country(booking.country_code),
    )


@router.get("", response_model=list[BookingOut])
async def list_my_bookings(rider: RiderUser, session: DbSession) -> list[BookingOut]:
    rows = await bookings_service.list_for_rider(session, rider.id)
    return [await _out(session, row) for row in rows]


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate, rider: RiderUser, session: DbSession
) -> BookingOut:
    """حجزٌ جديد — **ولا يمنعه أن يكون صاحبُه في رحلةٍ الآن**.

    الحجزُ ليس رحلة، فحدُّ «رحلةٌ نشطةٌ واحدة» لا محلَّ له هنا: من هو في رحلةٍ
    الآن له أن يحجز للغد. والفحصُ يقع لحظةَ التنفيذ حيث يعني شيئاً.
    """
    booking = await bookings_service.create(
        session,
        rider=rider,
        pickup=Coordinates(lat=payload.pickup.lat, lng=payload.pickup.lng),
        dropoff=Coordinates(lat=payload.dropoff.lat, lng=payload.dropoff.lng),
        scheduled_at=payload.scheduled_at,
        vehicle_category=payload.vehicle_category,
        pickup_address=payload.pickup_address,
        dropoff_address=payload.dropoff_address,
        gender_preference=payload.gender_preference,
        payment_method_hint=payload.payment_method_hint,
    )
    await session.commit()
    await session.refresh(booking)
    return await _out(session, booking)


@router.delete("/{booking_id}", response_model=BookingOut)
async def cancel_booking(
    booking_id: uuid.UUID, rider: RiderUser, session: DbSession
) -> BookingOut:
    """إلغاءٌ مجانيٌّ لحجزٍ لم يُنفَّذ — لا كرماً بل لأن لا كبتنَ تحرّك بعد."""
    booking = await bookings_service.get_for_rider(session, booking_id, rider.id)
    cancelled = await bookings_service.cancel(session, booking=booking, actor=rider)
    await session.commit()
    return await _out(session, cancelled)
