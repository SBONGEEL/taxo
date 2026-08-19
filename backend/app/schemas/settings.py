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
from app.schemas.config import CountryConfigOut

# كل مبلغ NUMERIC(12,3) — نفس قيد القاعدة معبَّراً عنه في طبقة الإدخال
Money = Field(ge=0, max_digits=12, decimal_places=3)
OptionalMoney = Field(default=None, ge=0, max_digits=12, decimal_places=3)


# ---------------------------------------------------------------- التسعير


# حقولُ المحطات (المرحلة 12-ب) — كلُّها **صفرٌ افتراضاً** فلا تُفتح كلفةٌ
# على راكبٍ بالسكوت، وصفرُ السقف يعني «لا سقف» لا «سقفٌ مقداره صفر»
StopMinutes = Field(default=0, ge=0, le=240)


class PricingRuleCreate(BaseModel):
    country_code: CountryCode
    vehicle_category: VehicleCategory
    base_fare: Decimal = Money
    price_per_km: Decimal = Money
    price_per_min: Decimal = Money
    minimum_fare: Decimal = Money
    cancellation_fee: Decimal = Money

    stop_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)
    stop_free_minutes: int = StopMinutes
    stop_price_per_min: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=3
    )
    stop_max_wait_minutes: int = StopMinutes

    # --- الوقفةُ غير المخطَّطة (§5.10-ب) ---
    pause_price_per_min: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=3
    )
    arrival_free_minutes: int = StopMinutes
    pause_max_minutes: int = StopMinutes


class PricingRuleUpdate(BaseModel):
    base_fare: Decimal | None = OptionalMoney
    price_per_km: Decimal | None = OptionalMoney
    price_per_min: Decimal | None = OptionalMoney
    minimum_fare: Decimal | None = OptionalMoney
    cancellation_fee: Decimal | None = OptionalMoney

    stop_fee: Decimal | None = OptionalMoney
    stop_free_minutes: int | None = Field(default=None, ge=0, le=240)
    stop_price_per_min: Decimal | None = OptionalMoney
    stop_max_wait_minutes: int | None = Field(default=None, ge=0, le=240)

    pause_price_per_min: Decimal | None = OptionalMoney
    arrival_free_minutes: int | None = Field(default=None, ge=0, le=240)
    pause_max_minutes: int | None = Field(default=None, ge=0, le=240)


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

    stop_fee: Decimal
    stop_free_minutes: int
    stop_price_per_min: Decimal
    stop_max_wait_minutes: int

    pause_price_per_min: Decimal
    arrival_free_minutes: int
    pause_max_minutes: int

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

    # ------------------------------------------- عرضُ هذا الكبتن (البند ٥٤)
    # **الخصمُ محسوبٌ لهذا الكبتن لا قائمةُ العروض القائمة**: عرضٌ يُرى ولا
    # يُطبَّق عند الضغط أسوأُ من عرضٍ لا يُرى (الفرع و). ومن لا يستحقّ يرى
    # السعرَ عارياً ولا يعلم أن ثمّة عرضاً.
    offer_name: str | None = None
    offer_discount: Decimal | None = None
    # السعرُ بعد الخصم — **يُحسب في الخلفية** كبقية المال (§14)
    price_after_discount: Decimal | None = None
    offer_ends_at: datetime | None = None
    # **اسمُ عرضٍ استفاد منه هذا الكبتنُ سلفاً فاستنفد حدَّه** — يُذكر ولا
    # يُطبَّق. و`None` لمن لم يستحقّ قطُّ: التمييزُ بينهما هو الغرض.
    exhausted_offer_name: str | None = None


class PaymentSettingOut(BaseModel):
    """سياساتُ الدفع لدولة (SPEC القسم 6.2/13.6)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    cliq_confirmation_hours: int
    # مبالغُ البقشيش (المرحلة 12-و) — صفرٌ يعني «لم يُضبط» فتُخفى الميزة
    tip_preset_small: Decimal
    tip_preset_medium: Decimal
    tip_max: Decimal
    updated_at: datetime


class PaymentSettingUpdate(BaseModel):
    """سياساتُ الدفع — والحقولُ **اختياريةٌ كلُّها** فيُعدَّل ما يُرسل وحده.

    مهلةُ كليك بالساعات وحدُّها الأعلى أسبوعٌ كي لا تُشلّ الميزة بقيمةٍ لا
    تنقضي. ومبالغُ البقشيش (المرحلة 12-و) **صفرُها يعني «لم يُضبط»** فتُخفى
    الميزة — فلا حدَّ أدنى يمنع المشرفَ من إطفائها بإعادتها إلى الصفر.
    """

    cliq_confirmation_hours: int | None = Field(default=None, ge=1, le=168)
    tip_preset_small: Decimal | None = Field(default=None, ge=0, le=1000)
    tip_preset_medium: Decimal | None = Field(default=None, ge=0, le=1000)
    tip_max: Decimal | None = Field(default=None, ge=0, le=1000)


# --------------------------------------------------- سقوف طلب رمز التحقق


class OtpSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_code: CountryCode
    window_minutes: int
    max_per_window: int
    max_per_day: int
    max_per_registration: int
    lockout_minutes: int
    resend_base_seconds: int
    resend_max_seconds: int
    updated_at: datetime


class OtpSettingUpdate(BaseModel):
    """ما يُرسَل يُطبَّق وحدَه — والحقلُ الغائب لا يُلمس.

    **وصفرُ أيِّ سقفٍ يعني «لا سقف»** ويُكتب صراحةً: هذه حرّاسٌ لا ميزات،
    فانفتاحُها يجب أن يكون قراراً مكتوباً لا سكوتاً.
    """

    window_minutes: int | None = Field(default=None, ge=1, le=1440)
    max_per_window: int | None = Field(default=None, ge=0, le=100)
    max_per_day: int | None = Field(default=None, ge=0, le=500)
    max_per_registration: int | None = Field(default=None, ge=0, le=500)
    lockout_minutes: int | None = Field(default=None, ge=0, le=1440)
    resend_base_seconds: int | None = Field(default=None, ge=5, le=600)
    resend_max_seconds: int | None = Field(default=None, ge=5, le=3600)


class OtpExhaustedOut(BaseModel):
    """أرقامٌ بلغت سقفاً اليوم — **رؤيةٌ لا منع**.

    والمنعُ يقع من العدّادات نفسِها؛ هذه القائمةُ ليرى المشرفُ تكراراً مشبوهاً
    **قبل** أن يحرق رقمَ الإرسال، لا بعده.
    """

    day: str
    phones: list[str]


class CountryRow(BaseModel):
    """دولةٌ كما تراها اللوحة — **بحالها لا مصفاةً** (SPEC §24).

    اللوحةُ ترى الدولَ كلَّها دائماً، مطفأةً كانت أو ظاهرة: من يشعل سوقاً يحتاج
    أن يراه مطفأً أولاً. و`GET /config` مصفّىً للتطبيقات، فلو قرأت اللوحةُ منه
    لاختفى عنها ما جاءت لتشعله.
    """

    country_code: CountryCode
    name: str
    visible: bool
    config: CountryConfigOut


class CountriesOut(BaseModel):
    countries: list[CountryRow]
