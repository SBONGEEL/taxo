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

celery_app = Celery(
    "taxo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.subscriptions"],
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
