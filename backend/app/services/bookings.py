"""الرحلات المجدولة — الحجزُ وتنفيذُه (SPEC القسم 5.11، المرحلة 12-ط).

**والحجزُ ليس رحلة** (قرارُ المالك): هذا الملفُّ يكتب صفَّ حجزٍ، ولا يُنشئ رحلةً
إلا لحظةَ التنفيذ — **وحين يُنشئها يستدعي `rides.request_ride` نفسَه**، فلا بابَ
ثانياً لإنشاء رحلة. وبابٌ ثانٍ يعني قاعدةً تُفحص في أحدهما وتُنسى في الآخر: فحصُ
المحطات، وحدُّ الرحلة النشطة، وتفضيلُ الجنس، وتجميدُ العمولة — كلُّها هناك.

**والسعرُ يُحسب عند التنفيذ.** ما يُخزَّن هنا تقديرٌ لحظةَ الحجز للعرض وحده
(`estimated_fare_at_booking`)، فالتسعيرةُ تتغيّر من اللوحة والمسارُ يُعاد حسابُه
على نقاطه أصلاً.

**وثلاثةُ فروقٍ عن الرحلة الفورية، كلُّها لأن صاحبَ الحجز نائمٌ لا أمام الشاشة:**

1. التوزيعُ يبدأ **قبل الموعد بهامش** — التوزيعُ نفسُه يستغرق حتى دقيقتين.
2. **حجزٌ حلَّ موعدُه وصاحبُه في رحلةٍ جارية** يصير `missed` **بإشعار**: الفهرسُ
   يمنع رحلةً ثانية أصلاً، والصمتُ يجعله يظنّ أن سيارةً في الطريق.
3. **وفشلُ التوزيع يُبلَّغ بإشعارٍ يعرف أنه حجز**: `no_driver_found` على رحلةٍ
   فوريةٍ يراه صاحبُه على الشاشة؛ ومن حجز موعدَ مطارٍ ونام يستحق أن يُوقَظ.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from httpx import HTTPError

from app.core.exceptions import (
    AppError,
    Conflict,
    FeatureDisabled,
    InvalidInput,
    NotFound,
    RideAlreadyActive,
    WomenServiceUnavailable,
)
from app.models.booking import RideBooking
from app.models.enums import (
    BookingStatus,
    FeatureKey,
    GenderPreference,
    PaymentMethod,
    RideStatus,
    VehicleCategory,
)
from app.models.ride import Ride, make_point
from app.models.user import User
from app.services import dispatch, pricing, rides as rides_service, settings_service
from app.services.directions import Coordinates
from app.services.notifications import (
    publish_booking_missed,
    publish_booking_no_driver,
    publish_booking_preference_dropped,
)

logger = logging.getLogger(__name__)

# **الهامشُ قبل الموعد**: التوزيعُ يعرض عشرين ثانيةً لكل كبتنٍ حتى خمسِ محاولاتٍ
# أو دقيقتين (القسم 5.3)، فبدءُ التوزيع في اللحظة يعني كبتناً يصل متأخراً بيقين.
# وعشرُ دقائقَ تكفي للبحث وللوصول إلى نقطة الانطلاق، ولا تُقدّم الموعدَ كثيراً.
LEAD_MINUTES = 10

# **أقلُّ مهلةٍ للحجز**: حجزٌ لبعد خمسِ دقائق ليس حجزاً بل طلبٌ فوريٌّ بطريقٍ
# أطول — ويُربك صاحبَه لأنه لا يرى بحثاً يجري. والحدُّ أكبرُ من الهامش بيقين.
MIN_LEAD_MINUTES = 30

# **وأقصى أفق**: حجزٌ لبعد ثلاثة أشهرٍ يحمل تسعيرةً وسائقين لا نعرف شيئاً عنهم،
# ويجعل الجدولَ ذاكرةً لوعودٍ لا أحدَ يذكرها. شهرٌ يكفي كلَّ حاجةٍ حقيقية.
MAX_HORIZON_DAYS = 30

# سقفُ ما ينتظر لكل راكب — حارسٌ ضد ملءِ الجدول بحجوزٍ لا تُنفَّذ، لا سياسةُ عمل
MAX_OPEN_PER_RIDER = 10


class BookingsUnavailable(FeatureDisabled):
    code = "scheduled_rides_unavailable"
    message = "الرحلات المجدولة غير مفعّلة في بلدك"


class BookingNotAllowed(Conflict):
    code = "booking_not_allowed"
    message = "لا يمكن تنفيذ هذا الطلب على الحجز"


def _now() -> datetime:
    return datetime.now(UTC)


async def offered_in(session: AsyncSession, user: User) -> bool:
    return await settings_service.is_feature_enabled(
        session, user.country_code, FeatureKey.SCHEDULED_RIDES_ENABLED
    )


# ------------------------------------------------------------------ القراءة


async def list_for_rider(
    session: AsyncSession, rider_id: uuid.UUID, *, limit: int = 50
) -> list[RideBooking]:
    """حجوزاتُه — الأحدثُ موعداً أولاً، والمنتظرُ قبل المنتهي."""
    rows = await session.scalars(
        select(RideBooking)
        .where(RideBooking.rider_id == rider_id)
        .order_by(
            (RideBooking.status != BookingStatus.PENDING),
            RideBooking.scheduled_at,
        )
        .limit(limit)
    )
    return list(rows)


async def get_for_rider(
    session: AsyncSession, booking_id: uuid.UUID, rider_id: uuid.UUID
) -> RideBooking:
    row = await session.scalar(
        select(RideBooking).where(
            RideBooking.id == booking_id, RideBooking.rider_id == rider_id
        )
    )
    if row is None:
        raise NotFound("الحجز غير موجود")
    return row


async def _open_count(session: AsyncSession, rider_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(RideBooking)
            .where(
                RideBooking.rider_id == rider_id,
                RideBooking.status == BookingStatus.PENDING,
            )
        )
        or 0
    )


# ------------------------------------------------------------------ الإنشاء


async def create(
    session: AsyncSession,
    *,
    rider: User,
    pickup: Coordinates,
    dropoff: Coordinates,
    scheduled_at: datetime,
    vehicle_category: VehicleCategory,
    pickup_address: str | None = None,
    dropoff_address: str | None = None,
    gender_preference: GenderPreference | None = None,
    payment_method_hint: PaymentMethod | None = None,
) -> RideBooking:
    """يكتب حجزاً واحداً. الـcommit للراوتر.

    **ولا يُفحص «رحلةٌ نشطةٌ واحدة» هنا**: الحجزُ ليس رحلةً، ومن هو في رحلةٍ الآن
    له أن يحجز للغد — وهذا هو نصفُ سببِ الجدول المستقل. والفحصُ يقع لحظةَ
    التنفيذ حيث يعني شيئاً.
    """
    if not await offered_in(session, rider):
        raise BookingsUnavailable()

    if scheduled_at.tzinfo is None:
        raise InvalidInput("موعد الحجز يحتاج منطقةً زمنية")

    now = _now()
    if scheduled_at < now + timedelta(minutes=MIN_LEAD_MINUTES):
        raise InvalidInput(
            f"أقرب حجزٍ بعد {MIN_LEAD_MINUTES} دقيقة — وما هو أقرب فاطلبه الآن"
        )
    if scheduled_at > now + timedelta(days=MAX_HORIZON_DAYS):
        raise InvalidInput(f"أقصى حجزٍ بعد {MAX_HORIZON_DAYS} يوماً")

    if await _open_count(session, rider.id) >= MAX_OPEN_PER_RIDER:
        raise BookingNotAllowed(
            f"لديك {MAX_OPEN_PER_RIDER} حجوزٍ تنتظر — ألغِ واحداً قبل إضافة آخر"
        )

    # **تفضيلُ الجنس يُفحص عند الحجز أيضاً** لا عند التنفيذ وحده: وعدٌ بكبتنةٍ
    # في سوقٍ لا خدمةَ نسائيةً فيه وعدٌ يُخلف بعد أسبوع، والرفضُ الآن مفهوم
    preference = (
        rider.ride_gender_preference if gender_preference is None else gender_preference
    )
    if preference is not GenderPreference.ANY and not await (
        settings_service.is_feature_enabled(
            session, rider.country_code, FeatureKey.WOMEN_SERVICE_ENABLED
        )
    ):
        raise WomenServiceUnavailable()

    # تقديرٌ للعرض — **وفشلُه لا يمنع الحجز**: الأجرةُ تُحسب عند التنفيذ، وحجزٌ
    # يُرفض لأن مزوّدَ المسارات تعثّر لحظتَها رفضٌ لا سببَ له عند صاحبه
    # تقديرٌ للعرض — **وفشلُ المزوّد لا يمنع الحجز**: الأجرةُ تُحسب عند التنفيذ،
    # وحجزٌ يُرفض لأن مزوّدَ المسارات تعثّر لحظتَها رفضٌ لا سببَ له عند صاحبه.
    #
    # **والالتقاطُ ضيّقٌ لا `Exception` عريضة**: العريضةُ ابتلعت خطأً في اسم حقلٍ
    # في أول تشغيل (`estimated_fare` مكانَ `fare`) فخُزّن `NULL` بلا أن يقول
    # شيءٌ شيئاً — وهو بعينه العطبُ الذي تحرسه قاعدةُ «لا تبتلع ما ليس عطبَ مزوّد».
    estimate: Decimal | None = None
    try:
        quote = await pricing.estimate(
            session,
            country_code=rider.country_code,
            vehicle_category=vehicle_category,
            pickup=pickup,
            dropoff=dropoff,
        )
        estimate = quote.fare
    except (AppError, HTTPError) as caught:
        logger.warning("تعذّر تقدير أجرة حجزٍ لـ%s: %s", rider.id, caught)

    booking = RideBooking(
        rider_id=rider.id,
        country_code=rider.country_code,
        pickup_point=make_point(pickup.lat, pickup.lng),
        pickup_address=pickup_address,
        dropoff_point=make_point(dropoff.lat, dropoff.lng),
        dropoff_address=dropoff_address,
        vehicle_category=vehicle_category,
        gender_preference=preference,
        payment_method_hint=payment_method_hint,
        scheduled_at=scheduled_at,
        status=BookingStatus.PENDING,
        estimated_fare_at_booking=estimate,
    )
    session.add(booking)
    await session.flush()
    await session.refresh(booking)
    return booking


async def cancel(
    session: AsyncSession, *, booking: RideBooking, actor: User
) -> RideBooking:
    """إلغاءُ حجزٍ لم يُنفَّذ — **مجاناً بلا استثناء**.

    وليس هذا كرماً بل نتيجة: رسمُ الإلغاء تعويضُ كبتنٍ تحرّك (القسم 5)، ولا
    كبتنَ بعد. ومن سُلّم حجزُه إلى التوزيع صار له رحلةٌ تُلغى من بابها وبرسمها —
    فلا قاعدةَ مالٍ جديدةٌ هنا.
    """
    locked = await session.scalar(
        select(RideBooking)
        .where(RideBooking.id == booking.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert locked is not None
    if locked.status is not BookingStatus.PENDING:
        raise BookingNotAllowed(
            "هذا الحجز لم يعد منتظراً — إن كانت له رحلةٌ فألغِها من شاشتها"
        )

    locked.status = BookingStatus.CANCELLED
    locked.cancelled_at = _now()
    locked.cancelled_by = actor.id
    # **قراءةٌ جديدة بعد التعديل**: `pickup_lat`/`lng` أعمدةٌ محسوبةٌ في القاعدة
    # وكلُّ UPDATE يُبطلها، فتسلسلُ الصفِّ بعدها يحاول تحميلاً كسولاً خارج سياق
    # async ويرفع `MissingGreenlet` — نفسُ `rides._flush_and_reload` حرفياً
    return await _flush_and_reload(session, locked)


# ------------------------------------------------------------------ التنفيذ


async def _flush_and_reload(
    session: AsyncSession, booking: RideBooking
) -> RideBooking:
    """يثبّت التعديل ثم يعيد قراءة الصف (انظر `rides._flush_and_reload`)."""
    await session.flush()
    row = await session.scalar(
        select(RideBooking).where(RideBooking.id == booking.id)
    )
    assert row is not None
    return row


async def due_ids(session: AsyncSession, *, limit: int = 100) -> list[uuid.UUID]:
    """حجوزٌ حلَّ وقتُ تسليمها للتوزيع — الأقدمُ موعداً أولاً.

    **بلا قفلٍ هنا**: القفلُ يخصّ التنفيذَ نفسَه لا اختيارَ المرشَّحين، وقفلُ
    مئةِ صفٍّ في معاملةٍ واحدة يجعل دورةً تعطّل غيرها (نفسُ شكل `referrals`).
    """
    horizon = _now() + timedelta(minutes=LEAD_MINUTES)
    rows = await session.scalars(
        select(RideBooking.id)
        .where(
            RideBooking.status == BookingStatus.PENDING,
            RideBooking.scheduled_at <= horizon,
        )
        .order_by(RideBooking.scheduled_at)
        .limit(limit)
    )
    return list(rows)


async def _locked(session: AsyncSession, booking_id: uuid.UUID) -> RideBooking:
    """يقرأ الحجزَ **مقفولاً** قبل فحص حالته.

    وبغير القفل تمرّ دورتان متزامنتان على صفٍّ واحد فتقرآن `pending` كلتاهما،
    فتُنشئان **رحلتين** لحجزٍ واحد — أو تفشل الثانيةُ على
    `uq_rides_active_rider` باستثناءٍ يُسقط بقيةَ الدورة. والاختبارُ يفشل بحذفه.
    """
    row = await session.scalar(
        select(RideBooking)
        .where(RideBooking.id == booking_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:  # pragma: no cover - صفٌّ محذوف
        raise NotFound("الحجز غير موجود")
    return row


async def execute(
    session: AsyncSession, redis: Redis, booking_id: uuid.UUID
) -> Ride | None:
    """يُنشئ رحلةَ الحجز ويُسلّمها للتوزيع. يعيد `None` إن لم تُنشأ.

    **ولا تُنشأ الرحلةُ هنا بيد**: `rides.request_ride` هو البابُ، فتُفحص كلُّ
    قواعده وتُجمَّد عمولتُه ويُطبَّق تفضيلُه. والتوزيعُ يُطلق من المستدعي **بعد
    الـcommit** كما في الراوتر: مهمةُ التوزيع تقرأ الرحلةَ من جلسةٍ أخرى.
    """
    booking = await _locked(session, booking_id)
    if booking.status is not BookingStatus.PENDING:
        return None

    rider = await session.get(User, booking.rider_id)
    assert rider is not None

    # **الخدمةُ قد تُطفأ بين الحجز والتنفيذ**: لا تُرفض الرحلةُ حينها — من رتّب
    # موعدَه لا يُترك بلا سيارة — بل تُنشأ بلا تفضيلٍ **ويُبلَّغ صاحبُها**.
    # والمخزَّنُ لا يُمحى: هو اختيارُها ويعود إن عادت الخدمة
    preference = booking.gender_preference
    downgraded = False
    if preference is not GenderPreference.ANY and not await (
        settings_service.is_feature_enabled(
            session, rider.country_code, FeatureKey.WOMEN_SERVICE_ENABLED
        )
    ):
        preference = GenderPreference.ANY
        downgraded = True

    try:
        ride = await rides_service.request_ride(
            session,
            rider=rider,
            pickup=Coordinates(lat=booking.pickup_lat, lng=booking.pickup_lng),
            dropoff=Coordinates(lat=booking.dropoff_lat, lng=booking.dropoff_lng),
            vehicle_category=booking.vehicle_category,
            pickup_address=booking.pickup_address,
            dropoff_address=booking.dropoff_address,
            gender_preference=preference,
        )
    except RideAlreadyActive:
        # **صاحبُه في رحلةٍ الآن**: الفهرسُ يمنع الثانية، فيصير الحجزُ `missed`
        # بإشعار — لا يُحذف بصمتٍ ولا يُترك معلّقاً يُنفَّذ بعد ساعة
        booking.status = BookingStatus.MISSED
        booking.notified_at = _now()
        await session.flush()
        await session.commit()
        await _tell(
            publish_booking_missed(
                session, redis, rider_id=booking.rider_id, booking_id=booking.id
            )
        )
        return None

    booking.ride_id = ride.id
    booking.status = BookingStatus.DISPATCHED
    await _flush_and_reload(session, booking)

    if downgraded:
        booking.notified_at = _now()
        await session.flush()
        await session.commit()
        await _tell(
            publish_booking_preference_dropped(
                session,
                redis,
                rider_id=booking.rider_id,
                booking_id=booking.id,
                ride_id=ride.id,
            )
        )
    return ride


async def report_failures(session: AsyncSession, redis: Redis) -> int:
    """يُبلّغ عن حجوزٍ سُلّمت للتوزيع فلم تجد كبتناً.

    **ولماذا هنا لا في الموزّع؟** الموزّعُ لا يعرف الحجوزَ، وتعليمُه إياها يجعل
    مسارَ الرحلة الفورية يحمل شرطاً لا يخصّه. وهو يُخطر صاحبَ الرحلة أصلاً — لكن
    بنصِّ رحلةٍ فورية: «لم نجد كبتناً» لمن هو أمام الشاشة. ومن حجز ونام يحتاج
    نصّاً يقول **أيُّ حجزٍ** فشل ومتى كان موعدُه.

    و`notified_at` يمنع التكرار في كل دورة (عمودٌ لا مفتاحُ Redis: الصفُّ قائم).
    """
    rows = (
        await session.execute(
            select(RideBooking, Ride)
            .join(Ride, Ride.id == RideBooking.ride_id)
            .where(
                RideBooking.status == BookingStatus.DISPATCHED,
                RideBooking.notified_at.is_(None),
                Ride.status == RideStatus.NO_DRIVER_FOUND,
            )
            .limit(50)
        )
    ).all()

    told = 0
    for booking, _ride in rows:
        locked = await _locked(session, booking.id)
        if locked.notified_at is not None:
            await session.rollback()
            continue
        locked.notified_at = _now()
        await session.commit()
        await _tell(
            publish_booking_no_driver(
                session,
                redis,
                rider_id=locked.rider_id,
                booking_id=locked.id,
                ride_id=locked.ride_id,
            )
        )
        told += 1
    return told


async def _tell(coroutine) -> None:
    """يُشغّل إشعاراً **بعد** الـcommit ولا يُسقط ما استدعاه إن تعثّر.

    والإشعاراتُ نفسُها في `services/notifications.py` كبقية إشعارات المشروع: بابٌ
    واحدٌ يكتب صفَّ الصندوق ثم يُرسل Push، فلا قناةٌ تُضاف لحدثٍ وتُنسى لآخر.
    """
    try:
        await coroutine
    except Exception:  # noqa: BLE001 - إشعارٌ متعثّر لا يُبطل ما جرى
        logger.warning("تعذّر إبلاغ صاحب الحجز", exc_info=True)


async def run_due(session: AsyncSession, redis: Redis) -> dict[str, int]:
    """دورةٌ واحدة: تنفيذُ ما حلَّ، ثم الإبلاغُ عن فشلٍ وقع.

    **وكلُّ حجزٍ في معاملته**، والتوزيعُ يُطلق **بعد الـcommit** — فمهمةُ
    التوزيع تقرأ الرحلةَ من جلسةٍ أخرى ولا ترى ما لم يُثبَّت.
    """
    tally = {"dispatched": 0, "missed": 0, "failed": 0}
    for booking_id in await due_ids(session):
        try:
            ride = await execute(session, redis, booking_id)
            if ride is None:
                tally["missed"] += 1
                continue
            await session.commit()
            dispatch.start(ride.id)
            tally["dispatched"] += 1
        except Exception:  # noqa: BLE001 - حجزٌ متعثّر لا يُسقط الدورة
            await session.rollback()
            tally["failed"] += 1
            logger.exception("تعذّر تنفيذ الحجز %s", booking_id)

    tally["reported"] = await report_failures(session, redis)
    return tally
