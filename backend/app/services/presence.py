"""أيُّ أجهزةِ مستخدمٍ مفتوحةٌ الآن على WebSocket (SPEC القسم 10 — المرحلة 8).

القاعدة التي يخدمها هذا الملف: **لا Push لجهازٍ سوكته نشط.** الحدث وصله عبر
المقبس قبل أن يخرج الإشعار أصلاً، فإرسالُه إليه إشعارٌ مكرَّر على شاشةٍ
مفتوحة — وهو أسوأ أنواع الإزعاج لأنه يقول للمستخدم إن التطبيق لا يعرف أنه
يستعمله.

**والمفتوحُ ليس الظاهرَ** (SPEC §٦١-ل/٣، ٢٠٢٦-١٠-٠٥): المقبسُ يبقى حيّاً
والتطبيقُ في الخلفية — خدمةُ الكبتن الأمامية تُبقيه عمداً، ومقبسُ الراكب
يعيش دقائقَ بعد أن يغادر شاشتَه — **فكان الإشعارُ يُحجب عن هاتفٍ في الجيب
لأن مقبسَه لم يُغلق بعد**: لا شيءَ في الشريط، ولا صوت. فالتطبيقُ يبلّغ مقبسَه
حين يغيب عن صاحبه وحين يعود، **والحجبُ لما أمامَ صاحبه وحدَه**
(`foreground_devices`). **وما لم يبلّغ يُحسب أمامَه** — وهو حكمُ اليوم حرفاً،
فحزمةٌ أو شيفرةٌ أقدمُ لا تتغيّر عليها قاعدة.

**التخزين hash لا مفاتيح متفرقة.** إرسالُ إشعارٍ يحتاج جواب «أيُّ أجهزته
مفتوحة» في نداءٍ واحد؛ ومسحُ Redis بـ SCAN لكل إشعار لا يُحتمل. فالحقل لكل
جهاز، وقيمتُه لحظةُ انتهائه — إذ لا عمر لعضوٍ داخل hash في Redis، فالتنقيةُ
كسولةٌ عند القراءة كما في `geo.nearby`. وعمرٌ على الـ hash نفسه يمنع بقاء
أثرٍ لمستخدمٍ انقطع كلُّ أجهزته. **وعلامةُ الخلفية hash ثانٍ بالعمر نفسِه**،
يُجدَّد مع أثر المقبس في الضربة نفسِها — فلا تعيش إحداهما بعد الأخرى.

**المقبس بلا `device_id` لا يمنع Push**: من أراد ألا يصله إشعارٌ مكرَّر
يعرّف نفسه، والتطبيق يعرف مُعرِّف جهازه لأنه هو من سجّله لدى FCM.
"""

from __future__ import annotations

import time
import uuid

from redis.asyncio import Redis

_KEY = "ws:sockets:{user_id}"
# **الأجهزةُ المفتوحةُ الغائبةُ عن أصحابها** — مجموعةٌ جزئيةٌ من `_KEY` بقيمها نفسِها
_BACKGROUND_KEY = "ws:background:{user_id}"

# عمر أثر المقبس. أطول من دورة الإنعاش بضعفٍ فلا يُحسب المتصلُ منقطعاً على
# تأخّرٍ عابر، وأقصر من أن يبقى أثر مقبسٍ مات فيُحرم صاحبُه من الإشعارات
TTL_SECONDS = 90
REFRESH_SECONDS = 30


def _now() -> float:
    return time.time()


async def heartbeat(
    redis: Redis, user_id: uuid.UUID, device_id: str, *, background: bool = False
) -> None:
    """يرفع أثر الجهاز أو يجدّده — يُستدعى عند الاتصال ثم دورياً، **وعند تبدّل ظهوره**.

    **وحالُه معه في الضربة نفسِها**: في الخلفية تُجدَّد علامتُه بعمر الأثر،
    وأمامَ صاحبه تُرفع — فلا تبقى علامةٌ لجهازٍ عاد إلى شاشته.
    """
    key = _KEY.format(user_id=user_id)
    expires_at = str(_now() + TTL_SECONDS)
    await redis.hset(key, device_id, expires_at)
    await redis.expire(key, TTL_SECONDS * 2)

    background_key = _BACKGROUND_KEY.format(user_id=user_id)
    if background:
        await redis.hset(background_key, device_id, expires_at)
        await redis.expire(background_key, TTL_SECONDS * 2)
    else:
        await redis.hdel(background_key, device_id)


async def leave(redis: Redis, user_id: uuid.UUID, device_id: str) -> None:
    """يُسقط أثر الجهاز عند إغلاق المقبس — فيعود Push إليه فوراً."""
    await redis.hdel(_KEY.format(user_id=user_id), device_id)
    await redis.hdel(_BACKGROUND_KEY.format(user_id=user_id), device_id)


async def _live(redis: Redis, key: str) -> set[str]:
    """حقولُ hash لم ينقضِ عمرُها، مع تنقيةٍ كسولة لما انقضى."""
    raw = await redis.hgetall(key)
    if not raw:
        return set()

    now = _now()
    active: set[str] = set()
    stale: list[str] = []

    for field, value in raw.items():
        device_id = field.decode() if isinstance(field, bytes) else str(field)
        text = value.decode() if isinstance(value, bytes) else str(value)
        try:
            expires_at = float(text)
        except ValueError:  # pragma: no cover - قيمة تالفة
            stale.append(device_id)
            continue
        if expires_at > now:
            active.add(device_id)
        else:
            stale.append(device_id)

    if stale:
        await redis.hdel(key, *stale)
    return active


async def active_devices(redis: Redis, user_id: uuid.UUID) -> set[str]:
    """أجهزةُ المستخدم المفتوحة الآن — **ظاهرةً أو في الخلفية**."""
    return await _live(redis, _KEY.format(user_id=user_id))


async def foreground_devices(redis: Redis, user_id: uuid.UUID) -> set[str]:
    """المفتوحةُ **وأمامَ صاحبها** — كلُّ مفتوحٍ لم يبلّغ أنه في الخلفية."""
    opened = await active_devices(redis, user_id)
    if not opened:
        return set()
    return opened - await _live(redis, _BACKGROUND_KEY.format(user_id=user_id))
