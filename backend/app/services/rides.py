"""منطق الرحلة: الطلب والانتقالات بين الحالات (SPEC القسم 5).

كل تغيير حالة يمر من هنا لا من الراوتر، وكل انتقال يُفحص ضد
`ALLOWED_TRANSITIONS` قبل تنفيذه. الـ commit مسؤولية الراوتر.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import and_, false, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.currency import currency_for_country
from app.core.exceptions import (
    CancelReasonNotApplicable,
    CancellationDebtBlocked,
    InvalidInput,
    InvalidRideTransition,
    MultiStopUnavailable,
    NotFound,
    PermissionDenied,
    RideAlreadyActive,
    WomenServiceUnavailable,
)
from app.models.driver import Driver
from app.models.enums import (
    CancelReasonCode,
    DriverStatus,
    FeatureKey,
    GenderPreference,
    RideStatus,
    UserRole,
    VehicleCategory,
)
from app.models.ride import (
    ACTIVE_DRIVER_STATUSES,
    ACTIVE_RIDER_STATUSES,
    MAX_INTERMEDIATE_STOPS,
    Ride,
    RideStop,
    make_point,
)
from app.models.user import User
from app.services import cancellation
from app.services import dispatch, pricing, route, settings_service, verification
from app.services.directions import Coordinates, Route
from app.core.exceptions import AmbiguousRole

@dataclass(frozen=True, slots=True)
class StopRequest:
    """محطةٌ وسيطة كما تصل من الطلب — **بترتيبها في القائمة**.

    الترتيبُ والحذفُ يقعان في شاشة الطلب قبل التأكيد (SPEC القسم 5.10)، فتصل
    الخلفيةَ قائمةٌ مرتَّبة ولا مسارَ لإعادة ترتيبِ رحلةٍ قائمة.
    """

    lat: float
    lng: float
    address: str | None = None


# آلة الحالات — ما ليس هنا ممنوع (SPEC القسم 5)
ALLOWED_TRANSITIONS: dict[RideStatus, frozenset[RideStatus]] = {
    # لا قبول مباشر من `requested`: التوزيع هو من يعرض الرحلة، وأول ما يفعله
    # نقلها إلى `searching`. القبول بلا عرضٍ سابق ليس له باب في هذه الآلة.
    RideStatus.REQUESTED: frozenset(
        {
            RideStatus.SEARCHING,
            RideStatus.CANCELLED_BY_RIDER,
        }
    ),
    RideStatus.SEARCHING: frozenset(
        {
            RideStatus.ACCEPTED,
            RideStatus.CANCELLED_BY_RIDER,
            RideStatus.NO_DRIVER_FOUND,
        }
    ),
    RideStatus.ACCEPTED: frozenset(
        {
            RideStatus.ARRIVED,
            RideStatus.CANCELLED_BY_RIDER,
            RideStatus.CANCELLED_BY_DRIVER,
        }
    ),
    RideStatus.ARRIVED: frozenset(
        {
            RideStatus.IN_PROGRESS,
            RideStatus.CANCELLED_BY_RIDER,
            RideStatus.CANCELLED_BY_DRIVER,
        }
    ),
    # لا إلغاء بعد بدء الرحلة: الإنهاء هو المخرج الوحيد — ومعه الوقوفُ عند
    # محطةٍ وسيطة (المرحلة 12-ب)
    RideStatus.IN_PROGRESS: frozenset({RideStatus.COMPLETED, RideStatus.AT_STOP}),
    # **ولا إلغاء من `at_stop` كما لا إلغاء من `in_progress`**: الراكب في
    # السيارة، والانتظارُ جزءٌ من الرحلة لا فاصلٌ يعيد فتح ما أُغلق. ومخرجاها
    # استئنافٌ، أو إنهاءٌ عند المحطة حين يتجاوز الانتظارُ سقفَه (القسم 5.10)
    RideStatus.AT_STOP: frozenset({RideStatus.IN_PROGRESS, RideStatus.COMPLETED}),
    RideStatus.COMPLETED: frozenset(),
    RideStatus.CANCELLED_BY_RIDER: frozenset(),
    RideStatus.CANCELLED_BY_DRIVER: frozenset(),
    RideStatus.NO_DRIVER_FOUND: frozenset(),
}

_LOAD_DRIVER_CARD = (
    selectinload(Ride.driver).selectinload(Driver.user),
    selectinload(Ride.driver).selectinload(Driver.vehicles),
)


def _now() -> datetime:
    return datetime.now(UTC)


async def _flush_and_reload(session: AsyncSession, ride: Ride) -> Ride:
    """يثبّت التعديل ثم يعيد قراءة الصف.

    خطا العرض والطول قيم محسوبة في القاعدة، وكل UPDATE يُبطلها — فبدون قراءة
    جديدة يحاول ORM تحميلها كسولاً وقت التسلسل ويفشل خارج سياق async.
    """
    await session.flush()
    return await get_ride(session, ride.id)


def _require_transition(ride: Ride, target: RideStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[ride.status]:
        raise InvalidRideTransition(
            f"لا يمكن الانتقال من «{ride.status.value}» إلى «{target.value}»"
        )


# ------------------------------------------------------------------ القراءة


async def get_ride(session: AsyncSession, ride_id: uuid.UUID) -> Ride:
    ride = await session.scalar(
        select(Ride).where(Ride.id == ride_id).options(*_LOAD_DRIVER_CARD)
    )
    if ride is None:
        raise NotFound("الرحلة غير موجودة")
    return ride


async def get_ride_for_user(
    session: AsyncSession, ride_id: uuid.UUID, user: User
) -> Ride:
    """الرحلة بعد التحقق من الملكية — لا IDOR (SPEC القسم 14)."""
    ride = await get_ride(session, ride_id)

    if user.has_role(UserRole.ADMIN, UserRole.SUPPORT):
        return ride
    if ride.rider_id == user.id:
        return ride
    if ride.driver is not None and ride.driver.user_id == user.id:
        return ride

    # 404 لا 403: وجود الرحلة نفسه ليس معلومة يستحقها غير أطرافها
    raise NotFound("الرحلة غير موجودة")



def _side_of(user: User, declared: UserRole | None = None) -> UserRole:
    """أيَّ جانبٍ من الرحلة يقف صاحبُ الحساب — **والعمليةُ تعلنه** (§22).

    كان السطرُ `if role == DRIVER: … else: …`، فحسابٌ بدورين يقع في فرعٍ واحدٍ
    **بلا أثر**: تختفي رحلتُه الجارية من الجانب الآخر، ويُعرض نصفُ سجلِّه
    وكأنه كلُّه. وهو أخبثُ من خطأ: لا استثناءَ ولا سطرَ سجلّ ولا شكوى.
    """
    rider = user.has_role(UserRole.RIDER)
    driver = user.has_role(UserRole.DRIVER)

    if declared is not None:
        # الإعلانُ يقرّر ولا يمنح: يُفحص أن صاحبَه يملك ذلك الدور
        if not user.has_role(declared):
            raise PermissionDenied("لا رحلاتِ لهذا الحساب من هذا الجانب")
        return declared

    if rider and driver:
        raise AmbiguousRole(
            "ride_side_undecided",
            "لم يُعلَن جانبُ الرحلات، والحسابُ يحمل الدورين",
        )
    return UserRole.DRIVER if driver else UserRole.RIDER


async def has_any_active_ride(session: AsyncSession, user: User) -> bool:
    """أفي رحلةٍ جاريةٍ **على أيِّ جانب** — بلا سؤالٍ عن جانبه.

    **ولا تمرّ بـ`_side_of`**، وذلك مقصود: من يحمل الدورين هو بالضبط من يُسأل
    هذا السؤال (عند التبديل)، فسؤالٌ يرتدّ عليه لا يجيب. والدلالةُ هي المطلوبةُ
    نفسُها: لا يُبدَّل ومن جانبيه واحدٌ مشغول.
    """
    driver_id = await session.scalar(
        select(Driver.id).where(Driver.user_id == user.id)
    )
    found = await session.scalar(
        select(Ride.id).where(
            or_(
                and_(
                    Ride.rider_id == user.id,
                    Ride.status.in_(ACTIVE_RIDER_STATUSES),
                ),
                and_(
                    Ride.driver_id == driver_id,
                    Ride.status.in_(ACTIVE_DRIVER_STATUSES),
                )
                if driver_id is not None
                else false(),
            )
        )
    )
    return found is not None


async def active_ride_for_user(
    session: AsyncSession, user: User, *, declared: UserRole | None = None
) -> Ride | None:
    """الرحلة الجارية للمستخدم — عليها يعتمد استرجاع الحالة بعد انقطاع (SPEC القسم 10)."""
    stmt = select(Ride).options(*_LOAD_DRIVER_CARD)

    if _side_of(user, declared) is UserRole.DRIVER:
        driver_id = await session.scalar(select(Driver.id).where(Driver.user_id == user.id))
        stmt = stmt.where(
            Ride.driver_id == driver_id, Ride.status.in_(ACTIVE_DRIVER_STATUSES)
        )
    else:
        stmt = stmt.where(
            Ride.rider_id == user.id, Ride.status.in_(ACTIVE_RIDER_STATUSES)
        )

    return await session.scalar(stmt)


async def _rider_has_active_ride(session: AsyncSession, rider_id: uuid.UUID) -> bool:
    return (
        await session.scalar(
            select(Ride.id).where(
                Ride.rider_id == rider_id, Ride.status.in_(ACTIVE_RIDER_STATUSES)
            )
        )
    ) is not None


async def _driver_has_active_ride(session: AsyncSession, driver_id: uuid.UUID) -> bool:
    return (
        await session.scalar(
            select(Ride.id).where(
                Ride.driver_id == driver_id, Ride.status.in_(ACTIVE_DRIVER_STATUSES)
            )
        )
    ) is not None


async def list_rides_for_user(
    session: AsyncSession,
    user: User,
    *,
    limit: int,
    offset: int,
    declared: UserRole | None = None,
) -> Sequence[Ride]:
    """رحلات المستخدم بدوره: الراكب رحلاته، والكبتن ما أُسند إليه."""
    stmt = select(Ride).options(*_LOAD_DRIVER_CARD)

    if _side_of(user, declared) is UserRole.DRIVER:
        driver_id = await session.scalar(select(Driver.id).where(Driver.user_id == user.id))
        stmt = stmt.where(Ride.driver_id == driver_id)
    else:
        stmt = stmt.where(Ride.rider_id == user.id)

    stmt = stmt.order_by(Ride.created_at.desc()).limit(limit).offset(offset)
    return (await session.scalars(stmt)).all()


# ------------------------------------------------------------------- الطلب


def reject_stop_at_dropoff(
    stops: Sequence[StopRequest], dropoff: Coordinates
) -> None:
    """محطةٌ عند الوجهة تُمنع — **ويناديها بابا التقدير والطلب معاً**.

    **العطبُ** (قِيس 2026-08-23): كانت تُقبل ويُحصَّل رسمُها كاملاً — **رسمُ
    وقفةٍ لا وجودَ لها**، لأن الكبتنَ ينتهي هناك على كلِّ حال.

    **والحدُّ نصفُ قطر الالتقاء نفسُه، ولا يُخترع رقمٌ ثانٍ**: هو مقيسٌ
    ومستعمَلٌ في «وصلتُ» وفي إعفاء رسم الإلغاء، **ومسافةٌ واحدةٌ بحدّين
    تفترق** — وأحدُهما يقرّر مالاً. والدالّةُ مستعارةٌ لا مكتوبةٌ ثانيةً.

    **والمنعُ عند الإضافة لا إسقاطُ الرسم صامتاً**: من مُنع يعرف فوراً
    ويصحّح، ومن قُبلت محطتُه ثم اختفى رسمُها لا يفهم لماذا.

    **ويناديه التقديرُ أيضاً**: حارسٌ يقبل في التقدير ويرفض عند التأكيد
    يجعل الراكبَ يبني على رقمٍ ثم يُردّ — وهو أسوأُ من ألّا يُمنع.
    """
    from app.services import geo as geo_service, pauses as pauses_service
    from app.services.cancellation import _metres_between

    for stop in stops:
        near = _metres_between(
            geo_service.Position(lat=stop.lat, lng=stop.lng),
            dropoff.lat,
            dropoff.lng,
        )
        if near <= pauses_service.ARRIVAL_RADIUS_METERS:
            raise InvalidInput("هذه المحطة عند وجهتك", field="stops")


async def request_ride(
    session: AsyncSession,
    *,
    rider: User,
    pickup: Coordinates,
    dropoff: Coordinates,
    vehicle_category: VehicleCategory,
    pickup_address: str | None = None,
    dropoff_address: str | None = None,
    gender_preference: GenderPreference | None = None,
    stops: Sequence[StopRequest] = (),
    promo_code: str | None = None,
    scheduled_for: datetime | None = None,
    share: bool = False,
    share_gender_confirmed: bool = False,
) -> Ride:
    """ينشئ رحلة بحالة `requested`.

    الإسناد لا يبدأ من هنا: الراوتر يُطلق `dispatch.start` **بعد الـ commit**،
    لأن مهمة التوزيع تقرأ الرحلة من جلسة أخرى فلا ترى ما لم يُثبَّت بعد.

    و`gender_preference` غيرُ الممرَّر يعني «خذ افتراضي الملف» لا «`any`»:
    الراكبة تضبطه مرةً في حسابها فيسري على كل طلبٍ لا تختار فيه شيئاً — وهذا
    هو الفرق بين إعدادٍ يعمل وإعدادٍ يُنسى.
    """
    # **الحسابُ المحدود لا يطلب رحلة** (قرارُ المالك 2026-08-31): من سجّل
    # ببريده رقمُه **محجوزٌ لا مملوك** — **والرحلةُ تضع إنساناً في سيارةِ
    # إنسان، والرقمُ هو ما يُتّصل به حين يقع شيء**.
    #
    # **ومكانُه هنا لا في الراوتر** للعلّة المكتوبة تحته حرفاً: **الحجزُ
    # المجدول ينشئ رحلاتِه من هذا الباب نفسِه** (12-ط)، وحارسٌ في الراوتر
    # بابٌ يُنسى في الباب الثاني.
    verification.require_usable_account(rider)

    if await _rider_has_active_ride(session, rider.id):
        raise RideAlreadyActive()

    # **ديونُ الإلغاء تمنع الطلبَ عند حدٍّ تحدّده الإدارة** (§4 من المواصفة).
    # وهو **سؤالٌ واحدٌ مسقوفٌ لا جمعُ دَينٍ في المسار الحرج**: مقارنةُ عددٍ
    # على مؤشّرٍ جزئيّ، وصفرُ الحدِّ يعني «لا إيقاف» فلا يُستدعى شيءٌ أصلاً.
    # ومكانُه هنا لا في الراوتر: الحجزُ المجدول ينشئ رحلاتِه من هذا الباب
    # نفسِه (12-ط)، وحارسٌ في الراوتر بابٌ يُنسى في الباب الثاني
    if await cancellation.blocks_new_ride(
        session, user_id=rider.id, country=rider.country_code
    ):
        raise CancellationDebtBlocked()

    # **الفحصُ عند الإنشاء لا عند العرض** (SPEC القسم 4/`multi_stop_enabled`):
    # واجهةٌ تخفي زرَّ «إضافة محطة» لا تمنع طلباً مصنوعاً بيد. وإطفاءُ المفتاح
    # يمنع الطلبات الجديدة وحدها — الرحلاتُ الجارية بمحطاتها تكمل
    if stops and not await settings_service.is_feature_enabled(
        session, rider.country_code, FeatureKey.MULTI_STOP_ENABLED
    ):
        raise MultiStopUnavailable()
    if len(stops) > MAX_INTERMEDIATE_STOPS:
        raise InvalidInput(
            f"أقصى عدد محطاتٍ وسيطة {MAX_INTERMEDIATE_STOPS}"
        )

    # **محطةٌ عند الوجهة تُمنع عند الإضافة** (قرارُ المالك 2026-08-23): كانت
    # تُقبل ويُحصَّل رسمُها كاملاً — **رسمُ وقفةٍ لا وجودَ لها**، لأن الكبتنَ
    # ينتهي هناك على كلِّ حال.
    #
    # **والحدُّ نصفُ قطر الالتقاء نفسُه ولا يُخترع رقمٌ ثانٍ**: هو مقيسٌ
    # ومستعمَلٌ في «وصلتُ» وفي إعفاء رسم الإلغاء، **ومسافةٌ واحدةٌ بحدّين
    # تفترق** — وأحدُهما يقرّر مالاً. والدالّةُ مستعارةٌ لا مكتوبةٌ ثانيةً،
    # للعلّة نفسِها.
    #
    # **والمنعُ عند الإضافة لا إسقاطُ الرسم صامتاً**: من مُنع يعرف فوراً
    # ويصحّح، ومن قُبلت محطتُه ثم اختفى رسمُها **لا يفهم لماذا** — والكبتنُ
    # يقف عندها فعلاً فيُقرأ الإسقاطُ ظلماً له.
    reject_stop_at_dropoff(stops, dropoff)

    preference = (
        rider.ride_gender_preference if gender_preference is None else gender_preference
    )
    if preference is not GenderPreference.ANY and not await (
        settings_service.is_feature_enabled(
            session, rider.country_code, FeatureKey.WOMEN_SERVICE_ENABLED
        )
    ):
        # الخدمة مطفأة في هذه الدولة، والتطبيقُ لا يعرض المفتاح أصلاً — فما
        # يصل هنا طلبٌ مصنوع باليد أو تفضيلٌ في ملفٍ بقي من سوقٍ آخر. ولا
        # يُبتلع صامتاً: طلبٌ يُسنَد لأيّ كبتنٍ بعد أن طُلب فيه غيرُه أسوأ من
        # طلبٍ يُرفض بسببه
        raise WomenServiceUnavailable()

    # **المشاركةُ تُفحص عند الإنشاء كالمحطات** (12-ي): واجهةٌ تخفي المفتاح لا
    # تمنع طلباً مصنوعاً بيد. و`share_percent` صفرٌ يعني رحلةً غيرَ مشتركة
    share_percent = Decimal("0.00")
    if share:
        from app.services import sharing as sharing_service

        await sharing_service.require_available(session, rider.country_code)
        # **أضيقُ من المواصفة بقرار المالك الرابع**: طلبٌ بتفضيلٍ نسائيٍّ لا
        # يُشارَك إلا بخيارٍ صريحٍ من صاحبته — والقبولُ الصامتُ لا يكفي أمناً
        sharing_service.guard_gender_choice(
            preference, share_confirmed=share_gender_confirmed
        )
        # **بلا محطاتٍ في القطع الأول** (SPEC §5.12): مسارٌ بمحطاتٍ لا يُطابَق
        # عليه ممرٌّ، ووعدُ التفافٍ محدودٍ لا يُحفظ فوق التفافاتٍ اختارها الأول
        if stops:
            raise InvalidInput("المشاركة لا تجتمع مع محطاتٍ وسيطة")
        row = await sharing_service.settings_for(session, rider.country_code)
        assert row is not None  # `require_available` تحقّق منه
        share_percent = row.discount_percent

    # السعر يُعاد حسابه هنا ولا يُقرأ من طلب العميل مهما أرسل
    quote = await pricing.estimate(
        session,
        country_code=rider.country_code,
        vehicle_category=vehicle_category,
        pickup=pickup,
        dropoff=dropoff,
        stops=[Coordinates(lat=stop.lat, lng=stop.lng) for stop in stops],
    )
    # تسعيرةُ الدولة تُقرأ مرةً واحدة: منها التقديرُ ومنها الحقولُ المجمَّدة
    rule = await pricing.get_rule(session, rider.country_code, vehicle_category)

    ride = Ride(
        rider_id=rider.id,
        country_code=rider.country_code,
        vehicle_category=vehicle_category,
        # موعدُ الحجز مجمَّداً على الرحلة (12-ط) — و`None` للطلب الفوري
        scheduled_for=scheduled_for,
        pickup_point=make_point(pickup.lat, pickup.lng),
        pickup_address=pickup_address,
        dropoff_point=make_point(dropoff.lat, dropoff.lng),
        dropoff_address=dropoff_address,
        status=RideStatus.REQUESTED,
        distance_km=quote.route.distance_km,
        duration_min=quote.route.duration_min,
        estimated_fare=quote.fare,
        currency=currency_for_country(rider.country_code),
        # **نسبةُ السوق مبدئياً — وتُحسم لحظةَ القبول** (§25.11).
        #
        # لا كبتنَ عند الإنشاء أصلاً (التوزيعُ يعرض على واحدٍ بعد واحد)، فنسبةُ
        # **اشتراكه** لا تُعرف هنا. وهذه قيمةٌ مبدئيةٌ يستبدلها `accept_ride`
        # بنسبة صاحبِ الرحلة الفعليّ — **قبل أن يتحرك أيُّ مال**، فالتجميدُ
        # يبقى واحداً ولا يُعاد حسابُه بعد ذلك أبداً.
        commission_percent_at_ride=await settings_service.commission_percent_for(
            session, rider.country_code
        ),
        # يُجمَّد كالعمولة: تغييرُ الملف بعد الطلب لا يغيّر لمن يُعرض هذا الطلب
        gender_preference=preference,
        # المحطاتُ ومعدلاتُ انتظارها **مجمَّدةٌ لحظتها** (SPEC القسم 5.10):
        # مشرفٌ يرفع سعر الدقيقة ورحلةٌ واقفةٌ عند محطةٍ الآن لا يجوز أن
        # يتغيّر عدّادُها تحت عين راكبها
        stops_count=len(stops),
        stop_fee_at_ride=rule.stop_fee,
        stop_free_minutes_at_ride=rule.stop_free_minutes,
        stop_price_per_min_at_ride=rule.stop_price_per_min,
        stop_max_wait_minutes_at_ride=rule.stop_max_wait_minutes,
        # **معاملاتُ الوقفة تُجمَّد كغيرها** (§5.10-ب): تعديلُ اللوحة يحكم ما
        # يأتي لا وقفةً يقف فيها كبتنٌ الآن
        pause_price_per_min_at_ride=rule.pause_price_per_min,
        arrival_free_minutes_at_ride=rule.arrival_free_minutes,
        pause_max_minutes_at_ride=rule.pause_max_minutes,
        # تُجمَّد كالعمولة: تعديلُ النسبة في اللوحة يحكم ما يأتي لا رحلةً سائرة
        share_discount_percent_at_ride=share_percent,
        # **ما سيراه الكبتنُ على بطاقة العرض قبل أن يقبل** (§6-أ): دَينُ إلغاءٍ
        # على هذا الراكب يُسلَّم نقداً مع الأجرة. يُجمَّد هنا كموعد الحجز
        # ونسبةِ العمولة — الرحلةُ تحمل **ما عُرض**، والمصدرُ يبقى الجدول
        carried_cancellation_fee=await cancellation.debt_of(session, rider.id),
    )
    session.add(ride)

    # **الكوبونُ يُجمَّد قبل الـflush** (12-ز): الرمزُ يُتحقق منه تحت قفل صفّه،
    # فطلبان متزامنان بنفس الرمز لا يتجاوزان حدَّ المستخدم ولا الميزانية. ولا
    # مبلغَ يُكتب — الأجرةُ النهائية لا تُعرف قبل الإنهاء (القسم 6.6)
    if promo_code:
        from app.services import promo as promo_service

        await promo_service.apply_to_ride(
            session, ride=ride, rider=rider, code=promo_code
        )
    else:
        # **وكوبونُ ترحيب المُحال في `else` لا بجانبه** (تعميمُ الإحالة): من
        # كتب رمزاً اختار عرضاً بعينه، وإحلالُ غيره محلَّه — ولو كان أكبر —
        # يجعل الشاشةَ تعرض ما لم يطلبه. **ولا يُفشل الطلبَ بحال**: الراكبُ لم
        # يسأل هذه الهدية، فردُّ خطأٍ على «اطلب رحلة» بسببها أسوأُ من غيابها
        from app.services import referrals as referrals_service

        await referrals_service.apply_welcome_promo(session, ride=ride, rider=rider)

    # الإلحاقُ بالمجموعة لا `RideStop(ride=…)`: العلاقةُ أحاديةُ الاتجاه
    # (`Ride.stops` بلا `back_populates`)، والـcascade هو ما يكتب `ride_id`
    for index, stop in enumerate(stops, start=1):
        ride.stops.append(
            RideStop(
                sequence=index,
                point=make_point(stop.lat, stop.lng),
                address=stop.address,
            )
        )

    try:
        await session.flush()
    except IntegrityError as exc:
        # الفهرس الجزئي `uq_rides_active_rider` — طلبان متزامنان من نفس الراكب
        await session.rollback()
        raise RideAlreadyActive() from exc

    return ride


# -------------------------------------------------------------- الانتقالات


async def mark_searching(session: AsyncSession, ride: Ride) -> Ride:
    """بداية التوزيع — يستدعيها `services/dispatch.py` وحدها."""
    _require_transition(ride, RideStatus.SEARCHING)
    ride.status = RideStatus.SEARCHING
    return await _flush_and_reload(session, ride)


async def mark_no_driver_found(session: AsyncSession, ride: Ride) -> Ride:
    """نفدت المحاولات أو المهلة بلا قبول (SPEC القسم 5.3)."""
    _require_transition(ride, RideStatus.NO_DRIVER_FOUND)
    ride.status = RideStatus.NO_DRIVER_FOUND
    return await _flush_and_reload(session, ride)


async def accept_ride(
    session: AsyncSession, redis: Redis, ride_id: uuid.UUID, driver: Driver
) -> Ride:
    """قبول الكبتن للرحلة المعروضة عليه.

    لا يقبلها إلا من عُرضت عليه وضمن مهلته — التوزيع يعرضها على واحد في كل
    مرة (SPEC القسم 5.3)، فالقبول من كبتن آخر لا يكون إلا التفافاً على الدور.
    المرحلة 7 تضيف شرط الاشتراك الساري.
    """
    if driver.status != DriverStatus.APPROVED:
        raise PermissionDenied("حساب الكبتن غير معتمد بعد")
    await dispatch.require_offer(redis, ride_id, driver.id)
    if await _driver_has_active_ride(session, driver.id):
        raise RideAlreadyActive("لديك رحلة جارية بالفعل")

    # قفل الصف: كبتنان يضغطان «قبول» في نفس اللحظة لا يفوزان معاً
    ride = await session.scalar(
        select(Ride).where(Ride.id == ride_id).with_for_update()
    )
    if ride is None:
        raise NotFound("الرحلة غير موجودة")

    driver_user = await session.get(User, driver.user_id)
    if driver_user is None or driver_user.country_code != ride.country_code:
        raise PermissionDenied("الرحلة خارج نطاق بلدك")

    _require_transition(ride, RideStatus.ACCEPTED)

    ride.driver_id = driver.id
    ride.status = RideStatus.ACCEPTED
    ride.accepted_at = _now()
    driver.current_ride_id = ride.id

    # **وهنا تُحسم نسبةُ العمولة** (§25.11، قرارُ المالك 2026-08-20).
    #
    # الوعدُ «صفر عمولة ما دام اشتراكك سارياً» يخصّ **الكبتن**، ولا كبتنَ يُعرف
    # عند إنشاء الرحلة — فما جُمّد هناك نسبةُ السوق مبدئياً. وهنا صار صاحبُها
    # معروفاً، فتُكتب نسبتُه **مرةً واحدةً وقبل أن يتحرك أيُّ مال** (`payments`
    # لا تعمل قبل `completed`).
    #
    # **وقراءةُ عمودٍ لا استعلام**: `driver` مقروءٌ أصلاً في هذا المسار، فلا ضمَّ
    # ولا استعلامَ ثانٍ (§٥-ج) — وهي سابقةُ `rating_avg` و`level` نفسُها.
    #
    # **و`None` تعني «لا اشتراكَ ساري»** فتبقى نسبةُ السوق، وصفرٌ يعني اشتراكاً
    # اشتُري على صفر — وهما حالان لا يحملهما رقمٌ واحد.
    if driver.commission_percent_from_subscription is not None:
        ride.commission_percent_at_ride = driver.commission_percent_from_subscription

    try:
        return await _flush_and_reload(session, ride)
    except IntegrityError as exc:
        # الفهرس الجزئي `uq_rides_active_driver` — قبولان متزامنان لنفس الكبتن
        await session.rollback()
        raise RideAlreadyActive("لديك رحلة جارية بالفعل") from exc


async def mark_arrived(session: AsyncSession, ride: Ride) -> Ride:
    """«وصلتُ إلى الراكب» — **وتبدأ معها مهلةُ الانتظار** (§5.10-ب).

    **والعدّادُ لا يبدأ خارج نطاق الالتقاء** (قرارُ المالك في الفرع هـ، بتعليله:
    «وإلا صار «وصلت» الكاذبُ باباً للكسب»). والضغطةُ هي ما يبدؤه (الفرع د)،
    والنطاقُ **شرطُ صحّتها**.

    **ولا تُرفض الحالةُ خارج النطاق**: الرحلةُ تمضي والكبتنُ يُعلن وصولَه —
    الذي لا يقع هو **المال**. ورفضُ «وصلت» كان سيوقف رحلةً بسبب دقّةِ GPS.
    """
    _require_transition(ride, RideStatus.ARRIVED)
    ride.status = RideStatus.ARRIVED
    ride.arrived_at = _now()

    from app.services import pauses

    await pauses.begin_arrival_wait(
        session, ride, within_radius=await _driver_at_pickup(session, ride)
    )
    # **وتُفرَّغ العلاقةُ بعد إنشاء الوقفة** — انظر `routers/rides.begin_pause`:
    # `ride.pauses` محمَّلةٌ مع الصفّ، وصفٌّ يُضاف بعدها لا يظهر فيها
    await session.flush()
    session.expire(ride, ["pauses"])
    return await _flush_and_reload(session, ride)


async def _driver_at_pickup(session: AsyncSession, ride: Ride) -> bool:
    """هل الكبتنُ داخل نطاق الالتقاء الآن؟

    **ويُقرأ من آخرِ بثٍّ حيٍّ** (`geo.last_position`) — الفهرسُ للإحداثيات
    ومفتاحُ الحضور للحياة، كما في إعفاء رسم الإلغاء. **وصمتٌ يعني «لا عدّاد»**:
    الشكُّ لمن سيُحاسَب، وهو الراكب.
    """
    from app.core.redis_client import get_redis_client
    from app.services import geo, pauses
    from app.services.cancellation import _metres_between

    if ride.driver_id is None:  # pragma: no cover
        return False
    position = await geo.last_position(
        get_redis_client(), driver_id=ride.driver_id, country_code=ride.country_code
    )
    if position is None:
        return False
    # **ودالةُ المسافة مستعارةٌ من إعفاء رسم الإلغاء لا مكتوبةٌ ثانيةً**: صيغتان
    # لمسافةٍ واحدةٍ تفترقان، وإحداهما تقرّر مالاً
    metres = _metres_between(position, ride.pickup_lat, ride.pickup_lng)
    return metres <= pauses.ARRIVAL_RADIUS_METERS


async def start_ride(session: AsyncSession, ride: Ride) -> Ride:
    """بدءُ الرحلة — **ويُغلق معها عدّادُ انتظار الوصول**.

    ووقفةٌ تبقى مفتوحةً تُقاس **حتى الآن**، فتكبر فاتورتُها كلَّما فُتحت الشاشة.
    """
    _require_transition(ride, RideStatus.IN_PROGRESS)
    ride.status = RideStatus.IN_PROGRESS
    ride.started_at = _now()

    from app.services import pauses

    await pauses.end_open(session, ride.id)
    return await _flush_and_reload(session, ride)


async def _close_open_pause(session: AsyncSession, ride: Ride) -> None:
    """**وقفةٌ مفتوحةٌ عند الإنهاء تُغلق قبل الحساب** — وإلا كبرت إلى الأبد."""
    from app.services import pauses

    await pauses.end_open(session, ride.id)


async def complete_ride(session: AsyncSession, ride: Ride, driver: Driver) -> Ride:
    """إنهاء الرحلة وتثبيت `final_fare` (SPEC القسم 5.7/5.8).

    السعر النهائي = المقدّر، **إلا** أن تنحرف المسافة الفعلية المحسوبة من نقاط
    المسار انحرافاً كبيراً؛ فعندها يُعاد الحساب عليها بنفس تسعيرة الدولة
    والفئة. المدة تبقى المقدّرة: القسم 5.7 يبني إعادة الحساب على **المسافة**
    وحدها، وإقحامُ زمنٍ فعليٍّ لم يطلبه يحمّل الراكبَ ازدحامَ الطريق مرتين.

    غياب النقاط (تطبيقُ كبتنٍ صامت) يُبقي المقدَّر حكماً — لا تخمين لمسافة.
    تحصيل المبلغ نفسه في `services/payments.py` بعد هذه اللحظة.
    """
    _require_transition(ride, RideStatus.COMPLETED)
    ride.status = RideStatus.COMPLETED
    ride.completed_at = _now()

    actual_km = await route.actual_distance_km(session, ride.id)
    ride.actual_distance_km = actual_km
    # **قبل الحساب لا بعده**: `minutes_of` تقيس المفتوحةَ حتى الآن
    await _close_open_pause(session, ride)
    ride.final_fare = await _final_fare(session, ride, actual_km)

    # **خصمُ الكوبون دفعةٌ تُنشأ هنا وتؤكَّد** (12-ز، القسم 6.6): الأجرةُ صارت
    # معلومةً للتوّ، والقاعدةُ مجمَّدةٌ على الرحلة. وبها يصير ما على الراكب
    # الأجرةَ ناقصَ الخصم تلقائياً، وتُجمع أرباحُ الكبتن من الصفَّين كأن لا كوبون
    if ride.promo_code_id is not None:
        from app.services import promo as promo_service

        rider = await session.get(User, ride.rider_id)
        if rider is not None:
            await promo_service.settle_discount(session, ride, rider=rider)

    # **وخصمُ المشاركة صفٌّ ثانٍ مستقل** (12-ي) بنفس الآلية وبقناته `share`.
    # ويجتمعان على رحلةٍ واحدة بلا قاعدةٍ جديدة: الدفعُ المختلط من 6-أ يجمع
    # الصفوفَ ويطرحها من `final_fare`، فتُخصم النسبتان معاً ويقبض الكبتنُ كأن
    # لا خصمَ في واحدةٍ منهما. **ومستقلٌّ لا مدموج** لأن `promo.spent()` يقيس
    # ميزانيةَ الكوبون بجمع دفعات `promo` وحدَها
    if ride.share_discount_percent_at_ride > 0:
        from app.services import sharing as sharing_service

        rider = await session.get(User, ride.rider_id)
        if rider is not None:
            await sharing_service.settle_discount(session, ride, rider=rider)

    driver.current_ride_id = None
    return await _flush_and_reload(session, ride)


async def _final_fare(
    session: AsyncSession, ride: Ride, actual_km: Decimal | None
) -> Decimal:
    """الأجرةُ النهائية = أجرةُ الطريق + رسمُ الانتظار.

    ورسمُ الانتظار يُحسب **بالمعدلات المجمَّدة على الرحلة** لا من الإعدادات:
    تعديلُ المشرف يحكم ما بعده (SPEC القسم 5.10). ويُضاف **بعد** الحدّ
    الأدنى لا قبله: الحدُّ الأدنى حدُّ أجرةِ طريق، ورسمُ انتظارٍ يُبتلع فيه
    يعني كبتناً وقف عشرين دقيقةً بلا مقابل.
    """
    base = ride.estimated_fare
    if actual_km is not None and route.deviates(ride.distance_km, actual_km):
        rule = await pricing.get_rule(
            session, ride.country_code, ride.vehicle_category
        )
        base, _ = pricing.calculate_fare(
            rule,
            Route(distance_km=actual_km, duration_min=ride.duration_min),
            ride.stops_count,
        )

    # **ورسمُ الوقفات داخلٌ في `final_fare`** (قرارُ المالك في الفرع و):
    # المجموعُ واحدٌ والسببُ ظاهرٌ في التفصيل — لا مبلغان يُجمعان بيد
    return pricing.round_money(
        base
        + await waiting_charge_for(session, ride)
        + await pause_charge_for(session, ride)
    )


async def pause_charge_for(
    session: AsyncSession, ride: Ride, now: datetime | None = None
) -> Decimal:
    """رسمُ الوقفات غير المخطَّطة — **بابٌ واحدٌ يقرؤه الحسابُ والشاشة**."""
    from app.services import pauses

    return await pauses.charge_for(session, ride, now)


async def waiting_charge_for(
    session: AsyncSession, ride: Ride, now: datetime | None = None
) -> Decimal:
    """رسمُ انتظارِ هذه الرحلة حتى اللحظة — بمعدلاتها المجمَّدة.

    **يُقرأ أثناء الرحلة كما يُقرأ عند إنهائها**: منه يرى الراكبُ رسمَه
    الحالي وهو واقف، فلا مفاجأةَ في شاشة الدفع (SPEC القسم 5.10). والمحطةُ
    التي لم تُستأنف بعد تُقاس حتى الآن.
    """
    if ride.stops_count == 0:
        return Decimal("0.000")

    stops = await stops_of(session, ride.id)
    return pricing.waiting_charge(
        stops,
        free_minutes=ride.stop_free_minutes_at_ride,
        price_per_min=ride.stop_price_per_min_at_ride,
        now=now or _now(),
    )


async def stops_of(session: AsyncSession, ride_id: uuid.UUID) -> list[RideStop]:
    return list(
        (
            await session.scalars(
                select(RideStop)
                .where(RideStop.ride_id == ride_id)
                .order_by(RideStop.sequence)
            )
        ).all()
    )


# ------------------------------------------------- المحطات الوسيطة (12-ب)


async def arrive_at_stop(
    session: AsyncSession, ride: Ride, stop_id: uuid.UUID
) -> tuple[Ride, RideStop]:
    """وصل الكبتنُ محطةً وسيطة — يبدأ عدّادُ الانتظار.

    **الصفُّ يُقفل قبل فحص الانتقال** كما تفرض قاعدة المشروع على كل تغيير
    حالة: بغير القفل تمر ضغطتان متزامنتان فتكتبان ختمين، ويبدأ العدّادُ من
    الثاني فيضيع على الكبتن ما انتظره بينهما.
    """
    stop = await _locked_stop(session, ride, stop_id)
    if stop.arrived_at is not None:
        raise InvalidRideTransition("وصلتَ هذه المحطة بالفعل")

    _require_transition(ride, RideStatus.AT_STOP)
    ride.status = RideStatus.AT_STOP
    stop.arrived_at = _now()
    await session.flush()
    return await _flush_and_reload(session, ride), stop


async def resume_from_stop(
    session: AsyncSession, ride: Ride, stop_id: uuid.UUID
) -> tuple[Ride, RideStop]:
    """يستأنف الكبتنُ السير — يُقفل عدّادُ الانتظار وتبدأ الساقُ التالية.

    و**زيادةُ `current_leg` هنا وحدها**: هذا هو كاتبُ العمود الوحيد، تحت قفل
    صفِّ الرحلة. بغيره تُزاد مرتين بضغطتين متزامنتين، فتُنسب نقاطُ ساقٍ إلى
    ساقٍ لم تبدأ ويُقرأ دليلُ النزاع خطأً.
    """
    stop = await _locked_stop(session, ride, stop_id)
    if stop.arrived_at is None:
        raise InvalidRideTransition("لم تصل هذه المحطة بعد")
    if stop.resumed_at is not None:
        raise InvalidRideTransition("استأنفتَ من هذه المحطة بالفعل")

    _require_transition(ride, RideStatus.IN_PROGRESS)
    ride.status = RideStatus.IN_PROGRESS
    ride.current_leg = ride.current_leg + 1
    stop.resumed_at = _now()
    await session.flush()
    return await _flush_and_reload(session, ride), stop


async def _locked_stop(
    session: AsyncSession, ride: Ride, stop_id: uuid.UUID
) -> RideStop:
    """يقفل صفَّ الرحلة ثم صفَّ المحطة — **بهذا الترتيب**.

    ترتيبُ الأقفال في المشروع يبدأ بصفِّ الرحلة (`CLAUDE.md`)، فمن يقفل
    المحطةَ أولاً ثم الرحلة يفتح باب جمودٍ مع كل مسارٍ آخر يمس الرحلة.
    """
    await session.refresh(ride, with_for_update=True)

    stop = await session.scalar(
        select(RideStop)
        .where(RideStop.id == stop_id, RideStop.ride_id == ride.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if stop is None:
        raise NotFound("المحطة غير موجودة في هذه الرحلة")
    return stop


# كم بلاغَ «الطرف ليس بالجنس المعلَن» يوسم الحساب للمراجعة (المرحلة 10-ج).
# ثلاثةٌ لا واحد: بلاغٌ واحد قد يكون سوءَ فهمٍ أو ضوءاً خافتاً أو كبتناً أرسل
# غيرَه، ووسمُ حسابٍ من أول بلاغٍ يجعل الوسمَ سلاحاً بيد من يريد الإضرار
GENDER_MISMATCH_FLAG_THRESHOLD = 3


def _gender_mismatch_applies(ride: Ride, driver: Driver | None, by_role: UserRole) -> bool:
    """هل لهذا السبب محلٌّ في هذه الرحلة أصلاً؟

    - **الراكبة**: لا تُلغي مجاناً بحجّة الجنس إلا إن كانت قد طلبت جنساً.
      وبغير هذا الشرط يصير السببُ باباً مفتوحاً للإفلات من رسوم الإلغاء.
    - **الكبتن**: لا يُلغي بها إلا إن كان قد قصر عملَه على جنس. وهو لا يدفع
      رسوماً أصلاً، لكن **البلاغ يُوسم به حسابُ الراكب** — فبلاغٌ بلا محلٍّ
      يسم بريئاً.
    """
    if by_role == UserRole.DRIVER:
        return driver is not None and driver.gender_preference is not GenderPreference.ANY
    return ride.gender_preference is not GenderPreference.ANY


async def cancel_ride(
    session: AsyncSession,
    ride: Ride,
    *,
    by_role: UserRole,
    reason: str | None = None,
    reason_code: CancelReasonCode | None = None,
) -> Ride:
    """إلغاء مجاني قبل القبول، وبرسوم بعده (SPEC القسم 5).

    الرسوم تُثبَّت على الرحلة هنا؛ تحصيلها مع بقية الدفع في المرحلة 6.

    و**`gender_mismatch` إلغاءٌ بلا رسوم لأيّ الطرفين** (المرحلة 10-ج): امرأةٌ
    طلبت سائقةً فجاءها رجل لا تُغرَّم لأنها رفضت الركوب معه — وتغريمُها هنا
    تجعل الأرخصَ لها أن تركب. ويُسجَّل البلاغ على حساب الطرف الآخر، فالتكرار
    هو ما يميّز سوءَ الفهم من نمطٍ يتكرر.
    """
    # قفل الصف قبل فحص الانتقال: قبولُ كبتنٍ وقع في هذه اللحظة لا يُدهس
    await session.refresh(ride, with_for_update=True)

    target = (
        RideStatus.CANCELLED_BY_DRIVER
        if by_role == UserRole.DRIVER
        else RideStatus.CANCELLED_BY_RIDER
    )
    _require_transition(ride, target)

    driver = (
        await session.get(Driver, ride.driver_id)
        if ride.driver_id is not None
        else None
    )
    mismatch = reason_code is CancelReasonCode.GENDER_MISMATCH
    if mismatch and not _gender_mismatch_applies(ride, driver, by_role):
        raise CancelReasonNotApplicable()

    fee = Decimal("0.000")
    # لا رسوم على الكبتن الملغي — الرسم على من ألغى بعد ارتباط الطرفين
    if (
        by_role == UserRole.RIDER
        and not mismatch
        and ride.status in (RideStatus.ACCEPTED, RideStatus.ARRIVED)
    ):
        rule = await pricing.get_rule(session, ride.country_code, ride.vehicle_category)
        fee = pricing.round_money(rule.cancellation_fee)

    if mismatch:
        await _record_gender_mismatch(session, ride, driver, by_role=by_role)

    ride.status = target
    ride.cancelled_at = _now()
    ride.cancelled_reason = reason
    ride.cancel_reason_code = reason_code.value if reason_code else None
    ride.cancellation_fee = fee

    if driver is not None and driver.current_ride_id == ride.id:
        driver.current_ride_id = None

    return await _flush_and_reload(session, ride)


async def _record_gender_mismatch(
    session: AsyncSession,
    ride: Ride,
    driver: Driver | None,
    *,
    by_role: UserRole,
) -> None:
    """يُدخل البلاغ على حساب **الطرف الآخر** — من أُبلغ عنه لا من أبلغ."""
    reported_user_id = (
        ride.rider_id if by_role == UserRole.DRIVER else (driver.user_id if driver else None)
    )
    if reported_user_id is None:
        return  # لا كبتن مسنداً بعد: لا أحد يُبلَّغ عنه

    reported = await session.get(User, reported_user_id, with_for_update=True)
    if reported is not None:
        reported.gender_mismatch_reports += 1


def is_flagged_for_gender_mismatch(user: User) -> bool:
    """الوسمُ سؤالٌ عن العدد لا عمودٌ يُكتب — فتغييرُ الحدّ يعيد تقييم الجميع."""
    return user.gender_mismatch_reports >= GENDER_MISMATCH_FLAG_THRESHOLD


async def stops_over_max_wait(
    session: AsyncSession, now: datetime | None = None
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """محطاتٌ تجاوز انتظارُها سقفَها ولم تُخطَر بعد — `(ride_id, stop_id)`.

    **الشرطُ يُقرأ بالساعة لا بعمود** كشرط الاشتراك: المقارنةُ بين `now` وبين
    `arrived_at + السقف`، والسقفُ **المجمَّد على الرحلة** لا الذي في الإعدادات.
    و`stop_max_wait_minutes_at_ride = 0` يعني **لا سقف** فتُستثنى رحلتُه.
    """
    moment = now or _now()
    rows = await session.execute(
        select(Ride.id, RideStop.id)
        .join(RideStop, RideStop.ride_id == Ride.id)
        .where(
            Ride.status == RideStatus.AT_STOP,
            Ride.stop_max_wait_minutes_at_ride > 0,
            RideStop.arrived_at.is_not(None),
            RideStop.resumed_at.is_(None),
            RideStop.notified_at.is_(None),
            # `عدد × interval '1 minute'` بدل `make_interval(mins=…)`:
            # `func` في SQLAlchemy لا يمرّر وسائط مسمّاة إلى دوال SQL
            RideStop.arrived_at
            + Ride.stop_max_wait_minutes_at_ride * text("interval '1 minute'")
            <= moment,
        )
    )
    return [(ride_id, stop_id) for ride_id, stop_id in rows.all()]


async def mark_stop_notified(
    session: AsyncSession, stop_id: uuid.UUID
) -> tuple[Ride, RideStop] | None:
    """يختم `notified_at` تحت قفل الصف — أو `None` إن سبقه أحد.

    **القفلُ هو ما يجعل التنبيه واحداً**: عاملان يقرآن نفس الصف في نفس الدورة
    ويكتبان ختمين، فيصل الطرفين إشعاران عن وقوفٍ واحد. والفحصُ **بعد** القفل
    لا قبله — وهذا هو الفرق بين حارسٍ يعمل وحارسٍ يبدو أنه يعمل.
    """
    stop = await session.scalar(
        select(RideStop)
        .where(RideStop.id == stop_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if stop is None or stop.notified_at is not None or stop.resumed_at is not None:
        return None

    ride = await get_ride(session, stop.ride_id)
    # استأنف الكبتنُ بين القراءة والقفل: لا تجاوزَ يُخطَر عنه
    if ride.status is not RideStatus.AT_STOP:
        return None

    stop.notified_at = _now()
    await session.flush()
    return ride, stop
