"""اشتراك Redis pub/sub لكل اتصال WebSocket.

لا سجل اتصالات في ذاكرة العملية: كل مقبس يفتح اشتراكه الخاص، فبثٌّ صادر من
أي عامل uvicorn يصل صاحبه أينما كان جالساً.
"""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis
from redis.asyncio.client import PubSub


class Subscription:
    """اشتراك حيّ بقنوات تتبدل أثناء الاتصال.

    قنوات الراكب مثلاً تتغير عند إسناد كبتن له: يُضاف بثّ موقعه ثم يُزال عند
    انتهاء الرحلة.
    """

    def __init__(self, redis: Redis) -> None:
        self._pubsub: PubSub = redis.pubsub()
        self._channels: set[str] = set()

    async def __aenter__(self) -> "Subscription":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def subscribe(self, channel: str) -> None:
        if channel in self._channels:
            return
        await self._pubsub.subscribe(channel)
        self._channels.add(channel)

    async def unsubscribe(self, channel: str) -> None:
        if channel not in self._channels:
            return
        await self._pubsub.unsubscribe(channel)
        self._channels.discard(channel)

    async def poll(self, timeout: float) -> dict[str, Any] | None:
        """رسالة واحدة إن وصلت خلال المهلة، وإلا None.

        المهلة قصيرة قصداً: الحلقة نفسها تتولى المهام الدورية بين الرسائل.
        """
        message = await self._pubsub.get_message(
            ignore_subscribe_messages=True, timeout=timeout
        )
        if message is None or message.get("type") != "message":
            return None
        try:
            return json.loads(message["data"])
        except (TypeError, ValueError):  # pragma: no cover - حمولة تالفة
            return None

    async def close(self) -> None:
        await self._pubsub.aclose()
