"""إضافةُ الدور الثاني لحسابٍ قائم — **راكبٌ يصير كبتناً برقمه نفسِه، وكبتنٌ يصير راكباً** (أمرُ المالك ٢٠٢٦-١٠-٢٩، SPEC §21.6).

## ما كان يمنعه
`create_account` يرفض رقماً له حسابٌ من نوعه (`phone_already_registered`)، و`app_scope.guard` يرفض راكباً في تطبيق الكبتن
(`wrong_app_for_role`) — **والنموذجُ يسمح بالدورين منذ §21** (`user_roles` مجموعة، ومحفظتان بسياق الفعل)، فلم يكن الناقصُ إلا
البابَ. و§21.2 كان يقول «لا مسارَ جديدَ يمنح دوراً» — **وأمرُ المالك فتح هذا البابَ وحدَه**، بشروطه:

- **هويّةٌ واحدة**: الرقمُ والاسمُ والبريد على الصفِّ نفسِه، **ولا يُنشأ حسابٌ ثانٍ ولا يُدمج ولا يُحذف شيء**.
- **يُمنح بعد إثبات الهويّة لا قبله**: الرمزُ لا يصدر إلا بعد كلمة المرور في `POST /auth/login` (والعاملُ الثاني إن كان —
  حسابٌ بعاملٍ ثانٍ لا يُعرض عليه البابُ هنا، فيبقى رفضُه كما كان).
- **ولا يمنح موافقة**: دورُ الكبتن يصير صفَّ `drivers` بحال `pending` — المستنداتُ والمركبةُ وموافقةُ الإدارة بمسارها القائم.
- **ولا مالَ يتحرّك**: لا قيدَ في الدفتر، والمحفظتان منفصلتان بسياق الفعل (`wallet.owner_type_for`)، ومحفظةُ الدور الجديد
  تبدأ صفراً لأنها مجموعُ قيودٍ لا وجودَ لها.

## والرمز
قيمةٌ عشوائيّةٌ في Redis **مربوطةٌ بالحساب والتطبيق الهدف**، عشرُ دقائق، تُستهلك مرّةً (`GETDEL`) — نمطُ `handoff` حرفاً.
"""

from __future__ import annotations

import secrets
import uuid

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_scope import ClientApp
from app.core.exceptions import InvalidToken, PermissionDenied
from app.models.driver import Driver
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.services import audit

TOKEN_TTL_SECONDS = 600
_KEY = "enroll:{token}"

#: **أيُّ دورٍ يضيفه كلُّ تطبيق** — الراكبُ والكبتنُ وحدَهما؛ واللوحةُ لا تُضاف أدوارُها من هنا أبداً
ROLE_FOR_APP: dict[ClientApp, UserRole] = {ClientApp.RIDER: UserRole.RIDER, ClientApp.DRIVER: UserRole.DRIVER}
#: **ومن يحقّ له** — من يملك الدورَ المقابلَ وحدَه: راكبٌ يضيف الكبتن، وكبتنٌ يضيف الراكب
_COUNTERPART: dict[UserRole, UserRole] = {UserRole.RIDER: UserRole.DRIVER, UserRole.DRIVER: UserRole.RIDER}


def can_enroll(user: User, app: ClientApp | None) -> bool:
    """أيُعرض البابُ؟ — تطبيقُ راكبٍ أو كبتن، والحسابُ يملك الدورَ المقابلَ ولا يملك هذا، وليس محظوراً."""
    target = ROLE_FOR_APP.get(app) if app is not None else None
    if target is None or user.has_role(target):
        return False
    if getattr(user, "is_blocked", False):
        return False
    return user.has_role(_COUNTERPART[target])


def require_role_open(user: User, app: ClientApp | None) -> None:
    """**دورُ الراكب المحظورُ وحدَه لا يدخل تطبيقَ الراكب** (الترحيلة `0134`) — وتطبيقُ الكبتن مفتوحٌ له. يُسأل عند الدخول والتبديل."""
    if app is ClientApp.RIDER and user.rider_blocked_at is not None and not user.is_blocked:
        raise PermissionDenied("حسابُ الراكب موقوفٌ — تواصل مع الدعم")


def _key(token: str) -> str:
    return _KEY.format(token=token)


async def issue(redis: Redis, *, user_id: uuid.UUID, app: ClientApp) -> str:
    token = secrets.token_urlsafe(32)
    await redis.set(_key(token), f"{user_id}:{app.value}", ex=TOKEN_TTL_SECONDS)
    return token


async def consume(redis: Redis, *, token: str, app: ClientApp) -> uuid.UUID:
    raw = await redis.getdel(_key(token))
    if raw is None:
        raise InvalidToken("انتهت مهلةُ إضافة الملف — سجّل الدخول مرّةً أخرى")
    value = raw if isinstance(raw, str) else raw.decode()
    owner, _, wanted = value.partition(":")
    if wanted != app.value:
        raise InvalidToken("هذا الرمزُ لا يخصّ هذا التطبيق")
    try:
        return uuid.UUID(owner)
    except ValueError as exc:  # pragma: no cover - قيمةٌ تالفة
        raise InvalidToken() from exc


async def enroll(session: AsyncSession, *, user: User, app: ClientApp) -> User:
    """يضيف دورَ التطبيق إلى الحساب — **صفُّ دورٍ، وصفُّ كبتنٍ `pending` إن كان الكبتن، ولا شيءَ غيرهما**.

    **ولا يكتب `users.role`** (§21: العمودُ جسرٌ يُكتب عند الإنشاء وحدَه، واختبارٌ يمنع غيرَه) — التخويلُ يقرأ المجموعة.
    """
    target = ROLE_FOR_APP.get(app)
    if target is None or not can_enroll(user, app):
        raise PermissionDenied("لا يُضاف هذا الملفُّ إلى هذا الحساب")
    user.role_grants.append(UserRoleGrant(role=target))
    if target is UserRole.DRIVER:
        existing = await session.scalar(select(Driver).where(Driver.user_id == user.id))
        if existing is None:
            session.add(Driver(user_id=user.id))
    await session.flush()
    await audit.record(
        session, actor=user, action=AuditAction.UPDATE, entity_type="user", entity_id=user.id,
        details={"action": "role_added", "role": target.value, "app": app.value,
                 "reason": "أمرُ المالك ٢٠٢٦-١٠-٢٩: الرقمُ نفسُه راكباً وكبتناً (SPEC §21.6)"},
    )
    return user
