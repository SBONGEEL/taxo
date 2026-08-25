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
from celery.schedules import crontab

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

# كنسُ الطلبات المعلّقة (المرحلة 12، الصيانة). عشرُ دقائق: مهلةُ إعادة السؤال
# عشرون دقيقة، فدورةٌ أسرعُ لا تجد ما تسأل عنه — ودورةٌ أبطأُ تُطيل حبسَ راكبٍ
# دفعتُه المعلّقة تحجز أجرةَ رحلته
ORDER_SWEEP_INTERVAL_SECONDS = 600

# تقليمُ صندوق الوارد. **يوميّاً لا كلَّ دقيقة**: مدةُ الحفظ تسعون يوماً، وما
# يتجاوزها في يومٍ يُحذف في دورةٍ واحدة. والدفعةُ مسقوفةٌ فالأولى بعد التشغيل
# تأخذ أياماً — وذلك مقصودٌ لا عجز
NOTIFICATION_TRIM_INTERVAL_SECONDS = 86_400

# دورةُ الرحلات المجدولة (المرحلة 12-ط). **دقيقةٌ واحدة**: الموعدُ بالدقيقة،
# ودورةٌ أطول تجعل «حجزَ السابعة» يعني «بين السابعة وبعدها بخمس» — ومن حجز
# موعدَ طائرةٍ لا يقبل ذلك. والدورةُ رخيصةٌ حين لا مستحقّ: استعلامٌ على فهرسٍ جزئي
BOOKING_INTERVAL_SECONDS = 60

# دورةُ رسوم الإلغاء (`design/CANCELLATION-FEE.md`). عشرُ دقائق كالسلف: مهلةُ
# الحامل بالساعات ومدّةُ الدَّين بالأيام، فدقّةُ الدقيقة لا تشتري شيئاً — ولا
# ينتظرها **رفعُ** المنع، فهو يقع في مسار الشحن نفسِه
CANCELLATION_INTERVAL_SECONDS = 600

# دورةُ مراقبة جلسة واتساب الذاتية. **دقيقةٌ واحدة**: الجلسةُ حين تسقط توقف
# تسجيلَ المستخدمين الجدد كلَّهم، والفرقُ بين دقيقةٍ وخمسٍ هو أربعُ دقائقَ من
# بابٍ مغلقٍ لا يعلم به أحد
WHATSAPP_WATCH_INTERVAL_SECONDS = 60

celery_app = Celery(
    "taxo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.notifications",
        "app.tasks.bookings",
        "app.tasks.maintenance",
        "app.tasks.payments",
        "app.tasks.advances",
        "app.tasks.backups",
        "app.tasks.pauses",
        "app.tasks.cancellation",
        "app.tasks.levels",
        "app.tasks.referrals",
        "app.tasks.stops",
        "app.tasks.subscriptions",
        "app.tasks.document_expiry",
        "app.tasks.whatsapp",
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
        # السلف (البند ١٥): الإيقافُ بانقضاء المهلة وتنبيهُ اقترابها. وكلُّ
        # عشر دقائق تكفي — المهلةُ أيامٌ لا دقائق، ورفعُ الإيقاف لا ينتظر هذه
        # الدورة أصلاً بل يقع في مسار السداد نفسِه
        "sweep-advances": {
            "task": "app.tasks.advances.sweep_advances",
            "schedule": 600.0,
        },
        "pay-referral-rewards": {
            "task": "app.tasks.referrals.pay_referral_rewards",
            "schedule": REFERRAL_INTERVAL_SECONDS,
        },
        # **كلَّ ربع ساعةٍ تسأل عن الموعد** (خطةُ النسخ §٣): الموعدُ بيانٌ في
        # القاعدة والدورةُ ثابتةٌ في الكود — و`cron` النظام مرفوضٌ لأنه مصدرُ
        # حقيقةٍ ثانٍ للموعد يفترق عن اللوحة أوّلَ تعديل
        # **كلَّ دقيقة كسقف المحطات** — والتنبيهُ يُنبِّه ولا يُنهي رحلة
        "sweep-pause-limits": {
            "task": "app.tasks.pauses.sweep_pause_limits",
            "schedule": 60.0,
        },
        "run-due-backup": {
            "task": "app.tasks.backups.run_due_backup",
            "schedule": 900.0,
        },
        # **كلَّ ساعة** (قرارُ المالك ٥): المستوى حكمٌ على أداء شهرٍ كامل، ودورةٌ
        # أسرعُ تُعيد حسابَ ألفِ صفٍّ لتغيّرٍ لا يراه أحد
        "reevaluate-driver-levels": {
            "task": "app.tasks.levels.reevaluate_driver_levels",
            "schedule": 3600.0,
        },
        "sweep-provider-orders": {
            "task": "app.tasks.maintenance.sweep_provider_orders",
            "schedule": ORDER_SWEEP_INTERVAL_SECONDS,
        },
        "run-due-bookings": {
            "task": "app.tasks.bookings.run_due_bookings",
            "schedule": BOOKING_INTERVAL_SECONDS,
        },
        # **كنسُ ملفاتِ الوثائق اليتيمة** — أسبوعياً لا يومياً: لا مسارَ حذفٍ
        # للكبتن اليوم، واليتيمُ يقع باستبدالٍ انقطع بين الملفِّ والصفّ. ومسحُ
        # مجلدٍ فيه آلافُ الملفات عملٌ لا يُكرَّر بلا سبب
        # **مرّةً في اليوم لا كلَّ دقيقة** (البند ج): العتبةُ يومٌ لا لحظة،
        # ودورةٌ كلَّ دقيقةٍ تسأل القاعدةَ ١٤٤٠ مرّةً عن سؤالٍ جوابُه يتغيّر
        # مرّةً. **والساعةُ 02:30 UTC = 05:30 بعمّان** — بعد منتصف ليل السوقين
        # بساعاتٍ، فيقع التعليقُ في يومه لا قبله.
        "sweep-document-expiry": {
            "task": "app.tasks.document_expiry.sweep_document_expiry",
            "schedule": crontab(hour=2, minute=30),
        },
        "sweep-orphan-documents": {
            "task": "app.tasks.maintenance.sweep_orphan_documents",
            "schedule": crontab(hour=4, minute=20, day_of_week=5),
        },
        "trim-notifications": {
            "task": "app.tasks.maintenance.trim_notifications",
            "schedule": NOTIFICATION_TRIM_INTERVAL_SECONDS,
        },
        # رسومُ الإلغاء (`design/CANCELLATION-FEE.md` §6-أ و§10): منعُ حاملٍ
        # انقضت مهلتُه، ومآلُ دَينٍ لم يعد صاحبُه. **وعشرُ دقائق كالسلف**:
        # المهلتان ساعاتٌ وأيام، ورفعُ المنع لا ينتظر هذه الدورة أصلاً بل يقع
        # في مسار الشحن نفسِه
        "sweep-cancellation-charges": {
            "task": "app.tasks.cancellation.sweep_cancellation_charges",
            "schedule": CANCELLATION_INTERVAL_SECONDS,
        },
        # جلسةُ واتساب الذاتية — **كلَّ دقيقة**: سقوطُها يوقف تسجيلَ المستخدمين
        # الجدد كلَّهم، ودورةٌ كلَّ خمسٍ تعني خمسَ دقائقَ من تسجيلٍ واقفٍ بلا أن
        # يعلم أحد. والدورةُ رخيصةٌ: نداءٌ واحدٌ داخل الشبكة، ولا تنبيهَ إلا
        # على **تحوّل** الحال
        "watch-whatsapp-session": {
            "task": "app.tasks.whatsapp.watch_whatsapp_session",
            "schedule": WHATSAPP_WATCH_INTERVAL_SECONDS,
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
