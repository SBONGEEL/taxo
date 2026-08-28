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
from app.models.user_role_grant import has_role_clause

logger = logging.getLogger(__name__)

# مفتاحُ «قيل هذا التنبيهُ آنفاً» — **في Redis لا في عمود**: التنبيهُ حدثٌ لا
# سجلّ، وعمودٌ له يجعل «هل نُبِّه؟» سؤالاً يُجاب من مكانين
ALERT_KEY = "backup:alerted"
ALERT_TTL_SECONDS = 6 * 3600


async def _notify_admins(session, redis, *, alerts) -> None:
    """يصل صندوقَ كلِّ `admin` — **فلا يعتمد التنبيهُ على أن يفتح أحدٌ الشاشة**.

    **وبابُه `publish_backup_alert` لا `notify_user`**: الثاني دفعٌ وحدَه،
    والمشرفُ بلا أجهزةِ دفعٍ بالتصميم — فكان الإنذارُ ينادي من لا يسمع.
    """
    from sqlalchemy import select

    from app.models.user import User
    from app.services import notifications

    admins = (
        await session.scalars(
            select(User.id).where(
                has_role_clause(UserRole.ADMIN),
                User.is_blocked.is_(False),
            )
        )
    ).all()
    for user_id in admins:
        await notifications.publish_backup_alert(
            session,
            redis,
            user_id=user_id,
            stale_hours=alerts.stale_hours,
            unpulled=alerts.unpulled,
            disk_percent=alerts.disk_percent,
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
            await _notify_admins(session, redis, alerts=alerts)
            await session.commit()
        return "alerted"


@celery_app.task(name="app.tasks.backups.run_due_backup")
def run_due_backup() -> str:
    return run_async(_sweep())
