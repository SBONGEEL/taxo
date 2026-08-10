"""مزود إشعارات وهمي — ما يُبنى عليه نظام الإشعارات ويُختبر (القسم 15/أ).

يكتب ما «أُرسل» في قائمة Redis لكل رمز، فيقرأه الاختبار والمطوّر كما يقرأ
جهازٌ حقيقي إشعاره. الحالة في Redis لا في الذاكرة لأن عاملي uvicorn لا
يتقاسمان ذاكرة، وبعمرٍ محدود لأن إشعاراً منسيّاً ليس بياناً يُحتفظ به.

الرمز `INVALID_TOKEN` يُردّ دائماً «غير مسجَّل»، فيُختبر تنظيفُ الرموز الميتة
على مسارٍ حقيقي بدل أن يبقى فرعاً لا يمر به اختبار.

**ممنوع في الإنتاج** (`__init__.get_push_provider`).
"""

from __future__ import annotations

import json

from redis.asyncio import Redis

from app.services.push.base import PushMessage, PushResult

SENT_KEY = "push:mock:{token}"
_TTL_SECONDS = 600
_MAX_KEPT = 20

# رمزٌ يحاكي جهازاً حُذف عنه التطبيق
INVALID_TOKEN = "INVALID_TOKEN"


class MockPushProvider:
    provider_name = "mock"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def send(self, tokens: list[str], message: PushMessage) -> PushResult:
        delivered = 0
        invalid: list[str] = []

        for token in tokens:
            if token == INVALID_TOKEN:
                invalid.append(token)
                continue
            key = SENT_KEY.format(token=token)
            await self._redis.rpush(
                key,
                json.dumps(
                    {
                        "title": message.title,
                        "body": message.body,
                        "data": message.data,
                        "high_priority": message.high_priority,
                    },
                    ensure_ascii=False,
                ),
            )
            await self._redis.ltrim(key, -_MAX_KEPT, -1)
            await self._redis.expire(key, _TTL_SECONDS)
            delivered += 1

        return PushResult(
            delivered=delivered,
            failed=len(invalid),
            invalid_tokens=tuple(invalid),
        )

    async def test_connection(self) -> str:
        return "المزود الوهمي جاهز — لا شبكة خارجية"


async def sent_messages(redis: Redis, token: str) -> list[dict]:
    """ما «وصل» جهازاً بعينه — للاختبارات وللتجربة اليدوية."""
    raw = await redis.lrange(SENT_KEY.format(token=token), 0, -1)
    return [json.loads(item) for item in raw]
