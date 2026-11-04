"""**مراقبةُ الوصول من الخارج** (أمرُ المالك ٢٠٢٦-١١-٠٥، بعد حادثة «ERR network_timeout» على شاشة الإقلاع).

كلَّ دقيقةٍ يُطلب الرابطان العامّان **من الإنترنت لا من داخل الشبكة**: الطلبُ يخرج من الخادم إلى حافّة Cloudflare ثمّ يعود عبر النفق
— **فيمرّ بما يمرّ به هاتفُ الراكب**: الاسمُ في DNS، والحافّة، والنفق، والحاوية. وفحصُ `docker` الداخليُّ لا يرى إلا الأخيرة.

**ويُشعَر المالكُ إن بقي الرابطُ ساقطاً دقيقتين فأكثر**، ومرّةً واحدةً للانقطاع الواحد (`SET NX` كوسيط الدفع في `gateway_health`)
— ثمّ مرّةً حين يعود ومعه مدّتُه. **ودقيقتان لا أقلّ**: رفعٌ يعيد الخلفيّةَ في ستِّ ثوانٍ، أو حزمةٌ ضاعت، لا يوقظان أحداً.

## وما لا تراه — مكتوبٌ لا مسكوتٌ عنه

**الفاحصُ على الخادم نفسِه**: إن سقط الخادمُ كلُّه، أو العاملُ، أو Redis، **سقط الفاحصُ معه ولا يُشعَر أحد**. فهذه طبقةٌ تمسك
النفقَ والحافّةَ والحاوياتِ واسمَ النطاق، **ولا تمسك موتَ الخادم** — وذلك يحتاج فاحصاً خارجه (`STATE.md`).
ولا تقيس شبكةَ هاتفٍ بعينه: حادثةُ ٤ نوفمبر كانت بين هاتفٍ والحافّة، والرابطان يجيبان من كلِّ مكانٍ آخر.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

#: الرابطان كما يطلبهما التطبيقان — `api` للخلفيّة و`app` لقشرة الراكب
TARGETS: dict[str, str] = {
    "api": "https://api.tajora.ly/health",
    "app": "https://app.tajora.ly/",
}
#: كم ثانيةً من السقوط المتّصل قبل الإشعار
ALERT_AFTER_SECONDS = 120
TIMEOUT_SECONDS = 10.0

_DOWN_SINCE = "uptime:down_since:{}"
_ALERTED = "uptime:alerted:{}"

Fetch = Callable[[str], Awaitable[bool]]


async def _fetch(url: str) -> bool:
    """**٢٠٠ في عشر ثوانٍ** — وما عداه سقوط: مهلة، أو ٥٠٢ من الحافّة، أو اسمٌ لا يُحلّ."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False,
                                     headers={"User-Agent": "taxo-uptime/1"}) as client:
            response = await client.get(url)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


async def probe(redis, *, fetch: Fetch | None = None, now: float | None = None) -> dict[str, str]:
    """فحصٌ واحدٌ للرابطين — **ويُعيد حالَ كلٍّ منهما** (`up` · `down` · `alerted`) ليُقرأ في سجلّ العامل."""
    from app.services import alert_capture

    fetch = fetch or _fetch
    now = time.time() if now is None else now
    result: dict[str, str] = {}
    for name, url in TARGETS.items():
        ok = await fetch(url)
        down_key, alerted_key = _DOWN_SINCE.format(name), _ALERTED.format(name)
        if ok:
            since = await redis.get(down_key)
            await redis.delete(down_key)
            # **العودةُ يُشعَر بها من أُشعر بالسقوط وحدَه** — وسقوطُ دقيقةٍ لم يُشعَر به لا عودةَ تُعلَن له
            if await redis.delete(alerted_key):
                minutes = max(1, round((now - float(since)) / 60)) if since else None
                alert_capture.ship_after_commit(None, "service_up", "signal", uuid.uuid4(), target=name, minutes=minutes)
            result[name] = "up"
            continue
        await redis.set(down_key, str(now), nx=True)
        since = float(await redis.get(down_key) or now)
        if now - since >= ALERT_AFTER_SECONDS and await redis.set(alerted_key, "1", nx=True):
            minutes = max(1, round((now - since) / 60))
            alert_capture.ship_after_commit(None, "service_down", "signal", uuid.uuid4(), target=name, minutes=minutes)
            logger.error("الرابط %s ساقطٌ منذ %s دقيقة — أُشعر المالك", name, minutes)
            result[name] = "alerted"
        else:
            logger.warning("الرابط %s لم يُجب (%s)", name, url)
            result[name] = "down"
    return result


def enabled() -> bool:
    """**على الإنتاج وحدَه**: بيئةُ التطوير لا تملك هذين الرابطين، وفحصُها لهما يُشعر المالكَ عن إنتاجٍ سليم."""
    return settings.is_production
