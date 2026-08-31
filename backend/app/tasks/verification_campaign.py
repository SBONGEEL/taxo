"""المهمّةُ الدوريّةُ لحملة تأكيد الأرقام (قرارُ المالك 2026-08-31).

**التذكيرُ والإيقافُ والتجمّدُ لا يفعلها أحد** — تراها الساعةُ وحدها. وبغير
هذه المهمّة تبقى الحملةُ صفّاً في جدولٍ لا يتحرّك.

**والإيداعُ قبل الإرسال** — قاعدةُ المشروع: «الإشعاراتُ تُنشر بعد `commit`».
فحالٌ تُعلن ثم تتراجع معاملتُها **تصل صاحبَها ولا تقع**، ومن أرسل داخل
المعاملة أرسل «حسابك موقوف» لمن لم يُوقَف.

**والمنطقُ في الخدمة وهذه غلافٌ رقيق** — فالاختباراتُ تستدعي الخدمةَ مباشرةً
ولا تحتاج عاملاً يعمل، كبقيّة مهامّ هذا المجلَّد.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import notifications, verification_campaign
from app.services.push.base import PushMessage
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> dict[str, int]:
    async with SessionLocal() as session:
        counters, outbox = await verification_campaign.tick(session)
        await session.commit()

        redis = get_redis_client()
        for item in outbox:
            # **كلُّ إشعارٍ على حدة**: واحدٌ يتعثّر لا يمنع من بعده — وهي
            # قاعدةُ `tasks/stops.py` نفسُها
            try:
                await notifications._safe_notify(
                    session,
                    redis,
                    user_id=item.user_id,
                    message=PushMessage(
                        title=item.title, body=item.body, data=item.data
                    ),
                )
            except Exception:  # pragma: no cover - يعتمد على عطلٍ خارجي
                logger.exception("تعذّر إشعارُ %s في حملة التأكيد", item.user_id)

    if any(counters.values()):
        logger.info("حملةُ التأكيد: %s", counters)
    return counters


@celery_app.task(name="tasks.verification_campaign.sweep")
def sweep() -> dict[str, int]:
    return run_async(_sweep())
