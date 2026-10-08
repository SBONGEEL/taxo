"""محادثاتُ الرحلات وبلاغاتُها في اللوحة (SPEC §٦٦-ب/١٠ و١٣) — **بصلاحيةٍ مستقلّةٍ لا يملكها أحدٌ افتراضاً، وكلُّ فتحٍ سطرٌ في التدقيق**.

**والصلاحيةُ نفسُها لقائمة البلاغات ولمعالجتها** (`trip_chats.read`): الصفُّ يحمل نصَّ الرسالة المبلَّغ عنها، **فقراءتُه قراءةُ
محادثة** — وصلاحيةٌ أضيقُ للبلاغات تفتح بابَ النصوص من جانبٍ آخر.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.deps import DbSession, TripChatsReader
from app.models.enums import CountryCode, RideMessageReportStatus
from app.schemas.trip_chat import (
    AdminChatMessageOut,
    AdminChatReportOut,
    AdminChatThreadOut,
    ChatReportHandleIn,
)
from app.services import trip_chat

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/rides/{ride_id}/chat", response_model=AdminChatThreadOut)
async def read_ride_chat(ride_id: uuid.UUID, admin: TripChatsReader, session: DbSession) -> AdminChatThreadOut:
    """**محادثةُ رحلة** — والقراءةُ نفسُها فعلٌ يُسأل عنه: من، وأيَّ محادثة، ومتى، وكم رسالة (`audit_logs`). **ولا تُعلَّم مقروءة.**"""
    thread = await trip_chat.admin_thread(session, ride_id=ride_id, actor=admin)
    await session.commit()
    ride, names = thread.ride, thread.names
    driver_user_id = ride.driver.user_id if ride.driver is not None else None
    return AdminChatThreadOut(
        ride_id=ride.id,
        country_code=ride.country_code,
        status=ride.status,
        rider_id=ride.rider_id,
        rider_name=names.get(ride.rider_id),
        driver_user_id=driver_user_id,
        driver_name=names.get(driver_user_id) if driver_user_id else None,
        messages=[
            AdminChatMessageOut(
                id=message.id,
                sender_role=message.sender_role,
                sender_id=message.sender_id,
                sender_name=names.get(message.sender_id) if message.sender_id else None,
                body=message.body,
                created_at=message.created_at,
                read_at=message.read_at,
                open_reports=thread.open_reports.get(message.id, 0),
            )
            for message in thread.messages
        ],
    )


@router.get("/chat-reports", response_model=list[AdminChatReportOut])
async def list_chat_reports(
    admin: TripChatsReader,
    session: DbSession,
    status: RideMessageReportStatus | None = None,
    country_code: CountryCode | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminChatReportOut]:
    """**«الرسائلُ المبلَّغُ عنها»** — المفتوحُ أوّلاً. **وفتحُ القائمة يُدقَّق**: فيها نصوصُ محادثات."""
    rows = await trip_chat.list_reports(
        session, actor=admin, status=status, country=country_code, limit=limit, offset=offset
    )
    await session.commit()
    return [AdminChatReportOut.of(row) for row in rows]


@router.post("/chat-reports/{report_id}/handle", response_model=AdminChatReportOut)
async def handle_chat_report(
    report_id: uuid.UUID, payload: ChatReportHandleIn, admin: TripChatsReader, session: DbSession
) -> AdminChatReportOut:
    """**«عولج»** بسطرٍ اختياريّ — مرّةً واحدة (`chat_report_already_handled`)، **ومعه يبدأ عدّادُ حذف المحادثة**."""
    row = await trip_chat.handle_report(session, report_id=report_id, actor=admin, note=payload.note)
    await session.commit()
    return AdminChatReportOut.of(row)
