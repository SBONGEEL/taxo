"""مناطقُ التسعير (SPEC §٧٤-أ/٥، أمرُ المالك ٢٠٢٦-١٠-١٣) — **سعرٌ موحَّدٌ لكلِّ دولة، إلا منطقةً وُسمت «وعرة»**.

**عامّةٌ لأيِّ دولة**: صفٌّ لكلِّ منطقة (ولايةٍ في الجزائر) بمضلّعها (`geography(MULTIPOLYGON)` — ولايةٌ قد تكون أجزاءً، والولاياتُ
الجديدةُ مضمومةٌ إلى أمّها حتى يبدأ عملُها). **ولايةُ الانطلاق تحكم** (`ST_Covers` على نقطة الالتقاء)، وغيرُ الموسومة لا أثرَ لها.

**والموسومةُ «وعرة» بأحد وجهين يختارهما المالك**:
- **نسبةٌ على سعر الرحلة** (`percent`) — افتراضاً **+25%** بنصّه، تُضبط لكلِّ منطقة؛
- **أو جدولُ أسعارٍ مستقلٌّ كامل** (`table`) — صفٌّ لكلِّ فئةٍ في `zone_pricing_rules` يحلّ محلَّ تسعيرة الدولة؛ وفئةٌ بلا صفٍّ تبقى
  بتسعيرة الدولة.

**ولا عمودَ مالٍ يُمسّ**: المنطقةُ معدّلاتٌ وحالٌ لا قيود — وأثرُها سطرٌ في تفصيل الأجرة (`rugged`) يُجمَّد على الرحلة كغيره.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

ZONE_MODE_PERCENT = "percent"
ZONE_MODE_TABLE = "table"
#: **افتراضُ المالك بلفظه**: «+25% على سعر كلِّ رحلة»
DEFAULT_RUGGED_PERCENT = Decimal("25.00")


class PricingZone(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pricing_zones"
    __table_args__ = (
        UniqueConstraint("country_code", "code", name="uq_pricing_zone_code"),
        CheckConstraint("adjustment_mode IN ('percent', 'table')", name="pricing_zone_mode_valid"),
        # **نسبةٌ تزيد لا تُنقص، ولها سقف** — منطقةٌ «وعرة» بخصمٍ ليست وعرة، ومئتان بالمئة خطأُ إدخالٍ لا سياسة
        CheckConstraint("adjustment_percent >= 0 AND adjustment_percent <= 200", name="pricing_zone_percent_range"),
        Index("ix_pricing_zones_area", "area", postgresql_using="gist"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    #: **رمزُ المنطقة** — رقمُ الولاية في الجزائر («16»)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(80), nullable=False)
    name_fr: Mapped[str | None] = mapped_column(String(80), nullable=True)
    #: **ما ضُمَّ إليها** — الولاياتُ الجديدة (القانون ٢٦-٠٦) التي تتبعها حتى يبدأ عملُها، نصّاً للعرض
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    area = mapped_column(Geography(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False)
    rugged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    adjustment_mode: Mapped[str] = mapped_column(
        String(8), nullable=False, default=ZONE_MODE_PERCENT, server_default=text("'percent'")
    )
    adjustment_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=DEFAULT_RUGGED_PERCENT, server_default=text("25.00")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ZonePricingRule(UUIDMixin, TimestampMixin, Base):
    """**جدولُ أسعار منطقةٍ وعرةٍ مستقلّ** — يحلّ محلَّ تسعيرة الدولة لفئته حين يكون وجهُ المنطقة `table`."""

    __tablename__ = "zone_pricing_rules"
    __table_args__ = (
        UniqueConstraint("zone_id", "vehicle_category", name="uq_zone_pricing_rule"),
        CheckConstraint(
            "base_fare >= 0 AND price_per_km >= 0 AND price_per_min >= 0 AND minimum_fare >= 0",
            name="zone_pricing_rule_not_negative",
        ),
    )

    zone_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pricing_zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vehicle_category: Mapped[str] = mapped_column(String(32), nullable=False)
    base_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price_per_km: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price_per_min: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
