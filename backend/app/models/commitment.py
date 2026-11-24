"""**نقاطُ الالتزام** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، الجزء ب؛ SPEC §١١٤-ب) — الترحيلة `0190`.

* **القاعدةُ لكلِّ دولة** (`commitment_rules`): النافذةُ والمدّةُ وقواعدُ الاستراحة افتراضاتٌ تُحرَّر من اللوحة، **وقيمُ النقاط والتحويل
  فارغةٌ حتى يضعها المالك**، وقيدٌ في القاعدة يمنع التشغيلَ بلا قيم.
* **يومُ الكبتن** (`driver_duty_days`): حكمٌ واحدٌ لكلِّ يومٍ محلّيّ — تحقّق، لم يتحقّق، أُسقط — **وسببٌ يُرى**.
* **النقاط** (`driver_points_entries`): كسبٌ بباقيه وتاريخِ انتهائه، **والتحويلُ يستهلك الأقدمَ أوّلاً** (كنقاط الولاء).
* **رصيدُ الاشتراك** (`subscription_credit_entries`): **دفترٌ مستقلٌّ إلحاقيٌّ** (مُشغِّلٌ في القاعدة يرفض التعديلَ والحذف) — **ليس في
  `wallet_transactions`**، فلا بابَ سحبٍ ولا تحويلٍ ولا نقدٍ يقرؤه أصلاً؛ لا يُصرف إلا في اشتراك TAXO.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, Currency

#: **حكمُ اليوم**
DUTY_MET = "met"
DUTY_NOT_MET = "not_met"
DUTY_DISQUALIFIED = "disqualified"

#: **أنواعُ النقاط**
POINTS_DAILY = "daily"
POINTS_DISCOUNTED_RIDE = "discounted_ride"
POINTS_CONVERSION = "conversion"
POINTS_EXPIRY = "expiry"
POINTS_ADJUSTMENT = "adjustment"

#: **أنواعُ قيود رصيد الاشتراك**
CREDIT_FROM_POINTS = "points_conversion"
CREDIT_SUBSCRIPTION = "subscription_payment"
CREDIT_EXPIRY = "expiry"
CREDIT_ADJUSTMENT = "adjustment"


class CommitmentRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "commitment_rules"
    __table_args__ = (
        UniqueConstraint("country_code", name="uq_commitment_rules_country"),
        CheckConstraint(
            "span_minutes BETWEEN 60 AND 1020 AND max_break_minutes BETWEEN 0 AND 240 "
            "AND max_total_break_minutes BETWEEN 0 AND 600 AND max_break_minutes <= max_total_break_minutes "
            "AND max_total_break_minutes < span_minutes AND window_start < window_end",
            name="commitment_rules_shape",
        ),
        CheckConstraint(
            "(points_per_day IS NULL OR points_per_day > 0) AND (points_per_credit_unit IS NULL OR points_per_credit_unit > 0) "
            "AND (credit_unit_value IS NULL OR credit_unit_value > 0) AND (daily_points_cap IS NULL OR daily_points_cap > 0) "
            "AND (monthly_points_cap IS NULL OR monthly_points_cap > 0) "
            "AND (points_expiry_days IS NULL OR points_expiry_days BETWEEN 1 AND 1095) "
            "AND (credit_expiry_days IS NULL OR credit_expiry_days BETWEEN 1 AND 1095) AND max_accounts_per_device >= 1",
            name="commitment_rules_values",
        ),
        CheckConstraint(
            "NOT is_enabled OR (points_per_day IS NOT NULL AND points_per_credit_unit IS NOT NULL "
            "AND credit_unit_value IS NOT NULL)",
            name="commitment_rules_enabled_needs_values",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    window_start: Mapped[time] = mapped_column(Time, nullable=False, default=time(7, 0), server_default=text("'07:00'"))
    window_end: Mapped[time] = mapped_column(Time, nullable=False, default=time(23, 59), server_default=text("'23:59'"))
    span_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=600, server_default=text("600"))
    max_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"))
    max_total_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120, server_default=text("120"))
    #: **قيمُ المالك** — فارغةٌ حتى يضعها
    points_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: كلُّ `points_per_credit_unit` نقطةً = `credit_unit_value` رصيدَ اشتراكٍ بعملة الدولة
    points_per_credit_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credit_unit_value: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    daily_points_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_points_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_expiry_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credit_expiry_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    require_service_area: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    max_accounts_per_device: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))


class DriverDutyDay(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "driver_duty_days"
    __table_args__ = (
        UniqueConstraint("driver_id", "day", name="uq_driver_duty_days_driver_day"),
        CheckConstraint("status IN ('met', 'not_met', 'disqualified')", name="driver_duty_days_status"),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False
    )
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    online_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    break_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    longest_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    span_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    span_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: **السببُ بالعربيّة كما يراه الكبتن**
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    #: **أعلامُ الريبة** للوحة — لا تُسقط يوماً وحدَها
    flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    rides_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DriverPointsEntry(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "driver_points_entries"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('daily', 'discounted_ride', 'conversion', 'expiry', 'adjustment')", name="driver_points_kind"
        ),
        CheckConstraint(
            "(kind IN ('daily', 'discounted_ride') AND points > 0 AND remaining BETWEEN 0 AND points) OR "
            "(kind IN ('conversion', 'expiry') AND points < 0 AND remaining = 0) OR "
            "(kind = 'adjustment' AND ((points < 0 AND remaining = 0) OR (points > 0 AND remaining BETWEEN 0 AND points)))",
            name="driver_points_sign",
        ),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duty_day_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("driver_duty_days.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
    credit_entry_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SubscriptionCreditEntry(UUIDMixin, Base):
    """**قيدٌ في رصيد الاشتراك** — إلحاقيٌّ لا يُعدَّل (مُشغِّلُ `0190`)، والرصيدُ مجموعُه."""

    __tablename__ = "subscription_credit_entries"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('points_conversion', 'subscription_payment', 'expiry', 'adjustment')", name="subscription_credit_kind"
        ),
        CheckConstraint(
            "(kind = 'points_conversion' AND amount > 0) OR (kind IN ('subscription_payment', 'expiry') AND amount < 0) "
            "OR (kind = 'adjustment' AND amount <> 0)",
            name="subscription_credit_sign",
        ),
        CheckConstraint("balance_after >= 0", name="subscription_credit_non_negative"),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("driver_subscriptions.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
