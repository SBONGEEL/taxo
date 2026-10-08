"""المهمّتان الدوريّتان للمدفوعات غير المؤكَّدة (`design/PAYMENTS-UNCONFIRMED.md` §٣/§٢-٥، SPEC §٦٤-ج).

- **التذكيرات كلَّ خمس دقائق**: مواعيدُ §٣ بعد نهاية الرحلة، **مختومةً على الصفّ** — فكنسان معاً تذكيرٌ واحد.
- **الإتمامُ الآليُّ للكاش كلَّ خمس دقائق** — بمفتاحه المستقلّ (`cash_auto_confirm_enabled`) فوق مفتاح الميزة.

**كلُّ دفعةٍ في معاملتها** (نمطُ `tasks/payments.py`): صفٌّ يسقط — لأن كبتناً أكّده في اللحظة نفسِها أو لأن إشعاراً تعثّر —
لا يُسقط الدورةَ ولا يُرجع ما قبله. **والإرسالُ بعد الـcommit**: تذكيرٌ يُعلَن ثمّ ترتدّ معاملتُه يصل صاحبَه ولا يُختم، فيتكرّر.

**ولا ساعاتَ هدوءٍ للراكب في الخلفية** (§٣ يذكر «التي اختارها الراكب — R23»): **لا إعدادَ لكلِّ راكبٍ قائمٌ اليوم**، وساعاتُ
السوق (`notification_settings`) للحملات التسويقية لا للمعاملات (`notifications.py`: «غيرُ قابلةٍ للإطفاء»). فيُرسل التذكيرُ في
موعده حتى يُبنى إعدادُ الراكب.

والمنطقُ في `services/unconfirmed_payments.py` وهذه غلافٌ رقيق، فالاختباراتُ تستدعي الخدمةَ مباشرةً.
"""

from __future__ import annotations

import logging
import uuid

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.ride import Ride
from app.services import cancellation, notifications
from app.services import unconfirmed_payments as service
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def remind_payment(payment_id: uuid.UUID) -> int:
    """تذكيرُ دفعةٍ واحدةٍ في معاملتها — ويعيد عددَ ما أُرسل."""
    async with SessionLocal() as session:
        notices = await service.remind_one(session, payment_id)
        await session.commit()
        await service.send(session, get_redis_client(), notices)
    return len(notices)


async def _sweep_reminders() -> int:
    async with SessionLocal() as session:
        due = await service.reminder_candidate_ids(session)
    sent = 0
    for payment_id in due:
        try:
            sent += await remind_payment(payment_id)
        except Exception:  # pragma: no cover - عطلٌ عابر لا يُسقط الدورة
            logger.exception("تعذّر تذكيرُ الدفعة %s", payment_id)
    return sent


async def auto_confirm_payment(payment_id: uuid.UUID) -> bool:
    """إتمامُ دفعةٍ واحدةٍ إن اجتمعت شروطُها — **ثمّ يُقال للطرفين ما يُقال بعد «استلمت»** وللكبتن نافذةُ اعتراضه."""
    redis = get_redis_client()
    async with SessionLocal() as session:
        payment = await service.auto_confirm_one(session, payment_id)
        if payment is None:
            await session.rollback()
            return False
        notice = await service.auto_confirmed_notice(session, payment)
        ride = await session.get(Ride, payment.ride_id)
        await session.commit()

        if ride is not None:
            await notifications.publish_payment_confirmed(
                session, redis, rider_id=ride.rider_id, payment=payment
            )
            await cancellation.announce_ride_collection(session, redis, ride_id=ride.id)
        if notice is not None:
            await service.send(session, redis, [notice])
    return True


async def _sweep_auto_confirm() -> int:
    async with SessionLocal() as session:
        due = await service.auto_confirm_candidate_ids(session)
    confirmed = 0
    for payment_id in due:
        try:
            if await auto_confirm_payment(payment_id):
                confirmed += 1
        except Exception:  # pragma: no cover - عطلٌ عابر لا يُسقط الدورة
            logger.exception("تعذّر الإتمامُ الآليُّ للدفعة %s", payment_id)
    return confirmed


@celery_app.task(name="app.tasks.unconfirmed_payments.remind_unconfirmed_payments")
def remind_unconfirmed_payments() -> dict[str, int]:
    sent = run_async(_sweep_reminders())
    if sent:
        logger.info("تذكيراتُ المدفوعات المعلَّقة: %s", sent)
    return {"sent": sent}


@celery_app.task(name="app.tasks.unconfirmed_payments.auto_confirm_cash")
def auto_confirm_cash() -> dict[str, int]:
    confirmed = run_async(_sweep_auto_confirm())
    if confirmed:
        logger.info("الإتمامُ الآليُّ للكاش: %s دفعة", confirmed)
    return {"confirmed": confirmed}
