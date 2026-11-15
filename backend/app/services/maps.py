"""**مزوّدُ الخرائط لكلِّ دولةٍ وميزة، والرجوعُ الآليُّ إلى Mapbox، والبحثُ الموحَّد** (قرارُ المالك ٢٠٢٦-١١-١٥).

**من يقرّر المزوّد**: مفتاحُ الميزة للدولة (`google_maps_display` · `google_places_search` · `google_routes`) **وعقدُ Google قائم**
**وGoogle غيرُ معلَّمٍ متوقّفاً** **ولم يبلغ سقفَه اليوميّ**. وما عدا ذلك Mapbox — كما كان حرفاً.

**والبحثُ الموحَّد** (`search`): صندوقٌ واحدٌ يجمع — أماكنَ المستخدم المحفوظة، **ثمّ أماكنَ TAXO** (أماكنُ المالك بأسمائها البديلة،
**ثمّ ما تعلّمته الرحلاتُ المكتملة**)، ثمّ نتائجَ المزوّد. **ومتسامحٌ مع الخطأ الإملائيّ** في أماكن TAXO (مسافةُ تحريرٍ صغيرة بعد
التطبيع: «ستي مول» تجد «سيتي مول»)، وGoogle متسامحٌ بطبعه. **وبلدُ المستخدم وحدَه، والعربيّةُ أوّلاً.**
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode, FeatureKey, ProviderKey
from app.services import google_maps, settings_service
from app.services.providers import credentials as credentials_service

logger = logging.getLogger(__name__)

#: **«open»** حالُ خدمة البيانات المفتوحة — مفتاحُ حالٍ وإشعار، لا مفتاحُ Google
Feature = Literal["display", "search", "routes", "open"]
FEATURE_FLAGS: dict[str, FeatureKey] = {
    "display": FeatureKey.GOOGLE_MAPS_DISPLAY,
    "search": FeatureKey.GOOGLE_PLACES_SEARCH,
    "routes": FeatureKey.GOOGLE_ROUTES,
}
#: **كم يبقى Google «متوقّفاً» بعد فشل** — لا يُطرق في كلِّ طلبٍ وهو ساقط، ويُجرَّب ثانيةً بعدها
DOWN_SECONDS = 600
_DOWN = "maps:google:down:{}"
_CAP = "maps:google:calls:{}:{}"

#: **نسبةُ البيانات المفتوحة كما تطلبها رخصتاها** — ODbL تشترط «© OpenStreetMap contributors»، وOverture تُذكر مصدراً
OPEN_ATTRIBUTION = "© OpenStreetMap contributors · Overture Maps"
#: **مهلةُ الخدمة المحلّية** — فهرسٌ على القرص يجيب في عُشر ثانية، فثانيتان سقفٌ لا تقدير
OPEN_TIMEOUT = 2.0
#: نقطةُ حقنٍ للاختبار وحدَه
open_transport: httpx.AsyncBaseTransport | None = None
MAPBOX_FORWARD = "https://api.mapbox.com/search/geocode/v6/forward"
MAPBOX_REVERSE = "https://api.mapbox.com/search/geocode/v6/reverse"


def _redis():
    from app.core.redis_client import get_redis_client

    return get_redis_client()


async def google_values(session: AsyncSession) -> dict[str, Any] | None:
    values = await credentials_service.get_values(session, ProviderKey.GOOGLE_MAPS, None)
    return values if values and values.get("server_key") else None


async def is_down(feature: Feature) -> bool:
    try:
        return bool(await _redis().exists(_DOWN.format(feature)))
    except Exception:  # pragma: no cover - Redis معطّلٌ لا يمنع خريطة
        return False


async def note(feature: Feature, *, up: bool, reason: str | None = None, country: CountryCode | None = None) -> None:
    """**الحالُ وإشعارُ المالك عند تبدّلها وحدَه** — `SET NX` و`DELETE` ذرّيّان: عشرةُ طلباتٍ تصطدم بالانقطاع إشعارٌ واحد."""
    from app.services import alert_capture

    key = _DOWN.format(feature)
    try:
        redis = _redis()
        if up:
            changed = bool(await redis.delete(key))
        else:
            changed = bool(await redis.set(key, reason or "fail", nx=True, ex=DOWN_SECONDS))
    except Exception:  # pragma: no cover
        logger.warning("تعذّرت كتابةُ حال Google Maps", exc_info=True)
        return
    if changed:
        kind = "maps_restored" if up else "maps_fallback"
        alert_capture.ship_after_commit(
            None, kind, "signal", uuid.uuid4(), country=country.value if country else None,
            provider=f"{feature}: {reason}" if reason else feature,
        )
    if not up:
        logger.error("Google Maps (%s) فشل — الرجوعُ إلى Mapbox: %s", feature, reason)


async def _spend(api: str, values: dict[str, Any]) -> bool:
    """**عدّادُ اليوم لكلِّ واجهة** — يعيد `False` إن بلغ السقف (فلا نداء)، ويُعدّ قبل النداء: نداءٌ سقط كُلِّف أيضاً."""
    raw = str(values.get(f"cap_{api}") or "").strip()
    try:
        cap = int(raw) if raw else google_maps.DEFAULT_CAPS[api]
    except ValueError:
        cap = google_maps.DEFAULT_CAPS[api]
    try:
        redis = _redis()
        key = _CAP.format(api, google_maps.today())
        used = int(await redis.incr(key))
        if used == 1:
            await redis.expire(key, 2 * 24 * 3600)
    except Exception:  # pragma: no cover - بلا عدّادٍ لا نخاطر بفاتورة
        return False
    return used <= cap


async def provider_for(session: AsyncSession, country: CountryCode | None, feature: Feature) -> str:
    """`"google"` أو `"mapbox"` — **ولا يُقال «google» إلا والمفتاحُ والعقدُ والصحّةُ معاً**."""
    if country is None:
        return "mapbox"
    if not await settings_service.is_feature_enabled(session, country, FEATURE_FLAGS[feature]):
        return "mapbox"
    if await google_values(session) is None or await is_down(feature):
        return "mapbox"
    return "google"


async def use_google(session: AsyncSession, country: CountryCode | None, feature: Feature, api: str) -> dict[str, Any] | None:
    """**قيمُ العقد إن كان Google هو المزوّدَ لهذا النداء الآن** — وإلا `None` فيذهب المنادي إلى Mapbox. والسقفُ يُستهلك هنا."""
    if await provider_for(session, country, feature) != "google":
        return None
    values = await google_values(session)
    if values is None:
        return None
    if not await _spend(api, values):
        await note(feature, up=False, reason=f"بلغ السقفَ اليوميّ ({api})", country=country)
        return None
    return values


# ═════════════════════════ البحث الموحَّد


@dataclass
class Result:
    id: str
    source: str  # saved · taxo · learned · google · mapbox
    name: str
    address: str = ""
    lat: float | None = None
    lng: float | None = None
    #: **اقتراحُ Google بلا موقع** — يُحلّ بـ`resolve` عند الاختيار (الجلسةُ نفسُها)
    place_id: str | None = None
    distance_m: int | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class SearchAnswer:
    items: list[Result]
    #: «Powered by Google» تحت القائمة حين فيها نتائجُ Google — وMapbox يُنسب كذلك
    attribution: str | None


def _edit_distance(a: str, b: str, limit: int) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        best = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            value = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            current.append(value)
            best = min(best, value)
        if best > limit:
            return limit + 1
        previous = current
    return previous[-1]


def fuzzy_score(needle: str, names: list[str]) -> int | None:
    """**0 يبدأ به · 1 يحويه · 2 قريبٌ إملائيّاً** — و`None` لا يطابق. **والتسامحُ بطول النصّ**: حرفٌ لأربعةٍ فأكثر، حرفان لثمانيةٍ فأكثر."""
    if len(needle) < 2:
        return None
    limit = 2 if len(needle) >= 8 else 1 if len(needle) >= 4 else 0
    best: int | None = None
    for name in names:
        if not name:
            continue
        if name.startswith(needle) or f" {needle}" in f" {name}":
            return 0
        if needle in name:
            best = 1 if best is None else min(best, 1)
            continue
        if limit:
            words = name.split()
            spans = [" ".join(words[i : i + len(needle.split())]) for i in range(len(words))] + [name]
            if any(_edit_distance(needle, span[: len(needle) + limit], limit) <= limit for span in spans):
                best = 2 if best is None else min(best, 2)
    return best


async def _open_search(country: CountryCode, query: str, near: tuple[float, float] | None) -> list[Result] | None:
    """**الخدمةُ المحلّية** — `None` ⇐ فشلت (فيُرجع إلى Mapbox ويُشعَر المالكُ مرّة)، وقائمةٌ فارغة ⇐ أجابت بلا نتيجة."""
    from app.core.config import settings

    base = settings.places_search_url.rstrip("/")
    if not base or await is_down("open"):
        return None
    params: dict[str, str] = {"q": query, "cc": country.value, "limit": "8"}
    if near:
        params["lat"], params["lng"] = str(near[0]), str(near[1])
    try:
        async with httpx.AsyncClient(timeout=OPEN_TIMEOUT, transport=open_transport) as client:
            response = await client.get(f"{base}/search", params=params)
        if response.status_code == 503:
            # **مشغولةٌ لا ساقطة** — حدُّ عمّالها امتلأ؛ هذا الطلبُ إلى Mapbox، ولا تُعلَّم متوقّفةً ولا يُشعَر أحد
            return None
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        await note("open", up=False, reason=type(exc).__name__, country=country)
        return None
    await note("open", up=True)
    out: list[Result] = []
    for item in body.get("items") or []:
        out.append(Result(
            id=f"o-{item['id']}", source="open", name=item["name"],
            address=item.get("context") or (item.get("name_en") or ""),
            lat=float(item["lat"]), lng=float(item["lng"]), distance_m=item.get("distance_m"),
        ))
    return out


async def _recent(session: AsyncSession, user_id: uuid.UUID, needle: str) -> list[Result]:
    """**وجهاتُ الراكب الأخيرة** (ثلاثون يوماً، رحلاتٌ مكتملة) — ما طابق منها يتقدّم بعد المحفوظة."""
    from app.models.enums import RideStatus
    from app.models.ride import Ride
    from app.services import map_places

    rows = (await session.execute(
        select(Ride.dropoff_address, Ride.dropoff_lat, Ride.dropoff_lng)
        .where(Ride.rider_id == user_id, Ride.status == RideStatus.COMPLETED, Ride.dropoff_address.is_not(None),
               Ride.created_at >= recent_cutoff())
        .order_by(Ride.created_at.desc()).limit(30)
    )).all()
    out: list[Result] = []
    seen: set[str] = set()
    for address, lat, lng in rows:
        key = map_places.normalize(address)
        if key in seen or fuzzy_score(needle, [key]) is None:
            continue
        seen.add(key)
        out.append(Result(id=f"recent-{len(out)}", source="recent", name=address, lat=lat, lng=lng))
        if len(out) >= 3:
            break
    return out


async def search(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    country: CountryCode,
    query: str,
    near: tuple[float, float] | None,
    session_token: str | None,
) -> SearchAnswer:
    from app.services import learned_places, map_places

    needle = map_places.normalize(query)
    items: list[Result] = []

    # ١ — المحفوظة (البيت، العمل …) تتقدّم ما طابق منها
    from app.models.place import SavedPlace

    for saved in await session.scalars(select(SavedPlace).where(SavedPlace.user_id == user_id)):
        if fuzzy_score(needle, [map_places.normalize(saved.label), map_places.normalize(saved.address or "")]) is not None:
            items.append(Result(id=f"saved-{saved.id}", source="saved", name=saved.label, address=saved.address or "",
                                lat=saved.lat, lng=saved.lng))

    # ١ب — وجهاتُ الراكب الأخيرة
    items.extend(await _recent(session, user_id, needle))

    # ٢ — أماكنُ TAXO: أماكنُ المالك بأسمائها البديلة، ثمّ ما تعلّمته الرحلات
    for spot, distance, score in await map_places.fuzzy_search(session, country, query, near):
        items.append(Result(id=f"own-{spot.id}", source="taxo", name=spot.name_ar, address=spot.name_en or "",
                            lat=spot.lat, lng=spot.lng, distance_m=distance, extra={"score": score}))
    for learned in await learned_places.search(session, country, query, near):
        items.append(Result(id=f"learned-{learned.id}", source="learned", name=learned.label, lat=learned.lat, lng=learned.lng))

    # ٣ — المزوّد: Google إن كان هو، وإلا Mapbox؛ وفشلُ Google يُعاد على Mapbox في الطلب نفسِه
    provider_items: list[Result] = []
    attribution: str | None = None
    if len(needle) >= 2:
        values = await use_google(session, country, "search", "autocomplete")
        if values is not None:
            try:
                suggestions = await google_maps.autocomplete(
                    values["server_key"], query.strip(), country.value, session_token=session_token or str(uuid.uuid4()), near=near
                )
                provider_items = [Result(id=f"g-{s.place_id}", source="google", name=s.name, address=s.address, place_id=s.place_id)
                                  for s in suggestions]
                attribution = "google"
                await note("search", up=True)
            except google_maps.GoogleFailed as exc:
                await note("search", up=False, reason=exc.reason, country=country)
                values = None
        if values is None and await settings_service.is_feature_enabled(session, country, FeatureKey.OPEN_PLACES_SEARCH):
            # **البياناتُ المفتوحة** (قرارُ المالك ٢٠٢٦-١١-١٥) — وفشلُها أو خلوُّها يمرّ إلى Mapbox تحتها
            opened = await _open_search(country, query.strip(), near)
            if opened:
                provider_items, attribution, values = opened, "open", {}
        if values is None:
            provider_items = await _mapbox_forward(session, country, query.strip(), near)
            attribution = "mapbox" if provider_items else None

    taxo_points = [(r.lat, r.lng, map_places.normalize(r.name)) for r in items if r.lat is not None]
    for result in provider_items:
        # **نتيجةُ مزوّدٍ باسم مكانٍ لنا** تُسقط: مكانُنا هو هو، واسمُنا يصحّحه
        if any(map_places.normalize(result.name) == name for _, _, name in taxo_points):
            continue
        items.append(result)
    return SearchAnswer(items=items[:20], attribution=attribution)


async def resolve(session: AsyncSession, country: CountryCode, place_id: str, session_token: str | None) -> google_maps.PlacePoint:
    """**موقعُ اقتراح Google المختار** — من ذاكرة Redis أسبوعاً (الإحداثياتُ مسموحٌ حفظُها ٣٠ يوماً)، وإلا Details."""
    cache_key = f"maps:place:{place_id}"
    try:
        cached = await _redis().get(cache_key)
    except Exception:  # pragma: no cover
        cached = None
    if cached:
        data = json.loads(cached)
        return google_maps.PlacePoint(**data)
    values = await use_google(session, country, "search", "details")
    if values is None:
        raise google_maps.GoogleFailed("Google غيرُ متاحٍ الآن")
    try:
        point = await google_maps.details(values["server_key"], place_id, session_token=session_token)
    except google_maps.GoogleFailed as exc:
        await note("search", up=False, reason=exc.reason, country=country)
        raise
    try:
        payload = {"place_id": point.place_id, "address": point.address, "lat": point.lat, "lng": point.lng}
        await _redis().set(cache_key, json.dumps(payload), ex=7 * 24 * 3600)
    except Exception:  # pragma: no cover
        pass
    return point


async def reverse(session: AsyncSession, country: CountryCode | None, lat: float, lng: float) -> tuple[str | None, str]:
    """**عنوانُ الدبوس ومزوّدُه** — ذاكرةُ ساعةٍ لكلِّ ١١ متراً تقريباً (أربعُ منازل) فلا يُدفع لتحريكٍ صغير."""
    cache_key = f"maps:reverse:{round(lat, 4)}:{round(lng, 4)}"
    try:
        cached = await _redis().get(cache_key)
    except Exception:  # pragma: no cover
        cached = None
    if cached:
        data = json.loads(cached)
        return data.get("address"), data.get("provider", "google")
    address: str | None = None
    provider = "mapbox"
    values = await use_google(session, country, "search", "geocode")
    if values is not None:
        try:
            address = await google_maps.reverse(values["server_key"], lat, lng)
            provider = "google"
            await note("search", up=True)
        except google_maps.GoogleFailed as exc:
            await note("search", up=False, reason=exc.reason, country=country)
            values = None
    if values is None:
        address = await _mapbox_reverse(session, country, lat, lng)
    try:
        await _redis().set(cache_key, json.dumps({"address": address, "provider": provider}), ex=3600)
    except Exception:  # pragma: no cover
        pass
    return address, provider


# ═════════════════════════ Mapbox — الاحتياط، من الخلفية بتوكنها السرّيّ


async def _mapbox_token(session: AsyncSession, country: CountryCode | None) -> str | None:
    values = await credentials_service.get_values(session, ProviderKey.MAPBOX, country)
    return (values or {}).get("secret_token") or (values or {}).get("public_token")


async def _mapbox_get(url: str, params: dict) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=google_maps.TIMEOUT_SECONDS, transport=google_maps.transport) as http:
            response = await http.get(url, params=params)
        if response.status_code >= 400:
            return None
        body = response.json()
        return body if isinstance(body, dict) else None
    except (httpx.HTTPError, ValueError):
        return None


async def _mapbox_forward(
    session: AsyncSession, country: CountryCode, query: str, near: tuple[float, float] | None
) -> list[Result]:
    token = await _mapbox_token(session, country)
    if not token:
        return []
    params = {"q": query, "access_token": token, "language": "ar", "country": country.value.lower(), "limit": "6"}
    if near:
        params["proximity"] = f"{near[1]},{near[0]}"
    body = await _mapbox_get(MAPBOX_FORWARD, params)
    out: list[Result] = []
    for index, feature in enumerate((body or {}).get("features") or []):
        props = feature.get("properties") or {}
        point = props.get("coordinates") or {}
        if "latitude" not in point:
            continue
        out.append(Result(
            id=f"m-{props.get('mapbox_id') or index}", source="mapbox",
            name=props.get("name") or props.get("full_address") or "موقع",
            address=props.get("full_address") or props.get("place_formatted") or "",
            lat=float(point["latitude"]), lng=float(point["longitude"]),
        ))
    return out


async def _mapbox_reverse(session: AsyncSession, country: CountryCode | None, lat: float, lng: float) -> str | None:
    token = await _mapbox_token(session, country)
    if not token:
        return None
    body = await _mapbox_get(MAPBOX_REVERSE, {"longitude": str(lng), "latitude": str(lat), "access_token": token,
                                               "language": "ar", "limit": "1"})
    first = (((body or {}).get("features") or [{}])[0] or {}).get("properties") or {}
    return first.get("full_address") or first.get("name") or None


def recent_cutoff(now: datetime | None = None) -> datetime:
    """**ما تعلّمناه يبقى ٣٠ يوماً بلا تأكيد** — شرطُ Google على الإحداثيات، ومعه يسقط ما لم يعد يُقصد."""
    return (now or datetime.now(UTC)) - timedelta(days=30)
