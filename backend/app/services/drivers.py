"""حضور الكبتن: الاتصال والانفصال وبث الموقع (SPEC القسم 10/12).

الطبقة التي فوق `services/geo.py`: تلك تعرف Redis وحده، وهذه تعرف من يحق له
أن يظهر على الخريطة أصلاً. يستعملها الراوتر ومقبس WebSocket معاً.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:  # pragma: no cover - للتلميح فقط
    from app.schemas.party import DriverPartyOut

from app.core.exceptions import Conflict, DocumentsIncomplete, PermissionDenied
from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, VehicleCategory
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services import approach, broadcast
from app.services import geo, route
from app.services import presence_token
from app.ws import events


@dataclass(frozen=True, slots=True)
class PresenceContext:
    """ما يلزم لكتابة موقع الكبتن، مقروءاً من القاعدة مرة واحدة.

    مقبس الكبتن يستقبل موقعاً كل ثلاث ثوانٍ؛ لولا هذا لسأل القاعدة عن دولته
    وفئة مركبته مع كل رسالة.
    """

    driver_id: uuid.UUID
    country_code: CountryCode
    vehicle_category: VehicleCategory
    # **المركبةُ المنشورةُ قبل القبول** (2026-08-22) — تُقرأ مرةً مع بقية
    # الثوابت لا مع كلِّ بثّ، ويكتبها الحضورُ في هاشه
    # (`vehicle_skins.publishable_skin_for`)
    skin: geo.MapSkin | None = None


async def presence_context(session: AsyncSession, driver: Driver) -> PresenceContext:
    """يتحقق من أهلية الظهور ويجمع ثوابتها."""
    if driver.status != DriverStatus.APPROVED:
        raise PermissionDenied("حساب الكبتن غير معتمد بعد")

    country_code = await session.scalar(
        select(User.country_code).where(User.id == driver.user_id)
    )
    category = await session.scalar(
        select(Vehicle.category)
        .where(Vehicle.driver_id == driver.id)
        .order_by(Vehicle.created_at)
        .limit(1)
    )
    if category is None:
        # الراكب يختار الفئة عند الطلب، فكبتن بلا مركبة مسجّلة لا يقابل أي طلب
        raise Conflict("سجّل مركبتك قبل الاتصال")

    # **الاستيرادُ هنا لا في الرأس**: `vehicle_skins` يستورد `wallet` الذي
    # يستورد `settings_service` — وهذا الملفُّ يُستورد من `ws/` مبكّراً،
    # فحلقةٌ في الاستيراد تسقط الإقلاعَ كلَّه
    from app.services import vehicle_skins

    return PresenceContext(
        driver_id=driver.id,
        country_code=country_code,
        vehicle_category=category,
        skin=await vehicle_skins.publishable_skin_for(session, driver),
    )


async def go_online(
    session: AsyncSession, driver: Driver
) -> PresenceContext:
    """يرفع `is_online`. الـ commit مسؤولية المستدعي.

    لا يدخل الكبتنُ الفهرسَ الجغرافي هنا: لا موقع له بعد. أول بث موقع هو ما
    يجعله مرئياً للتوزيع فعلاً.
    """
    context = await presence_context(session, driver)
    driver.is_online = True
    return context


async def go_offline(session: AsyncSession, redis: Redis, driver: Driver) -> None:
    """خروج صريح: يسقط من الفهرس فوراً بلا انتظار انقضاء الحضور.

    **ويُلغى رمزُ الحضور هنا لا في الراوتر** (§23.4): هذا هو البابُ الذي تمرّ
    به كلُّ طرق إنهاء الاستقبال — ضغطةُ الكبتن، وإغلاقُ المقبس، ومسحُ
    الاشتراك. **وحارسٌ في الراوتر بابٌ يُنسى في الباب الثاني**، وهي القاعدةُ
    نفسُها التي وضعت `blocks_new_ride` في `rides.request_ride`.
    """
    country_code = await session.scalar(
        select(User.country_code).where(User.id == driver.user_id)
    )
    driver.is_online = False
    await geo.go_offline(redis, driver_id=driver.id, country_code=country_code)
    await presence_token.revoke(redis, user_id=driver.user_id)


async def report_location(
    redis: Redis,
    context: PresenceContext,
    *,
    lat: float,
    lng: float,
    heading: float | None,
) -> None:
    """بث موقع واحد: يحدّث Redis GEO ويصل راكبَه المُسنَد إن كان في رحلة.

    البث غير مشروط برحلة جارية لأن قناة الموقع خاصة بالكبتن، ولا يشترك فيها
    إلا راكبٌ أسندت له القاعدة هذا الكبتن — فلا تسريب.

    ومن هنا وحده يُلتقط مسار الرحلة (SPEC القسم 5.7): البثّ هو مصدر النقاط،
    فوضعُ الالتقاط في مسارٍ آخر يعني مساراً ناقصاً لكبتنٍ يبث من القناة
    الأخرى. `route.capture` يعرف بنفسه متى لا يكتب شيئاً.

    **وعمرُ الحضور من سياسة البثّ** (§٧٥-ج) لا ثابتٍ هنا — والتطبيقُ الأقدمُ الذي يبثّ كلَّ ثلاث ثوانٍ يمرّ من هنا كما كان.
    """
    policy = await broadcast.current_policy(redis)
    await geo.update_location(
        redis,
        driver_id=context.driver_id,
        country_code=context.country_code,
        lat=lat,
        lng=lng,
        heading=heading,
        vehicle_category=context.vehicle_category,
        skin=context.skin,
        ttl=policy.presence_ttl,
    )
    await route.capture(
        redis, driver_id=context.driver_id, lat=lat, lng=lng, heading=heading
    )
    await events.publish_driver_location(
        redis, driver_id=context.driver_id, lat=lat, lng=lng, heading=heading
    )
    # **«الكبتن يقترب»** (§61-ي/١١): قراءةُ مفتاحٍ واحدٍ لمن لا رحلةَ له — ولا يُسقط البثَّ بسقوطه
    await approach.check(redis, driver_id=context.driver_id, lat=lat, lng=lng)


async def report_heartbeat(redis: Redis, context: PresenceContext) -> bool:
    """**نبضةُ «ما زلتُ متّصلاً»** (§٧٥-ج) — يجدّد الحضورَ بلا موقع. و`False`: الحضورُ انقضى فليرسلِ التطبيقُ موقعَه الآن."""
    policy = await broadcast.current_policy(redis)
    return await geo.touch(redis, driver_id=context.driver_id, ttl=policy.presence_ttl)


async def report_points(
    redis: Redis,
    context: PresenceContext,
    *,
    points: list[route.TripPoint],
    seq: int | None,
) -> bool:
    """**دفعةُ نقاط الرحلة** (§٧٥-ج): كلُّها إلى مسار الأجرة، **وآخرُها هو الموقعُ الحاليّ** (الفهرس والحضور والاقتراب)، **وكلُّها
    للراكب** فيعيدها على خريطته بنعومة. يعيد `True` إن قُبلت فيُقَرّ بها.

    **والترتيبُ مقصود**: المسارُ أوّلاً — فإن تعذّرت كتابتُه لم يُقَرّ بالدفعة وأعادها التطبيق، **ولا يُحدَّث الموقعُ الحاليُّ بنقطةٍ
    لم تُحفظ في الأجرة**.
    """
    if not points:
        return True
    accepted = await route.capture_points(redis, driver_id=context.driver_id, points=points, seq=seq)
    if not accepted:
        return False
    ordered = sorted(points, key=lambda p: p.t)
    last = ordered[-1]
    policy = await broadcast.current_policy(redis)
    await geo.update_location(
        redis,
        driver_id=context.driver_id,
        country_code=context.country_code,
        lat=last.lat,
        lng=last.lng,
        heading=last.heading,
        vehicle_category=context.vehicle_category,
        skin=context.skin,
        ttl=policy.presence_ttl,
    )
    await events.publish_driver_location(
        redis,
        driver_id=context.driver_id,
        lat=last.lat,
        lng=last.lng,
        heading=last.heading,
        path=[(p.lat, p.lng, p.heading, last.t - p.t) for p in ordered],
    )
    await approach.check(redis, driver_id=context.driver_id, lat=last.lat, lng=last.lng)
    return True


async def nearby_available(
    redis: Redis,
    session: AsyncSession,
    *,
    country_code: CountryCode,
    lat: float,
    lng: float,
    radius_km: float | None = None,
    max_count: int | None = None,
    rider: User | None = None,
    test: bool | None = None,
) -> list[geo.DriverPresence]:
    """الكباتن المتاحون حول الراكب لعرضهم على خريطته (SPEC القسم 10).

    «المتاحون فقط»: أونلاين + معتمد + اشتراك ساري + بلا رحلة — بنفس استدعاء
    `dispatch.eligible_driver_ids`، فمن لا يصلح للإسناد لا يُعرض سيارةً متاحة.

    **وتفضيلُ الجنس داخلٌ في «المتاح»** (المرحلة 10-ج) بتفضيل ملف الراكبة
    الافتراضي — لا تفضيلِ رحلةٍ لم تُطلب بعد. فخريطةٌ ترسم سيارةً لن تأتيَ
    أسوأُ من خريطةٍ فارغة: الأولى تُقرأ وعداً، والثانية تُقرأ واقعاً.

    **وعالمُ التجربة داخلٌ فيه كذلك** (SPEC §٦٥-ج): وسمُ الراكب إن مُرِّر،
    وإلا `test` لمن ينظر بلا راكب (كبتنٌ إلى زملائه، و«الطلبُ مرتفع» حوله)،
    **وإلا فحقيقيّ** — فلا يُرسم كبتنُ تجربةٍ على خريطةِ أحدٍ لم يُسمَّ عالمُه.
    """
    from app.services import dispatch, map_settings

    # **حدُّ الخريطةِ من إعداداتها لا من ثوابت التوزيع** (قرارُ المالك
    # 2026-08-22): `geo.SEARCH_RADIUS_KM` قاعدةُ مواصفةٍ للتوزيع، وهذه تفضيلُ
    # عرضٍ لسوق. وخلطُهما يجعل حقلَ عرضٍ في اللوحة يغيّر **من يصله الطلب**.
    limits = await map_settings.limits_for(session, country_code)
    presences = await geo.nearby(
        redis,
        country_code=country_code,
        lat=lat,
        lng=lng,
        radius_km=limits.radius_km if radius_km is None else radius_km,
        limit=limits.max_count if max_count is None else max_count,
    )
    if not presences:
        return []

    match = (
        None
        if rider is None
        else await dispatch.gender_match(
            session,
            country_code=country_code,
            rider_gender=rider.gender,
            preference=rider.ride_gender_preference,
        )
    )

    world = rider.is_test if rider is not None else bool(test)

    available: list[geo.DriverPresence] = []
    for category in {presence.vehicle_category for presence in presences}:
        of_category = [p for p in presences if p.vehicle_category == category]
        eligible = await dispatch.eligible_driver_ids(
            session,
            [p.driver_id for p in of_category],
            category,
            gender=match,
            test=world,
        )
        available.extend(p for p in of_category if p.driver_id in eligible)

    available.sort(key=lambda presence: presence.distance_km)
    # **والسقفُ يُطبَّق بعد الترشيح لا قبله**: قصُّ الخمسين قبل استبعاد غير
    # المؤهّلين يعطي خريطةً بثلاث سياراتٍ في سوقٍ فيه ثلاثون متاحاً — يُقصّ
    # الحاضرون فيبقى المؤهّلون قلّةً بلا سبب
    ceiling = limits.max_count if max_count is None else max_count
    return available[:ceiling]


# ------------------------------------------------- خريطةُ الراكب مشتركةً بالخلايا (§٧٥-د/٢)

#: **ضلعُ الخليّة** (~٢٫٢ كم) — كلُّ راكبٍ في الخليّة يقرأ حسابَها الواحد
NEARBY_CELL_DEG = 0.02
#: **عمرُ حساب الخليّة** — دون دورة البثّ (٥ ثوانٍ)، فلا يرى راكبٌ صورةً أقدمَ من دورةٍ واحدة
NEARBY_CELL_SECONDS = 4
#: **وحدودُ العرض من القاعدة كلَّ نصف دقيقة** لا مع كلِّ إطار — تفضيلُ عرضٍ يغيّره المشرفُ نادراً
_MAP_LIMITS_SECONDS = 30.0
_map_limits: dict[str, tuple[float, object]] = {}


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rad = math.radians
    h = math.sin(rad(lat2 - lat1) / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(rad(lng2 - lng1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


async def _limits(session: AsyncSession, country_code: CountryCode):
    from app.services import map_settings

    key = CountryCode(country_code).value
    cached = _map_limits.get(key)
    if cached is not None and time.monotonic() - cached[0] < _MAP_LIMITS_SECONDS:
        return cached[1]
    limits = await map_settings.limits_for(session, country_code)
    _map_limits[key] = (time.monotonic(), limits)
    return limits


def _encode(presence: geo.DriverPresence) -> dict:
    data = dataclasses.asdict(presence)
    data["driver_id"] = str(presence.driver_id)
    data["vehicle_category"] = VehicleCategory(presence.vehicle_category).value
    if presence.skin is not None:
        data["skin"]["skin_id"] = str(presence.skin.skin_id)
    return data


def _decode(data: dict) -> geo.DriverPresence:
    skin = data.get("skin")
    return geo.DriverPresence(
        driver_id=uuid.UUID(data["driver_id"]),
        lat=data["lat"],
        lng=data["lng"],
        heading=data.get("heading"),
        vehicle_category=VehicleCategory(data["vehicle_category"]),
        distance_km=data["distance_km"],
        skin=None if not skin else geo.MapSkin(**(skin | {"skin_id": uuid.UUID(skin["skin_id"])})),
        at=data.get("at"),
        seen=data.get("seen"),
    )


async def nearby_for_map(
    redis: Redis,
    session: AsyncSession,
    *,
    country_code: CountryCode,
    lat: float,
    lng: float,
    rider: User,
) -> list[geo.DriverPresence]:
    """**ما يُرسم على خريطة الراكب كلَّ خمس ثوانٍ — بحسابٍ مشتركٍ لكلِّ خليّة** (§٧٥-د/٢).

    **العلّةُ مقيسة** (المرحلة ١، ٢٠٢٦-١٠-١٣): كلُّ راكبٍ مفتوحِ التطبيق كان يكلّف القاعدةَ ثلاثةَ استعلاماتٍ كلَّ خمس ثوانٍ (حدودُ الخريطة ·
    شرطُ الجنس · الأهليّة) — **فاستهلكت القاعدةُ نواتين وربعاً عند ٢٠٠ راكب**. فالآن: **المؤهَّلون حول مركز الخليّة** بنصف قطر الخريطة مزيداً
    بنصف قُطر الخليّة يُحسبون **مرّةً لكلِّ خليّةٍ وعالمٍ وشرطِ جنسٍ كلَّ `NEARBY_CELL_SECONDS`** في Redis (فتشترك فيه العمليّاتُ كلُّها)، **ثمّ
    لكلِّ راكبٍ من نقطته هو**: المسافةُ والحدُّ والترتيبُ والسقف — **فالنتيجةُ نتيجةُ `nearby_available` نفسُها** (القاعدةُ نفسُها في الأهليّة،
    وقِيس التطابقُ في `test_nearby_cells.py`).
    """
    limits = await _limits(session, country_code)
    cell_lat = round(lat / NEARBY_CELL_DEG) * NEARBY_CELL_DEG
    cell_lng = round(lng / NEARBY_CELL_DEG) * NEARBY_CELL_DEG
    world = int(bool(rider.is_test))
    gender = rider.gender.value if rider.gender is not None else "-"
    preference = getattr(rider.ride_gender_preference, "value", rider.ride_gender_preference) or "-"
    key = (
        f"nearby:cell:{CountryCode(country_code).value}:{world}:{gender}:{preference}:"
        f"{cell_lat:.3f}:{cell_lng:.3f}"
    )
    raw = await redis.get(key)
    if raw is None:
        # نصفُ قُطر الخليّة (أبعدُ نقطةٍ فيها عن مركزها) — فكلُّ سيّارةٍ في نصف قطر أيِّ راكبٍ فيها داخلةٌ في الحساب
        margin_km = NEARBY_CELL_DEG * 111.32 * math.sqrt(2) / 2
        presences = await nearby_available(
            redis,
            session,
            country_code=country_code,
            lat=cell_lat,
            lng=cell_lng,
            radius_km=limits.radius_km + margin_km,
            max_count=limits.max_count * 6,
            rider=rider,
        )
        raw = json.dumps([_encode(p) for p in presences])
        await redis.set(key, raw, ex=NEARBY_CELL_SECONDS)
    mine: list[geo.DriverPresence] = []
    for presence in map(_decode, json.loads(raw)):
        distance = _km(lat, lng, presence.lat, presence.lng)
        if distance <= limits.radius_km:
            mine.append(dataclasses.replace(presence, distance_km=round(distance, 3)))
    mine.sort(key=lambda presence: presence.distance_km)
    return mine[: limits.max_count]


def anonymous_ref(driver_id: uuid.UUID, salt: str) -> str:
    """بديل مجهول لهوية الكبتن على خريطة الراكب.

    SPEC القسم 10 يوجب تجهيل هذه المواقع تماماً، لكن تنعيم حركة الأيقونات في
    الواجهة يحتاج مفتاحاً يربط السيارة بين تحديث وآخر. الحل بديلٌ مشتق بمِلح
    خاص بكل اتصال/طلب: ثابت داخل الجلسة الواحدة، مختلف في التالية — فلا
    يُتتبع كبتن عبر الزمن ولا يُستدل على هويته.
    """
    return hashlib.blake2s(
        str(driver_id).encode(), key=salt.encode()[:32], digest_size=8
    ).hexdigest()


# ------------------------------------------------- اعتماد الكبتن (8-ب)


async def lock(session: AsyncSession, driver: Driver) -> Driver:
    """يقفل صفَّ الكبتن **قبل أن يُقرأ حالتُه ليُقرَّر عليها**.

    قراءةُ الحالة ثم الكتابةُ عليها ليست ذرّيةً وحدها تحت READ COMMITTED —
    والخسارةُ هنا ليست قيداً مكرَّراً بل **إيقافاً يُلغى**: مشرفٌ يوقف كبتناً
    (`suspended`) في اللحظة التي يستبدل فيها هو مستنداً أو يغيّر لوحته يجد
    فعلَه مكتوباً فوق قراره — إذ يكتب المسارُ `pending` عن `approved` قرأها
    قبل الإيقاف، فيعود الموقوفُ إلى طابور المراجعة كأن شيئاً لم يكن.

    والقفلُ **بعد** قفل صفوف الأبناء لا قبلها حيث يسبقه حفظُ ملفٍ يصل من
    الشبكة: لا يُحتجز صفٌّ عبر رفعٍ يملي العميلُ طولَه.
    """
    await session.refresh(driver, with_for_update=True)
    return driver


async def set_status(
    session: AsyncSession,
    *,
    driver: Driver,
    status: DriverStatus,
    actor: User | None,
    reason: str | None = None,
) -> Driver:
    """يغيّر حالة الكبتن ويسجّلها في التدقيق. الـ commit مسؤولية الراوتر.

    `actor` يقبل `None` لتغييرٍ لم يقرره مشرف: استبدالُ الكبتن لمستندٍ مطلوب
    يعيده `pending` من تلقاء الفعل لا من قرار أحد (المرحلة 9-ب). والقيدُ
    يُكتب في الحالتين — سؤال «لماذا سقط اعتمادُه؟» يُسأل بعد شهر.
    """
    from app.models.enums import AuditAction
    from app.services import audit

    driver.status = status
    details: dict[str, str] = {"status": status.value}
    if reason is not None:
        details["reason"] = reason

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="driver",
        entity_id=driver.id,
        details=details,
    )
    await session.flush()
    return driver


async def approve(session: AsyncSession, *, driver: Driver, actor: User) -> Driver:
    """اعتماد الكبتن — **بحارسين لا واحد**.

    **الأول: رقمٌ مُثبت مهما كان مفتاح التحقق.** رقمُ الكبتن هو ما يستلم عليه
    حوالات كليك (SPEC القسم 6/9) وما تصله عليه تنبيهاتُ الاشتراك؛ فاعتمادُ من
    لا نعرف أنه يملكه إرسالُ مالٍ إلى رقمٍ مجهول. ولذلك لا يعفيه إطفاء
    `otp_verification_enabled`: ذاك يعفي **التسجيل** ليمر الناس، لا الاعتماد
    ليمر المال.

    **والثاني (المرحلة 9-ب): مستنداتٌ مطلوبةٌ مقبولةٌ كلها.** SPEC القسم 12/1
    يقول «لا يُعتمد الكبتن قبل مراجعة الإدارة للمستندات»، والقسم 13/2 يجعل
    المراجعة قبولاً أو رفضاً لكل مستند. وبغير هذا الحارس تصير المراجعة
    عادةً لا شرطاً: زرُّ «اعتماد» يعمل والمستنداتُ فارغة، وهو ما كان يقع
    فعلاً قبل هذه المرحلة.

    وليس بينهما ترتيبٌ ذو معنى فيُفحص الأرخص أولاً.
    """
    from app.services import documents, verification

    owner = await session.get(User, driver.user_id)
    verification.require_verified(owner)

    missing = await documents.missing_required(session, driver.id)
    if missing:
        names = "، ".join(documents.label_for(item) for item in missing)
        raise DocumentsIncomplete(f"مستندات لم تُعتمد بعد: {names}")

    return await set_status(
        session, driver=driver, status=DriverStatus.APPROVED, actor=actor
    )


async def parties_of(
    session: AsyncSession, driver_ids: "Sequence[uuid.UUID]"
) -> "dict[uuid.UUID, DriverPartyOut]":
    """كباتنُ صفحةٍ باسمهم ورقمهم — **استعلامٌ ثانٍ لا ضمٌّ** (§٤٧٫١٩).

    **والعلّةُ هي علّةُ `ride_log.payment_summaries` بحرفها**: ضمٌّ يضاعف صفَّ
    الطلب بعدد ما يعلّق به، **فتصير صفحةُ الخمسين أقلَّ من خمسين صامتةً**.
    واستعلامٌ واحدٌ على مجموعة المعرّفات يجيب الصفحةَ كلَّها.

    **ولا لوحةَ هنا**: لا صفَّ من الصفوف التي تستعمله يعرض مركبة، **وحقلٌ
    يُحسب ولا يقرؤه أحدٌ هو ما يمسكه `check:readers`**.
    """
    from app.schemas.party import DriverPartyOut

    wanted = {driver_id for driver_id in driver_ids}
    if not wanted:
        return {}
    rows = (
        await session.scalars(
            select(Driver)
            .where(Driver.id.in_(wanted))
            .options(selectinload(Driver.user))
        )
    ).all()
    return {row.id: DriverPartyOut.of_driver(row) for row in rows}
