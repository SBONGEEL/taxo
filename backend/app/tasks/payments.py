"""المهمة الدورية لمهلة تأكيد حوالة كليك (SPEC القسم 6.2/6).

«عند الرفض أو **انقضاء مهلة التأكيد** → `disputed`». الرفضُ فعلُ الكبتن،
والانقضاءُ هذه المهمة — وبغيرها تبقى الدفعة معلّقةً إلى الأبد إن لم يفتح
تطبيقه، فيبقى مالُ الراكب بلا فصلٍ ولا أحد يعرف.

**كلُّ دفعةٍ في معاملتها**: صفٌّ يفشل — لأن كبتناً أكّده في اللحظة نفسها، أو
لأن إشعاراً تعثّر — لا يُسقط الدورة كلها ولا يُرجع من نُوزع قبله. والبثُّ بعد
الـcommit كما في كل مسار: قبله قد نُعلن نزاعاً يرتدّ.

والمنطق في `services/payments.py` وهذه غلافٌ رقيق، فالاختبارات تستدعي الخدمة
مباشرةً ولا تحتاج عاملاً يعمل.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.ride import Ride
from app.services import notifications, payments
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _expire_one(payment_id: Any) -> bool:
    async with SessionLocal() as session:
        payment = await payments.expire_cliq_confirmation(session, payment_id)
        if payment is None:
            return False

        ride = await session.get(Ride, payment.ride_id)
        driver = await session.get(Driver, ride.driver_id) if ride else None
        await session.commit()

        if ride is not None and driver is not None:
            await notifications.publish_cliq_confirmation_expired(
                session,
                get_redis_client(),
                driver_user_id=driver.user_id,
                rider_user_id=ride.rider_id,
                ride_id=ride.id,
                payment=payment,
            )
            await session.commit()
    return True


async def _sweep() -> int:
    async with SessionLocal() as session:
        due = await payments.expired_cliq_payment_ids(session)

    expired = 0
    for payment_id in due:
        try:
            if await _expire_one(payment_id):
                expired += 1
        except Exception:  # pragma: no cover - عطلٌ عابر لا يُسقط الدورة
            logger.exception("تعذّر إنهاء مهلة الدفعة %s", payment_id)
    return expired


@celery_app.task(name="app.tasks.payments.sweep_cliq_confirmations")
def sweep_cliq_confirmations() -> dict[str, int]:
    """ينقل دفعات كليك التي انقضت مهلتها إلى نزاع، ويُخطر الطرفين."""
    expired = run_async(_sweep())
    logger.info("كنس مهل كليك: %s دفعة صارت نزاعاً", expired)
    return {"expired": expired}
