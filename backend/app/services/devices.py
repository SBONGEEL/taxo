"""أجهزة المستخدم ورموزها لدى FCM (SPEC القسم 4/10 — المرحلة 8).

ثلاث عمليات: تسجيلُ جهازٍ عند الدخول، وحذفُه عند الخروج، وتعطيلُ رمزٍ قال
المزود إنه لم يعد مسجَّلاً.

**التسجيل يسرق الرمز ولا يشاركه.** رمز FCM يعرّف تثبيتَ تطبيقٍ واحد على
جهازٍ واحد؛ فإن سجّل عليه حسابٌ آخر انتقل إليه وحده — وإلا وصل إشعارُ الحساب
السابق إلى من يحمل الهاتف بعده. وهذا هو المعنى العملي لـ «تسجيل/حذف الجهاز
عند الدخول والخروج».
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput
from app.models.device import DeviceToken
from app.models.enums import DevicePlatform
from app.models.user import User


def _now() -> datetime:
    return datetime.now(UTC)


async def register(
    session: AsyncSession,
    *,
    user: User,
    device_id: str,
    token: str,
    platform: DevicePlatform,
) -> DeviceToken:
    """يسجّل جهازاً أو يحدّث رمزه. الـ commit مسؤولية المستدعي."""
    device_id = device_id.strip()
    token = token.strip()
    if not device_id or not token:
        raise InvalidInput("مُعرّف الجهاز ورمز الإشعارات مطلوبان")

    # الرمز فريد على مستوى الجدول: أيُّ صفٍّ آخر يحمله لم يعد يصف هذا الجهاز
    await session.execute(
        delete(DeviceToken).where(
            DeviceToken.token == token,
            ~(
                (DeviceToken.user_id == user.id)
                & (DeviceToken.device_id == device_id)
            ),
        )
    )

    existing = await session.scalar(
        select(DeviceToken).where(
            DeviceToken.user_id == user.id, DeviceToken.device_id == device_id
        )
    )
    if existing is None:
        existing = DeviceToken(
            user_id=user.id, device_id=device_id, token=token, platform=platform
        )
        session.add(existing)
    else:
        existing.token = token
        existing.platform = platform

    # إعادة التسجيل تُحيي رمزاً عُطّل: التطبيق يعمل الآن ورمزه جديد
    existing.is_active = True
    existing.last_seen_at = _now()
    await session.flush()
    return existing


async def unregister(session: AsyncSession, *, user: User, device_id: str) -> None:
    """حذفٌ عند الخروج — رمزٌ لحسابٍ خرج من الجهاز لا يُبقى عليه."""
    await session.execute(
        delete(DeviceToken).where(
            DeviceToken.user_id == user.id,
            DeviceToken.device_id == device_id.strip(),
        )
    )


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID
) -> Sequence[DeviceToken]:
    return (
        await session.scalars(
            select(DeviceToken)
            .where(DeviceToken.user_id == user_id)
            .order_by(DeviceToken.last_seen_at.desc())
        )
    ).all()


async def active_tokens_for(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    exclude_device_ids: Iterable[str] = (),
) -> list[str]:
    """رموزُ أجهزةٍ يجوز الإرسال إليها الآن.

    `exclude_device_ids` هي الأجهزة المفتوحة على WebSocket (القسم 10): وصلها
    الحدثُ فعلاً، فإشعارُها تكرارٌ على شاشة مفتوحة.
    """
    excluded = {device_id for device_id in exclude_device_ids if device_id}
    stmt = select(DeviceToken.device_id, DeviceToken.token).where(
        DeviceToken.user_id == user_id, DeviceToken.is_active.is_(True)
    )
    rows = (await session.execute(stmt)).all()
    return [token for device_id, token in rows if device_id not in excluded]


async def deactivate_tokens(session: AsyncSession, tokens: Iterable[str]) -> int:
    """يعطّل رموزاً ردّ عليها المزود «غير مسجَّل» — تعطيلٌ لا حذف.

    الصفُّ يبقى فيتعرف على الجهاز نفسه عند إعادة التسجيل، ولا يُعاد الإرسال
    إلى رمزٍ ميت في كل حملة.
    """
    values = [token for token in tokens if token]
    if not values:
        return 0
    result = await session.execute(
        update(DeviceToken)
        .where(DeviceToken.token.in_(values))
        .values(is_active=False)
    )
    return int(result.rowcount or 0)
