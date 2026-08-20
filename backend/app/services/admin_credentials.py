"""اعتمادُ دخولِ المشرف — إنشاءٌ وتعديلٌ وتسجيلُ استعمال.

**والاسمُ يُطبَّع في بيتٍ واحد** (`models/admin_credential.normalize_username`):
دالّتان تطبّعان بطريقتين تجعلان اسماً يُكتب ولا يُوجد.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput
from app.models.admin_credential import AdminCredential, normalize_username
from app.models.enums import AuditAction
from app.models.user import User
from app.services import audit

# اسمٌ لا يُخمَّن: هذه الثلاثةُ أولُ ما يُجرَّب على أيِّ لوحةٍ في العالم
FORBIDDEN_USERNAMES: frozenset[str] = frozenset({"admin", "taxo", "root"})

MIN_LENGTH = 3
MAX_LENGTH = 64


def validate_username(raw: str) -> str:
    """يعيد الاسمَ مطبَّعاً أو يرفع `InvalidInput`."""
    name = normalize_username(raw)
    if not (MIN_LENGTH <= len(name) <= MAX_LENGTH):
        raise InvalidInput(
            f"اسم المستخدم بين {MIN_LENGTH} و{MAX_LENGTH} حرفاً"
        )
    if not all(ch.isalnum() or ch in "._-" for ch in name):
        raise InvalidInput("اسم المستخدم: حروفٌ وأرقامٌ و«.» و«_» و«-» فقط")
    if name in FORBIDDEN_USERNAMES:
        raise InvalidInput("اسم المستخدم هذا محجوز — اختر غيره")
    return name


async def create(
    session: AsyncSession,
    *,
    user: User,
    username: str,
    is_break_glass: bool = False,
) -> AdminCredential:
    row = AdminCredential(
        user_id=user.id,
        username=validate_username(username),
        is_break_glass=is_break_glass,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("اسم المستخدم مأخوذ") from exc
    return row


async def for_user(
    session: AsyncSession, user_id: uuid.UUID
) -> AdminCredential | None:
    return await session.scalar(
        select(AdminCredential).where(AdminCredential.user_id == user_id)
    )


async def rename(
    session: AsyncSession, *, user: User, new_username: str
) -> AdminCredential:
    """يغيّر الاسمَ — **ويُسجَّل بالقديم والجديد**.

    وهذا استثناءُ «لا قيمَ في التدقيق» المعتاد: القيمةُ هنا **هي الحدث** — من
    يقرأ السجلَّ بعد شهرٍ يسأل «من صار من؟»، واسمُ حقلٍ تغيّر لا يجيبه.
    """
    row = await for_user(session, user.id)
    if row is None:
        raise InvalidInput("هذا الحساب لا يدخل باسم مستخدم")

    old = row.username
    row.username = validate_username(new_username)
    if row.username == old:
        return row
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("اسم المستخدم مأخوذ") from exc

    await audit.record(
        session,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="admin_credential",
        entity_id=row.id,
        details={"field": "username", "from": old, "to": row.username},
    )
    return row


async def note_login(
    session: AsyncSession, user: User, *, redis: Redis | None = None
) -> None:
    """يختم آخرَ دخول — **ويصيح إن كان حسابَ طوارئ**.

    والصياحُ صفٌّ في التدقيق **بلا فاعلٍ في `details`**: الفاعلُ هو الحساب
    نفسُه، وما يُقال هو أن البابَ النائمَ فُتح.
    """
    row = await for_user(session, user.id)
    if row is None:
        return
    row.last_login_at = datetime.now(UTC)
    if row.is_break_glass:
        await audit.record(
            session,
            actor=user,
            action=AuditAction.UPDATE,
            entity_type="admin_break_glass_login",
            entity_id=row.id,
            details={"username": row.username},
        )
