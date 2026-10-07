"""أبوابُ الكبتن لـ«بين المدن» (SPEC §٦٣-ج/٧) — يعلن رحلتَه ويلغيها قبل المهلة وينطلق وينهي.

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

from app.routers.intercity_common import booking_out, trip_out

router = APIRouter(prefix="/drivers/me/intercity", tags=["intercity"])


# ------------------------------------------------------------------ الكبتن


@router.get("/routes", response_model=list[RouteOut])
async def driver_routes(driver: CurrentDriver, session: DbSession) -> list[RouteOut]:
    user = await session.get(User, driver.user_id)
    rows = await session.scalars(
        select(IntercityRoute).where(IntercityRoute.country_code == user.country_code, IntercityRoute.is_active.is_(True))
    )
    return [RouteOut.model_validate(row) for row in rows]


@router.get("/trips", response_model=list[TripOut])
async def driver_trips(driver: CurrentDriver, session: DbSession) -> list[TripOut]:
    rows = await session.scalars(
        select(IntercityTrip).where(IntercityTrip.driver_id == driver.id).order_by(IntercityTrip.departs_at.desc()).limit(50)
    )
    return [await trip_out(session, row, for_driver=True) for row in rows]


@router.post("/trips", response_model=TripOut, status_code=status.HTTP_201_CREATED)
async def post_trip(payload: TripIn, driver: CurrentDriver, session: DbSession) -> TripOut:
    user = await session.get(User, driver.user_id)
    trip = await intercity.post_trip(
        session, driver=driver, user=user, route_id=payload.route_id, departs_at=payload.departs_at,
        seats=payload.seats, min_seats=payload.min_seats,
    )
    await session.commit()
    return await trip_out(session, trip, for_driver=True)


@router.post("/trips/{trip_id}/cancel", response_model=TripOut)
async def cancel_trip(trip_id: uuid.UUID, driver: CurrentDriver, session: DbSession) -> TripOut:
    await intercity.cancel_trip(session, trip_id=trip_id, driver=driver)
    await session.commit()
    return await trip_out(session, await session.get(IntercityTrip, trip_id), for_driver=True)


@router.post("/trips/{trip_id}/depart", response_model=TripOut)
async def depart_trip(trip_id: uuid.UUID, driver: CurrentDriver, session: DbSession) -> TripOut:
    trip = await intercity.depart(session, trip_id=trip_id, driver=driver)
    await session.commit()
    return await trip_out(session, trip, for_driver=True)


@router.post("/trips/{trip_id}/complete", response_model=TripOut)
async def complete_trip(trip_id: uuid.UUID, driver: CurrentDriver, session: DbSession) -> TripOut:
    await intercity.complete(session, trip_id=trip_id, driver=driver)
    await session.commit()
    return await trip_out(session, await session.get(IntercityTrip, trip_id), for_driver=True)


