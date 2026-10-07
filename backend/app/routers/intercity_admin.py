"""أبوابُ اللوحة لـ«بين المدن» (SPEC §٦٣-ج/٧) — المساراتُ والتصاريح.

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

router = APIRouter(prefix="/admin/intercity", tags=["admin-intercity"])


# ------------------------------------------------------------------ اللوحة


@router.get("/routes", response_model=list[RouteOut])
async def admin_routes(_staff: StaffUser, session: DbSession, country: CountryCode | None = None) -> list[RouteOut]:
    query = select(IntercityRoute).order_by(IntercityRoute.from_city)
    if country is not None:
        query = query.where(IntercityRoute.country_code == country)
    return [RouteOut.model_validate(row) for row in await session.scalars(query)]


@router.post("/routes", response_model=RouteOut, status_code=status.HTTP_201_CREATED)
async def create_route(payload: RouteIn, admin: SettingsWriter, session: DbSession) -> RouteOut:
    row = IntercityRoute(**payload.model_dump())
    session.add(row)
    await session.flush()
    await audit.record(session, actor=admin, action=AuditAction.CREATE, entity_type="intercity_route", entity_id=row.id,
                       details=payload.model_dump(mode="json"))
    await session.commit()
    return RouteOut.model_validate(row)


@router.patch("/routes/{route_id}", response_model=RouteOut)
async def update_route(route_id: uuid.UUID, payload: RoutePatch, admin: SettingsWriter, session: DbSession) -> RouteOut:
    row = await session.get(IntercityRoute, route_id)
    if row is None:
        raise NotFound("المسار غير موجود")
    changed = audit.apply_changes(row, payload.model_dump(exclude_unset=True))
    if changed:
        await audit.record(session, actor=admin, action=AuditAction.UPDATE, entity_type="intercity_route", entity_id=row.id,
                           changes=changed)
    await session.commit()
    await session.refresh(row)
    return RouteOut.model_validate(row)


@router.get("/permits", response_model=list[PermitOut])
async def admin_permits(_staff: StaffUser, session: DbSession, driver_id: uuid.UUID | None = None) -> list[PermitOut]:
    query = select(IntercityPermit).order_by(IntercityPermit.created_at.desc())
    if driver_id is not None:
        query = query.where(IntercityPermit.driver_id == driver_id)
    return [PermitOut.model_validate(row) for row in await session.scalars(query)]


@router.post("/drivers/{driver_id}/permit", response_model=PermitOut, status_code=status.HTTP_201_CREATED)
async def grant_permit(driver_id: uuid.UUID, payload: PermitIn, admin: SettingsWriter, session: DbSession) -> PermitOut:
    permit = await intercity.grant_permit(
        session, admin=admin, driver_id=driver_id, vehicle_id=payload.vehicle_id, seats=payload.seats,
        insurance_expires_on=payload.insurance_expires_on,
    )
    await audit.record(session, actor=admin, action=AuditAction.CREATE, entity_type="intercity_permit", entity_id=permit.id,
                       details=payload.model_dump(mode="json"))
    await session.commit()
    return PermitOut.model_validate(permit)


@router.post("/permits/{permit_id}/revoke", response_model=PermitOut)
async def revoke_permit(permit_id: uuid.UUID, admin: SettingsWriter, session: DbSession) -> PermitOut:
    permit = await session.get(IntercityPermit, permit_id)
    if permit is None:
        raise NotFound("التصريح غير موجود")
    if permit.revoked_at is None:
        permit.revoked_at = intercity._now()
        await audit.record(session, actor=admin, action=AuditAction.UPDATE, entity_type="intercity_permit", entity_id=permit.id,
                           details={"revoked": True})
    await session.commit()
    return PermitOut.model_validate(permit)


