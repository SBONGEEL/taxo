"""حضور الكباتن اللحظي على Redis GEO (SPEC القسم 2/10).

الموقع اللحظي لا يُكتب في القاعدة: يتغير كل ثلاث ثوانٍ لكل كبتن أونلاين ولا
قيمة تاريخية له، فمصدره الوحيد Redis. أعمدة `geography` في `rides` وحدها
تخزين دائم.

لكل كبتن مفتاحان:

- `geo:drivers:{country}` — الـ zset الجغرافي الذي تبحث فيه خوارزمية التوزيع.
  مفصول بالدولة لأن البحث لا يعبر الحدود أصلاً، فلا داعي لفهرس واحد ضخم.
- `geo:presence:{driver_id}` — hash بالاتجاه وفئة المركبة، **بعمر محدود**
  (`PRESENCE_TTL_SECONDS`). انقضاؤه معناه أن الكبتن صمت: يسقط من كل نتيجة بحث.

سبب الفصل: أعضاء الـ zset لا تقبل TTL في Redis، فجعلنا الحضور في مفتاح يقبله
وصار الـ zset يُنظَّف كسولاً — كل بحث يمر على عضو بلا حضور يزيله.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from redis.asyncio import Redis

from app.models.enums import CountryCode, VehicleCategory

# صمتٌ أطول من هذا يعني كبتناً غير متاح. SPEC القسم 5 يعتبر انقطاع الكبتن
# أكثر من 60 ثانية حدثاً يستحق التنبيه، فهو الحد الطبيعي لعمر الحضور.
PRESENCE_TTL_SECONDS = 60

# نصف قطر البحث الابتدائي ثم الموسّع (SPEC القسم 5.3)
SEARCH_RADIUS_KM = 3.0
MAX_SEARCH_RADIUS_KM = 7.0

# سقف ما يُقرأ من الـ zset في البحث الواحد — التوزيع يحتاج الأقرب لا الجميع
SEARCH_LIMIT = 50


def geo_key(country_code: CountryCode) -> str:
    return f"geo:drivers:{CountryCode(country_code).value}"


def presence_key(driver_id: uuid.UUID | str) -> str:
    return f"geo:presence:{driver_id}"


@dataclass(frozen=True, slots=True)
class DriverPresence:
    """كبتن حاضر الآن كما تراه خوارزمية التوزيع وخريطة الراكب."""

    driver_id: uuid.UUID
    lat: float
    lng: float
    heading: float | None
    vehicle_category: VehicleCategory
    distance_km: float


async def update_location(
    redis: Redis,
    *,
    driver_id: uuid.UUID,
    country_code: CountryCode,
    lat: float,
    lng: float,
    heading: float | None,
    vehicle_category: VehicleCategory,
) -> None:
    """بث موقع واحد: يحدّث الفهرس الجغرافي ويجدّد عمر الحضور."""
    key = presence_key(driver_id)
    pipe = redis.pipeline()
    pipe.geoadd(geo_key(country_code), (lng, lat, str(driver_id)))
    pipe.hset(
        key,
        mapping={
            "heading": "" if heading is None else str(heading),
            "vehicle_category": VehicleCategory(vehicle_category).value,
        },
    )
    pipe.expire(key, PRESENCE_TTL_SECONDS)
    await pipe.execute()


async def go_offline(
    redis: Redis, *, driver_id: uuid.UUID, country_code: CountryCode
) -> None:
    """خروج صريح — لا ننتظر انقضاء العمر."""
    pipe = redis.pipeline()
    pipe.zrem(geo_key(country_code), str(driver_id))
    pipe.delete(presence_key(driver_id))
    await pipe.execute()


async def nearby(
    redis: Redis,
    *,
    country_code: CountryCode,
    lat: float,
    lng: float,
    radius_km: float = SEARCH_RADIUS_KM,
    limit: int = SEARCH_LIMIT,
) -> list[DriverPresence]:
    """الكباتن الحاضرون ضمن نصف القطر، مرتبين من الأقرب.

    «حاضر» هنا معناه أن مفتاح حضوره لم ينقضِ؛ أما «مؤهل للإسناد» (معتمد،
    أونلاين، بلا رحلة) فتفحصه `dispatch` في القاعدة.
    """
    rows = await redis.geosearch(
        geo_key(country_code),
        longitude=lng,
        latitude=lat,
        radius=radius_km,
        unit="km",
        sort="ASC",
        count=limit,
        withdist=True,
        withcoord=True,
    )
    if not rows:
        return []

    pipe = redis.pipeline()
    for row in rows:
        pipe.hgetall(presence_key(row[0]))
    presence_rows = await pipe.execute()

    found: list[DriverPresence] = []
    stale: list[str] = []

    for row, data in zip(rows, presence_rows, strict=True):
        member, distance, (member_lng, member_lat) = row[0], row[1], row[2]
        if not data:
            stale.append(member)  # صمت أطول من العمر المسموح
            continue
        try:
            driver_id = uuid.UUID(member)
            category = VehicleCategory(data["vehicle_category"])
        except (KeyError, ValueError):
            stale.append(member)  # عضو تالف — يُنظَّف كما يُنظَّف المنقضي
            continue

        raw_heading = data.get("heading") or ""
        found.append(
            DriverPresence(
                driver_id=driver_id,
                lat=float(member_lat),
                lng=float(member_lng),
                heading=float(raw_heading) if raw_heading else None,
                vehicle_category=category,
                distance_km=round(float(distance), 3),
            )
        )

    if stale:
        await redis.zrem(geo_key(country_code), *stale)

    return found
