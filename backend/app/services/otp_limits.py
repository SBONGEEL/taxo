"""سقوفُ طلب رمز التحقق — **على الرقم، في الخلفية، لكل القنوات** (2026-08-16).

قرارُ المالك، وقواعدُه الأربع مطبَّقةٌ حرفاً:

* **في الخلفية على Redis** لا في البوابة ولا في الواجهة. البوابةُ تحمي **رقمَنا**
  من الحظر (سقفُها لكل مستقبِلٍ وسقفُها الكلي)، وهذه تحمي **المستخدمين
  والكلفة** — وسقفٌ في الواجهة زينةٌ يلتفّ عليها أيُّ نداءٍ مصنوعٍ بيد.
* **والعدُّ على الرقم المطلوب لا على IP**: عشراتُ المستخدمين خلف شبكةِ مقهىً
  واحدةٍ لا يخنق بعضُهم بعضاً، والمسيءُ يُلاحَق وحدَه — وهي قاعدةُ سقف بثّ
  الموقع نفسُها.
* **ولكل قنوات الرمز لا واتساب وحدها**: موضعُ الحارس `otp.issue`، وهو البابُ
  الذي تمرّ منه كلُّ قناةٍ **نولّد فيها الرمزَ ونرسله نحن** (واتساب والرسائل).
  ولذلك من استنفد محاولاته لا يلتفّ عليها بتبديل القناة.
  > **وFirebase خارجَه بحكم شكله لا بإغفال**: الرمزُ يُرسل من جهاز المستخدم
  > ولا يمرّ بنا أصلاً، فليس لنا فيه ما نعدّه. وسقفُه عند Google.
* **والمستخدمُ يُقال له متى**: كلُّ رفضٍ هنا يحمل `retry_after` بالثواني،
  والتطبيقان يرسمانه عدّاداً — لا زرّاً يعمل ولا يفعل شيئاً.

**وثلاثةُ سقوفٍ لا واحد**، وترتيبُ فحصها هو الأهمّ فيها: **الأشدُّ أولاً**.
فمن تجاوز سقفَ التسجيل يُقال له ذلك، لا «انتظر ثلاثين ثانية» ثم يعاود فيُرفض
بسببٍ آخر — رسالةٌ تصف أقربَ الحواجز لا أبعدَها تجعله يحاول إلى ما لا نهاية.

**والاستنفادُ يُسجَّل في مجموعةِ اليوم** ليراه المشرف: تكرارٌ مشبوهٌ يُرى قبل
أن يحرق الرقم، لا بعده.
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RateLimited
from app.models.enums import CountryCode
from app.models.otp_setting import (
    DEFAULT_LOCKOUT_MINUTES,
    DEFAULT_MAX_PER_DAY,
    DEFAULT_MAX_PER_REGISTRATION,
    DEFAULT_MAX_PER_WINDOW,
    DEFAULT_RESEND_BASE_SECONDS,
    DEFAULT_RESEND_MAX_SECONDS,
    DEFAULT_WINDOW_MINUTES,
    OtpSetting,
)

# مفاتيحُ العدّ — كلُّها بالرقم، ولا مفتاحَ فيها بـIP
WINDOW_KEY = "otp:req:window:{phone}"
DAY_KEY = "otp:req:day:{phone}"
REGISTRATION_KEY = "otp:req:signup:{phone}"
RESEND_KEY = "otp:resend:{phone}"
RESEND_STEP_KEY = "otp:resend:step:{phone}"
LOCK_KEY = "otp:locked:{phone}"

# مجموعةُ من استنفد اليوم — يقرؤها المشرف. **مفتاحٌ لكل يوم** بعمرِ يومين:
# سؤالُ اللوحة «من استنفد اليوم» لا «من استنفد يوماً ما»
EXHAUSTED_KEY = "otp:exhausted:{day}"
EXHAUSTED_TTL_SECONDS = 172_800

DAY_SECONDS = 86_400

# عمرُ عدّاد التسجيل. **طويلٌ لا لا نهائي**: رقمٌ استُهلك سقفُه قبل شهرين ولم
# يُسجَّل به أحدٌ قد يكون بيد صاحبٍ جديد — والشرائحُ تُعاد بيعُها في السوقين
REGISTRATION_TTL_SECONDS = 30 * DAY_SECONDS


@dataclass(frozen=True, slots=True)
class Policy:
    """سقوفُ دولةٍ كما تُقرأ لحظةَ السؤال — ولا يُجمَّد منها شيء."""

    window_minutes: int
    max_per_window: int
    max_per_day: int
    max_per_registration: int
    lockout_minutes: int
    resend_base_seconds: int
    resend_max_seconds: int


async def policy_for(session: AsyncSession, country: CountryCode) -> Policy:
    """سياسةُ الدولة — **وصفٌّ غائبٌ يُقرأ بالافتراضات لا بالانفتاح**.

    غيابُ الصف حالُ تركيبٍ جديدٍ قبل البذر، وقراءتُه «لا سقف» تجعل أوّلَ سوقٍ
    يُفتح بلا حارسٍ راجعه أحد — وهذه سقوفٌ حارسة، فالسكوتُ فيها يحمي.
    """
    row = await session.get(OtpSetting, country)
    if row is None:
        return Policy(
            window_minutes=DEFAULT_WINDOW_MINUTES,
            max_per_window=DEFAULT_MAX_PER_WINDOW,
            max_per_day=DEFAULT_MAX_PER_DAY,
            max_per_registration=DEFAULT_MAX_PER_REGISTRATION,
            lockout_minutes=DEFAULT_LOCKOUT_MINUTES,
            resend_base_seconds=DEFAULT_RESEND_BASE_SECONDS,
            resend_max_seconds=DEFAULT_RESEND_MAX_SECONDS,
        )
    return Policy(
        window_minutes=row.window_minutes,
        max_per_window=row.max_per_window,
        max_per_day=row.max_per_day,
        max_per_registration=row.max_per_registration,
        lockout_minutes=row.lockout_minutes,
        resend_base_seconds=row.resend_base_seconds,
        resend_max_seconds=row.resend_max_seconds,
    )


def _refused(message: str, retry_after: int) -> RateLimited:
    """رفضٌ **يحمل متى** — بغيره يبقى الزرُّ يُضغط ولا شيءَ يقع."""
    return RateLimited(message, retry_after=max(1, retry_after))


async def _mark_exhausted(redis: Redis, phone: str) -> None:
    """يسجّل الرقمَ في مجموعة اليوم — للوحة لا للمنع.

    والمنعُ يقع من العدّادات نفسِها؛ هذه **رؤيةٌ** فقط: من يرى عشرين رقماً
    استنفدت اليوم يعرف أن شيئاً يجري قبل أن يُحظر رقمُه.
    """
    from datetime import UTC, datetime

    key = EXHAUSTED_KEY.format(day=datetime.now(UTC).date().isoformat())
    await redis.sadd(key, phone)
    await redis.expire(key, EXHAUSTED_TTL_SECONDS)


async def guard(
    session: AsyncSession, redis: Redis, phone: str, country: CountryCode
) -> None:
    """يرفع `RateLimited` إن بلغ الرقمُ سقفاً — أو يمرّ صامتاً.

    **ولا يعدّ شيئاً**: العدُّ في `record` بعد نجاح الإرسال. وسقفٌ يعدّ
    المحاولةَ الفاشلة يعاقب صاحبَ الرقم على عطبٍ عندنا — من ارتدّت رسالتُه
    لانقطاع البوابة لم يستهلك شيئاً.

    **والترتيبُ من الأشدِّ إلى الأخفّ** كي تصف الرسالةُ أبعدَ الحواجز لا أقربَها.
    """
    policy = await policy_for(session, country)

    locked = await redis.ttl(LOCK_KEY.format(phone=phone))
    if locked and locked > 0:
        raise _refused(
            f"استنفدتَ محاولات طلب الرمز — أعد المحاولة بعد {_minutes(locked)}",
            locked,
        )

    if policy.max_per_registration > 0:
        used = int(await redis.get(REGISTRATION_KEY.format(phone=phone)) or 0)
        if used >= policy.max_per_registration:
            await _mark_exhausted(redis, phone)
            raise _refused(
                "تجاوزتَ عدد مرات طلب رمز التسجيل لهذا الرقم — راجع الدعم",
                REGISTRATION_TTL_SECONDS,
            )

    if policy.max_per_day > 0:
        used = int(await redis.get(DAY_KEY.format(phone=phone)) or 0)
        if used >= policy.max_per_day:
            ttl = await redis.ttl(DAY_KEY.format(phone=phone))
            await _lock(redis, phone, policy)
            await _mark_exhausted(redis, phone)
            raise _refused(
                f"بلغتَ الحدَّ اليوميَّ لطلب الرمز — أعد المحاولة بعد "
                f"{_minutes(max(ttl, policy.lockout_minutes * 60))}",
                max(ttl, policy.lockout_minutes * 60),
            )

    if policy.max_per_window > 0:
        used = int(await redis.get(WINDOW_KEY.format(phone=phone)) or 0)
        if used >= policy.max_per_window:
            await _lock(redis, phone, policy)
            await _mark_exhausted(redis, phone)
            wait = policy.lockout_minutes * 60 or await redis.ttl(
                WINDOW_KEY.format(phone=phone)
            )
            raise _refused(
                f"طلبتَ الرمز مراتٍ كثيرةً — أعد المحاولة بعد {_minutes(wait)}",
                wait,
            )

    resend = await redis.ttl(RESEND_KEY.format(phone=phone))
    if resend and resend > 0:
        raise _refused(f"انتظر {resend} ثانية قبل طلب رمز جديد", resend)


async def _lock(redis: Redis, phone: str, policy: Policy) -> None:
    if policy.lockout_minutes > 0:
        await redis.set(
            LOCK_KEY.format(phone=phone), "1", ex=policy.lockout_minutes * 60
        )


def _minutes(seconds: int) -> str:
    """نصٌّ يقرؤه إنسان — «٤٥ دقيقة» لا «٢٧٠٠ ثانية»."""
    if seconds < 90:
        return f"{seconds} ثانية"
    if seconds < 5400:
        return f"{round(seconds / 60)} دقيقة"
    return f"{round(seconds / 3600)} ساعة"


async def record(
    session: AsyncSession, redis: Redis, phone: str, country: CountryCode
) -> int:
    """يعدّ محاولةً **نجحت** ويعيد مهلةَ الإعادة القادمة بالثواني.

    **والمهلةُ تتزايد بالتكرار**: الأساسُ ثم ضِعفُه ثم ضِعفاه، محدودةً بسقفٍ —
    فالضغطةُ المكرّرة تُعالَج بثلاثين ثانية، والآلةُ تُعالَج بعشر دقائق، ولا
    تبلغ ساعةً فتصير منعاً دائماً لم يقرّره أحد.
    """
    policy = await policy_for(session, country)

    window_seconds = max(60, policy.window_minutes * 60)
    await _bump(redis, WINDOW_KEY.format(phone=phone), window_seconds)
    await _bump(redis, DAY_KEY.format(phone=phone), DAY_SECONDS)
    await _bump(
        redis, REGISTRATION_KEY.format(phone=phone), REGISTRATION_TTL_SECONDS
    )

    step = await _bump(redis, RESEND_STEP_KEY.format(phone=phone), window_seconds)
    delay = min(
        policy.resend_max_seconds,
        policy.resend_base_seconds * 2 ** max(0, step - 1),
    )
    await redis.set(RESEND_KEY.format(phone=phone), "1", ex=delay)
    return delay


async def _bump(redis: Redis, key: str, ttl: int) -> int:
    """زيادةٌ بعمرٍ يُضبط عند أول ضربة — نفسُ شكل `core/rate_limit.hit`."""
    count = int(await redis.incr(key))
    if count == 1:
        await redis.expire(key, ttl)
    return count


async def clear_for_registration(redis: Redis, phone: str) -> None:
    """يُصفَّر عدّادُ التسجيل **بإنشاء الحساب** — لأن التسجيل وقع.

    وهذا هو ما يجعل السقفَ الثالث عادلاً: من سجّل فعلاً لم يعد «من يطلب رموزاً
    بلا أن يسجّل»، وحسابُه بعدها يخضع للنافذة واليوميّ كغيره. **ولا تُمحى
    النافذةُ ولا اليوميّ**: من أنشأ حساباً للتوّ لا يُمنح رصيداً جديداً من
    الرسائل في الدقيقة نفسِها.
    """
    await redis.delete(REGISTRATION_KEY.format(phone=phone))


async def exhausted_today(redis: Redis) -> list[str]:
    """أرقامُ اليوم التي بلغت سقفاً — تقرؤها اللوحة."""
    from datetime import UTC, datetime

    key = EXHAUSTED_KEY.format(day=datetime.now(UTC).date().isoformat())
    members = await redis.smembers(key)
    return sorted(
        member.decode() if isinstance(member, bytes) else str(member)
        for member in members
    )


async def reset(redis: Redis, phone: str) -> None:
    """يمسح كلَّ عدّادات رقمٍ — بابُ الإدارة حين يكون الحاجزُ خطأً.

    **ولا يُنادى من مسار مستخدم**: سقفٌ يرفعه صاحبُه ليس سقفاً.
    """
    await redis.delete(
        WINDOW_KEY.format(phone=phone),
        DAY_KEY.format(phone=phone),
        REGISTRATION_KEY.format(phone=phone),
        RESEND_KEY.format(phone=phone),
        RESEND_STEP_KEY.format(phone=phone),
        LOCK_KEY.format(phone=phone),
    )
