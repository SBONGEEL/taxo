"""مراقبةُ جلسة واتساب الذاتية — **جلسةٌ تسقط صامتةً توقف التسجيل كلَّه**.

وهذا هو سببُ وجود هذه المهمّة وحدَه: كلُّ ما عداها في هذه القناة يُكتشف بمحاولة
إرسالٍ تفشل — أي **بعد** أن يقف مستخدمٌ أمام شاشةٍ لا تُكمل. والمهمّةُ تسبقه.

**وتنبّه على التحوّل لا على الحال**: تنبيهٌ كلَّ دقيقةٍ ما دامت ساقطةً يُقرأ
ضجيجاً في الساعة الأولى ويُصمَت عنه في الثانية — وهي بعينها الساعةُ التي يهمّ
فيها. فيُحفظ آخرُ حالٍ في Redis، ولا يُرسل شيءٌ إلا حين تتغيّر.

**ولا تُنبّه على `disconnected` فوراً**: انقطاعٌ عابرٌ يعود وحدَه بعد ثوانٍ،
وإيقاظُ المشرف له يجعله يتجاهل الإيقاظَ التالي. فتُمهَل دورتين، ثم تُقال.
**أما `awaiting_qr` و`unreachable` فتُقالان في الحال**: الأولى تنتظر إنساناً
والثانيةُ تعني أن البوابةَ نفسَها ليست هناك، وكلتاهما لا تعود وحدها.

**والعودةُ تُقال أيضاً**: من أُوقظ لعطبٍ يستحق أن يعرف أنه انتهى، وإلا بقي
يفتح الشاشةَ يتفقّد.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.enums import UserRole
from app.models.user import User
from app.services import notifications
from app.services.whatsapp import session as whatsapp_session
from app.tasks.celery_app import celery_app, run_async
from sqlalchemy import select

logger = logging.getLogger(__name__)

STATE_KEY = "whatsapp:session:last_state"
STRIKE_KEY = "whatsapp:session:strikes"

# الحالُ التي لا تعود وحدها — تُقال في الحال
URGENT = ("awaiting_qr", "unreachable")

# **ودورتان قبل إعلان الانقطاع**: العابرُ يعود في ثوانٍ، وإيقاظُ المشرف له
# يجعله يتجاهل الإيقاظَ الذي بعده
DISCONNECT_STRIKES = 2

# عمرُ المفتاحين: أطولُ من دورتين بكثير، وأقصرُ من أن يبقى حالٌ قديمٌ يُقارَن
# به بعد يوم — والقياسُ حينها يُعاد من أوّله وهو الصواب
_TTL_SECONDS = 3600


async def _admins(session) -> list[User]:
    rows = await session.scalars(
        select(User).where(User.role == UserRole.ADMIN, User.is_blocked.is_(False))
    )
    return list(rows)


async def _watch() -> str:
    redis = get_redis_client()
    async with SessionLocal() as session:
        state = await whatsapp_session.read(session)

        # القناةُ ليست الذاتية — لا جلسةَ تُراقَب، ويُنسى ما حُفظ
        if state.state == whatsapp_session.STATE_OFF:
            await redis.delete(STATE_KEY, STRIKE_KEY)
            return state.state

        previous_raw = await redis.get(STATE_KEY)
        previous = (
            previous_raw.decode() if isinstance(previous_raw, bytes) else previous_raw
        )

        if state.state == "disconnected":
            strikes = int(await redis.incr(STRIKE_KEY))
            await redis.expire(STRIKE_KEY, _TTL_SECONDS)
            if strikes < DISCONNECT_STRIKES:
                # لم تُعلن بعد: الحالُ المحفوظ يبقى كما كان حتى يُحسم
                return f"{state.state}:{strikes}"
        else:
            await redis.delete(STRIKE_KEY)

        if state.state == previous:
            return state.state

        await redis.set(STATE_KEY, state.state, ex=_TTL_SECONDS)
        if previous is None:
            # أوّلُ قياسٍ بعد إقلاعٍ ليس حدثاً: لا شيءَ **تغيّر**
            return state.state

        recovered = state.state == "linked"
        if not recovered and state.state not in URGENT and state.state != "disconnected":
            return state.state

        for admin in await _admins(session):
            await notifications.publish_whatsapp_session(
                session,
                redis,
                user_id=admin.id,
                state=state.state,
                needs_human=state.needs_human,
                detail=state.last_error,
            )
        await session.commit()
        logger.warning(
            "whatsapp session %s -> %s (notified)", previous, state.state
        )
        return state.state


@celery_app.task(name="app.tasks.whatsapp.watch_whatsapp_session")
def watch_whatsapp_session() -> str:
    return run_async(_watch())
