"""مهمّةُ مراقبة الوصول — كلَّ دقيقة من `beat` (`services/uptime.py`)."""

from __future__ import annotations

from app.core.redis_client import get_redis_client
from app.tasks.celery_app import celery_app, run_async


async def _probe() -> dict[str, str]:
    from app.services import uptime

    if not uptime.enabled():
        return {}
    return await uptime.probe(get_redis_client())


@celery_app.task(name="app.tasks.uptime.probe_public_urls", soft_time_limit=45, time_limit=55)
def probe_public_urls() -> dict[str, str]:
    """**أقصرُ من الدقيقة دائماً**: رابطان بعشر ثوانٍ لكلٍّ، فلا تتراكم فحوصٌ على عاملٍ بطيء."""
    return run_async(_probe())
