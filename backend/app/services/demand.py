"""«الطلب مرتفع» حول الكبتن (§٦٢-ج/٤٣، رئيسيةُ الكبتن C04).

**عدٌّ لا خريطة، ولا مضاعِفَ سعر**: خريطةُ الطلب بمناطقها ومضاعِفاتها («عبدون ×1.4») لا تُبنى — التسعيرُ المتحرّك «لا يُبنى الآن»
بقول المالك (§١٥-ب). **ويُبنى ما يقوله العدُّ وحدَه**: ما طُلب حول الكبتن في آخر ربع ساعة، مقارَناً بمن يستقبل حوله الآن.

**والقاعدة**: مرتفعٌ حين تبلغ الطلباتُ **ثلاثاً** في **ثلاثة كيلومترات** خلال **ربع ساعة**، **وتزيد على الكباتن المتاحين** في الدائرة
نفسِها (سواه). **فالطلبُ وحدَه لا يكفي**: عشرةُ طلباتٍ حولها عشرون كبتناً ليست طلباً مرتفعاً لمن يقرأ الجملةَ ليتحرّك إليها.

**ولا يخرج من الباب إلا نعم/لا** — لا عددٌ ولا موضع: الطلباتُ مواقعُ ركّاب، وعددُها حول نقطةٍ يختارها السائلُ يُقرأ خريطةً لمن
يسأل كلَّ دقيقةٍ من مكانٍ آخر. **والنقطةُ موقعُ الكبتن المبثوثُ نفسُه** (`geo.last_position`) لا إحداثيّاتٌ يرسلها التطبيق — فلا
يُسأل عن مكانٍ ليس فيه. **وبلا بثٍّ حيٍّ لا جواب** (`False`): من لا يستقبل لا طلبَ «حوله».
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver
from app.models.enums import CountryCode
from app.models.ride import Ride
from app.services import geo

WINDOW_MINUTES = 15
RADIUS_KM = 3.0
MIN_REQUESTS = 3
# **سقفُ من يُعدّ من الكباتن** — يكفي أن يُعرف أنهم بلغوا عددَ الطلبات؛ وقائمةٌ بلا سقفٍ تقرأ كلَّ سوقٍ في كلِّ سؤال
SUPPLY_CAP = 200

_EARTH_KM = 6371.0088


def _km_between(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """مسافةٌ على الكرة — **هندسةٌ لا مال**، تقرّر شرطاً ثمّ تُنسى (كـ`cancellation._metres_between`)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_lat = p2 - p1
    d_lng = math.radians(lng2 - lng1)
    h = math.sin(d_lat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lng / 2) ** 2
    return 2 * _EARTH_KM * math.asin(math.sqrt(h))


async def high_near(
    session: AsyncSession,
    redis: Redis,
    *,
    driver: Driver,
    country: CountryCode,
    now: datetime,
) -> bool:
    """أمرتفعٌ الطلبُ حول هذا الكبتن الآن؟ — **نعم/لا وحدَها** (انظر رأسَ الملف)."""
    here = await geo.last_position(redis, driver_id=driver.id, country_code=country)
    if here is None:
        return False

    # **مربّعٌ في القاعدة ثمّ دائرةٌ هنا**: الفهرسُ يقصّ ما بعُد، والمسافةُ الحقيقيةُ تُحسم على القليل الباقي
    d_lat = RADIUS_KM / 111.0
    d_lng = RADIUS_KM / (111.0 * max(math.cos(math.radians(here.lat)), 0.01))
    rows = await session.execute(
        select(Ride.pickup_lat, Ride.pickup_lng).where(
            Ride.country_code == country,
            Ride.created_at >= now - timedelta(minutes=WINDOW_MINUTES),
            Ride.created_at <= now,
            Ride.pickup_lat.between(here.lat - d_lat, here.lat + d_lat),
            Ride.pickup_lng.between(here.lng - d_lng, here.lng + d_lng),
        )
    )
    requests = sum(
        1
        for lat, lng in rows.all()
        if _km_between(here.lat, here.lng, float(lat), float(lng)) <= RADIUS_KM
    )
    if requests < MIN_REQUESTS:
        return False

    # **والمتاحون كما يراهم التوزيعُ وخريطةُ الراكب** (`drivers.nearby_available`) — لا الحاضرون وحدَهم: من في رحلةٍ أو بلا
    # اشتراكٍ لا يلتقط طلباً، فعدُّه عرضاً يُخفي طلباً مرتفعاً حقاً
    from app.services import drivers as drivers_service

    available = await drivers_service.nearby_available(
        redis,
        session,
        country_code=country,
        lat=here.lat,
        lng=here.lng,
        radius_km=RADIUS_KM,
        max_count=SUPPLY_CAP,
    )
    others = sum(1 for presence in available if presence.driver_id != driver.id)
    return requests > others
