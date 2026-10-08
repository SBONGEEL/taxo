"""أبوابُ الراكب لـ«بين المدن» (SPEC §٦٣-ج/٧) — الرحلاتُ المفتوحةُ والحجزُ وإلغاؤه.

**`router` واحدٌ لكلِّ ملفّ** — `check:contract` يقرأ `@router` وأوّلَ `prefix`.
"""


from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.core.deps import CurrentDriver, DbSession, RiderUser, SettingsWriter, StaffUser
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode
from app.models.intercity import IntercityBooking, IntercityPermit, IntercityRoute, IntercityTrip
from app.models.user import User
from app.schemas.intercity import (
    BookingIn,
    IntercityBookingOut,
    PermitIn,
    PermitOut,
    RouteIn,
    RouteOut,
    RoutePatch,
    TripIn,
    TripOut,
)
from app.services import audit, intercity

from app.routers.intercity_common import booking_out, trip_out

router = APIRouter(prefix="/intercity", tags=["intercity"])


# ------------------------------------------------------------------ الراكب


@router.get("/trips", response_model=list[TripOut])
async def open_trips(rider: RiderUser, session: DbSession) -> list[TripOut]:
    await intercity.require_enabled(session, rider.country_code)
    rows = await session.scalars(
        select(IntercityTrip)
        .join(IntercityRoute, IntercityRoute.id == IntercityTrip.route_id)
        .join(Driver, Driver.id == IntercityTrip.driver_id)
        .join(User, User.id == Driver.user_id)
        .where(
            # **رحلاتُ عالمه وحدَه** (SPEC §٦٥-ج): رحلةُ كبتنِ التجربة لا يحجز فيها راكبٌ حقيقيٌّ مقعداً بماله، وراكبُ
            # التجربة لا يحجز عند كبتنٍ حقيقيّ — سوقٌ يلتقي فيه الطرفان خارج التوزيع (و`book` يسأل ثانيةً)
            User.is_test.is_(rider.is_test),
            IntercityRoute.country_code == rider.country_code,
            IntercityTrip.status == "open",
            IntercityTrip.departs_at > intercity._now(),
        )
        .order_by(IntercityTrip.departs_at)
        .limit(100)
    )
    return [await trip_out(session, row) for row in rows]


@router.post("/bookings", response_model=IntercityBookingOut, status_code=status.HTTP_201_CREATED)
async def book(payload: BookingIn, rider: RiderUser, session: DbSession) -> IntercityBookingOut:
    row = await intercity.book(session, rider=rider, trip_id=payload.trip_id, seats=payload.seats, whole_car=payload.whole_car)
    await session.commit()
    return await booking_out(session, row)


@router.get("/bookings", response_model=list[IntercityBookingOut])
async def my_bookings(rider: RiderUser, session: DbSession) -> list[IntercityBookingOut]:
    rows = await session.scalars(
        select(IntercityBooking).where(IntercityBooking.rider_id == rider.id).order_by(IntercityBooking.created_at.desc()).limit(50)
    )
    return [await booking_out(session, row) for row in rows]


@router.post("/bookings/{booking_id}/cancel", response_model=IntercityBookingOut)
async def cancel_booking(booking_id: uuid.UUID, rider: RiderUser, session: DbSession) -> IntercityBookingOut:
    row = await intercity.cancel_booking(session, booking_id=booking_id, rider=rider)
    await session.commit()
    return await booking_out(session, row)
