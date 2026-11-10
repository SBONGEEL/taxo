"""**أهدافُ الكبتن ومكافآتُها** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٦، SPEC §٩٧/١٦) — الترحيلة `0154`.

**الهدف**: عددُ رحلاتٍ مكتملةٍ بين بدايةٍ ونهاية، ومكافأةٌ لمن بلغه **تُصرف إلى المحفظة آليّاً**، **وسقفُ ميزانيّةٍ** لا تتجاوزه
المكافآتُ مجتمعة. **والمبالغُ يضعها المالكُ وحدَه** ويبقى المفتاحُ (`driver_goals_enabled`) مطفأً حتى يضعها.

**والمصروفُ لا عمودَ له** (درسُ `budget_spent`): يُجمع من `driver_goal_awards` تحت قفل صفِّ الهدف. وصفُّ المكافأة **فريدٌ لكلِّ
هدفٍ وكبتن** — فلا تُصرف مرّتين.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class DriverGoal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "driver_goals"
    __table_args__ = (
        CheckConstraint("target > 0", name="driver_goal_target_positive"),
        CheckConstraint("reward_amount > 0", name="driver_goal_reward_positive"),
        CheckConstraint("budget_cap >= reward_amount", name="driver_goal_budget_covers_one"),
        CheckConstraint("ends_at > starts_at", name="driver_goal_window"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: **رحلاتٌ مكتملةٌ** في النافذة — المعيارُ الوحيدُ المقيسُ اليوم
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    budget_cap: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class DriverGoalAward(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "driver_goal_awards"
    __table_args__ = (UniqueConstraint("goal_id", "driver_id", name="uq_driver_goal_award"),)

    goal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("driver_goals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    #: «goal» · الإيداعُ الذي صرفه — للتدقيق
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
