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

#: **سماحُ الساعة عند فكّ الرمز** (قِيس ٢٠٢٦-١٠-٠٧): PyJWT 2.15 يرفض رمزاً `iat`ه بعد «الآن» **بلا سماح**، و`iat` يُقطع إلى
#: الثانية — **فخطوةُ ساعةٍ إلى الوراء** بعد سكّه تجعل الرمزَ الطازجَ «لم يصلح بعد» فيُردّ الطلبُ التالي ٤٠١ ويخرج صاحبُه.
#: **وقِيست الخطوةُ في حاوية التطوير**: أربعٌ في دقيقة، أكبرُها ٠٫٤٣٥ ث — وهي ٤٠١ «كبتنان معاً» و«السقف عند نشوء الدَّين» العابرتان.
#: **خمسُ ثوانٍ** تسعها وتسع انزياحَ ساعةٍ بين حاويتين، **ولا تُطيل عمرَ رمز الوصول (ثلاثون دقيقة) إلا بها**
_CLOCK_LEEWAY = timedelta(seconds=5)


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
    expires_delta: timedelta | None,
    extra_claims: dict[str, Any] | None = None,
    *,
    jti: str | None = None,
    issued_at: datetime | None = None,
) -> tuple[str, str, datetime | None]:
    """يُرجع (token, jti, expires_at) — و`expires_at` لا وجودَ له بلا عمر."""
    issued_at = issued_at or _now()
    jti = jti or str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "jti": jti,
        "iat": int(issued_at.timestamp()),
        "iss": settings.app_name,
    }
    expires_at = None
    if expires_delta is not None:
        expires_at = issued_at + expires_delta
        payload["exp"] = int(expires_at.timestamp())
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def create_access_token(
    subject: str, extra_claims: dict[str, Any] | None = None
) -> tuple[str, str, datetime]:
    token, jti, expires_at = _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims,
    )
    assert expires_at is not None  # توكنُ الوصول قصيرُ العمر دائماً
    return token, jti, expires_at


def create_refresh_token(
    subject: str,
    *,
    sid: str | None = None,
    jti: str | None = None,
    issued_at: datetime | None = None,
) -> tuple[str, str, datetime | None]:
    """رمزُ التجديد — **بلا تاريخ انتهاء** (SPEC §60، قرارُ المالك ٢٠٢٦-١٠-٠٤).

    **صلاحيتُه صفٌّ حيٌّ في `auth_sessions` ورمزٌ يطابقه**، لا ساعة: الدخولُ يبقى
    حتى يخرج صاحبُه. و`sid` مُعرِّفُ الجلسة، و`jti`/`issued_at` يُمرَّران حين يُعاد
    سكُّ الرمز الحاليِّ **حرفاً** في مهلة السماح (`token_service.rotate`) — فالتوقيعُ
    حتميٌّ ما دامت الحمولةُ هي هي.
    """
    claims = {"sid": sid} if sid else None
    return _create_token(
        subject, "refresh", None, claims, jti=jti, issued_at=issued_at
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
            leeway=_CLOCK_LEEWAY,
        )
    except jwt.PyJWTError as exc:  # منتهٍ / توقيع خاطئ / تالف
        raise TokenError(str(exc)) from exc

    if payload.get("typ") != expected_type:
        raise TokenError("unexpected token type")
    if not payload.get("sub") or not payload.get("jti"):
        raise TokenError("malformed token payload")
    return payload
