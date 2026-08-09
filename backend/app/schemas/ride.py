from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CountryCode,
    Currency,
    RideStatus,
    VehicleCategory,
)


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


class RideCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


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
    duration_min: Decimal
    estimated_fare: Decimal
    final_fare: Decimal | None
    cancellation_fee: Decimal | None
    commission_percent_at_ride: Decimal

    cancelled_reason: str | None
    driver: RideDriverOut | None = None

    created_at: datetime
    accepted_at: datetime | None
    arrived_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
