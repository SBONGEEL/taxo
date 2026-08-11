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


@dataclass(frozen=True, slots=True)
class PendingRide:
    """طلبٌ ينتظر كبتناً — نقطةُ انطلاقه وكم مضى عليه."""

    ride_id: uuid.UUID
    lat: float
    lng: float
    status: RideStatus
    created_at: object


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
        lat, lng, heading, category = live[driver.id]
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
