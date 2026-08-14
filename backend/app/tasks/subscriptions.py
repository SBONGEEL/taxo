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
    redis = get_redis_client()

    # **التجديدُ قبل الكنس** (البند ١٤): من جُدِّد له لا يُخطر بانتهاءٍ لم يقع،
    # ولا يُعلَّم اشتراكُه منتهياً وقد صار له غطاءٌ جديد. والترتيبُ هو القاعدة
    # كلُّها: كنسٌ يسبق التجديدَ يُخرج كبتناً من التوزيع لثوانٍ ثم يعيده
    renewed = await subscriptions.renew_due(redis)

    async with SessionLocal() as session:
        result = await subscriptions.sweep(session)
        await session.commit()
        # البثّ بعد الـ commit وداخل الجلسة: Push يقرأ أجهزة الكبتن من القاعدة
        await subscriptions.publish_sweep(session, redis, result)
    return {
        "expired": len(result.expired),
        "expiring": len(result.expiring),
        "renewed": renewed,
    }


@celery_app.task(name="app.tasks.subscriptions.sweep_subscriptions")
def sweep_subscriptions() -> dict[str, Any]:
    """يعلّم المنتهي، ويُخرج صاحبه من التوزيع، وينبّه من يقترب انتهاؤه."""
    summary = run_async(_sweep())
    logger.info(
        "كنس الاشتراكات: %s منتهٍ، %s على وشك الانتهاء، %s جُدِّد تلقائياً",
        summary["expired"],
        summary["expiring"],
        summary["renewed"],
    )
    return summary
