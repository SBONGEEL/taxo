"""الحجزُ المضمون كما يراه الكبتن (SPEC §٦٣-ج/٣) — **بلا اسم الراكب ولا رقمه**: لا يراهما في رحلةٍ عاديّةٍ أصلاً."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import Currency, VehicleCategory


class GuaranteeOfferOut(BaseModel):
    id: uuid.UUID
    scheduled_at: datetime
    vehicle_category: VehicleCategory
    pickup_lat: float
    pickup_lng: float
    pickup_address: str | None
    dropoff_lat: float
    dropoff_lng: float
    dropoff_address: str | None
    #: تقديرٌ لحظةَ الحجز — **والأجرةُ تُحسب عند التنفيذ**
    estimated_fare_at_booking: Decimal | None
    #: **رسمُ الضمان له كاملاً بلا عمولة** حين تتمّ الرحلةُ في وقتها
    guarantee_fee: Decimal
    currency: Currency
    accepted: bool
    confirm_requested: bool


class GuaranteeCancelCostOut(BaseModel):
    """**ما يكلّفه إلغاءُ الكبتن رحلتَه الآن** (§٦٣-ج/٣) — `null` حيث لا كلفة: رحلةٌ عاديّة، أو حجزٌ لم يؤكّده."""

    #: **رسمُ الضمان المجمَّد على الحجز** — يخرج من محفظته إلى الراكب بقدر رصيده (§٥-١/١٣)
    cancel_penalty: Decimal | None
    currency: Currency
    #: **كم اعتذاراً يحجبه، وكم يوماً** — من إعدادات سوقه لا من الشاشة
    ban_threshold: int
    ban_days: int


class ServiceSettingOut(BaseModel):
    """إعداداتُ الخدمات الجديدة لسوقٍ واحد (SPEC §٦٣) — **وكلُّ مبلغٍ يُضبط من اللوحة**، والأرقامُ الأولى افتراضاتُ المالك."""

    model_config = {"from_attributes": True}

    country_code: str
    #: رسمُ الضمان — **وصفرٌ يُخفي الخدمة** ولو اشتعل مفتاحُها
    guarantee_fee: Decimal
    guarantee_late_minutes: int
    guarantee_confirm_minutes: int
    guarantee_confirm_window_minutes: int
    guarantee_offer_hours: int
    guarantee_ban_threshold: int
    guarantee_ban_days: int
    #: رسمُ الطرد للكبتن (§٦٣-ج/٤) — وصفرٌ يُخفيه
    parcel_fee: Decimal
    #: بالساعة (§٦٣-ج/٥) — السعرُ وكيلومتراتُ الساعة ودقائقُ الإلغاء وأقصى الساعات
    hourly_rate: Decimal
    hourly_km_per_hour: int
    hourly_cancel_minutes: int
    hourly_max_hours: int
    #: المشوارُ الثابت (§٦٣-ج/٦) — الخصمُ وحافزُ الكبتن المعتمد وأقصى أيام التعليق
    commute_discount_percent: Decimal
    commute_captain_incentive: Decimal
    commute_max_suspend_days: int
    #: بين المدن (§٦٣-ج/٧) — مهلةُ إلغاء الكبتن بالساعات
    intercity_cancel_deadline_hours: int
    #: الاسترداد الأسبوعي (§٦٣-ج/٨) — المبلغُ وأيامُ الأسبوع بلا جمعته
    cashback_amount: Decimal
    cashback_days: int
    #: **محادثةُ الرحلة ومكالمتُها** (§٦٦) — مدّةُ الاحتفاظ بالمحادثة وسجلِّ المكالمات، **والتسجيلُ (مطفأٌ افتراضاً)** ومدّتُه
    chat_retention_days: int
    call_recording_enabled: bool
    call_recording_retention_days: int


class ServiceSettingUpdate(BaseModel):
    guarantee_fee: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    guarantee_late_minutes: int | None = Field(default=None, ge=1, le=120)
    guarantee_confirm_minutes: int | None = Field(default=None, ge=15, le=240)
    guarantee_confirm_window_minutes: int | None = Field(default=None, ge=1, le=60)
    guarantee_offer_hours: int | None = Field(default=None, ge=1, le=72)
    guarantee_ban_threshold: int | None = Field(default=None, ge=1, le=10)
    guarantee_ban_days: int | None = Field(default=None, ge=1, le=365)
    parcel_fee: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    hourly_rate: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    hourly_km_per_hour: int | None = Field(default=None, ge=0, le=200)
    hourly_cancel_minutes: int | None = Field(default=None, ge=0, le=240)
    hourly_max_hours: int | None = Field(default=None, ge=1, le=24)
    commute_discount_percent: Decimal | None = Field(default=None, ge=0, lt=100, max_digits=5, decimal_places=2)
    commute_captain_incentive: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    commute_max_suspend_days: int | None = Field(default=None, ge=0, le=31)
    intercity_cancel_deadline_hours: int | None = Field(default=None, ge=1, le=48)
    cashback_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    cashback_days: int | None = Field(default=None, ge=2, le=14)
    chat_retention_days: int | None = Field(default=None, ge=1, le=3650)
    #: **إشعالُه يشترط نشرَ «تسجيلُ المكالمات» في سياستَي السوق** — يحرسه بابُ الكتابة لا الشاشة
    call_recording_enabled: bool | None = None
    call_recording_retention_days: int | None = Field(default=None, ge=1, le=3650)
