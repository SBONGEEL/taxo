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


@celery_app.task(name="app.tasks.maintenance.sweep_orphan_documents")
def sweep_orphan_documents() -> str:
    """يمحو ملفاتِ الوثائق التي لا صفَّ لها — **قرصٌ لا مالكَ لما فيه**.

    **ولمَ مهمّةٌ لا `CASCADE`؟** المفتاحُ الأجنبيُّ يمحو **الصفَّ** ولا يمسّ
    القرص. ولا مسارَ حذفِ كبتنٍ في المشروع اليوم، لكنّ اليتيمَ يقع بغيره:
    استبدالُ وثيقةٍ يحذف ملفَها **بعد** الإيداع، فانقطاعٌ بينهما يترك ملفاً بلا
    مرجع. **ومشكلةُ قرصٍ يمتلئ تظهر بعد سنة**، حين لا أحدَ يذكر ما تركها.

    **والاتجاهُ واحد**: يُمحى ملفٌّ لا صفَّ له، **ولا يُمحى صفٌّ لا ملفَ له** —
    الثاني عطبٌ يجب أن يُرى لا أن يُنظَّف، وصفٌّ يَعِد بملفٍّ مفقود هو ما
    يكتشفه المشرفُ يومَ المراجعة فيسأل.
    """
    return run_async(_sweep_orphan_documents())


async def _sweep_orphan_documents() -> str:
    from sqlalchemy import select

    from app.core import storage
    from app.models.driver import DriverDocument

    root = storage.root()
    if not root.exists():
        return "0"

    from app.models.ride_call import RideCall

    async with SessionLocal() as session:
        known = {
            row for row in (await session.scalars(select(DriverDocument.file_path)))
        }
        # **وتسجيلاتُ المكالمات معروفةٌ لا يتيمة** (SPEC §٦٦-ج/١٦) — تُكتب تحت الجذر نفسِه، ولها كنسُها بموعدها
        # (`ride_calls.purge_expired`). **وبغير هذا السطر يمحوها هذا الكنسُ أسبوعياً قبل موعدها** ويبقى صفُّها يَعِد بملف
        known |= {
            row
            for row in (
                await session.scalars(
                    select(RideCall.recording_path).where(RideCall.recording_path.is_not(None))
                )
            )
        }

    removed = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        # **الملفُّ المؤقتُ يُترك لساعةٍ**: رفعٌ جارٍ الآن اسمُه `.part-…`،
        # ومحوُه تحت يدِ صاحبه يجعل رفعاً سليماً يفشل بلا سبب
        if path.name.startswith(".part-"):
            continue
        if relative in known:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:  # pragma: no cover
            logger.warning("تعذّر محوُ ملفٍ يتيم: %s", relative)

    if removed:
        logger.info("مُحيت %d ملفَ وثيقةٍ بلا صفّ", removed)
    return str(removed)
