"""**الازدحامُ من كباتننا — مجهولاً مجمَّعاً** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّة ٣-٢؛ `design/MAP-OPEN-DATA-TRAFFIC.md`).

**الطريقة طريقةُ OpenTraffic** (والشيفرةُ لا — رخصتُها LGPL ومتوقّفة): نقطةٌ بلا هويّة ⇐ سرعةٌ على مقطع طريق ⇐ متوسّطٌ لكلِّ مقطع
**لا يُنشر إلا إذا مرّ به `K_MIN` كباتن مختلفون** في النافذة.

**وما يُحفظ، وما لا يُحفظ** (يُقال في سياسة الخصوصية بالنصّ نفسِه):
1. **السرعةُ تُحسب في الخادم** من موقعين متتاليين للكبتن نفسِه **يصلان أصلاً** (بثُّ الموقع القائم) — لا بثَّ جديد.
2. **العيّنةُ بلا هويّة**: موضعٌ واتجاهٌ وسرعة، **وبصمةٌ مملّحةٌ بملحِ النافذة** (ربعُ ساعة) لعدِّ المختلفين وحدَه — والملحُ يُمحى بعد
   النافذة، **فلا تُربط بصمةٌ بكبتنٍ ولا نافذةٌ بأخرى**.
3. **العيّناتُ تُمحى عند التجميع** (كلَّ خمس دقائق)، وما يبقى **مجموعُ السرعات وعددُها لكلِّ مقطع** ومجموعةُ البصمات حتى تنقضي النافذة.
4. **لا شيءَ في القاعدة** — Redis وحدَه، وكلُّ مفتاحٍ بعمرٍ ينقضي.
5. **وأقلُّ من `K_MIN` ⇒ لا لون**: لا يُرسم «سالكٌ» لطريقٍ لم يمرّ به أحد.

**ولا يمسّ الأجرةَ ولا مسارَها ولا معادلتَها** — العرضُ وحدَه (المهمّة ٣-٥). ولا يعمل إلا والمفتاحُ مشتعلٌ للدولة (`map_live_traffic`).
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import time
import uuid

import httpx
from redis.asyncio import Redis

from app.core.config import settings
from app.models.enums import CountryCode

#: **أقلُّ عددِ كباتن مختلفين** ليُرسم لونُ مقطع — فلا يُعرف كبتنٌ بعينه من لونٍ مرّ وحده به
K_MIN = 3
#: نافذةُ التجميع والملح — ربعُ ساعة
WINDOW_S = 900
#: أقصى ما بين موقعين لتُحسب منهما سرعة — وأبعدُ من هذا ليس «سيراً متّصلاً»
MAX_GAP_S = 60
MIN_GAP_S = 3
RAW_CAP = 20_000

_ON = "traffic:on:{cc}"
_RAW = "traffic:raw:{cc}"
_SALT = "traffic:salt:{w}"
_ACC = "traffic:acc:{cc}:{w}"
_WHO = "traffic:who:{cc}:{w}:{seg}"
_GEOM = "traffic:geom:{seg}"
_VIEW = "traffic:view:{cc}"


def window(now: float | None = None) -> int:
    return int((now or time.time()) // WINDOW_S)


def metres(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dx = (lng2 - lng1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 110_540
    return math.hypot(dx, dy)


async def previous(redis: Redis, *, driver_id: uuid.UUID, country_code: CountryCode) -> tuple[float, float, int] | None:
    """**الموقعُ السابقُ ولحظتُه** — يُقرأ قبل أن يكتب البثُّ فوقه، **ولا شيءَ والمفتاحُ مطفأ** (فلا قراءةَ زائدةَ على كلِّ بثّ)."""
    from app.services import geo

    cc = CountryCode(country_code).value
    if not await redis.exists(_ON.format(cc=cc)):
        return None
    pipe = redis.pipeline()
    pipe.geopos(geo.geo_key(country_code), str(driver_id))
    pipe.hget(geo.presence_key(driver_id), "at")
    position, at = await pipe.execute()
    if not position or not position[0] or not at:
        return None
    lng, lat = position[0]
    return float(lat), float(lng), int(at)


async def sample(
    redis: Redis,
    *,
    driver_id: uuid.UUID,
    country_code: CountryCode,
    previous: tuple[float, float, int] | None,
    lat: float,
    lng: float,
    heading: float | None,
) -> None:
    """**عيّنةٌ واحدةٌ بلا هويّة** — من الموقع السابق (`previous` = خطّ عرض، خطّ طول، لحظتُه) والحاليّ. لا شيءَ إن كان المفتاحُ مطفأً."""
    cc = CountryCode(country_code).value
    if previous is None or not await redis.exists(_ON.format(cc=cc)):
        return
    gap = int(time.time()) - previous[2]
    if not MIN_GAP_S <= gap <= MAX_GAP_S:
        return
    kph = metres(previous[0], previous[1], lat, lng) / gap * 3.6
    if kph > 160:  # قفزةُ GPS لا سرعة
        return
    w = window()
    salt_key = _SALT.format(w=w)
    await redis.set(salt_key, secrets.token_hex(16), nx=True, ex=WINDOW_S * 2)
    salt = await redis.get(salt_key)
    salt = salt.decode() if isinstance(salt, bytes) else str(salt)
    who = hashlib.sha256(f"{salt}:{driver_id}".encode()).hexdigest()[:12]
    item = json.dumps([round(lat, 6), round(lng, 6), None if heading is None else round(heading), round(kph, 1), who, w])
    pipe = redis.pipeline()
    pipe.rpush(_RAW.format(cc=cc), item)
    pipe.ltrim(_RAW.format(cc=cc), -RAW_CAP, -1)
    pipe.expire(_RAW.format(cc=cc), WINDOW_S)
    await pipe.execute()


async def _places(path: str, payload: dict | None = None) -> dict | None:
    base = settings.places_search_url.rstrip("/")
    if not base:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await (client.post(base + path, json=payload) if payload is not None else client.get(base + path))
        return response.json() if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


async def aggregate(redis: Redis, country_code: CountryCode, *, enabled: bool) -> dict:
    """**يُفرغ العيّنات ويجمعها** — كلَّ خمس دقائق من Celery. **والعيّناتُ تُمحى هنا أيّاً كانت النتيجة**؛ والمطفأُ يمحو كلَّ شيء."""
    cc = CountryCode(country_code).value
    pipe = redis.pipeline()
    pipe.lrange(_RAW.format(cc=cc), 0, -1)
    pipe.delete(_RAW.format(cc=cc))
    raw, _ = await pipe.execute()
    if not enabled:
        await redis.delete(_ON.format(cc=cc), _VIEW.format(cc=cc))
        return {"cc": cc, "enabled": False, "dropped": len(raw)}
    await redis.set(_ON.format(cc=cc), "1", ex=WINDOW_S)
    points = [json.loads(item) for item in raw]
    if not points:
        return {"cc": cc, "enabled": True, "samples": 0}
    matched = await _places("/match", {"points": [[p[0], p[1], p[2]] for p in points]})
    segs = (matched or {}).get("segs") or [None] * len(points)
    pipe = redis.pipeline()
    touched = 0
    for point, seg in zip(points, segs):
        if seg is None:
            continue
        w = point[5]
        acc = _ACC.format(cc=cc, w=w)
        pipe.hincrbyfloat(acc, f"{seg}:s", point[3])
        pipe.hincrby(acc, f"{seg}:n", 1)
        pipe.expire(acc, WINDOW_S * 2)
        who = _WHO.format(cc=cc, w=w, seg=seg)
        pipe.sadd(who, point[4])
        pipe.expire(who, WINDOW_S * 2)
        touched += 1
    await pipe.execute()
    await redis.delete(_VIEW.format(cc=cc))
    return {"cc": cc, "enabled": True, "samples": len(points), "matched": touched}


def level(kph: float, free: float) -> str:
    ratio = kph / max(free, 1.0)
    if ratio >= 0.65:
        return "free"
    if ratio >= 0.35:
        return "slow"
    return "heavy"


async def view(redis: Redis, country_code: CountryCode) -> dict:
    """**ما يُرسم** — مقاطعُ النافذتين الأخيرتين التي مرّ بها `K_MIN` كباتن مختلفون فأكثر، بلونٍ لا برقم. مخبّأٌ دقيقةً."""
    cc = CountryCode(country_code).value
    empty = {"type": "FeatureCollection", "features": []}
    if not await redis.exists(_ON.format(cc=cc)):
        return empty
    cached = await redis.get(_VIEW.format(cc=cc))
    if cached:
        return json.loads(cached)
    now = window()
    sums: dict[str, list[float]] = {}
    who: dict[str, set[str]] = {}
    for w in (now - 1, now):
        acc = await redis.hgetall(_ACC.format(cc=cc, w=w))
        for field, value in acc.items():
            field = field.decode() if isinstance(field, bytes) else field
            seg, kind = field.rsplit(":", 1)
            bucket = sums.setdefault(seg, [0.0, 0.0])
            bucket[0 if kind == "s" else 1] += float(value)
        for seg in list(sums):
            # **البصماتُ لا تُجمع بين النافذتين** — ملحان مختلفان، فكبتنٌ واحدٌ فيهما بصمتان؛ فالعددُ أكبرُ النافذتين لا مجموعُهما
            members = await redis.smembers(_WHO.format(cc=cc, w=w, seg=seg))
            if len(members) > len(who.get(seg, ())):
                who[seg] = {m.decode() if isinstance(m, bytes) else m for m in members}
    ready = [seg for seg, members in who.items() if len(members) >= K_MIN and sums[seg][1] > 0]
    features = []
    if ready:
        missing = [seg for seg in ready if not await redis.exists(_GEOM.format(seg=seg))]
        if missing:
            found = await _places("/segments", {"ids": [int(seg) for seg in missing]}) or {}
            for seg, geom in (found.get("segments") or {}).items():
                await redis.set(_GEOM.format(seg=seg), json.dumps(geom), ex=86_400)
        for seg in ready:
            geom = await redis.get(_GEOM.format(seg=seg))
            if not geom:
                continue
            geom = json.loads(geom)
            mean = sums[seg][0] / sums[seg][1]
            features.append({"type": "Feature", "properties": {"l": level(mean, geom["free"])},
                             "geometry": {"type": "LineString", "coordinates": geom["coords"]}})
    result = {"type": "FeatureCollection", "features": features}
    await redis.set(_VIEW.format(cc=cc), json.dumps(result), ex=60)
    return result
