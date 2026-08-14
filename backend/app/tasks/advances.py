"""المهمة الدورية للسلف (البند ١٥) — الإيقافُ بانقضاء المهلة، وتنبيهُ اقترابها.

**ولماذا دورةٌ لا فحصٌ في التوزيع؟** لأن `eligible_driver_ids` تُنادى لكل طلبٍ
ولخريطة كل راكب: قراءةُ ساعةٍ وجمعُ دفترٍ هناك تضع حساباً ماليّاً في المسار
الحرج. فالدورةُ تكتب **العمودَ المحضَّر** (`drivers.advance_blocked`) والتوزيعُ
يقرؤه بشرطٍ واحدٍ ساكن.

**والاتجاهُ الآخرُ ليس هنا**: رفعُ الإيقاف يقع في **مسار السداد نفسِه**
(`advances._settle_if_clear`) لا في هذه الدورة — من سدَّد وبقي ممنوعاً عشر
دقائق يقرأ السدادَ بلا أثر، فيسدّد مرةً أخرى أو يتّصل بالدعم. الدورةُ تمنع،
والسدادُ يفكّ.

والمنطقُ في `services/advances.py` وهذه غلافٌ رقيق.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import advances, notifications
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)

# نافذةُ تنبيه الاقتراب — أربعٌ وعشرون ساعةً كنافذة الاشتراك: يومٌ عملٍ واحدٌ
# يكفي لسداد سلفةٍ بقيمة اشتراكٍ يومي
DUE_SOON_WINDOW = timedelta(hours=24)

# ومفتاحُ الإزالة في Redis لا عمودٌ على الصف: **التنبيهُ حدثٌ لا سجلّ** — نفسُ
# قاعدةِ تنبيه الاشتراك قبل أربعٍ وعشرين ساعة
DUE_SOON_TTL = int(DUE_SOON_WINDOW.total_seconds()) * 2


async def _sweep() -> int:
    redis = get_redis_client()
    blocked = 0
    async with SessionLocal() as session:
        for advance in await advances.overdue_drivers(session):
            driver = await advances.block_for_overdue(session, advance)
            if driver is None:
                continue
            await session.commit()
            blocked += 1
            user_id = await advances.driver_user_id(session, driver.id)
            if user_id is not None:
                remaining = advance.amount - await advances.repaid_amount(
                    session, advance.id
                )
                await notifications.publish_advance_event(
                    session,
                    redis,
                    driver_user_id=user_id,
                    kind="advance_overdue",
                    amount=remaining,
                    currency=advance.currency.value,
                    due_at=advance.due_at,
                )
    return blocked


async def _notify_due_soon() -> int:
    redis = get_redis_client()
    sent = 0
    async with SessionLocal() as session:
        for advance, user_id in await advances.due_soon(session, DUE_SOON_WINDOW):
            key = f"advance:due_soon:{advance.id}"
            if not await redis.set(key, "1", ex=DUE_SOON_TTL, nx=True):
                continue
            remaining = advance.amount - await advances.repaid_amount(
                session, advance.id
            )
            await notifications.publish_advance_event(
                session,
                redis,
                driver_user_id=user_id,
                kind="advance_due_soon",
                amount=remaining,
                currency=advance.currency.value,
                due_at=advance.due_at,
            )
            sent += 1
    return sent


@celery_app.task(name="app.tasks.advances.sweep_advances")
def sweep_advances() -> int:
    blocked = run_async(_sweep())
    sent = run_async(_notify_due_soon())
    if blocked or sent:
        logger.info("advances: blocked=%s due_soon=%s", blocked, sent)
    return blocked
