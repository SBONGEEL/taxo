"""مُرسِلُ بريدٍ وهميّ — **ما يُبنى عليه التدفّقُ ويُختبر بلا رسالةٍ واحدة**.

**وهو الطريقُ الوحيدُ العاملُ اليومَ بقرار المالك**: لا عقدَ Resend ولا رسالةَ
حقيقيّةٌ حتى إذنُه. **فكلُّ ما فوقه مبنيٌّ ومقيسٌ الآن**، ويومَ يُدخَل العقدُ
الحقيقيُّ لا يتغيّر سطرٌ إلا في `__init__`.

**وآخرُ رسالةٍ تُحفظ في Redis** بعمرٍ قصير — كـ`sms/mock.py` حرفاً: عاملا
uvicorn لا يتقاسمان ذاكرة، **والاختبارُ يقرأ الرمزَ من حيث كُتب**. ومفتاحٌ
عابرٌ لا جدول: رسالةٌ منسيّةٌ ليست بياناً يُحتفظ به.

**وممنوعٌ في الإنتاج** (`__init__.get_email_provider`): مُرسِلٌ يقول «أُرسلت»
بلا إرسالٍ يعني **رمزاً يقرؤه من يبلغ Redis لا من يملك الصندوق** — وذاك
تحقّقٌ بلا هوية.
"""

from __future__ import annotations

from redis.asyncio import Redis

#: آخرُ رسالةٍ لكلِّ عنوان — يقرؤها الاختبارُ والمطوّر، وعمرُها كعمر الرمز وزيادة
LAST_MESSAGE_KEY = "email:mock:{address}"
_TTL_SECONDS = 600


class MockEmailProvider:
    provider_name = "mock"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def send(self, to: str, *, subject: str, body: str) -> str:
        # **الموضوعُ يُحفظ مع النصّ**: اختبارٌ يقرأ النصَّ وحدَه لا يرى موضوعاً
        # فارغاً أو مكرَّراً — وهو حقلٌ يراه المستخدمُ أوّلاً
        await self._redis.set(
            LAST_MESSAGE_KEY.format(address=to.lower()),
            f"{subject}\n\n{body}",
            ex=_TTL_SECONDS,
        )
        return f"mock-email-{to.lower()}"

    async def test_connection(self, test_email: str | None = None) -> str:
        if test_email:
            await self.send(
                test_email, subject="TAXO: اختبار اتصال", body="اختبارُ اتصال."
            )
            return "المُرسِلُ الوهميّ: أُرسلت رسالةُ اختبار"
        return "المُرسِلُ الوهميّ جاهز — لا شبكةَ خارجية"


async def last_message(redis: Redis, address: str) -> str | None:
    """آخرُ ما «أُرسل» إلى عنوان — للاختبارات وللتجربة اليدوية في التطوير."""
    raw = await redis.get(LAST_MESSAGE_KEY.format(address=address.lower()))
    if raw is None:
        return None
    return raw.decode() if isinstance(raw, bytes) else str(raw)
