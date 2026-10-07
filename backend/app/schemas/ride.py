from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.settlement import SettlementState
from app.schemas.driver import MapSkinOut
from app.models.enums import (
    CancelReasonCode,
    CountryCode,
    Currency,
    FareLineKind,
    GenderPreference,
    PaymentMethod,
    RidePayer,
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
    # **تقديرُ طرد** (§٦٣-ج/٤) — يضيف رسمَه ويُعيد شروطَه. **ولا يُسمّى `parcel`**: طلبُ الرحلة يرث هذا المخطّط وله `parcel` بتفاصيله
    is_parcel: bool = False
    # **تقديرُ ساعات** (§٦٣-ج/٥) — `null` لرحلةٍ عاديّة
    hourly_hours: int | None = Field(default=None, ge=1, le=24)


class RideEstimateOut(BaseModel):
    """السعر المقدّر — محسوب في الخلفية بالكامل (SPEC القسم 5)."""

    country_code: CountryCode
    vehicle_category: VehicleCategory
    currency: Currency
    distance_km: Decimal
    duration_min: Decimal
    estimated_fare: Decimal
    minimum_fare_applied: bool
    # **سعرُ المشاركة يُحسب هنا لا في التطبيق** (القسم 14): نسبةٌ مضروبةٌ في
    # أجرةٍ حسابُ مال، وواجهةٌ تضربها تصير طرفاً في تحديد ما يُدفع. و`null`
    # تعني «لا مشاركةَ في هذا السوق» — فلا يرسم التطبيقُ خياراً بلا سعر،
    # ولا يخترع صفراً يقرأ «مجاناً»
    share_discount: Decimal | None = None
    share_fare: Decimal | None = None
    # **شروطُ الوقوف تُقال قبل الطلب** (§5.10: «والشاشةُ تقول سعرَه قبل الطلب،
    # فيكون معلوماً ولو لم يكن مقدَّراً»). **ورسمُ الانتظار خارج التقدير عمداً**
    # — لا يُعرف قبل أن يقع — فما يُنشر هنا **شروطُه** لا مبلغُه.
    #
    # ومحلُّها التقديرُ لا `/config`: الأربعةُ لكلِّ (دولة × فئة)، والتقديرُ هو
    # الموضعُ الوحيد الذي عُرفت فيه الفئةُ المختارة. والتفصيلُ في
    # `services/pricing.FareEstimate`.
    stop_fee: Decimal
    stop_free_minutes: int
    stop_price_per_min: Decimal
    stop_max_wait_minutes: int
    # **رسمُ المطار للكبتن** (§٦٣-ج/٢) — داخل `estimated_fare` ويُنشر وحدَه ليُقال سطراً. و`null` بلا رسم
    airport_fee: Decimal | None = None
    # **رسمُ الطرد للكبتن وشروطُه** (§٦٣-ج/٤) — `null` في غير تقدير طرد. **والشروطُ من الخلفية** فلا تكتبها واجهتان بلفظين
    parcel_fee: Decimal | None = None
    parcel_terms: list[str] | None = None
    # **بالساعة** (§٦٣-ج/٥) — سعرُ الساعة وكيلومتراتُها وأقصى الساعات، لتقول الشاشةُ «8.000 للساعة شاملةً 15 كم». و`null` حيث لا خدمة
    hourly_rate: Decimal | None = None
    hourly_km_per_hour: int | None = None
    hourly_max_hours: int | None = None


class RideForOtherIn(BaseModel):
    """الراكبُ الفعليُّ ومن يدفع (§٦٣-ج/١) — **يُحفظان لهذه الرحلة وحدَها ويُمحيان بعد ٣٠ يوماً**.

    والرقمُ يُطبَّع في الخدمة إلى E.164 بقواعد السوقين (+962 · +218)، ورقمٌ لا يُطبَّع **يرفض الطلب** — رقمٌ لا يُتّصل به
    يُسقط سببَ حفظه.
    """

    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=6, max_length=20)
    payer: RidePayer = RidePayer.REQUESTER


class ParcelIn(BaseModel):
    """الطرد (§٦٣-ج/٤) — المستلمُ ومن يدفع، **وإقرارُ المرسل بالشروط** (طلبٌ بلا إقرارٍ يُرفض)."""

    recipient_name: str = Field(min_length=2, max_length=80)
    recipient_phone: str = Field(min_length=6, max_length=20)
    recipient_address: str = Field(min_length=3, max_length=255)
    payer: RidePayer = RidePayer.REQUESTER
    accepted_terms: bool = False


class HourlyIn(BaseModel):
    """بالساعة (§٦٣-ج/٥) — الساعاتُ ومن أين يُدفع محجوزُها عند البدء."""

    hours: int = Field(ge=1, le=24)
    prepay: Literal["wallet", "cash"] = "wallet"


class HourlyPrepayIn(BaseModel):
    prepay: Literal["wallet", "cash"]


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
    # **المشاركة (12-ي)**: الخصمُ يُطبَّق ولو لم يوجد شريك — الشركةُ تتحمّله
    # (قرارُ المالك الثالث)، فالوعدُ يُحترم ولا يُفاجأ صاحبُه برفع سعر
    share: bool = False
    # **خيارٌ صريحٌ منفصل، وهو شرطُ المشاركة على طلبٍ مجنَّس** (قرارُ المالك
    # الرابع): «كانت ستوافق لو سُئلت» ليست موافقة. ولا يُدمج مع `share` في حقلٍ
    # واحد لأن ما يقوله كلٌّ منهما مختلف — الأولُ «أقبل المشاركة»، والثاني
    # «أقبلها وأنا أعلم أن شريكي قد لا يوافق تفضيلي في جنس الكبتن»
    share_gender_confirmed: bool = False
    # **رحلةٌ لشخصٍ آخر** (§٦٣-ج/١) — `null` لرحلةٍ يركبها صاحبُها
    for_other: RideForOtherIn | None = None
    # **الطرد** (§٦٣-ج/٤) — `null` لرحلةٍ عاديّة
    parcel: ParcelIn | None = None
    # **بالساعة** (§٦٣-ج/٥) — والوجهةُ اختياريّة: ترسل الواجهةُ نقطةَ الانطلاق نفسَها وجهةً إن لم تُختر
    hourly: HourlyIn | None = None
    # **«انتظري، نوسّع البحث»** (§٦٤-ج/٤-٣) — للطلب النسائيّ وحدَه، ويُردّ على غيره
    widen_search: bool = False


class RideCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
    # سببٌ مصنَّف بجانب النص الحر. `gender_mismatch` ليست وصفاً: هي التي
    # تُسقط رسوم الإلغاء وتُدخل بلاغاً، فلا تُترك لنصٍّ حر يُقرأ باحتمالات
    reason_code: CancelReasonCode | None = None


class RiderSummaryOut(BaseModel):
    """بطاقةُ «حسابي» (R15، §٦١-ط/٢): رحلاتُه المكتملة وتقييمُه — **و`rating_avg` فارغٌ بلا تقييم** فلا يُرسم صفر."""

    completed_rides: int
    rating_avg: Decimal | None
    ratings_count: int


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
    # مجموعُ ما تأكّد — رقمٌ يُعرض، **لا حكمٌ يُستنتج منه**
    paid_amount: Decimal
    # حالُ السداد محسوبةً في الخلفية (`services/settlement.py`): كانت كلُّ
    # شاشةٍ تستنتجها بمقارنةٍ خاصةٍ بها فأخطأت ثلاثٌ من أربع
    settlement: SettlementState


def stops_of(ride: "Ride", moment: datetime) -> list["RideStopOut"]:
    """محطاتُ الرحلة كما تُنشر — **بانٍ واحدٌ يناديه بابان**.

    يناديه `RideOut.from_ride` لشاشتَي الراكب والكبتن، **ويناديه بابُ اللوحة**
    (`GET /admin/rides/{id}`). وقبلَه كانت اللوحةُ تُنشر بلا محطاتٍ البتّة —
    فالمشرفُ يرى مجموعَ رسم الوقوف ولا يرى **عند أيِّ محطةٍ ولا كم** (قِيس
    2026-08-23). **وحلُّه بانٍ ثانٍ يشبه الأول هو الشكلُ الثامن بعينه**: بابان
    ينشران الشيءَ نفسَه ويفترقان أوّلَ تعديل — فالاشتقاقُ من موضعٍ واحد.

    و`moment` نقطةُ قياس الانتظار: تُمرَّر في الاختبارات وتُترك للحظة في
    التشغيل. **ويحتاج `ride.stops` محمّلةً** — وهي `lazy="selectin"`.
    """
    from app.services import pricing

    return [
        RideStopOut(
            id=stop.id,
            sequence=stop.sequence,
            lat=stop.lat,
            lng=stop.lng,
            address=stop.address,
            arrived_at=stop.arrived_at,
            resumed_at=stop.resumed_at,
            waited_minutes=pricing.round_money(pricing.waiting_minutes(stop, moment)),
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


class FareLineOut(BaseModel):
    """سطرٌ من تفصيل الأجرة — **من الخلفية حرفاً** (§١٤): الشاشةُ ترسم `amount` ولا تضرب `quantity` في شيء."""

    kind: FareLineKind
    amount: Decimal
    # كيلومتراتٌ أو دقائقُ أو عددُ محطات — **لتسمية السطر وحدَها**
    quantity: Decimal | None = None


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
    #: **مركبتُه الحقيقيةُ أياً كانت ندرتُها** (2026-08-22): قبل القبول تُخفى
    #: النادرةُ لأن ما يُرى ويندر يصير معرّفاً ينقض تجهيل §10، **وبعده** يعرف
    #: الراكبُ اسمَه ولوحتَه أصلاً فلا شيءَ يُخفى. و`None` لمن لا مركبةَ نشطةً
    #: له — ولا بديلَ يُدسّ هنا: بعد القبول لا فئةَ تُميَّز بغيابٍ
    skin: MapSkinOut | None = None

    @classmethod
    def from_ride(cls, ride: "Ride") -> "RideDriverOut | None":
        """تتطلب تحميل `driver.user` و`driver.vehicles` مسبقاً (selectinload).

        **و`driver.active_skin` تصل بالضمّ** (`lazy="joined"` على النموذج)،
        فهذا البانِي متزامنٌ ولا يستطيع استعلاماً — والضمُّ لا ذهابَ ثانٍ له.
        """
        if ride.driver is None:
            return None
        vehicles = ride.driver.vehicles
        skin = ride.driver.active_skin
        return cls(
            id=ride.driver.id,
            name=ride.driver.user.name,
            rating_avg=ride.driver.rating_avg,
            vehicle=RideVehicleOut.model_validate(vehicles[0]) if vehicles else None,
            skin=MapSkinOut.for_skin(skin),
        )


class RidePauseOut(BaseModel):
    """وقفةٌ مفتوحةٌ كما يراها الطرفان — **حقائقُ لا جملةُ حالة**.

    **والدقائقُ والمبلغُ معاً** (§14): الوقتُ يرسمه التطبيقُ محلياً بين
    الإطارات، والمبلغُ يأتي من هنا — فالوقتُ حسابُ وقتٍ والمالُ حسابُ مال.
    ويُرسل الوقتُ كذلك ليكون للتطبيق **نقطةُ بدءٍ مقيسة** لا تخمين.
    """

    id: uuid.UUID
    # `pause` وقفةٌ في منتصف الرحلة، و`arrival` انتظارٌ عند الوصول — والنصُّ
    # يختلف بينهما في الشاشتين، فالنوعُ يُنشر
    kind: str
    started_at: datetime
    waited_minutes: Decimal
    charge: Decimal
    free_minutes: int
    # تجاوزَ السقف — **يُنبَّه عنده الطرفان ولا تُنهى الرحلة** (الفرع أ)
    over_max: bool = False


#: أطوارُ ما بعد القبول وقبل الانتهاء — **فيها وحدَها يُنشر اسمُ الراكب الفعليّ ورقمُه** (§٦٣-ج/١)
PASSENGER_VISIBLE = frozenset(
    {RideStatus.ACCEPTED, RideStatus.ARRIVED, RideStatus.IN_PROGRESS, RideStatus.AT_STOP}
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
    # **تفصيلُ الأجرة مجمَّداً** (R10، §٦٢-ج/٢٥): قبل الإنهاء أسطرُ `estimated_fare`، وبعده أسطرُ `final_fare` — **ومجموعُ كلٍّ منهما
    # مبلغُه حرفاً**. وفارغٌ لرحلةٍ أقدمَ من التجميد: لا تفصيلَ يُرسم بدل تفصيلٍ مخترَع
    fare_lines: list[FareLineOut] = Field(default_factory=list)
    cancellation_fee: Decimal | None
    # **مبلغٌ مستوفى لكبتنٍ آخر يُسلَّم نقداً مع الأجرة** (§6-أ)، مجمَّدٌ لحظةَ
    # الطلب. يقرؤه تطبيقُ الكبتن ليرسم بطاقةً **قبل** القبول: من قَبِل وهو
    # يعرف لا يشتكي، وحجّتُه حجّةُ شارتي «مشتركة» و«طلب نسائي» بعينها.
    # و`null`/صفرٌ يعني «لا شيءَ محمول» فلا تُرسم بطاقة
    carried_cancellation_fee: Decimal | None
    commission_percent_at_ride: Decimal

    cancelled_reason: str | None
    # ما طُلب في هذه الرحلة من جنس الكبتن. يقرؤه تطبيق الكبتن ليرسم شارة
    # «طلب نسائي» على بطاقة العرض، وتطبيقُ الراكبة لتعرض ما اختارته.
    # **وهو تفضيلُ الطلب لا جنسُ صاحبه**: جنسُ أيّ طرفٍ لا يغادر الخلفية
    gender_preference: GenderPreference
    # موعدُ الحجز إن وُلدت منه (المرحلة 12-ط) — و`null` لرحلةٍ فورية. يقرؤه
    # تطبيقُ الكبتن ليرسم «موعدها ٧:٠٠» على بطاقة العرض: من يعرف أن الرحلةَ
    # محجوزةٌ لا يتذمّر من راكبٍ يخرج في موعده لا في لحظة وصوله
    scheduled_for: datetime | None = None
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
    # **رسمُ المحطات مجمَّدٌ ومجموعٌ في الخلفية** (القسم 14): `stop_fee` وحدةٌ
    # و`stops_charge` حاصلُها في عددها. **والمجموعُ يُنشر لأن الشاشة لا تضرب**
    # — واجهةٌ تحسب `رسم × عدد` تصير طرفاً في تحديد ما يُدفع، وهو بعينه ما
    # منعه §14 حين منع تمرير المال بـ`Number`. والوحدةُ تُنشر معه ليصحّ
    # **اسمُ** السطر لا حسابُه («محطتان × 0.500») بلا أن يُشتقّ منه مبلغ
    stop_fee: Decimal = Decimal("0.000")
    stops_charge: Decimal = Decimal("0.000")

    # --- الوقفةُ غير المخطَّطة وانتظارُ الوصول (§5.10-ب) ---
    # **الوقفةُ المفتوحةُ وحدَها تُنشر** لا قائمتُها كلُّها: ما يرسمه التطبيقان
    # عدّادٌ يمشي **الآن**، وقائمةُ وقفاتٍ مضت لا يقرؤها أحدٌ في شاشة رحلةٍ جارية.
    # والمجموعُ يُقرأ من `pause_charge`
    open_pause: RidePauseOut | None = None
    # **رسمُ الوقفات حتى اللحظة** — يُقرأ أثناءها كما يُقرأ بعدها، فلا مفاجأةَ
    # في شاشة الدفع: **مبلغٌ لم يُعلَن حين نشأ يُقرأ خطأً في الحساب**
    pause_charge: Decimal = Decimal("0.000")
    pause_price_per_min: Decimal = Decimal("0.000")
    pause_max_minutes: int = 0
    # **عدّادُ الأجرة** (§٦٢-ج/٤٢، C07 «حتى الآن»): المقدَّرةُ ورسمُ الانتظار والوقفات
    # **حتى اللحظة** — وهي `_final_fare` بعينها ما لم ينحرف الطريق. **والسعرُ هنا
    # مقدَّمٌ لا عدّادُ مسافة** (القسم 5.7): فلا يكبر بالكيلومتر، ويكبر بما يتراكم
    # وحدَه — وانحرافُ الطريق يُحكم عند الإنهاء لا قبله
    current_fare: Decimal = Decimal("0.000")
    # **أيُطلب رمزُ الرحلة قبل البدء؟** (§٦٢-ج/٥، CW4) — **السؤالُ وحدَه لا الرمز**: هذا التمثيلُ يصل الطرفين وبثَّ المقبس، والرمزُ ما
    # تُدخله الكبتنة؛ فيُقرأ للراكبة من بابها (`GET /rides/{id}/start-code`)
    start_code_required: bool = False

    # ------------------------------------ رحلةٌ لشخصٍ آخر (§٦٣-ج/١)
    # **`for_other` و`payer` يُنشران دائماً**: الكبتنُ يقرأ على بطاقة العرض أنه سيقبض من غير صاحب الطلب أو لا يقبض شيئاً —
    # **من قَبِل وهو يعرف لا يشتكي** (حجّةُ «موعدها» و«طلب نسائي»). **والاسمُ والرقمُ في أطوار القبول وحدَها**
    # (`PASSENGER_VISIBLE`): العرضُ يمرّ على كباتن يرفضونه، والرقمُ أُعطي ليتصل به من يأتي — لا ليمرّ على كلِّ من عُرض عليه.
    # **وبعد الانتهاء يُطويان** فلا يبقى رقمُ غريبٍ في سجلِّ أحد
    for_other: bool = False
    payer: RidePayer = RidePayer.REQUESTER
    passenger_name: str | None = None
    passenger_phone: str | None = None
    # **رحلةٌ تمسّ مطاراً** (§٦٣-ج/٢) — شارةُ «مطار» على بطاقة العرض، والرسمُ سطرُه في `fare_lines`
    airport: bool = False
    # **الطرد** (§٦٣-ج/٤) — النوعُ دائماً، **والمستلمُ في أطوار القبول وحدَها** كالراكب الفعليّ
    ride_type: str = "standard"
    recipient_name: str | None = None
    recipient_phone: str | None = None
    recipient_address: str | None = None
    # **بالساعة** (§٦٣-ج/٥) — الساعاتُ والكيلومتراتُ المشمولة (محسوبةٌ هنا، فلا تضرب الشاشة) ومن أين يُدفع المحجوز
    hourly_hours: int | None = None
    hourly_included_km: int | None = None
    hourly_prepay_method: str | None = None
    # **رحلةٌ من المشوار الثابت** (§٦٣-ج/٦) — مدفوعةٌ مقدّماً، فلا شاشةَ دفعٍ ولا «استلم» عند الكبتن
    commute: bool = False
    # **بحثٌ موسَّعٌ اختارته** (§٦٤-ج/٤-٣) — تقول شاشتُها «نوسّع البحث» لا «نبحث»
    search_widened: bool = False

    # ------------------------------------ مشاركةُ الرحلة (12-ي)
    # **النسبةُ المجمَّدة لا ما في الإعدادات الآن**: بها يرسم التطبيقان شارةَ
    # «رحلة مشتركة» ويعرض الراكبُ توفيرَه. وصفرٌ يعني رحلةً غيرَ مشتركة.
    #
    # **ولا يُنشر مبلغُ الخصم هنا**: يُحسب على `final_fare` عند الإنهاء، وقبله
    # لا وجودَ له — ورقمٌ يُعرض قبل أن يوجد وعدٌ لا يملكه أحد. وما يقرؤه أيُّ
    # إنسانٍ بعد الإنهاء صفُّ الدفعة بقناة `share` في الإيصال
    share_discount_percent: Decimal = Decimal("0.00")
    # هل معك راكبٌ آخر فعلاً؟ — و`None` تعني رحلةً منفردة
    share_group_id: uuid.UUID | None = None
    share_seat: int = 1

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
        # **`pricing` يبقى هنا** رغم انتقال بناء المحطات إلى `stops_of`:
        # `pause_charge` أدناه يستعمله. وحذفُه مع النقل كسر `from_ride` كلَّها
        # بـ`NameError` — ظهر ٥٠٠ على **إلغاء رحلة** لأن البثَّ يمرّ من هنا.
        from app.services import pricing

        moment = now or datetime.now(UTC)
        stops = stops_of(ride, moment)
        # **الوقفةُ تُحسب من الصفوف المحمَّلة لا باستعلام**: `from_ride` يُنادى
        # في بثِّ المقبس حيث لا جلسة
        from app.services import pauses as pauses_service

        current = next((row for row in ride.pauses if row.ended_at is None), None)
        open_pause = (
            RidePauseOut(
                id=current.id,
                kind=current.kind,
                started_at=current.started_at,
                waited_minutes=pauses_service.minutes_of(current, moment),
                charge=pauses_service.charge_of(current, moment),
                free_minutes=current.free_minutes_at_pause,
                over_max=(
                    current.max_minutes_at_pause > 0
                    and pauses_service.minutes_of(current, moment)
                    > current.max_minutes_at_pause
                ),
            )
            if current is not None
            else None
        )
        pause_charge = pricing.round_money(
            sum(
                (pauses_service.charge_of(row, moment) for row in ride.pauses),
                Decimal("0.000"),
            )
        )
        waiting_charge = pricing.waiting_charge(
            ride.stops,
            free_minutes=ride.stop_free_minutes_at_ride,
            price_per_min=ride.stop_price_per_min_at_ride,
            now=moment,
        )

        return cls(
            stops=stops,
            current_leg=ride.current_leg,
            share_discount_percent=ride.share_discount_percent_at_ride,
            share_group_id=ride.share_group_id,
            share_seat=ride.share_seat,
            waiting_charge=waiting_charge,
            stop_free_minutes=ride.stop_free_minutes_at_ride,
            stop_price_per_min=ride.stop_price_per_min_at_ride,
            stop_max_wait_minutes=ride.stop_max_wait_minutes_at_ride,
            stop_fee=ride.stop_fee_at_ride,
            stops_charge=pricing.round_money(
                ride.stop_fee_at_ride * ride.stops_count
            ),
            open_pause=open_pause,
            pause_charge=pause_charge,
            pause_price_per_min=ride.pause_price_per_min_at_ride,
            pause_max_minutes=ride.pause_max_minutes_at_ride,
            # **بالقيم نفسِها التي تُنشر بجانبه** — لحظةٌ واحدةٌ للثلاثة، فلا يفترق
            # العدّادُ عن السطرين اللذين يشرحانه
            current_fare=pricing.round_money(
                ride.estimated_fare + waiting_charge + pause_charge
            ),
            start_code_required=ride.start_code is not None,
            for_other=ride.for_other,
            airport=ride.facility_id is not None,
            ride_type=ride.ride_type,
            hourly_hours=ride.hourly_hours,
            hourly_included_km=(
                ride.hourly_hours * (ride.hourly_km_per_hour_at_ride or 0) if ride.hourly_hours else None
            ),
            hourly_prepay_method=ride.hourly_prepay_method,
            commute=ride.commute_id is not None,
            search_widened=ride.search_widened,
            recipient_name=ride.recipient_name if ride.status in PASSENGER_VISIBLE else None,
            recipient_phone=ride.recipient_phone if ride.status in PASSENGER_VISIBLE else None,
            recipient_address=ride.recipient_address if ride.status in PASSENGER_VISIBLE else None,
            payer=RidePayer(ride.payer),
            passenger_name=(
                ride.passenger_name if ride.status in PASSENGER_VISIBLE else None
            ),
            passenger_phone=(
                ride.passenger_phone if ride.status in PASSENGER_VISIBLE else None
            ),
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
            fare_lines=[FareLineOut.model_validate(line) for line in (ride.fare_lines or [])],
            cancellation_fee=ride.cancellation_fee,
            carried_cancellation_fee=ride.carried_cancellation_fee,
            commission_percent_at_ride=ride.commission_percent_at_ride,
            scheduled_for=ride.scheduled_for,
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


class RouteStepOut(BaseModel):
    """تعليمةُ ملاحةٍ واحدة — نصُّها بالعربية، وشكلُها الذي يُقاس عليه الانحراف.

    **والشكلُ هنا هو هندسةُ الخطوة لا `overview`**: قِيس على مسارٍ حقيقيٍّ في
    عمّان أن `overview=simplified` يعطي ٢١ رأساً لثمانية كيلومترات (خطؤه يصل
    **٨٣١ م** في أسوأ مسارٍ مخزَّنٍ عندنا)، وهندسةَ الخطوات تعطي ٢٧٧ رأساً
    بخطأٍ أقصاه **٤٫٨ م**. **فقياسُ الانحراف على `overview` يُخفي الشريطَ عن
    كبتنٍ يسير على الطريق تماماً** — وهو عكسُ ما بُني له.
    """

    text: str
    distance_m: int
    shape: list[list[float]]
    # **نوعُ المناورة واتجاهُها بكلمة Mapbox** (§٦٢-ج/٤٢) — منهما يُرسم السهم.
    # و`null` لخطوةٍ خُزِّنت قبلهما أو بلا مناورةٍ معروفة: نصٌّ بلا سهم
    maneuver: str | None = None
    modifier: str | None = None


class ApproachOut(BaseModel):
    """مسارُ الكبتن إلى نقطة الالتقاء — للعرض (C05) أو الاقتراب (C06 · R08)، §٦٢-ج/١٠.

    **`[[lng, lat]…]` كـ`RouteLineOut`**، ومعه مدّتُه ومسافتُه كما قالهما المزوّد — **والوقتُ المتبقّي يُحسب في الجهاز** من
    الخطّ وموضع الكبتن لا بسؤالٍ ثانٍ (الاستطلاعُ يضاعف الفاتورة). **والخطواتُ للكبتن وحدَه** (الراكبُ لا يقودها).
    """

    points: list[list[float]]
    steps: list[RouteStepOut] = []
    duration_min: float
    distance_km: float


class EtaCategoryOut(BaseModel):
    vehicle_category: VehicleCategory
    #: دقائقُ أقربِ كبتنٍ متاحٍ من هذه الفئة — **دقيقةٌ واحدةٌ حدٌّ أدنى**
    minutes: int


class EtaOut(BaseModel):
    """«تصل خلال 3 د» قبل الطلب (R05 · R06، §٦٢-ج/١٠) — **`enabled: false` حيث المفتاحُ مطفأ** فلا يُرسم شيء،
    **وفئةٌ بلا كبتنٍ متاحٍ غائبةٌ** لا «بعيدة»."""

    enabled: bool
    categories: list[EtaCategoryOut] = []


class RouteLineOut(BaseModel):
    """شكلُ مسار الرحلة كما قاله Mapbox — `[[lng, lat], …]` (البند ٨).

    **وقائمةٌ فارغةٌ جوابٌ صحيحٌ لا خطأ**: عقدُ Mapbox قد يكون مطفأً أو النداءُ
    سقط، والتطبيقُ حينها يرسم الدبوسين وحدهما. و**الترتيبُ (طول، عرض)** كما
    يكتبه Mapbox وGeoJSON — عكسُ المألوف، فاسمُ الحقل وحدَه لا يكفي والتوثيقُ
    هنا هو ما يمنع خطاً مرسوماً في البحر.
    """

    points: list[list[float]]
    # **كم إعادةَ توجيهٍ بقيت** (البند ١٧-٤) — يقرؤها التطبيقُ فيكفّ عن الطلب.
    # و`None` على القراءة العادية: السؤالُ لا معنى له إلا بعد إعادةِ توجيه
    reroutes_left: int | None = None
    # **خطواتُ الملاحة** (البند ٧) — نصُّ التعليمة وهندستُها ومسافتُها.
    # **وفارغةٌ حالٌ صحيحةٌ لا خطأ**: المفتاحُ مطفأٌ، أو الرحلةُ قُبلت قبل
    # إشعاله — والشريطُ لا يُرسم. وهو ما يجعل «يختفي صامتاً» سلوكَ الغياب
    # نفسِه لا فرعاً ثانياً في التطبيق
    steps: list[RouteStepOut] = []
    # **عتبةُ الانحراف بالأمتار — تُنشر ولا تُكتب في التطبيق** (§17.3).
    # وقيمتُها مقيسة: هندسةُ الخطوة خطؤها **٤٫٨ م** في أسوأ رأسٍ قِيس، فـ٨٠ م
    # نحوُ ستةَ عشرَ ضعفَه — وهي النسبةُ نفسُها التي قِيست لإعادة التوجيه
    # (البند ١٧-٤)، **ورقمان لمفهومٍ واحدٍ يفترقان**
    deviation_threshold_m: int = 80


class RecordedRouteOut(BaseModel):
    """**المسارُ الذي سارته الرحلةُ فعلاً** — نقاطُ `ride_route_points` بترتيب زمنها (§٦٢-ج/١١).

    **غيرُ `RouteLineOut`**: ذاك ما قاله Mapbox قبل أن تُسار، وهذا ما سجّله بثُّ الكبتن أثناءها (نقطةٌ كلَّ عشرين ثانيةً
    من البدء إلى الإنهاء، §5.7) — **فلا يبدأ قبل نقطة الانطلاق**: طريقُ الكبتن إلى راكبه لا يُسجَّل ولا يُنشر.

    **و`[[lng, lat], …]` كـ`RouteLineOut`** (ترتيبُ GeoJSON) فيرسمه التطبيقُ بالبانِي نفسِه. **ولا زمنَ معه**: الطرفان يريان
    الخطَّ لا ساعةَ كلِّ نقطة — **أقلُّ بيانٍ يكفي الرسم**، والزمنُ دليلُ نزاعٍ يقرؤه المشرفُ من بابه (§13.4).

    **وقائمةٌ فارغةٌ حالٌ صحيحة**: تطبيقُ الكبتن صمت فلم تُكتب نقطة — والخريطةُ ترسم الدبوسين وحدهما، **ولا خطَّ يُخترع**.
    """

    points: list[list[float]]
    #: **قُصّ الذيلُ عند السقف** (`ride_log.ROUTE_POINT_CAP`) — والسقفُ نفسُه الذي يقرأ به المشرفُ، **ويُقال حين يقع**
    truncated: bool


class RideDriverStatsOut(BaseModel):
    """**عددُ رحلات الكبتن المكتملة** في بطاقته التي يراها راكبُه أثناء الرحلة (R08 «4.92 · 2,140 رحلة»، §٦٢-ج/٢٧).

    **بابٌ لا حقلٌ في `RideDriverOut`**: ذاك يُبنى متزامناً في بثّ المقبس حيث لا جلسةَ تَعُدّ، وحقلٌ يملؤه بابٌ وينساه آخر
    هو الشكلُ الثامن بعينه. **وبابٌ مفتاحُه الرحلةُ لا الكبتن** كبابِ صورته (`/rides/{id}/driver/photo`) — **ويُجيب ما دامت
    جارية**: عددٌ يتغيّر بعدها يجعل رحلةً قديمةً نافذةً على عمل الكبتن كلَّ يوم.
    """

    completed_rides: int


class StartRideRequest(BaseModel):
    """بدءُ الرحلة — **والرمزُ لرحلةٍ تطلبه وحدَها** (§٦٢-ج/٥). وغيابُ الجسم كلِّه بدءٌ بلا رمز كما كان: تطبيقٌ أقدمُ لا يرسل شيئاً."""

    code: str | None = Field(default=None, pattern=r"^[0-9]{4}$")


class TrackLinkOut(BaseModel):
    """رمزُ رابط التتبّع (§٦٣-ج/١) — **التطبيقُ يبني الرابطَ من عنوانه هو** (`/t/{token}`)، فلا نطاقَ مكتوبٌ في الخلفية
    يفترق عن مكان التطبيق."""

    token: str


class PublicTrackVehicleOut(BaseModel):
    make: str
    model: str
    color: str
    plate_number: str


class PublicTrackOut(BaseModel):
    """ما يراه من يفتح رابطَ التتبّع بلا دخول (§٦٣-ج/١) — **أقلُّ ما يكفي**: اسمُ الكبتن وسيارتُه ولوحتُها وموقعُه.

    **و`ended` بلا شيءٍ معه** — الرابطُ يتوقّف بانتهاء الرحلة، ولا يبقى منه أثرٌ لمن فتحه بعدها.
    """

    state: Literal["searching", "coming", "arrived", "riding", "ended"]
    captain_name: str | None = None
    vehicle: PublicTrackVehicleOut | None = None
    position: CoordinatesIn | None = None


class StartCodeOut(BaseModel):
    """رمزُ الرحلة لصاحبتها — أربعُ خاناتٍ لاتينية."""

    code: str
