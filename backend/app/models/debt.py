"""دَينُ الكبتن — الترحيلة `0061`.

**الدَّينُ ليس رصيداً سالباً**: جدولٌ مستقلٌّ، والحارسُ عند مصدر الدفتر يبقى
كما هو — لا `balance_after` سالبٌ إطلاقاً. وهي قاعدةُ `driver_advances`
نفسُها، وهذا بيتُها الثالث.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, Currency, DriverDebtSource, DriverDebtStatus


class DriverDebt(UUIDMixin, TimestampMixin, Base):
    """مبلغٌ استحقّ على كبتنٍ من رحلةٍ قبض مالَها بيده.

    **ولمَ يستحقّ**: قناةٌ يقبضها بيده (كاش/كليك) لا تكتب `ride_earning` —
    فالأجرةُ كلُّها في جيبه **ومنها عمولةُ المنصّة**. فالمستحقُّ مالٌ يحمله
    عنّا، لا قرضٌ أعطيناه — ولذلك يُحصَّل **قبل** اقتطاع السلفة.
    """

    __tablename__ = "driver_debts"

    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False
    )
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    source: Mapped[DriverDebtSource] = mapped_column(
        pg_enum(DriverDebtSource, "driver_debt_source"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: **المحصَّلُ منه** — والسدادُ الجزئيُّ حالةٌ في الصفّ لا جدولٌ رابع
    collected: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, server_default=text("0")
    )
    currency: Mapped[Currency] = mapped_column(
        pg_enum(Currency, "currency"), nullable=False
    )
    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rides.id", ondelete="SET NULL"), nullable=True
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[DriverDebtStatus] = mapped_column(
        pg_enum(DriverDebtStatus, "driver_debt_status"),
        nullable=False,
        server_default=text("'outstanding'"),
    )
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    written_off_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    written_off_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    writeoff_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="driver_debt_amount_positive"),
        CheckConstraint(
            "collected >= 0 AND collected <= amount",
            name="driver_debt_collected_within",
        ),
        # **دفعةٌ واحدةٌ تُنشئ دَيناً واحداً** — والحمايةُ في القاعدة
        UniqueConstraint(
            "payment_id", "source", name="driver_debt_once_per_payment"
        ),
        Index(
            "driver_debt_outstanding",
            "driver_id",
            postgresql_where=text("status = 'outstanding'"),
        ),
    )

    @property
    def remaining(self) -> Decimal:
        """ما بقي منه — **الصفرُ هو ما يرفع المنع** لا ما دونه."""
        return self.amount - self.collected
