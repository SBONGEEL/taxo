from __future__ import annotations

from typing import Annotated

import uuid
from decimal import Decimal

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep, RiderUser
from app.core import storage
from app.core.exceptions import NotFound, PermissionDenied
from app.models.driver import Driver
from app.models.enums import CancellationChargeStatus, RideStatus, UserRole
from app.models.ride import Ride
from app.schemas.rating import RatingCreate, RatingOut
from app.schemas.promo import PromoPreviewOut, PromoValidateRequest
from app.schemas.tip import TipCreate, TipOptionsOut, TipOut
from app.schemas.ride import (
    CoordinatesIn,
    RideListItem,
    RideCancelRequest,
    RideCreateRequest,
    RideEstimateOut,
    RideEstimateRequest,
    RideOut,
    RouteLineOut,
)
from app.services import cancellation
from app.services import (
    dispatch,
    documents as documents_service,
    notifications,
    pricing,
    promo as promo_service,
    ratings as ratings_service,
    ride_log,
    rides as rides_service,
    route,
    pauses,
    route_line,
    sharing,
    tips as tips_service,
    tracking,
)
from app.services.directions import Coordinates
from app.ws import events
from app.core.exceptions import AmbiguousRole

router = APIRouter(prefix="/rides", tags=["rides"])


def _coords(value: CoordinatesIn) -> Coordinates:
    return Coordinates(lat=value.lat, lng=value.lng)


def _to_out(ride: Ride) -> RideOut:
    return RideOut.from_ride(ride)


async def _assigned_ride(
    session: AsyncSession, ride_id: uuid.UUID, driver: Driver
) -> Ride:
    """رحلة هذا الكبتن هو المُسند إليها — وإلا فلا شأن له بها."""
    ride = await rides_service.get_ride(session, ride_id)
    if ride.driver_id != driver.id:
        raise PermissionDenied("هذه الرحلة ليست مُسندة إليك")
    return ride


# ------------------------------------------------------------------ التسعير


@router.post("/estimate", response_model=RideEstimateOut)
async def estimate_ride(
    payload: RideEstimateRequest, rider: RiderUser, session: DbSession
) -> RideEstimateOut:
    """سعر مقدّر قبل تأكيد الطلب — بلا أي كتابة في القاعدة."""
    quote = await pricing.estimate(
        session,
        country_code=rider.country_code,
        vehicle_category=payload.vehicle_category,
        pickup=_coords(payload.pickup),
        dropoff=_coords(payload.dropoff),
        stops=[_coords(stop) for stop in payload.stops],
    )
    shared = await sharing.preview(
        session, fare=quote.fare, country=rider.country_code
    )
    return RideEstimateOut(
        share_discount=shared[0] if shared else None,
        share_fare=shared[1] if shared else None,
        country_code=quote.country_code,
        vehicle_category=quote.vehicle_category,
        currency=quote.currency,
        distance_km=quote.route.distance_km,
        duration_min=quote.route.duration_min,
        estimated_fare=quote.fare,
        minimum_fare_applied=quote.minimum_fare_applied,
    )


# -------------------------------------------------------------------- الطلب


@router.post("", response_model=RideOut, status_code=status.HTTP_201_CREATED)
async def request_ride(
    payload: RideCreateRequest, rider: RiderUser, session: DbSession
) -> RideOut:
    """يُنشئ الرحلة ويبدأ البحث عن كبتن فوراً (SPEC القسم 5).

    ترجع الرحلة بحالة `requested`؛ انتقالها إلى `searching` ثم إسنادها يصل
    الراكبَ عبر WebSocket، ويمكن استرجاعه في أي وقت من `GET /rides/me/active`.
    """
    ride = await rides_service.request_ride(
        session,
        rider=rider,
        pickup=_coords(payload.pickup),
        dropoff=_coords(payload.dropoff),
        vehicle_category=payload.vehicle_category,
        pickup_address=payload.pickup_address,
        dropoff_address=payload.dropoff_address,
        gender_preference=payload.gender_preference,
        promo_code=payload.promo_code,
        share=payload.share,
        share_gender_confirmed=payload.share_gender_confirmed,
        stops=[
            rides_service.StopRequest(
                lat=stop.lat, lng=stop.lng, address=stop.address
            )
            for stop in payload.stops
        ],
    )
    await session.commit()
    # قراءة جديدة: خطا العرض والطول محسوبان في القاعدة ولا يعودان مع INSERT
    body = _to_out(await rides_service.get_ride(session, ride.id))
    # التوزيع بعد الـ commit وحده (مهمته تقرأ الرحلة من جلسة أخرى) وبعد بناء
    # الرد، فلا تسبق `searching` الجوابَ الذي يقول `requested`
    dispatch.start(ride.id)
    return body


# ------------------------------------------------------------------ القراءة



# **إعلانُ الجانب** (SPEC §22): هذان المساران يخدمهما التطبيقان معاً
# (`CurrentUser`)، فمن حمل الدورين لا يقول دورُه أيَّ رحلاتٍ يعني. واختياريٌّ
# عمداً: صاحبُ دورٍ واحدٍ لا يُطالَب بشيء، ولا يُخرج هذا عميلاً قائماً.
RideSide = Annotated[
    UserRole | None,
    Query(alias="side", description="أيُّ جانبٍ من الرحلات — لمن يحمل الدورين"),
]


@router.get("/me", response_model=list[RideListItem])
async def list_my_rides(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    side: RideSide = None,
) -> list[RideListItem]:
    """سجل الرحلات: للراكب رحلاته، وللكبتن ما أُسند إليه.

    **ومعها ملخّصُ دفعها في استعلامٍ ثانٍ لا في نداءٍ لكل صف** (بند 19):
    صفحةٌ من عشرين رحلة لا تصير عشرين نداءً — نفس ما يفعله سجلُّ اللوحة.
    """
    rides = await rides_service.list_rides_for_user(
        session, user, limit=limit, offset=offset, declared=side
    )
    summaries = await ride_log.payment_summaries(session, [ride.id for ride in rides])
    return [
        RideListItem(
            ride=_to_out(ride),
            has_open_dispute=summary.has_open_dispute,
            payment_methods=summary.methods,
            paid_amount=summary.paid_amount,
            settlement=ride_log.settlement_of(ride, summary),
        )
        for ride, summary in (
            (ride, summaries.get(ride.id, ride_log.EMPTY_SUMMARY)) for ride in rides
        )
    ]


@router.get("/me/active", response_model=RideOut | None)
async def get_my_active_ride(
    user: CurrentUser, session: DbSession, side: RideSide = None
) -> RideOut | None:
    """آخر حالة للرحلة الجارية — عليها يعتمد الاسترجاع بعد انقطاع الاتصال."""
    ride = await rides_service.active_ride_for_user(session, user, declared=side)
    return _to_out(ride) if ride is not None else None


@router.get("/{ride_id}", response_model=RideOut)
async def get_ride(ride_id: uuid.UUID, user: CurrentUser, session: DbSession) -> RideOut:
    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    return _to_out(ride)


@router.get("/{ride_id}/route-line", response_model=RouteLineOut)
async def get_route_line(
    ride_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> RouteLineOut:
    """شكلُ المسار على الطرق — للطرفين بعد القبول (البند ٨).

    **الملكيةُ أولاً**: `get_ride_for_user` هو نفسُ بابِ بقية قراءات الرحلة، فلا
    يُقرأ مسارُ رحلةِ غيرك (القسم 14). و**يُجلب هنا إن لم يكن مكتوباً**: القبول
    يطلبه، وهذا يغطّي قبولاً وقع ونداءُ Mapbox فيه سقط — بلا أن يُعاد الطلبُ
    لمن كُتب له.

    ومسارٌ فارغٌ جوابٌ صحيح (`points: []`): التطبيقُ يرسم الدبوسين وحدهما.
    """
    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    points = await route_line.ensure(session, ride.id)
    await session.commit()
    return RouteLineOut(points=points or [])


# -------------------------------------------------------------- حالات الرحلة


@router.get("/{ride_id}/driver/photo")
async def get_driver_photo(
    ride_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> FileResponse:
    """صورةُ كبتن هذه الرحلة — **لطرفَيها وحدهما** (البند ٥٢).

    **ومنفذٌ ثانٍ أضيقُ من منفذ المستندات لا توسيعٌ له**: `document_response`
    يفحص ملكيةَ الكبتن لمستنده ويردّ `private, no-store` — وهو الصواب لوثيقة
    هوية، ولا يصلح لصورةٍ **يراها الراكب**. والبديلُ المرفوض مسارٌ يأخذ
    `driver_id` فيعرض وجوهَ الكباتن لمن يعدّ المعرّفات؛ فالمفتاحُ هنا
    **الرحلةُ** لا الكبتن، و`get_ride_for_user` هو الحارسُ القائم الذي يقول
    «أنت طرفٌ فيها».

    **ولا تُردّ إلا مقبولةً**: صورةٌ تنتظر المراجعة قد تكون صورةَ شخصٍ آخر أو
    صورةً مسيئة — وعرضُها قبل أن يراها مشرفٌ يُبطل المراجعةَ نفسَها. و404
    حينها هو الجواب الصحيح: التطبيقُ يرسم الحرفَ الأول، وهو ما يرسمه للمُعفاة
    أيضاً — **والحالان متشابهان في الشاشة بقصد**، فغيابُ الصورة لا يُعلن أنها
    امرأة.

    **و`no-store` تبقى**: الصورةُ لطرفِ رحلةٍ لا لأيِّ قارئ، وتخزينُها في
    وسيطٍ مشترك يجعلها تُقرأ من غير مسارها.
    """
    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    if ride.driver_id is None:
        raise NotFound("لا كبتن لهذه الرحلة بعد")

    photo = await documents_service.approved_photo(session, ride.driver_id)
    if photo is None:
        raise NotFound("لا صورة لهذا الكبتن")

    path = storage.resolve(photo.file_path)
    return FileResponse(
        path,
        media_type=photo.content_type,
        headers={
            "Content-Disposition": f'inline; filename="driver{path.suffix}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{ride_id}/accept", response_model=RideOut)
async def accept_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    """قبول الطلب المعروض — لا يقبله غير المعروض عليه (SPEC القسم 5.3)."""
    ride = await rides_service.accept_ride(session, redis, ride_id, driver)
    await session.commit()

    # إيقاظ مهمة التوزيع لتتوقف، ثم إعلام الطرفين — كلاهما بعد الـ commit
    await dispatch.notify_accepted(redis, ride_id)
    await dispatch.release_offer(redis, ride_id, driver.id)
    await notifications.publish_ride_event(
        session, redis, ride, events.RideEvent.DRIVER_ASSIGNED
    )

    # **الجوابُ يُبنى قبل أيِّ commit ثانٍ**: `pickup_lat`/`dropoff_lat` خصائصُ
    # محسوبةٌ في القاعدة (`column_property`)، والـcommit يُبطلها — فقراءتُها
    # بعده تُطلق تحميلاً كسولاً خارج السياق غير المتزامن (`MissingGreenlet`).
    # وهي المصيدةُ التي من أجلها تنتهي كلُّ دالةٍ مُعدِّلةٍ بـ`_flush_and_reload`
    out = _to_out(ride)

    # **وشكلُ المسار يُطلب مرةً هنا** (البند ٨، قرارُ المالك): بعد الـcommit فلا
    # يُحمل قفلُ صفِّ الرحلة عبر نداء Mapbox، وقبل أن يفتح أيُّ طرفٍ خريطته.
    # وفشلُه لا يمسّ القبول — `ensure` تبتلع خطأ المزوّد وتعيد `None`
    if await route_line.ensure(session, ride.id) is not None:
        await session.commit()
    return out


@router.post("/{ride_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> Response:
    """رفض الطلب أو تجاهله قبل انتهاء العدّاد (SPEC القسم 12.3).

    لا يمس حالة الرحلة: ينهي دور هذا الكبتن فقط فينتقل التوزيع للتالي بلا
    انتظار بقية المهلة.
    """
    await dispatch.require_offer(redis, ride_id, driver.id)
    await dispatch.notify_declined(redis, ride_id, driver.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{ride_id}/arrive", response_model=RideOut)
async def mark_arrived(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    ride = await rides_service.mark_arrived(
        session, await _assigned_ride(session, ride_id, driver)
    )
    await session.commit()
    await notifications.publish_ride_event(
        session, redis, ride, events.RideEvent.DRIVER_ARRIVED
    )
    return _to_out(ride)


@router.post("/{ride_id}/start", response_model=RideOut)
async def start_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    ride = await rides_service.start_ride(
        session, await _assigned_ride(session, ride_id, driver)
    )
    await session.commit()
    # من هنا يُراقَب اتصال الكبتن حتى نهاية الرحلة (SPEC القسم 5)
    tracking.start(ride.id)
    # ومن هنا يبدأ تسجيل المسار الفعلي: قبل `in_progress` الكبتن في طريقه
    # للراكب، وذاك ليس من مسار الرحلة (SPEC القسم 5.7)
    await route.begin(redis, driver_id=driver.id, ride_id=ride.id)
    await notifications.publish_ride_event(
        session, redis, ride, events.RideEvent.RIDE_STARTED
    )
    return _to_out(ride)


@router.post("/{ride_id}/stops/{stop_id}/arrive", response_model=RideOut)
async def arrive_at_stop(
    ride_id: uuid.UUID,
    stop_id: uuid.UUID,
    driver: CurrentDriver,
    session: DbSession,
    redis: RedisDep,
) -> RideOut:
    """وصل الكبتنُ محطةً وسيطة — **من هنا يبدأ ختمُ الانتظار** (القسم 5.10).

    والراوترُ يُحلّ من له الحق ولا يكتب حالة: الانتقالُ والقفلُ في الخدمة.
    """
    ride, _ = await rides_service.arrive_at_stop(
        session, await _assigned_ride(session, ride_id, driver), stop_id
    )
    await session.commit()
    await notifications.publish_ride_event(
        session, redis, ride, events.RideEvent.STOP_REACHED
    )
    return _to_out(ride)


@router.post("/{ride_id}/stops/{stop_id}/resume", response_model=RideOut)
async def resume_from_stop(
    ride_id: uuid.UUID,
    stop_id: uuid.UUID,
    driver: CurrentDriver,
    session: DbSession,
    redis: RedisDep,
) -> RideOut:
    """يستأنف الكبتنُ السير — يُقفل عدّادُ الانتظار وتبدأ الساقُ التالية."""
    ride, _ = await rides_service.resume_from_stop(
        session, await _assigned_ride(session, ride_id, driver), stop_id
    )
    await session.commit()
    await notifications.publish_ride_event(
        session, redis, ride, events.RideEvent.STOP_RESUMED
    )
    return _to_out(ride)


@router.post("/{ride_id}/complete", response_model=RideOut)
async def complete_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    """الإنهاء يثبّت `final_fare` على المسافة الفعلية إن انحرفت (القسم 5.7).

    إيقاف التسجيل **قبل** إنهاء الرحلة لا بعده: بثّةٌ تصل بين الحسابِ
    والإيقاف تضيف نقطةً لمسارٍ حُسبت مسافته بالفعل.
    """
    await route.end(redis, driver_id=driver.id)
    ride = await rides_service.complete_ride(
        session, await _assigned_ride(session, ride_id, driver), driver
    )
    await session.commit()
    await tracking.stop(ride.id)
    await notifications.publish_ride_event(
        session, redis, ride, events.RideEvent.RIDE_COMPLETED
    )
    return _to_out(ride)



def _cancelling_role(user: User, ride: Ride) -> UserRole:
    """بأيِّ صفةٍ ألغى — **والرحلةُ نفسُها تقوله، فلا إعلانَ يُطلب** (§22).

    وهي تقرّر مالاً: الحالةُ تصير `cancelled_by_rider` أو `cancelled_by_driver`،
    وعليها يقوم رسمُ الإلغاء وعدُّ المشرف.

    **وهذا أنقى صورةٍ لقاعدة «سياقُ الفعل»**: الصفُّ يحمل راكبَه وكبتنَه بالاسم،
    فالسؤالُ «أيُّهما هذا المستخدم؟» جوابُه في الرحلة لا في أدواره — ولا يُسأل
    عنه عميلٌ أصلاً. وحسابٌ بدورين ألغى رحلةً هو راكبُها **راكبٌ فيها** مهما
    ملك، ولو كان كبتناً في رحلةٍ أخرى.

    ويبقى الارتدادُ المسمّى لما لا تجيب عنه الرحلة: من ليس طرفاً فيها أصلاً —
    وهو ما لا يبلغ هذا السطرَ لأن `get_ride_for_user` يردّه قبله، والحارسُ هنا
    لئلا يصير ذلك اعتماداً على ترتيبِ سطرين.
    """
    if ride.rider_id == user.id:
        return UserRole.RIDER
    if ride.driver is not None and ride.driver.user_id == user.id:
        return UserRole.DRIVER
    raise AmbiguousRole(
        "cancelling_side_undecided",
        "لم يتبيّن بأيِّ صفةٍ يُسجَّل هذا الإلغاء",
    )


@router.post("/{ride_id}/cancel", response_model=RideOut)
async def cancel_ride(
    ride_id: uuid.UUID,
    payload: RideCancelRequest,
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
) -> RideOut:
    """يلغيها الراكب صاحبها أو الكبتن المُسند إليها — لا أحد سواهما.

    الإدارة تقرأ الرحلات لكنها لا تلغيها من هنا؛ الملكية نفسها يفحصها
    `get_ride_for_user`.
    """
    if not user.has_role(UserRole.RIDER, UserRole.DRIVER):
        raise PermissionDenied()

    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    was_searching = ride.status == RideStatus.SEARCHING

    ride = await rides_service.cancel_ride(
        session,
        ride,
        by_role=_cancelling_role(user, ride),
        reason=payload.reason,
        reason_code=payload.reason_code,
    )
    # **ورسمُ الإلغاء يُحصَّل هنا لا يُعرض وحده** (`design/CANCELLATION-FEE.md`):
    # كان الرقمُ يُجمَّد على الرحلة ولا يُكتب له صفٌّ ولا قيد، فيقرأ الراكبُ
    # ديناً بلا بابٍ يدفع منه، ولا يصل من تحرّك شيء. **وفي معاملة الإلغاء
    # نفسِها** — رسمٌ يُكتب بعد إيداعٍ منفصل يضيع بأولِ انقطاع
    charge = await cancellation.charge_for(
        session, redis, ride=ride, fee=ride.cancellation_fee or Decimal("0.000")
    )

    # **ومن بقي من مجموعة المشاركة** (12-ي): يُرفع سعرُه إلى المنفرد قبل
    # الانطلاق ولا يُرفع بعده — والقرارُ كلُّه في `sharing`، وهنا نداؤه.
    # وقبل الإيداع لأنه تعديلُ صفٍّ، والإشعارُ بعده كبقية الأحداث
    aftermath = await sharing.on_member_cancelled(session, ride)
    await session.commit()

    if aftermath is not None:
        await notifications.publish_share_partner_cancelled(
            session,
            redis,
            rider_id=aftermath.rider_id,
            ride_id=aftermath.ride_id,
            price_kept=aftermath.price_kept,
        )

    # **والكبتنُ يُخبَر بحاله لا بوقوعه فقط** (القسم ٨): «وصلك الآن» غيرُ
    # «معلّقٌ حتى يدفع» — والثاني يجعله يفتّش عن مالٍ في رصيده ليس فيه
    if charge is not None:
        await notifications.publish_cancellation_compensation(
            session,
            redis,
            driver_id=charge.beneficiary_driver_id,
            ride_id=ride.id,
            amount=charge.amount,
            currency=charge.currency,
            settled=charge.status is CancellationChargeStatus.SETTLED,
        )

    if was_searching:
        # إلغاء أثناء البحث: تتوقف المهمة وتُطوى البطاقة من شاشة المعروض عليه
        await dispatch.stop(ride_id)
        await dispatch.withdraw_offer(session, redis, ride_id)
    if ride.driver_id is not None:
        await route.end(redis, driver_id=ride.driver_id)
    await tracking.stop(ride_id)
    await notifications.publish_ride_event(
        session, redis, ride, events.RideEvent.RIDE_CANCELLED
    )
    return _to_out(ride)


# ------------------------------------------------------------------ التقييم


@router.get("/{ride_id}/ratings", response_model=list[RatingOut])
async def list_ride_ratings(
    ride_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> list[RatingOut]:
    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    entries = await ratings_service.list_for_ride(session, ride.id)
    return [RatingOut.model_validate(entry) for entry in entries]


@router.post(
    "/{ride_id}/ratings", response_model=RatingOut, status_code=status.HTTP_201_CREATED
)
async def rate_ride(
    ride_id: uuid.UUID,
    payload: RatingCreate,
    user: CurrentUser,
    session: DbSession,
) -> RatingOut:
    """تقييم متبادل بعد `completed` — مسار واحد لكلا الطرفين (SPEC القسم 5.9).

    من يقيّم مَن يُشتق من الرحلة نفسها لا من دور الحساب: كبتنٌ آخر دورُه
    `driver` ليس طرفاً في هذه الرحلة.
    """
    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    rating = await ratings_service.rate(
        session, ride=ride, rater=user, stars=payload.stars, comment=payload.comment
    )
    await session.commit()
    return RatingOut.model_validate(rating)


# ----------------------------------------------------- الكوبون (12-ز)


@router.post("/promo/validate", response_model=PromoPreviewOut)
async def validate_promo(
    payload: PromoValidateRequest, rider: RiderUser, session: DbSession
) -> PromoPreviewOut:
    """زرُّ «تطبيق» في ورقة التأكيد — **تحقّقٌ لا يستهلك شيئاً**.

    ويرفع نفسَ أخطاء الطلب الحقيقي (رمزٌ خاطئ، عرضٌ نفد، استعملتَه سابقاً): زرٌّ
    يقول «مقبول» ثم يرتدّ عند الطلب يُعلّم الراكبَ ألّا يثق بالشاشة.

    **والمسارُ تحت `/rides` لأن الرمزَ يخصّ رحلةً لم توجد بعد**، والخصمُ يُحسب
    على تقديرها. و`RiderUser`: الكبتنُ لا يطبّق كوبوناً على راكب.
    """
    promo, discount = await promo_service.preview(
        session,
        code=payload.code,
        country=payload.country_code,
        rider=rider,
        fare=payload.fare,
    )
    return PromoPreviewOut(
        code=promo.code,
        discount_type=promo.discount_type,
        discount=discount,
        fare_after=pricing.round_money(payload.fare - discount),
        currency=currency_for_country(payload.country_code).value,
    )


# ----------------------------------------------------- البقشيش (12-و)


@router.get("/{ride_id}/tip", response_model=TipOptionsOut)
async def tip_options(
    ride_id: uuid.UUID, user: RiderUser, session: DbSession
) -> TipOptionsOut:
    """ما ترسمه شاشةُ التقييم — **والخلفيةُ تقرّر أن تُعرض أصلاً**.

    ثلاثةُ شروطٍ تجتمع (مفتاحٌ، محفظةٌ مفعّلة، مبالغُ مضبوطة)، ولا يعرفها
    التطبيقُ من عنده. و`RiderUser` لأن البقشيشَ يُعطى ولا يُطلب: الكبتنُ لا
    يسأل عن بقشيشِ رحلةٍ ولا يراه إلا في أرباحه.
    """
    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    country = ride.country_code
    given = await tips_service.for_ride(session, ride.id)
    row = await tips_service.settings_for(session, country)
    offered = await tips_service.offered_in(session, country)

    return TipOptionsOut(
        offered=offered,
        currency=currency_for_country(country).value,
        presets=(
            [
                amount
                for amount in (row.tip_preset_small, row.tip_preset_medium)
                if row and amount > 0
            ]
            if offered and row
            else []
        ),
        # مُكمَّمٌ كبقية المال — `"0"` بين `"0.000"` عطبُ عرضٍ لا حساب
        max_amount=row.tip_max if offered and row else Decimal("0.000"),
        given=TipOut.model_validate(given) if given else None,
    )


@router.post(
    "/{ride_id}/tip", response_model=TipOut, status_code=status.HTTP_201_CREATED
)
async def add_tip(
    ride_id: uuid.UUID,
    payload: TipCreate,
    user: RiderUser,
    session: DbSession,
    redis: RedisDep,
) -> TipOut:
    """بقشيشٌ من الراكب للكبتن — **بلا عمولةٍ عليه** (قرارُ المالك).

    والإشعارُ بعد الـcommit كقاعدة المشروع: حدثٌ يُعلَن قبل أن يستقر قد يُعلَن
    ثم يتراجع.
    """
    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    tip = await tips_service.create(session, ride=ride, rider=user, amount=payload.amount)
    await session.commit()
    await session.refresh(tip)

    await notifications.publish_tip_received(
        session,
        redis,
        driver_user_id=tip.driver_id,
        tip=tip,
    )
    return TipOut.model_validate(tip)


@router.post("/{ride_id}/reroute", response_model=RouteLineOut)
async def reroute_ride(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession
) -> RouteLineOut:
    """يعيد رسمَ المسار من موضع الكبتن — **بسقفٍ في الخلفية** (البند ١٧-٤).

    **وللكبتن وحدَه**: هو من انحرف وهو من يقود، والراكبُ يرى الخطَّ المجمَّد على
    رحلته. ولو فُتح للراكب لصار لكلِّ رحلةٍ طالبان لنداءٍ واحدٍ مدفوع.

    **والسقفُ هنا لا في التطبيق**: عميلٌ يعدّ لنفسه عميلٌ يوجّه إنفاقاً — وهي
    قاعدةُ `card_gateway.return_url_for` نفسُها. والتطبيقُ يقرأ `reroutes_left`
    فيكفّ عن الطلب، **وكفُّه راحةٌ لا حراسة**.
    """
    ride = await rides_service.get_ride(session, ride_id)
    if ride.driver_id != driver.id:
        raise NotFound("الرحلة غير موجودة")

    points, left = await route_line.reroute(session, ride_id)
    await session.commit()
    return RouteLineOut(points=points or [], reroutes_left=left)


@router.post("/{ride_id}/pause", response_model=RideOut)
async def begin_pause(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    """«نقطة توقف» — **بيد الكبتن وحدَه** (§5.10-ب، الفرع ب).

    وعدّادٌ توقفه الحركةُ يخطئ في الزحام، **وعدّادٌ لا يُصدَّق لا يُحتجّ به**.

    **والراكبُ يُخبَر أن العدّاد يعمل ولماذا** — سطرٌ صريحٌ لا رقمٌ يظهر في
    الفاتورة آخرَ الرحلة: **مبلغٌ لم يُعلَن حين نشأ يُقرأ خطأً في الحساب**.
    """
    ride = await _driver_ride(session, ride_id, driver)
    await pauses.begin_pause(session, ride)
    await session.commit()
    # **وتُفرَّغ الجلسةُ قبل إعادة القراءة.** `Ride.pauses` علاقةٌ محمَّلةٌ مع
    # الصفّ، وكائنُ الرحلة في **هوية الجلسة** منذ قراءته أولَ السطر — فـ
    # `get_ride` يعيد **الكائنَ نفسَه بعلاقته البائتة**، ويُسلسَل الجوابُ بلا
    # الوقفة التي أُنشئت للتوّ.
    #
    # ووجدَه فتحُ الشاشة لا اختبار: اختباراتُ الوقفة تقرأ الصفوفَ من جلسةٍ
    # جديدة، فترى ما لا يراه التطبيق. **والصفُّ يُكتب صحيحاً والجوابُ يكذب** —
    # وهو بعينه شكلُ «حقلٌ بلا مُرسِل» الذي شحنه هذا المشروع مراراً.
    session.expire_all()
    ride = await rides_service.get_ride(session, ride_id)

    await notifications.publish_ride_paused(session, redis, ride=ride, paused=True)
    return RideOut.from_ride(ride)


@router.post("/{ride_id}/resume", response_model=RideOut)
async def resume_pause(
    ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    """«استئناف» — يُغلق الوقفةَ ويوقف العدّاد."""
    ride = await _driver_ride(session, ride_id, driver)
    await pauses.resume(session, ride)
    await session.commit()
    session.expire_all()  # انظر `begin_pause` — العلاقةُ بائتةٌ بلا تفريغ
    ride = await rides_service.get_ride(session, ride_id)

    await notifications.publish_ride_paused(session, redis, ride=ride, paused=False)
    return RideOut.from_ride(ride)


async def _driver_ride(
    session: DbSession, ride_id: uuid.UUID, driver: Driver
) -> Ride:
    """رحلةٌ يقودها هذا الكبتن — **٤٠٤ لا ٤٠٣**: وجودُ الرحلة ليس معلومةً لغيره."""
    ride = await rides_service.get_ride(session, ride_id)
    if ride.driver_id != driver.id:
        raise NotFound("الرحلة غير موجودة")
    return ride
