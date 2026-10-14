"""ملاحظاتُ المستخدمين من داخل التطبيقين — «أرسل ملاحظة» (SPEC §٧٦/٤، أمرُ المالك ٢٠٢٦-١٠-١٤).

**وُلدت لمختبري المسار المغلق في Google Play**: نصٌّ وصورةُ شاشةٍ اختياريّة، **وما يلزم لقراءتها**: من أرسل · أيُّ تطبيق · أيُّ إصدار ·
متى. **والإصدارُ إصداران** لأن الشاشاتِ تُحمَّل من الخادم (`server.url`): **إصدارُ الغلاف** المثبَّت من المتجر (`app_version`) **وحزمةُ
الشاشات** التي حمّلها (`web_build`) — والملاحظةُ عن شاشةٍ لا يُعرف من أيِّ حزمةٍ هي لا يُعرف إن أُصلحت.

**والصفُّ يُمحى مع صاحبه** حين يُجهَّل حسابُه (`account_deletion`) — نصٌّ حرٌّ قد يحمل ما يعرّفه، **وتنتهي بعد سنة**
(`feedback.expired_rows`). **ولا مالَ هنا.**
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AppFeedback(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "app_feedback"
    __table_args__ = (
        CheckConstraint("app IN ('rider', 'driver')", name="app_feedback_app"),
        CheckConstraint("char_length(message) BETWEEN 1 AND 2000", name="app_feedback_message_length"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: `rider` أو `driver` — التطبيقُ الذي كُتبت منه، لا دورُ الحساب (حسابٌ واحدٌ قد يملك الدورين)
    app: Mapped[str] = mapped_column(String(8), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    #: إصدارُ الغلاف المثبَّت `الإصدار+البناء` — و`NULL` من متصفّحٍ لا غلافَ له
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: حزمةُ الشاشات المحمَّلة (اسمُ ملفِّ الدخول) — **ما يُصلَح فيه الخللُ فعلاً**
    web_build: Mapped[str | None] = mapped_column(String(80), nullable=True)
    #: `android` · `ios` · `web`
    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: المسارُ الذي كانت عليه الشاشة (قالبُه لا معرّفاتُه)
    route: Mapped[str | None] = mapped_column(String(120), nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    screenshot_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: قرأها المشرفُ وعالجها — **و`NULL` جديدةٌ تنتظر**
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
