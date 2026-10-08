"""زمنُ الوصول (§٦٢-ج/١٠) — **نداءاتُ Mapbox مخزَّنةً قصيرةَ العمر، خلف مفتاحٍ لكلِّ سوق** (`eta_enabled`، مطفأٌ افتراضاً).

**والكلفةُ على المالك فتُعدّ** (قولُه في القائمة: «يُقاس عددُ النداءات ويُكتب»): كلُّ نداءٍ يخرج من هنا يُحصى في
`eta:calls:{السوق}:{اليوم}`، **ولا نداءَ حيث يكفي حسابٌ في الجهاز** — وهي قاعدةُ `FUTURE-FEATURES` (الخرائط، ج): **الاستطلاعُ
يضاعف الفاتورة سبعَ مرّات**، فالوقتُ المتبقّي يُحسب في التطبيق من الخطّ المخزَّن وسرعةِ الحركة، **والخادمُ يرسم الخطَّ مرّةً**.

**وثلاثةُ نداءاتٍ لا غيرها**:

1. **مسارُ العرض** (C05 «1.2 كم · 4 د حتى الراكب»): يطلبه الكبتنُ المعروضُ عليه بعد أن يصله العرض — فلا يتأخّر العرضُ ببطء
   مزوّد — **ويُخزَّن لـ`OFFER_FRESH_S`**.
2. **مسارُ الاقتراب** (C06 و R08 «في الطريق إليك · 5 د»): **هو مسارُ العرض نفسُه إن قُبل وهو طازج** — فلا نداءَ ثانٍ عند القبول —
   وإلا نداءٌ واحدٌ يُخزَّن ما بقيت الرحلةُ في طريقها. **ويُصلح خطأً قائماً**: الوقتُ في الطريق إلى الراكب كان يُحسب على خطِّ الرحلة
   إلى الوجهة (`TAXO2-DESIGN-CORRECTIONS` §٣٥) — والكبتنُ لم يبلغ بدايتَه بعد.
3. **أقربُ كبتنٍ لكلِّ فئةٍ قبل الطلب** (R05 · R06 «تصل خلال 3 د»): نداءٌ لكلِّ فئةٍ فيها كبتنٌ متاح، **مخزَّنٌ دقيقةً لكلِّ خليّةٍ**
   (منزلتان عشريّتان ونصف ≈ ٥٥٠ م) — فتحريكُ الدبوس في الحيّ نفسِه لا يدفع ثمنَ نداء.

**والفشلُ لا يُفشل شيئاً**: لا مفتاح، أو لا موقعَ مبثوث، أو سقط المزوّد ⇐ لا رقم — والشاشةُ تسكت كما سكتت قبل هذا البند.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.enums import CountryCode, FeatureKey, RideStatus, VehicleCategory
from app.models.ride import Ride
from app.models.user import User
from app.services import directions, geo, settings_service

logger = logging.getLogger(__name__)

#: مسارُ العرض يُعاد استعمالُه للاقتراب ما دام أحدثَ من دقيقتين — بعدها تحرّك الكبتنُ بما يكفي ليختلف الطريق
OFFER_FRESH_S = 120
#: الاقترابُ يبقى ما بقيت الرحلةُ في طريقها — ثلاثُ ساعاتٍ تتجاوز أطولَ انتظارٍ مقبول
APPROACH_TTL_S = 3 * 3600
#: الأقربُ قبل الطلب — دقيقةٌ لكلِّ خليّة: الكباتنُ يتحرّكون، والرقمُ لا يُعرض أقدمَ من ذلك
NEAREST_TTL_S = 60
#: العدّادُ يبقى أربعين يوماً — شهرٌ كاملٌ يُقرأ مع فائضٍ لمن يقرؤه متأخّراً
CALLS_TTL_S = 40 * 86400

#: حالاتُ «في الطريق إلى الراكب» — وبعد الوصول لا اقترابَ يُرسم
APPROACHING = frozenset({RideStatus.ACCEPTED})


def _approach_key(ride_id: uuid.UUID) -> str:
    return f"ride:{ride_id}:approach"


def _offer_key(ride_id: uuid.UUID, driver_id: uuid.UUID) -> str:
    return f"ride:{ride_id}:offer-route:{driver_id}"


def calls_key(country: CountryCode, day: str) -> str:
    """عدّادُ نداءات اليوم لسوق — **يُقرأ في القياس وفي أيِّ لوحةٍ تُبنى لاحقاً**."""
    return f"eta:calls:{country.value}:{day}"


async def enabled(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(session, country, FeatureKey.ETA_ENABLED)


async def _route(
    session: AsyncSession,
    redis: Redis,
    country: CountryCode,
    origin: directions.Coordinates,
    destination: directions.Coordinates,
    *,
    with_geometry: bool,
    with_steps: bool = False,
) -> directions.Route | None:
    """نداءٌ واحدٌ يُحصى — **والحصرُ قبل الجواب**: نداءٌ سقط قد كُلِّف أيضاً."""
    key = calls_key(country, datetime.now(UTC).strftime("%Y%m%d"))
    await redis.incr(key)
    await redis.expire(key, CALLS_TTL_S)
    try:
        return await directions.route_between(
            session,
            origin,
            destination,
            country_code=country,
            with_geometry=with_geometry,
            with_steps=with_steps,
        )
    except AppError as exc:
        # **خطأُ المزوّد وحدَه يُبتلع** — كقاعدة `route_line.ensure`: استثناءٌ آخرُ عطبٌ يُرى
        logger.warning("تعذّر حسابُ زمن الوصول: %s", exc.code)
        return None


def _pack(route: directions.Route) -> dict[str, Any]:
    return {
        "points": route.geometry or [],
        "steps": route.steps or [],
        "duration_min": float(route.duration_min),
        "distance_km": float(route.distance_km),
    }


async def _wants_steps(session: AsyncSession, ride: Ride) -> bool:
    """خطواتُ الملاحة تُطلب **حيث يُرسم شريطُها** — مفتاحُ `next_instruction_enabled` نفسُه (حمولةٌ لا نداء)."""
    return await settings_service.is_feature_enabled(
        session, ride.country_code, FeatureKey.NEXT_INSTRUCTION_ENABLED
    )


async def offer_route(
    session: AsyncSession, redis: Redis, *, ride: Ride, driver_id: uuid.UUID
) -> dict[str, Any] | None:
    """مسارُ الكبتن المعروضِ عليه إلى نقطة الالتقاء (C05) — **مخزَّنٌ لـ`OFFER_FRESH_S`** فيصير اقترابَه إن قَبِل."""
    if not await enabled(session, ride.country_code):
        return None
    cached = await redis.get(_offer_key(ride.id, driver_id))
    if cached:
        return json.loads(cached)
    here = await geo.last_position(redis, driver_id=driver_id, country_code=ride.country_code)
    if here is None:
        return None
    route = await _route(
        session,
        redis,
        ride.country_code,
        directions.Coordinates(lat=here.lat, lng=here.lng),
        directions.Coordinates(lat=ride.pickup_lat, lng=ride.pickup_lng),
        with_geometry=True,
        with_steps=await _wants_steps(session, ride),
    )
    if route is None or not route.geometry:
        return None
    packed = _pack(route)
    await redis.set(_offer_key(ride.id, driver_id), json.dumps(packed), ex=OFFER_FRESH_S)
    return packed


async def approach(session: AsyncSession, redis: Redis, *, ride: Ride) -> dict[str, Any] | None:
    """مسارُ الاقتراب — **المخزَّنُ أوّلاً، ثمّ مسارُ العرض الطازجُ نفسُه، ثمّ نداءٌ واحد** (رأسُ الملف).

    **ولا يُطلب بعد الوصول**: من وقف عند الراكب لا طريقَ يُرسم إليه. والمخزَّنُ يُقرأ ما بقي — فقارئٌ متأخّرٌ لا يدفع نداءً.
    """
    stored = await redis.get(_approach_key(ride.id))
    if stored:
        return json.loads(stored)
    if ride.status not in APPROACHING or ride.driver_id is None:
        return None
    if not await enabled(session, ride.country_code):
        return None

    fresh = await redis.get(_offer_key(ride.id, ride.driver_id))
    if fresh:
        packed = json.loads(fresh)
    else:
        here = await geo.last_position(redis, driver_id=ride.driver_id, country_code=ride.country_code)
        if here is None:
            return None
        route = await _route(
            session,
            redis,
            ride.country_code,
            directions.Coordinates(lat=here.lat, lng=here.lng),
            directions.Coordinates(lat=ride.pickup_lat, lng=ride.pickup_lng),
            with_geometry=True,
            with_steps=await _wants_steps(session, ride),
        )
        if route is None or not route.geometry:
            return None
        packed = _pack(route)
    await redis.set(_approach_key(ride.id), json.dumps(packed), ex=APPROACH_TTL_S)
    return packed


def _cell(value: float) -> str:
    """خليّةُ التخزين — **نصفُ منزلةٍ ثالثة** (≈٥٥٠ م): الحيُّ نفسُه خليّةٌ واحدة."""
    return f"{math.floor(value * 200) / 200:.3f}"


async def nearest_minutes(
    session: AsyncSession,
    redis: Redis,
    *,
    rider: User,
    lat: float,
    lng: float,
) -> dict[VehicleCategory, int]:
    """دقائقُ أقربِ كبتنٍ متاحٍ لكلِّ فئةٍ إلى النقطة (R05 · R06) — **المتاحُ كما يراه التوزيع** (`drivers.nearby_available`
    بتفضيلها)، **ونداءٌ لكلِّ فئةٍ في الخليّة كلَّ دقيقةٍ على الأكثر**. وفئةٌ بلا كبتنٍ متاحٍ لا رقمَ لها — لا «بعيد».
    """
    country = rider.country_code
    if not await enabled(session, country):
        return {}
    from app.services import drivers as drivers_service

    presences = await drivers_service.nearby_available(
        redis, session, country_code=country, lat=lat, lng=lng, rider=rider
    )
    closest: dict[VehicleCategory, Any] = {}
    for presence in presences:  # مرتّبون من الأقرب
        closest.setdefault(presence.vehicle_category, presence)

    minutes: dict[VehicleCategory, int] = {}
    # **والخليّةُ لكلِّ عالمٍ على حدة** (SPEC §٦٥-ج): الخريطةُ أعلاه تعزل كبتنَ التجربة، **والمخزَّنُ مشتركٌ بين كلِّ من في
    # الخليّة** — فدقائقُ حسبها راكبُ التجربة من كبتن تجربةٍ كانت ستُعرض دقيقةً كاملةً على راكبٍ حقيقيٍّ بجانبه
    world = ":test" if rider.is_test else ""
    for category, presence in closest.items():
        key = f"eta:nearest:{country.value}:{category.value}:{_cell(lat)}:{_cell(lng)}{world}"
        cached = await redis.get(key)
        if cached is not None:
            minutes[category] = int(cached)
            continue
        route = await _route(
            session,
            redis,
            country,
            directions.Coordinates(lat=presence.lat, lng=presence.lng),
            directions.Coordinates(lat=lat, lng=lng),
            with_geometry=False,
        )
        if route is None:
            continue
        # **دقيقةٌ واحدةٌ حدٌّ أدنى** — «تصل خلال 0 د» تُقرأ عطباً لا وصولاً (قاعدةُ `lib/eta` في التطبيق)
        value = max(1, math.ceil(float(route.duration_min)))
        await redis.set(key, str(value), ex=NEAREST_TTL_S)
        minutes[category] = value
    return minutes
