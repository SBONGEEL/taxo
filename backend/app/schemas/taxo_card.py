"""بطاقاتُ شحن TAXO — العقدُ على السلك (SPEC §٧٣-هـ المرحلة ٢).

**وكلُّ ردٍّ ماليٍّ يحمل `currency`**، **وأسماءُ مجاميعه تنتهي بـ`_amount`** — فيعرفها قاموسُ المال (`core/money_wire.py`) ويصوغها
«1500» للجزائريّ على السلك، والأردنيُّ والليبيُّ كما هما.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CardShopPaymentMode,
    CountryCode,
    Currency,
    TaxoCardBatchStatus,
    TaxoCardStatus,
    WalletOwnerType,
)


class TaxoCardRedeemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=40)
    wallet: WalletOwnerType | None = None


class TaxoCardRedeemedOut(BaseModel):
    serial: str
    amount: Decimal
    currency: Currency


class CardDenominationOut(BaseModel):
    id: uuid.UUID
    amount: Decimal
    currency: Currency
    is_active: bool


class CardDenominationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class CardDenominationActiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class CardShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None
    address: str | None
    discount_percent: Decimal
    payment_mode: CardShopPaymentMode
    is_active: bool
    notes: str | None


class CardShopIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    discount_percent: Decimal = Field(ge=0, lt=100, max_digits=5, decimal_places=2)
    payment_mode: CardShopPaymentMode
    notes: str | None = Field(default=None, max_length=2000)


class CardShopUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    discount_percent: Decimal | None = Field(default=None, ge=0, lt=100, max_digits=5, decimal_places=2)
    payment_mode: CardShopPaymentMode | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CardBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    denomination_id: uuid.UUID
    quantity: int = Field(ge=1, le=5000)
    shop_id: uuid.UUID | None = None
    valid_from: datetime
    expires_at: datetime


class CardBatchOut(BaseModel):
    """**الدفعةُ بأرقامها** — كلُّها من الخلفية (§14): العدُّ بالحال، وقيمةُ ما استُعمل وما سُلِّم، **والمستحقُّ من المحلّ بشرطه المجمَّد**."""

    id: uuid.UUID
    number: int
    amount: Decimal
    currency: Currency
    quantity: int
    shop_id: uuid.UUID | None
    shop_name: str | None
    discount_percent_at_issue: Decimal
    payment_mode_at_issue: CardShopPaymentMode | None
    valid_from: datetime
    expires_at: datetime
    status: TaxoCardBatchStatus
    cancel_reason: str | None
    created_at: datetime
    active: int
    redeemed: int
    cancelled: int
    redeemed_amount: Decimal
    live_amount: Decimal
    due_amount: Decimal


class CardCodeOut(BaseModel):
    serial: str
    code: str


class CardBatchCreatedOut(BaseModel):
    """**الرموزُ هنا مرّةً واحدة** — ولا بابَ يعيدها: تُخزَّن بصماتُها وحدَها."""

    batch: CardBatchOut
    codes: list[CardCodeOut]


class TaxoCardOut(BaseModel):
    id: uuid.UUID
    serial: str
    amount: Decimal
    currency: Currency
    status: TaxoCardStatus
    batch_number: int
    redeemed_at: datetime | None
    redeemed_by_name: str | None
    cancel_reason: str | None


class CardShopReportOut(BaseModel):
    shop_id: uuid.UUID
    shop_name: str
    currency: Currency
    batches: int
    cards: int
    redeemed: int
    cancelled: int
    redeemed_amount: Decimal
    live_amount: Decimal
    due_amount: Decimal


class CardGuessAlertOut(BaseModel):
    id: uuid.UUID
    scope: str
    user_name: str | None
    user_phone: str | None
    ip: str | None
    attempts: int
    created_at: datetime
    reviewed_at: datetime | None


class TaxoCardLimitsOut(BaseModel):
    max_wrong_per_account: int
    max_wrong_per_ip: int
    window_minutes: int


class TaxoCardLimitsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    max_wrong_per_account: int | None = Field(default=None, ge=1, le=100)
    max_wrong_per_ip: int | None = Field(default=None, ge=1, le=1000)
    window_minutes: int | None = Field(default=None, ge=1, le=1440)
