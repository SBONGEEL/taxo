"""المهمّةُ الدوريةُ لرسوم الإلغاء (`design/CANCELLATION-FEE.md` §6-أ و§10).

**شيئان لا ثالث لهما، ولكلٍّ سببُ دورةٍ لا سببُ مسار:**

1. **حاملٌ انقضت مهلتُه** (§6-أ): قبض رسمَ إلغاءٍ نقداً مع أجرته ولم يحوّله.
   يُكتب له العمودُ المحضَّر `drivers.cancellation_carry_blocked` فيخرج من
   التوزيع — بشكلِ إيقاف السلفة وسببِه: `eligible_driver_ids` تُنادى لكل طلبٍ
   ولخريطة كل راكب، وجمعُ دفترٍ فيها يضع حساباً ماليّاً في المسار الحرج.
   **والاتجاهُ الآخر ليس هنا**: رفعُ المنع يقع في مسار الشحن نفسِه
   (`cancellation.collect_from_carrier`) — من شحن وبقي ممنوعاً عشر دقائق يقرأ
   الشحنَ بلا أثر.

2. **راكبٌ لم يعد** (§10): **ولا حسمَ في الكود** — المآلُ إعدادٌ per-country،
   وثلاثةُ خياراتٍ لا رابع: يبقى معلّقاً (فلا تمرّ عليه الدورةُ أصلاً)، أو
   تشطبه الإدارة (فتتركه الدورةُ لها وتكتفي بجعله ظاهراً في اللوحة)، أو
   **تتحمّله الشركة** فيصل المتضررَ مالُه بدائنٍ بلا مدينٍ مقابل.

**ولماذا لا تشطب الدورةُ حين يقول الإعدادُ «تشطبه الإدارة»؟** لأن ذلك هو نصُّ
الخيار: فرقٌ بين إعدادٍ يقول «افعل» وإعدادٍ يقول «اعرضه على إنسان». ودورةٌ
تشطب في الحالتين تجعل الخيارَين واحداً وتُلغي القرارَ الذي وُضع الإعدادُ له.

**وكلُّ صفٍّ يلتزم في معاملته**: خطأٌ على واحدٍ لا يُلغي ما وقع لغيره — قاعدةُ
كنسِ الطلبات المعلّقة نفسُها.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.cancellation import RideCancellationCharge
from app.models.enums import UnpaidCancellationOutcome
from app.services import cancellation
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)

# **نصُّ السبب الذي يدخل قيدَ التدقيق** — «بأيِّ إعدادٍ قُرِّر» بحرف §10.
# وهو محتوى القرار نفسُه لا قيمةُ حقلٍ تُخفى، كسببِ شطب السلفة
COMPANY_BEARS_REASON = "تحمّلتها الشركة بإعداد الدولة: مضت مدّةُ الدَّين ولم يُسدَّد"


async def _block_overdue_carriers() -> int:
    blocked = 0
    async with SessionLocal() as session:
        for driver_id in await cancellation.overdue_carrier_ids(session):
            driver = await cancellation.block_carrier(session, driver_id)
            if driver is None:  # pragma: no cover - سباقُ دورتين أو سدادٌ سبقها
                await session.rollback()
                continue
            await session.commit()
            blocked += 1
    return blocked


async def _apply_unpaid_outcome() -> int:
    redis = get_redis_client()
    applied = 0
    async with SessionLocal() as session:
        for charge_id in await cancellation.stale_charge_ids(session):
            charge = await session.get(RideCancellationCharge, charge_id)
            if charge is None:  # pragma: no cover
                continue
            outcome = await cancellation.outcome_for_charge(session, charge)
            # **«تشطبه الإدارة» ليست فعلاً هنا**: الصفُّ يبقى معلّقاً ظاهراً في
            # شاشة اللوحة، ويشطبه إنسانٌ باسمه — وهو نصُّ الخيار
            if outcome is not UnpaidCancellationOutcome.COMPANY_BEARS:
                continue
            settled = await cancellation.bear_by_company(
                session, charge_id=charge_id, reason=COMPANY_BEARS_REASON
            )
            if settled is None:  # pragma: no cover
                await session.rollback()
                continue
            await session.commit()
            applied += 1
            # **المتضررُ يُخبَر بوصول ماله وحدَه**: الراكبُ لم يدفع شيئاً، وخبرٌ
            # يصله بأن دَينَه «سُوّي» يقرأ إعفاءً منحه أحدٌ له — ولم يُمنح
            await cancellation.announce_arrival(session, redis, [settled])
    return applied


@celery_app.task(name="app.tasks.cancellation.sweep_cancellation_charges")
def sweep_cancellation_charges() -> int:
    blocked = run_async(_block_overdue_carriers())
    applied = run_async(_apply_unpaid_outcome())
    if blocked or applied:
        logger.info("cancellation: blocked=%s borne=%s", blocked, applied)
    return blocked + applied
