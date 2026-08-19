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
from app.models.otp_template import OtpTemplatePurpose
from app.services import otp_templates
from app.core.exceptions import InvalidOtpCode, RateLimited
from app.models.enums import CountryCode
from app.services import otp_limits
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

    async def send_code(
        self,
        to: str,
        code: str,
        *,
        ttl_minutes: int,
        purpose: str = "registration",
        body: str = "",
    ) -> str: ...


class SmsCodeSender:
    """يكيّف مزودَ الرسائل على عقد `OtpSender` — وهو من يصوغ نصَّ الرسالة.

    والنصُّ يبقى في هذا الملف لأنه نصُّ **الرمز** لا نصُّ المزود: تغييرُ صياغته
    قرارٌ واحد لكل مزودي الرسائل، لا قرارٌ في ملف أسلاكِ كلٍّ منهم.
    """

    def __init__(self, provider) -> None:
        self._provider = provider
        self.provider_name = getattr(provider, "provider_name", "sms")

    async def send_code(
        self,
        to: str,
        code: str,
        *,
        ttl_minutes: int,
        purpose: str = "registration",
        body: str = "",
    ) -> str:
        # **قالبُ اللوحة لقناة واتساب وحدَها** (قرارُ المالك 2026-08-19): مسارُ
        # الرسائل القصيرة نصُّه هنا كما كان، ولم يُطلب تحريرُه — و`body` يصله
        # مصاغاً فيُهمَل عمداً بدل أن يُخلط نصّان في قناةٍ واحدة.
        return await self._provider.send(
            to, MESSAGE_TEMPLATE.format(code=code, minutes=ttl_minutes)
        )


async def issue(
    session: AsyncSession,
    redis: Redis,
    phone: str,
    *,
    country: CountryCode | None = None,
    sender: OtpSender | None = None,
    purpose: str = OtpTemplatePurpose.REGISTRATION,
) -> Challenge:
    """يولّد رمزاً ويوصله عبر القناة المعطاة — أو عبر مزود الرسائل افتراضاً.

    الترتيب مقصود: يُحفظ الرمز **قبل** الإرسال ويُمحى إن فشل الإرسال — فلا
    يبقى رمزٌ حيٌّ لم يصل صاحبَه، ولا يصل رمزٌ لا أثر له عندنا.

    و`sender` غائباً يعني مزودَ الرسائل: القناةُ تُقرَّر في
    `services/verification.py` وحدها، وافتراضُ الرسائل هنا يبقي كل مستدعٍ قديم
    على حاله بدل أن يصير القرارُ في موضعين.

    **وهذا البابُ هو موضعُ سقوف الطلب** (`services/otp_limits.py`، قرارُ المالك
    2026-08-16): كلُّ قناةٍ **نولّد فيها الرمزَ ونرسله نحن** تمرّ من هنا، فسقفٌ
    هنا سقفٌ على الحساب لا على قناة — ومن استنفد محاولاته لا يلتفّ عليها
    بتبديل القناة. و`country` يُمرَّر من `verification.py` التي تعرف دولةَ
    الرقم؛ وغيابُه يقرأ سياسةَ الدولة الافتراضية بدل أن يُسقط الحارس.

    **والعدُّ بعد نجاح الإرسال لا قبله**: من ارتدّت رسالتُه لانقطاع البوابة لم
    يستهلك محاولةً — والسقفُ عقوبةُ إلحاحٍ لا عقوبةُ عطبٍ عندنا.
    """
    market = country or settings.default_country_code
    await otp_limits.guard(session, redis, phone, market)

    channel = sender or SmsCodeSender(await get_sms_provider(session))
    code = generate_code()

    await redis.set(
        _CODE_KEY.format(phone=phone), _digest(code), ex=CODE_TTL_SECONDS
    )
    await redis.delete(_ATTEMPTS_KEY.format(phone=phone))

    ttl_minutes = CODE_TTL_SECONDS // 60
    # **الصياغةُ هنا لأن القالبَ في قاعدة البيانات ومن يملك الجلسةَ هو من يقرأ.**
    # والمزودُ لا جلسةَ له، فلو قرأ كلُّ مزودٍ قالبَه لصار للقالب قارئان.
    rendered = otp_templates.render(
        await otp_templates.body_for(session, purpose),
        code=code,
        minutes=ttl_minutes,
    )

    try:
        await channel.send_code(
            phone,
            code,
            ttl_minutes=ttl_minutes,
            purpose=purpose,
            body=rendered,
        )
    except Exception:
        await redis.delete(_CODE_KEY.format(phone=phone))
        raise

    resend_after = await otp_limits.record(session, redis, phone, market)
    # **والمفتاحُ القديم يبقى مكتوباً**: اختباراتٌ قائمةٌ تمحوه لتتخطّى المهلة،
    # وهو أيضاً ما يقرؤه أيُّ مسارٍ لم يُنقل بعد. والمهلةُ الحقيقيةُ في
    # `otp_limits` — وهذا صدىً لها بعمرها نفسِه لا مصدرٌ ثانٍ يخالفها
    await redis.set(COOLDOWN_KEY.format(phone=phone), "1", ex=resend_after)
    return Challenge(
        sent=True,
        expires_in=CODE_TTL_SECONDS,
        resend_after=resend_after,
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
