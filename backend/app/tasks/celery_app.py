"""إعداد Celery ومهامه الدورية (SPEC القسم 2/8).

**ما يدخل هنا وما لا يدخل**: Celery لما يحتمل التأجيل — انتهاء الاشتراكات
والإشعارات والتقارير. توزيعُ الرحلة ليس منها: تفاعليٌّ بمقياس الثواني والراكبُ
ينتظر على الشاشة، فمكانه مهمةُ asyncio داخل عملية التطبيق (`services/dispatch`).

الوسيط Redis نفسه الذي يحمل الحضور والعروض: بنيةٌ تحتية واحدة أقل مما يُدار
ويُراقَب، والمهام هنا قليلة وخفيفة.

**عملية العامل ليست عملية التطبيق**، فلا حلقة أحداث تعمل فيها أصلاً. `run_async`
يفتح حلقةً واحدة لكل عملية ويُبقيها: مجمّع اتصالات asyncpg يرتبط بالحلقة التي
فُتح فيها، فحلقةٌ جديدة لكل مهمة تترك خلفها اتصالات لا يملكها أحد.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from celery import Celery

from app.core.config import settings

# دورة الكنس. أقصر من نافذة تنبيه الـ 24 ساعة بكثير فلا يضيع تنبيه، وأطول من
# أن تُثقل القاعدة. تعليم المنتهي ليس سباقاً مع الوقت أصلاً: الأهلية تُقرأ
# بالساعة في التوزيع، فمرورُ المهمة يُصلح الجدول لا يحرس المال.
SWEEP_INTERVAL_SECONDS = 300

# دورة إرسال الحملات (المرحلة 8). دقيقةٌ واحدة: الحملة تُجدول بدقةِ الدقيقة،
# ودورةٌ أطول تجعل «أرسلها الثامنة» تعني «بين الثامنة والثامنة وخمس دقائق».
# والدورة رخيصة حين لا حملة مستحقة — استعلامٌ واحد على فهرس الحالة والموعد.
CAMPAIGN_INTERVAL_SECONDS = 60

# دورة كنس مهل تأكيد كليك (القسم 6.2/6). خمسُ دقائق كدورة الاشتراكات: المهلة
# نفسها بالساعات، فدقّةُ الدقيقة لا تشتري شيئاً — والتأخرُ خمس دقائق في فتح
# نزاعٍ أهونُ من استعلامٍ كل دقيقة على جدول الدفعات.
STOP_WAIT_INTERVAL_SECONDS = 60.0
CLIQ_SWEEP_INTERVAL_SECONDS = 300

# دورةُ مكافآت الإحالة (المرحلة 12-ح). عشرُ دقائق: الاستحقاقُ يقع بإكمال رحلةٍ
# أو باعتماد حساب، وكلاهما لا ينتظره أحدٌ على شاشة — ومكافأةٌ تصل بعد عشر دقائق
# مكافأةٌ وصلت. والدورةُ رخيصةٌ حين لا مستحقّ: استعلامٌ واحدٌ على فهرس
# `rewarded_at IS NULL`
REFERRAL_INTERVAL_SECONDS = 600

celery_app = Celery(
    "taxo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.notifications",
        "app.tasks.payments",
        "app.tasks.referrals",
        "app.tasks.stops",
        "app.tasks.subscriptions",
    ],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # مهمةٌ عالقة على نداءٍ خارجي لا تُبقي العامل مشغولاً إلى الأبد
    task_time_limit=300,
    task_soft_time_limit=240,
    beat_schedule={
        "sweep-subscriptions": {
            "task": "app.tasks.subscriptions.sweep_subscriptions",
            "schedule": SWEEP_INTERVAL_SECONDS,
        },
        "dispatch-campaigns": {
            "task": "app.tasks.notifications.dispatch_campaigns",
            "schedule": CAMPAIGN_INTERVAL_SECONDS,
        },
        "sweep-cliq-confirmations": {
            "task": "app.tasks.payments.sweep_cliq_confirmations",
            "schedule": CLIQ_SWEEP_INTERVAL_SECONDS,
        },
        # كل دقيقة: السقفُ يُقاس بالدقائق، ودورةٌ كل خمسٍ تجعل تنبيهاً عن
        # تجاوزٍ يصل بعد خمس دقائق من وقوعه — والراكب واقفٌ يقرأ عدّاده
        "sweep-stop-waiting": {
            "task": "app.tasks.stops.sweep_stop_waiting",
            "schedule": STOP_WAIT_INTERVAL_SECONDS,
        },
        "pay-referral-rewards": {
            "task": "app.tasks.referrals.pay_referral_rewards",
            "schedule": REFERRAL_INTERVAL_SECONDS,
        },
    },
)


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """يشغّل مهمةً غير متزامنة على حلقة هذه العملية الواحدة."""
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
