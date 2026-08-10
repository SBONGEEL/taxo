from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    Currency,
    DisputeResolution,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    ProviderOrderPurpose,
    ProviderOrderStatus,
)

# نفس مفتاح عدم التكرار المستعمل في التحويل — القسم 14 يفرضه على الدفع أيضاً
IdempotencyKey = Field(min_length=8, max_length=64)


class PaymentCreate(BaseModel):
    """اختيار الراكب لقناة الدفع بعد اكتمال الرحلة.

    لا مبلغ هنا: المبلغ هو المتبقي من `final_fare` محسوباً في الخلفية —
    التسعير في الخلفية حصراً (SPEC القسم 14).
    """

    method: PaymentMethod
    idempotency_key: str = IdempotencyKey

    # للبطاقة وحدها (SPEC القسم 6.4): حفظُ البطاقة قرارُ صاحبها لا افتراضُنا،
    # و`saved_card_id` هو «الدفع بضغطة» — بطاقةٌ محفوظة سلفاً بلا صفحة دفع
    save_card: bool = False
    saved_card_id: uuid.UUID | None = None


class PaymentDisputeRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class PaymentResolveRequest(BaseModel):
    resolution: DisputeResolution
    note: str | None = Field(default=None, max_length=255)


class PaymentRefundRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ride_id: uuid.UUID
    method: PaymentMethod
    provider: PaymentProvider | None
    provider_payment_id: str | None
    amount: Decimal
    currency: Currency
    status: PaymentStatus
    confirmed_by: PaymentConfirmedBy | None
    confirmed_at: datetime | None
    transaction_id: uuid.UUID | None

    dispute_reason: str | None
    disputed_at: datetime | None
    resolution: DisputeResolution | None
    resolution_note: str | None
    resolved_at: datetime | None

    created_at: datetime


class CardOrderOut(BaseModel):
    """طلب الدفع لدى المزود كما تراه الواجهة (SPEC القسم 6.4).

    `redirect_url` هو ما تفتحه الواجهة، و`cart_id` هو ما تسأل به عن الحال بعد
    العودة. لا مرجعَ مزودٍ داخلياً هنا ولا مفتاحَ عقد: الواجهة تعرض وتنتظر.
    """

    model_config = ConfigDict(from_attributes=True)

    cart_id: str
    provider: PaymentProvider
    purpose: ProviderOrderPurpose
    status: ProviderOrderStatus
    amount: Decimal
    currency: Currency
    redirect_url: str | None
    failure_reason: str | None
    transaction_id: uuid.UUID | None
    created_at: datetime


class RidePaymentsOut(BaseModel):
    """حال الدفع على رحلة كاملةً — لا دفعةً واحدة.

    الدفع المختلط صفّان (SPEC القسم 6)، فالردّ على «ادفع» قائمةٌ دائماً وإن
    كان فيها عنصر واحد. `cliq_alias` يظهر مع دفعة كليك وحدها: هو ما تعرضه
    شاشة الدفع مع زر النسخ (القسم 6.2). و`card_order` يظهر مع طلب بطاقةٍ لم
    يُحسم: منه تبني الواجهة «متابعة الدفع» بعد عودةٍ مقطوعة (القسم 6.4).
    """

    ride_id: uuid.UUID
    currency: Currency
    final_fare: Decimal | None
    outstanding: Decimal
    payments: list[PaymentOut]
    cliq_alias: str | None = None
    card_order: CardOrderOut | None = None


class CardTopupCreate(BaseModel):
    """شحن محفظة بالبطاقة — فوريٌّ آلي بلا طلبٍ ينتظر إنساناً (SPEC القسم 7)."""

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    save_card: bool = False
    saved_card_id: uuid.UUID | None = None


class SavedCardOut(BaseModel):
    """ما يُعرض من بطاقةٍ محفوظة — **لا رمزَ المزود ولا رقمَ بطاقة**.

    `provider_token` لا يخرج من الخلفية أبداً: هو ما يُدفع به، وعرضُه يبطل
    غرضَ الـ tokenization كلَّه (SPEC القسم 4).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: PaymentProvider
    brand: str | None
    last4: str
    expiry_month: int
    expiry_year: int
    is_default: bool
    created_at: datetime
