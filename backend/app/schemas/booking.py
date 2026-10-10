"""مخطّطاتُ الرحلات المجدولة (SPEC القسم 5.11، المرحلة 12-ط)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    BookingStatus,
    Currency,
    GenderPreference,
    PaymentMethod,
    RideStatus,
)
from app.schemas.ride import CoordinatesIn
from app.schemas.category import CategoryKey


class BookingCreate(BaseModel):
    """حجزٌ جديد — نفسُ حقول الطلب الفوري ومعها الموعد.

    **ولا محطاتٍ وسيطة ولا تكرار** في هذا القطع (القسم 5.11): كلاهما بندٌ
    مستقلٌّ في `FUTURE-FEATURES` 29 بحجمه الحقيقي.
    """

    pickup: CoordinatesIn
    dropoff: CoordinatesIn
    scheduled_at: datetime
    vehicle_category: CategoryKey
    pickup_address: str | None = Field(default=None, max_length=255)
    dropoff_address: str | None = Field(default=None, max_length=255)
    gender_preference: GenderPreference | None = None
    payment_method_hint: PaymentMethod | None = None
    # **حجزٌ مضمون** (§٦٣-ج/٣) — رسمُه من المحفظة لحظةَ الحجز، ولا يُطلب قبل ساعتين من موعده
    guaranteed: bool = False


class BookingOut(BaseModel):
    """حجزٌ كما يقرؤه صاحبُه.

    **و`ride_status` مقروءةٌ من الرحلة لا محفوظةٌ على الحجز**: ما جرى بعد
    التسليم تقوله الرحلةُ نفسُها (لا عمودَ `fulfilled` هنا)، والشاشةُ تبني
    الجملةَ من الاثنين — نفسُ قاعدةِ بناء نصِّ الإشعار من `data`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: BookingStatus
    scheduled_at: datetime
    vehicle_category: CategoryKey
    gender_preference: GenderPreference
    payment_method_hint: PaymentMethod | None
    pickup_lat: float
    pickup_lng: float
    pickup_address: str | None
    dropoff_lat: float
    dropoff_lng: float
    dropoff_address: str | None
    # **اسمُه يقول إنه تقديرٌ لحظةَ الحجز**: الأجرةُ تُحسب عند التنفيذ
    estimated_fare_at_booking: Decimal | None
    # **والعملةُ مع المبلغ لا بعده**: مبلغٌ يُرسل بلا عملته تُطبعه الشاشةُ عارياً
    # — وهو بعينه العطبُ الذي شحن في جدول الكوبونات باللوحة قبل يومين
    currency: Currency
    ride_id: uuid.UUID | None
    ride_status: RideStatus | None = None
    # **ينتظر اختيارَها** (§٦٤-ج/٤-١): حجزٌ نسائيٌّ والخدمةُ متوقّفة — لم يُطلب، وبطاقتُه تعرض «أي كبتن» و«إلغاء»
    awaiting_choice: bool = False
    cancelled_at: datetime | None
    created_at: datetime
    # ---- الحجزُ المضمون (§٦٣-ج/٣)
    guaranteed: bool = False
    #: الرسمُ المحفوظ — **وحالُه** (`held` · `paid` · `refunded`) فيرى صاحبُه أين مالُه
    guarantee_fee: Decimal | None = None
    guarantee_state: str | None = None
    #: **اسمُ الكبتن المحجوز** — وعدُ الضمان أن يُعرف قبل الموعد
    captain_name: str | None = None
