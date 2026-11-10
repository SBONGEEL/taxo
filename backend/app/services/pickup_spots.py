"""**نقاطُ التقاطٍ ذكيّة** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١١، SPEC §٩٧/١١).

قبل الطلب يُقترح على الراكب **أقربُ نقطةٍ سهلة** إلى دبّوسه، **فيقبلها أو يُبقي دبّوسه**. ومصدران، بهذا الترتيب:

1. **نقاطُ المالك** — مكانٌ في «الأماكن» بفئة `pickup` (بوّابة، زاوية، جانبُ الشارع الرئيسيّ) في مدى `RADIUS_M`؛ الأقربُ يُقترح باسمه.
2. **الالتقاطاتُ السابقة** — **أين بدأت الرحلاتُ المكتملةُ فعلاً**: أوّلُ نقطة مسارٍ بعد `started_at` (لا دبّوسُ الطلب)، آخرَ ٩٠ يوماً.
   **مجمَّعةٌ في خلايا** (~٢٠ م) **ولا تُحفظ خليةٌ دون ثلاثة ركّابٍ مختلفين** — فلا يُقرأ منها موقعُ راكبٍ بعينه. تُبنى كلَّ ليلة
   (`tasks/pickup_spots.py`) في Redis لكلِّ دولة، والأرجحُ ما كثرت التقاطاتُه وقرُب.

**ولا اقتراحَ** حين الدبّوسُ على النقطة نفسِها (دون `MIN_MOVE_M`)، أو المفتاحُ مطفأ (`map_settings.pickup_suggest_enabled`).
**لا مالَ فيها ولا نداءَ مزوّد.**
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode, MapPlaceCategory, RideStatus
from app.models.map_place import SOURCE_OWNER, MapPlace
from app.models.ride import Ride, RideRoutePoint
from app.services import map_settings

RADIUS_M = 150
MIN_MOVE_M = 15
MIN_RIDERS = 3
WINDOW_DAYS = 90
CELL_DEG = 0.0002
MAX_SPOTS = 5000
#: **نصفُ المسافة التي تُنقص الوزن** — خليةٌ بعشرين التقاطاً على ١٢٠ م تُقدَّم على خليةٍ بثلاثةٍ على ٢٠ م
DISTANCE_SCALE_M = 40
KEY = "pickup:spots:{country}"
TTL_SECONDS = 3 * 86400


@dataclass(frozen=True)
class Suggestion:
    lat: float
    lng: float
    name_ar: str | None
    name_en: str | None
    source: str
    distance_m: int


def meters(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """مسافةُ الدائرة العظمى — تكفي لمدى مئةٍ وخمسين متراً."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(round(2 * r * math.asin(math.sqrt(a))))


def cluster(rows: Iterable[tuple[uuid.UUID, float, float]]) -> list[list[float]]:
    """**خلايا الالتقاط** — `[lat, lng, count]` لكلِّ خليةٍ فيها `MIN_RIDERS` ركّابٍ مختلفون فأكثر، الأكثرُ أوّلاً."""
    cells: dict[tuple[int, int], list] = {}
    for rider, lat, lng in rows:
        cell = cells.setdefault((round(lat / CELL_DEG), round(lng / CELL_DEG)), [0.0, 0.0, 0, set()])
        cell[0] += lat
        cell[1] += lng
        cell[2] += 1
        cell[3].add(rider)
    spots = [[round(c[0] / c[2], 6), round(c[1] / c[2], 6), c[2]] for c in cells.values() if len(c[3]) >= MIN_RIDERS]
    spots.sort(key=lambda spot: -spot[2])
    return spots[:MAX_SPOTS]


async def actual_pickups(session: AsyncSession, country: CountryCode, since: datetime) -> list[tuple[uuid.UUID, float, float]]:
    """**أين بدأت كلُّ رحلةٍ مكتملة** — أوّلُ نقطة مسارٍ بعد البدء، لا دبّوسُ الطلب."""
    query = (
        select(RideRoutePoint.ride_id, Ride.rider_id, RideRoutePoint.lat, RideRoutePoint.lng)
        .join(Ride, Ride.id == RideRoutePoint.ride_id)
        .where(
            Ride.country_code == country,
            Ride.status == RideStatus.COMPLETED,
            Ride.started_at.is_not(None),
            Ride.created_at >= since,
            RideRoutePoint.created_at >= Ride.started_at,
        )
        .order_by(RideRoutePoint.ride_id, RideRoutePoint.created_at)
        .distinct(RideRoutePoint.ride_id)
    )
    return [(rider, float(lat), float(lng)) for _ride, rider, lat, lng in (await session.execute(query)).all()]


async def rebuild(session: AsyncSession, redis: Redis, *, now: datetime | None = None) -> dict[str, int]:
    """**البناءُ الليليّ** — خلايا كلِّ دولةٍ في Redis، ويعيد عددَها لكلِّ دولة."""
    since = (now or datetime.now(UTC)) - timedelta(days=WINDOW_DAYS)
    counts: dict[str, int] = {}
    for country in CountryCode:
        spots = cluster(await actual_pickups(session, country, since))
        await redis.set(KEY.format(country=country.value), json.dumps(spots), ex=TTL_SECONDS)
        counts[country.value] = len(spots)
    return counts


async def suggest(session: AsyncSession, redis: Redis, country: CountryCode, lat: float, lng: float) -> Suggestion | None:
    if not await map_settings.pickup_suggest_enabled(session, country):
        return None
    best: Suggestion | None = None
    places = await session.scalars(
        select(MapPlace).where(
            MapPlace.country_code == country,
            MapPlace.category == MapPlaceCategory.PICKUP.value,
            MapPlace.is_hidden.is_(False),
            MapPlace.source == SOURCE_OWNER,
        )
    )
    for place in places:
        distance = meters(lat, lng, place.lat, place.lng)
        if distance <= RADIUS_M and (best is None or distance < best.distance_m):
            best = Suggestion(place.lat, place.lng, place.name_ar, place.name_en, "place", distance)
    if best is None:
        raw = await redis.get(KEY.format(country=CountryCode(country).value))
        top = -1.0
        for spot_lat, spot_lng, count in json.loads(raw) if raw else []:
            distance = meters(lat, lng, spot_lat, spot_lng)
            if distance > RADIUS_M:
                continue
            weight = count / (1 + distance / DISTANCE_SCALE_M)
            if weight > top:
                top, best = weight, Suggestion(spot_lat, spot_lng, None, None, "history", distance)
    if best is None or best.distance_m < MIN_MOVE_M:
        return None
    return best
