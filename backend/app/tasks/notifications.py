"""المهمة الدورية لحملات الإشعارات (SPEC القسم 13 — المرحلة 8).

غلافٌ رقيق على `services/campaigns.py` كما هو `tasks/subscriptions.py`:
المنطق كله في الخدمة، والاختبارات تستدعيها مباشرةً فلا تحتاج عاملاً يعمل.

**حملةٌ لكل معاملة**: تُقفل، تُرسل دفعاتها، ثم يُثبَّت أثرها. سقوطُ حملةٍ
لا يمحو ما أُرسل قبلها، والتقدّمُ محفوظٌ في `notification_deliveries` لا في
ذاكرة المهمة — فالدورةُ التالية تكمل من حيث انتهت هذه.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.db import SessionLocal
from app.services import campaigns
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _dispatch_due() -> dict[str, int]:
    async with SessionLocal() as session:
        due = await campaigns.due_campaign_ids(session)

    sent = 0
    deferred = 0
    for campaign_id in due:
        async with SessionLocal() as session:
            campaign = await campaigns.get_campaign(
                session, campaign_id, for_update=True
            )
            # أُلغيت أو أُرسلت بين القراءة والقفل — لا شأن للمهمة بها
            if campaign.status is not campaigns.CampaignStatus.SCHEDULED:
                continue
            result = await campaigns.dispatch(session, campaign)
            await session.commit()

        sent += result.sent
        deferred += int(result.deferred)

    return {"campaigns": len(due), "sent": sent, "deferred": deferred}


@celery_app.task(name="app.tasks.notifications.dispatch_campaigns")
def dispatch_campaigns() -> dict[str, Any]:
    """يرسل ما حان موعده من الحملات، ويؤجّل ما كان في ساعات هدوء دولته."""
    summary = run_async(_dispatch_due())
    logger.info(
        "حملات الإشعارات: %s حملة، %s إشعاراً مُرسلاً، %s مؤجلة",
        summary["campaigns"],
        summary["sent"],
        summary["deferred"],
    )
    return summary
