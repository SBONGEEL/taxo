"""عقدُ محادثة الرحلة (SPEC §٦٦-ب) — للطرفين، وللّوحة بصلاحيتها المستقلّة.

**ولا رقمَ هاتفٍ في شيءٍ منها**: الطرفان يقرآن الجانبَ («الراكب»/«الكبتن») لا الاسمَ ولا الرقم، **واللوحةُ تقرأ الأسماءَ وحدَها** —
ما يحتاجه من يعالج بلاغاً.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.models.enums import (
    CountryCode,
    RatingRaterType,
    RideMessageReportReason,
    RideMessageReportStatus,
    RideStatus,
)
from app.models.trip_chat import MAX_BODY_CHARS
from app.schemas.ride_call import RideCallOut

if TYPE_CHECKING:
    from app.models.trip_chat import RideMessage
    from app.services.trip_chat import ReportRow


class ChatMessageIn(BaseModel):
    #: **حتى ٣٠٠ حرف** — والقيدُ نفسُه في القاعدة. والفراغُ في الطرفين يُنزع قبل العدّ في الخدمة
    body: str = Field(min_length=1, max_length=MAX_BODY_CHARS)


class ChatMessageOut(BaseModel):
    """رسالةٌ كما يراها أحدُ الطرفين — **و`mine` تقول هل هي منه** فلا يحسبها التطبيقُ من دوره."""

    id: uuid.UUID
    ride_id: uuid.UUID
    sender_role: RatingRaterType
    mine: bool
    body: str
    created_at: datetime
    read_at: datetime | None = None

    @classmethod
    def of(cls, message: "RideMessage", viewer_side: RatingRaterType) -> "ChatMessageOut":
        """**البانِي الواحد** لبابَي القراءة والإرسال — والحمولةُ على المقبس من الحقول نفسِها (`trip_chat.deliver`)."""
        return cls(
            id=message.id,
            ride_id=message.ride_id,
            sender_role=message.sender_role,
            mine=message.sender_role == viewer_side,
            body=message.body,
            created_at=message.created_at,
            read_at=message.read_at,
        )


class ChatThreadOut(BaseModel):
    """**المحادثةُ لطرفها** — رسائلُها، **وهل يُكتب فيها** (`open`)، **وهل يُرسم زرُّ الاتصال** (`can_call`).

    `open`/`can_call` كلاهما «في النافذة والمفتاحُ مشتعل»: بعد انتهاء الرحلة تبقى مقروءةً **ويختفي زرُّ الاتصال** (§٦٦-أ/١).
    و`notice` **سطرُ المراجعة بحرف التصميم المُقَرّ** — من الخلفية لا من التطبيقين، فلا يفترقان.
    """

    ride_id: uuid.UUID
    open: bool
    can_call: bool
    unread: int
    notice: str
    max_chars: int
    messages: list[ChatMessageOut]
    #: **المكالمةُ الحيّةُ إن وُجدت** — فيعود إليها تطبيقٌ فُتح من إشعار
    active_call: RideCallOut | None = None


class ChatReportIn(BaseModel):
    reason: RideMessageReportReason
    note: str | None = Field(default=None, max_length=200)


class ChatReportOut(BaseModel):
    """«وصل بلاغُك، وسيراجعه فريقُ TAXO.» — **والنصُّ في التطبيق، وهنا ما يحتاجه ليقوله.**"""

    id: uuid.UUID
    message_id: uuid.UUID
    reason: RideMessageReportReason
    status: RideMessageReportStatus
    created_at: datetime


# ═════════════════════════ اللوحة


class AdminChatMessageOut(BaseModel):
    id: uuid.UUID
    sender_role: RatingRaterType
    sender_id: uuid.UUID | None = None
    sender_name: str | None = None
    body: str
    created_at: datetime
    read_at: datetime | None = None
    #: بلاغاتٌ مفتوحةٌ على هذه الرسالة
    open_reports: int


class AdminChatThreadOut(BaseModel):
    ride_id: uuid.UUID
    country_code: CountryCode
    status: RideStatus
    rider_id: uuid.UUID
    rider_name: str | None = None
    driver_user_id: uuid.UUID | None = None
    driver_name: str | None = None
    messages: list[AdminChatMessageOut]


class AdminReportedMessageOut(BaseModel):
    id: uuid.UUID
    body: str
    sender_role: RatingRaterType
    sender_id: uuid.UUID | None = None
    sender_name: str | None = None
    created_at: datetime


class AdminChatReportOut(BaseModel):
    """**صفُّ «الرسائل المبلَّغ عنها»** — الرسالةُ ومرسلُها، ومن أبلغ، والسبب، والرحلة، والحال (§١ «البلاغ»)."""

    id: uuid.UUID
    status: RideMessageReportStatus
    reason: RideMessageReportReason
    note: str | None = None
    created_at: datetime
    ride_id: uuid.UUID
    country_code: CountryCode
    message: AdminReportedMessageOut
    reporter_id: uuid.UUID | None = None
    reporter_name: str | None = None
    reporter_role: RatingRaterType | None = None
    handled_at: datetime | None = None
    handled_by_name: str | None = None
    handled_note: str | None = None

    @classmethod
    def of(cls, row: "ReportRow") -> "AdminChatReportOut":
        """**البانِي الواحد** لبابَي القائمة والمعالجة — من صفِّ `trip_chat._report_rows` نفسِه (الشكلُ الثامن)."""
        report, message, names = row.report, row.message, row.names
        return cls(
            id=report.id,
            status=report.status,
            reason=report.reason,
            note=report.note,
            created_at=report.created_at,
            ride_id=row.ride_id,
            country_code=row.country_code,
            message=AdminReportedMessageOut(
                id=message.id,
                body=message.body,
                sender_role=message.sender_role,
                sender_id=message.sender_id,
                sender_name=names.get(message.sender_id) if message.sender_id else None,
                created_at=message.created_at,
            ),
            reporter_id=report.reporter_id,
            reporter_name=names.get(report.reporter_id) if report.reporter_id else None,
            reporter_role=row.reporter_role,
            handled_at=report.handled_at,
            handled_by_name=names.get(report.handled_by) if report.handled_by else None,
            handled_note=report.handled_note,
        )


class ChatReportHandleIn(BaseModel):
    note: str = Field(default="", max_length=500)
