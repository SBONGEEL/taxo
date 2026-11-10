"""**تجاربُ الأسعار** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٤، SPEC §٩٧/٤) — الترحيلة `0155`.

**التجربة**: نسبةٌ على أجرة الطريق (بين −50٪ و+50٪) **لنسبةٍ من ركّاب دولةٍ** (اختيارٌ ثابتٌ لكلِّ راكبٍ ببصمة معرّفه)، **أو لجزءٍ منها**
(دائرةٌ حول نقطة)، لعددِ أيّام. **ومن في نطاقها ولم يقع في ذراعها يُحسب «مقارنة»** بالسعر العاديّ، فتُقارَن الذراعان.

**لا شيءَ يعمل افتراضيّاً**: تُنشأ مسوّدة، ويبدؤها المالك، ويوقفها، ثمّ يقرّر: **تطبيقُ الفائز** (النسبةُ على تسعيرة الدولة كلِّها — للتجربة
على الدولة كلِّها وحدَها) **أو الإلغاء**. **والنسبةُ والنطاقُ لا يتغيّران بعد الإنشاء** — رحلاتٌ سُعِّرت بها تُعاد عليها عند الإنهاء.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, PriceExperimentStatus

EXPERIMENT_STATUSES = tuple(status.value for status in PriceExperimentStatus)


class PriceExperiment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "price_experiments"
    __table_args__ = (
        CheckConstraint("adjust_percent <> 0 AND adjust_percent BETWEEN -50 AND 50", name="price_experiment_percent"),
        CheckConstraint("share_percent BETWEEN 1 AND 100", name="price_experiment_share"),
        CheckConstraint("days BETWEEN 1 AND 60", name="price_experiment_days"),
        CheckConstraint(
            "(center_lat IS NULL AND center_lng IS NULL AND radius_km IS NULL) OR "
            "(center_lat IS NOT NULL AND center_lng IS NOT NULL AND radius_km > 0)",
            name="price_experiment_area",
        ),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{value}'" for value in EXPERIMENT_STATUSES) + ")", name="price_experiment_status"
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: **النسبةُ على أجرة الطريق** — موجبةٌ زيادةٌ وسالبةٌ خصم
    adjust_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    #: **نسبةُ الركّاب في ذراع التجربة** (١–١٠٠) من ركّاب النطاق
    share_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    #: **النطاق**: الدولةُ كلُّها (الثلاثةُ فارغة) أو دائرةٌ حول نقطة الانطلاق
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_km: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft", server_default=text("'draft'"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: **نهايةُ المدّة** — تُكتب عند البدء (`started_at + days`)، وبعدها لا تُسعِّر التجربةُ رحلةً ولو بقيت «تعمل»
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
