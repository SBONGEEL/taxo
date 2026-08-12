"""المهمة الدورية لسقف انتظار المحطة (SPEC القسم 5.10، المرحلة 12-ب).

الوصولُ فعلُ الكبتن والاستئنافُ فعلُه، أما **بلوغُ السقف فلا يفعله أحد**:
تراه الساعةُ وحدها. وبغير هذه المهمة يقف العدّادُ يمشي بلا أن يعرف أحدٌ أنه
تجاوز — فيُفاجأ الراكبُ بالرقم في شاشة الدفع، ويظنّ الكبتنُ أن لا مخرج له.

**ولا إنهاءَ آلي**: المهمة **تُخطر** وتفتح للكبتن خيارَ الإنهاء، والقرارُ
فعلُه. راكبٌ تأخّر دقيقتين فوق السقف ليس راكباً تُترك أمتعتُه على الرصيف،
ومهمةٌ دوريةٌ تُنهي رحلةً بالنيابة عن إنسانٍ تفعل ما لا يُراجَع.

**والتنبيه مرةً واحدة**: `ride_stops.notified_at` هو أثرُه — بغيره يتكرر في
كل دورة حتى يستأنف الكبتن. وعمودٌ هنا لا مفتاحُ Redis (كتنبيه الاشتراك) لأن
الصفَّ قائمٌ أصلاً، فلا يحتاج أثراً يعيش خارجه.

والمنطق في `services/rides.py` وهذه غلافٌ رقيق، فالاختبارات تستدعي الخدمة
مباشرةً ولا تحتاج عاملاً يعمل.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import notifications, rides as rides_service
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> int:
    """يُخطر الطرفين عن كل محطةٍ تجاوز انتظارُها سقفَها ولم تُخطَر بعد."""
    notified = 0
    async with SessionLocal() as session:
        due = await rides_service.stops_over_max_wait(session)

    for ride_id, stop_id in due:
        # **كلُّ محطةٍ في معاملتها**: صفٌّ يفشل — لأن الكبتن استأنف في اللحظة
        # نفسها، أو لأن إشعاراً تعثّر — لا يُسقط الدورة ولا يُرجع من أُخطر قبله
        try:
            async with SessionLocal() as session:
                marked = await rides_service.mark_stop_notified(session, stop_id)
                if marked is None:
                    continue
                ride, stop = marked
                await session.commit()

                # البثُّ بعد الـcommit كما في كل مسار: قبله قد نُعلن ما يرتدّ
                await notifications.publish_stop_wait_exceeded(
                    session, get_redis_client(), ride=ride, stop=stop
                )
                await session.commit()
            notified += 1
        except Exception:  # pragma: no cover - لا تُسقط الدورة
            logger.exception("تعذّر تنبيه تجاوز انتظار المحطة %s", stop_id)

    return notified


@celery_app.task(name="app.tasks.stops.sweep_stop_waiting")
def sweep_stop_waiting() -> int:
    return run_async(_sweep())
