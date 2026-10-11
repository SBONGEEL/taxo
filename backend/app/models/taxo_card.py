"""بطاقاتُ شحن TAXO — الفئاتُ والمحلّاتُ والدفعاتُ والبطاقات (SPEC §٧٣-أ/٧، §٧٣-هـ المرحلة ٢).

**الرمزُ لا يُخزَّن**: تُخزَّن بصمتُه (`code_hash` — `HMAC-SHA256` بسرِّ `TAXO_CARD_CODE_PEPPER`) ويُعرض نصُّه مرّةً لحظةَ التوليد؛ **فتسريبُ
القاعدة لا يكشف رمزاً**. والرقمُ التسلسليُّ عامٌّ يُطبع ويُبحث به ولا يشحن.

**ولا حذف**: الترحيلةُ `0113` تضع مُشغّلاً يرفض `DELETE` على الدفعات والبطاقات — الإلغاءُ بسببٍ مكتوبٍ هو ما يُوقف بطاقة.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    CardShopPaymentMode,
    CountryCode,
    Currency,
    TaxoCardBatchStatus,
    TaxoCardStatus,
    WalletOwnerType,
)


class CardDenomination(UUIDMixin, TimestampMixin, Base):
    """**فئةٌ ثابتةٌ يضعها المالك** لكلِّ دولة — ولا فئةَ مبذورة (لا تُخترع قيم)."""

    __tablename__ = "card_denominations"
    __table_args__ = (
        UniqueConstraint("country_code", "amount"),
        CheckConstraint("amount > 0", name="card_denomination_positive"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class CardShop(UUIDMixin, TimestampMixin, Base):
    """**محلٌّ يبيع البطاقات** — خصمُه ونمطُ دفعه من اللوحة (§٧٣-أ/٧)، **وتجمّدهما الدفعةُ لحظةَ إصدارها**."""

    __tablename__ = "card_shops"
    __table_args__ = (
        CheckConstraint("discount_percent >= 0 AND discount_percent < 100", name="card_shop_discount_range"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"), server_default=text("0"))
    payment_mode: Mapped[CardShopPaymentMode] = mapped_column(
        pg_enum(CardShopPaymentMode, "card_shop_payment_mode"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CardBatch(UUIDMixin, TimestampMixin, Base):
    """**دفعةُ بطاقاتٍ تُولَّد معاً** — بفئتها ومحلّها ونافذتها، **مجمَّدةً لحظةَ الإصدار** فتعديلُ المحلّ بعدها لا يغيّر ما بيعه."""

    __tablename__ = "card_batches"
    __table_args__ = (
        UniqueConstraint("country_code", "number"),
        CheckConstraint("amount > 0", name="card_batch_amount_positive"),
        CheckConstraint("quantity > 0", name="card_batch_quantity_positive"),
        CheckConstraint("expires_at > valid_from", name="card_batch_window"),
        CheckConstraint(
            "status <> 'cancelled' OR length(btrim(coalesce(cancel_reason, ''))) > 0", name="card_batch_cancel_has_reason"
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    #: رقمُ الدفعة في سوقها — يدخل الرقمَ التسلسليَّ لكلِّ بطاقة
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    shop_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("card_shops.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_percent_at_issue: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))
    payment_mode_at_issue: Mapped[CardShopPaymentMode | None] = mapped_column(
        pg_enum(CardShopPaymentMode, "card_shop_payment_mode"), nullable=True
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[TaxoCardBatchStatus] = mapped_column(
        pg_enum(TaxoCardBatchStatus, "taxo_card_batch_status"), nullable=False, default=TaxoCardBatchStatus.ACTIVE
    )
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    shop: Mapped[CardShop | None] = relationship(CardShop, lazy="joined")


class TaxoCard(UUIDMixin, TimestampMixin, Base):
    """**بطاقةٌ واحدة** — بصمةُ رمزها ورقمُها التسلسليُّ وحالُها، **ومن استعملها ومتى وأين قُيّدت**."""

    __tablename__ = "taxo_cards"
    __table_args__ = (
        CheckConstraint("amount > 0", name="taxo_card_amount_positive"),
        CheckConstraint(
            "status <> 'cancelled' OR length(btrim(coalesce(cancel_reason, ''))) > 0", name="taxo_card_cancel_has_reason"
        ),
        CheckConstraint(
            "status <> 'redeemed' OR (redeemed_by IS NOT NULL AND transaction_id IS NOT NULL)", name="taxo_card_redeemed_traced"
        ),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("card_batches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    serial: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    #: **بصمةُ الرمز لا الرمز** — `HMAC-SHA256` بأربعةٍ وستّين حرفاً ستّ عشريّاً
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[TaxoCardStatus] = mapped_column(
        pg_enum(TaxoCardStatus, "taxo_card_status"), nullable=False, default=TaxoCardStatus.ACTIVE, index=True
    )
    redeemed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    redeemed_owner_type: Mapped[WalletOwnerType | None] = mapped_column(
        pg_enum(WalletOwnerType, "wallet_owner_type"), nullable=True
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("wallet_transactions.id", ondelete="RESTRICT"), nullable=True
    )
    payment_request_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("payment_requests.id", ondelete="RESTRICT"), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped[CardBatch] = relationship(CardBatch, lazy="joined")


class TaxoCardSetting(UUIDMixin, TimestampMixin, Base):
    """**سقوفُ التخمين لكلِّ دولة** (§٧٣-هـ المرحلة ٢/٨) — حدودٌ أمنيّةٌ لا مال، تُضبط من اللوحة."""

    __tablename__ = "taxo_card_settings"
    __table_args__ = (
        UniqueConstraint("country_code"),
        CheckConstraint(
            "max_wrong_per_account >= 1 AND max_wrong_per_ip >= 1 AND window_minutes >= 1", name="taxo_card_settings_positive"
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    max_wrong_per_account: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default=text("5"))
    max_wrong_per_ip: Mapped[int] = mapped_column(Integer, nullable=False, default=20, server_default=text("20"))
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default=text("60"))


class CardGuessAlert(UUIDMixin, TimestampMixin, Base):
    """**تنبيهٌ في اللوحة**: حسابٌ أو عنوانٌ بلغ سقفَ المحاولات الخاطئة — **يُكتب مرّةً عند البلوغ** ويُعلَّم «رُوجع» بيد مشرف."""

    __tablename__ = "card_guess_alerts"

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    #: `account` أو `ip`
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
