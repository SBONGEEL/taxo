"""المهمة الدورية لمكافآت الإحالة (SPEC القسم 9.1، المرحلة 12-ح).

**ولماذا مهمةٌ دورية لا فعلٌ عند إنهاء الرحلة؟** لسببين:

1. عدُّ رحلاتٍ ومقارنتُها بحدٍّ عملٌ لا يقرؤه أحدٌ في لحظة الإنهاء — والرحلةُ
   طريقٌ ساخن يمرّ منه كلُّ راكب.
2. **وأخطرُ**: فشلُ كتابةِ مكافأةٍ لا يجوز أن يُفشل إنهاءَ رحلة، ولا يجوز في
   المقابل أن يُبتلع صامتاً كما يُبتلع فشلُ التقاط نقطةِ مسار — فالمالُ ليس
   أثراً. وبفصلِه إلى دورةٍ مستقلة يكون الفشلُ **إعادةَ محاولةٍ في الدورة
   التالية**، وهو الجوابُ الصحيح لكلٍّ من الأمرين.

والمنطقُ في `services/referrals.py` وهذه غلافٌ رقيق — فالاختبارات تستدعي الخدمة
مباشرةً ولا تحتاج عاملاً يعمل.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.referral import Referral
from app.services import notifications, referrals
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> int:
    async with SessionLocal() as session:
        # `pay_due` تُنهي معاملةَ كلِّ صفٍّ بنفسها: قفلُ صفِّ الإحالة يبقى إلى
        # نهاية المعاملة، وحملُه على مئتي صفٍّ إلى آخر الدورة يمنع كلَّ ما يمسّها
        paid = await referrals.pay_due(session)

        # **والإشعارُ بعد الالتزام** كبقية المشروع: مالٌ يُعلَن قبل أن يُثبَّت
        # قد يُلغى بتراجعٍ فيقرأ صاحبُه مكافأةً لا وجودَ لها. **ولا يُفشل
        # الدورة**: `_safe_notify` يبتلع فشلَه، والمالُ وصل على كل حال
        redis = get_redis_client()
        for referral_id in paid:
            row = await session.get(Referral, referral_id)
            if row is None:  # pragma: no cover
                continue
            await notifications.publish_referral_rewarded(
                session, redis, referrer_id=row.referrer_user_id, referral=row
            )
        await session.commit()
        return len(paid)


@celery_app.task(name="app.tasks.referrals.pay_referral_rewards")
def pay_referral_rewards() -> int:
    paid = run_async(_sweep())
    if paid:
        logger.info("referral rewards paid: %s", paid)
    return paid
