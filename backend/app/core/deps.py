from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.exceptions import AccountBlocked, InvalidToken, NotFound, PermissionDenied
from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.enums import UserRole
from app.models.user import User
from app.services.token_service import access_token_subject

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_redis() -> Redis:
    return get_redis_client()


RedisDep = Annotated[Redis, Depends(get_redis)]


def client_ip(request: Request) -> str:
    """أول IP في X-Forwarded-For إن وُجد وسيط، وإلا عنوان الاتصال المباشر."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


ClientIP = Annotated[str, Depends(client_ip)]


async def get_current_user(
    session: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise InvalidToken("مطلوب توكن دخول")

    user_id = access_token_subject(credentials.credentials)
    user = await session.get(User, user_id)
    if user is None:
        raise InvalidToken()
    if user.is_blocked:
        raise AccountBlocked()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole, enforce_two_factor: bool = True):
    """يقيّد endpoint على أدوار محددة — ومعه حارسُ التحقق الثنائي.

    `enforce_two_factor=False` لبابِ تسجيل العامل وحده (القسم 14.1): الحارسُ
    يردّ المشرفَ المُلزَمَ بلا عامل، فلو حرس بابَ التسجيل أيضاً صار الإلزامُ
    حلقةً مغلقة — «سجّل عاملاً» على بابٍ لا يُفتح قبل تسجيل عامل. والاستثناءُ
    وسيطٌ صريحٌ هنا لا مطابقةُ مسارٍ بالنصّ: مسارٌ يُطابَق باسمه يُنسى عند أول
    إعادة تسمية، والوسيطُ يظهر في تعريف الـendpoint نفسه.

    والحارسُ **لا يُستعلم عنه إلا لطاقم اللوحة**: مسارُ راكبٍ لا يدفع استعلاماً
    عن سياسةٍ لا تخصّه. وفي الحالة الغالبة (المفتاح مطفأ) هو استعلامٌ واحدٌ عن
    صفٍّ واحد، ولا يُسأل عن العامل أصلاً.
    """

    async def _dependency(user: CurrentUser, session: DbSession) -> User:
        # **«يملك الدور» لا «دورُه هو»** (نموذجُ الأدوار، 2026-08-19). والقراءةُ
        # تبقى من قاعدة البيانات في كل طلب — لا من مطالبةٍ في التوكن: مطالبةٌ
        # تُوقّع مرةً تبقى صادقةً بعد سحب الدور حتى تنتهي صلاحيتُها.
        if not user.has_role(*roles):
            raise PermissionDenied()
        if enforce_two_factor and user.has_role(*_STAFF_ROLES):
            from app.services import security_settings

            await security_settings.ensure_factor_ready(session, user)
        return user

    return _dependency


_STAFF_ROLES = frozenset({UserRole.ADMIN, UserRole.SUPPORT})

# admin كامل الصلاحية؛ support قراءة ومعالجة نزاعات فقط (SPEC القسم 13/8)
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPPORT))]
RiderUser = Annotated[User, Depends(require_roles(UserRole.RIDER))]

# بابُ «أمان حسابي» وحده — يفتح لطاقم اللوحة قبل أن يكون لهم عاملٌ مسجّل
SecuritySelfUser = Annotated[
    User,
    Depends(
        require_roles(UserRole.ADMIN, UserRole.SUPPORT, enforce_two_factor=False)
    ),
]


async def get_current_driver(
    session: DbSession,
    user: Annotated[User, Depends(require_roles(UserRole.DRIVER))],
) -> Driver:
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        raise NotFound("ملف الكبتن غير موجود")
    return driver


CurrentDriver = Annotated[Driver, Depends(get_current_driver)]
