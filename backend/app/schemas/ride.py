from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CancelReasonCode,
    CountryCode,
    Currency,
    GenderPreference,
    RideStatus,
    VehicleCategory,
)

if TYPE_CHECKING:
    from app.models.ride import Ride


class CoordinatesIn(BaseModel):
    """إحداثيات WGS84 كما ترسلها الواجهة من دبوس الخريطة."""

    lat: float = Field(ge=-90, le=90, examples=[31.9539])
    lng: float = Field(ge=-180, le=180, examples=[35.9106])


class RideEstimateRequest(BaseModel):
    pickup: CoordinatesIn
    dropoff: CoordinatesIn
    vehicle_category: VehicleCategory = VehicleCategory.ECONOMY


class RideEstimateOut(BaseModel):
    """السعر المقدّر — محسوب في الخلفية بالكامل (SPEC القسم 5)."""

    country_code: CountryCode
    vehicle_category: VehicleCategory
    currency: Currency
    distance_km: Decimal
    duration_min: Decimal
    estimated_fare: Decimal
    minimum_fare_applied: bool


class RideCreateRequest(RideEstimateRequest):
    # عنوانان اختياريان: الاعتماد الأساسي على الدبوس والـ Geocoding مكمّل
    pickup_address: str | None = Field(default=None, max_length=255)
    dropoff_address: str | None = Field(default=None, max_length=255)
    # `null` = «خذ افتراضي ملفي» لا `any`: التطبيق لا يرسل الحقل حين لا تختار
    # الراكبة شيئاً، فيسري ما ضبطته مرةً في حسابها (المرحلة 10-ج)
    gender_preference: GenderPreference | None = None


class RideCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
    # سببٌ مصنَّف بجانب النص الحر. `gender_mismatch` ليست وصفاً: هي التي
    # تُسقط رسوم الإلغاء وتُدخل بلاغاً، فلا تُترك لنصٍّ حر يُقرأ باحتمالات
    reason_code: CancelReasonCode | None = None


class RideVehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    make: str
    model: str
    color: str
    plate_number: str
    category: VehicleCategory


class RideDriverOut(BaseModel):
    """بطاقة الكبتن التي يراها الراكب بعد القبول (SPEC القسم 5.4)."""

    id: uuid.UUID
    name: str
    rating_avg: Decimal
    vehicle: RideVehicleOut | None = None

    @classmethod
    def from_ride(cls, ride: "Ride") -> "RideDriverOut | None":
        """تتطلب تحميل `driver.user` و`driver.vehicles` مسبقاً (selectinload)."""
        if ride.driver is None:
            return None
        vehicles = ride.driver.vehicles
        return cls(
            id=ride.driver.id,
            name=ride.driver.user.name,
            rating_avg=ride.driver.rating_avg,
            vehicle=RideVehicleOut.model_validate(vehicles[0]) if vehicles else None,
        )


class RideOut(BaseModel):
    id: uuid.UUID
    rider_id: uuid.UUID
    status: RideStatus
    country_code: CountryCode
    vehicle_category: VehicleCategory
    currency: Currency

    pickup: CoordinatesIn
    pickup_address: str | None
    dropoff: CoordinatesIn
    dropoff_address: str | None

    distance_km: Decimal
    # المسافة المسجَّلة فعلاً من نقاط المسار — فارغة قبل الإنهاء وحين صمت
    # تطبيق الكبتن (SPEC القسم 5.7)
    actual_distance_km: Decimal | None
    duration_min: Decimal
    estimated_fare: Decimal
    final_fare: Decimal | None
    cancellation_fee: Decimal | None
    commission_percent_at_ride: Decimal

    cancelled_reason: str | None
    # ما طُلب في هذه الرحلة من جنس الكبتن. يقرؤه تطبيق الكبتن ليرسم شارة
    # «طلب نسائي» على بطاقة العرض، وتطبيقُ الراكبة لتعرض ما اختارته.
    # **وهو تفضيلُ الطلب لا جنسُ صاحبه**: جنسُ أيّ طرفٍ لا يغادر الخلفية
    gender_preference: GenderPreference
    driver: RideDriverOut | None = None

    created_at: datetime
    accepted_at: datetime | None
    arrived_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None

    @classmethod
    def from_ride(cls, ride: "Ride") -> "RideOut":
        """التمثيل الوحيد للرحلة — يستعمله الراوتر وبثّ أحداث WebSocket معاً."""
        return cls(
            id=ride.id,
            rider_id=ride.rider_id,
            status=ride.status,
            country_code=ride.country_code,
            vehicle_category=ride.vehicle_category,
            currency=ride.currency,
            pickup=CoordinatesIn(lat=ride.pickup_lat, lng=ride.pickup_lng),
            pickup_address=ride.pickup_address,
            dropoff=CoordinatesIn(lat=ride.dropoff_lat, lng=ride.dropoff_lng),
            dropoff_address=ride.dropoff_address,
            distance_km=ride.distance_km,
            actual_distance_km=ride.actual_distance_km,
            duration_min=ride.duration_min,
            estimated_fare=ride.estimated_fare,
            final_fare=ride.final_fare,
            cancellation_fee=ride.cancellation_fee,
            commission_percent_at_ride=ride.commission_percent_at_ride,
            cancelled_reason=ride.cancelled_reason,
            gender_preference=ride.gender_preference,
            driver=RideDriverOut.from_ride(ride),
            created_at=ride.created_at,
            accepted_at=ride.accepted_at,
            arrived_at=ride.arrived_at,
            started_at=ride.started_at,
            completed_at=ride.completed_at,
            cancelled_at=ride.cancelled_at,
        )
