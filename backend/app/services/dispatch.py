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
    DispatchMode,
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
from app.services.dispatch_settings import DEFAULTS as _DEFAULTS
from app.services.dispatch_settings import DispatchRules, rules_for
from app.services import (
    geo,
    missions,
    notifications,
    settings_service,
    subscriptions,
)
from app.schemas.ride import RideOut
from app.ws import events

logger = logging.getLogger(__name__)

# **صارت إعداداً، ولا نسخةَ لها هنا** (قرارُ المالك 2026-08-30، و§5.3 عُدِّلت
# معه في الجلسة نفسِها): كان هنا ثلاثةُ ثوابتَ فوقها «ثوابت SPEC القسم 5.3 —
# لا إعدادات». **والقيمُ الحيّةُ في `dispatch_settings`** وتُقرأ **مرّةً عند
# بدء توزيع الرحلة** — فرحلةٌ جاريةٌ تُكمل بما بدأت به، والتبديلُ يسري على
# التالية. **ونصفُ متغيّرٍ أسوأُ من أيِّ الحالين**.
#
# **ولم يُترك اسمٌ هنا يحمل الافتراضَ نسخةً ثانية**: كان أهونَ أن يبقى
# `OFFER_TIMEOUT_SECONDS = _DEFAULTS.offer_timeout_seconds` ليعمل ما يقرؤه،
# **لكنه بيتٌ ثانٍ لقيمةٍ واحدة** — ومن يضبط أحدَهما في اختبارٍ يظنّ أنه ضبط
# السلوك، والسلوكُ يقرأ الآخر. وهو الشكلُ الذي كلّف هذا المشروعَ مراراً.

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


def driver_offer_km_key(driver_id: uuid.UUID | str) -> str:
    """المسافةُ التي عُرضت مع الطلب — **تُخزَّن ولا تُعاد حسابها**.

    استعادةُ العرض بعد انقطاعٍ تحتاج الرقمَ نفسَه الذي رآه الكبتن، **وحسابُه
    ثانيةً صيغةٌ ثانيةٌ لقيمةٍ واحدة** تفترقان أولَ تعديل. ومفتاحٌ مستقلٌّ لا
    تغييرُ صيغة القيمة الأولى: `accept_ride` يقرأ تلك، وتغييرُ شكلها يمسّ
    مسارَ قبولٍ يعمل.
    """
    return f"dispatch:driver_offer_km:{driver_id}"


def signal_key(ride_id: uuid.UUID | str) -> str:
    return f"dispatch:signal:{ride_id}"


def cooldown_key(ride_id: uuid.UUID | str) -> str:
    """**مجموعةٌ مرتَّبةٌ بلحظة انتهاء التبريد** — لا مفتاحٌ لكلِّ كبتن.

    **ولمَ واحدةٌ لا مفاتيحُ متفرّقة**: الحلقةُ تسأل «من في تبريده الآن؟» قبل
    كلِّ دورة — سؤالٌ واحدٌ عن مجموعةٍ أرخصُ من `n` سؤالاً عن مفاتيح، **ولا
    يحتاج معرفةَ الأسماء مسبقاً** وهي المشكلةُ نفسُها التي تجعل `mget` لا يصلح.
    """
    return f"dispatch:cooled:{ride_id}"


def broadcast_key(ride_id: uuid.UUID | str) -> str:
    """المعروضُ عليهم دفعةً واحدة — **مجموعةٌ لا قيمةٌ مفردة**.

    **ومفتاحٌ ثانٍ لا توسيعُ الأول**: `offer_key` قيمةٌ مفردةٌ يقرأها مسارُ
    القبول ومسارُ الاستعادة منذ المرحلة ٤، **وقلبُ شكلها يمسّ مساراً يعمل**.
    """
    return f"dispatch:broadcast:{ride_id}"


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
    """يمنع قبول رحلة لم تُعرض على هذا الكبتن — أو انتهت مهلته فيها.

    **وفي البثِّ يُسأل عن العضوية لا عن المساواة**: الدفعةُ كلُّها معروضٌ
    عليها، **وأولُ من يقبل يأخذ** — والفصلُ بينهم ليس هنا بل في انتقال حال
    الرحلة تحت قفل صفِّها (`searching → accepted`)، فالخاسرُ يُردّ بحالٍ
    لا بمهلة.
    """
    if await current_offer(redis, ride_id) == driver_id:
        return
    if await redis.sismember(broadcast_key(ride_id), str(driver_id)):
        return
    raise RideOfferExpired()


async def broadcast_members(redis: Redis, ride_id: uuid.UUID) -> set[uuid.UUID]:
    """من تحمل شاشاتُهم بطاقةَ هذه الرحلة الآن (نمطُ البثّ)."""
    raw = await redis.smembers(broadcast_key(ride_id))
    members: set[uuid.UUID] = set()
    for item in raw:
        try:
            members.add(uuid.UUID(item))
        except ValueError:  # pragma: no cover - قيمة تالفة
            continue
    return members


async def cool_down(
    redis: Redis, ride_id: uuid.UUID, driver_id: uuid.UUID, rules: DispatchRules
) -> None:
    """**تبريدٌ لا استبعادٌ دائم** (قرارُ المالك 2026-08-30).

    كان الرافضُ يُستبعد **بقيّةَ الرحلة** (`tried: set` في ذاكرة المهمّة).
    **و١٢٠ ثانيةً كانت ستُبقيه استبعاداً دائماً** لأنها مهلةُ الرحلة كلِّها —
    ولذلك ٣٠: تعيده حوالي المحاولة الرابعة، **فيراه ثانيةً في الطلب نفسِه
    ولا يعود إليه فور رفضه**.
    """
    seconds = rules.cooldown_seconds
    expiry = time.time() + seconds
    pipe = redis.pipeline()
    pipe.zadd(cooldown_key(ride_id), {str(driver_id): expiry})
    # **عمرُ المفتاح أطولُ من أطول رحلةِ بحث** — فلا يبقى بعد انتهائها
    pipe.expire(cooldown_key(ride_id), seconds + rules.total_timeout_seconds)
    await pipe.execute()


async def cooled_drivers(redis: Redis, ride_id: uuid.UUID) -> set[uuid.UUID]:
    """من هم في تبريدهم **الآن** — والمنتهيةُ تُكنس في السؤال نفسِه."""
    await redis.zremrangebyscore(cooldown_key(ride_id), "-inf", time.time())
    cooled: set[uuid.UUID] = set()
    for item in await redis.zrange(cooldown_key(ride_id), 0, -1):
        try:
            cooled.add(uuid.UUID(item))
        except ValueError:  # pragma: no cover
            continue
    return cooled


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
    # **الدفعةُ كلُّها تُطوى لا واحدٌ منها** (2026-08-30): في نمط البثِّ
    # `current_offer` فارغةٌ والبطاقاتُ على أربع شاشات — فسحبٌ يقرأ المفردةَ
    # وحدَها كان سيترك أربعةً ينظرون إلى رحلةٍ أُلغيت.
    holders = await broadcast_members(redis, ride_id)
    single = await current_offer(redis, ride_id)
    if single is not None:
        holders.add(single)
    if not holders:
        return

    await redis.delete(broadcast_key(ride_id))
    for driver_id in holders:
        await release_offer(redis, ride_id, driver_id)
        driver_user_id = await session.scalar(
            select(Driver.user_id).where(Driver.id == driver_id)
        )
        if driver_user_id is not None:
            await events.publish_offer_expired(
                redis, driver_user_id=driver_user_id, ride_id=ride_id
            )


async def _reserve_offer(
    redis: Redis,
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    ttl: int,
    distance_km: float | None = None,
) -> bool:
    """يحجز الكبتن لهذه الرحلة. False إن كان معروضاً عليه طلب آخر."""
    reserved = await redis.set(
        driver_offer_key(driver_id), str(ride_id), nx=True, ex=ttl
    )
    if not reserved:
        return False
    await redis.set(offer_key(ride_id), str(driver_id), ex=ttl)
    if distance_km is not None:
        await redis.set(driver_offer_km_key(driver_id), str(distance_km), ex=ttl)
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


async def _eligible_levels(
    session: AsyncSession,
    driver_ids: list[uuid.UUID],
    vehicle_category: VehicleCategory,
    *,
    gender: GenderMatch | None = None,
) -> dict[uuid.UUID, int]:
    """من بين الحاضرين جغرافياً: من يحق له استقبال طلب الآن — **ومستواه معه**.

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
        return {}

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
        # **وموقوفٌ لعمولةٍ قبضها بيده ولم تصلنا** (الترحيلة `0061`): عمودٌ
        # محضَّرٌ ثالثٌ بالشكل نفسِه، **ويُشعل فوق سقف اللوحة وحدَه** — وسقفٌ
        # غيرُ مكتوبٍ (`NULL`) لا يحجب أحداً، فلا يتغيّر شيءٌ حتى يُكتب الرقم.
        Driver.debt_blocked.is_(False),
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

    rows = await session.execute(
        select(Driver.id, Driver.level)
        .join(User, Driver.user_id == User.id)
        .where(*conditions)
    )
    return {driver_id: level for driver_id, level in rows.all()}


async def eligible_driver_ids(
    session: AsyncSession,
    driver_ids: list[uuid.UUID],
    vehicle_category: VehicleCategory,
    *,
    gender: GenderMatch | None = None,
) -> set[uuid.UUID]:
    """المؤهَّلون وحدَهم — وهو ما تقرؤه خريطةُ الراكب.

    **و`_eligible_levels` تقرأ المستوى في الاستعلام نفسِه** (البند ٥٣، §٥-ج):
    `drivers.level` عمودٌ في الصفِّ الذي يُقرأ أصلاً، فلا ضمَّ جديدٌ ولا استعلامٌ
    ثانٍ — ومسارُ العرض هذا **لا يزيد استعلاماً واحداً** عمّا كان.
    """
    return set(
        await _eligible_levels(
            session, driver_ids, vehicle_category, gender=gender
        )
    )


async def _ranked_candidates(
    session: AsyncSession,
    redis: Redis,
    *,
    ride: Ride,
    tried: set[uuid.UUID],
    gender: GenderMatch | None = None,
) -> list[geo.DriverPresence]:
    """المؤهَّلون مرتَّبين من الأقرب — **قائمةٌ لا واحد**.

    **ولمَ صارت قائمة**: نمطُ البثِّ يعرض على دفعةٍ معاً (قرارُ المالك
    2026-08-30)، **والتسلسليُّ يأخذ أوّلَها** — فترتيبٌ واحدٌ للنمطين، ولا
    دالّتان تُرتِّبان بطريقتين تفترقان أوّلَ تعديل.

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

        levels = await _eligible_levels(
            session,
            [presence.driver_id for presence in presences],
            ride.vehicle_category,
            gender=gender,
        )
        ranked = [p for p in presences if p.driver_id in levels]
        if not ranked:
            continue

        # **الأقربُ يبقى الأول، والمستوى يفصل بين المتقاربين** (البند ٥٣، §٥).
        #
        # وصيغةُ **الخصم بالأمتار** (قرارُ المالك ١): المسافةُ المؤثِّرة =
        # المسافة − خصمُ المستوى، بحدٍّ أقصى ١٠٠م. **ولا عتبةَ حادّة**: صيغةُ
        # الشرائح المرفوضة كانت تجعل فرقَ مترين بين ٤٩٩ و٥٠١ يقلب القاعدة.
        # **وأقصى إزاحةٍ = الخصمُ نفسُه**، فيُقرأ «كم مترٍ يساوي هذا المستوى».
        #
        # **ومطفأً تُعاد خريطةٌ فارغة فيصير الخصمُ صفراً للجميع** — والترتيبُ
        # حرفياً كما هو اليوم، بلا فرعٍ ثانٍ في الشيفرة يقول «رتّب بطريقةٍ أخرى»
        # **ولا يُسأل عن الخصم إلا حين يكون هناك ما يُرتَّب** (§٥-ج): مرشَّحٌ
        # واحدٌ هو الأوّلُ مهما كان مستواه، فقراءةُ الإعدادات له استعلامان في
        # نافذةِ العشرين ثانية بلا أن يتغيّر شيء. وهي الحالُ الغالبةُ فعلاً —
        # سوقٌ فيه كبتنٌ واحدٌ قريبٌ أشيعُ من سوقٍ فيه اثنان متقاربان
        discounts = (
            await missions.discounts_for(session, ride.country_code)
            if len(ranked) > 1
            else {}
        )
        if discounts:
            ranked.sort(
                key=lambda p: (
                    p.distance_km * 1000 - discounts.get(levels[p.driver_id], 0),
                    # **والمسافةُ الحقيقيةُ فاصلٌ ثانٍ**: متساويان في المؤثِّرة
                    # يُرتَّبان بالأقرب فعلاً، فلا يقرّر ترتيبُ ريدِس بينهما
                    p.distance_km,
                )
            )

        # `presences` مرتبة من الأقرب، فأولُ مؤهلٍ فيها هو الأقربُ المؤهل
        return ranked

    return []


async def _next_candidate(
    session: AsyncSession,
    redis: Redis,
    *,
    ride: Ride,
    tried: set[uuid.UUID],
    gender: GenderMatch | None = None,
) -> geo.DriverPresence | None:
    """أقربُ مؤهَّلٍ واحد — **غلافٌ فوق الترتيب الواحد** لا ترتيبٌ ثانٍ."""
    ranked = await _ranked_candidates(
        session, redis, ride=ride, tried=tried, gender=gender
    )
    return ranked[0] if ranked else None


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


async def pending_offer_frame(
    session: AsyncSession, redis: Redis, *, driver: Driver
) -> dict | None:
    """إطارُ العرض المعلَّق على هذا الكبتن — **أو `None` إن لم يبقَ عرض**.

    **العلّةُ**: العرضُ يعيش في Redis بمهلته (`dispatch:driver_offer:{id}`)،
    **وكان المقبسُ يصمت عنه عند الاتصال** — فكبتنٌ نقر إشعارَ الطلب، أو عاد
    من انقطاعٍ لحظيّ، يفتح شاشةً فارغةً بينما عرضُه حيٌّ بضع ثوانٍ. ثم تنتهي
    المهلةُ فيُقرأ ذلك **عطباً في التطبيق** لا مهلةً انقضت.

    **والمهلةُ المتبقّيةُ تُقرأ من `TTL` نفسِه لا تُقدَّر**: بطاقةٌ تُرسم
    بعشرين ثانيةً وقد بقي منها ثلاثٌ **تَعِد بوقتٍ لا وجودَ له**، ومن يعتمد
    عليها يضغط «قبول» على عرضٍ انتهى.
    """
    key = driver_offer_key(driver.id)
    raw = await redis.get(key)
    if raw is None:
        return None
    remaining = await redis.ttl(key)
    if remaining is None or remaining <= 0:
        return None

    ride_id = raw.decode() if isinstance(raw, bytes) else str(raw)
    ride = await session.get(Ride, uuid.UUID(ride_id))
    # **حالتُه تُقرأ من القاعدة**: عرضٌ قُبل أو أُلغي في الأثناء لا يُرسم
    if ride is None or ride.status is not RideStatus.SEARCHING:
        return None

    stored = await redis.get(driver_offer_km_key(driver.id))
    distance = float(stored) if stored is not None else 0.0
    return {
        "type": events.RideEvent.RIDE_OFFER.value,
        "ride": RideOut.from_ride(ride).model_dump(mode="json"),
        "distance_to_pickup_km": distance,
        "expires_in_seconds": int(remaining),
    }


async def _offer_to(
    redis: Redis,
    *,
    ride: Ride,
    candidate: geo.DriverPresence,
    driver_user_id: uuid.UUID,
    timeout: int,
) -> None:
    """يُظهر البطاقةَ على شاشةِ كبتنٍ بعينه — بابٌ واحدٌ للنمطين.

    **وجلسةٌ قصيرةٌ للإشعار وحدَه**: البثُّ لا يحتاجها، لكن Push يقرأ أجهزةَ
    الكبتن من القاعدة — ولا تُحجز جلسةٌ طوال انتظار المهلة من أجل ذلك.
    """
    async with SessionLocal() as session:
        await notifications.publish_ride_offer(
            session,
            redis,
            driver_user_id=driver_user_id,
            ride=ride,
            distance_to_pickup_km=candidate.distance_km,
            expires_in_seconds=timeout,
        )


async def _fold(
    redis: Redis,
    ride_id: uuid.UUID,
    held: dict[uuid.UUID, uuid.UUID],
    rules: DispatchRules,
) -> None:
    """يطوي بطاقاتِ دورةٍ انتهت، ويضع أصحابَها في تبريدهم."""
    if not held:
        return
    await redis.srem(broadcast_key(ride_id), *[str(d) for d in held])
    for driver_id, driver_user_id in held.items():
        await release_offer(redis, ride_id, driver_id)
        await cool_down(redis, ride_id, driver_id, rules)
        await events.publish_offer_expired(
            redis, driver_user_id=driver_user_id, ride_id=ride_id
        )


async def _run(ride_id: uuid.UUID) -> None:
    from app.services import rides as rides_service

    redis = get_redis_client()
    attempts = 0
    # **ما تحمله الشاشاتُ الآن**: كبتن → مستخدمُه. **ويُطوى في `finally`**
    # لأن إلغاءَ الراكب يُلغي هذه المهمّة **من داخل الانتظار**، فالسطورُ التي
    # تليه لا تُنفَّذ أبداً — وكانت البطاقةُ تبقى على شاشة الكبتن حتى تنقضي
    # مهلتُها (عطبٌ قِيس 2026-08-30).
    held: dict[uuid.UUID, uuid.UUID] = {}
    rules: DispatchRules = _DEFAULTS

    # `requested → searching`: من هنا فصاعداً الراكب يرى «نبحث عن كبتن»
    async with SessionLocal() as session:
        locked = await _locked_ride(session, ride_id)
        if locked is None or locked.status != RideStatus.REQUESTED:
            return  # أُلغيت قبل أن يبدأ البحث
        await rides_service.mark_searching(session, locked)
        # **تُقرأ القواعدُ مرّةً هنا** — والتبديلُ حيّاً يسري على الرحلة
        # التالية لا على هذه (انظر `services/dispatch_settings.py`)
        rules = await rules_for(session, locked.country_code)
        await session.commit()

    deadline = time.monotonic() + rules.total_timeout_seconds

    # **المشاركةُ تُجرَّب قبل أوّل عرض** (12-ي): المقعدُ الثاني في سيارةٍ سائرةٍ
    # أصلاً أسرعُ للراكب وأربحُ للكبتن من إيقاظ سيارةٍ أخرى — وإن لم يوجد، تمضي
    # الحلقةُ أدناه كأن الميزةَ غيرُ موجودة. **ومكانُه هنا لا في الراوتر**: طلبُ
    # الرحلة يجيب فوراً بـ`requested`، والمطابقةُ نداءُ Mapbox لا يجوز أن يقف
    # عليه ردُّ الطلب — كما لا يقف عليه العرضُ الأول.
    if await _try_sharing(ride_id):
        return

    try:
        while attempts < rules.max_attempts and time.monotonic() < deadline:
            async with SessionLocal() as session:
                ride = await _load_ride(session, ride_id)
                # أُلغيت أو قُبلت من مسار آخر — لا شأن للتوزيع بها بعد الآن
                if ride is None or ride.status != RideStatus.SEARCHING:
                    return
                # شرطُ المطابقة يُقرأ في كل دورة لا مرةً عند البدء: مفتاحُ
                # الخدمة قد يُطفأ أثناء البحث، وجنسُ الكبتن قد يُختم في هذه
                # الدقيقة — وقراءتُه هنا تكلّف استعلامين بجانب استعلام الأهلية
                match = await gender_match_for(
                    session,
                    ride=ride,
                    gender=await rider_gender(session, ride.rider_id),
                )
                # **التبريدُ يُقرأ في كلِّ دورة**، وهو الفرقُ كلُّه عن `tried`:
                # مجموعةٌ **تنقص** بمرور الوقت لا مجموعةٌ تكبر أبداً
                ranked = await _ranked_candidates(
                    session,
                    redis,
                    ride=ride,
                    tried=await cooled_drivers(redis, ride_id),
                    gender=match,
                )
                wanted = (
                    rules.broadcast_batch_size
                    if rules.mode is DispatchMode.BROADCAST
                    else 1
                )
                chosen = ranked[:wanted]
                user_ids: dict[uuid.UUID, uuid.UUID] = {}
                if chosen:
                    user_ids = {
                        driver_id: user_id
                        for driver_id, user_id in (
                            await session.execute(
                                select(Driver.id, Driver.user_id).where(
                                    Driver.id.in_([p.driver_id for p in chosen])
                                )
                            )
                        ).all()
                    }

            # لا أحد قريب بعد — ننتظر ظهور كبتن، والانتظار خارج الجلسة حتى لا
            # يُحجز اتصال بالقاعدة طوال المهلة. ولا تُحتسب محاولةٌ على غيابهم.
            if not chosen:
                await asyncio.sleep(IDLE_POLL_SECONDS)
                continue

            held = {}
            for candidate in chosen:
                driver_user_id = user_ids.get(candidate.driver_id)
                if driver_user_id is None:  # pragma: no cover - صفٌّ اختفى
                    continue
                if not await _reserve_offer(
                    redis,
                    ride_id,
                    candidate.driver_id,
                    rules.offer_timeout_seconds,
                    distance_km=candidate.distance_km,
                ):
                    # معروضٌ عليه طلبٌ آخر الآن — **يُبرَّد لا يُستبعد**، فقد
                    # يفرغ قبل أن ينتهي بحثُنا
                    await cool_down(redis, ride_id, candidate.driver_id, rules)
                    continue
                held[candidate.driver_id] = driver_user_id

            if not held:
                # كلُّ من وجدناه مشغولٌ الآن — ولا تُحتسب محاولة
                await asyncio.sleep(IDLE_POLL_SECONDS)
                continue

            attempts += 1
            if rules.mode is DispatchMode.BROADCAST:
                pipe = redis.pipeline()
                pipe.sadd(broadcast_key(ride_id), *[str(d) for d in held])
                pipe.expire(broadcast_key(ride_id), rules.offer_timeout_seconds)
                await pipe.execute()

            # تُمسح إشاراتُ المحاولة السابقة حتى لا يُقرأ رفضٌ قديمٌ جواباً الآن
            await redis.delete(signal_key(ride_id))
            for candidate in chosen:
                if candidate.driver_id in held:
                    await _offer_to(
                        redis,
                        ride=ride,
                        candidate=candidate,
                        driver_user_id=held[candidate.driver_id],
                        timeout=rules.offer_timeout_seconds,
                    )

            # **ورفضُ واحدٍ في البثِّ لا ينهي الدورة**: تُطوى بطاقتُه وحدَه
            # ويبقى الباقون — وتنتهي الدورةُ بقبولٍ أو بخلوّ الدفعة أو بالمهلة.
            round_end = time.monotonic() + rules.offer_timeout_seconds
            accepted = False
            while held and time.monotonic() < round_end:
                remaining = min(round_end, deadline) - time.monotonic()
                if remaining <= 0:
                    break
                signal = await _wait_for_signal(redis, ride_id, remaining)
                if signal == _SIGNAL_ACCEPTED:
                    accepted = True
                    break
                if signal is None:
                    break
                if signal.startswith(_SIGNAL_DECLINED):
                    _, _, raw = signal.partition(":")
                    try:
                        refuser = uuid.UUID(raw)
                    except ValueError:  # pragma: no cover - قيمة تالفة
                        continue
                    if refuser in held:
                        await cool_down(redis, ride_id, refuser, rules)
                        await redis.srem(broadcast_key(ride_id), str(refuser))
                        held.pop(refuser, None)

            if accepted:
                # ## **من فاز تبقى بطاقتُه، ومن لم يفز تُطوى بطاقتُه فوراً**
                #
                # **عطبٌ وجدَته إعادةُ القراءة 2026-08-30**: كان `held = {}`
                # وحدَه — فتبقى البطاقةُ على شاشات من لم يفوزوا حتى تنقضي
                # مهلتُها، **فيضغط أحدُهم «اقبل» على رحلةٍ أُخذت**. ويُردّ
                # بخطأٍ لا يفهمه، وقد ترك ما في يده لأجلها.
                #
                # **والفائزُ يُقرأ من صفِّ الرحلة لا من الإشارة**:
                # `notify_accepted` لا تحمل هويّةً، **وقراءةُ الصفِّ بعد
                # الالتزام تقول من كتبه فعلاً** — ولا يُخمَّن من سبق.
                async with SessionLocal() as session:
                    winner = await session.scalar(
                        select(Ride.driver_id).where(Ride.id == ride_id)
                    )
                held.pop(winner, None)
                await _fold(redis, ride_id, held, rules)
                held = {}
                return

            # صمتوا أو رفضوا: تُطوى البطاقاتُ ويدخل أصحابُها التبريد
            await _fold(redis, ride_id, held, rules)
            held = {}

        await _mark_no_driver_found(redis, ride_id)
    finally:
        # **الإلغاءُ يمرّ من هنا وحدَه**: `task.cancel()` يرفع `CancelledError`
        # داخل الانتظار، **فما بعده لا يُنفَّذ** — وبلا هذا البند تبقى البطاقةُ
        # على شاشة الكبتن حتى تنقضي مهلتُها، وقد يقبل رحلةً أُلغيت.
        if held:
            with contextlib.suppress(Exception):
                await _fold(redis, ride_id, held, rules)


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
