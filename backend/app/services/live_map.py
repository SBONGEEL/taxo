"""الخريطة الحيّة في اللوحة (SPEC القسم 13/1).

**هذه هي الطريق الوحيد الذي تخرج منه هويةُ كبتنٍ مع موقعه**، ولذلك يحكمها
ثلاثة قيود مكتوبةٌ هنا ومفروضةٌ في الراوتر:

1. **لـ admin وحده** لا `support`: القسم 13/8 يعطي الدعمَ قراءةً ومعالجةَ
   نزاعات، ومعرفةُ أين يقف كلُّ كبتنٍ الآن ليست منهما — هي معلومةٌ عن أشخاص
   قبل أن تكون تقريرَ تشغيل.
2. **يُسجَّل من قرأها** في سجل التدقيق. قراءةٌ تُسجَّل نادرة في هذا النظام،
   وهذه منها: من يفتح خريطةَ مواقع الناس يُسأل عنها. والقيدُ **مخنوقٌ بنافذة**
   (`AUDIT_WINDOW_SECONDS`) لأن الشاشة تستعلم كل بضع ثوانٍ، وسجلٌّ يمتلئ بمئة
   صفٍّ للجلسة الواحدة يخفي القرارات الحقيقية بينها. فجلسةُ مراقبةٍ = قيدٌ واحد.
3. **ولا يُعاد استعمال هذا التمثيل في أيّ واجهةٍ أخرى**: خريطةُ الراكب تمر
   بـ`drivers.nearby_available` و`anonymous_ref` وتبقى مجهّلةً كما يفرض القسم
   10 — إحداثياتٌ واتجاهٌ وفئةُ مركبةٍ لا غير. الفرقُ بين الدالتين مقصود، ومن
   يوحّدهما «تبسيطاً» يسرّب الهوية إلى تطبيق الراكب.

والموقعُ من Redis والهويةُ من القاعدة: لا عمودَ موقعٍ يُكتب لأجل هذه الشاشة.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode, RideStatus, VehicleCategory
from app.models.ride import Ride
from app.models.user import User
from app.services import audit, geo

# نافذةُ خنق قيد التدقيق: جلسةُ مراقبةٍ واحدة تكتب قيداً واحداً
AUDIT_WINDOW_SECONDS = 900
_AUDIT_KEY = "audit:live_map:{admin_id}:{country}"
_AUDIT_DRIVER_KEY = "audit:live_map:driver:{admin_id}:{driver_id}"

# ما تعرضه الخريطة من الطلبات المعلّقة — الرحلة قبل أن يقبلها أحد
PENDING_STATUSES = (RideStatus.REQUESTED, RideStatus.SEARCHING)


@dataclass(frozen=True, slots=True)
class LiveDriver:
    """كبتنٌ حاضرٌ الآن **بهويته** — تمثيلٌ لا يخرج إلا إلى اللوحة."""

    driver_id: uuid.UUID
    name: str
    phone: str
    lat: float
    lng: float
    heading: float | None
    vehicle_category: VehicleCategory
    plate_number: str | None
    on_ride: bool
    ride_id: uuid.UUID | None
    # **ثلاثُ حالاتٍ لا اثنتان** (قرارُ المالك 2026-08-22): «متاحٌ» و«في رحلة»
    # كانتا كلَّ ما تقوله اللوحة، **و«يوشك أن يختفي» ليست إحداهما**. مفتاحُ
    # الحضور عمرُه ستون ثانية، فكبتنٌ آخرُ بثٍّ له قبل خمسٍ وخمسين **يظهر
    # كالحاضر تماماً ثم يختفي بلا أن يتحرك شيء** — فيُقرأ اختفاؤه عطباً في
    # اللوحة، أو تُتّخذ عليه قرارٌ وهو غير موجود
    state: str
    seconds_since_update: int | None


@dataclass(frozen=True, slots=True)
class PendingRide:
    """طلبٌ ينتظر كبتناً — نقطةُ انطلاقه وكم مضى عليه."""

    ride_id: uuid.UUID
    lat: float
    lng: float
    status: RideStatus
    created_at: object


# **حدُّ «الشحوب» مشتقٌّ من عمر المفتاح لا مختارٌ بالذوق**: ثلثا العمر. فما
# جاوزه بقيت له ثلثٌ من حياته، **وهو الوقتُ الذي يصلح للتنبيه** — وأيُّ رقمٍ
# ثابتٍ هنا يفترق عن `PRESENCE_TTL_SECONDS` يومَ يتغيّر، فيصير الشحوبُ إمّا
# دائماً وإمّا مستحيلاً
STALE_AFTER_SECONDS = (geo.PRESENCE_TTL_SECONDS * 2) // 3


def _state_of(*, on_ride: bool, age: int | None) -> str:
    """**«في رحلة» يسبق «شاحب»**: الأولى واقعةٌ في القاعدة، والثاني ظنٌّ من
    صمتٍ قصير — وكبتنٌ في رحلةٍ صمت دقيقةً في نفقٍ لا يُقرأ «مفقوداً»."""
    if on_ride:
        return "on_ride"
    if age is None or age >= STALE_AFTER_SECONDS:
        return "stale"
    return "available"


async def drivers_now(
    redis: Redis, session: AsyncSession, *, country: CountryCode
) -> list[LiveDriver]:
    """كلُّ من له حضورٌ حيّ في الدولة، بهويته وحالِ رحلته.

    ولا فلترةَ بالأهلية هنا خلافاً لخريطة الراكب: المشرف يريد أن يرى **من في
    الشارع**، بمن فيهم من انقضى اشتراكه أو مَن في رحلة — وذلك بالضبط ما تخفيه
    خريطةُ الراكب لأنها تعرض «من يمكنه أن يأتيك».
    """
    members = await redis.zrange(geo.geo_key(country), 0, -1, withscores=False)
    if not members:
        return []

    positions = await redis.geopos(geo.geo_key(country), *members)
    pipe = redis.pipeline()
    for member in members:
        pipe.hgetall(geo.presence_key(member))
    presence_rows = await pipe.execute()

    live: dict[uuid.UUID, tuple[float, float, str | None, str | None]] = {}
    for member, position, data in zip(members, positions, presence_rows, strict=True):
        if not data or position is None:
            continue  # صمتٌ أطول من عمر المفتاح — حاضرٌ في الفهرس لا في الواقع
        try:
            driver_id = uuid.UUID(member)
        except ValueError:  # pragma: no cover - عضوٌ تالف
            continue
        live[driver_id] = (
            float(position[1]),
            float(position[0]),
            data.get("heading") or None,
            data.get("vehicle_category"),
            int(data["at"]) if (data.get("at") or "").isdigit() else None,
        )

    if not live:
        return []

    rows = (
        await session.scalars(
            select(Driver)
            .options(selectinload(Driver.user), selectinload(Driver.vehicles))
            .join(User, Driver.user_id == User.id)
            .where(Driver.id.in_(live.keys()), User.country_code == country)
        )
    ).all()

    result: list[LiveDriver] = []
    for driver in rows:
        lat, lng, heading, category, at = live[driver.id]
        age = None if at is None else max(0, int(time.time()) - at)
        vehicle = driver.vehicles[0] if driver.vehicles else None
        result.append(
            LiveDriver(
                driver_id=driver.id,
                name=driver.user.name,
                phone=driver.user.phone,
                lat=lat,
                lng=lng,
                heading=float(heading) if heading else None,
                vehicle_category=(
                    VehicleCategory(category)
                    if category
                    else (vehicle.category if vehicle else VehicleCategory.ECONOMY)
                ),
                plate_number=vehicle.plate_number if vehicle else None,
                on_ride=driver.current_ride_id is not None,
                ride_id=driver.current_ride_id,
                state=_state_of(
                    on_ride=driver.current_ride_id is not None, age=age
                ),
                seconds_since_update=age,
            )
        )
    return result


async def pending_rides(
    session: AsyncSession, *, country: CountryCode
) -> list[PendingRide]:
    """الطلبات التي لم يقبلها أحدٌ بعد — «طلبات بانتظار سائق» في التصميم."""
    rows = (
        await session.scalars(
            select(Ride)
            .where(Ride.country_code == country, Ride.status.in_(PENDING_STATUSES))
            .order_by(Ride.created_at)
        )
    ).all()
    return [
        PendingRide(
            ride_id=ride.id,
            lat=ride.pickup_lat,
            lng=ride.pickup_lng,
            status=ride.status,
            created_at=ride.created_at,
        )
        for ride in rows
    ]


@dataclass(frozen=True, slots=True)
class DriverPosition:
    """موضعُ كبتنٍ واحدٍ الآن — **ولا كائنَ يعني صمتاً لا موضعاً عند الصفر**.

    **ولا `state` هنا خلافاً لـ`LiveDriver`**: تلك ثلاثيّةٌ تجيب «أمتفرّغٌ أم
    في رحلةٍ أم شحُب بثُّه»، **وهذه لا تُقرأ إلا وصاحبُها في رحلة** — فتجيب
    الثلاثيّةُ «في رحلة» دائماً وتبتلع السؤالَ الوحيد الذي يُسأل هنا: **أطازجٌ
    هذا الدبّوس؟** فيُنشر `stale` عارياً ومعه عمرُه.

    **ويُحسب في الخلفية لا في اللوحة** للعلّة المكتوبة على `LiveDriverOut`
    نفسِه: لوحةٌ تقارن الثواني بعتبةٍ من عندها **تفترق عن الخلفية أوّلَ ما
    يتغيّر `PRESENCE_TTL_SECONDS`، ولا شيءَ يفشل**.
    """

    lat: float
    lng: float
    seconds_since_update: int | None
    stale: bool


async def position_of(
    redis: Redis, *, driver_id: uuid.UUID, country: CountryCode
) -> DriverPosition | None:
    """آخرُ موضعٍ بثّه كبتنٌ بعينه — **من البثِّ القائم لا من بنيةٍ ثانية**.

    **والحياةُ من مفتاح الحضور والموضعُ من الفهرس**، كما في
    `geo.last_position` بحرفه: الفهرسُ الجغرافيُّ لا يقبل عمراً لعضوٍ فيه،
    **فعضوٌ باقٍ فيه بلا مفتاحِ حضورٍ موضعٌ قديمٌ يُقرأ حاضراً**.

    **ولمَ لا يُنادى `geo.last_position` نفسُه**: تلك تجيب «أين» ولا تجيب
    «منذ متى» — **ودبّوسٌ بلا عمره هو العطبُ الذي أنشأ الحالةَ الثالثة في هذه
    الخدمة** (قرارُ المالك 2026-08-22): موضعٌ عمرُه خمسٌ وخمسون ثانية يُرسم
    كموضعِ اللحظة، ثمّ يختفي بلا أن يتحرّك شيء.
    """
    data = await redis.hgetall(geo.presence_key(driver_id))
    if not data:
        return None
    positions = await redis.geopos(geo.geo_key(country), str(driver_id))
    if not positions or positions[0] is None:
        return None
    lng, lat = positions[0]
    at = int(data["at"]) if (data.get("at") or "").isdigit() else None
    age = None if at is None else max(0, int(time.time()) - at)
    return DriverPosition(
        lat=float(lat),
        lng=float(lng),
        seconds_since_update=age,
        stale=age is None or age >= STALE_AFTER_SECONDS,
    )


async def record_access(
    session: AsyncSession,
    redis: Redis,
    *,
    admin: User,
    country: CountryCode,
) -> bool:
    """يكتب قيدَ تدقيقٍ لفتح الخريطة — مرةً لكل جلسة مراقبة.

    الخنقُ بمفتاح Redis لا بعمود: «هل سُجّل لهذا المشرف قريباً؟» سؤالٌ عابر
    عمرُه دقائق، وقيدُ التدقيق نفسه هو السجل الدائم. ويعيد `True` حين يكتب،
    فيظهر في الاختبار أن الجلسة الواحدة قيدٌ واحد لا مئة.
    """
    key = _AUDIT_KEY.format(admin_id=admin.id, country=country.value)
    first = await redis.set(key, "1", ex=AUDIT_WINDOW_SECONDS, nx=True)
    if not first:
        return False

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.READ,
        entity_type="live_map",
        entity_id=None,
        details={"country_code": country.value},
    )
    await session.commit()
    return True


async def record_driver_access(
    session: AsyncSession,
    redis: Redis,
    *,
    admin: User,
    driver_id: uuid.UUID,
) -> bool:
    """قيدُ تدقيقٍ لقراءة موضعِ **كبتنٍ بعينه** — مرةً لكلِّ جلسة مراقبة.

    **ولا يُعاد استعمالُ `record_access`**، ومفتاحُ الخنق غيرُ مفتاحها: قيدٌ
    يقول «قرأ الخريطةَ الحيّة للأردن» عمّن فتح ملفَّ كبتنٍ واحد **يصف فعلاً
    لم يقع** — وسجلُّ التدقيق يُقرأ بعد شهرٍ ليقال ماذا جرى، **فقيدٌ أوسعُ من
    الفعل كقيدٍ أضيقَ منه: كلاهما يكذب**. ولو تشارك المفتاحان لَابتلع أحدُهما
    الآخرَ في نافذته: من فتح الخريطةَ ثمّ ملفَّ كبتنٍ لم يُكتب لفتحِ الملفّ
    قيدٌ أصلاً.

    **والخنقُ بنافذة `AUDIT_WINDOW_SECONDS` نفسِها**: القسمُ يستعلم كلَّ خمس
    ثوانٍ كالخريطة، **وسجلٌّ فيه مئتا صفٍّ لساعةِ مراقبةٍ يخفي القرارات
    بينها**.
    """
    key = _AUDIT_DRIVER_KEY.format(admin_id=admin.id, driver_id=driver_id)
    first = await redis.set(key, "1", ex=AUDIT_WINDOW_SECONDS, nx=True)
    if not first:
        return False

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.READ,
        entity_type="driver_live",
        entity_id=driver_id,
    )
    await session.commit()
    return True
