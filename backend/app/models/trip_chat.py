"""محادثةُ الرحلة (SPEC §٦٦-ب، `design/APPROVALS-DATA.md` §١) — **ما يُحفظ هو ما أُقرّ، ولا عمودَ لغيره**.

**يُحفظ**: نصُّ الرسالة (حتى ٣٠٠ حرف) · من أرسلها وبأيِّ صفة (راكبٌ أو كبتن) · وقتُها · رحلتُها · ووقتُ قراءتها.
**ولا يُحفظ**: صورٌ ولا صوتٌ ولا ملفّاتٌ ولا مواقع — **لا عمودَ لها**، فلا يحفظها خطأٌ في الشيفرة يوماً. **ولا أرقامُ هواتف**: تُردّ
قبل أن تُكتب (`services/chat_filter.py`)، فلا يُحفظ رقمٌ ليُحذف بعدها.

**وكم يبقى**: `service_settings.chat_retention_days` لكلِّ سوقٍ بعد انتهاء الرحلة (٩٠ افتراضاً)، ثمّ يُحذف بمهمّةٍ يوميّة — **والمحادثةُ
التي فيها بلاغٌ مفتوحٌ تبقى حتى يُعالَج، ثمّ تجري المدّةُ من وقت معالجته** (`services/trip_chat.purge_expired`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, pg_enum
from app.models.enums import RatingRaterType, RideMessageReportReason, RideMessageReportStatus

#: **أطولُ رسالة** — قرارُ التصميم المُقَرّ، ويحرسه قيدٌ في القاعدة لا التحقّقُ وحدَه
MAX_BODY_CHARS = 300


class RideMessage(UUIDMixin, Base):
    """**رسالةٌ واحدةٌ بين طرفَي رحلة** — لا تُحرَّر ولا تُحذف بيد أحد.

    **`sender_role` جانبُ الرحلة لا دورُ الحساب** (§22): حسابٌ يحمل الدورين راكبٌ في رحلةٍ هو راكبُها. **والنوعُ هو نوعُ «جانب
    التقييم» القائم** (`rating_rater_type`) — قيمتان بالمعنى نفسِه، فلا يُخترع نوعٌ ثانٍ يفترق عنه.

    **و`sender_id` يُفرَّغ ولا يمحو الرسالة** (`SET NULL`): الحسابُ لا يُحذف صفُّه أصلاً (يُجهَّل)، وحذفُ رسائل صاحبه بابُه
    `account_deletion._anonymize` لا تتابعُ المفتاح.
    """

    __tablename__ = "ride_messages"
    __table_args__ = (
        CheckConstraint(f"char_length(body) BETWEEN 1 AND {MAX_BODY_CHARS}", name="ride_message_body_length"),
        # **ما يُقرأ في كلِّ فتح**: رسائلُ رحلةٍ بترتيبها — وهو نفسُه ما يمسحه الكنسُ رحلةً رحلة
        Index("ix_ride_messages_ride_id_created_at", "ride_id", "created_at"),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sender_role: Mapped[RatingRaterType] = mapped_column(pg_enum(RatingRaterType, "rating_rater_type"), nullable=False)
    body: Mapped[str] = mapped_column(String(MAX_BODY_CHARS), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    #: **متى قرأها الطرفُ الآخر** — يُكتب حين يفتح المحادثة، ولا تكتبه قراءةُ المشرف
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<RideMessage {self.ride_id} {self.sender_role}>"


class RideMessageReport(UUIDMixin, Base):
    """**بلاغٌ عن رسالةِ الطرف الآخر** — سببٌ وسطرٌ اختياريّ، وحالُه ومن عالجه ومتى.

    **بلاغٌ واحدٌ لكلِّ مُبلِّغٍ على رسالة** (فريدٌ في القاعدة): ضغطتان على «أبلغ» لا تصنعان بلاغين، والبابُ يعيد الأوّلَ نفسَه.
    **وبلاغٌ مفتوحٌ يُبقي محادثتَه** حتى يُعالَج — والكنسُ يقرأ ذلك من هنا.
    """

    __tablename__ = "ride_message_reports"
    __table_args__ = (
        UniqueConstraint("message_id", "reporter_id", name="uq_ride_message_reports_message_id_reporter_id"),
        # **معالَجٌ ⇔ له وقتُ معالجة** — فلا يُقرأ بلاغٌ «معالَجاً» بلا أثر، ولا يجري عليه عدّادُ الحذف من وقتٍ فارغ
        CheckConstraint("(status = 'handled') = (handled_at IS NOT NULL)", name="ride_message_report_handled_complete"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ride_messages.id", ondelete="CASCADE"), nullable=False)
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[RideMessageReportReason] = mapped_column(
        pg_enum(RideMessageReportReason, "ride_message_report_reason"), nullable=False
    )
    #: سطرٌ اختياريٌّ يكتبه المُبلِّغ — **نصٌّ حرٌّ كتبه هو**، فيُمحى مع حسابه
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[RideMessageReportStatus] = mapped_column(
        pg_enum(RideMessageReportStatus, "ride_message_report_status"),
        nullable=False,
        default=RideMessageReportStatus.OPEN,
        server_default=text("'open'"),
        index=True,
    )
    handled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handled_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<RideMessageReport {self.message_id} {self.status}>"
