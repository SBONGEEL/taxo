"""مزود واتساب وهمي — ما يُبنى عليه التدفق ويُختبر (SPEC القسم 15/أ).

نفس قواعد `sms/mock.py` حرفاً بحرف، ومفتاحُه منفصل: القناتان قد تعملان في
سوقين مختلفين في اللحظة نفسها، ومفتاحٌ واحد يجعل اختبارَ إحداهما يقرأ رسالةَ
الأخرى فيمرّ وهو يقيس شيئاً آخر.

**وممنوع في الإنتاج** (`__init__.build_provider`): مزودٌ يقول «أُرسل» بلا إرسال
يعني رمزاً يقرأه من يبلغ Redis لا من يملك الهاتف.
"""

from __future__ import annotations

from redis.asyncio import Redis

LAST_MESSAGE_KEY = "whatsapp:mock:{phone}"
_TTL_SECONDS = 600


class MockWhatsAppProvider:
    provider_name = "mock"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def send_code(self, to: str, code: str, *, ttl_minutes: int) -> str:
        await self._redis.set(
            LAST_MESSAGE_KEY.format(phone=to),
            f"TAXO WhatsApp: {code} ({ttl_minutes}m)",
            ex=_TTL_SECONDS,
        )
        return f"mock-whatsapp-{to}"

    async def test_connection(self, test_phone: str | None = None) -> str:
        if test_phone:
            await self.send_code(test_phone, "000000", ttl_minutes=5)
            return "المزود الوهمي: أُرسلت رسالة اختبار"
        return "المزود الوهمي جاهز — لا شبكة خارجية ولا قالب يُتحقق منه"


async def last_message(redis: Redis, phone: str) -> str | None:
    """آخر ما «أُرسل» إلى رقم — للاختبارات وللتجربة اليدوية في التطوير."""
    raw = await redis.get(LAST_MESSAGE_KEY.format(phone=phone))
    if raw is None:
        return None
    return raw.decode() if isinstance(raw, bytes) else str(raw)
