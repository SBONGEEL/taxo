"""ما يُبنى للعرض في «بين المدن» (SPEC §٦٣-ج/٧) — **مشتركٌ بين أبواب الكبتن والراكب**، وبلا موجِّه.

**وأسماءُ الركّاب للكبتن قبل الانطلاق بساعة، وأرقامُهم عند الانطلاق وحدَه** (سطرا الخصوصية في §٦٣-هـ).
"""


from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.core.deps import CurrentDriver, DbSession, RiderUser, SettingsWriter, StaffUser
from app.core.exceptions import NotFound
from app.models.enums import AuditAction, CountryCode
from app.models.intercity import IntercityBooking, IntercityPermit, IntercityRoute, IntercityTrip
from app.models.user import User
from app.schemas.intercity import (
    BookingIn,
    BookingOut,
    PermitIn,
    PermitOut,
    RouteIn,
    RouteOut,
    RoutePatch,
    TripIn,
    TripOut,
)
from app.services import audit, intercity


async def trip_out(session, trip: IntercityTrip, *, for_driver: bool = False) -> TripOut:
    route = await session.get(IntercityRoute, trip.route_id)
    passengers: list[dict] = []
    if for_driver and trip.status in ("open", "departed") and trip.departs_at - intercity._now() <= timedelta(hours=1):
        rows = await session.execute(
            select(User.name, User.phone, IntercityBooking.seats)
            .join(IntercityBooking, IntercityBooking.rider_id == User.id)
            .where(IntercityBooking.trip_id == trip.id, IntercityBooking.status == "booked")
        )
        for name, phone, seats in rows:
            passengers.append({"name": name, "seats": seats, "phone": phone if trip.status == "departed" else None})
    return TripOut(
        id=trip.id,
        route=RouteOut.model_validate(route),
        departs_at=trip.departs_at,
        seats_offered=trip.seats_offered,
        seats_booked=await intercity.booked_seats(session, trip.id),
        min_seats=trip.min_seats,
        price_car=trip.price_car_at_trip,
        price_seat=trip.price_seat_at_trip,
        currency=currency_for_country(route.country_code),
        status=trip.status,
        passengers=passengers,
    )


async def booking_out(session, row: IntercityBooking) -> BookingOut:
    return BookingOut(
        id=row.id,
        trip=await trip_out(session, await session.get(IntercityTrip, row.trip_id)),
        seats=row.seats,
        whole_car=row.whole_car,
        amount=row.amount,
        payment=row.payment,
        status=row.status,
    )
