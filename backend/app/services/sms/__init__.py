"""نقطة القرار الوحيدة: أيُّ مزود رسائل يعمل الآن.

نفس دور `card_gateway.get_gateway` و`auth.get_auth_strategy`: المصدر عقدُ
`provider_credentials` المشفّر لا `.env`، وتفعيلُ العقد من صفحة العقود يحوّل
الدخول كله إلى OTP بلا تعديل endpoint (SPEC القسم 15/أ).

**المزود الوهمي ممنوع في الإنتاج**: رمزٌ «يُرسل» إلى Redis يقرؤه من يبلغ
Redis لا من يملك الهاتف، وذاك دخولٌ بلا هوية.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.enums import ProviderKey
from app.services.providers import credentials as credentials_service
from app.services.sms.base import (
    REQUEST_TIMEOUT_SECONDS,
    SmsError,
    SmsProvider,
    SmsUnavailable,
)
from app.services.sms.http_sms import HttpSmsProvider
from app.services.sms.mock import MockSmsProvider, last_message

__all__ = [
    "REQUEST_TIMEOUT_SECONDS",
    "HttpSmsProvider",
    "MockSmsProvider",
    "SmsError",
    "SmsProvider",
    "SmsUnavailable",
    "build_provider",
    "get_sms_provider",
    "last_message",
]


def build_provider(values: Mapping[str, Any]) -> SmsProvider:
    """يبني المزود من قيم عقدٍ مفكوك التشفير — يُستدعى من هنا ومن زر الاختبار."""
    if bool(values.get("use_mock")) and not settings.is_production:
        return MockSmsProvider(get_redis_client())

    endpoint = str(values.get("endpoint") or "").strip()
    api_key = str(values.get("api_key") or "").strip()
    if not endpoint or not api_key:
        raise SmsUnavailable("عقد مزود الرسائل ناقص العنوان أو المفتاح")

    return HttpSmsProvider(
        provider_name=str(values.get("provider_name") or "sms"),
        endpoint=endpoint,
        api_key=api_key,
        sender_id=str(values.get("sender_id") or "TAXO"),
    )


async def get_sms_provider(session: AsyncSession) -> SmsProvider:
    """مزود الرسائل المفعّل، أو 503 إن لم يُدخل عقده.

    العقد عام لا per-country: رقمُ الهاتف يحمل دولته، والمرسِل واحد.
    """
    values = await credentials_service.get_values(session, ProviderKey.SMS)
    if not values:
        raise SmsUnavailable()
    return build_provider(values)
