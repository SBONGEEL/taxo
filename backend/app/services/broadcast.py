"""بثُّ موقع الكبتن المتكيّف (SPEC §٧٥-ج، أمرُ المالك ٢٠٢٦-١٠-١٣) — **السياسةُ التي يتبعها التطبيق، ومهلةُ الحضور المشتقّة منها**.

## ما يحمله التطبيق

`Policy` — فاصلُ كلِّ حال (متاحٌ · في الطريق · الرحلةُ ودفعتُها ونقاطُها) وعتبةُ السكون والنبضة. **يُرسل في إطار «connected» وكلّما
تغيّر** (قناةُ `drivers:broadcast` التي يشترك فيها كلُّ مقبس كبتن) — فالقيمُ الجديدةُ تصل حيّةً بلا تحديثٍ ولا إعادةِ تشغيل.

## الفاصلُ الفعّالُ للمتاحين

* **يدويّ**: ما كتبه المشرف (`available_seconds`).
* **آليّ**: من عدد المتّصلين **بجدولٍ في اللوحة**، كلَّ دورةٍ لـ`beat` (`TICK_SECONDS`). **وبلا تذبذب** — قراري (§٧٥-أ تركه لي):
  - **الصعودُ** (فاصلٌ أطول) **فوريّ** حين يعبر العددُ حدَّ درجته: الحملُ يُخفَّف حين يأتي لا بعد دقائق.
  - **والنزولُ بشرطين معاً**: أن يكون العددُ **دون حدِّ الدرجة الأدنى بهامش `DOWN_MARGIN`** (فعددٌ يتأرجح حول ١٠٠٠ لا ينزل ويصعد كلَّ
    دورة) **وأن تمضي `MIN_DWELL_SECONDS` على آخر تغيير**.
  **وحدّا المالك الصلبان** (١٥–٤٥) يُفرضان على كلِّ قيمةٍ تخرج من الجدول، ولو كتب المشرفُ غيرَهما فيه.
* **ويعيش في Redis** (`STATE_KEY`) لا في صفِّ الإعدادات — فالآليُّ لا يكتب إعداداً أبداً، **وكلُّ تغييرٍ سطرٌ في `broadcast_changes`**.

## مهلةُ الحضور — **متّسقةٌ مع الفاصل والنبضة دائماً**

`presence_ttl = النبضة + أطولُ فاصلٍ قائم + GRACE_SECONDS`: كبتنٌ ساكنٌ لا يرسل إلا نبضتَه، أو متاحٌ بفاصل ٤٥، **لا يسقط من التوزيع
أبداً**؛ ومن أغلق التطبيقَ يسقط فوراً بإغلاق مقبسه، **ومن انقطع صامتاً يسقط بعد المهلة** (دقيقتان تقريباً بالقيم الافتراضيّة).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broadcast import BroadcastChange, BroadcastSettings
from app.models.enums import CountryCode
from app.ws import events

logger = logging.getLogger(__name__)

#: حدّا المالك الصلبان لفاصل المتاحين — «لا أقلَّ من ١٥ ولا أكثرَ من ٤٥»
MIN_AVAILABLE_SECONDS = 15
MAX_AVAILABLE_SECONDS = 45
#: دورةُ الطور الآليّ (`beat`)
TICK_SECONDS = 30
#: النزولُ يشترط عدداً دون الحدِّ بهذه النسبة…
DOWN_MARGIN = 0.10
#: …وهذه المدّةَ على آخر تغيير
MIN_DWELL_SECONDS = 300
#: هامشُ الشبكة فوق النبضة وأطول فاصل — إطارٌ تأخّر على طريقٍ ضعيفٍ لا يُسقط كبتناً
GRACE_SECONDS = 30

STATE_KEY = "broadcast:state"
CHANNEL = "drivers:broadcast"
EVENT = "broadcast_policy"

#: ما تبذره الترحيلة — ويُستعمل حين لا صفَّ (اختبارٌ على قاعدةٍ فارغة) **بالقيم نفسِها**
DEFAULT_STEPS: list[dict] = [
    {"max_online": 1000, "seconds": 15},
    {"max_online": 2000, "seconds": 20},
    {"max_online": 3000, "seconds": 30},
    {"max_online": None, "seconds": 45},
]


@dataclass(frozen=True, slots=True)
class Policy:
    """ما يتبعه تطبيقُ الكبتن — بالثواني والأمتار."""

    mode: str
    available_seconds: int
    heading_seconds: int
    trip_send_seconds: int
    trip_record_seconds: int
    move_meters: int
    heartbeat_seconds: int

    @property
    def presence_ttl(self) -> int:
        longest = max(self.available_seconds, self.heading_seconds, self.trip_send_seconds)
        return self.heartbeat_seconds + longest + GRACE_SECONDS

    def frame(self) -> dict:
        return {"type": EVENT, **asdict(self), "presence_ttl": self.presence_ttl}


#: السياسةُ قبل أن يُكتب شيء — قيمُ الترحيلة نفسُها
DEFAULT_POLICY = Policy(
    mode="automatic",
    available_seconds=15,
    heading_seconds=10,
    trip_send_seconds=15,
    trip_record_seconds=2,
    move_meters=30,
    heartbeat_seconds=60,
)


# ------------------------------------------------------------------ الإعدادات


async def get_settings(session: AsyncSession) -> BroadcastSettings:
    """الصفُّ الواحد — **ويُنشأ بقيم الترحيلة إن غاب** (قاعدةُ اختبارٍ لم تُبذر)."""
    row = await session.scalar(select(BroadcastSettings))
    if row is None:
        row = BroadcastSettings(auto_steps=[dict(step) for step in DEFAULT_STEPS])
        session.add(row)
        await session.flush()
    return row


def clamp(seconds: int) -> int:
    return max(MIN_AVAILABLE_SECONDS, min(MAX_AVAILABLE_SECONDS, int(seconds)))


def band_of(online: int, steps: list[dict]) -> int:
    """رقمُ الدرجة التي يقع فيها هذا العدد — الأولى التي حدُّها ≥ العدد، والأخيرةُ بلا حدّ."""
    for index, step in enumerate(steps):
        limit = step.get("max_online")
        if limit is None or online <= int(limit):
            return index
    return len(steps) - 1


def next_band(current: int | None, online: int, steps: list[dict], *, dwell_ok: bool) -> int:
    """**الدرجةُ التالية بهامشٍ ومُكث** — الصعودُ فوريّ، والنزولُ بعددٍ دون الحدِّ بـ`DOWN_MARGIN` وبعد `MIN_DWELL_SECONDS`."""
    up = band_of(online, steps)
    if current is None or current >= len(steps):
        return up
    if up > current:
        return up
    # العددُ لو زاد بالهامش — فإن بقي دون الدرجة الحاليّة نزلنا إليها، وإلا بقينا
    down = band_of(int(online / (1 - DOWN_MARGIN)) + 1, steps)
    if down < current and dwell_ok:
        return down
    return current


# ------------------------------------------------------------------ الحال في Redis


async def _state(redis: Redis) -> dict:
    raw = await redis.get(STATE_KEY)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


_cache: tuple[float, Policy] | None = None
_CACHE_SECONDS = 5


async def current_policy(redis: Redis) -> Policy:
    """**السياسةُ القائمة** — من Redis بذاكرةٍ قصيرةٍ في العمليّة (كلُّ بثِّ موقعٍ يقرأ المهلة، فلا نداءَ لكلِّ إطار)."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _CACHE_SECONDS:
        return _cache[1]
    state = await _state(redis)
    policy = DEFAULT_POLICY
    if state.get("policy"):
        try:
            policy = Policy(**state["policy"])
        except TypeError:
            policy = DEFAULT_POLICY
    _cache = (now, policy)
    return policy


def forget_cache() -> None:
    """للاختبارات ولمن كتب السياسةَ في العمليّة نفسِها."""
    global _cache
    _cache = None


async def count_online(redis: Redis) -> int:
    """**المتّصلون الآن في كلِّ الدول** — مفاتيحُ حضورٍ حيّة (كما يعدّ `stats.online_driver_count`)، **وكباتنُ التجربة معهم**: الحملُ
    على الخادم حملٌ أيّاً كان صاحبُه."""
    from app.services import stats

    total = 0
    for country in CountryCode:
        total += await stats.online_driver_count(redis, country)
    return total


def _policy_of(row: BroadcastSettings, available: int) -> Policy:
    return Policy(
        mode=row.mode,
        available_seconds=clamp(available),
        heading_seconds=row.heading_seconds,
        trip_send_seconds=row.trip_send_seconds,
        trip_record_seconds=row.trip_record_seconds,
        move_meters=row.move_meters,
        heartbeat_seconds=row.heartbeat_seconds,
    )


async def apply(
    session: AsyncSession,
    redis: Redis,
    *,
    source: str = "automatic",
    actor_id: uuid.UUID | None = None,
    now: float | None = None,
) -> Policy:
    """**دورةٌ واحدة**: يقرأ الإعدادات والعدد، يقرّر الفاصل، ويكتب الحالَ وينشرها إن تغيّرت. **ولا يكتب في صفِّ الإعدادات.**

    يُستدعى من `beat` كلَّ `TICK_SECONDS`، ومن باب اللوحة بعد كلِّ حفظ (`source="admin"`) — فما يكتبه المشرفُ يصل الكباتنَ فوراً.
    """
    now = time.time() if now is None else now
    row = await get_settings(session)
    steps = list(row.auto_steps or DEFAULT_STEPS)
    state = await _state(redis)
    online = await count_online(redis)
    old_policy = state.get("policy") or {}
    old_seconds = old_policy.get("available_seconds")

    if row.mode == "manual":
        band = None
        seconds = clamp(row.available_seconds)
    else:
        current = state.get("band") if state.get("mode") == "automatic" else None
        dwell_ok = now - float(state.get("changed_at") or 0) >= MIN_DWELL_SECONDS
        band = next_band(current, online, steps, dwell_ok=dwell_ok)
        seconds = clamp(steps[band]["seconds"])

    policy = _policy_of(row, seconds)
    changed_policy = asdict(policy) != old_policy
    changed_seconds = old_seconds != policy.available_seconds
    new_state = {
        "mode": row.mode,
        "band": band,
        "policy": asdict(policy),
        "online": online,
        "checked_at": now,
        "changed_at": now if changed_seconds else float(state.get("changed_at") or now),
    }
    await redis.set(STATE_KEY, json.dumps(new_state))
    if changed_seconds:
        session.add(
            BroadcastChange(
                # **لحظةُ الدورة نفسُها** لا `now()` المعاملة — فترتيبُ السجلّ ترتيبُ الدورات ولو تقاربت
                created_at=datetime.fromtimestamp(now, UTC),
                source=source,
                online_count=online,
                old_seconds=old_seconds,
                new_seconds=policy.available_seconds,
                actor_id=actor_id,
            )
        )
        await session.flush()
        logger.info("فاصلُ المتاحين %s ← %s (المتّصلون %s، %s)", old_seconds, policy.available_seconds, online, source)
    if changed_policy:
        forget_cache()
        await events.publish(redis, CHANNEL, policy.frame())
    return policy


async def live(redis: Redis) -> dict:
    """ما تُريه اللوحة حيّاً: الطورُ والفاصلُ الحاليّ وعددُ المتّصلين ومتى قِيس."""
    state = await _state(redis)
    policy = await current_policy(redis)
    return {
        "mode": state.get("mode") or policy.mode,
        "available_seconds": policy.available_seconds,
        "presence_ttl": policy.presence_ttl,
        "online": state.get("online"),
        "checked_at": state.get("checked_at"),
        "changed_at": state.get("changed_at"),
    }


async def recent_changes(session: AsyncSession, limit: int = 20) -> list[BroadcastChange]:
    rows = await session.scalars(
        select(BroadcastChange).order_by(BroadcastChange.created_at.desc()).limit(limit)
    )
    return list(rows)
