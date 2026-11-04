"""مهامُّ قناة فيسبوك (SPEC §٩٤/٢): الجدولةُ بعد الموافقة، والمزامنةُ الدوريّة.

**والمزامنةُ لا تُنبّه كلَّ دورة**: عقدٌ غيرُ مُدخَلٍ يُسجَّل تحذيراً ويُترك — القناةُ تقول ذلك في رأسها حين تُفتح.
"""

from __future__ import annotations

import logging
import uuid

from app.core.db import SessionLocal
from app.services.facebook import graph, posts as fb_posts
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _push(post_id: str) -> str:
    async with SessionLocal() as session:
        result = await fb_posts.push(session, uuid.UUID(post_id))
        await session.commit()
        return result


@celery_app.task(name="app.tasks.facebook.push_post")
def push_post(post_id: str) -> str:
    return run_async(_push(post_id))


async def _sync() -> str:
    async with SessionLocal() as session:
        try:
            counts = await fb_posts.sync(session)
        except graph.FacebookNotConfigured:
            return "not_configured"
        except graph.FacebookError as exc:
            logger.warning("مزامنةُ فيسبوك سقطت: %s", exc)
            return "error"
        await session.commit()
        return f"imported={counts['imported']} updated={counts['updated']}"


@celery_app.task(name="app.tasks.facebook.sync_facebook")
def sync_facebook() -> str:
    return run_async(_sync())
