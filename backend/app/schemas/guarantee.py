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


class ServiceSettingUpdate(BaseModel):
    guarantee_fee: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    guarantee_late_minutes: int | None = Field(default=None, ge=1, le=120)
    guarantee_confirm_minutes: int | None = Field(default=None, ge=15, le=240)
    guarantee_confirm_window_minutes: int | None = Field(default=None, ge=1, le=60)
    guarantee_offer_hours: int | None = Field(default=None, ge=1, le=72)
    guarantee_ban_threshold: int | None = Field(default=None, ge=1, le=10)
    guarantee_ban_days: int | None = Field(default=None, ge=1, le=365)
