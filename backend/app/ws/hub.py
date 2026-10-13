"""اشتراك Redis pub/sub لاتصالات WebSocket — **اتصالٌ واحدٌ بـRedis لكلِّ عمليّة، يوزّع على مقابسها** (SPEC §٧٥-د/٢).

لا سجل اتصالات في ذاكرة العملية يُعتمد عليه للتوجيه: البثُّ يمرّ دائماً عبر Redis، فبثٌّ صادرٌ من أيِّ عامل uvicorn يصل صاحبه أينما كان
جالساً — **والعمّالُ صاروا عدّة** (§٧٥-د/٢).

## لمَ صار اتصالاً واحداً (قِيس على الإنتاج ٢٠٢٦-١٠-١٣، المرحلة ١)

كان كلُّ مقبسٍ يفتح اشتراكَه الخاصّ — **اتصالَ Redis لكلِّ تطبيقٍ مفتوح**، فوق اتصال المقبس نفسِه. **فنفدت الملفّاتُ المفتوحة** (حدُّ العمليّة
١٠٢٤) عند نحو ٩٠٠ تطبيقٍ مفتوح: «Too many open files» ٨١٧ مرّة، ورُفض ١٩٦ راكباً، وضاع ٦١ طلباً. **فصار لكلِّ عمليّةٍ «محورٌ» واحد**:
اشتراكٌ واحدٌ بـRedis، **وعدّادٌ لكلِّ قناة** (يُرسل `SUBSCRIBE` عند أوّل مقبسٍ و`UNSUBSCRIBE` عند آخرهم)، **وقارئٌ واحدٌ يوزّع** كلَّ رسالةٍ على
طوابير المقابس المشتركة فيها. **والواجهةُ (`Subscription`) كما كانت حرفاً** — فلا يتغيّر من يستعملها.

## وما يحفظه

* **الترتيبُ داخل القناة**: قارئٌ واحدٌ وطوابيرُ FIFO.
* **«اشترك ثمّ اقرأ الحال»** (`_ringing_now` وأخواتها): `subscribe` لا يعود إلا وقد أُرسل `SUBSCRIBE` — كما كان.
* **السقوطُ والعودة**: إن انقطع اتصالُ Redis أعاد القارئُ فتحَه **واشترك في كلِّ قناةٍ عدّادُها فوق الصفر**.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

logger = logging.getLogger(__name__)

#: قناةٌ يبقى المحورُ مشتركاً فيها دائماً — فلاتصاله وجودٌ قبل أوّل مقبسٍ وبعد آخرهم (القراءةُ بلا اشتراكٍ خطأٌ في redis-py)
_KEEPALIVE = "hub:keepalive"
_READ_TIMEOUT_SECONDS = 1.0
_RETRY_SECONDS = 1.0


class _Hub:
    """**المحورُ الواحد** لعمليّةٍ وحلقتها: اشتراكٌ واحدٌ بـRedis، وطوابيرُ المقابس لكلِّ قناة."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._pubsub: PubSub | None = None
        self._queues: dict[str, set[asyncio.Queue[str]]] = {}
        self._lock = asyncio.Lock()
        self._reader: asyncio.Task | None = None

    async def _ensure(self) -> PubSub:
        if self._pubsub is None:
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(_KEEPALIVE)
        if self._reader is None or self._reader.done():
            self._reader = asyncio.create_task(self._read(), name="ws-hub-reader")
        return self._pubsub

    async def add(self, channel: str, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            pubsub = await self._ensure()
            members = self._queues.setdefault(channel, set())
            if not members:
                await pubsub.subscribe(channel)
            members.add(queue)

    async def remove(self, channel: str, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            members = self._queues.get(channel)
            if not members or queue not in members:
                return
            members.discard(queue)
            if not members:
                del self._queues[channel]
                if self._pubsub is not None:
                    with contextlib.suppress(Exception):  # اتصالٌ سقط: لا اشتراكَ يُلغى، وإعادةُ الفتح لا تعيده
                        await self._pubsub.unsubscribe(channel)

    async def _read(self) -> None:
        while True:
            try:
                pubsub = self._pubsub
                if pubsub is None:
                    return
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=_READ_TIMEOUT_SECONDS)
                if message is None or message.get("type") != "message":
                    continue
                for queue in tuple(self._queues.get(message["channel"], ())):
                    queue.put_nowait(message["data"])
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — اتصالٌ سقط: يُعاد فتحُه ويُعاد الاشتراكُ في كلِّ قناةٍ حيّة
                logger.warning("محورُ المقابس: انقطع اتصالُ Redis — يُعاد", exc_info=True)
                await asyncio.sleep(_RETRY_SECONDS)
                await self._reconnect()

    async def _reconnect(self) -> None:
        async with self._lock:
            old, self._pubsub = self._pubsub, None
            if old is not None:
                with contextlib.suppress(Exception):
                    await old.aclose()
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe(_KEEPALIVE, *self._queues.keys())
                self._pubsub = pubsub
            except Exception:  # noqa: BLE001 — Redis ما زال غائباً؛ الدورةُ التالية تحاول
                self._pubsub = self._redis.pubsub()
                with contextlib.suppress(Exception):
                    await self._pubsub.subscribe(_KEEPALIVE)

    async def close(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reader
            self._reader = None
        if self._pubsub is not None:
            with contextlib.suppress(Exception):
                await self._pubsub.aclose()
            self._pubsub = None
        self._queues.clear()


#: محورٌ لكلِّ (حلقة، عميل) — العمليّةُ الحيّةُ حلقةٌ واحدة، والاختباراتُ كذلك؛ والمفتاحُ يحمي من حلقةٍ ثانيةٍ لا تتوقّعها
_hubs: dict[tuple[int, int], _Hub] = {}


def _hub_for(redis: Redis) -> _Hub:
    key = (id(asyncio.get_running_loop()), id(redis))
    hub = _hubs.get(key)
    if hub is None:
        hub = _hubs[key] = _Hub(redis)
    return hub


async def shutdown() -> None:
    """إطفاءُ العمليّة: يُغلق كلُّ محورٍ في هذه الحلقة قبل إغلاق عميل Redis."""
    loop = id(asyncio.get_running_loop())
    for key in [k for k in _hubs if k[0] == loop]:
        await _hubs.pop(key).close()


class Subscription:
    """اشتراك حيّ بقنوات تتبدل أثناء الاتصال — **عبر محور العمليّة** لا اتصالٍ خاصّ.

    قنوات الراكب مثلاً تتغير عند إسناد كبتن له: يُضاف بثّ موقعه ثم يُزال عند
    انتهاء الرحلة.
    """

    def __init__(self, redis: Redis) -> None:
        self._hub = _hub_for(redis)
        self._channels: set[str] = set()
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def __aenter__(self) -> "Subscription":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def subscribe(self, channel: str) -> None:
        if channel in self._channels:
            return
        await self._hub.add(channel, self._queue)
        self._channels.add(channel)

    async def unsubscribe(self, channel: str) -> None:
        if channel not in self._channels:
            return
        self._channels.discard(channel)
        await self._hub.remove(channel, self._queue)

    async def poll(self, timeout: float) -> dict[str, Any] | None:
        """رسالة واحدة إن وصلت خلال المهلة، وإلا None.

        المهلة قصيرة قصداً: الحلقة نفسها تتولى المهام الدورية بين الرسائل.
        """
        try:
            raw = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            try:
                raw = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            except TimeoutError:
                return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):  # pragma: no cover - حمولة تالفة
            return None

    async def close(self) -> None:
        for channel in list(self._channels):
            await self.unsubscribe(channel)
