"""مخرجاتُ الخريطة الحيّة — **الشكل الوحيد الذي يحمل هويةً مع موقع**.

وهو مفصولٌ عمداً عن `NearbyDriverOut` في `schemas/driver.py` رغم تشابه نصف
الحقول: ذاك مجهَّلٌ بحكم القسم 10 ويخرج إلى تطبيق الراكب، وهذا مكشوفٌ ويخرج
إلى اللوحة وحدها. توحيدُهما في نموذجٍ واحدٍ بحقولٍ اختيارية يجعل تسريبَ الاسم
إلى الراكب سطراً منسياً بدل أن يكون مستحيلاً.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.enums import RideStatus, VehicleCategory
from app.schemas.admin_ride import RidePointOut


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
    # **حالةٌ محسوبةٌ في الخلفية لا في اللوحة** — قاعدةُ §14 مطبَّقةً على حكمٍ
    # لا على مبلغ: لوحةٌ تحسب «شاحب» بنفسها تفترق عن الخلفية أولَ ما يتغيّر
    # `PRESENCE_TTL_SECONDS`، ولا شيءَ يفشل
    state: Literal["available", "on_ride", "stale"]
    seconds_since_update: int | None


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


class DriverLivePositionOut(BaseModel):
    """أين هو الآن — **وغيابُ الكائن كلِّه صمتٌ لا موضعٌ عند الصفر**.

    **ولا `state` ثلاثيّةً هنا**: هذا لا يُقرأ إلا وصاحبُه في رحلة، فتجيب
    الثلاثيّةُ «في رحلة» دائماً **وتبتلع السؤالَ الوحيد المطروح**: أطازجٌ هذا
    الدبّوس؟ فيخرج `stale` عارياً ومعه عمرُه بالثواني.
    """

    model_config = ConfigDict(from_attributes=True)

    lat: float
    lng: float
    # ثوانٍ منذ آخر بثّ — و`null` ختمٌ غيرُ موجود، **لا «الآن»**
    seconds_since_update: int | None
    # **محسوبةٌ في الخلفية** من `STALE_AFTER_SECONDS`: لوحةٌ تقارن بعتبةٍ من
    # عندها تفترق أوّلَ ما يتغيّر عمرُ الحضور، ولا شيءَ يفشل
    stale: bool


class DriverLiveRideOut(BaseModel):
    """رحلةُ الكبتن الجارية ومسارُها وموضعُه — **البند ٦، §39٫٦**.

    **وأضيقُ من `AdminRideDetail` بقصد**: هذا يخرج من البابِ الوحيد الثاني
    الذي يقرن هويةً بموقع، **فلا يحمل إلا ما تحتاجه خريطةٌ داخل ملفّ** — ولا
    اسمَ راكبٍ ولا رقمَه ولا مالاً. **ومن أرادها كاملةً فبابُها سجلُّ
    الرحلات** (`GET /admin/rides/{ride_id}`، لكلِّ `staff`)، ولا يُوسَّع هذا
    ليصير طريقاً ثانياً إليه.
    """

    ride_id: uuid.UUID
    status: RideStatus
    pickup_lat: float
    pickup_lng: float
    pickup_address: str | None
    dropoff_lat: float
    dropoff_lng: float
    dropoff_address: str | None
    accepted_at: datetime | None
    started_at: datetime | None
    # المسارُ الفعليُّ من `ride_route_points` — **دليلُ النزاع نفسُه** (§5.7)،
    # ولا بنيةَ ثانيةً تُبنى له
    route: list[RidePointOut]
    # **والقصُّ يُقال**: مسارٌ ناقصٌ يُقرأ كاملاً دليلٌ يكذب
    route_truncated: bool
    position: DriverLivePositionOut | None
