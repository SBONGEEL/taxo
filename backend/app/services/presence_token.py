"""رمزُ الحضور — **بابٌ واحدٌ لا غير، وليس رمزَ جلسة**.

**العلّةُ مقيسةٌ لا مقدَّرة** (S21، 2026-08-21): الخدمةُ الأمامية في تطبيق
الكبتن تبثّ موقعَه كلَّ ٢٠ ثانيةً ساعاتٍ، بينما **رمزُ الوصول عمرُه ٣٠
دقيقة**. فمن يجدّده والنظامُ يخنق مؤقتاتِ الـWebView؟

**ولا يُسلَّم رمزُ التجديد إلى الخدمة** (§23): تدويرُه **أحاديُّ الاستعمال**،
وهو ما يجعل سرقتَه تُكتشف — حاملان يُبطل أحدُهما الآخر. **فحاملٌ ثانٍ يشتري
الدوامَ بإخراج الكبتن من حسابه وسط وردية.**

**فهذا رمزٌ ثالثٌ بغرضٍ واحد**، وسابقتُه في المشروع قائمة: رمزُ التبديل بين
التطبيقين (§23) ورمزُ تحدّي العامل الثاني (12-د) — **كلاهما قيمةٌ عشوائيةٌ في
Redis لبابٍ بعينه، لا رمزٌ يحمل هوية**.

---

**وماذا يستطيع من سرقه؟ جملةً واحدة:**

> **يستطيع أن يكذب على الخريطة بموقع كبتنٍ واحد، ولا شيءَ غيرَ ذلك** — لا
> يقرأ حساباً، ولا يقبل رحلة، ولا يمسّ محفظةً ولا وثيقة، **ولا يفتح جلسة**.
> وأسوأُ ما يبلغه أن يُعرض على ذلك الكبتن طلبٌ وهو ليس حيث يقول، **فيُلغيه
> ويُحتسب عليه إلغاء**.

**وحدُّه مبنيٌّ لا موصوف**: `X-Presence-Token` **ترويسةٌ مستقلّة** لا
`Authorization`، فلا تمرّ بـ`get_current_user` أصلاً ولا يمكن أن تُقرأ جلسةً
بالخطأ؛ ولا تُقبل إلا في التبعية التي يستعملها **مسارٌ واحد**؛
و`test_presence_token.py` يرسلها إلى مساراتٍ أخرى ويشترط ردَّها.

**ويُلغى لحظةَ الفصل**: `drivers.go_offline` — وهي البابُ الذي تمرّ به كلُّ
طرق الخروج من الاستقبال (ضغطةُ الكبتن، وإغلاقُ المقبس، ومسحُ الاشتراك) —
**وعند تسجيل الخروج** في `auth.logout`. فما من طريقٍ يُنهي عملَ الكبتن ويترك
الرمزَ حيّاً.

**ورمزٌ واحدٌ لكلِّ كبتن**: إصدارُ ثانٍ يُبطل الأول. فجهازٌ أُخذ منه لا يبقى
يبثّ بعد أن يدخل صاحبُه من جهازٍ آخر — **وهي الخاصيّةُ التي تجعل «الإلغاء»
فعلاً لا وعداً**.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid

from redis.asyncio import Redis

#: **عمرُه ورديةٌ لا شهر**: طويلٌ كفايةً ألّا ينقطع كبتنٌ يعمل، وقصيرٌ كفايةً
#: أن يموت المسروقُ من نفسه إن لم يُلغَ. ويُجدَّد مع كلِّ بثٍّ صحيح، فلا
#: تنقطع ورديةٌ أطولُ منه ما دام صاحبُها يعمل.
TTL_SECONDS = 12 * 60 * 60

_TOKEN_KEY = "presence:token:{digest}"
_OWNER_KEY = "presence:owner:{user_id}"


def _digest(token: str) -> str:
    """**يُخزَّن مُلخَّصُه لا هو**: من قرأ Redis لا يخرج منه برمزٍ صالح."""
    return hashlib.sha256(token.encode()).hexdigest()


async def issue(redis: Redis, *, user_id: uuid.UUID) -> str:
    """رمزٌ جديدٌ لهذا الكبتن — **ويُبطل ما قبله**."""
    await revoke(redis, user_id=user_id)
    token = secrets.token_urlsafe(32)
    digest = _digest(token)
    await redis.set(_TOKEN_KEY.format(digest=digest), str(user_id), ex=TTL_SECONDS)
    await redis.set(_OWNER_KEY.format(user_id=user_id), digest, ex=TTL_SECONDS)
    return token


async def resolve(redis: Redis, token: str) -> uuid.UUID | None:
    """صاحبُ الرمز إن كان حيّاً — **ويُمدَّد عمرُه بالاستعمال**.

    فوردياتٌ أطولُ من اثنتي عشرة ساعةً لا تنقطع، **ورمزٌ لا يُستعمل يموت**.
    """
    if not token:
        return None
    key = _TOKEN_KEY.format(digest=_digest(token))
    raw = await redis.get(key)
    if raw is None:
        return None
    owner = raw.decode() if isinstance(raw, bytes) else str(raw)
    try:
        user_id = uuid.UUID(owner)
    except ValueError:  # pragma: no cover - قيمةٌ مشوَّهةٌ لا تُقرأ هويةً
        return None
    await redis.expire(key, TTL_SECONDS)
    await redis.expire(_OWNER_KEY.format(user_id=user_id), TTL_SECONDS)
    return user_id


async def revoke(redis: Redis, *, user_id: uuid.UUID) -> None:
    """**يُنادى من كلِّ طريقٍ يُنهي الاستقبال** — والغيابُ ليس خطأً."""
    owner_key = _OWNER_KEY.format(user_id=user_id)
    digest = await redis.get(owner_key)
    if digest is not None:
        text = digest.decode() if isinstance(digest, bytes) else str(digest)
        await redis.delete(_TOKEN_KEY.format(digest=text))
    await redis.delete(owner_key)
