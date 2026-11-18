"""**تجميعُ الازدحام المجهول** كلَّ خمس دقائق من `beat` (`services/traffic.py`) — ويمحو العيّناتِ في كلِّ تشغيلٍ أيّاً كانت النتيجة."""

from __future__ import annotations

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode, FeatureKey
from app.tasks.celery_app import celery_app, run_async

INTERVAL_SECONDS = 300.0


async def _aggregate() -> list[dict]:
    from app.services import settings_service, traffic

    redis = get_redis_client()
    out = []
    async with SessionLocal() as session:
        for country in CountryCode:
            enabled = await settings_service.is_feature_enabled(session, country, FeatureKey.MAP_LIVE_TRAFFIC)
            out.append(await traffic.aggregate(redis, country, enabled=enabled))
    return out


@celery_app.task(name="app.tasks.traffic.aggregate_traffic", soft_time_limit=90, time_limit=110)
def aggregate_traffic() -> list[dict]:
    return run_async(_aggregate())
