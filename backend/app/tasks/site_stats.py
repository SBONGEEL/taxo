"""استيرادُ أرقام Play اليوميّ («الإحصاءات»). **عقدٌ غيرُ مُدخَلٍ لا يُسجَّل سقوطاً** — الشاشةُ تقول «لم يُدخَل» من رأسها."""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.services import play_reports, site_stats
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _import() -> str:
    async with SessionLocal() as session:
        try:
            rows = await play_reports.run(session)
        except play_reports.PlayReportsNotConfigured:
            return "not_configured"
        except Exception as exc:  # noqa: BLE001 — يُسجَّل في `stats_imports` ويُرى في الشاشة
            await session.rollback()
            logger.warning("استيرادُ Play سقط: %s", exc)
            await site_stats.record_import(session, "play", 0, str(exc)[:500] or type(exc).__name__)
            await session.commit()
            return "error"
        await site_stats.record_import(session, "play", rows, None)
        await session.commit()
        return f"rows={rows}"


@celery_app.task(name="app.tasks.site_stats.import_play")
def import_play() -> str:
    return run_async(_import())
