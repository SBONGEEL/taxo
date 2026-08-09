from __future__ import annotations

from app.core.config import settings
from app.services.auth.base import AuthMethod, AuthStrategy
from app.services.auth.otp import OtpAuthStrategy
from app.services.auth.password import PasswordAuthStrategy

_password_strategy = PasswordAuthStrategy()
_otp_strategy = OtpAuthStrategy()


def sms_provider_enabled() -> bool:
    """هل يوجد مزود SMS مفعّل؟

    المرحلة 1: تُقرأ من البيئة. المرحلة 2 فصاعداً يصبح المصدر جدول
    `provider_credentials` (صفحة العقود) — نقطة التبديل هذه الدالة وحدها.
    """
    return bool(settings.sms_provider and settings.sms_provider.strip())


def get_auth_strategy() -> AuthStrategy:
    return _otp_strategy if sms_provider_enabled() else _password_strategy


__all__ = [
    "AuthMethod",
    "AuthStrategy",
    "OtpAuthStrategy",
    "PasswordAuthStrategy",
    "get_auth_strategy",
    "sms_provider_enabled",
]
