from __future__ import annotations

from fastapi import APIRouter, status

from app.core import rate_limit
from app.core.config import settings
from app.core.deps import (
    AuthStrategyDep,
    ClientIP,
    CurrentUser,
    DbSession,
    RedisDep,
)
from app.core.exceptions import InvalidInput, InvalidToken, RateLimited
from app.core.phone import InvalidPhoneNumber, resolve_phone
from app.models.user import User
from app.schemas.auth import (
    AuthMethodResponse,
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.services import token_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/method", response_model=AuthMethodResponse)
async def auth_method(strategy: AuthStrategyDep) -> AuthMethodResponse:
    """طريقة الدخول الحالية — تقرأها الواجهة بدل أن تفترضها."""
    return strategy.describe()


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    payload: RegisterRequest,
    session: DbSession,
    redis: RedisDep,
    strategy: AuthStrategyDep,
    ip: ClientIP,
) -> AuthResponse:
    limit = await rate_limit.hit(
        redis, f"register:{ip}", limit=10, window_seconds=3600
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    try:
        user = await strategy.register(session, payload)
    except InvalidPhoneNumber as exc:
        raise InvalidInput(str(exc)) from exc

    await session.commit()
    await session.refresh(user)

    tokens = await token_service.issue_token_pair(redis, user)
    return AuthResponse(user=UserOut.model_validate(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    session: DbSession,
    redis: RedisDep,
    strategy: AuthStrategyDep,
    ip: ClientIP,
) -> AuthResponse:
    try:
        phone = resolve_phone(payload.phone, payload.country_code)
    except InvalidPhoneNumber as exc:
        raise InvalidInput(str(exc)) from exc

    # حدّان: على الرقم (منع تخمين كلمة مرور حساب بعينه) وعلى الـ IP
    for key in (f"login:phone:{phone}", f"login:ip:{ip}"):
        limit = await rate_limit.hit(
            redis,
            key,
            limit=settings.login_rate_limit_attempts,
            window_seconds=settings.login_rate_limit_window_seconds,
        )
        if not limit.allowed:
            raise RateLimited(retry_after=limit.retry_after)

    user = await strategy.authenticate(session, phone, payload.password)

    await rate_limit.reset(redis, f"login:phone:{phone}")
    tokens = await token_service.issue_token_pair(redis, user)
    return AuthResponse(user=UserOut.model_validate(user), tokens=tokens)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest, session: DbSession, redis: RedisDep
) -> TokenPair:
    user_id, _ = await token_service.rotate_refresh_token(redis, payload.refresh_token)

    user = await session.get(User, user_id)
    if user is None or user.is_blocked:
        # حساب محذوف أو محظور: أبطل بقية جلساته أيضاً
        await token_service.revoke_all_for_user(redis, user_id)
        raise InvalidToken()

    return await token_service.issue_token_pair(redis, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, redis: RedisDep) -> None:
    await token_service.revoke_refresh_token(redis, payload.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
