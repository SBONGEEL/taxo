"""نظامُ الدفع الجديد — العقدُ على السلك (SPEC §٧٣-هـ المرحلة ١).

**وكلُّ ردٍّ يحمل `currency`** — فالمبلغُ الجزائريُّ يُصاغ «150» على السلك (`core/money_wire.py`) والأردنيُّ والليبيُّ كما هما.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CountryCode,
    Currency,
    PaymentProviderKind,
    PaymentRequestPurpose,
    PaymentRequestStatus,
    WalletOwnerType,
)

#: **معرّفُ الطريقة** — لاتينيٌّ قصيرٌ ثابت؛ والوسيطُ يُعرف به في المرحلة ٣
PROVIDER_CODE = Field(min_length=2, max_length=40, pattern=r"^[a-z][a-z0-9_]{1,39}$")


class PaymentMethodOut(BaseModel):
    """**طريقةُ دفعٍ كما يراها الراكبُ والكبتن** — بما يلزمه ليدفع: إلى أين، وما يُطلب منه."""

    id: uuid.UUID
    kind: PaymentProviderKind
    name: str
    account_holder: str | None
    account_number: str | None
    bank_name: str | None
    instructions: str | None
    has_qr: bool
    #: **الإيصالُ ورقمُ التحويل إجباريّان** — يقرؤهما التطبيقُ ليطلبهما، والخادمُ يرفض من دونهما (§٧٣-هـ/٢)
    requires_receipt: bool


class PaymentMethodsOut(BaseModel):
    currency: Currency
    methods: list[PaymentMethodOut]


class MyPaymentRequestOut(BaseModel):
    """**دفعتي كما أراها** — بحالها وسببِ رفضها أو إلغائها أو ردّها كما كُتب."""

    id: uuid.UUID
    provider_name: str
    kind: PaymentProviderKind
    purpose: PaymentRequestPurpose
    amount: Decimal
    credited_amount: Decimal | None
    currency: Currency
    status: PaymentRequestStatus
    reference: str | None
    rejection_reason: str | None
    cancel_reason: str | None
    refund_reason: str | None
    outcome_note: str | None
    created_at: datetime


class AdminPaymentMethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    kind: PaymentProviderKind
    code: str
    name: str
    integration: str | None
    enabled: bool
    for_topup: bool
    for_subscription: bool
    account_holder: str | None
    account_number: str | None
    bank_name: str | None
    instructions: str | None
    has_qr: bool
    sort_order: int
    updated_at: datetime


class AdminPaymentMethodCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    kind: PaymentProviderKind
    code: str = PROVIDER_CODE
    name: str = Field(min_length=2, max_length=80)
    enabled: bool = False
    for_topup: bool = True
    for_subscription: bool = True
    account_holder: str | None = Field(default=None, max_length=120)
    account_number: str | None = Field(default=None, max_length=64)
    bank_name: str | None = Field(default=None, max_length=120)
    instructions: str | None = Field(default=None, max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=999)


class AdminPaymentMethodUpdate(BaseModel):
    """**كلُّ حقلٍ اختياريّ** — ما لم يُرسل لا يُمسّ. **والنوعُ والمعرّفُ والسوقُ لا تتغيّر بعد الإنشاء**: الطلباتُ تُقرأ بها."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=80)
    enabled: bool | None = None
    for_topup: bool | None = None
    for_subscription: bool | None = None
    account_holder: str | None = Field(default=None, max_length=120)
    account_number: str | None = Field(default=None, max_length=64)
    bank_name: str | None = Field(default=None, max_length=120)
    instructions: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0, le=999)


class AdminPaymentRequestOut(BaseModel):
    """**طلبُ الدفع في طابور الموظّف الماليّ** — بصاحبه وطريقته وإيصاله وما جرى عليه."""

    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None
    user_phone: str | None
    owner_type: WalletOwnerType
    country_code: CountryCode
    currency: Currency
    provider_id: uuid.UUID
    provider_name: str
    kind: PaymentProviderKind
    purpose: PaymentRequestPurpose
    plan_id: uuid.UUID | None
    amount: Decimal
    credited_amount: Decimal | None
    status: PaymentRequestStatus
    reference: str | None
    external_id: str | None
    has_receipt: bool
    receipt_content_type: str | None
    rejection_reason: str | None
    cancel_reason: str | None
    refund_reason: str | None
    outcome_note: str | None
    transaction_id: uuid.UUID | None
    subscription_id: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime


class PaymentApproveIn(BaseModel):
    """**مبلغُ الموظّف — ما وصل الحسابَ فعلاً** (قرارُ المالك ٢٠٢٦-٠٨-٢٩). و`None` «بمبلغه كما ادّعى»."""

    model_config = ConfigDict(extra="forbid")

    credited_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)


class PaymentReasonIn(BaseModel):
    """**السببُ كما سيقرؤه صاحبُ الدفعة** — للرفض والردّ والإلغاء (قرارُ المالك: كلُّ رفضٍ بسببٍ مكتوب)."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class PaymentCancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)
