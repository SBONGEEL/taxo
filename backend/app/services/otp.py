"""رموز التحقق برسالة قصيرة (SPEC القسم 15/أ — المرحلة 8).

«المصادقة عبر OTP برسائل SMS — قبل إضافة مزود SMS: دخول بهاتف + كلمة مرور؛
بعد تفعيله: يتحول الدخول لـ OTP آلياً.» هذا الملف هو الرمز نفسه: توليدُه
وحفظُه والتحقق منه. ومن يرسله يقرره `services/sms` لا هذا الملف.

ثلاث قواعد يحملها الكود:

- **لا يُحفظ الرمز، بل بصمته.** HMAC بمفتاح الخدمة، فنسخةٌ من Redis وقعت في
  يدٍ لا تُعطي رمزاً يُدخَل به. والمقارنة بزمنٍ ثابت.
- **عدّاد محاولات مع الرمز نفسه، لا مع النافذة الزمنية وحدها.** ستة أرقام
  مليونُ احتمال، وخمس دقائق تكفي لتخمينها آلياً لولا أن العدّاد يحرق الرمز
  بعد خمس محاولات — وحدُّ المعدل على المسار حارسٌ ثانٍ لا بديل.
- **مهلة إعادة إرسال.** كل رسالة تكلف مالاً، وزرُّ «أعد الإرسال» بلا مهلة
  بابُ إغراقٍ لجيب المنصة ولهاتف صاحب الرقم معاً.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import InvalidOtpCode, RateLimited
from app.services.sms import get_sms_provider

CODE_LENGTH = 6
CODE_TTL_SECONDS = 300
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60

_CODE_KEY = "otp:code:{phone}"
_ATTEMPTS_KEY = "otp:attempts:{phone}"
# عام لا خاص: الاختبار يقدّم الساعة دقيقةً بمحوه بدل أن ينتظرها
COOLDOWN_KEY = "otp:cooldown:{phone}"

# نصٌّ لاتيني الأرقام عمداً: يعبر بوابات الرسائل بلا لبس ترميز، ويُقرأ في كل
# لوحة مفاتيح
MESSAGE_TEMPLATE = "TAXO: رمز التحقق {code}. صالح {minutes} دقائق. لا تشاركه مع أحد."


@dataclass(frozen=True, slots=True)
class Challenge:
    """ما تحتاجه الواجهة لرسم شاشة الرمز — بلا الرمز نفسه بالطبع.

    و`channel` (المرحلة 12-هـ) ليس تفصيلاً تشخيصياً: الشاشةُ تقول «أرسلنا
    الرمز في واتساب» أو «برسالة نصية»، ومن ينتظر رسالةً نصيةً وقد وصله واتساب
    يفتح تطبيقاً خطأً ثم يطلب إعادة الإرسال — وكلُّ إعادةٍ رسالةٌ مدفوعة.
    """

    sent: bool
    expires_in: int | None = None
    resend_after: int | None = None
    channel: str | None = None


def _digest(code: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode("utf-8"), code.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def generate_code() -> str:
    """رمزٌ من مولّدٍ آمنٍ تشفيرياً — لا `random`."""
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


class OtpSender(Protocol):
    """من يوصل الرمز — **ويعرف كيف يُصاغ في قناته** (المرحلة 12-هـ).

    قبل واتساب كان هذا الملف يصوغ النصَّ ويسلّمه لمزود الرسائل. ولا يصحّ ذلك
    مع قوالب المصادقة في واتساب: القالبُ معتمدٌ عند ميتا ولا يقبل نصّاً حرّاً،
    وما يُرسل مُعامِلٌ واحد هو الرمز. فصار العقدُ «أوصِل هذا الرمز» لا «أرسل
    هذا النص» — والصياغةُ عند من يملكها.
    """

    provider_name: str

    async def send_code(self, to: str, code: str, *, ttl_minutes: int) -> str: ...


class SmsCodeSender:
    """يكيّف مزودَ الرسائل على عقد `OtpSender` — وهو من يصوغ نصَّ الرسالة.

    والنصُّ يبقى في هذا الملف لأنه نصُّ **الرمز** لا نصُّ المزود: تغييرُ صياغته
    قرارٌ واحد لكل مزودي الرسائل، لا قرارٌ في ملف أسلاكِ كلٍّ منهم.
    """

    def __init__(self, provider) -> None:
        self._provider = provider
        self.provider_name = getattr(provider, "provider_name", "sms")

    async def send_code(self, to: str, code: str, *, ttl_minutes: int) -> str:
        return await self._provider.send(
            to, MESSAGE_TEMPLATE.format(code=code, minutes=ttl_minutes)
        )


async def issue(
    session: AsyncSession,
    redis: Redis,
    phone: str,
    *,
    sender: OtpSender | None = None,
) -> Challenge:
    """يولّد رمزاً ويوصله عبر القناة المعطاة — أو عبر مزود الرسائل افتراضاً.

    الترتيب مقصود: يُحفظ الرمز **قبل** الإرسال ويُمحى إن فشل الإرسال — فلا
    يبقى رمزٌ حيٌّ لم يصل صاحبَه، ولا يصل رمزٌ لا أثر له عندنا.

    و`sender` غائباً يعني مزودَ الرسائل: القناةُ تُقرَّر في
    `services/verification.py` وحدها، وافتراضُ الرسائل هنا يبقي كل مستدعٍ قديم
    على حاله بدل أن يصير القرارُ في موضعين.
    """
    cooldown = await redis.ttl(COOLDOWN_KEY.format(phone=phone))
    if cooldown and cooldown > 0:
        raise RateLimited(
            f"انتظر {cooldown} ثانية قبل طلب رمز جديد", retry_after=cooldown
        )

    channel = sender or SmsCodeSender(await get_sms_provider(session))
    code = generate_code()

    await redis.set(
        _CODE_KEY.format(phone=phone), _digest(code), ex=CODE_TTL_SECONDS
    )
    await redis.delete(_ATTEMPTS_KEY.format(phone=phone))

    try:
        await channel.send_code(
            phone, code, ttl_minutes=CODE_TTL_SECONDS // 60
        )
    except Exception:
        await redis.delete(_CODE_KEY.format(phone=phone))
        raise

    await redis.set(
        COOLDOWN_KEY.format(phone=phone), "1", ex=RESEND_COOLDOWN_SECONDS
    )
    return Challenge(
        sent=True,
        expires_in=CODE_TTL_SECONDS,
        resend_after=RESEND_COOLDOWN_SECONDS,
    )


async def verify(redis: Redis, phone: str, code: str) -> None:
    """يتحقق من الرمز ويستهلكه — يرفع `InvalidOtpCode` وإلا لا يعيد شيئاً.

    الرمز يُمحى عند النجاح: رمزٌ يُقبل مرتين رمزٌ يُعاد استعماله بعد أن رآه من
    لا يملك الهاتف.
    """
    stored = await redis.get(_CODE_KEY.format(phone=phone))
    if stored is None:
        raise InvalidOtpCode()

    attempts = await redis.incr(_ATTEMPTS_KEY.format(phone=phone))
    if attempts == 1:
        await redis.expire(_ATTEMPTS_KEY.format(phone=phone), CODE_TTL_SECONDS)
    if attempts > MAX_ATTEMPTS:
        # يُحرق الرمز لا المحاولة وحدها: بغير ذلك يبقى الرمز حياً لمن يعيد الطلب
        await redis.delete(_CODE_KEY.format(phone=phone))
        raise RateLimited("محاولات كثيرة — اطلب رمزاً جديداً")

    expected = stored.decode() if isinstance(stored, bytes) else str(stored)
    if not hmac.compare_digest(expected, _digest(code.strip())):
        raise InvalidOtpCode()

    await redis.delete(
        _CODE_KEY.format(phone=phone), _ATTEMPTS_KEY.format(phone=phone)
    )
