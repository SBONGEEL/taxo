"""نقطة القرار الوحيدة: هل قناةُ واتساب متاحة الآن، وبأي عقد.

نفس دور `sms.get_sms_provider` و`card_gateway.get_gateway`: المصدر عقدُ
`provider_credentials` المشفّر لا `.env`، وإدخالُ العقد من صفحة العقود يفتح
القناة بلا تعديل endpoint (SPEC القسم 15/أ).

**والعقدُ عامٌّ والمفتاحُ per-country**، وهذا التقسيم مقصود: رقمُ الأعمال الواحد
عند ميتا يخدم السوقين (ورقمُ المستخدم يحمل دولته)، أما **إشعالُ القناة فقرارُ
سوق** — تُجرَّب في الأردن قبل ليبيا، أو تُطفأ في سوقٍ لم يُعتمد قالبُه بلغته.
ولذلك `feature_key` في سجل المزودين **غائبٌ عمداً**: المزامنةُ التلقائية تُشعل
مفتاحَ دولة العقد عند تفعيله، وهنا العقدُ لا دولةَ له — والمفتاحُ يجب أن يبقى
بيد المشرف كما طلب المالك، مطفأً حتى يُشعله بضغطة زر.

**والمزود الوهمي ممنوع في الإنتاج**: رمزٌ «يُرسل» إلى Redis يقرأه من يبلغ Redis
لا من يملك الهاتف.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.enums import ProviderKey
from app.services.providers import credentials as credentials_service
from app.services.whatsapp.base import (
    REQUEST_TIMEOUT_SECONDS,
    WhatsAppError,
    WhatsAppOtpProvider,
    WhatsAppUnavailable,
)
from app.services.whatsapp.cloud_api import WhatsAppCloudProvider
from app.services.whatsapp.mock import MockWhatsAppProvider, last_message

__all__ = [
    "REQUEST_TIMEOUT_SECONDS",
    "MockWhatsAppProvider",
    "WhatsAppCloudProvider",
    "WhatsAppError",
    "WhatsAppOtpProvider",
    "WhatsAppUnavailable",
    "build_provider",
    "get_provider_or_none",
    "get_whatsapp_provider",
    "last_message",
]


def build_provider(values: Mapping[str, Any]) -> WhatsAppOtpProvider:
    """يبني المزود من قيم عقدٍ مفكوك التشفير — من هنا ومن زر الاختبار."""
    if credentials_service.is_mock(values) and not settings.is_production:
        return MockWhatsAppProvider(get_redis_client())

    phone_number_id = str(values.get("phone_number_id") or "").strip()
    access_token = str(values.get("access_token") or "").strip()
    template_name = str(values.get("template_name") or "").strip()
    if not phone_number_id or not access_token or not template_name:
        raise WhatsAppUnavailable(
            "عقد واتساب ناقص: يلزم Phone Number ID وToken واسم القالب"
        )

    return WhatsAppCloudProvider(
        phone_number_id=phone_number_id,
        access_token=access_token,
        template_name=template_name,
        template_language=str(values.get("template_language") or "ar").strip() or "ar",
        waba_id=str(values.get("waba_id") or "").strip(),
    )


async def get_whatsapp_provider(session: AsyncSession) -> WhatsAppOtpProvider:
    """مزود واتساب المفعّل، أو 503 إن لم يُدخل عقده."""
    values = await credentials_service.get_values(session, ProviderKey.WHATSAPP)
    if not values:
        raise WhatsAppUnavailable()
    return build_provider(values)


async def get_provider_or_none(session: AsyncSession) -> WhatsAppOtpProvider | None:
    """المزود إن كان عقدُه مفعّلاً وسليماً، وإلا `None`.

    **`None` هي الحالة الطبيعية لا عطل** — كما في `push` و`cliq`: غيابُ عقد
    واتساب يعني أن القناة غير مفتوحة، ومسارُ التحقق ينتقل إلى التالية بلا أن
    يفشل الطلبُ الذي استدعاه. والعقدُ الناقص يُقرأ كغائب هنا لنفس السبب: لا
    يُوقِف تسجيلَ المستخدمين عقدٌ نصفُ مُدخل — ومكانُ الشكوى منه زرُّ الاختبار
    في صفحة العقود، حيث السؤالُ مطروحٌ فعلاً.
    """
    values = await credentials_service.get_values(session, ProviderKey.WHATSAPP)
    if not values:
        return None
    try:
        return build_provider(values)
    except WhatsAppUnavailable:
        return None
