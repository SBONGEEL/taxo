"""**أماكنُ الخريطة** (SPEC §٧١-د) — ما يرسمه التطبيقان فوق أسماء المزوّد، وما يتقدّم نتائجَ البحث.

**مصدران لا ثالث**: أماكنُ المالك (`map_places`، غيرُ المخفيّة) **ومطاراتُ السوق المفعَّلة** من بيتها (`facilities.airports_for_rider`) —
قراءةٌ لا نسخة، فمرفقٌ يُطفأ هناك يغيب هنا بلا خطوةٍ ثانية.

**والمفتاحُ يحكم البابين**: سوقٌ لم يُشعل `map_places_enabled` يُعطى قائمتين فارغتين — **فالخريطةُ والبحثُ فيه كما كانا حرفاً**.

**والبحثُ هنا لا في القاعدة** — الأماكنُ مئات: يُقرأ ما في السوق ويُطابَق بعد **تطبيعِ العربيّة** (الهمزاتُ على الألف، والتاءُ المربوطة،
والألفُ المقصورة، والتشكيلُ والتطويل تُطوى)، فـ«مكه مول» تجد «مكة مول» و«الاردنية» تجد «الأردنيّة». **والأقربُ أوّلاً** بين ما طابق،
وما يبدأ بالنصّ قبل ما يحويه.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import CountryCode, FeatureKey
from app.models.map_place import SOURCE_OWNER, MapPlace
from app.services import facilities, settings_service

#: سقفُ نتائج البحث — ما يتّسع له رأسُ القائمة فوق نتائج المزوّد
SEARCH_LIMIT = 6

_MARKS = re.compile("[ً-ْٰـ]")  # التشكيلُ والألفُ الخنجريّةُ والتطويل
_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})


def normalize(text: str) -> str:
    """**تطبيعٌ للمطابقة وحدَها** — لا يُعرض: الاسمُ يُرسم كما كتبه المالك."""
    folded = _MARKS.sub("", text or "").translate(_FOLD).casefold()
    return " ".join(folded.split())


@dataclass(frozen=True)
class Spot:
    id: uuid.UUID
    name_ar: str
    name_en: str | None
    category: str
    lat: float
    lng: float
    source: str


def _meters(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """**مسافةُ الدائرة العظمى** — تكفي لترتيب «الأقرب أوّلاً» داخل مدينة، ولا تُعرض مسافةَ طريق."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(2 * r * math.asin(math.sqrt(a)))


async def visible(session: AsyncSession, country: CountryCode, *, for_map: bool = False) -> list[Spot]:
    """**ما يُبحث فيه** — فارغٌ حين المفتاحُ مطفأ. **و`for_map` ما يُرسم**: أماكنُ المالك وحدَها ومطاراتُ السوق — **لا المستورد**
    (§٧١-ح/٤): أسماءُ OSM في خريطة المزوّد أصلاً، ورسمُها ثانيةً نسخةٌ فوق أصلها."""
    if not await settings_service.is_feature_enabled(session, country, FeatureKey.MAP_PLACES_ENABLED):
        return []
    query = (
        select(MapPlace)
        .where(MapPlace.country_code == country, MapPlace.is_hidden.is_(False))
        .order_by(MapPlace.name_ar)
    )
    if for_map:
        query = query.where(MapPlace.source == SOURCE_OWNER)
    rows = await session.scalars(query)
    spots = [Spot(row.id, row.name_ar, row.name_en, row.category, row.lat, row.lng, "place") for row in rows]
    for facility_id, name, lat, lng in await facilities.airports_for_rider(session, country=country):
        spots.append(Spot(facility_id, name, None, "airport", float(lat), float(lng), "facility"))
    return spots


async def search(
    session: AsyncSession, country: CountryCode, query: str, near: tuple[float, float] | None
) -> list[tuple[Spot, int | None]]:
    """**ما طابق، الأقربُ أوّلاً** — وما يبدأ بالنصّ (في أيِّ كلمةٍ من الاسم) قبل ما يحويه في وسطه."""
    needle = normalize(query)
    if len(needle) < 2:
        return []
    ranked: list[tuple[int, int, Spot, int | None]] = []
    for spot in await visible(session, country):
        names = [normalize(spot.name_ar)] + ([normalize(spot.name_en)] if spot.name_en else [])
        if not any(needle in name for name in names):
            continue
        starts = any(name.startswith(needle) or f" {needle}" in f" {name}" for name in names)
        distance = _meters(near[0], near[1], spot.lat, spot.lng) if near else None
        ranked.append((0 if starts else 1, distance if distance is not None else 0, spot, distance))
    ranked.sort(key=lambda item: (item[0], item[1], item[2].name_ar))
    return [(spot, distance) for _, _, spot, distance in ranked[:SEARCH_LIMIT]]


# ═════════════════════════ اللوحة — إضافةٌ وتعديلٌ وإخفاء، ولا حذف


async def list_for_panel(session: AsyncSession, country: CountryCode | None) -> list[MapPlace]:
    """**كلُّها بما فيها المخفيّة** — فالمشرفُ يرى ما أخفاه."""
    query = select(MapPlace).order_by(MapPlace.country_code, MapPlace.name_ar)
    if country is not None:
        query = query.where(MapPlace.country_code == country)
    return list(await session.scalars(query))


async def get(session: AsyncSession, place_id: uuid.UUID) -> MapPlace:
    row = await session.get(MapPlace, place_id)
    if row is None:
        raise NotFound("المكانُ غيرُ موجود")
    return row


def require_name(changes: dict) -> None:
    """**إرسالُ `name_ar: null` صراحةً ليس «لم يُرسَل»** — والعمودُ إلزاميّ، فيُرفض بنصٍّ لا بخطأ قاعدة."""
    if "name_ar" in changes and changes["name_ar"] is None:
        raise InvalidInput("الاسمُ العربيُّ إلزاميّ")
    if "category" in changes and changes["category"] is None:
        raise InvalidInput("الفئةُ إلزاميّة")
    for key in ("lat", "lng", "is_hidden"):
        if key in changes and changes[key] is None:
            raise InvalidInput("الموقعُ والإخفاءُ لا يُفرَّغان")
