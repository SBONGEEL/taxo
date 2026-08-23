from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.services.settlement import SettlementState
from app.schemas.driver import MapSkinOut
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

        return cls(
            stops=stops,
            current_leg=ride.current_leg,
            share_discount_percent=ride.share_discount_percent_at_ride,
            share_group_id=ride.share_group_id,
            share_seat=ride.share_seat,
            waiting_charge=pricing.waiting_charge(
                ride.stops,
                free_minutes=ride.stop_free_minutes_at_ride,
                price_per_min=ride.stop_price_per_min_at_ride,
                now=moment,
            ),
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
