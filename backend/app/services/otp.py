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
    """ما تحتاجه الواجهة لرسم شاشة الرمز — بلا الرمز نفسه بالطبع."""

    sent: bool
    expires_in: int | None = None
    resend_after: int | None = None


def _digest(code: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode("utf-8"), code.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def generate_code() -> str:
    """رمزٌ من مولّدٍ آمنٍ تشفيرياً — لا `random`."""
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


async def issue(session: AsyncSession, redis: Redis, phone: str) -> Challenge:
    """يولّد رمزاً ويرسله عبر المزود المفعّل.

    الترتيب مقصود: يُحفظ الرمز **قبل** الإرسال ويُمحى إن فشل الإرسال — فلا
    يبقى رمزٌ حيٌّ لم يصل صاحبَه، ولا يصل رمزٌ لا أثر له عندنا.
    """
    cooldown = await redis.ttl(COOLDOWN_KEY.format(phone=phone))
    if cooldown and cooldown > 0:
        raise RateLimited(
            f"انتظر {cooldown} ثانية قبل طلب رمز جديد", retry_after=cooldown
        )

    provider = await get_sms_provider(session)
    code = generate_code()

    await redis.set(
        _CODE_KEY.format(phone=phone), _digest(code), ex=CODE_TTL_SECONDS
    )
    await redis.delete(_ATTEMPTS_KEY.format(phone=phone))

    try:
        await provider.send(
            phone,
            MESSAGE_TEMPLATE.format(code=code, minutes=CODE_TTL_SECONDS // 60),
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
