"""مهمّتا صيانةٍ من المرحلة 12: تقليمُ الصندوق وكنسُ الطلبات المعلّقة.

**وهما مهمّتان في ملفٍ واحدٍ لأنهما نوعٌ واحد من العمل**: لا أحدَ ينتظرهما على
شاشة، ولا واحدةٌ منهما تُبلِّغ أحداً بشيء — تنظيفٌ يقيس نفسه ويسجّل ما فعل.
وكلتاهما غلافٌ رقيقٌ على خدمته، فالاختباراتُ تستدعي الخدمةَ ولا تحتاج عاملاً.

**والفرقُ بينهما في الخطر لا في الشكل**: التقليمُ يحذف أثراً مضى (الحقيقةُ في
الرحلات والدفعات وقيود الدفتر، والصندوقُ أثرُها)، والكنسُ **يمسّ مالاً** —
فيسأل المزودَ ولا يخمّن، وقواعدُه في `services/order_maintenance.py`.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.services import inbox, order_maintenance
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _trim() -> int:
    async with SessionLocal() as session:
        removed = await inbox.trim(session)
        await session.commit()
        return removed


@celery_app.task(name="app.tasks.maintenance.trim_notifications")
def trim_notifications() -> int:
    """يحذف من صندوق الوارد ما تجاوز مدةَ الحفظ — دفعةً مسقوفةً في الدورة."""
    removed = run_async(_trim())
    if removed:
        logger.info("user_notifications trimmed: %s", removed)
    return removed


async def _sweep() -> dict[str, int]:
    async with SessionLocal() as session:
        # `sweep` تُنهي معاملةَ كلِّ طلبٍ بنفسها — فلا commit هنا
        return await order_maintenance.sweep(session)


@celery_app.task(name="app.tasks.maintenance.sweep_provider_orders")
def sweep_provider_orders() -> dict[str, int]:
    """يسأل المزودَ عن كل طلبٍ معلّقٍ طال، ويُسقط ما لم يصله أصلاً."""
    tally = run_async(_sweep())
    if any(count for key, count in tally.items() if key != "open"):
        logger.info("provider orders swept: %s", tally)
    return tally
