"""المهمّةُ اليوميّةُ لصلاحية المستندات (البند ج) — غلافٌ رقيقٌ على الخدمة.

**دورةٌ لا فحصٌ في التوزيع** — كسلفة الكبتن: `eligible_driver_ids` تُنادى لكلِّ
طلبٍ ولخريطة كلِّ راكب، وقراءةُ تواريخَ وجمعُ مستنداتٍ هناك تضع استعلاماً
ثقيلاً في المسار الحرج. **والتعليقُ يكتب `drivers.status`، والتوزيعُ يقرؤه
بشرطٍ واحدٍ ساكنٍ كما يقرؤه اليوم.**

**ومرّةً في اليوم لا كلَّ دقيقة**: العتبةُ يومٌ لا لحظة، ودورةٌ كلَّ دقيقةٍ
تسأل القاعدةَ ١٤٤٠ مرّةً عن سؤالٍ جوابُه يتغيّر مرّةً.

**واليومُ يومُ البلد لا يومُ الخادم** — والمنطقةُ من `notification_settings`.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import document_expiry, notifications
from app.models.enums import CountryCode
from app.services.stats import country_today
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)

# **مفتاحٌ لكلِّ (مستند، عتبة)** لا لكلِّ مستند: بلا العتبة يبتلع تنبيهُ
# الثلاثين تنبيهَ السبعة. **والتنبيهُ حدثٌ لا سجلّ**، فمفتاحُ Redis لا عمود.
NOTICE_TTL = 60 * 60 * 24 * 40


async def _sweep() -> tuple[int, int]:
    redis = get_redis_client()
    notified = 0
    suspended = 0
    async with SessionLocal() as session:
      # **دورةٌ لكلِّ سوقٍ بيومِه** — لا يومٌ واحدٌ لل    # **دورةٌ لكلِّ سوقٍ بيومِه** — لا يومٌ واحدٌ للاثنين
        for country in CountryCode:
            today = await country_today(session, country)

            for item in await document_expiry.expiring_on(
                session, today=today, country=country
            ):
                key = f"docexp:notice:{item.document_id}:{item.days_left}"
                if not await redis.set(key, "1", ex=NOTICE_TTL, nx=True):
                    continue
                await notifications.publish_document_expiring(
                    session,
                    redis,
                    driver_user_id=item.driver_user_id,
                    document_id=item.document_id,
                    doc_type=item.doc_type,
                    expires_on=item.expires_on,
                    days_left=item.days_left,
                )
                await session.commit()
                notified += 1

            for item in await document_expiry.expired_requiring_suspension(
                session, today=today, country=country
            ):
                driver = await document_expiry.suspend_for_expiry(session, item=item)
                if driver is None:
                    await session.rollback()
                    continue
                await session.commit()
                suspended += 1
                # **بعد الـcommit** كما تفرض قاعدة البثّ: حالةٌ تُعلن ثم تُلغى
                # أسوأُ من حالةٍ تتأخّر لحظة.
                await notifications.publish_document_expired(
                    session,
                    redis,
                    driver_user_id=item.driver_user_id,
                    document_id=item.document_id,
                    doc_type=item.doc_type,
                    expires_on=item.expires_on,
                )
                await session.commit()
    return notified, suspended


@celery_app.task(name="app.tasks.document_expiry.sweep_document_expiry")
def sweep_document_expiry() -> dict[str, int]:
    notified, suspended = run_async(_sweep())
    if notified or suspended:
        logger.info(
            "صلاحيةُ المستندات: %s تنبيهاً و%s تعليقاً", notified, suspended
        )
    return {"notified": notified, "suspended": suspended}
