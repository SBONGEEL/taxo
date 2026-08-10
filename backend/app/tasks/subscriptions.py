"""المهمة الدورية لاشتراكات الكباتن (SPEC القسم 8).

«Celery task دورية: تعليم الاشتراكات المنتهية + إخراج الكبتن من التوزيع» —
ومعها تنبيه الأربع والعشرين ساعة. المنطق كله في `services/subscriptions.py`
وهذه غلافٌ رقيق: الاختبارات تستدعي الخدمة مباشرةً فلا تحتاج عاملاً يعمل.

**البثّ بعد الـ commit** كما في كل مسار: قبله قد نُعلن انتهاءً يرتدّ.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import subscriptions
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> dict[str, int]:
    async with SessionLocal() as session:
        result = await subscriptions.sweep(session)
        await session.commit()
        # البثّ بعد الـ commit وداخل الجلسة: Push يقرأ أجهزة الكبتن من القاعدة
        await subscriptions.publish_sweep(session, get_redis_client(), result)
    return {"expired": len(result.expired), "expiring": len(result.expiring)}


@celery_app.task(name="app.tasks.subscriptions.sweep_subscriptions")
def sweep_subscriptions() -> dict[str, Any]:
    """يعلّم المنتهي، ويُخرج صاحبه من التوزيع، وينبّه من يقترب انتهاؤه."""
    summary = run_async(_sweep())
    logger.info(
        "كنس الاشتراكات: %s منتهٍ، %s على وشك الانتهاء",
        summary["expired"],
        summary["expiring"],
    )
    return summary
