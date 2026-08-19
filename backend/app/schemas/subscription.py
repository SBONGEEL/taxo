from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CountryCode,
    Currency,
    PaymentMethod,
    SubscriptionDurationType,
    SubscriptionStatus,
)
from app.models.subscription import DriverSubscription
from app.schemas.settings import SubscriptionPlanOut

# نفس مفتاح عدم التكرار المستعمل في الدفع والتحويل (SPEC القسم 14)
IdempotencyKey = Field(min_length=8, max_length=64)


class SubscriptionPurchase(BaseModel):
    """شراء اشتراك من رصيد المحفظة.

    لا مبلغ هنا: السعر سعرُ الخطة محسوباً في الخلفية — كل حساب مالي في الخلفية
    حصراً (SPEC القسم 14).
    """

    plan_id: uuid.UUID
    idempotency_key: str = IdempotencyKey


class SubscriptionCardPurchase(BaseModel):
    """شراء اشتراك بالبطاقة — لا مفتاح عدم تكرار من العميل.

    مفتاحه مشتقٌّ من صفّ الطلب لدى المزود (`card-subscription:{id}`): الحسم
    يأتي من المزود لا من ضغطة العميل، فمفتاحٌ يرسله العميل لا يحرس شيئاً هنا.
    """

    plan_id: uuid.UUID
    save_card: bool = False
    saved_card_id: uuid.UUID | None = None


class AdminSubscriptionCreate(BaseModel):
    """تسجيل اشتراكٍ قبضته الإدارة كاشاً أو كليكاً (SPEC القسم 8/13.5)."""

    driver_id: uuid.UUID
    plan_id: uuid.UUID
    method: PaymentMethod
    # فارغٌ يعني «بسعر الخطة» — والقيمة الصريحة لخصمٍ أو تسويةٍ يقرّرها المشرف
    amount_paid: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=3
    )
    reference: str | None = Field(default=None, max_length=120)


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_id: uuid.UUID
    plan_id: uuid.UUID
    plan_name: str
    duration_type: SubscriptionDurationType
    country_code: CountryCode
    currency: Currency
    starts_at: datetime
    expires_at: datetime
    amount_paid: Decimal
    # **ما سُجّل فعلاً لا ما حسبه العرض** (البند ٥٤، شرطُ المالك): لو حصّل
    # المشرفُ السعرَ كاملاً بالخطأ فلا يرى الكبتنُ خصماً لم ينله — و
    # `discount_amount` هو الفرقُ بين المجمَّد والمدفوع، لا قرارُ العرض.
    list_price: Decimal
    discount_amount: Decimal
    payment_method: PaymentMethod
    status: SubscriptionStatus
    transaction_id: uuid.UUID | None
    reference: str | None
    created_at: datetime

    @classmethod
    def from_subscription(cls, subscription: DriverSubscription) -> "SubscriptionOut":
        """يحتاج `plan` محمّلةً — اسم الخطة ومدتها يُعرضان مع كل صف."""
        plan = subscription.plan
        return cls(
            id=subscription.id,
            driver_id=subscription.driver_id,
            plan_id=subscription.plan_id,
            plan_name=plan.name,
            duration_type=plan.duration_type,
            country_code=plan.country_code,
            currency=plan.currency,
            starts_at=subscription.starts_at,
            expires_at=subscription.expires_at,
            amount_paid=subscription.amount_paid,
            list_price=subscription.list_price,
            discount_amount=subscription.discount_amount,
            payment_method=subscription.payment_method,
            status=subscription.status,
            transaction_id=subscription.transaction_id,
            reference=subscription.reference,
            created_at=subscription.created_at,
        )


class MySubscriptionOut(BaseModel):
    """شاشة «اشتراكي» في تطبيق الكبتن (SPEC القسم 12.5).

    `days_remaining` و`coverage_until` مبنيان على **نهاية التغطية** لا على
    الصف الحالي: من جدّد مبكراً له صفّان متتاليان، وعدُّ أيام أولهما وحده يقول
    له إن اشتراكه ينتهي غداً وهو مغطّى شهراً.
    """

    is_active: bool
    coverage_until: datetime | None
    days_remaining: int
    current: SubscriptionOut | None
    plans: list[SubscriptionPlanOut]
