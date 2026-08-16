"""مهمّةُ النسخ الاحتياطي — **كلَّ ربع ساعةٍ تسأل عن الموعد** (الخطة §٣).

والموعدُ بيانٌ في القاعدة والدورةُ ثابتةٌ في الكود — شكلُ `subscriptions.renew_due`
نفسُه. و**cron النظام مرفوضٌ** لأنه يصير مصدرَ حقيقةٍ ثانياً للموعد يفترق عن
اللوحة أوّلَ تعديل.

**والتنبيهُ على التحوّل لا على الحال** (قاعدةُ `tasks/whatsapp.py`): تنبيهٌ يتكرر
كلَّ ربع ساعةٍ يُهمَل خلال ساعة — وهي الساعةُ التي يهمّ فيها.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.enums import UserRole
from app.services import backups
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)

# مفتاحُ «قيل هذا التنبيهُ آنفاً» — **في Redis لا في عمود**: التنبيهُ حدثٌ لا
# سجلّ، وعمودٌ له يجعل «هل نُبِّه؟» سؤالاً يُجاب من مكانين
ALERT_KEY = "backup:alerted"
ALERT_TTL_SECONDS = 6 * 3600


async def _notify_admins(session, redis, *, title: str, body: str, data: dict) -> None:
    """يصل صندوقَ كلِّ `admin` — **فلا يعتمد التنبيهُ على أن يفتح أحدٌ الشاشة**."""
    from sqlalchemy import select

    from app.models.user import User
    from app.services import notifications
    from app.services.push import PushMessage

    admins = (
        await session.scalars(
            select(User.id).where(
                User.role == UserRole.ADMIN, User.is_blocked.is_(False)
            )
        )
    ).all()
    for user_id in admins:
        await notifications.notify_user(
            session,
            redis,
            user_id=user_id,
            message=PushMessage(title=title, body=body, data=data),
        )


async def _sweep() -> str:
    redis = get_redis_client()
    async with SessionLocal() as session:
        due = await backups.is_due(session)

        if due:
            # **قفلٌ يمنع نسختين معاً**: عاملان يلتقطان الموعدَ نفسَه يملآن
            # القرصَ ويتنازعان I/O. و`SET NX` هو الحارس، لا ترتيبُ الجدولة
            got = await redis.set(
                backups.LOCK_KEY,
                "1",
                nx=True,
                ex=backups.LOCK_TTL_SECONDS,
            )
            if got:
                try:
                    run = await backups.take(session)
                    logger.info("scheduled backup: %s (%s)", run.name, run.status)
                finally:
                    await redis.delete(backups.LOCK_KEY)

        alerts = await backups.alerts(session)
        if not alerts.any:
            await redis.delete(ALERT_KEY)
            return "ok"

        # **يُقال مرةً كلَّ ستِّ ساعات لا كلَّ ربع ساعة**
        if await redis.set(ALERT_KEY, "1", nx=True, ex=ALERT_TTL_SECONDS):
            lines = []
            if alerts.stale_hours is not None:
                lines.append(f"مضى {alerts.stale_hours} ساعةً بلا نسخةٍ ناجحة")
            if alerts.unpulled is not None:
                lines.append(f"{alerts.unpulled} نسخٍ لم تُسحب بعد")
            if alerts.disk_percent is not None:
                lines.append(f"مساحةُ النسخ بلغت {alerts.disk_percent}٪ من سقفها")
            await _notify_admins(
                session,
                redis,
                title="النسخ الاحتياطي يحتاج انتباهك",
                body=" · ".join(lines),
                data={
                    "type": "backup_alert",
                    "stale_hours": alerts.stale_hours,
                    "unpulled": alerts.unpulled,
                    "disk_percent": alerts.disk_percent,
                },
            )
            await session.commit()
        return "alerted"


@celery_app.task(name="app.tasks.backups.run_due_backup")
def run_due_backup() -> str:
    return run_async(_sweep())
