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


class RidePaymentsOut(BaseModel):
    """حال الدفع على رحلة كاملةً — لا دفعةً واحدة.

    الدفع المختلط صفّان (SPEC القسم 6)، فالردّ على «ادفع» قائمةٌ دائماً وإن
    كان فيها عنصر واحد. `cliq_alias` يظهر مع دفعة كليك وحدها: هو ما تعرضه
    شاشة الدفع مع زر النسخ (القسم 6.2).
    """

    ride_id: uuid.UUID
    currency: Currency
    final_fare: Decimal | None
    outstanding: Decimal
    payments: list[PaymentOut]
    cliq_alias: str | None = None
