"""صندوق وارد الإشعارات داخل التطبيق (المرحلة 9-ب).

الطبقة الوحيدة التي تكتب `user_notifications` وتقرؤه. تُستدعى الكتابةُ من
بابَي الإرسال القائمين وحدهما — `services/notifications.py` للمعاملاتي و
`services/campaigns.py` للتسويقي — فلا تُضاف قناةٌ لحدثٍ وتُنسى لآخر، وهو
نفس مبدأ «بابٌ واحد للقناتين» الذي أرسته المرحلة 8.

**ما يُكتب وما لا يُكتب:**

- المعاملاتي يُكتب **دائماً**: لا عقد FCM، أو الجهاز مفتوحٌ فلا Push له —
  كلاهما لا يعني أن الحدث لم يقع.
- التسويقي يُكتب **لمن أُرسل إليه فعلاً** (`DeliveryStatus.SENT`) لا لمن
  تُخطّي. من أطفأ إشعارات العروض أطفأها؛ وإدخالُها صندوقَه من بابٍ آخر
  التفافٌ على إطفاءٍ صريح.

و`record` تضيف للجلسة ولا تُنهي معاملة — الـ commit مسؤولية المستدعي، كما
بقية الخدمات.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import UserNotification

# سقفُ قراءةٍ واحد لكل المسارات: الصندوق ينمو بلا تقليم حتى المرحلة 12
MAX_PAGE_SIZE = 100


def _now() -> datetime:
    return datetime.now(UTC)


async def record(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> UserNotification:
    """يضيف صفَّ صندوقٍ واحداً. الـ commit مسؤولية المستدعي."""
    entry = UserNotification(
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        # `{}` و`None` سواءٌ للقارئ، وتخزينُ الفارغ يملأ العمود بلا معنى
        data=data or None,
    )
    session.add(entry)
    return entry


async def list_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    unread_only: bool = False,
) -> Sequence[UserNotification]:
    stmt = (
        select(UserNotification)
        .where(UserNotification.user_id == user_id)
        .order_by(UserNotification.created_at.desc())
    )
    if unread_only:
        stmt = stmt.where(UserNotification.read_at.is_(None))
    return (
        await session.scalars(stmt.limit(min(limit, MAX_PAGE_SIZE)).offset(offset))
    ).all()


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    """عدد غير المقروء — النقطة الحمراء على الجرس تُرسم منه."""
    return (
        await session.scalar(
            select(func.count())
            .select_from(UserNotification)
            .where(
                UserNotification.user_id == user_id,
                UserNotification.read_at.is_(None),
            )
        )
        or 0
    )


async def mark_read(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    ids: Sequence[uuid.UUID] | None = None,
) -> int:
    """يعلّم إشعارات المستخدم مقروءةً ويعيد عددَ ما تغيّر.

    الشرط `user_id` موجودٌ حتى مع تمرير المُعرّفات: معرّفٌ لغير صاحبه لا
    يُعلَّم ولا يُبلَّغ عنه — الجهل به هو الجواب الصحيح (لا IDOR، القسم 14).
    وغيرُ المقروء وحده يُحدَّث فلا يُزاح ختمُ قراءةٍ قديم.
    """
    stmt = (
        update(UserNotification)
        .where(
            UserNotification.user_id == user_id,
            UserNotification.read_at.is_(None),
        )
        .values(read_at=_now())
    )
    if ids is not None:
        if not ids:
            return 0
        stmt = stmt.where(UserNotification.id.in_(list(ids)))

    result = await session.execute(stmt)
    return result.rowcount or 0
