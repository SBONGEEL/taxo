"""شكلُ مسار الرحلة على الطرق — للطرفين بعد القبول (البند ٨، 2026-08-14).

**قرارُ المالك (2026-08-14)**: يُطلب **مرةً عند القبول ويُحفظ على الرحلة**، لا على
مسار التقدير. والتفريقُ عن `DESIGN-DECISIONS` بند 38 قرارُه أيضاً: ذاك يمنع خطاً
**نرسمه نحن** بين نقطتين — وهو يوهم بمسارٍ لم يقله أحد؛ وهذا **مسارٌ قاله Mapbox**.

وثلاثُ قواعدَ تحكمه:

- **لا يُطلب قبل القبول.** التقديرُ يُنادى مع كل تحريكِ دبوس، وشكلُ المسار حمولةٌ
  تُرسل لمن لم يطلب رحلةً بعد — ونداءٌ لكل تحريكٍ يضاعف كلفةَ Mapbox بلا قارئ.
- **ولا يُعاد طلبُه بعد أن يُكتب.** طلبٌ ثانٍ لاحقاً قد يعطي مساراً آخر (زحمةٌ
  تبدّلت)، فيرى الراكبُ خطاً والكبتنُ غيرَه على رحلةٍ واحدة. تجميدٌ كتجميد العمولة.
- **وفشلُه لا يُفشل شيئاً.** عقدٌ مطفأٌ أو نداءٌ سقط ⇒ `None`، والتطبيقُ يرسم
  الدبوسين وحدهما. وهو نفسُ ما يفعله التقاطُ نقاط المسار: أثرٌ لا يُسقط رحلةً.

**والنداءُ خارج قفل صفِّ الرحلة**: القبولُ يُنهي معاملتَه أولاً ثم يُطلب الشكل
(`routers/rides.accept_ride` بعد الـcommit) — قاعدةُ «لا يُحمل قفلُ صفٍّ عبر نداء
مزوّدٍ يمكن أن يقع قبله» (`CLAUDE.md`).
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.redis_client import get_redis_client
from app.models.ride import Ride, RideStop
from app.services import directions

logger = logging.getLogger(__name__)

# قبل القبول لا خطَّ: لا كبتنَ ولا رحلةَ يُساقُ فيها بعد
DRAWABLE_STATUSES = frozenset(
    {"accepted", "arrived", "in_progress", "at_stop", "completed"}
)


def decode(stored: str | None) -> list[list[float]] | None:
    """يقرأ العمودَ نصّاً ويعيد الإحداثيات — و`None` لكل ما ليس مسارَ نقطتين."""
    if not stored:
        return None
    try:
        points = json.loads(stored)
    except json.JSONDecodeError:  # pragma: no cover - صفٌّ تالفٌ لا يُكتب من هنا
        return None
    if not isinstance(points, list) or len(points) < 2:
        return None
    return points


# **سقفُ إعادة التوجيه لكل رحلة** (البند ١٧-٤) — وهو **الشيءُ الوحيد الذي يعاود
# نداءَ Directions**، فالسقفُ هو ما يجعل الفاتورةَ محسوبةً سلفاً.
#
# وحسابُ المالك: عند ألف رحلةٍ يومياً، ٤ نداءاتٍ لكل رحلة اليومَ → ١٢٠ ألفاً
# شهرياً؛ وبثلاثِ إعاداتٍ كحدٍّ أقصى → ٢٧٠ ألفاً. **والسقفُ في الخلفية لا في
# التطبيق**: عميلٌ يعدّ لنفسه هو عميلٌ يوجّه إنفاقاً — والقاعدةُ نفسُها التي
# تجعل `card_gateway.return_url_for` لا يقبل ادّعاءَ العميل.
MAX_REROUTES = 3


async def reroute(
    session: AsyncSession, ride_id: uuid.UUID
) -> tuple[list[list[float]] | None, int]:
    """يعيد رسمَ المسار من موضع الكبتن — **إن بقي من سقفها شيء**.

    يعيد (المسار، ما بقي من السقف). الـcommit للمستدعي.

    **ولا يُعاد الرسمُ من نقطة الانطلاق** بل **من موقع الكبتن الآن**: من انحرف
    عن الطريق لا يعيده خطٌّ يبدأ حيث لم يعد.

    **وفشلُه يُبقي الخطَّ القديم** ولا يمحوه: خطٌّ قديمٌ أنفعُ من لا خطّ، وهو
    قاعدةُ `ensure` نفسُها — الخطُّ زينةُ خريطةٍ لا شرطُ رحلة.

    **والسقفُ يُستهلك بالمحاولة الناجحة وحدَها**: نداءٌ سقط لم يكلّف شيئاً،
    وخصمُه من رصيدِ كبتنٍ انحرف مرةً يجعل العطبَ عقوبةً عليه.
    """
    from app.services import geo

    ride = await session.get(Ride, ride_id)
    if ride is None:  # pragma: no cover
        return None, 0
    if ride.status.value not in DRAWABLE_STATUSES or ride.driver_id is None:
        return decode(ride.route_polyline), 0

    left = MAX_REROUTES - (ride.reroute_count or 0)
    if left <= 0:
        return decode(ride.route_polyline), 0

    position = await geo.last_position(
        get_redis_client(),
        driver_id=ride.driver_id,
        country_code=ride.country_code,
    )
    if position is None:
        # **ولا يُعاد الرسمُ بلا موضعٍ معروف**: البديلُ هو الانطلاقُ من نقطةٍ
        # مضت، وهو أسوأُ من الخطِّ القائم
        return decode(ride.route_polyline), left

    stops = (
        await session.scalars(
            select(RideStop)
            .where(RideStop.ride_id == ride.id, RideStop.arrived_at.is_(None))
            .order_by(RideStop.sequence)
        )
    ).all()

    try:
        route = await directions.route_between(
            session,
            directions.Coordinates(lat=position.lat, lng=position.lng),
            directions.Coordinates(lat=ride.dropoff_lat, lng=ride.dropoff_lng),
            country_code=ride.country_code,
            stops=[
                directions.Coordinates(lat=stop.lat, lng=stop.lng) for stop in stops
            ],
            with_geometry=True,
        )
    except AppError as exc:
        logger.warning("تعذّرت إعادة توجيه الرحلة %s: %s", ride_id, exc.code)
        return decode(ride.route_polyline), left

    if route.geometry is None:
        return decode(ride.route_polyline), left

    ride.route_polyline = json.dumps(route.geometry, separators=(",", ":"))
    ride.reroute_count = (ride.reroute_count or 0) + 1
    await session.flush()
    return route.geometry, MAX_REROUTES - ride.reroute_count


async def ensure(session: AsyncSession, ride_id: uuid.UUID) -> list[list[float]] | None:
    """يُرجع شكلَ المسار، ويطلبه من Mapbox مرةً واحدةً إن لم يكن مكتوباً.

    الـcommit للمستدعي. ويعيد `None` بلا استثناء إن تعذّر — الخطُّ زينةُ خريطةٍ
    لا شرطُ رحلة.
    """
    ride = await session.get(Ride, ride_id)
    if ride is None:  # pragma: no cover - يُتحقق من الملكية قبله
        return None

    stored = decode(ride.route_polyline)
    if stored is not None:
        return stored
    if ride.status.value not in DRAWABLE_STATUSES:
        return None

    stops = (
        await session.scalars(
            select(RideStop)
            .where(RideStop.ride_id == ride.id)
            .order_by(RideStop.sequence)
        )
    ).all()

    try:
        route = await directions.route_between(
            session,
            directions.Coordinates(lat=ride.pickup_lat, lng=ride.pickup_lng),
            directions.Coordinates(lat=ride.dropoff_lat, lng=ride.dropoff_lng),
            country_code=ride.country_code,
            stops=[
                directions.Coordinates(lat=stop.lat, lng=stop.lng) for stop in stops
            ],
            with_geometry=True,
        )
    except AppError as exc:
        # **يُبتلع خطأُ المزوّد وحدَه** لا كلُّ استثناء: `except Exception` هنا
        # هو ما ابتلع `AttributeError` في 12-ط وخزّن NULL بلا أن يعرف أحد
        logger.warning("تعذّر جلب شكل مسار الرحلة %s: %s", ride_id, exc.code)
        return None

    if route.geometry is None:
        return None

    ride.route_polyline = json.dumps(route.geometry, separators=(",", ":"))
    await session.flush()
    return route.geometry
