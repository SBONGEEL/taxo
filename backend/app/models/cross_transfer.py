"""**التحويلُ بين الدول** (أمرُ المالك ٢٠٢٦-١١-٢٢، `design/OWNER-2026-11-22-CROSS-TRANSFER.md`، SPEC §٧/التحويل بين الدول).

ثلاثةُ جداول، **وكلُّها جديدة** — لا عمودَ يُضاف إلى جدولِ مالٍ قائم (شرطُ المالك: «إلا المدخلاتِ الجديدةَ للتحويل بين الدول»):

- `fx_rates`: **سعرُ صرفٍ لكلِّ اتّجاه** (من عملةٍ إلى أخرى) ورسمُه وتاريخُ ضبطه ومن ضبطه. **والاتّجاهان صفّان لا صفٌّ يُقلب**:
  مقلوبُ السعر ليس سعرَ الشراء — الصرّافُ يبيع ويشتري بسعرين، وقلبُ سعرٍ واحدٍ يفرض على المشرف ما لم يقرّره.
  **ولا صفَّ يُبذر**: لا سعرَ حتى يكتبه مشرف، **وغيابُه يردّ التحويل** (لا يضبطه الوكيلُ أبداً — شرطُ المالك).
- `cross_transfer_limits`: **حدّا المرسل اليوميُّ والشهريُّ** لكلِّ دولة مرسل، بعملتها. **وصفرٌ = «لم يُضبط» فيُردّ** — قاعدةُ
  `wallet_settings` نفسُها، **وحدودُ التحويل داخل الدولة لا تُمسّ ولا تُعدّ فيها هذه**.
- `cross_transfers`: **سجلُّ كلِّ تحويل** — المبلغان والسعرُ والرسمُ المستعمَلة لحظتَها، وقيودُه الثلاثة. **فالسعرُ يتغيّر في `fx_rates`
  ولا يتغيّر هنا**: ما وقع يُقرأ بسعر وقوعه.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, Currency

#: **دقّةُ السعر** — ثمانيةُ أرقامٍ بعد الفاصلة: ‎1 د.أ ≈ 190 د.ج و‎1 د.ج ≈ 0.0054 د.أ، والثانيةُ تحتاج خاناتٍ لا يحملها `MONEY`
RATE = Numeric(18, 8)


class FxRate(UUIDMixin, TimestampMixin, Base):
    """سعرُ صرف اتّجاهٍ واحد: كم يصل من `to_currency` مقابل واحدٍ من `from_currency`، ورسمُ التحويل نسبةً من المبلغ المرسَل."""

    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", name="uq_fx_rates_pair"),
        CheckConstraint("from_currency <> to_currency", name="fx_rate_distinct_pair"),
        CheckConstraint("rate > 0", name="fx_rate_positive"),
        CheckConstraint("fee_percent >= 0 AND fee_percent <= 20", name="fx_fee_percent_range"),
    )

    from_currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    to_currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    fee_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    set_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class CrossTransferLimit(UUIDMixin, TimestampMixin, Base):
    """حدّا التحويل بين الدول لكلِّ مرسلٍ في دولةٍ واحدة — بعملة دولة المرسل."""

    __tablename__ = "cross_transfer_limits"
    __table_args__ = (
        UniqueConstraint("country_code", name="uq_cross_transfer_limits_country"),
        CheckConstraint("daily_limit >= 0 AND monthly_limit >= 0", name="cross_limits_non_negative"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    daily_limit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    monthly_limit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))


class CrossTransfer(UUIDMixin, TimestampMixin, Base):
    """تحويلٌ واحدٌ بين دولتين — **بسعره ورسمه لحظةَ وقوعه**، ووصلةُ قيوده في الدفتر."""

    __tablename__ = "cross_transfers"
    __table_args__ = (
        CheckConstraint("amount > 0 AND fee >= 0 AND received > 0", name="cross_transfer_amounts"),
        CheckConstraint("from_currency <> to_currency", name="cross_transfer_distinct"),
    )

    sender_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    from_currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    to_currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    #: ما أرسله المرسلُ بعملته (بلا الرسم) · الرسمُ بعملته · وما وصل المستلمَ بعملته
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    fee: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    received: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    fee_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    rate_set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    out_transaction_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("wallet_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    in_transaction_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("wallet_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    fee_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("wallet_transactions.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
