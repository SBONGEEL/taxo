"""نقطة القرار الوحيدة: أيُّ مزود إشعارات يعمل الآن.

نفس دور `card_gateway.get_gateway` و`sms.get_sms_provider`: المصدر عقد
`provider_credentials` المشفّر، وتفعيلُه من صفحة العقود يشغّل الإشعارات بلا
نشر كود (SPEC القسم 15/أ). وغيابُ العقد **ليس خطأ**: قبل FCM يكفي الـ
WebSocket والتطبيق مفتوح — ولذلك `get_push_provider_or_none`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.enums import ProviderKey
from app.services.providers import credentials as credentials_service
from app.services.push.base import (
    PushError,
    PushMessage,
    PushProvider,
    PushResult,
    PushUnavailable,
)
from app.services.push.fcm import FcmPushProvider, parse_service_account
from app.services.push.mock import MockPushProvider, sent_messages

__all__ = [
    "FcmPushProvider",
    "MockPushProvider",
    "PushError",
    "PushMessage",
    "PushProvider",
    "PushResult",
    "PushUnavailable",
    "build_provider",
    "get_push_provider",
    "get_push_provider_or_none",
    "sent_messages",
]


def build_provider(values: Mapping[str, Any]) -> PushProvider:
    if bool(values.get("use_mock")) and not settings.is_production:
        return MockPushProvider(get_redis_client())

    project_id = str(values.get("project_id") or "").strip()
    raw_account = str(values.get("service_account_json") or "").strip()
    if not project_id or not raw_account:
        raise PushUnavailable("عقد FCM ناقص معرّف المشروع أو ملف حساب الخدمة")

    return FcmPushProvider(
        project_id=project_id, service_account=parse_service_account(raw_account)
    )


async def get_push_provider(session: AsyncSession) -> PushProvider:
    """المزود المفعّل أو 503 — لمسارٍ طلب الإرسال صراحةً (زر الاختبار)."""
    values = await credentials_service.get_values(session, ProviderKey.FCM)
    if not values:
        raise PushUnavailable()
    return build_provider(values)


async def get_push_provider_or_none(session: AsyncSession) -> PushProvider | None:
    """المزود إن كان مفعّلاً، وإلا `None` بلا استثناء.

    هذا ما تستدعيه مسارات الإشعار: عقدٌ غير مُدخل حالةٌ طبيعية قبل المرحلة 8
    وبعدها، ولا يجوز أن يُسقط طلبَ رحلةٍ أو يُفشل مهمةَ كنس.
    """
    values = await credentials_service.get_values(session, ProviderKey.FCM)
    if not values:
        return None
    try:
        return build_provider(values)
    except PushUnavailable:
        # عقدٌ مفعّل لكنه ناقص: يُسجَّل ولا يُرفع — الحدث وصل على WebSocket
        return None
