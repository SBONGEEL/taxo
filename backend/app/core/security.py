from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

_BCRYPT_ROUNDS = 12


# ---------------------------------------------------------------- كلمات المرور

def _prehash(password: str) -> bytes:
    """sha256 ثم base64 قبل bcrypt.

    يتجاوز حد bcrypt (72 بايت) الذي تتخطاه كلمات المرور العربية بسهولة،
    ويمنع اقتطاعاً صامتاً للأحرف الزائدة.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(_BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode())
    except ValueError:
        return False


# ------------------------------------------------------------------------ JWT

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    """يُرجع (token, jti, expires_at)."""
    issued_at = _now()
    expires_at = issued_at + expires_delta
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "jti": jti,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.app_name,
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def create_access_token(
    subject: str, extra_claims: dict[str, Any] | None = None
) -> tuple[str, str, datetime]:
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims,
    )


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    return _create_token(
        subject, "refresh", timedelta(days=settings.refresh_token_expire_days)
    )


class TokenError(Exception):
    """توكن غير صالح أو منتهٍ أو من نوع غير متوقع."""


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.app_name,
        )
    except jwt.PyJWTError as exc:  # منتهٍ / توقيع خاطئ / تالف
        raise TokenError(str(exc)) from exc

    if payload.get("typ") != expected_type:
        raise TokenError("unexpected token type")
    if not payload.get("sub") or not payload.get("jti"):
        raise TokenError("malformed token payload")
    return payload
