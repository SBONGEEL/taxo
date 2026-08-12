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


async def fetch_route(token: str, *waypoints: Coordinates) -> Route:
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
        # لا نحتاج شكل المسار هنا؛ الملاحة في تطبيق الكبتن (المرحلة 10)
        "overview": "false",
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

    return Route(
        distance_km=(meters / 1000).quantize(_KM, rounding=ROUND_HALF_UP),
        duration_min=(seconds / 60).quantize(_MIN, rounding=ROUND_HALF_UP),
    )


async def route_between(
    session: AsyncSession,
    pickup: Coordinates,
    dropoff: Coordinates,
    country_code: CountryCode | None = None,
    stops: Sequence[Coordinates] = (),
) -> Route:
    """المسار بتوكن Mapbox السري المحفوظ في عقود المزودين.

    و`stops` محطاتٌ **وسيطة** بترتيبها بين الانطلاق والوجهة الأخيرة.
    """
    values = await credentials_service.get_values(
        session, ProviderKey.MAPBOX, country_code
    )
    token = (values or {}).get("secret_token")
    if not token:
        raise RoutingUnavailable()

    return await fetch_route(token, pickup, *stops, dropoff)
