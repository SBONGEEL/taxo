from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.enums import ProviderKey
from app.services.auth.base import AuthMethod, AuthStrategy
from app.services.auth.otp import OtpAuthStrategy
from app.services.auth.password import PasswordAuthStrategy

_password_strategy = PasswordAuthStrategy()
_otp_strategy = OtpAuthStrategy()


async def sms_provider_enabled(session: AsyncSession) -> bool:
    """هل يوجد مزود SMS مفعّل؟

    المصدر جدول `provider_credentials` (صفحة العقود) — إدخال عقد SMS وتفعيله
    يحوّل الدخول إلى OTP بلا نشر كود ولا تعديل أي endpoint. هذه الدالة هي
    نقطة القرار الوحيدة.
    """
    from app.services.providers.credentials import provider_is_active

    return await provider_is_active(session, ProviderKey.SMS)


async def get_auth_strategy(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthStrategy:
    return _otp_strategy if await sms_provider_enabled(session) else _password_strategy


__all__ = [
    "AuthMethod",
    "AuthStrategy",
    "OtpAuthStrategy",
    "PasswordAuthStrategy",
    "get_auth_strategy",
    "sms_provider_enabled",
]
