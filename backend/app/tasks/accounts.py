"""المهمّةُ الدورية لحذف الحسابات — **كلَّ ساعة** (SPEC §59-د).

والمنطقُ كلُّه في `services/account_deletion.py`، وهذه غلافٌ رقيق: معاملةٌ لكلِّ
حساب، **وحسابٌ عليه مالٌ أو مانعٌ يُؤجَّل ولا يُجهَّل**، والمشرفُ يُنبَّه مرّةً
عند تغيّر السبب. **و`beat` واحدٌ كما هو** — والصفُّ يُؤخذ بـ`SKIP LOCKED`
فعاملان لا يعالجانه مرّتين إن وقع ذلك.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import account_deletion
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _run() -> dict[str, int]:
    return await account_deletion.anonymize_due(SessionLocal, get_redis_client())


@celery_app.task(name="app.tasks.accounts.anonymize_due")
def anonymize_due() -> dict[str, int]:
    counts = run_async(_run())
    if counts["anonymized"] or counts["deferred"]:
        logger.info("accounts: %s", counts)
    return counts
