"""مخطّطاتُ الكوبونات (SPEC القسم 6.6، المرحلة 12-ز)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode, PromoDiscountType


class PromoValidateRequest(BaseModel):
    """تحقّقٌ لا يستهلك شيئاً — لزرِّ «تطبيق» قبل الطلب.

    و`fare` هو **التقديرُ المعروض** على الشاشة: الخصمُ النهائي يُحسب على الأجرة
    الفعلية عند الإنهاء، وهذا الرقمُ عرضٌ لا التزام. ولا تحسبه الشاشةُ بنفسها
    (القسم 14): نسبةٌ تُضرب في الواجهة تفترق عن نسبةٍ تُضرب في الخلفية.
    """

    code: str = Field(min_length=2, max_length=32)
    country_code: CountryCode
    fare: Decimal = Field(gt=0, le=100000)


class PromoPreviewOut(BaseModel):
    code: str
    discount_type: PromoDiscountType
    discount: Decimal
    fare_after: Decimal
    currency: str


class PromoCodeOut(BaseModel):
    """صفُّ رمزٍ كما تراه اللوحة — ومعه **المصروفُ محسوباً** لا مراكماً.

    و`spent` قد **يتجاوز** `budget_total`: السقفُ يمنع تطبيقاً جديداً لا رحلةً
    تحمل الرمز (القسم 6.6)، فرقمٌ مقصوصٌ عند السقف يجعل المشرفَ يظنه صارماً.
    """

    model_config = ConfigDict(from_attributes=True)

    id: object
    code: str
    country_code: CountryCode
    discount_type: PromoDiscountType
    discount_value: Decimal
    max_discount: Decimal | None
    budget_total: Decimal
    per_user_limit: int
    total_usage_limit: int | None
    valid_from: object | None
    valid_until: object | None
    is_active: bool
    spent: Decimal
    used_count: int
