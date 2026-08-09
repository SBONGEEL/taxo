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
from app.services.auth import AuthStrategy, get_auth_strategy
from app.services.token_service import access_token_subject

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_redis() -> Redis:
    return get_redis_client()


RedisDep = Annotated[Redis, Depends(get_redis)]
AuthStrategyDep = Annotated[AuthStrategy, Depends(get_auth_strategy)]


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


def require_roles(*roles: UserRole):
    """يقيّد endpoint على أدوار محددة."""

    async def _dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDenied()
        return user

    return _dependency


# admin كامل الصلاحية؛ support قراءة ومعالجة نزاعات فقط (SPEC القسم 13/8)
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPPORT))]
RiderUser = Annotated[User, Depends(require_roles(UserRole.RIDER))]


async def get_current_driver(
    session: DbSession,
    user: Annotated[User, Depends(require_roles(UserRole.DRIVER))],
) -> Driver:
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        raise NotFound("ملف الكبتن غير موجود")
    return driver


CurrentDriver = Annotated[Driver, Depends(get_current_driver)]
