from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import CountryCode, FeatureKey, ProviderKey

# قيم الحقول نصوص أو مفاتيح تشغيل — لا هياكل متداخلة
CredentialValue = str | bool | None


class ProviderFieldOut(BaseModel):
    """وصف حقل في بطاقة المزود — تبني منه اللوحة النموذج بلا معرفة مسبقة."""

    key: str
    label: str
    secret: bool
    required: bool


class ProviderSpecOut(BaseModel):
    provider_key: ProviderKey
    label: str
    per_country: bool
    feature_key: FeatureKey | None
    fields: list[ProviderFieldOut]


class ProviderCredentialUpsert(BaseModel):
    country_code: CountryCode | None = None
    # الحقول السرية تعود من اللوحة مقنّعة (****) وتُترك كما هي عند الحفظ
    values: dict[str, CredentialValue] = Field(default_factory=dict)
    is_active: bool | None = None


class ProviderCredentialOut(BaseModel):
    """بطاقة عقد كما تراها اللوحة — القيم السرية مقنّعة دائماً."""

    id: uuid.UUID
    provider_key: ProviderKey
    country_code: CountryCode | None
    is_active: bool
    values: dict[str, Any]
    last_tested_at: datetime | None
    updated_at: datetime


class ProviderCatalogOut(BaseModel):
    providers: list[ProviderSpecOut]
    credentials: list[ProviderCredentialOut]


class ProviderTestRequest(BaseModel):
    """رقمٌ اختياري لاختبار مزود الرسائل بإرسالٍ فعلي.

    بغيره لا تُرسل رسالة مدفوعة: زرُّ اختبارٍ يرسل إلى رقمٍ لم يطلبه أحد
    ليس اختباراً بريئاً.
    """

    test_phone: str | None = Field(default=None, max_length=20)


class ProviderTestResult(BaseModel):
    """نتيجة الاختبار — **200 حتى عند الفشل**.

    فشلُ عقدٍ عند اختباره ليس خطأً في الطلب: المشرف طلب أن يعرف، وقد عرف.
    ونصُّ السبب هو كل فائدة الزر.
    """

    ok: bool
    detail: str
    credential: ProviderCredentialOut
