"""الدخولُ بالبصمة بعد الخروج (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §60-ج) — **إشعالٌ وصرفٌ ونسيانٌ وإبطال**.

انظر `models/device_login.py` لماذا هو بيانُ جهازٍ لا رمزُ جلسة. **والخلفيةُ لا تعرف بصمةً هنا أيضاً**: الجهازُ يشهد بالبصمة على
نفسه ثمّ يقرأ السرَّ من مخزنه الآمن، والخلفيةُ لا ترى إلا سرّاً تقارن بصمتَه — كما كانت لا ترى إلا رمزَ تجديد.

**ولا قفلَ صفٍّ يُضاف إلى ترتيب الأقفال**: الصرفُ يقفل صفَّ البيان وحدَه (`FOR UPDATE` قبل الفحص)، ولا رحلةَ ولا مالَ في المسار.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidCredentials, InvalidInput
from app.models.device_login import DeviceLogin
from app.models.user import User

#: أسبابُ الإبطال — نصٌّ قصيرٌ في `device_logins.revoked_reason`
REVOKE_REPLACED = "replaced"
REVOKE_FORGOTTEN = "forgotten"
REVOKE_DISABLED = "disabled"

APPS = ("rider", "driver")


def _now() -> datetime:
    return datetime.now(UTC)


def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _new_secret() -> str:
    return secrets.token_urlsafe(32)


def _app(app: str) -> str:
    if app not in APPS:
        raise InvalidInput("الدخولُ بالبصمة لتطبيقَي الراكب والكبتن وحدَهما", field="app")
    return app


async def enroll(session: AsyncSession, *, user: User, device_id: str, app: str) -> str:
    """**يُشعل البصمةَ على هذا الجهاز** ويعيد السرَّ مرّةً واحدة — والبيانُ الحيُّ السابقُ للجهاز نفسِه يُبطَل لا يُجاوَر."""
    app = _app(app)
    await session.execute(
        update(DeviceLogin)
        .where(
            DeviceLogin.user_id == user.id,
            DeviceLogin.device_id == device_id,
            DeviceLogin.app == app,
            DeviceLogin.revoked_at.is_(None),
        )
        .values(revoked_at=_now(), revoked_reason=REVOKE_REPLACED)
    )
    secret = _new_secret()
    session.add(DeviceLogin(user_id=user.id, device_id=device_id, app=app, secret_hash=_digest(secret)))
    await session.flush()
    return secret


async def _live(session: AsyncSession, *, device_id: str, secret: str, app: str) -> DeviceLogin | None:
    return await session.scalar(
        select(DeviceLogin)
        .where(
            DeviceLogin.secret_hash == _digest(secret),
            DeviceLogin.device_id == device_id,
            DeviceLogin.app == app,
            DeviceLogin.revoked_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def spend(session: AsyncSession, *, device_id: str, secret: str, app: str) -> tuple[User, str]:
    """**يصرف السرَّ ويُدوِّره** — ويعيد صاحبَه والسرَّ الجديد. **وكلُّ رفضٍ رفضٌ واحد** («بياناتُ الدخول غير صحيحة»): من لا
    يملك السرَّ لا يُخبَر أكان الجهازُ مسجّلاً أم أُبطل أم لم يكن."""
    app = _app(app)
    row = await _live(session, device_id=device_id, secret=secret, app=app)
    if row is None:
        raise InvalidCredentials()
    user = await session.get(User, row.user_id)
    if user is None or user.is_blocked or user.deactivated_at is not None:
        row.revoked_at = _now()
        row.revoked_reason = REVOKE_DISABLED
        await session.flush()
        raise InvalidCredentials()
    fresh = _new_secret()
    row.secret_hash = _digest(fresh)
    row.last_used_at = _now()
    await session.flush()
    return user, fresh


async def forget(session: AsyncSession, *, device_id: str, secret: str, app: str) -> None:
    """**«الدخول بحساب آخر»** — يُبطل البيانَ بسرّه، **ولا يفشل**: غيابُه هو المقصود."""
    if app not in APPS:
        return
    row = await _live(session, device_id=device_id, secret=secret, app=app)
    if row is not None:
        row.revoked_at = _now()
        row.revoked_reason = REVOKE_FORGOTTEN
        await session.flush()


async def revoke_all(session: AsyncSession, user_id: uuid.UUID | str, *, reason: str) -> int:
    """**يُبطل كلَّ بيانات الحساب** — يناديه `token_service.revoke_all_for_user`، فكلُّ ما يُبطل الجلسات كلَّها يُبطلها معه."""
    result = await session.execute(
        update(DeviceLogin)
        .where(DeviceLogin.user_id == user_id, DeviceLogin.revoked_at.is_(None))
        .values(revoked_at=_now(), revoked_reason=reason[:32])
    )
    return result.rowcount or 0
