"""اختبارُ الحمل على الإنتاج (SPEC §٧٥) — **هويّةُ حساباته، وتخطّي Mapbox لها وحدَها حين يُشعَل، وعدّادُ نداءات Mapbox الحقيقيّة**.

**أمرُ المالك**: «No paid Mapbox calls … mock or skip them for test trips; report the number of paid calls made (target: zero).»

* **حسابُ الحمل** = موسومٌ بالتجربة (`is_test`) **ورقمُه في النطاق المحجوز** (`STRESS_PHONE_PREFIX`، «07 19…» في الأردن — لا يُعطى
  لمشغّلٍ جوّال). **الشرطان معاً**: لا حسابَ تجربةٍ آخر ولا حسابَ حقيقيٌّ يدخل هنا.
* **والتخطّي مشروطٌ بمفتاحٍ في Redis** (`SWITCH_KEY`) **بعمرٍ أقصاه ست ساعات**: يُشعَل قبل الحمل ويُنزع بعده (ويُقاس نزعُه) — **فما لم
  يُشعَل لا يتغيّر شيءٌ لأحد**، ولا لحساب الحمل نفسِه. **ولا طريقَ مختصراً للدخول**: جلساتُ الحمل تُصدَر على الخادم ببابها (`token_service`).
* **والمسارُ البديلُ خطٌّ مستقيمٌ بين النقاط × ١٫٣** (معاملُ الطريق) **بسرعة ٣٠ كم/س** — يكفي ليُسعَّر ويُرسم، **ولا نداءَ شبكة**؛ ويُعدّ
  (`STUB_COUNT_KEY`). **وكلُّ نداءٍ حقيقيٍّ لـMapbox يُعدّ** في `directions.fetch_route` (`calls_key`) — فيُقاس «صفرُ نداءٍ مدفوع» لا يُفترض.
"""

from __future__ import annotations

import math
from contextvars import ContextVar
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from app.core.redis_client import get_redis_client

if TYPE_CHECKING:  # pragma: no cover
    from app.models.user import User
    from app.services.directions import Coordinates, Route

#: **النطاقُ المحجوز** — «+962 7 19 …»: البادئةُ ٧١ غيرُ معطاةٍ لمشغّلٍ جوّالٍ في الأردن (المشغّلون ٧٧ · ٧٨ · ٧٩)
STRESS_PHONE_PREFIX = "+962719"
SWITCH_KEY = "stress:route_stub"
SWITCH_TTL_SECONDS = 6 * 60 * 60
STUB_COUNT_KEY = "stress:route_stub:count"
ROAD_FACTOR = Decimal("1.3")
STUB_SPEED_KMH = Decimal("30")
_KM = Decimal("0.001")
_MIN = Decimal("0.01")

_request_is_stress: ContextVar[bool] = ContextVar("stress_account", default=False)


def is_stress_account(user: User | None) -> bool:
    return user is not None and bool(user.is_test) and (user.phone or "").startswith(STRESS_PHONE_PREFIX)


def mark_request(user: User) -> None:
    """**يُسمّي الطلبَ الجاري** — من تبعيّة المصادقة؛ وطلبٌ لغيره يبقى كما كان."""
    _request_is_stress.set(is_stress_account(user))


def calls_key(day: str | None = None) -> str:
    """عدّادُ نداءات Mapbox الحقيقيّة في اليوم (UTC) — **ما يُقاس به «صفرُ نداءٍ مدفوع»**."""
    return f"directions:calls:{day or datetime.now(UTC).strftime('%Y%m%d')}"


async def stub_active() -> bool:
    """**طلبُ حسابِ حملٍ والمفتاحُ مشتعل** — الشرطان معاً."""
    if not _request_is_stress.get():
        return False
    return bool(await get_redis_client().exists(SWITCH_KEY))


def _haversine_km(a: Coordinates, b: Coordinates) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a.lat, a.lng, b.lat, b.lng))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


async def stub_route(*waypoints: Coordinates, with_geometry: bool = False) -> Route:
    from app.services.directions import Route

    km = sum((_haversine_km(a, b) for a, b in zip(waypoints, waypoints[1:])), 0.0)
    distance = (Decimal(str(km)) * ROAD_FACTOR).quantize(_KM, rounding=ROUND_HALF_UP)
    minutes = (distance / STUB_SPEED_KMH * 60).quantize(_MIN, rounding=ROUND_HALF_UP)
    await get_redis_client().incr(STUB_COUNT_KEY)
    geometry = [[p.lng, p.lat] for p in waypoints] if with_geometry else None
    return Route(distance_km=distance, duration_min=minutes, geometry=geometry, steps=None)
