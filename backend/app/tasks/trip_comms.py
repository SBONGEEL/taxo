"""مهمّتا محادثة الرحلة ومكالمتها (SPEC §٦٦) — **غلافان رقيقان على الخدمتين**.

١) **`sweep_trip_comms` — يوميّة**: «الأقدمُ يُحذف آلياً بمهمّةٍ مجدولة» (§٦٦-ب/١٢) — رسائلُ رحلةٍ مضت مدّةُ سوقها، وسجلُّ مكالماتها،
   والتسجيلاتُ التي حلّ موعدُها. **دفعاتٌ لا حذفٌ واحد**، كلُّ دفعةٍ معاملتُها — حتى تفرغ أو يبلغ السقف، والباقي غداً.
   **وتعمل والمفتاحان مطفآن**: الإطفاءُ يمنع الجديد ولا يُبقي ما حُفظ قبله فوق موعده.
٢) **`expire_ringing_calls` — كلَّ دقيقة**: رنينٌ تجاوز ثلاثين ثانيةً يُكتب «لم يُردّ»، ويُخبر الطرفين، **ويصل المتصَلَ به إشعارُ
   «مكالمةٌ فائتة»** (§٦٦-د/٤). والحكمُ الكسولُ في الخدمة يسبقها — هذه تُنظّف ما لم يلمسه أحد.
"""

from __future__ import annotations

import logging

from app.core import storage
from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import ride_calls, trip_chat
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)

#: **سقفُ الدفعات في التشغيلة** — ألفٌ في كلٍّ، فمئةُ دفعةٍ مئةُ ألف سطرٍ في الليلة والباقي غداً
MAX_BATCHES = 100


async def _sweep() -> dict[str, int]:
    tally = {"messages": 0, "deleted_accounts": 0, "calls": 0, "recordings": 0}
    for _ in range(MAX_BATCHES):
        async with SessionLocal() as session:
            chat = await trip_chat.purge_expired(session)
            calls, files = await ride_calls.purge_expired(session)
            await session.commit()
        # **الملفّاتُ بعد الالتزام لا قبله** — صفٌّ يشير إلى ملفٍّ ممحوٍّ عطل، وملفٌّ بلا صفٍّ نفاية
        for relative_path in files:
            await storage.delete(relative_path)
        tally["messages"] += chat["messages"]
        tally["deleted_accounts"] += chat["deleted_accounts"]
        tally["calls"] += calls
        tally["recordings"] += len(files)
        if not (chat["messages"] or chat["deleted_accounts"] or calls or files):
            break
    return tally


@celery_app.task(name="app.tasks.trip_comms.sweep_trip_comms")
def sweep_trip_comms() -> dict[str, int]:
    tally = run_async(_sweep())
    if any(tally.values()):
        logger.info("كنسُ المحادثة والمكالمات: %s", tally)
    return tally


async def _expire() -> int:
    redis = get_redis_client()
    async with SessionLocal() as session:
        missed = await ride_calls.expire_ringing(session)
        await session.commit()
        for call in missed:
            await ride_calls.publish_missed(session, redis, call)
    return len(missed)


@celery_app.task(name="app.tasks.trip_comms.expire_ringing_calls")
def expire_ringing_calls() -> int:
    missed = run_async(_expire())
    if missed:
        logger.info("مكالماتٌ فائتة: %s", missed)
    return missed
