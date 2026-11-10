"""**طابورُ الطلبات في اللوحة** (البندان ٨ و٩) — المحادثةُ بجانب الحساب وآخر رحلاته، والحسمُ بسبب، والإحصاء."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core import storage
from app.core.deps import DbSession, RedisDep, StaffUser
from app.core.exceptions import NotFound
from app.models.enums import CountryCode
from app.models.ride import Ride
from app.models.user import User
from app.schemas.support_ticket import (
    AdminAccountBrief,
    AdminDecisionIn,
    AdminRideBrief,
    AdminTicketDetailOut,
    AdminTicketOut,
    AdminTicketPage,
    SupportMessageIn,
    SupportMessageOut,
)
from app.services import support_tickets

router = APIRouter(prefix="/admin/support/tickets", tags=["admin"])


async def _names(session, ids) -> dict:
    wanted = {value for value in ids if value is not None}
    if not wanted:
        return {}
    rows = await session.execute(select(User.id, User.name).where(User.id.in_(wanted)))
    return dict(rows.all())


def _out(ticket, names: dict) -> AdminTicketOut:
    return AdminTicketOut(
        id=ticket.id,
        kind=ticket.kind,
        status=ticket.status,
        category=ticket.category,
        app=ticket.app,
        country_code=ticket.country_code.value if hasattr(ticket.country_code, "value") else str(ticket.country_code),
        ride_id=ticket.ride_id,
        user_id=ticket.user_id,
        user_name=names.get(ticket.user_id),
        against_user_id=ticket.against_user_id,
        against_name=names.get(ticket.against_user_id),
        needs_staff=ticket.needs_staff,
        decision_reason=ticket.decision_reason,
        handled_at=ticket.handled_at,
        has_photo=ticket.photo_path is not None,
        created_at=ticket.created_at,
        last_message_at=ticket.last_message_at,
    )


@router.get("", response_model=AdminTicketPage)
async def list_tickets(
    _staff: StaffUser,
    session: DbSession,
    status: Literal["active", "open", "in_review", "resolved", "rejected"] | None = None,
    kind: Literal["support", "lost_item", "complaint"] | None = None,
    country_code: CountryCode | None = None,
    waiting: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AdminTicketPage:
    found = await support_tickets.page(
        session, status=status, kind=kind, country=country_code, waiting_only=waiting, limit=limit, offset=offset
    )
    names = await _names(session, [t.user_id for t in found.rows] + [t.against_user_id for t in found.rows])
    return AdminTicketPage(items=[_out(t, names) for t in found.rows], total=found.total, waiting=found.waiting)


@router.get("/stats")
async def ticket_stats(_staff: StaffUser, session: DbSession, country_code: CountryCode | None = None, days: int = Query(default=90, ge=7, le=365)) -> dict:
    return await support_tickets.stats(session, country=country_code, days=days)


async def _detail(session, ticket) -> AdminTicketDetailOut:

    names = await _names(session, [ticket.user_id, ticket.against_user_id])
    owner = await session.get(User, ticket.user_id)
    rides = (
        await session.scalars(
            select(Ride)
            .where((Ride.rider_id == ticket.user_id) | (Ride.id == ticket.ride_id))
            .order_by(Ride.created_at.desc())
            .limit(5)
        )
    ).all()
    roles = sorted({str(getattr(role, "value", role)) for role in (getattr(owner, "roles", None) or [])}) if owner else []
    account = AdminAccountBrief(
        name=owner.name if owner else "—",
        phone=getattr(owner, "phone", None) if owner else None,
        roles=roles,
        created_at=owner.created_at if owner else ticket.created_at,
        rides=[AdminRideBrief(id=ride.id, status=str(getattr(ride.status, "value", ride.status)), created_at=ride.created_at) for ride in rides],
    )
    rows = await support_tickets.messages(session, ticket.id)
    return AdminTicketDetailOut(
        **_out(ticket, names).model_dump(),
        messages=[SupportMessageOut.model_validate(row) for row in rows],
        account=account,
    )


@router.get("/{ticket_id}", response_model=AdminTicketDetailOut)
async def get_ticket(ticket_id: uuid.UUID, _staff: StaffUser, session: DbSession) -> AdminTicketDetailOut:
    return await _detail(session, await support_tickets.get(session, ticket_id))


@router.post("/{ticket_id}/messages", response_model=AdminTicketDetailOut)
async def reply(ticket_id: uuid.UUID, payload: SupportMessageIn, staff: StaffUser, session: DbSession, redis: RedisDep) -> AdminTicketDetailOut:
    await support_tickets.staff_reply(session, redis, ticket_id=ticket_id, actor=staff, body=payload.body)
    await session.commit()
    return await _detail(session, await support_tickets.get(session, ticket_id))


@router.patch("/{ticket_id}", response_model=AdminTicketDetailOut)
async def decide(ticket_id: uuid.UUID, payload: AdminDecisionIn, staff: StaffUser, session: DbSession, redis: RedisDep) -> AdminTicketDetailOut:
    await support_tickets.decide(session, redis, ticket_id=ticket_id, actor=staff, status=payload.status, reason=payload.reason)
    await session.commit()
    return await _detail(session, await support_tickets.get(session, ticket_id))


@router.get("/{ticket_id}/photo")
async def ticket_photo(ticket_id: uuid.UUID, _staff: StaffUser, session: DbSession) -> FileResponse:
    ticket = await support_tickets.get(session, ticket_id)
    if not ticket.photo_path:
        raise NotFound("لا صورةَ مع هذا الطلب")
    path = storage.resolve(ticket.photo_path)
    return FileResponse(
        path,
        media_type=ticket.photo_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="ticket{path.suffix}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
