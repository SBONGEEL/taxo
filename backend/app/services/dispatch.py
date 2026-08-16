"""خوارزمية إسناد الرحلات للكباتن (SPEC القسم 5.3).

الطلب لا يُعرض على كل الكباتن دفعةً واحدة: يُعرض على **الأقرب أولاً** ولمدة
عشرين ثانية، فإن رفض أو صمت انتقل للتالي. تنتهي المحاولة بعد خمسة عروض أو
دقيقتين — أيهما أسبق — بحالة `no_driver_found`.

كل رحلة يتبعها مهمة asyncio مستقلة تعيش داخل عملية التطبيق. لا Celery هنا
قصداً: الأمر تفاعليّ بمقياس الثواني والراكب ينتظر على الشاشة، بينما Celery
(المرحلة 7) لما يحتمل التأجيل كانتهاء الاشتراكات.

**حالة العرض في Redis لا في الذاكرة**، فقبول الكبتن يُتحقق منه في أي عامل
uvicorn وصله الطلب:

- `dispatch:offer:{ride_id}` → الكبتن المعروض عليه الآن (بعمر المهلة)
- `dispatch:driver_offer:{driver_id}` → الرحلة المعروضة عليه (بعمرها نفسه)،
  يُكتب بـ NX فلا يُعرض على كبتن واحد طلبان في آن
- `dispatch:signal:{ride_id}` → قائمة يوقظ بها القبولُ والرفضُ المهمةَ النائمة
  بدل انتظار المهلة كاملة
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.exceptions import NotFound, RideOfferExpired
from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    DriverStatus,
    FeatureKey,
    Gender,
    GenderPreference,
    RideStatus,
    VehicleCategory,
)
from app.models.ride import ACTIVE_DRIVER_STATUSES, Ride
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services import geo, notifications, settings_service, subscriptions
from app.ws import events

logger = logging.getLogger(__name__)

# ثوابت SPEC القسم 5.3 — لا إعدادات: هذه قواعد التوزيع نفسها
OFFER_TIMEOUT_SECONDS = 20
MAX_ATTEMPTS = 5
TOTAL_TIMEOUT_SECONDS = 120

# مهلة بين دورتي بحث حين لا يوجد أي كبتن قريب — لا تُحتسب محاولة
IDLE_POLL_SECONDS = 3.0

_SIGNAL_ACCEPTED = "accepted"
_SIGNAL_DECLINED = "declined"
_SIGNAL_TTL_SECONDS = 60

# حذف مشروط بالقيمة: مهمة قديمة يجب ألا تمحو عرضاً أحدث للكبتن نفسه
_RELEASE_OFFER = """
if redis.call('get', KEYS[1]) == ARGV[1] then redis.call('del', KEYS[1]) end
if redis.call('get', KEYS[2]) == ARGV[2] then redis.call('del', KEYS[2]) end
return 1
"""

# المهام الجارية — لإيقافها عند إطفاء التطبيق ومنع تكرارها للرحلة الواحدة
_tasks: dict[uuid.UUID, asyncio.Task] = {}


def offer_key(ride_id: uuid.UUID | str) -> str:
    return f"dispatch:offer:{ride_id}"


def driver_offer_key(driver_id: uuid.UUID | str) -> str:
    return f"dispatch:driver_offer:{driver_id}"


def signal_key(ride_id: uuid.UUID | str) -> str:
    return f"dispatch:signal:{ride_id}"


# ------------------------------------------------------------------- العروض


async def current_offer(redis: Redis, ride_id: uuid.UUID) -> uuid.UUID | None:
    """الكبتن المعروضة عليه هذه الرحلة الآن، إن وُجد."""
    raw = await redis.get(offer_key(ride_id))
    if raw is None:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:  # pragma: no cover - قيمة تالفة
        return None


async def require_offer(redis: Redis, ride_id: uuid.UUID, driver_id: uuid.UUID) -> None:
    """يمنع قبول رحلة لم تُعرض على هذا الكبتن — أو انتهت مهلته فيها."""
    if await current_offer(redis, ride_id) != driver_id:
        raise RideOfferExpired()


async def release_offer(
    redis: Redis, ride_id: uuid.UUID, driver_id: uuid.UUID
) -> None:
    await redis.eval(
        _RELEASE_OFFER,
        2,
        offer_key(ride_id),
        driver_offer_key(driver_id),
        str(driver_id),
        str(ride_id),
    )


async def withdraw_offer(
    session: AsyncSession, redis: Redis, ride_id: uuid.UUID
) -> None:
    """يسحب العرض القائم ويطوي بطاقته من شاشة الكبتن (إلغاء أثناء البحث)."""
    driver_id = await current_offer(redis, ride_id)
    if driver_id is None:
        return

    await release_offer(redis, ride_id, driver_id)
    driver_user_id = await session.scalar(
        select(Driver.user_id).where(Driver.id == driver_id)
    )
    if driver_user_id is not None:
        await events.publish_offer_expired(
            redis, driver_user_id=driver_user_id, ride_id=ride_id
        )


async def _reserve_offer(
    redis: Redis, ride_id: uuid.UUID, driver_id: uuid.UUID, ttl: int
) -> bool:
    """يحجز الكبتن لهذه الرحلة. False إن كان معروضاً عليه طلب آخر."""
    reserved = await redis.set(
        driver_offer_key(driver_id), str(ride_id), nx=True, ex=ttl
    )
    if not reserved:
        return False
    await redis.set(offer_key(ride_id), str(driver_id), ex=ttl)
    return True


# ------------------------------------------------------------------ الإشارات


async def _signal(redis: Redis, ride_id: uuid.UUID, value: str) -> None:
    pipe = redis.pipeline()
    pipe.rpush(signal_key(ride_id), value)
    pipe.expire(signal_key(ride_id), _SIGNAL_TTL_SECONDS)
    await pipe.execute()


async def notify_accepted(redis: Redis, ride_id: uuid.UUID) -> None:
    """يوقظ المهمة فتتوقف فوراً بدل انتظار بقية المهلة."""
    await _signal(redis, ride_id, _SIGNAL_ACCEPTED)


async def notify_declined(
    redis: Redis, ride_id: uuid.UUID, driver_id: uuid.UUID
) -> None:
    """رفض صريح — ينتقل التوزيع للتالي بلا انتظار."""
    await release_offer(redis, ride_id, driver_id)
    await _signal(redis, ride_id, f"{_SIGNAL_DECLINED}:{driver_id}")


async def _wait_for_signal(
    redis: Redis, ride_id: uuid.UUID, timeout: float
) -> str | None:
    # BLPOP لا يقبل صفراً (معناه انتظار بلا نهاية)، وأدنى دقة له ثانية
    result = await redis.blpop([signal_key(ride_id)], timeout=max(1, round(timeout)))
    return result[1] if result else None


# ------------------------------------------------------------------- الأهلية


@dataclass(frozen=True, slots=True)
class GenderMatch:
    """طرفا المطابقة في رحلةٍ واحدة (المرحلة 10-ج).

    `None` بدل هذا الكائن يعني **لا مطابقةَ جنسٍ إطلاقاً**: إمّا لأن
    `women_service_enabled` مطفأ في هذه الدولة، أو لأن المستدعي لا علاقة له
    بالخدمة. وهو تمييزٌ مقصود عن `preference=any`: ذاك يعني «الراكبة لا يهمّها
    من يأتي» — ويبقى تفضيلُ **الكبتن** نافذاً — وهذا يعني «الميزة غير موجودة».
    """

    rider_gender: Gender | None
    preference: GenderPreference


async def gender_match(
    session: AsyncSession,
    *,
    country_code: CountryCode,
    rider_gender: Gender | None,
    preference: GenderPreference,
) -> GenderMatch | None:
    """شرطُ المطابقة لهذه الدولة — أو `None` إن كانت الخدمة مطفأة فيها.

    نقطةُ قرارٍ واحدة يمرّ بها التوزيعُ وخريطةُ الراكب معاً، فلا تفترق «من
    يُعرض متاحاً» عن «من يُسنَد إليه» — وهو الالتزام الذي تحمله
    `drivers.nearby_available` منذ المرحلة 4.
    """
    if not await settings_service.is_feature_enabled(
        session, country_code, FeatureKey.WOMEN_SERVICE_ENABLED
    ):
        return None
    return GenderMatch(rider_gender=rider_gender, preference=preference)


async def gender_match_for(
    session: AsyncSession, *, ride: Ride, gender: Gender | None
) -> GenderMatch | None:
    """شرطُ المطابقة لرحلةٍ بعينها — بتفضيلها المجمَّد لا بتفضيل الملف."""
    return await gender_match(
        session,
        country_code=ride.country_code,
        rider_gender=gender,
        preference=ride.gender_preference,
    )


async def rider_gender(session: AsyncSession, rider_id: uuid.UUID) -> Gender | None:
    """جنسُ الراكب كما أعلنه — بلا شرط ختم.

    الختمُ (`gender_verified_at`) شرطٌ في جانب الكبتن وحده: إعلانُ الراكبة
    يقيّد رحلتَها هي، وإعلانُ الكبتن يقيّد أمانَ غيره.
    """
    return await session.scalar(select(User.gender).where(User.id == rider_id))


async def eligible_driver_ids(
    session: AsyncSession,
    driver_ids: list[uuid.UUID],
    vehicle_category: VehicleCategory,
    *,
    gender: GenderMatch | None = None,
) -> set[uuid.UUID]:
    """من بين الحاضرين جغرافياً: من يحق له استقبال طلب الآن.

    تستعملها خريطة الراكب أيضاً، فما يُعرض «متاحاً» هو نفسه ما يُسنَد إليه.

    شروط SPEC القسم 5.3: معتمد + أونلاين + **اشتراك ساري** + بلا رحلة جارية،
    ومركبته من الفئة المطلوبة. وشرط الاشتراك يُقرأ من الجدول **بالساعة** لا من
    عمود الحالة وحده (`subscriptions.coverage_condition`): المهمة الدورية
    تعلّم المنتهي كل بضع دقائق، والقسم 8 يقول «لا اشتراك ساري = لا رحلات» —
    فالحكم للحظة الطلب لا لآخر مرور مهمة.

    **والمطابقة ثنائية الاتجاه** (المرحلة 10-ج) ومكانُها هنا لا في الراوتر:
    هذه هي الدالة التي تجيب «من يصلح لهذا الطلب»، وأيُّ تصفيةٍ فوقها تُنسى في
    أحد المسارين. الاتجاهان مستقلان تماماً:

    - **ما تطلبه الراكبة**: تفضيلٌ غير `any` يقصر النتيجة على كبتنٍ جنسُه
      **مختوم** بذلك الجنس. وغيرُ المختوم لا يُرشَّح لطلبٍ مجنَّس أصلاً.
    - **ما يقبله الكبتن**: كبتنٌ تفضيلُه غير `any` لا يُعرض عليه إلا راكبٌ من
      ذلك الجنس. وراكبٌ لم يعلن جنسه لا يطابق أحداً منهم.

    فراكبٌ اختار «لا يهمّني» **لا يُعرض طلبُه** على كبتنةٍ اختارت النساء
    وحدهن — الاتجاه الثاني لا يُلغيه سكوتُ الأول.
    """
    if not driver_ids:
        return set()

    busy = (
        select(Ride.id)
        .where(Ride.driver_id == Driver.id, Ride.status.in_(ACTIVE_DRIVER_STATUSES))
        .exists()
    )
    has_vehicle = (
        select(Vehicle.id)
        .where(Vehicle.driver_id == Driver.id, Vehicle.category == vehicle_category)
        .exists()
    )
    subscribed = subscriptions.covered_driver_ids_subquery().exists()

    conditions = [
        Driver.id.in_(driver_ids),
        Driver.status == DriverStatus.APPROVED,
        Driver.is_online.is_(True),
        Driver.current_ride_id.is_(None),
        # **موقوفٌ لدَينِ سلفةٍ تجاوز مهلته** (البند ١٥): عمودٌ محضَّرٌ تكتبه
        # المهمّةُ الدورية وتطفئه لحظةُ السداد — وجمعُ دفترٍ هنا يضع حساباً
        # ماليّاً في مسارٍ يمرّ به كلُّ طلبٍ وكلُّ خريطةِ راكب
        Driver.advance_blocked.is_(False),
        # **وموقوفٌ لمالِ كبتنٍ آخر في يده** (`CANCELLATION-FEE.md` §6-أ):
        # قبض رسمَ إلغاءٍ نقداً ولم يحوّله حتى انقضت مهلتُه. عمودٌ محضَّرٌ
        # بالشكل نفسِه ولسببه نفسِه، **ومنفصلٌ عن سابقه**: دَينان لمُقرِضَين
        # مختلفَين، وعمودٌ واحدٌ يحملهما يجعل سدادَ أحدهما يفتح بابَ الآخر
        Driver.cancellation_carry_blocked.is_(False),
        has_vehicle,
        subscribed,
        ~busy,
    ]
    if gender is not None:
        if gender.preference is not GenderPreference.ANY:
            conditions.append(User.gender == Gender(gender.preference.value))
            # الختمُ شرطٌ لا زينة: بغيره يصير الحقلُ ادّعاءً يكتبه صاحبه
            conditions.append(User.gender_verified_at.is_not(None))
        conditions.append(
            Driver.gender_preference == GenderPreference.ANY
            if gender.rider_gender is None
            else or_(
                Driver.gender_preference == GenderPreference.ANY,
                Driver.gender_preference
                == GenderPreference(gender.rider_gender.value),
            )
        )

    rows = await session.scalars(
        select(Driver.id).join(User, Driver.user_id == User.id).where(*conditions)
    )
    return set(rows.all())


async def _next_candidate(
    session: AsyncSession,
    redis: Redis,
    *,
    ride: Ride,
    tried: set[uuid.UUID],
    gender: GenderMatch | None = None,
) -> geo.DriverPresence | None:
    """أقرب كبتن مؤهل لم يُعرض عليه هذا الطلب بعد.

    يبدأ البحث بثلاثة كيلومترات ويتوسع لسبعة إن خلت الدائرة (SPEC القسم 5.3)
    — **وإلى عشرة في الطلب المجنَّس** (المرحلة 10-ج)، لأن دائرة المرشَّحين فيه
    أضيق ابتداءً فالتوسعةُ هي ما يفرق بين كبتنةٍ على بعد ثمانية كيلومترات
    و«لم نجد كبتناً».
    """
    widest = (
        geo.GENDERED_MAX_SEARCH_RADIUS_KM
        if gender is not None and gender.preference is not GenderPreference.ANY
        else geo.MAX_SEARCH_RADIUS_KM
    )
    for radius in (geo.SEARCH_RADIUS_KM, widest):
        presences = [
            presence
            for presence in await geo.nearby(
                redis,
                country_code=ride.country_code,
                lat=ride.pickup_lat,
                lng=ride.pickup_lng,
                radius_km=radius,
            )
            if presence.driver_id not in tried
            and presence.vehicle_category == ride.vehicle_category
        ]
        if not presences:
            continue

        eligible = await eligible_driver_ids(
            session,
            [presence.driver_id for presence in presences],
            ride.vehicle_category,
            gender=gender,
        )
        # `presences` مرتبة من الأقرب، فأول مؤهل فيها هو الأقرب المؤهل
        for presence in presences:
            if presence.driver_id in eligible:
                return presence

    return None


# ----------------------------------------------------------- تشغيل التوزيع


async def _load_ride(session: AsyncSession, ride_id: uuid.UUID) -> Ride | None:
    """الرحلة بعلاقاتها محمّلة: حمولة البث تحتاجها بعد إغلاق الجلسة."""
    from app.services import rides as rides_service

    try:
        return await rides_service.get_ride(session, ride_id)
    except NotFound:  # pragma: no cover - تُحذف الرحلة أثناء التوزيع
        return None


async def _locked_ride(session: AsyncSession, ride_id: uuid.UUID) -> Ride | None:
    """قفل صف الرحلة قبل تغيير حالتها.

    بلا القفل قد يقرأ التوزيعُ حالةً ويكتب فوق قبولٍ أو إلغاءٍ وقع بينهما.
    """
    return await session.scalar(
        select(Ride).where(Ride.id == ride_id).with_for_update()
    )


async def _mark_no_driver_found(redis: Redis, ride_id: uuid.UUID) -> None:
    from app.services import rides as rides_service

    async with SessionLocal() as session:
        locked = await _locked_ride(session, ride_id)
        if locked is None or locked.status != RideStatus.SEARCHING:
            return  # قُبلت أو أُلغيت بيننا وبين آخر فحص
        ride = await rides_service.mark_no_driver_found(session, locked)
        await session.commit()
        await notifications.publish_ride_event(
            session, redis, ride, events.RideEvent.NO_DRIVER_FOUND
        )


async def _try_sharing(ride_id: uuid.UUID) -> bool:
    """يحاول إلحاق الرحلة بمجموعةٍ قائمة — `True` إن التحقت فلا توزيع.

    **وفشلُه ليس فشلَ الطلب**: أيُّ تعثّرٍ هنا يعيد `False` فتمضي الرحلةُ في
    التوزيع العادي. المشاركةُ **زيادةٌ محتملة** بنصِّ قرار المالك الثالث — الوعدُ
    محفوظٌ بخصمه ولو لم يوجد شريك — فمعاملةٌ متعثّرةٌ في بحثٍ عن شريكٍ يجب ألّا
    تترك راكباً بلا سيارة.
    """
    from app.services import sharing as sharing_service

    try:
        async with SessionLocal() as session:
            ride = await _load_ride(session, ride_id)
            if ride is None or ride.share_discount_percent_at_ride <= 0:
                return False
            rider = await session.get(User, ride.rider_id)
            if rider is None:  # pragma: no cover - مفتاحٌ أجنبيٌّ يمنعه
                return False
            joined = await sharing_service.try_join(
                session, get_redis_client(), ride=ride, rider=rider
            )
            return joined is not None
    except Exception:  # noqa: BLE001 - مشاركةٌ متعثّرة لا تُلغي توزيعاً
        logger.warning("تعثّرت مطابقةُ المشاركة للرحلة %s", ride_id, exc_info=True)
        return False


async def _run(ride_id: uuid.UUID) -> None:
    from app.services import rides as rides_service

    redis = get_redis_client()
    deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS
    tried: set[uuid.UUID] = set()
    attempts = 0

    # `requested → searching`: من هنا فصاعداً الراكب يرى «نبحث عن كبتن»
    async with SessionLocal() as session:
        locked = await _locked_ride(session, ride_id)
        if locked is None or locked.status != RideStatus.REQUESTED:
            return  # أُلغيت قبل أن يبدأ البحث
        await rides_service.mark_searching(session, locked)
        await session.commit()

    # **المشاركةُ تُجرَّب قبل أوّل عرض** (12-ي): المقعدُ الثاني في سيارةٍ سائرةٍ
    # أصلاً أسرعُ للراكب وأربحُ للكبتن من إيقاظ سيارةٍ أخرى — وإن لم يوجد، تمضي
    # الحلقةُ أدناه كأن الميزةَ غيرُ موجودة. **ومكانُه هنا لا في الراوتر**: طلبُ
    # الرحلة يجيب فوراً بـ`requested`، والمطابقةُ نداءُ Mapbox لا يجوز أن يقف
    # عليه ردُّ الطلب — كما لا يقف عليه العرضُ الأول.
    if await _try_sharing(ride_id):
        return

    while attempts < MAX_ATTEMPTS and time.monotonic() < deadline:
        async with SessionLocal() as session:
            ride = await _load_ride(session, ride_id)
            # أُلغيت أو قُبلت من مسار آخر — لا شأن للتوزيع بها بعد الآن
            if ride is None or ride.status != RideStatus.SEARCHING:
                return
            # شرطُ المطابقة يُقرأ في كل دورة لا مرةً عند البدء: مفتاحُ الخدمة
            # قد يُطفأ أثناء البحث، وجنسُ الكبتن قد يُختم في هذه الدقيقة —
            # وقراءتُه هنا تكلّف استعلامين بجانب استعلام الأهلية نفسه
            match = await gender_match_for(
                session,
                ride=ride,
                gender=await rider_gender(session, ride.rider_id),
            )
            candidate = await _next_candidate(
                session, redis, ride=ride, tried=tried, gender=match
            )
            driver_user_id = (
                await session.scalar(
                    select(Driver.user_id).where(Driver.id == candidate.driver_id)
                )
                if candidate is not None
                else None
            )

        # لا أحد قريب بعد — ننتظر ظهور كبتن، والانتظار خارج الجلسة حتى لا
        # يُحجز اتصال بالقاعدة طوال المهلة. لا تُحتسب محاولة على غياب المرشحين.
        if candidate is None:
            await asyncio.sleep(IDLE_POLL_SECONDS)
            continue

        if not await _reserve_offer(
            redis, ride_id, candidate.driver_id, OFFER_TIMEOUT_SECONDS
        ):
            # معروض عليه طلب آخر في هذه اللحظة — نتخطاه بلا احتساب محاولة
            tried.add(candidate.driver_id)
            continue

        attempts += 1
        tried.add(candidate.driver_id)
        # تُمسح إشارات المحاولة السابقة حتى لا يُقرأ رفضٌ قديم على أنه جواب الآن
        await redis.delete(signal_key(ride_id))
        # جلسةٌ قصيرة للإشعار وحده: البثُّ لا يحتاجها لكن Push يقرأ أجهزة
        # الكبتن من القاعدة، ولا تُحجز جلسةٌ طوال انتظار المهلة من أجل ذلك
        async with SessionLocal() as session:
            await notifications.publish_ride_offer(
                session,
                redis,
                driver_user_id=driver_user_id,
                ride=ride,
                distance_to_pickup_km=candidate.distance_km,
                expires_in_seconds=OFFER_TIMEOUT_SECONDS,
            )

        remaining = min(OFFER_TIMEOUT_SECONDS, deadline - time.monotonic())
        signal = await _wait_for_signal(redis, ride_id, remaining)
        if signal == _SIGNAL_ACCEPTED:
            return

        # صمتَ أو رفض: تُطوى البطاقة من شاشته ويُحرَّر لطلب آخر
        await release_offer(redis, ride_id, candidate.driver_id)
        await events.publish_offer_expired(
            redis, driver_user_id=driver_user_id, ride_id=ride_id
        )

    await _mark_no_driver_found(redis, ride_id)


async def _guarded(ride_id: uuid.UUID) -> None:
    try:
        await _run(ride_id)
    except asyncio.CancelledError:
        raise
    except Exception:  # pragma: no cover - لا يجوز أن يسقط التوزيع صامتاً
        logger.exception("فشل توزيع الرحلة %s", ride_id)
    finally:
        _tasks.pop(ride_id, None)


def start(ride_id: uuid.UUID) -> None:
    """يبدأ توزيع رحلة **بعد الـ commit** — قبله لا يراها المهمة أصلاً."""
    if ride_id in _tasks:
        return
    _tasks[ride_id] = asyncio.create_task(_guarded(ride_id), name=f"dispatch:{ride_id}")


async def stop(ride_id: uuid.UUID) -> None:
    """إيقاف التوزيع عند إلغاء الراكب رحلته وهي في `searching`."""
    task = _tasks.pop(ride_id, None)
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def shutdown() -> None:
    """إطفاء التطبيق: تُلغى المهام الجارية بدل أن تُقطع في منتصفها."""
    for ride_id in list(_tasks):
        await stop(ride_id)
