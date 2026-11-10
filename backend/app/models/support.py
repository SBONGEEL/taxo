"""**الطوارئُ والتواصلُ لكلِّ دولة** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٧ و٨).

* `support_settings` — **رقمُ طوارئ الدولة** (يُتّصل به من الزرّ مباشرةً) **ورقمُ واتساب الدعم** (زرُّ «تواصل معنا»). من اللوحة لكلِّ دولة،
  وغيابُ الصفِّ افتراضُ الرقم الرسميّ (`DEFAULT_EMERGENCY`) وواتسابٌ غائب — فلا زرَّ واتساب يفتح رقماً لم يضعه أحد.
* `emergency_alerts` — **كلُّ ضغطةٍ على زرّ الطوارئ** من الراكب أو الكبتن: من ضغط · بأيِّ صفة · في أيِّ رحلة · أين. تصل اللوحةَ تنبيهاً
  عاجلاً وتبقى «مفتوحة» حتى يعالجها مشرفٌ بملاحظة. **ولا تُحذف** — سجلُّ سلامةٍ لا رسالة.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

#: **أرقامُ الطوارئ الرسميّة** — الأردن: الرقمُ الموحَّد ٩١١ (مديريةُ الأمن العامّ) · الجزائر: ١٧ الشرطة (والحمايةُ المدنيّة ١٤،
#: والدركُ ١٠٥٥) · **ليبيا بلا افتراض** — رقمٌ لم يُتحقَّق منه لا يُكتب في زرِّ طوارئ، ويضعه المالكُ من اللوحة قبل «شغّل ليبيا».
#: **والمالكُ يغيّرها من اللوحة**؛ هذه ما يُعرض قبل أن يضع شيئاً.
DEFAULT_EMERGENCY: dict[CountryCode, str] = {
    CountryCode.JO: "911",
    CountryCode.DZ: "17",
}

EMERGENCY_ROLES = ("rider", "driver")
EMERGENCY_STATUSES = ("open", "handled")


class SupportSetting(TimestampMixin, Base):
    __tablename__ = "support_settings"

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), primary_key=True)
    #: يُطلب من الزرّ بـ`tel:` — أرقامٌ و`+` وحدَها
    emergency_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: بصيغةٍ دوليّةٍ بلا `+` (`wa.me/<الرقم>`) — و`NULL` يُخفي زرَّ واتساب
    whatsapp_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class EmergencyAlert(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "emergency_alerts"
    __table_args__ = (
        CheckConstraint("role IN ('rider', 'driver')", name="emergency_alerts_role"),
        CheckConstraint("status IN ('open', 'handled')", name="emergency_alerts_status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: **الصفةُ التي ضغط بها** — التطبيقُ الذي ضغط منه، لا دورُ الحساب (حسابٌ واحدٌ قد يملك الدورين)
    role: Mapped[str] = mapped_column(String(8), nullable=False)
    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="SET NULL"), nullable=True, index=True
    )
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    #: موقعُ الضاغط لحظةَ الضغط (من جهازه) — والحيُّ بعدها من موقع الكبتن في الرحلة
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(8), nullable=False, server_default="open", index=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
