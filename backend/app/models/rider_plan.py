"""**اشتراكاتُ الركّاب** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٣، SPEC §٩٧/١٣) — الترحيلة `0156`.

**الخطّة** (لكلِّ دولة، يضعها المالك): اسمٌ ومدّةٌ وثمنٌ، **ونسبةُ خصمٍ على الرحلة بحدٍّ للرحلة وحدٍّ لكلِّ ثلاثين يوماً**، وشروط،
**ومن يتحمّل الخصم** (TAXO أو الكبتن). **والاشتراك** صفٌّ يُكتب **بعد أن يُقتطع ثمنُه من المحفظة** (لا `pending` — كاشتراك الكبتن)،
**ويجمّد شروطَ الخطّة لحظةَ الشراء**: تعديلُ الخطّة يحكم ما يُباع بعده لا ما بيع. **وكلُّ خصمٍ صفٌّ** (`rider_plan_uses`، فريدٌ لكلِّ
رحلة) — منه التوفيرُ الظاهرُ للراكب والحدُّ الشهريّ، **ولا عمودَ مصروف**.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

_BEARERS = "bearer IN ('taxo', 'captain')"


class RiderPlan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rider_plans"
    __table_args__ = (
        CheckConstraint("days BETWEEN 7 AND 365", name="rider_plan_days"),
        CheckConstraint("price > 0", name="rider_plan_price"),
        CheckConstraint("discount_percent > 0 AND discount_percent <= 50", name="rider_plan_percent"),
        CheckConstraint("per_ride_cap > 0 AND monthly_cap >= per_ride_cap", name="rider_plan_caps"),
        CheckConstraint(_BEARERS, name="rider_plan_bearer"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    per_ride_cap: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    monthly_cap: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    bearer: Mapped[str] = mapped_column(String(8), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class RiderPlanSubscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rider_plan_subscriptions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="rider_plan_sub_window"),
        CheckConstraint(_BEARERS, name="rider_plan_sub_bearer"),
    )

    rider_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rider_plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: **مجمَّدةٌ لحظةَ الشراء** — الثمنُ وشروطُ الخصم ومن يتحمّله
    price_paid: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    per_ride_cap: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    monthly_cap: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    bearer: Mapped[str] = mapped_column(String(8), nullable=False)


class RiderPlanUse(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rider_plan_uses"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rider_plan_subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    #: **فريدٌ** — رحلةٌ تُخصم مرّةً ولو أُعيد إنهاؤها
    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
