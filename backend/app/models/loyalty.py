"""**نقاطُ الولاء** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٤، SPEC §٩٧/١٤) — الترحيلة `0157`.

**القاعدةُ لكلِّ دولة** (يضعها المالك): نقاطٌ لكلِّ رحلةٍ مكتملة، ومدّةُ انتهاء النقاط، **وحدّا المستويين** (فضّيّ وذهبيّ بنقاط آخر ٣٦٥
يوماً) **وميزتُهما** (زيادةٌ بالمئة على ما يُكسب)، **والاستبدال**: كم نقطةً بكم من الرصيد.

**وكلُّ كسبٍ صفٌّ** (فريدٌ لكلِّ رحلة) بنقاطه وما بقي منها وتاريخِ انتهائه؛ **والاستبدالُ يستهلك الأقدمَ أوّلاً** (`remaining`)، **والرصيدُ
مجموعُ ما بقي ممّا لم ينتهِ** — فلا يُخصم المنتهي مرّتين.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class LoyaltyRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "loyalty_rules"
    __table_args__ = (
        UniqueConstraint("country_code", name="uq_loyalty_rules_country"),
        CheckConstraint("points_per_ride > 0", name="loyalty_points_per_ride"),
        CheckConstraint("expiry_days BETWEEN 30 AND 1095", name="loyalty_expiry"),
        CheckConstraint("gold_threshold > silver_threshold AND silver_threshold > 0", name="loyalty_tiers"),
        CheckConstraint("silver_bonus_percent BETWEEN 0 AND 100 AND gold_bonus_percent BETWEEN 0 AND 100", name="loyalty_bonus"),
        CheckConstraint("redeem_points > 0 AND redeem_value > 0", name="loyalty_redeem"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    points_per_ride: Mapped[int] = mapped_column(Integer, nullable=False)
    expiry_days: Mapped[int] = mapped_column(Integer, nullable=False)
    silver_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    gold_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    silver_bonus_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    gold_bonus_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    #: **الاستبدال**: كلُّ `redeem_points` نقطةً = `redeem_value` رصيداً بعملة الدولة
    redeem_points: Mapped[int] = mapped_column(Integer, nullable=False)
    redeem_value: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)


class LoyaltyEarning(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "loyalty_earnings"
    __table_args__ = (CheckConstraint("points > 0 AND remaining BETWEEN 0 AND points", name="loyalty_earning_points"),)

    rider_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    #: **فريدٌ** — رحلةٌ تكسب مرّةً
    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
