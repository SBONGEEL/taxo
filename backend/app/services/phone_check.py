"""«ألهذا الرقم حسابٌ؟» — يُسأل **قبل** رمز التسجيل لا بعده (قرارُ المالك ٢٠٢٦-١١-٠٢، SPEC §٢٣.٢-أ).

**العطبُ الذي وُجد لأجله**: «كبتن جديد؟» برقمٍ له حسابُ راكبٍ كان يرسل رمزَ واتساب، ثمّ يرفض التسجيلَ بعده
`phone_has_other_role` — رمزٌ لم يحتجه أحد. **والمالكُ اختار أن يُسأل الخادمُ قبل الرمز**، وعرف الثمن:
جوابٌ كهذا يقول لكلِّ من كتب رقماً أله حسابٌ أم لا.

**فالحدُّ هنا هو ما يجعل الثمنَ صغيراً، ويُعدّ الأرقامَ المختلفة لا الطلبات**: من أعاد الرقمَ نفسَه (رجع وصحّح اسمَه،
ضغط «التالي» ثانيةً) لا يُحاسَب، **ومن جرّب أرقاماً كثيرةً يُحاسَب على كلِّ رقمٍ جديد** — والمسحُ لا يكون إلا بأرقامٍ كثيرة.

**وسقوطُ الحدِّ لا يحجب أحداً عن التسجيل**: التطبيقُ يمضي حينها إلى الرمز كما كان قبل هذا الباب — فالحدُّ يمنع
**المعرفة** لا التسجيل، والمحجوبُ بشبكةٍ مشتركةٍ (CGNAT) يسجّل برمزٍ كما كان يسجّل.

**ولا رقمَ في السجلّ ولا في Redis**: يُحفظ ملخَّصُه (`sha256`) لأن السؤالَ «أهو رقمٌ جديدٌ لهذا المصدر؟» لا «أيُّ رقم».
"""

from __future__ import annotations

import hashlib
import logging

from redis.asyncio import Redis

from app.core.exceptions import RateLimited

logger = logging.getLogger(__name__)

#: **(النطاق، السقف، النافذة بالثواني)** — أرقامٌ مختلفةٌ لكلِّ مصدر.
#: الجهازُ أضيقُ لأنه إنسانٌ واحدٌ يكتب رقمَه (ورقمَ أخيه حين يخطئ)؛ والـIP أوسعُ لأن شبكةً واحدةً تحمل كثيرين.
#: **ومعرّفُ الجهاز يولّده التطبيقُ فيُبدَّل** — فسقفُ الـIP هو الحدُّ الحقيقيّ، وسقفُ الجهاز يمسك الهاتفَ الواحد.
DEVICE_LIMITS = ((4, 3600), (10, 86_400))
IP_LIMITS = ((10, 3600), (40, 86_400))


def _digest(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()[:20]


async def _admit(redis: Redis, key: str, member: str, cap: int, window: int) -> int | None:
    """يضمّ الرقمَ إلى مجموعة المصدر — **أو يعيد ما بقي من النافذة إن امتلأت برقمٍ جديد**."""
    full = f"phone-check:{key}"
    if await redis.sismember(full, member):
        return None
    if await redis.scard(full) >= cap:
        ttl = await redis.ttl(full)
        return int(ttl) if ttl and ttl > 0 else window
    pipe = redis.pipeline()
    pipe.sadd(full, member)
    pipe.ttl(full)
    _, ttl = await pipe.execute()
    if ttl is None or ttl < 0:
        await redis.expire(full, window)
    return None


async def guard(redis: Redis, *, ip: str, device: str | None, phone: str) -> None:
    """يمرّر الفحصَ أو يرفعه `RateLimited` — **ويُسجَّل الرفضُ إساءةً** بمصدره لا برقمه."""
    member = _digest(phone)
    scopes: list[tuple[str, str, tuple[tuple[int, int], ...]]] = [("ip", ip, IP_LIMITS)]
    if device:
        scopes.append(("device", device, DEVICE_LIMITS))
    for scope, source, limits in scopes:
        for cap, window in limits:
            retry = await _admit(redis, f"{scope}:{window}:{source}", member, cap, window)
            if retry is not None:
                logger.warning(
                    "phone_check_limited scope=%s window=%s cap=%s ip=%s device=%s",
                    scope,
                    window,
                    cap,
                    ip,
                    (device or "-")[:8],
                )
                raise RateLimited(retry_after=retry)
