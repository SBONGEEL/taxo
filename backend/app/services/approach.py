"""**«الكبتن يقترب»** (SPEC §61-ي/١١) — إشعارٌ للراكب حين يقترب كبتنُه، **مرّةً لكلِّ رحلة**.

**ولا يمسّ التوزيعَ ولا سيرَ الرحلة**: يُفعَّل بعد القبول (`arm`)، **ويُفحص في مسار بثّ الموقع نفسِه** (`check`) — وذلك المسارُ Redis
وحدَه كلَّ ثلاث ثوانٍ، **فلا قاعدةَ فيه إلا لحظةَ الإطلاق مرّةً**. **والعتبةُ مسافةٌ لا زمن**: لا زمنَ قيادةٍ يُحسب في النظام، وزمنٌ حقيقيٌّ يحتاج
نداءَ خرائطٍ مع كلِّ موقع أو سرعةً مخمَّنة — **فهي `notification_settings.approach_notice_meters`** (٨٠٠ م افتراضاً، تُضبط من اللوحة)،
**وتُقرأ عند القبول** فتسري على ما يُقبل بعد تغييرها.

**ومرّةً واحدة بقفلين لا بواحد**: `SET NX` في Redis يمنع أن يطرق كلُّ بثٍّ قريبٍ القاعدة، **والتحديثُ المشروطُ الذرّيّ** على
`rides.approach_notified_at` (`… WHERE status='accepted' AND approach_notified_at IS NULL`) **هو الحَكَم** — فلا يُرسل مرّتين ولو ضاع
مفتاحُ Redis أو تزامن موقعان، **ولا يُرسل لرحلةٍ تجاوزت «في الطريق إلى الراكب»**.

**وسقوطُه لا يُسقط بثَّ الموقع**: يُسجَّل ويُبتلع كما في `route.capture` — كبتنٌ يختفي من الخريطة لأن إشعاراً تعثّر خسارةٌ أكبر.
"""

from __future__ import annotations

import logging
import math
import uuid

from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models.enums import CountryCode, RideStatus
from app.models.notification import NotificationSetting
from app.models.ride import Ride

logger = logging.getLogger(__name__)

DEFAULT_APPROACH_METERS = 800
# عمرُ المفتاحين — أطولُ من أيِّ طريقٍ إلى راكب، ويزولان وحدَهما
APPROACH_TTL_SECONDS = 2 * 60 * 60


def armed_key(driver_id: uuid.UUID | str) -> str:
    return f"approach:armed:{driver_id}"


def done_key(ride_id: uuid.UUID | str) -> str:
    return f"approach:done:{ride_id}"


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """مسافةُ خطٍّ مستقيمٍ على الكرة بالأمتار (هافرساين) — عتبةٌ لا ملاحة."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def threshold_for(session: AsyncSession, country_code: CountryCode) -> int:
    """مسافةُ السوق — **قراءةٌ لا إنشاء** (بابُ اللوحة هو من يُنشئ صفَّ السوق)، والافتراضُ حين لا صفّ."""
    value = await session.scalar(
        select(NotificationSetting.approach_notice_meters).where(
            NotificationSetting.country_code == country_code
        )
    )
    return int(value) if value else DEFAULT_APPROACH_METERS


async def arm(
    redis: Redis,
    session: AsyncSession,
    *,
    driver_id: uuid.UUID,
    ride_id: uuid.UUID,
    country_code: CountryCode,
    pickup_lat: float,
    pickup_lng: float,
) -> None:
    """يُفعَّل بعد القبول: الرحلةُ ونقطةُ الانطلاق والمسافةُ في مفتاحٍ واحدٍ يقرؤه بثُّ الموقع."""
    meters = await threshold_for(session, country_code)
    key = armed_key(driver_id)
    await redis.hset(
        key,
        mapping={"ride_id": str(ride_id), "lat": str(pickup_lat), "lng": str(pickup_lng), "meters": str(meters)},
    )
    await redis.expire(key, APPROACH_TTL_SECONDS)


async def check(redis: Redis, *, driver_id: uuid.UUID, lat: float, lng: float) -> None:
    """يُنادى مع كلِّ بثّ موقع — **قراءةُ مفتاحٍ واحدٍ لمن لا رحلةَ له**، ولا قاعدةَ إلا لحظةَ الإطلاق."""
    try:
        armed = await redis.hgetall(armed_key(driver_id))
        if not armed:
            return
        if distance_m(lat, lng, float(armed["lat"]), float(armed["lng"])) > float(armed["meters"]):
            return
        ride_id = armed["ride_id"]
        if not await redis.set(done_key(ride_id), "1", nx=True, ex=APPROACH_TTL_SECONDS):
            return
        await redis.delete(armed_key(driver_id))
        await _fire(redis, uuid.UUID(ride_id))
    except Exception:  # pragma: no cover - لا يُسقط بثَّ الموقع
        logger.exception("تعذّر فحصُ «الكبتن يقترب» للكبتن %s", driver_id)


async def _fire(redis: Redis, ride_id: uuid.UUID) -> None:
    from app.services import notifications
    from app.services import rides as rides_service

    async with SessionLocal() as session:
        claimed = await session.scalar(
            update(Ride)
            .where(
                Ride.id == ride_id,
                Ride.status == RideStatus.ACCEPTED,
                Ride.approach_notified_at.is_(None),
            )
            .values(approach_notified_at=func.now())
            .returning(Ride.id)
        )
        if claimed is None:
            await session.rollback()
            return
        await session.commit()
        ride = await rides_service.get_ride(session, ride_id)
        await notifications.publish_driver_approaching(session, redis, ride)
