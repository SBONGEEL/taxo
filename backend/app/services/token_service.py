from __future__ import annotations

import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis

from app.core.exceptions import InvalidToken
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.auth import TokenPair

_REFRESH_PREFIX = "auth:refresh"


def _refresh_key(user_id: uuid.UUID | str, jti: str) -> str:
    return f"{_REFRESH_PREFIX}:{user_id}:{jti}"


async def issue_token_pair(redis: Redis, user: User) -> TokenPair:
    """يصدر access + refresh ويسجّل الـ refresh في Redis (قابل للإبطال)."""
    subject = str(user.id)
    access_token, _, access_expires = create_access_token(
        subject, {"role": user.role.value, "country": user.country_code.value}
    )
    refresh_token, refresh_jti, refresh_expires = create_refresh_token(subject)

    ttl = int((refresh_expires - datetime.now(timezone.utc)).total_seconds())
    await redis.set(_refresh_key(subject, refresh_jti), "1", ex=max(ttl, 1))

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=access_expires,
    )


async def rotate_refresh_token(redis: Redis, refresh_token: str) -> tuple[uuid.UUID, str]:
    """يتحقق من refresh token ويستهلكه (تدوير لمرة واحدة).

    يُرجع (user_id, jti المستهلَك). إعادة استخدام توكن مستهلَك ترفض.
    """
    try:
        payload = decode_token(refresh_token, "refresh")
    except TokenError as exc:
        raise InvalidToken() from exc

    subject = payload["sub"]
    jti = payload["jti"]

    deleted = await redis.delete(_refresh_key(subject, jti))
    if not deleted:
        raise InvalidToken("جلسة منتهية أو أُبطلت مسبقاً")

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise InvalidToken() from exc
    return user_id, jti


async def revoke_refresh_token(redis: Redis, refresh_token: str) -> None:
    """تسجيل الخروج: إبطال refresh token الخاص بهذا الجهاز فقط."""
    try:
        payload = decode_token(refresh_token, "refresh")
    except TokenError:
        return  # الخروج عملية idempotent — توكن تالف يُعامل كأنه أُبطل
    await redis.delete(_refresh_key(payload["sub"], payload["jti"]))


async def revoke_all_for_user(redis: Redis, user_id: uuid.UUID | str) -> int:
    """إبطال كل جلسات المستخدم (حظر حساب / تغيير كلمة مرور)."""
    pattern = f"{_REFRESH_PREFIX}:{user_id}:*"
    removed = 0
    async for key in redis.scan_iter(match=pattern, count=100):
        removed += await redis.delete(key)
    return removed


def access_token_subject(token: str) -> uuid.UUID:
    try:
        payload = decode_token(token, "access")
        return uuid.UUID(payload["sub"])
    except (TokenError, ValueError) as exc:
        raise InvalidToken() from exc


__all__ = [
    "access_token_subject",
    "issue_token_pair",
    "revoke_all_for_user",
    "revoke_refresh_token",
    "rotate_refresh_token",
]
