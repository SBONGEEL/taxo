"""مزود رسائل وهمي — ما يُبنى عليه تدفق OTP ويُختبر (SPEC القسم 15/أ).

«تُبنى كاملة الآن ضد واجهة مزود موحدة مع مزود وهمي mock للاختبار، وتتفعل
تلقائياً بمجرد إدخال بيانات العقد الحقيقي.» فهذا المزود يجعل تحوّلَ الدخول إلى
OTP قابلاً للتجربة كاملاً بلا عقدٍ ولا رسالةٍ مدفوعة.

**آخر رسالة تُحفظ في Redis** بعمرٍ قصير: عاملا uvicorn لا يتقاسمان ذاكرة،
والاختبار (أو المطوّر) يقرأ الرمز من حيث كُتب. ومفتاحٌ عابر لا جدول: رسالةٌ
منسيّة ليست بياناً يُحتفظ به.

**ممنوع في الإنتاج** (`__init__.get_sms_provider`): مزودٌ يقول «أُرسلت» بلا
إرسال يعني رمزاً يقرأه من يبلغ Redis لا من يملك الهاتف.
"""

from __future__ import annotations

from redis.asyncio import Redis

# آخر رسالة لكل رقم — يقرأها الاختبار والمطوّر، وعمرها كعمر رمز OTP وزيادة
LAST_MESSAGE_KEY = "sms:mock:{phone}"
_TTL_SECONDS = 600


class MockSmsProvider:
    provider_name = "mock"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def send(self, to: str, body: str) -> str:
        await self._redis.set(
            LAST_MESSAGE_KEY.format(phone=to), body, ex=_TTL_SECONDS
        )
        return f"mock-sms-{to}"

    async def test_connection(self, test_phone: str | None = None) -> str:
        if test_phone:
            await self.send(test_phone, "TAXO: اختبار اتصال")
            return "المزود الوهمي: أُرسلت رسالة اختبار"
        return "المزود الوهمي جاهز — لا شبكة خارجية"


async def last_message(redis: Redis, phone: str) -> str | None:
    """آخر ما «أُرسل» إلى رقم — للاختبارات وللتجربة اليدوية في التطوير."""
    raw = await redis.get(LAST_MESSAGE_KEY.format(phone=phone))
    if raw is None:
        return None
    return raw.decode() if isinstance(raw, bytes) else str(raw)
