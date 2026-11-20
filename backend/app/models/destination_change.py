"""**تعديلُ الوجهة** — صفٌّ لكلِّ عرضٍ رآه الراكب (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-أ).

**العرضُ لا يغيّر شيئاً**: يُحفظ هنا بحاله `quoted` ويعيش دقيقتين، **والرحلةُ لا تُمسّ** إلا بتأكيد الراكب (`confirmed`). ورفضُه
`declined`، وتركُه حتى ينقضي `expired`. **ولا يُحذف صفّ**: هو تاريخُ الرحلة — ما عُرض عليه، وما قَبِل، وما رفض.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin

#: الأطوار — قبل إسناد الكبتن، وبعده (القبولُ والوصولُ والرحلةُ الجارية)
PHASE_SEARCHING = "searching"
PHASE_IN_RIDE = "in_ride"

QUOTED = "quoted"
CONFIRMED = "confirmed"
DECLINED = "declined"
EXPIRED = "expired"


class RideDestinationChange(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ride_destination_changes"

    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id", ondelete="CASCADE"), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=QUOTED)

    old_lat: Mapped[float] = mapped_column(Float, nullable=False)
    old_lng: Mapped[float] = mapped_column(Float, nullable=False)
    old_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_lat: Mapped[float] = mapped_column(Float, nullable=False)
    new_lng: Mapped[float] = mapped_column(Float, nullable=False)
    new_address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: **أجرةُ الرحلة لحظةَ العرض** — والتأكيدُ يرفض إن تغيّرت بعده (عرضٌ على سعرٍ لم يعد قائماً)
    old_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: الأجرةُ الجديدةُ قبل التقريب (تصير `estimated_fare`)، وما رآه الراكبُ مقرَّباً بسياسة رحلته (`rounding.ride_display_fare`)
    new_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    shown_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    new_fare_lines: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB, nullable=True)
    new_distance_km: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    new_duration_min: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    #: ما قُطع فعلاً حين حُسب العرضُ أثناء الرحلة — جزءٌ من الحساب يُقرأ بعده (و`None` قبل البدء)
    traveled_km: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    #: **رسمُ المطار ومرفقُه للوجهة الجديدة** (§٦٣-ج/٢) — داخل `new_fare` كما في التقدير، ويصيران `captain_fees_at_ride`/`facility_id`
    new_captain_fees: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )
    new_facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
