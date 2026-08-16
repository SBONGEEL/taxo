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
from app.services.whatsapp.baileys import (
    DEFAULT_HOURLY,
    DEFAULT_PER_PHONE_HOURLY,
    BaileysGatewayProvider,
)
from app.services.whatsapp.cloud_api import WhatsAppCloudProvider
from app.services.whatsapp.mock import MockWhatsAppProvider, last_message

# قيمتا حقل `transport` في العقد — والغيابُ يُقرأ `cloud` (ما كان قبل الحقل)
TRANSPORT_CLOUD = "cloud"
TRANSPORT_BAILEYS = "baileys"

__all__ = [
    "DEFAULT_HOURLY",
    "DEFAULT_PER_PHONE_HOURLY",
    "REQUEST_TIMEOUT_SECONDS",
    "TRANSPORT_BAILEYS",
    "TRANSPORT_CLOUD",
    "BaileysGatewayProvider",
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


def _int_or(values: Mapping[str, Any], key: str, fallback: int) -> int:
    """رقمٌ من حقل عقد — والفارغُ يعني «الافتراضي» لا صفراً.

    وصفرٌ **مكتوبٌ صراحةً** يعني «لا سقف»: حالتان لا يجوز أن يحملهما حقلٌ
    فارغ (درسُ أصفار `wallet_settings`).
    """
    raw = str(values.get(key) or "").strip()
    if not raw:
        return fallback
    try:
        return max(0, int(raw))
    except ValueError:
        return fallback


def _build_baileys(values: Mapping[str, Any]) -> WhatsAppOtpProvider:
    """القناةُ الذاتية — بوابةٌ داخليةٌ لا تُرى من خارج شبكة المشروع."""
    base_url = str(values.get("gateway_url") or "").strip()
    gateway_key = str(values.get("gateway_key") or "").strip()
    if not base_url or not gateway_key:
        raise WhatsAppUnavailable(
            "عقد واتساب الذاتي ناقص: يلزم عنوان البوابة ومفتاحُها"
        )
    return BaileysGatewayProvider(
        base_url=base_url,
        gateway_key=gateway_key,
        redis=get_redis_client(),
        per_phone_hourly=_int_or(values, "per_phone_hourly", DEFAULT_PER_PHONE_HOURLY),
        hourly=_int_or(values, "hourly_limit", DEFAULT_HOURLY),
    )


def build_provider(values: Mapping[str, Any]) -> WhatsAppOtpProvider:
    """يبني المزود من قيم عقدٍ مفكوك التشفير — من هنا ومن زر الاختبار.

    **وحقلُ `transport` هو كلُّ الفرق بين القناتين** (قرارُ المالك 2026-08-16):
    الرسميةُ (`cloud`) والذاتيةُ (`baileys`) خلف الواجهة نفسِها، والتبديلُ
    بينهما **حقلٌ يُعدَّل في صفحة العقود بلا كودٍ جديد ولا نشر**.

    **وغيابُه يُقرأ `cloud`**: هو ما كان يعمل قبل هذا الحقل، فعقدٌ قائمٌ لا
    يتبدّل سلوكُه بترقية. وهي قاعدةُ «الغيابُ يعني ما كان» — لا «يعني الأحدث».

    **ومفتاحان لا يجتمعان**: مزوّدان مفعّلان معاً كانا سيفتحان سؤالَ «أيُّهما
    أولاً»، وهو سؤالٌ يُجاب بحالةٍ ثانيةٍ يمكن أن تخالف العقود — فالعقدُ واحدٌ
    وحقلٌ فيه يقول أيَّ سلكٍ يمشي عليه.
    """
    if credentials_service.is_mock(values) and not settings.is_production:
        return MockWhatsAppProvider(get_redis_client())

    if str(values.get("transport") or TRANSPORT_CLOUD).strip() == TRANSPORT_BAILEYS:
        return _build_baileys(values)

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
