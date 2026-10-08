"""محادثةُ الرحلة لطرفَيها (SPEC §٦٦-ب) — **المسارُ نفسُه للراكب وللكبتن، والملكيةُ من الرحلة لا من الدور**.

الراكبُ والكبتنُ يطرقان `/rides/{id}/chat` نفسَه؛ **والخدمةُ تقرأ أيَّ طرفٍ هو من الرحلة** (`trip_chat.party_of`) — كبابَي
`route` و`approach` القائمين — **وغيرُ الطرفين ٤٠٤ لا ٤٠٣**. والمنطقُ كلُّه في `services/trip_chat.py`، وهنا الالتزامُ والبثُّ بعده.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession, RedisDep
from app.models.trip_chat import MAX_BODY_CHARS
from app.schemas.ride_call import RideCallOut
from app.schemas.trip_chat import (
    ChatMessageIn,
    ChatMessageOut,
    ChatReportIn,
    ChatReportOut,
    ChatThreadOut,
)
from app.services import ride_calls, trip_chat

router = APIRouter(prefix="/rides", tags=["trip-chat"])


@router.get("/{ride_id}/chat", response_model=ChatThreadOut)
async def get_chat(ride_id: uuid.UUID, user: CurrentUser, session: DbSession, redis: RedisDep) -> ChatThreadOut:
    """**المحادثةُ لطرفها** — وفتحُها يعلّم رسائلَ الطرف الآخر مقروءةً ويُخبره بعد الالتزام. **ومقروءةٌ بعد الإغلاق.**"""
    thread = await trip_chat.read_thread(session, ride_id=ride_id, user=user)
    active = await ride_calls.current_for_ride(session, thread.ride.id)
    await session.commit()
    await trip_chat.announce_read(redis, thread)
    return ChatThreadOut(
        ride_id=thread.ride.id,
        open=thread.open,
        can_call=thread.can_call,
        unread=thread.unread,
        notice=trip_chat.IN_CHAT_NOTICE,
        max_chars=MAX_BODY_CHARS,
        messages=[ChatMessageOut.of(message, thread.party.side) for message in thread.messages],
        active_call=RideCallOut.of(active, user.id) if active is not None else None,
    )


@router.post("/{ride_id}/chat", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
async def send_chat(
    ride_id: uuid.UUID, payload: ChatMessageIn, user: CurrentUser, session: DbSession, redis: RedisDep
) -> ChatMessageOut:
    """**رسالةٌ إلى الطرف الآخر** — تُرفض بعد الإغلاق (`chat_closed`) وبرقمِ هاتفٍ (`chat_phone_number`) أو رابط (`chat_link`)
    **قبل أن تُحفظ**. والحدثُ والإشعارُ (بلا نصّ) بعد الالتزام."""
    message, party = await trip_chat.send(session, redis, ride_id=ride_id, user=user, body=payload.body)
    await session.commit()
    await trip_chat.deliver(session, redis, message, party)
    return ChatMessageOut.of(message, party.side)


@router.post("/{ride_id}/chat/{message_id}/report", response_model=ChatReportOut)
async def report_chat_message(
    ride_id: uuid.UUID, message_id: uuid.UUID, payload: ChatReportIn, user: CurrentUser, session: DbSession
) -> ChatReportOut:
    """**«أبلغ عن الرسالة»** — على رسالة الطرف الآخر وحدَها، **ومرّةً لكلِّ مُبلِّغ**: الضغطةُ الثانية تعيد البلاغَ نفسَه."""
    row = await trip_chat.report(
        session, ride_id=ride_id, message_id=message_id, user=user, reason=payload.reason, note=payload.note
    )
    await session.commit()
    return ChatReportOut(
        id=row.id, message_id=row.message_id, reason=row.reason, status=row.status, created_at=row.created_at
    )
