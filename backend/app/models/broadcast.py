"""إعداداتُ بثّ موقع الكبتن (SPEC §٧٥-ج، أمرُ المالك ٢٠٢٦-١٠-١٣) — جدولان، **ولا قيمةَ فاصلٍ مكتوبةٌ في الشيفرة**.

١. **`broadcast_settings`** — صفٌّ واحدٌ عالميّ (يحرسه `singleton`): الطورُ (يدويّ/آليّ) وفواصلُ كلِّ حال، وعتبةُ المسافة ومدّةُ النبضة،
   **وجدولُ الطور الآليّ** (عددُ المتّصلين ⇐ فاصلُ المتاحين). **عالميٌّ لا لكلِّ دولة**: ما يُحمى هو الخادمُ الواحد، وعددُه عددُ كلِّ
   المتّصلين عليه. **والصفُّ يُبذر بالترحيلة** بقيم المالك، فاللوحةُ تُري ما يعمل لا افتراضاً مخفيّاً.
٢. **`broadcast_changes`** — سجلُّ كلِّ تغييرٍ في الفاصل الفعّال للمتاحين: الوقتُ والعددُ والقديمُ والجديدُ ومن سبّبه (الطورُ الآليّ أو
   مشرف). **يُضاف إليه ولا يُعدَّل** — هو ما تقرؤه اللوحةُ «سجلَّ آخر التغييرات».

**والفاصلُ الفعّالُ نفسُه لا عمودَ له**: يعيش في Redis (`services/broadcast.py`) — **فالطورُ الآليُّ لا يكتب في صفِّ الإعدادات أبداً**، وما
يكتبه المشرفُ وحدَه يغيّره. **ولا مال هنا.**
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class BroadcastSettings(UUIDMixin, TimestampMixin, Base):
    """**صفٌّ واحد** — فواصلُ البثّ وطورُه. والحدودُ في القاعدة كما في المدخل: قيمةٌ تُدخَل يدويّاً خارجها تُرفض هنا أيضاً."""

    __tablename__ = "broadcast_settings"
    __table_args__ = (
        CheckConstraint("singleton IS TRUE", name="broadcast_settings_singleton"),
        CheckConstraint("mode IN ('manual', 'automatic')", name="broadcast_settings_mode"),
        # **حدّا المالك الصلبان**: «لا أقلَّ من ١٥ ولا أكثرَ من ٤٥» — في الطورين
        CheckConstraint("available_seconds BETWEEN 15 AND 45", name="broadcast_available_range"),
        CheckConstraint("heading_seconds BETWEEN 3 AND 60", name="broadcast_heading_range"),
        CheckConstraint("trip_send_seconds BETWEEN 3 AND 60", name="broadcast_trip_send_range"),
        CheckConstraint("trip_record_seconds BETWEEN 1 AND 10", name="broadcast_trip_record_range"),
        CheckConstraint("move_meters BETWEEN 5 AND 500", name="broadcast_move_range"),
        CheckConstraint("heartbeat_seconds BETWEEN 15 AND 120", name="broadcast_heartbeat_range"),
    )

    singleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True, unique=True
    )
    #: «automatic» افتراضاً: بأقلَّ من ألف متّصلٍ يعطي ١٥ ثانيةً — ما يعطيه اليدويُّ بقيمته الافتراضيّة حرفاً
    mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default="automatic", default="automatic")
    #: **فاصلُ المتاح في الطور اليدويّ** — والآليُّ يحسبه من الجدول ولا يقرأ هذا
    available_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15", default=15)
    #: في الطريق إلى الراكب (قَبِل ← وصل) — **لا يمسّه الطورُ الآليّ**
    heading_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10", default=10)
    #: في الرحلة: دفعةٌ كلَّ هذه الثواني…
    trip_send_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15", default=15)
    #: …ونقطةٌ تُسجَّل في الهاتف كلَّ هذه الثواني — **والخادمُ يستعمل النقاطَ كلَّها** (مسافةُ الأجرة)
    trip_record_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2", default=2)
    #: **قاعدةُ السكون**: لا إرسالَ ما لم يبتعد هذا عن آخر نقطةٍ أُرسلت (إلا في الرحلة)، **وإرسالٌ فوريٌّ إن ابتعد**
    move_meters: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30", default=30)
    #: **نبضةُ «ما زلتُ متّصلاً»** — بلا موقع، تُبقي الحضورَ حيّاً لساكنٍ لا يرسل
    heartbeat_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60", default=60)
    #: **جدولُ الطور الآليّ** — `[{"max_online": 1000, "seconds": 15}, …, {"max_online": null, "seconds": 45}]` بترتيبه، والأخيرُ بلا حدّ
    auto_steps: Mapped[list] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class BroadcastChange(UUIDMixin, Base):
    """**سطرٌ لكلِّ تغييرٍ في فاصل المتاحين الفعّال** — يُضاف ولا يُعدَّل."""

    __tablename__ = "broadcast_changes"
    __table_args__ = (CheckConstraint("source IN ('automatic', 'admin')", name="broadcast_changes_source"),)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    #: من سبّبه — «automatic» (عدُّ المتّصلين عبر عتبة) أو «admin» (مشرفٌ غيّر الطورَ أو القيمة)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    #: المتّصلون لحظتَه — كما عدّهم الطورُ الآليّ (مفاتيحُ حضورٍ حيّة)
    online_count: Mapped[int] = mapped_column(Integer, nullable=False)
    old_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
