"""إعادةُ تقييم المستويات — **الكاتبُ الوحيد** لـ`drivers.level` (البند ٥٣).

**ولماذا دورةٌ لا حسابٌ عند إنهاء الرحلة؟** لسببين، أحدهما أداءٌ والآخرُ صحّة:

1. عدُّ رحلاتِ شهرٍ ومقارنتُها بأهدافٍ عملٌ لا يقرؤه أحدٌ في لحظة الإنهاء —
   والرحلةُ طريقٌ ساخن يمرّ منه كلُّ راكب.
2. **وأخطرُ**: كاتبان لعمودٍ واحدٍ يجعلانه يفترق عن نفسه. `current_leg` في 12-ب
   له كاتبٌ واحدٌ لهذا السبب، و`rating_avg` يُعاد بناؤه كاملاً من مصدره لا
   يُدوَّر. فالمستوى يُبنى كاملاً هنا، و`level_computed_at` تجيب «متى حُسب؟».

**والدورةُ كلَّ ساعة** (قرارُ المالك ٥) — ومعها بدايةُ الشهر بالضرورة، فأوّلُ
دورةٍ في الشهر الجديد تقرأ مهامَّ الشهر الجديد وتُصفّي مستوياتِ ما قبله.

**وتعديلُ مهمّةٍ في اللوحة يستدعي إعادةَ تقييمٍ فوريةً لتلك الدولة** — وإلا عاش
المستوى على تعريفٍ حُذف، وهو بعينه ما تمنعه قاعدةُ الإحالة.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.services import missions
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> int:
    async with SessionLocal() as session:
        # `reevaluate_all` تُثبّت كلَّ سوقٍ بمعاملته: سوقٌ يفشل لا يُسقط الآخر،
        # ومعاملةٌ واحدةٌ على سوقين تحمل قفلاً على كل كبتنٍ فيهما حتى آخر الدورة
        return await missions.reevaluate_all(session)


@celery_app.task(name="app.tasks.levels.reevaluate_driver_levels")
def reevaluate_driver_levels() -> int:
    changed = run_async(_sweep())
    if changed:
        logger.info("driver levels recomputed: %s", changed)
    return changed
