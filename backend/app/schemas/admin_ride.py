"""سجل الرحلات في اللوحة (SPEC القسم 13/4).

مخططان لا واحد، والفرق بينهما مقصود:

- **`AdminRideRow`** صفٌّ في قائمةٍ يُقرأ ليُقرَّر «أيَّها أفتح». فيه اسمُ
  الطرفين وحالُ الدفع **مجموعاً في الاستعلام** — لا نداءَ لكل صف، كما في
  `AdminDriverRow`.
- **`AdminRideDetail`** ما يُفتح لرحلةٍ بعينها، ومعه **نقاط المسار**: هي دليلُ
  النزاع الذي وُجد `ride_route_points` لأجله (القسم 5.7)، ولا معنى لحملها في
  قائمةٍ من خمسين رحلة.

**ولا يُعاد استعمال `RideOut`** الذي يقرؤه الراكب والكبتن: ذاك يحمل بطاقةَ
الكبتن كما يراها راكبُه، وهذا يحمل الطرفين بهويتهما وأرقامهما — قرارُ من يرى
ماذا يُتخذ في المخطط لا بشرطٍ داخل دالةٍ واحدة (نفس سبب انفصال
`live_map.drivers_now` عن `drivers.nearby_available`).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.ride import RideStopOut
from app.services.settlement import SettlementState
from app.models.enums import (
    CountryCode,
    Currency,
    GenderPreference,
    PaymentMethod,
    PaymentStatus,
    RatingRaterType,
    RideStatus,
    VehicleCategory,
)


class RidePartyOut(BaseModel):
    """طرفٌ في الرحلة باسمه ورقمه — للوحة وحدها."""

    user_id: uuid.UUID
    name: str
    phone: str


class RideDriverPartyOut(RidePartyOut):
    driver_id: uuid.UUID
    plate_number: str | None = None


class AdminRideRow(BaseModel):
    id: uuid.UUID
    status: RideStatus
    country_code: CountryCode
    vehicle_category: VehicleCategory
    currency: Currency

    rider: RidePartyOut
    driver: RideDriverPartyOut | None

    pickup_address: str | None
    dropoff_address: str | None

    distance_km: Decimal
    actual_distance_km: Decimal | None
    estimated_fare: Decimal
    final_fare: Decimal | None
    cancellation_fee: Decimal | None

    # قنواتُ الدفع على هذه الرحلة — **جمعٌ لا قناة**: الدفعُ المختلط صفّان
    # (محفظة + كاش)، فعمودٌ واحد يخفي نصفَ الواقعة
    payment_methods: list[PaymentMethod]
    # مجموعُ ما تأكّد فعلاً — يُقارَن بالأجرة لتُقرأ الرحلةُ غيرَ مسدَّدة
    paid_amount: Decimal
    has_open_dispute: bool
    # حالُ السداد من المصدر الواحد (`services/settlement.py`) — لا مقارنةٌ في
    # الجدول: كان `Number(fare) > Number(paid_amount)` يقرأ دفعةً منتظِرةً
    # «غيرَ مسدَّدة» ورحلةً ملغاةً «مسدَّدة»
    settlement: SettlementState

    created_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None


class RidePaymentOut(BaseModel):
    id: uuid.UUID
    method: PaymentMethod
    status: PaymentStatus
    amount: Decimal
    dispute_reason: str | None
    resolution: str | None
    created_at: datetime


class RideRatingOut(BaseModel):
    rater_type: RatingRaterType
    stars: int
    comment: str | None
    created_at: datetime


class RidePointOut(BaseModel):
    """نقطةٌ من المسار الفعلي — `created_at` هو زمنُها (لا عمود `recorded_at`)."""

    lat: float
    lng: float
    created_at: datetime


class AdminRideDetail(AdminRideRow):
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float

    duration_min: Decimal
    commission_percent_at_ride: Decimal
    gender_preference: GenderPreference
    cancelled_reason: str | None
    cancel_reason_code: str | None

    accepted_at: datetime | None
    arrived_at: datetime | None
    started_at: datetime | None

    # **ما يفسّر الفرقَ بين المقدَّر والنهائيّ ولا تراه المسافة** (§5.10 و
    # §5.10-ب): عددُ المحطات ورسمُها ورسمُ الانتظار والوقفات. **وبغيرها كان
    # المشرفُ يعيد الحسبةَ بيده** — وهو ما نفاه توثيقُ الشاشة نفسُه، فكان
    # وعداً لا يقع كلما وقف كبتنٌ عند محطة
    stops_count: int
    stop_fee: Decimal
    stops_charge: Decimal
    waiting_charge: Decimal
    pause_charge: Decimal
    # **والمحطاتُ بصفوفها لا بعددها** (عطبٌ مقيسٌ 2026-08-23): كانت اللوحةُ
    # تنشر `stops_count` والمالَ وحدَه، **فيفصل المشرفُ في نزاع انتظارٍ وهو
    # لا يرى عند أيِّ محطةٍ وقف ولا كم** — يرى المجموع. وهي `RideStopOut`
    # نفسُها التي يقرؤها التطبيقان، **بانٍ واحدٌ لا شكلٌ ثانٍ يشبهه**.
    stops: list[RideStopOut]

    payments: list[RidePaymentOut]
    ratings: list[RideRatingOut]
    # دليلُ «أين سار ومتى» (القسم 5.7/13.4) — مسقوفٌ كي لا تصير رحلةٌ طويلة
    # جواباً بآلاف الصفوف، و`route_truncated` يقول إن القصَّ وقع بدل أن يُقرأ
    # مسارٌ ناقصٌ مساراً كاملاً
    route: list[RidePointOut]
    route_truncated: bool
