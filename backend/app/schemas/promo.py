"""مخطّطاتُ الكوبونات (SPEC القسم 6.6، المرحلة 12-ز)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class PromoCodeCreate(BaseModel):
    """رمزٌ جديد — و`budget_total` **مطلوبٌ** (شرطُ المالك: لكل رمزٍ سقف)."""

    code: str = Field(min_length=2, max_length=32)
    country_code: CountryCode
    discount_type: PromoDiscountType
    discount_value: Decimal = Field(gt=0, le=100000)
    max_discount: Decimal | None = Field(default=None, gt=0, le=100000)
    budget_total: Decimal = Field(ge=0, le=1000000)
    per_user_limit: int = Field(default=1, ge=1, le=100)
    total_usage_limit: int | None = Field(default=None, ge=1)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _percent_needs_sense(self) -> PromoCodeCreate:
        if self.discount_type is PromoDiscountType.PERCENT and self.discount_value > 100:
            raise ValueError("النسبة لا تتجاوز ١٠٠٪")
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until <= self.valid_from
        ):
            raise ValueError("تاريخ الانتهاء بعد تاريخ البداية")
        return self


class PromoCodeUpdate(BaseModel):
    """**ولا `code` فيه**: رحلاتٌ تشير إلى الرمز بمعرّفه، وتغييرُ نصِّه يجعل
    ملصقاً في الشارع يشير إلى عرضٍ آخر. والرمزُ الخاطئ يُطفأ ويُنشأ غيرُه."""

    discount_value: Decimal | None = Field(default=None, gt=0, le=100000)
    max_discount: Decimal | None = Field(default=None, gt=0, le=100000)
    budget_total: Decimal | None = Field(default=None, ge=0, le=1000000)
    per_user_limit: int | None = Field(default=None, ge=1, le=100)
    total_usage_limit: int | None = Field(default=None, ge=1)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool | None = None


class PromoCodeOut(BaseModel):
    """صفُّ رمزٍ كما تراه اللوحة — ومعه **المحسوبُ** لا المراكم.

    ثلاثةُ أرقامٍ لا رقم: `spent` ما دُفع فعلاً، و`committed` ما دُفع **ومعه ما
    وُعد به في رحلاتٍ جارية** (وهو ما يُقاس به السقف)، و`used_count` عددُ
    الرحلات. وكلُّها استعلامٌ لا عمود (القسم 6.6).

    و`committed` قد **يتجاوز** `budget_total`: السقفُ يمنع تطبيقاً جديداً لا
    رحلةً تحمل الرمز، فرقمٌ مقصوصٌ عنده يجعل المشرفَ يظنه صارماً.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    country_code: CountryCode
    discount_type: PromoDiscountType
    discount_value: Decimal
    max_discount: Decimal | None
    budget_total: Decimal
    per_user_limit: int
    total_usage_limit: int | None
    valid_from: datetime | None
    valid_until: datetime | None
    is_active: bool
    spent: Decimal
    committed: Decimal
    used_count: int
