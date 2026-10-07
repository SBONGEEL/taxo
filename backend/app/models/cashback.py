"""سلسلةُ الاسترداد الأسبوعي (SPEC §٦٣-ج/٨) — **واحدةٌ قائمةٌ لكلِّ راكب** (فهرسٌ فريدٌ جزئيّ)، **والمبلغُ مجمَّدٌ لحظةَ بدئها**.

**ولا حذف**: سلسلةٌ فاتها يومٌ تُوسم `lost`، والفائزةُ `won` بقيدها — **سجلٌّ يجيب «لمَ نزل هذا المبلغ»**.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class CashbackStreak(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "cashback_streaks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'won', 'lost') AND days_done >= 1 AND days_required >= 1 AND amount > 0 "
            "AND last_day >= started_on",
            name="cashback_streak_valid",
        ),
        Index("uq_cashback_streaks_active_rider", "rider_id", unique=True, postgresql_where=text("status = 'active'")),
    )

    rider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    #: **آخرُ يومٍ حُسب** — اليومُ المطلوبُ بعده هو التالي غيرُ الجمعة
    last_day: Mapped[date] = mapped_column(Date, nullable=False)
    days_done: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    days_required: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    #: **المبلغُ مجمَّدٌ لحظةَ البدء** — تعديلُ اللوحة يحكم السلاسلَ القادمة
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="active", server_default=text("'active'"))
    won_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
