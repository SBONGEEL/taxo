from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CommissionAppliesTo,
    CountryCode,
    Currency,
    FeatureKey,
    SubscriptionDurationType,
    VehicleCategory,
)

# كل مبلغ NUMERIC(12,3) — نفس قيد القاعدة معبَّراً عنه في طبقة الإدخال
Money = Field(ge=0, max_digits=12, decimal_places=3)
OptionalMoney = Field(default=None, ge=0, max_digits=12, decimal_places=3)


# ---------------------------------------------------------------- التسعير


class PricingRuleCreate(BaseModel):
    country_code: CountryCode
    vehicle_category: VehicleCategory
    base_fare: Decimal = Money
    price_per_km: Decimal = Money
    price_per_min: Decimal = Money
    minimum_fare: Decimal = Money
    cancellation_fee: Decimal = Money


class PricingRuleUpdate(BaseModel):
    base_fare: Decimal | None = OptionalMoney
    price_per_km: Decimal | None = OptionalMoney
    price_per_min: Decimal | None = OptionalMoney
    minimum_fare: Decimal | None = OptionalMoney
    cancellation_fee: Decimal | None = OptionalMoney


class PricingRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    vehicle_category: VehicleCategory
    base_fare: Decimal
    price_per_km: Decimal
    price_per_min: Decimal
    minimum_fare: Decimal
    cancellation_fee: Decimal
    updated_at: datetime


# ------------------------------------------------------------ مفاتيح الميزات


class FeatureFlagUpsert(BaseModel):
    country_code: CountryCode
    feature_key: FeatureKey
    enabled: bool
    # **إلزامي لإطفاء مفتاحٍ حارس** (`otp_verification_enabled`): إجراءُ
    # طوارئ يُسأل عنه لاحقاً، وسجلُّ تدقيقٍ يقول «أُطفئ» بلا «لماذا» نصفُ سجل
    reason: str | None = Field(default=None, min_length=8, max_length=280)


class CountryFeatureFlagsOut(BaseModel):
    country_code: CountryCode
    flags: dict[str, bool]


# ------------------------------------------------------------------ العمولة


class CommissionSettingUpdate(BaseModel):
    commission_enabled: bool | None = None
    commission_percent: Decimal | None = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    applies_to: CommissionAppliesTo | None = None


class CommissionSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    commission_enabled: bool
    commission_percent: Decimal
    applies_to: CommissionAppliesTo
    updated_at: datetime


# ------------------------------------------------------------ خطط الاشتراك


class SubscriptionPlanCreate(BaseModel):
    # العملة تُشتق من الدولة في الخلفية — لا تُقبل من العميل
    country_code: CountryCode
    name: str = Field(min_length=2, max_length=120)
    duration_type: SubscriptionDurationType
    price: Decimal = Money
    is_active: bool = True


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    duration_type: SubscriptionDurationType | None = None
    price: Decimal | None = OptionalMoney
    is_active: bool | None = None


class SubscriptionPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    name: str
    duration_type: SubscriptionDurationType
    price: Decimal
    currency: Currency
    is_active: bool
    updated_at: datetime
