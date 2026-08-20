"""Mapbox Directions — المسافة والمدة على مسارٍ من نقطتين أو أكثر.

تُستدعى من الخلفية حصراً (SPEC القسم 2): التوكن السري لا يغادرها، والواجهة
لا تحسب سعراً ولا مسافة. مصدر التوكن هو `provider_credentials` — لا `.env`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RoutingFailed, RoutingUnavailable
from app.models.enums import CountryCode, ProviderKey
from app.services.providers import credentials as credentials_service

MAPBOX_DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox/driving"
REQUEST_TIMEOUT_SECONDS = 10.0

_KM = Decimal("0.001")
_MIN = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Coordinates:
    lat: float
    lng: float

    def as_mapbox(self) -> str:
        """Mapbox يكتب الإحداثيات (طول، عرض) — عكس الترتيب المألوف."""
        return f"{self.lng},{self.lat}"


@dataclass(frozen=True, slots=True)
class Route:
    distance_km: Decimal
    duration_min: Decimal
    # إحداثياتُ المسار `[[lng, lat], …]` — **لا تُطلب إلا حين تُرسم** (البند ٨).
    # فارغةٌ على مسار التسعير: التقديرُ يُنادى مع كل تحريكٍ للدبوس، وشكلُ المسار
    # حمولةٌ تُرسل لمن لم يطلب رحلةً بعد
    geometry: list[list[float]] | None = None
    # **التعليماتُ بهندستها** (البند ٧): كلُّ خطوةٍ نصُّها وشكلُها ومسافتُها.
    # **والشكلُ يلزم لا زينة**: الانحرافُ يُقاس عن هندسة الخطوة لا عن
    # `overview` — قِيس أن الثانيةَ خطؤها **٨٣١ م** في أسوأ مسارٍ مخزَّنٍ
    # عندنا، والأولى **٤٫٨ م**. فقياسٌ على `overview` يُخفي الشريطَ عن كبتنٍ
    # يسير على الطريق تماماً
    steps: list[dict] | None = None


async def fetch_route(
    token: str,
    *waypoints: Coordinates,
    with_geometry: bool = False,
    with_steps: bool = False,
) -> Route:
    """نداء HTTP واحد لـ Mapbox — نقطة الحقن الوحيدة في الاختبارات.

    **نقطتان أو أكثر** (المرحلة 12-ب): Mapbox يقبل سلسلةَ إحداثياتٍ مفصولةً
    بفاصلةٍ منقوطة ويعيد مسافةَ المسار كلِّه ومدتَه. فالرحلةُ متعددة المحطات
    **نداءٌ واحد** لا نداءٌ لكل ساق: المجموعُ هو ما يُسعَّر، ونداءاتٌ متفرقة
    تُحمّل الراكبَ التفافاً لا يقع (المسارُ الأمثل عبر المحطات أقصرُ من
    مجموع المسارات المستقلة).
    """
    if len(waypoints) < 2:  # pragma: no cover - خطأ برمجي لا مدخلُ مستخدم
        raise ValueError("المسار يحتاج نقطتين على الأقل")
    url = f"{MAPBOX_DIRECTIONS_URL}/{';'.join(p.as_mapbox() for p in waypoints)}"
    params = {
        "access_token": token,
        "alternatives": "false",
        # **الشكلُ لا يُطلب إلا لمن يرسمه** (البند ٨، 2026-08-14): كان
        # `overview=false` دائماً — فالمسارُ الذي يمرّ به Mapbox معروفٌ له
        # ومجهولٌ لنا، وخريطةُ الرحلة بلا خط. ويبقى مطفأً على مسار التسعير:
        # ذاك يُنادى مع كل تحريكِ دبوس، وحمولةُ الشكل تُرسل لمن لم يطلب بعد.
        # و`simplified` لا `full`: خطٌّ يُرسم على شاشة هاتفٍ لا يفيده تفصيلُ
        # كلِّ منعطفٍ بالمتر، ويكلّفه حجماً يمرّ في كل قراءة
        "overview": "simplified" if with_geometry else "false",
        **({"geometries": "geojson"} if with_geometry else {}),
        # **الخطواتُ تُطلب لمن يعرضها وحدَه** (البند ٧): حمولتُها ليست صغيرة
        # (٢٧٧ رأساً مقابل ٢١ في مسارٍ من ٨ كم — مقيس)، ومسارُ التسعير يُنادى
        # مع كل تحريكِ دبوس.
        #
        # **و`language=ar` شرطٌ لا زينة**: بغيرها تعود التعليماتُ إنجليزيةً
        # بأسماءِ شوارعَ عربية («Drive east on شارع زهران») — جملةٌ مكسورةٌ
        # يقرؤها كبتنٌ وهو يقود. وقِيس أن `ar` تعيد «القيادة باتجاه الشرق في
        # شارع زهران»
        **(
            {"steps": "true", "language": "ar"}
            if with_steps
            else {}
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http_client:
            response = await http_client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise RoutingFailed() from exc

    routes = payload.get("routes") or []
    if not routes:
        raise RoutingFailed("لا يوجد مسار بري بين النقطتين")

    best = routes[0]
    try:
        meters = Decimal(str(best["distance"]))
        seconds = Decimal(str(best["duration"]))
    except (KeyError, TypeError, ArithmeticError) as exc:
        raise RoutingFailed() from exc

    # الشكلُ **لا يُفشل المسار إن غاب**: المسافةُ والمدةُ هما ما يُسعَّر، وخريطةٌ
    # بلا خطٍّ أهونُ من رحلةٍ بلا سعر
    geometry: list[list[float]] | None = None
    if with_geometry:
        coordinates = (best.get("geometry") or {}).get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            geometry = [[float(point[0]), float(point[1])] for point in coordinates]

    steps: list[dict] | None = None
    if with_steps:
        collected: list[dict] = []
        for leg in best.get("legs") or []:
            for step in leg.get("steps") or []:
                instruction = ((step.get("maneuver") or {}).get("instruction") or "").strip()
                shape = (step.get("geometry") or {}).get("coordinates")
                if not instruction or not isinstance(shape, list) or len(shape) < 2:
                    continue
                collected.append(
                    {
                        "text": instruction,
                        "distance_m": int(float(step.get("distance") or 0)),
                        "shape": [[float(p[0]), float(p[1])] for p in shape],
                    }
                )
        steps = collected or None

    return Route(
        distance_km=(meters / 1000).quantize(_KM, rounding=ROUND_HALF_UP),
        duration_min=(seconds / 60).quantize(_MIN, rounding=ROUND_HALF_UP),
        geometry=geometry,
        steps=steps,
    )


async def route_between(
    session: AsyncSession,
    pickup: Coordinates,
    dropoff: Coordinates,
    country_code: CountryCode | None = None,
    stops: Sequence[Coordinates] = (),
    with_geometry: bool = False,
    with_steps: bool = False,
) -> Route:
    """المسار بتوكن Mapbox السري المحفوظ في عقود المزودين.

    و`stops` محطاتٌ **وسيطة** بترتيبها بين الانطلاق والوجهة الأخيرة.
    و`with_geometry` لمن يرسم الخط لا لمن يسعّر (البند ٨).
    """
    values = await credentials_service.get_values(
        session, ProviderKey.MAPBOX, country_code
    )
    token = (values or {}).get("secret_token")
    if not token:
        raise RoutingUnavailable()

    return await fetch_route(
        token,
        pickup,
        *stops,
        dropoff,
        with_geometry=with_geometry,
        with_steps=with_steps,
    )
