"""صندوق وارد الإشعارات داخل التطبيق (المرحلة 9-ب).

ثلاثة مسارات لا أكثر: القائمة، وعدّاد غير المقروء (النقطة الحمراء على
الجرس)، وتعليمُها مقروءة. لا مسارَ إنشاء: الصفوف تُكتب من بابَي الإرسال
وحدهما (`services/notifications.py` و`services/campaigns.py`) — إشعارٌ
يُنشئه العميل ليس إشعاراً.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.notification import (
    MarkReadIn,
    UnreadCountOut,
    UserNotificationOut,
)
from app.services import inbox

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


@router.get("", response_model=list[UserNotificationOut])
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    unread_only: bool = False,
    limit: int = Query(default=30, ge=1, le=inbox.MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
) -> list[UserNotificationOut]:
    entries = await inbox.list_for_user(
        session, user.id, limit=limit, offset=offset, unread_only=unread_only
    )
    return [UserNotificationOut.model_validate(entry) for entry in entries]


@router.get("/unread-count", response_model=UnreadCountOut)
async def count_unread(user: CurrentUser, session: DbSession) -> UnreadCountOut:
    return UnreadCountOut(unread=await inbox.unread_count(session, user.id))


@router.post("/read", response_model=UnreadCountOut)
async def mark_read(
    payload: MarkReadIn, user: CurrentUser, session: DbSession
) -> UnreadCountOut:
    """يعلّم إشعارات صاحبها مقروءة ويعيد ما بقي غير مقروء.

    إعادةُ العدّاد لا عددِ ما تغيّر: الجرس يريد أن يعرف هل يُطفئ نقطته، لا
    كم صفّاً لمسه هذا الطلب.
    """
    await inbox.mark_read(session, user.id, ids=payload.ids)
    await session.commit()
    return UnreadCountOut(unread=await inbox.unread_count(session, user.id))
