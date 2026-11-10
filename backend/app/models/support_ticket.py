"""**التذاكرُ ورسائلُها** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٨ و٩) — الترحيلة `0152`.

ثلاثةُ أنواعٍ بجدولٍ واحد، لأنها شيءٌ واحد: **طلبٌ له حالٌ وخيطُ رسائلَ مع المشرفين**.

* `support` — «محادثة مع الدعم» من القائمة أو بعد مشكلة (البند ٨)، برحلةٍ أو بلا رحلة.
* `lost_item` — «نسيت شيئاً في السيارة» على رحلةٍ سابقة (البند ٩): **والكبتنُ طرفٌ في الخيط** يردّ من تطبيقه، **بلا أرقام هواتف**
  (`chat_filter`) — والمشرفُ يرى كلَّ شيء.
* `complaint` — «شكوى على هذه الرحلة» (البند ٩) بفئةٍ ونصٍّ وصورةٍ اختياريّة. **والطرفُ الآخرُ لا يرى الخيط**؛ يُحسب عليه في الإحصاء
  وفي درجة الجودة (البند ٣) ما لم تُرفض.

**الحال**: `open` ⇐ `in_review` (أوّلُ ردٍّ من مشرف) ⇐ `resolved` · `rejected` **بسببٍ إلزاميّ**، وكلُّ تغييرٍ يصل صاحبَها إشعاراً.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import ComplaintCategory, CountryCode, SupportTicketKind, SupportTicketStatus

#: **القيمُ من التعدادات** (`enums.py`) — مصدرُها الواحدُ للقيد وللواجهات (`check:enums`)
TICKET_KINDS = tuple(item.value for item in SupportTicketKind)
TICKET_STATUSES = tuple(item.value for item in SupportTicketStatus)
ACTIVE_STATUSES = (SupportTicketStatus.OPEN.value, SupportTicketStatus.IN_REVIEW.value)
COMPLAINT_CATEGORIES = tuple(item.value for item in ComplaintCategory)
AUTHOR_ROLES = ("user", "party", "staff")


class SupportTicket(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint("kind IN ('support', 'lost_item', 'complaint')", name="support_ticket_kind_values"),
        CheckConstraint("status IN ('open', 'in_review', 'resolved', 'rejected')", name="support_ticket_status_values"),
        CheckConstraint("app IN ('rider', 'driver')", name="support_ticket_app_values"),
        CheckConstraint(
            "category IS NULL OR category IN ('behavior', 'vehicle', 'route', 'fare', 'safety', 'other')",
            name="support_ticket_category_values",
        ),
        CheckConstraint("kind = 'support' OR ride_id IS NOT NULL", name="support_ticket_ride_required"),
        # **طلبٌ واحدٌ قائمٌ لكلِّ نوعٍ على الرحلة الواحدة** — والسباقُ بين ضغطتين يحسمه الفهرسُ لا الفحص
        Index(
            "support_tickets_one_active",
            "user_id",
            "ride_id",
            "kind",
            unique=True,
            postgresql_where=text("status IN ('open', 'in_review') AND ride_id IS NOT NULL"),
        ),
        Index("ix_support_tickets_status_last", "status", "last_message_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    app: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: **الطرفُ الآخرُ في الرحلة** — عليه تُحسب الشكوى، ومعه خيطُ المفقودات
    against_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'open'"))
    #: **ينتظر ردَّ مشرف** — يُرفع برسالة صاحبها أو الطرف، ويُخفض بردِّ مشرف
    needs_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class SupportMessage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "support_messages"
    __table_args__ = (
        CheckConstraint("author_role IN ('user', 'party', 'staff')", name="support_message_role_values"),
    )

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    author_role: Mapped[str] = mapped_column(String(8), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
