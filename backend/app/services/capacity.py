"""إنذارُ السعة (SPEC §٧٦/٢، أمرُ المالك ٢٠٢٦-١٠-١٤) — **المتّصلون الآن، وعتبتا الإنذار، وإشعارٌ للمشرفين حين تُبلغ إحداهما**.

**العتبتان ٧٠٪ من السعة الآمنة المقيسة** (٣٥٠ كبتناً و٧٠٠ راكب، `STRESS-REPORT-PROD-2.md`): ٢٥٠ و٥٠٠ — **في صفِّ `broadcast_settings`**
يحرّرهما المشرفُ حين يكبر الخادم، لا في الشيفرة.

* **الكباتنُ** — مفاتيحُ حضورٍ حيّة في كلِّ الدول (`broadcast.count_online`)، **وكباتنُ التجربة معهم**: الحملُ حملٌ أيّاً كان صاحبُه.
* **الركّابُ** — من فتح التطبيقَ الآن: **مقبسُ الراكب مفتوح** (`ws/routes.rider_socket`) يكتب نفسَه في مجموعةٍ مرتّبةٍ بآخر ظهور ويُنعشها
  كلَّ ٣٠ ثانية، **ويُعدّ من ظهر في التسعين الأخيرة** — فمقبسٌ مات بلا إغلاقٍ يسقط من العدّ وحدَه.
* **والإنذارُ مرّةً كلَّ نصف ساعة** ما دام العددُ فوق العتبة — إنذارٌ يتكرّر كلَّ دقيقةٍ يُتجاهل في الأولى. **والتنبيهُ في اللوحة حيٌّ**:
  يُحسب من العدد الآن، لا من آخر إشعار.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

RIDERS_KEY = "online:riders"
RIDER_REFRESH_SECONDS = 30
RIDER_STALE_SECONDS = 90
ALERT_COOLDOWN_KEY = "capacity:alert:cooldown"
ALERT_COOLDOWN_SECONDS = 1800
LAST_ALERT_KEY = "capacity:alert:last"


async def mark_rider(redis: Redis, user_id: uuid.UUID) -> None:
    await redis.zadd(RIDERS_KEY, {str(user_id): time.time()})


async def drop_rider(redis: Redis, user_id: uuid.UUID) -> None:
    await redis.zrem(RIDERS_KEY, str(user_id))


async def riders_online(redis: Redis) -> int:
    await redis.zremrangebyscore(RIDERS_KEY, "-inf", time.time() - RIDER_STALE_SECONDS)
    return int(await redis.zcard(RIDERS_KEY))


async def captains_online(redis: Redis) -> int:
    from app.services import broadcast

    return await broadcast.count_online(redis)


@dataclass(slots=True)
class Snapshot:
    captains: int
    riders: int
    alert_captains: int
    alert_riders: int
    last_alert_at: datetime | None

    @property
    def captains_alerting(self) -> bool:
        return self.captains >= self.alert_captains

    @property
    def riders_alerting(self) -> bool:
        return self.riders >= self.alert_riders

    @property
    def alerting(self) -> bool:
        return self.captains_alerting or self.riders_alerting


async def snapshot(session: AsyncSession, redis: Redis) -> Snapshot:
    from app.services import broadcast

    row = await broadcast.get_settings(session)
    last = await redis.get(LAST_ALERT_KEY)
    last_at = None
    if last:
        try:
            last_at = datetime.fromisoformat(json.loads(last)["at"])
        except (ValueError, KeyError, TypeError):
            last_at = None
    return Snapshot(
        captains=await captains_online(redis),
        riders=await riders_online(redis),
        alert_captains=row.alert_captains,
        alert_riders=row.alert_riders,
        last_alert_at=last_at,
    )


async def check(session: AsyncSession, redis: Redis) -> Snapshot:
    """دورةُ العامل كلَّ دقيقة: يُحسب العددُ، **وإن بلغ عتبةً ولم يُنذَر في نصف الساعة الماضية** يُنذَر المشرفون."""
    snap = await snapshot(session, redis)
    if not snap.alerting:
        return snap
    if not await redis.set(ALERT_COOLDOWN_KEY, "1", nx=True, ex=ALERT_COOLDOWN_SECONDS):
        return snap
    from app.services import notifications

    now = datetime.now(UTC)
    await redis.set(
        LAST_ALERT_KEY,
        json.dumps({"at": now.isoformat(), "captains": snap.captains, "riders": snap.riders}),
        ex=86_400,
    )
    await notifications.publish_capacity_alert(
        session,
        redis,
        captains=snap.captains,
        riders=snap.riders,
        alert_captains=snap.alert_captains,
        alert_riders=snap.alert_riders,
    )
    snap.last_alert_at = now
    return snap
