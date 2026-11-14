"""بطاقاتُ شحن TAXO — العقدُ على السلك (SPEC §٧٣-هـ المرحلة ٢).

**وكلُّ ردٍّ ماليٍّ يحمل `currency`**، **وأسماءُ مجاميعه تنتهي بـ`_amount`** — فيعرفها قاموسُ المال (`core/money_wire.py`) ويصوغها
«1500» للجزائريّ على السلك، والأردنيُّ والليبيُّ كما هما.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CardShopPaymentMode,
    CountryCode,
    Currency,
    TaxoCardBatchStatus,
    TaxoCardState,
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
    #: **دفعةٌ تُباع لشركةٍ بفاتورة** (§١٠٠-ب/٧) — بلا محلّ
    buyer_company: str | None = Field(default=None, min_length=2, max_length=160)
    buyer_tax_number: str | None = Field(default=None, max_length=40)


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
    #: **غيرُ مستعملةٍ تعمل** و**منتهيةٌ لم تُستعمل** — مجموعُهما `active`، ومن نافذة الدفعة لحظةَ القراءة
    unused: int
    expired: int
    redeemed_amount: Decimal
    live_amount: Decimal
    due_amount: Decimal
    #: **نوعُ الدفعة** (§١٠٠-أ/٣): `batch` أو `gift` أو `pos`
    kind: str = "batch"
    #: **دفعةُ شركة** (§١٠٠-ب/٧) — اسمُها ورقمُها الضريبيّ ورقمُ فاتورتها
    buyer_company: str | None = None
    buyer_tax_number: str | None = None
    invoice_number: str | None = None


class CardCodeOut(BaseModel):
    serial: str
    code: str


class CardExportIn(BaseModel):
    """**ملفُّ الدفعة لحظةَ إنشائها** (SPEC §١٠٠-أ/١) — الرموزُ من ردّ الإنشاء في يد اللوحة، **وكلمةُ السرّ لا تُخزَّن ولا تُسجَّل**."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["xlsx", "pdf", "sheet", "gift"]
    #: **تصميمُ النسخة المطبوعة للهدية** (للصيغة `gift` وحدَها)
    design: Literal["night", "sunrise", "city"] = "night"
    password: str = Field(min_length=8, max_length=128)
    codes: list[CardCodeOut] = Field(min_length=1, max_length=5000)


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
    #: **الحالُ كما تُقرأ** — `unused` · `redeemed` · `expired` · `cancelled` · `not_started` (من نافذة الدفعة لحظةَ القراءة)
    state: TaxoCardState = TaxoCardState.UNUSED
    #: **من باعها ومتى** (§١٠٠-ب/٤): المحلُّ من الدفعة، ونوعُها، **ومن أصدرها** (البائعُ في `pos`، والمشرفُ في غيرها) ووقتُ إصدارها
    batch_kind: str = "batch"
    shop_name: str | None = None
    issued_by_name: str | None = None
    issued_at: datetime | None = None


class BatchCardsOut(BaseModel):
    """**بطاقاتُ دفعة** (SPEC §١٠٠-أ/٢) — بلا رمز: التسلسلُ والحالُ والاستعمال وحدَها."""

    total: int
    cards: list[TaxoCardOut]


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


# ------------------------------------------------------------------ بطاقاتُ الهدية (§١٠٠-أ/٣)


class GiftCreateIn(BaseModel):
    """**هديةٌ تُولَّد الآن** بفئةٍ وضعها المالك: رابطٌ خاصٌّ أو نسخةٌ مطبوعة."""

    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    denomination_id: uuid.UUID
    design: Literal["night", "sunrise", "city"]
    delivery: Literal["link", "print"] = "link"
    expires_at: datetime
    recipient_name: str | None = Field(default=None, max_length=80)
    message: str | None = Field(default=None, max_length=200)


class GiftLinkOut(BaseModel):
    """**الهديةُ بحالها وأوقاتها**، بلا رمزٍ ولا رابط."""

    id: uuid.UUID
    card_id: uuid.UUID
    serial: str
    amount: Decimal
    currency: Currency
    design: str
    recipient_name: str | None
    message: str | None
    state: str
    sent_channel: str | None
    created_at: datetime
    sent_at: datetime | None
    opened_at: datetime | None
    open_count: int
    scratched_at: datetime | None
    redeemed_at: datetime | None
    expires_at: datetime
    cancelled_at: datetime | None
    cancel_reason: str | None


class GiftCreatedOut(BaseModel):
    """**الرابطُ أو الرمزُ هنا مرّةً واحدة**، ولا بابَ يعيدهما."""

    gift: GiftLinkOut | None
    batch_id: uuid.UUID
    serial: str
    url: str | None = None
    code: CardCodeOut | None = None


class GiftSentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal["whatsapp", "sms", "email", "copy"]


class GiftTokenIn(BaseModel):
    """**الرابطُ الخاصُّ في جسم الطلب** لا في المسار، فلا يقع في سجلِّ وصول."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=16, max_length=64)


class GiftPublicOut(BaseModel):
    """**ما تراه صفحةُ الهدية قبل الكشط**، بلا رمز."""

    amount: Decimal
    currency: Currency
    country_code: CountryCode
    design: str
    recipient_name: str | None
    message: str | None
    state: str
    expires_at: datetime


class GiftScratchedOut(BaseModel):
    code: str
    amount: Decimal
    currency: Currency


# ------------------------------------------------------------------ البائعون والبيعُ لحظةَ الطلب (§١٠٠-ب/٤–٥)


class PosSettingsOut(BaseModel):
    pos_enabled: bool
    pos_daily_cap: int
    pos_validity_days: int


class PosSettingsIn(BaseModel):
    """**يفتحه المالكُ وحدَه** — والسقفُ عددُ بطاقاتٍ لا مال."""

    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    pos_enabled: bool | None = None
    pos_daily_cap: int | None = Field(default=None, ge=1, le=500)
    pos_validity_days: int | None = Field(default=None, ge=30, le=1095)


class SellerOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    username: str | None
    shop_id: uuid.UUID
    shop_name: str
    is_active: bool
    is_blocked: bool
    has_factor: bool
    must_change_password: bool
    created_at: datetime
    currency: Currency
    sold: int = 0
    redeemed: int = 0
    cancelled: int = 0
    sold_amount: Decimal = Decimal("0")
    redeemed_amount: Decimal = Decimal("0")


class SellerCreateIn(BaseModel):
    """**يكتبه المالك** — والكلمةُ مؤقّتةٌ تتغيّر عند أوّل دخول."""

    model_config = ConfigDict(extra="forbid")

    shop_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class SellerActiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class ResellerDenominationOut(BaseModel):
    id: uuid.UUID
    amount: Decimal
    currency: Currency


class ResellerMeOut(BaseModel):
    """**ما يراه البائع**: محلُّه وفئاتُ سوقه، وهل البيعُ مفتوح، وكم باع في آخر ٢٤ ساعة من سقفه."""

    name: str
    shop_name: str
    country_code: CountryCode
    currency: Currency
    enabled: bool
    sold_today: int
    daily_cap: int
    validity_days: int
    denominations: list[ResellerDenominationOut]


class ResellerSellIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    denomination_id: uuid.UUID


class ResellerSaleOut(BaseModel):
    """**الرمزُ هنا مرّةً واحدةً للإيصال** — ولا يُخزَّن إلا بصمتُه."""

    serial: str
    code: str
    amount: Decimal
    currency: Currency
    shop_name: str
    sold_at: datetime
    expires_at: datetime


class ResellerSaleRowOut(BaseModel):
    serial: str
    amount: Decimal
    currency: Currency
    state: TaxoCardState
    sold_at: datetime
    redeemed_at: datetime | None


class InvoiceSettingsOut(BaseModel):
    """**البائعُ على فاتورة الشركات** (§١٠٠-ب/٧) — يكتبه المالك، وفارغُه يُطبع «TAXO» وحدَها."""

    invoice_seller_name: str | None
    invoice_seller_tax_number: str | None


class InvoiceSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    invoice_seller_name: str | None = Field(default=None, max_length=160)
    invoice_seller_tax_number: str | None = Field(default=None, max_length=40)


class CardBatchExtendIn(BaseModel):
    """**التمديدُ بسببٍ مكتوب** (§١٠٠-ب/١٢)."""

    model_config = ConfigDict(extra="forbid")

    expires_at: datetime
    reason: str = Field(min_length=3, max_length=500)


class CardKindReportOut(BaseModel):
    """**سطرُ نوعٍ في تقرير البطاقات** (§١٠٠-ب/١٤) — `batch` مطبوعة · `gift` هدية · `pos` بيعٌ في المحلّ · `corporate` للشركات (من المطبوعة)."""

    kind: str
    currency: Currency
    batches: int
    cards: int
    redeemed: int
    cancelled: int
    unused: int
    expired: int
    #: **نسبةُ الاستعمال** من البطاقات غير الملغاة، بخانةٍ عشريّةٍ واحدة — نصٌّ لا كسرٌ عائم
    redemption_rate: str
    issued_amount: Decimal
    redeemed_amount: Decimal
    outstanding_amount: Decimal
    expired_amount: Decimal
