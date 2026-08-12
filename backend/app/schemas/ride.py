from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CancelReasonCode,
    CountryCode,
    Currency,
    GenderPreference,
    PaymentMethod,
    RideStatus,
    VehicleCategory,
)

if TYPE_CHECKING:
    from app.models.ride import Ride


class CoordinatesIn(BaseModel):
    """إحداثيات WGS84 كما ترسلها الواجهة من دبوس الخريطة."""

    lat: float = Field(ge=-90, le=90, examples=[31.9539])
    lng: float = Field(ge=-180, le=180, examples=[35.9106])


class StopIn(BaseModel):
    """محطةٌ وسيطة كما ترسلها الواجهة — **بترتيبها في القائمة**."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    address: str | None = Field(default=None, max_length=255)


class RideEstimateRequest(BaseModel):
    pickup: CoordinatesIn
    dropoff: CoordinatesIn
    vehicle_category: VehicleCategory = VehicleCategory.ECONOMY
    # المحطاتُ الوسيطة — والوجهةُ الأخيرة تبقى `dropoff` (SPEC القسم 5.10).
    # السقفُ في طبقة الإدخال **ومعه فحصٌ في الخدمة**: هذا يحرس الشكل وذاك
    # يحرس القاعدة، ومن اكتفى بالأول حرس ما يصل من تطبيقه هو
    stops: list[StopIn] = Field(default_factory=list, max_length=2)


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
    # رمزُ الكوبون كما كتبه الراكب (12-ز) — يُطبَّع ويُتحقق منه في الخدمة، ورمزٌ
    # خاطئ **يرفض الطلبَ كلَّه** ولا يمرّ بلا خصم: من كتب رمزاً ينتظر خصمه، ورحلةٌ
    # تبدأ بسعرٍ كامل بعد رمزٍ سقط صامتاً شكوى دعمٍ لا صفقة
    promo_code: str | None = Field(default=None, max_length=32)


class RideCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
    # سببٌ مصنَّف بجانب النص الحر. `gender_mismatch` ليست وصفاً: هي التي
    # تُسقط رسوم الإلغاء وتُدخل بلاغاً، فلا تُترك لنصٍّ حر يُقرأ باحتمالات
    reason_code: CancelReasonCode | None = None


class RideListItem(BaseModel):
    """صفٌّ في سجل الرحلات — الرحلةُ **ومعها حالُ دفعها**.

    (`FUTURE-FEATURES` بند 19) شارةُ «نزاع» في سجل الكبتن تحتاج أن يعرف الصفُّ
    حالَ دفعته، و`RideOut` وحدها لا تحملها. والبندُ خيّر بين ضمِّ ملخّصٍ إلى
    الصف ونداءٍ ثانٍ لكل صف — و**الضمُّ هو الجواب**: صفحةٌ من عشرين رحلة لا
    يجوز أن تصير عشرين نداءً، وهي نفسُ القاعدة التي بُني عليها `AdminRideRow`.

    **ونوعٌ مستقلٌّ لا حقولٌ تُضاف إلى `RideOut`**: تلك تُبثّ في كل إطار مقبس
    وفي بطاقة العرض، فحسابُ ملخّصِ دفعٍ لكل واحدةٍ منها عملٌ لا يقرؤه أحد.
    """

    ride: "RideOut"
    # هل على هذه الرحلة نزاعٌ مفتوح — وهو ما ترسمه الشارة
    has_open_dispute: bool
    # قنواتُ الدفع عليها: المختلطُ صفّان، فقناةٌ واحدة تخفي نصف الواقعة.
    # **بالتعداد لا بالنص**: `check:enums` في التطبيقات يقابل هذا الاتحاد
    # بأعضاء `PaymentMethod` نفسِها، فقيمةٌ مخترعةٌ تسقط في البناء
    payment_methods: list[PaymentMethod]
    # مجموعُ ما تأكّد — يُقارَن بالأجرة فتُقرأ الرحلةُ غيرَ مسدَّدة
    paid_amount: Decimal


class RideStopOut(BaseModel):
    """محطةٌ وسيطة كما يراها الطرفان — ومعها **ما استحقّ عندها**.

    `waited_minutes` و`waiting_charge` **محسوبان في الخلفية** (SPEC القسم
    5.10/14): الواجهةُ ترسم عدّاداً من `arrived_at` — وذاك حسابُ وقت — أما
    المبلغُ فيصلها محسوباً، فلا تخترع الشاشةُ رقماً مالياً.
    """

    id: uuid.UUID
    sequence: int
    lat: float
    lng: float
    address: str | None
    arrived_at: datetime | None
    resumed_at: datetime | None
    waited_minutes: Decimal
    waiting_charge: Decimal
    # هل تجاوز انتظارُ هذه المحطة سقفَها — وعنده يُفتح للكبتن خيارُ الإنهاء
    over_max_wait: bool


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

    # --- تعدد الوجهات (المرحلة 12-ب) ---
    stops: list[RideStopOut] = Field(default_factory=list)
    current_leg: int = 0
    # رسمُ الانتظار **حتى اللحظة**: يُقرأ أثناء الوقوف كما يُقرأ بعده، فيرى
    # الراكبُ رسمَه الحالي ولا يفاجئه في شاشة الدفع
    waiting_charge: Decimal = Decimal("0.000")
    stop_free_minutes: int = 0
    stop_price_per_min: Decimal = Decimal("0.000")
    stop_max_wait_minutes: int = 0

    created_at: datetime
    accepted_at: datetime | None
    arrived_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None

    @classmethod
    def from_ride(cls, ride: "Ride", now: datetime | None = None) -> "RideOut":
        """التمثيل الوحيد للرحلة — يستعمله الراوتر وبثّ أحداث WebSocket معاً.

        و`now` نقطةُ قياسِ الانتظار: تُمرَّر في الاختبارات وتُترك فارغةً في
        التشغيل. **يحتاج `ride.stops` محمّلةً** — وهي `lazy="selectin"` فتصل
        مع الرحلة بلا نداءٍ ثانٍ.
        """
        from app.services import pricing

        moment = now or datetime.now(UTC)
        stops = [
            RideStopOut(
                id=stop.id,
                sequence=stop.sequence,
                lat=stop.lat,
                lng=stop.lng,
                address=stop.address,
                arrived_at=stop.arrived_at,
                resumed_at=stop.resumed_at,
                waited_minutes=pricing.round_money(
                    pricing.waiting_minutes(stop, moment)
                ),
                waiting_charge=pricing.waiting_charge(
                    [stop],
                    free_minutes=ride.stop_free_minutes_at_ride,
                    price_per_min=ride.stop_price_per_min_at_ride,
                    now=moment,
                ),
                over_max_wait=(
                    ride.stop_max_wait_minutes_at_ride > 0
                    and stop.arrived_at is not None
                    and stop.resumed_at is None
                    and pricing.waiting_minutes(stop, moment)
                    > ride.stop_max_wait_minutes_at_ride
                ),
            )
            for stop in ride.stops
        ]
        return cls(
            stops=stops,
            current_leg=ride.current_leg,
            waiting_charge=pricing.waiting_charge(
                ride.stops,
                free_minutes=ride.stop_free_minutes_at_ride,
                price_per_min=ride.stop_price_per_min_at_ride,
                now=moment,
            ),
            stop_free_minutes=ride.stop_free_minutes_at_ride,
            stop_price_per_min=ride.stop_price_per_min_at_ride,
            stop_max_wait_minutes=ride.stop_max_wait_minutes_at_ride,
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
