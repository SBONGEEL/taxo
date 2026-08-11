"""مخرجاتُ الخريطة الحيّة — **الشكل الوحيد الذي يحمل هويةً مع موقع**.

وهو مفصولٌ عمداً عن `NearbyDriverOut` في `schemas/driver.py` رغم تشابه نصف
الحقول: ذاك مجهَّلٌ بحكم القسم 10 ويخرج إلى تطبيق الراكب، وهذا مكشوفٌ ويخرج
إلى اللوحة وحدها. توحيدُهما في نموذجٍ واحدٍ بحقولٍ اختيارية يجعل تسريبَ الاسم
إلى الراكب سطراً منسياً بدل أن يكون مستحيلاً.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import RideStatus, VehicleCategory


class LiveDriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver_id: uuid.UUID
    name: str
    phone: str
    lat: float
    lng: float
    heading: float | None
    vehicle_category: VehicleCategory
    plate_number: str | None
    on_ride: bool
    ride_id: uuid.UUID | None


class PendingRideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ride_id: uuid.UUID
    lat: float
    lng: float
    status: RideStatus
    created_at: datetime


class LiveMapOut(BaseModel):
    drivers: list[LiveDriverOut]
    pending_rides: list[PendingRideOut]
