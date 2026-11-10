"""**«وجهتي»** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٥) — الكبتنُ يضع وجهةً فلا تصله إلا الطلباتُ في اتّجاهها.

* **الوجهةُ في Redis بمهلة** (`DEST_TTL`) لا في القاعدة: حالٌ عابرة، **وضياعُها يعيده إلى كلِّ الطلبات** — الاتجاهُ الآمنُ للخطأ.
* **مرّاتُ اليوم** من `dispatch_settings.destination_daily_uses` بيوم الدولة، **و`0` يطفئ الميزةَ في السوق**. والإلغاءُ لا يردّ مرّة.
* **«في اتّجاهها»** بقاعدتين معاً (`fits`): **الإنزالُ أقربُ إلى الوجهة من موضع الكبتن الآن**، **والانحرافُ** — طولُ «إلى الراكب ثم
  الإنزال ثم الوجهة» ناقصاً الطريقَ المباشر — **لا يزيد على نسبة اللوحة** من الطريق المباشر (وكيلومترٌ واحدٌ حدّاً أدنى: داخلَ
  المدينة نسبةٌ من طريقٍ قصيرٍ أمتار). **بخطٍّ مستقيمٍ لا بطريق** — تقريبٌ رخيصٌ في مسارٍ يمرّ به كلُّ طلب، ويُقال كذلك.
* **ويُطبَّق في التوزيع وحدَه** (`dispatch._ranked_candidates`) بعد شروط الأهليّة: من لا وجهةَ له لا يتغيّر عليه شيء.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput
from app.models.enums import CountryCode
from app.services import dispatch_settings

#: **أربعُ ساعات** — ورديّةُ عودةٍ إلى البيت لا يومٌ كامل؛ وبعدها يعود إلى كلِّ الطلبات بلا أن يتذكّر أحد
DEST_TTL = timedelta(hours=4)
#: أدنى انحرافٍ مقبولٍ بالكيلومتر مهما قصر الطريق
MIN_DETOUR_KM = 1.0


@dataclass(frozen=True, slots=True)
class Destination:
    lat: float
    lng: float
    label: str
    set_at: datetime


def _key(driver_id: uuid.UUID) -> str:
    return f"driver:dest:{driver_id}"


def _uses_key(driver_id: uuid.UUID, day: str) -> str:
    return f"driver:dest:uses:{driver_id}:{day}"


def km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rad = math.radians
    dlat, dlng = rad(lat2 - lat1), rad(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlng / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def fits(
    dest: Destination,
    *,
    driver_lat: float,
    driver_lng: float,
    pickup_lat: float,
    pickup_lng: float,
    dropoff_lat: float,
    dropoff_lng: float,
    detour_percent: int,
) -> bool:
    direct = km(driver_lat, driver_lng, dest.lat, dest.lng)
    remaining = km(dropoff_lat, dropoff_lng, dest.lat, dest.lng)
    if remaining >= direct:
        return False
    via = (
        km(driver_lat, driver_lng, pickup_lat, pickup_lng)
        + km(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        + remaining
    )
    return via - direct <= max(MIN_DETOUR_KM, direct * detour_percent / 100)


def _decode(raw: str | bytes | None) -> Destination | None:
    if not raw:
        return None
    data = json.loads(raw)
    return Destination(
        lat=float(data["lat"]), lng=float(data["lng"]), label=str(data["label"]),
        set_at=datetime.fromisoformat(data["set_at"]),
    )


async def current(redis: Redis, driver_id: uuid.UUID) -> Destination | None:
    return _decode(await redis.get(_key(driver_id)))


async def _today(session: AsyncSession, country: CountryCode, now: datetime) -> str:
    from app.services.stats import _zone

    return now.astimezone(await _zone(session, country)).date().isoformat()


async def uses_today(session: AsyncSession, redis: Redis, driver_id: uuid.UUID, country: CountryCode, now: datetime) -> int:
    return int(await redis.get(_uses_key(driver_id, await _today(session, country, now))) or 0)


async def set_destination(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_id: uuid.UUID,
    country: CountryCode,
    lat: float,
    lng: float,
    label: str,
    now: datetime | None = None,
) -> Destination:
    now = now or datetime.now(UTC)
    rules = await dispatch_settings.rules_for(session, country)
    if rules.destination_daily_uses <= 0:
        raise InvalidInput("«وجهتي» غير متاحة في دولتك الآن")
    day = await _today(session, country, now)
    used = await redis.incr(_uses_key(driver_id, day))
    if used == 1:
        await redis.expire(_uses_key(driver_id, day), int(timedelta(days=2).total_seconds()))
    if used > rules.destination_daily_uses:
        await redis.decr(_uses_key(driver_id, day))
        raise InvalidInput("استنفدت مرّات «وجهتي» لهذا اليوم")
    dest = Destination(lat=lat, lng=lng, label=label.strip()[:80] or "وجهتي", set_at=now)
    await redis.set(
        _key(driver_id),
        json.dumps({"lat": lat, "lng": lng, "label": dest.label, "set_at": now.isoformat()}),
        ex=int(DEST_TTL.total_seconds()),
    )
    return dest


async def clear(redis: Redis, driver_id: uuid.UUID) -> None:
    await redis.delete(_key(driver_id))


async def keep_heading(session: AsyncSession, redis: Redis, *, ride, ranked: list) -> list:
    """**من وضع وجهةً لا يبقى إلا إن كان الطلبُ في اتّجاهها** — ومن لا وجهةَ له كما هو. نداءٌ واحدٌ لـRedis للقائمة كلِّها."""
    if not ranked:
        return ranked
    raws = await redis.mget([_key(p.driver_id) for p in ranked])
    if not any(raws):
        return ranked
    rules = await dispatch_settings.rules_for(session, ride.country_code)
    kept = []
    for presence, raw in zip(ranked, raws, strict=True):
        dest = _decode(raw)
        if dest is None or fits(
            dest,
            driver_lat=presence.lat,
            driver_lng=presence.lng,
            pickup_lat=ride.pickup_lat,
            pickup_lng=ride.pickup_lng,
            dropoff_lat=ride.dropoff_lat,
            dropoff_lng=ride.dropoff_lng,
            detour_percent=rules.destination_detour_percent,
        ):
            kept.append(presence)
    return kept
