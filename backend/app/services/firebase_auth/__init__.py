"""نقطة القرار الوحيدة: هل التحقق من الهاتف يمر بـ Firebase، ومن يخدمه.

نفس دور `sms.get_sms_provider` و`push.get_push_provider`: المصدر عقد
`provider_credentials` مشفَّراً، وتفعيلُه من صفحة العقود يحوّل الدخول بلا نشر
كود (SPEC القسم 15/أ).

و`firebase_auth_enabled` هي ما تقرؤه `services/auth.get_auth_strategy` —
الحلقةُ الأولى في قرارٍ ثلاثي: Firebase، ثم مزود SMS التقليدي، ثم كلمة المرور.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import ProviderKey
from app.services.firebase_auth.base import (
    FirebaseAuthUnavailable,
    IdTokenVerifier,
    InvalidIdToken,
    VerifiedIdentity,
)
from app.services.firebase_auth.google_certs import FirebaseIdTokenVerifier
from app.services.firebase_auth.mock import MockIdTokenVerifier, mock_token
from app.services.providers import credentials as credentials_service

__all__ = [
    "FirebaseAuthUnavailable",
    "FirebaseIdTokenVerifier",
    "IdTokenVerifier",
    "InvalidIdToken",
    "MockIdTokenVerifier",
    "VerifiedIdentity",
    "build_verifier",
    "firebase_auth_enabled",
    "get_verifier",
    "mock_token",
]


def build_verifier(values: Mapping[str, Any]) -> IdTokenVerifier:
    project_id = str(values.get("project_id") or "").strip()
    if not project_id:
        raise FirebaseAuthUnavailable("عقد Firebase بلا معرّف مشروع")

    if bool(values.get("use_mock")) and not settings.is_production:
        return MockIdTokenVerifier(project_id=project_id)
    return FirebaseIdTokenVerifier(project_id=project_id)


async def get_verifier(session: AsyncSession) -> IdTokenVerifier:
    """مُحقِّق العقد المفعّل، أو 503 إن لم يُدخل.

    العقد عام لا per-country: مشروع Firebase واحد للسوقين، والرقم يحمل دولته.
    """
    values = await credentials_service.get_values(session, ProviderKey.FIREBASE_AUTH)
    if not values:
        raise FirebaseAuthUnavailable()
    return build_verifier(values)


async def firebase_auth_enabled(session: AsyncSession) -> bool:
    """هل يوجد عقد Firebase مفعّل **وكامل**؟

    الاكتمال شرطٌ في القرار لا في الاستعمال: عقدٌ مفعّل بلا `project_id`
    يُسقط الدخول كله إلى 503 لو اختير — فيُتخطّى إلى المزود التالي بدل أن
    يُغلق الباب على الجميع.
    """
    values = await credentials_service.get_values(session, ProviderKey.FIREBASE_AUTH)
    return bool(values and str(values.get("project_id") or "").strip())
