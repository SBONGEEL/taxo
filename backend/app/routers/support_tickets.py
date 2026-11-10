"""**طلباتي** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٨ و٩) — «محادثة مع الدعم» و«نسيت شيئاً» و«شكوى على الرحلة» من التطبيقين."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile, status

from app.core.deps import CurrentUser, DbSession, RedisDep
from app.schemas.support_ticket import (
    SupportMessageIn,
    SupportMessageOut,
    SupportTicketDetailOut,
    SupportTicketOut,
)
from app.services import support_tickets

router = APIRouter(prefix="/support/tickets", tags=["support"])


def _out(ticket, role: str) -> SupportTicketOut:
    return SupportTicketOut(
        id=ticket.id,
        kind=ticket.kind,
        status=ticket.status,
        category=ticket.category,
        ride_id=ticket.ride_id,
        my_role=role,
        decision_reason=ticket.decision_reason,
        has_photo=ticket.photo_path is not None,
        created_at=ticket.created_at,
        last_message_at=ticket.last_message_at,
    )


@router.post("", response_model=SupportTicketDetailOut, status_code=status.HTTP_201_CREATED)
async def open_ticket(
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
    app: Annotated[Literal["rider", "driver"], Form()],
    kind: Annotated[Literal["support", "lost_item", "complaint"], Form()],
    body: Annotated[str, Form(min_length=1, max_length=2000)],
    ride_id: Annotated[uuid.UUID | None, Form()] = None,
    category: Annotated[str | None, Form(max_length=16)] = None,
    photo: Annotated[UploadFile | None, File(description="صورةٌ اختياريّة للشكوى")] = None,
) -> SupportTicketDetailOut:
    ticket = await support_tickets.open_ticket(
        session, redis, user=user, app=app, kind=kind, body=body, ride_id=ride_id, category=category, photo=photo
    )
    await session.commit()
    return await _detail(session, ticket, "user")


@router.get("", response_model=list[SupportTicketOut])
async def my_tickets(user: CurrentUser, session: DbSession) -> list[SupportTicketOut]:
    return [_out(ticket, "user" if ticket.user_id == user.id else "party") for ticket in await support_tickets.mine(session, user)]


async def _detail(session, ticket, role: str) -> SupportTicketDetailOut:
    rows = await support_tickets.messages(session, ticket.id)
    return SupportTicketDetailOut(
        **_out(ticket, role).model_dump(), messages=[SupportMessageOut.model_validate(row) for row in rows]
    )


@router.get("/{ticket_id}", response_model=SupportTicketDetailOut)
async def my_ticket(ticket_id: uuid.UUID, user: CurrentUser, session: DbSession) -> SupportTicketDetailOut:
    access = await support_tickets.for_member(session, ticket_id, user)
    return await _detail(session, access.ticket, access.role)


@router.post("/{ticket_id}/messages", response_model=SupportTicketDetailOut, status_code=status.HTTP_201_CREATED)
async def post_message(
    ticket_id: uuid.UUID, payload: SupportMessageIn, user: CurrentUser, session: DbSession, redis: RedisDep
) -> SupportTicketDetailOut:
    await support_tickets.post(session, redis, ticket_id=ticket_id, user=user, body=payload.body)
    await session.commit()
    access = await support_tickets.for_member(session, ticket_id, user)
    return await _detail(session, access.ticket, access.role)
