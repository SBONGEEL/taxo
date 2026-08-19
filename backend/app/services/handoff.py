"""رمزُ تسليمٍ بين تطبيقَي المنصّة — **جلسةٌ تنتقل بلا كلمةِ مرورٍ ولا رمزِ تحقق**.

**والنمطُ ليس مخترَعاً هنا**: هو تحدّي العامل الثاني نفسُه (`services/totp.py`)
— قيمةٌ عشوائيةٌ مفتاحُها في Redis مربوطٌ بالمستخدم، قصيرةُ العمر، تُستهلَك مرةً
واحدة، **ولا تفتح أيَّ مسار**. وقد كُتبت هناك حجّتُه: «رمزٌ مكانه `sub` في توكنٍ
حقيقيٍّ ناقصِ صلاحية يصير جلسةً كاملةً بخطأٍ واحدٍ في حارسٍ واحد».

**ولا يُنقل رمزُ التجديد نفسُه** — وهو البديلُ الظاهر: تدويرُه أحاديُّ الاستعمال
(`rotate_refresh_token` يحذف المفتاحَ ويرفض الإعادة)، فحاملان يُبطل أحدُهما
الآخر ويخرج صاحبُهما عشوائياً. وهو فوق ذلك اعتمادٌ طويلُ العمر يسافر في رابطٍ أو
نيّةِ نظامٍ يلتقطها أيُّ تطبيقٍ يسجّل المخطط.

**والرمزُ مربوطٌ بالتطبيق الهدف**: رمزٌ يصلح لأيِّ تطبيق هو رمزُ جلسةٍ عامّ.
وربطُه يجعل المسروقَ — إن سُرق — لا يفتح إلا البابَ الذي كان مقصوداً أصلاً.

**ولا يمنح دوراً**: `app_scope.guard` يعمل عند المبادلة كما يعمل عند الدخول، فمن
لا يملك دورَ التطبيق الهدف يُرفض هنا كما يُرفض هناك. الرمزُ ينقل **جلسةً** لا
صلاحية.
"""

from __future__ import annotations

import secrets
import uuid

from redis.asyncio import Redis

from app.core.app_scope import ClientApp
from app.core.exceptions import InvalidToken

# **مئةٌ وعشرون ثانية — مشتقّةٌ من قياسٍ لا مختارة.** كانت ثلاثين على تقديرٍ
# بأن «فتحَ تطبيقٍ فعلٌ من ثوانٍ»، فسقطت على جهازٍ حقيقي: الإقلاعُ **البارد**
# حتى بلوغ مسار الاستقبال قِيس مرتين على S21 عند **٣٫٤ ثانية و١٥٫١ ثانية** —
# والنصفُ الأسوأُ يلتهم نصفَ النافذة قبل أن يبدأ نداءُ المبادلة. وقد وقع فعلاً:
# `invalid_token` على تسليمٍ سليمٍ تماماً.
#
# والمئةُ والعشرون نحوُ **ثمانية أضعاف** أسوأِ ما قِيس — نفسُ منطقِ كاشفِ ركود
# الرفع (§17). وما يحمل الأمانَ ليس قِصَرُ المهلة بل: **أحاديّةُ الاستعمال**،
# و**الارتباطُ بالتطبيق الهدف**، و**إعادةُ الفحص كاملاً عند المبادلة**.
TOKEN_TTL_SECONDS = 120

_KEY = "handoff:{token}"


def _key(token: str) -> str:
    return _KEY.format(token=token)


async def issue(redis: Redis, *, user_id: uuid.UUID, target: ClientApp) -> str:
    """يفتح تسليماً إلى تطبيقٍ بعينه ويعيد رمزَه.

    القيمةُ `user_id:target` — فالمبادلةُ تتحقق من الاثنين، ولا تُقبل في تطبيقٍ
    غيرِ الذي صدر له.
    """
    token = secrets.token_urlsafe(32)
    await redis.set(
        _key(token), f"{user_id}:{target.value}", ex=TOKEN_TTL_SECONDS
    )
    return token


async def consume(
    redis: Redis, *, token: str, target: ClientApp
) -> uuid.UUID:
    """يستهلك الرمزَ مرةً واحدةً ويعيد صاحبَه — أو يرفع `InvalidToken`.

    **والحذفُ قبل القراءة** (`GETDEL`): قراءةٌ ثم حذفٌ تترك نافذةً يُبادَل فيها
    الرمزُ مرتين من طلبين متزامنين، وهو بعينه ما يحرسه `rotate_refresh_token`.
    """
    raw = await redis.getdel(_key(token))
    if raw is None:
        raise InvalidToken("انتهت مهلة التبديل — أعد المحاولة من التطبيق الآخر")

    value = raw if isinstance(raw, str) else raw.decode()
    owner, _, wanted = value.partition(":")
    if wanted != target.value:
        # رمزٌ صدر لتطبيقٍ آخر — ولا يُقبل هنا ولو كان صاحبُه يملك الدورين
        raise InvalidToken("رمزُ التبديل لا يخصّ هذا التطبيق")

    try:
        return uuid.UUID(owner)
    except ValueError as exc:  # pragma: no cover - قيمةٌ تالفة
        raise InvalidToken() from exc
