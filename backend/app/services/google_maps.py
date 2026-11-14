"""**Google Maps Platform — المزوّدُ الأوّل للخرائط والبحث والمسارات** (قرارُ المالك ٢٠٢٦-١١-١٥)، **وMapbox احتياطٌ قائمٌ كاملاً**.

**ثلاثُ ميزاتٍ لكلِّ دولة، ولكلٍّ مفتاحُها** («مزوّد الخرائط» في اللوحة):
- `google_maps_display` — الخريطةُ المرسومة (بلاطاتُ Map Tiles API في محرّك الخرائط القائم)؛ مطفأ ⇐ Mapbox.
- `google_places_search` — البحث (Places API New: Autocomplete بجلسة ثمّ Details بحقولٍ محدودة) والعنوانُ العكسيّ (Geocoding).
- `google_routes` — المسافةُ والمدّةُ والشكلُ والخطوات (Routes API computeRoutes).

**والرجوعُ الآليّ** (`maps_health`): خطأٌ أو مهلةٌ أو حصّةٌ نفدت أو مفتاحٌ مرفوض ⇐ الطلبُ نفسُه يُعاد على Mapbox في الحال، وتُعلَّم
الميزةُ «متوقّفةً» عشرَ دقائق فلا يُطرق Google في كلِّ طلب، **ويُشعَر المالكُ في اللوحة مرّةً** عند التوقّف ومرّةً عند العودة.

**وحمايةُ الكلفة هنا قبل Google** — سقفٌ يوميٌّ لكلِّ واجهةٍ في Redis (يُضبط من العقد): بلغه ⇐ Mapbox حتى منتصف الليل، وإشعار.
فخللٌ يدور في حلقةٍ لا يصنع فاتورة. **وحصصُ Google اليوميّةُ في لوحته سياجٌ ثانٍ** لا بديل.

**وما لا يُخزَّن** (شروط Google): لا نصوصَ من Places تُحفظ دائماً — معرّفُ المكان وحده، والإحداثياتُ حتى ٣٠ يوماً (`learned_places`
تسقط بعد ٣٠ يوماً بلا تأكيد)، وتفاصيلُ المكان في Redis سبعةَ أيّام، والعنوانُ العكسيُّ ساعة.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

logger = logging.getLogger(__name__)

AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
DETAILS_URL = "https://places.googleapis.com/v1/places/{}"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
TIMEOUT_SECONDS = 6.0

#: **حقولُ التفاصيل — شريحةُ Essentials وحدَها** (لا `displayName`: هي Pro وأغلى؛ الاسمُ من نصِّ الاقتراح نفسِه)
DETAILS_FIELDS = "id,location,formattedAddress"
ROUTE_FIELDS = "routes.distanceMeters,routes.duration"
ROUTE_FIELDS_SHAPE = ROUTE_FIELDS + ",routes.polyline.encodedPolyline"
ROUTE_FIELDS_STEPS = (
    ROUTE_FIELDS_SHAPE
    + ",routes.legs.steps.distanceMeters,routes.legs.steps.polyline.encodedPolyline"
    + ",routes.legs.steps.navigationInstruction"
)

#: **السقوفُ اليوميّة الافتراضيّة** — تُبدَّل من العقد. محسوبةٌ بأضعاف الاستعمال الحاليّ لا بحدِّه
DEFAULT_CAPS = {"autocomplete": 4000, "details": 1500, "geocode": 3000, "routes": 6000}

_KM = Decimal("0.001")
_MIN = Decimal("0.01")

#: **مناورةُ Google بمفردات Mapbox** — فالسهمُ في تطبيق الكبتن يُشتقّ من النوع والاتجاه كما كان (`directions._collect_steps`)
MANEUVERS: dict[str, tuple[str, str | None]] = {
    "DEPART": ("depart", None),
    "STRAIGHT": ("continue", "straight"),
    "TURN_LEFT": ("turn", "left"),
    "TURN_RIGHT": ("turn", "right"),
    "TURN_SLIGHT_LEFT": ("turn", "slight left"),
    "TURN_SLIGHT_RIGHT": ("turn", "slight right"),
    "TURN_SHARP_LEFT": ("turn", "sharp left"),
    "TURN_SHARP_RIGHT": ("turn", "sharp right"),
    "UTURN_LEFT": ("turn", "uturn"),
    "UTURN_RIGHT": ("turn", "uturn"),
    "RAMP_LEFT": ("off ramp", "left"),
    "RAMP_RIGHT": ("off ramp", "right"),
    "FORK_LEFT": ("fork", "left"),
    "FORK_RIGHT": ("fork", "right"),
    "MERGE": ("merge", None),
    "ROUNDABOUT_LEFT": ("roundabout", None),
    "ROUNDABOUT_RIGHT": ("roundabout", None),
    "ROUNDABOUT_CLOCKWISE": ("roundabout", None),
    "ROUNDABOUT_COUNTERCLOCKWISE": ("roundabout", None),
    "NAME_CHANGE": ("new name", None),
}


class GoogleFailed(Exception):
    """**أيُّ فشلٍ يوجب الرجوعَ إلى Mapbox** — شبكة، مهلة، 4xx (مفتاح/حصّة/صلاحيّة)، 5xx، أو جوابٌ غيرُ مقروء. `reason` للوحة."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class NoRoute(Exception):
    """**جوابٌ سليمٌ بلا مسار** — ليس عطلاً في Google، فلا رجوعَ ولا إشعار."""


@dataclass(frozen=True, slots=True)
class Suggestion:
    place_id: str
    name: str
    address: str


@dataclass(frozen=True, slots=True)
class PlacePoint:
    place_id: str
    address: str
    lat: float
    lng: float


@dataclass(frozen=True, slots=True)
class GoogleRoute:
    distance_km: Decimal
    duration_min: Decimal
    geometry: list[list[float]] | None
    steps: list[dict] | None


def decode_polyline(encoded: str) -> list[list[float]]:
    """**خوارزميّةُ Google المنشورة** — وتعود `[[lng, lat], …]` بترتيب GeoJSON كما يكتبه Mapbox، فلا يتغيّر ما بعدها."""
    points: list[list[float]] = []
    index = lat = lng = 0
    length = len(encoded)
    while index < length:
        for axis in (0, 1):
            shift = result = 0
            while True:
                if index >= length:
                    return points
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if axis == 0:
                lat += delta
            else:
                lng += delta
        points.append([lng / 1e5, lat / 1e5])
    return points


def _seconds(value: Any) -> Decimal:
    text = str(value or "").strip()
    if not text.endswith("s"):
        raise GoogleFailed("مدّةٌ غيرُ مقروءة")
    return Decimal(text[:-1])


async def _post(url: str, key: str, body: dict, field_mask: str | None = None) -> dict:
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": key}
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    return await _send("POST", url, headers=headers, json=body)


async def _get(url: str, *, headers: dict | None = None, params: dict | None = None) -> dict:
    return await _send("GET", url, headers=headers or {}, params=params)


async def _send(method: str, url: str, **kwargs: Any) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as http:
            response = await http.request(method, url, **kwargs)
    except httpx.TimeoutException as exc:
        raise GoogleFailed("مهلةٌ انتهت") from exc
    except httpx.HTTPError as exc:
        raise GoogleFailed("تعذّر الاتصال") from exc
    if response.status_code == 429:
        raise GoogleFailed("الحصّةُ نفدت (429)")
    if response.status_code in (401, 403):
        raise GoogleFailed(f"المفتاحُ مرفوض ({response.status_code})")
    if response.status_code >= 400:
        raise GoogleFailed(f"خطأ {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise GoogleFailed("جوابٌ غيرُ مقروء") from exc
    if not isinstance(body, dict):
        raise GoogleFailed("جوابٌ غيرُ مقروء")
    return body


#: **نقطةُ الحقن في الاختبارات** — `None` في التشغيل الحقيقيّ
transport: httpx.AsyncBaseTransport | None = None


# ═════════════════════════ البحث


async def autocomplete(
    key: str, query: str, country: str, *, session_token: str, near: tuple[float, float] | None, language: str = "ar"
) -> list[Suggestion]:
    """**اقتراحاتٌ بجلسة** — `sessionToken` يجمع الكتابةَ والاختيارَ في جلسةٍ واحدةٍ تُحاسَب مرّة؛ وبلدُ المستخدم وحدَه."""
    body: dict[str, Any] = {
        "input": query,
        "languageCode": language,
        "includedRegionCodes": [country.lower()],
        "sessionToken": session_token,
    }
    if near:
        body["locationBias"] = {"circle": {"center": {"latitude": near[0], "longitude": near[1]}, "radius": 30000.0}}
    data = await _post(AUTOCOMPLETE_URL, key, body)
    out: list[Suggestion] = []
    for item in data.get("suggestions") or []:
        prediction = (item or {}).get("placePrediction") or {}
        place_id = prediction.get("placeId")
        fmt = prediction.get("structuredFormat") or {}
        name = ((fmt.get("mainText") or {}).get("text") or (prediction.get("text") or {}).get("text") or "").strip()
        address = ((fmt.get("secondaryText") or {}).get("text") or "").strip()
        if place_id and name:
            out.append(Suggestion(place_id=str(place_id), name=name, address=address))
    return out


async def details(key: str, place_id: str, *, session_token: str | None, language: str = "ar") -> PlacePoint:
    """**موقعُ الاقتراح المختار** — بحقول Essentials وحدَها، وبجلسة البحث نفسِها فتُغلق الجلسة."""
    params: dict[str, str] = {"languageCode": language}
    if session_token:
        params["sessionToken"] = session_token
    data = await _get(
        DETAILS_URL.format(place_id),
        headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": DETAILS_FIELDS},
        params=params,
    )
    location = data.get("location") or {}
    try:
        lat, lng = float(location["latitude"]), float(location["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GoogleFailed("مكانٌ بلا موقع") from exc
    return PlacePoint(place_id=place_id, address=str(data.get("formattedAddress") or ""), lat=lat, lng=lng)


async def reverse(key: str, lat: float, lng: float, *, language: str = "ar") -> str | None:
    """**عنوانٌ لدبوس** — `ZERO_RESULTS` جوابٌ سليمٌ يعني «لا عنوان»، وما سواه من الحالات فشلٌ يوجب الرجوع."""
    data = await _get(GEOCODE_URL, params={"latlng": f"{lat},{lng}", "language": language, "key": key})
    status = data.get("status")
    if status == "ZERO_RESULTS":
        return None
    if status != "OK":
        raise GoogleFailed(f"Geocoding: {status}")
    results = data.get("results") or []
    if not results:
        return None
    return str(results[0].get("formatted_address") or "") or None


# ═════════════════════════ المسار


async def route(
    key: str,
    waypoints: list[tuple[float, float]],
    *,
    with_geometry: bool,
    with_steps: bool,
    language: str = "ar",
) -> GoogleRoute:
    """**مسارٌ بالسيّارة بلا حركة مرور** (`TRAFFIC_UNAWARE` — شريحةُ Essentials، **ومسافتُه ثابتةٌ لا تتبدّل مع الزحام** فلا يقفز السعر)."""

    def point(p: tuple[float, float]) -> dict:
        return {"location": {"latLng": {"latitude": p[0], "longitude": p[1]}}}

    body: dict[str, Any] = {
        "origin": point(waypoints[0]),
        "destination": point(waypoints[-1]),
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
        "languageCode": language,
        "units": "METRIC",
    }
    if len(waypoints) > 2:
        body["intermediates"] = [point(p) for p in waypoints[1:-1]]
    mask = ROUTE_FIELDS_STEPS if with_steps else ROUTE_FIELDS_SHAPE if with_geometry else ROUTE_FIELDS
    data = await _post(ROUTES_URL, key, body, mask)
    routes = data.get("routes") or []
    if not routes:
        raise NoRoute()
    best = routes[0]
    try:
        meters = Decimal(str(best["distanceMeters"]))
        seconds = _seconds(best.get("duration"))
    except (KeyError, ArithmeticError) as exc:
        raise GoogleFailed("مسارٌ بلا مسافة") from exc
    geometry = None
    if with_geometry:
        encoded = (best.get("polyline") or {}).get("encodedPolyline")
        shape = decode_polyline(encoded) if encoded else []
        geometry = shape if len(shape) >= 2 else None
    steps = _steps(best) if with_steps else None
    return GoogleRoute(
        distance_km=(meters / 1000).quantize(_KM, rounding=ROUND_HALF_UP),
        duration_min=(seconds / 60).quantize(_MIN, rounding=ROUND_HALF_UP),
        geometry=geometry,
        steps=steps,
    )


def _steps(best: dict) -> list[dict] | None:
    collected: list[dict] = []
    for leg in best.get("legs") or []:
        for step in leg.get("steps") or []:
            nav = step.get("navigationInstruction") or {}
            text = str(nav.get("instructions") or "").strip()
            encoded = (step.get("polyline") or {}).get("encodedPolyline")
            shape = decode_polyline(encoded) if encoded else []
            if not text or len(shape) < 2:
                continue
            maneuver, modifier = MANEUVERS.get(str(nav.get("maneuver") or ""), (None, None))
            collected.append(
                {
                    "text": text,
                    "distance_m": int(step.get("distanceMeters") or 0),
                    "shape": shape,
                    "maneuver": maneuver,
                    "modifier": modifier,
                }
            )
    return collected or None


def today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")
