"""نقطة القرار الوحيدة: أيُّ مزود بطاقات يخدم هذه الدولة الآن.

نفس دور `services/auth/get_auth_strategy` بالضبط: الراوترات والخدمات لا تعرف
Telr من غيره، وتبديلُ المزود أو تشغيلُ الوهمي **إدخالُ عقدٍ من صفحة العقود لا
تعديلُ endpoint** (SPEC القسم 15). ومصدر المفاتيح `provider_credentials`
مشفّرةً — لا `.env` ولا كود (القسم 14).

**المزود الوهمي ممنوع في الإنتاج.** رفعُ `use_mock` هناك يعني مزوداً يقول
«دُفع» بلا أن يدفع أحد؛ فيُتجاهل الحقل ويُستعمل المزود الحقيقي، أو لا مزود.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import get_cipher
from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode, ProviderKey
from app.models.provider_credential import ProviderCredential
from app.services.card_gateway.base import (
    CardDetails,
    CardGateway,
    CardGatewayError,
    CardGatewayUnavailable,
    HostedPage,
    InvalidWebhookSignature,
    OrderRequest,
    OrderState,
    WebhookNotice,
)
from app.services.card_gateway.mock import MockCardGateway
from app.services.card_gateway.telr import TelrGateway
from app.services.providers import credentials as credentials_service

__all__ = [
    "CardDetails",
    "CardGateway",
    "CardGatewayError",
    "CardGatewayUnavailable",
    "HostedPage",
    "InvalidWebhookSignature",
    "MockCardGateway",
    "OrderRequest",
    "OrderState",
    "TelrGateway",
    "WebhookNotice",
    "build_gateway",
    "get_gateway",
    "mock_page_url",
    "resolve_webhook",
    "return_url_for",
]


def _mock_allowed(values: Mapping[str, Any]) -> bool:
    return bool(values.get("use_mock")) and not settings.is_production


def return_url_for(cart_id: str) -> str:
    """الصفحة التي يعود إليها المتصفح من صفحة المزود.

    عنوانُ واجهةٍ لا سرُّ مزود، فمكانه إعدادات البنية التحتية. الواجهة تقرأ
    `cart_id` منه وتسأل الخلفية عن الحال — ولا تُصدَّق في شيء آخر.
    """
    return f"{settings.card_return_url}?cart_id={cart_id}"


def mock_page_url(cart_id: str) -> str:
    """«صفحة الدفع» الوهمية: مسارٌ في هذه الخلفية نفسها، بلا شبكة خارجية."""
    return (
        f"{settings.public_api_base_url}{settings.api_v1_prefix}"
        f"/payments/card/mock/{cart_id}"
    )


def build_gateway(values: Mapping[str, Any]) -> CardGateway:
    """يبني المزود من قيم عقدٍ مفكوك التشفير — يُستدعى من هنا ومن زر الاختبار."""
    if _mock_allowed(values):
        return MockCardGateway(
            get_redis_client(), return_url_template=mock_page_url("{cart_id}")
        )
    store_id = str(values.get("store_id") or "").strip()
    auth_key = str(values.get("auth_key") or "").strip()
    if not store_id or not auth_key:
        raise CardGatewayUnavailable()
    return TelrGateway(
        store_id=store_id,
        auth_key=auth_key,
        test_mode=bool(values.get("test_mode")),
    )


async def get_gateway(
    session: AsyncSession, country_code: CountryCode
) -> CardGateway:
    """مزود بطاقات هذه الدولة، أو 503 إن لم يُدخل عقده ويُفعَّل."""
    values = await credentials_service.get_values(
        session, ProviderKey.TELR, country_code
    )
    if not values:
        raise CardGatewayUnavailable()
    return build_gateway(values)


async def resolve_webhook(
    session: AsyncSession, payload: Mapping[str, str]
) -> tuple[CardGateway, WebhookNotice]:
    """يجد العقد الذي يخصّه هذا الإشعار ثم يتحقق من توقيعه.

    الـ webhook لا يحمل دولة، فالمطابقة على **مُعرّف المتجر** في حمولته: هو ما
    يميّز عقد الأردن من غيره. عقدٌ لا يُطابقه مُعرّفٌ يعني إشعاراً لا نعرف
    مصدره — يُرفض ولا يُبحث له عن عقدٍ آخر يقبله.
    """
    store_id = str(payload.get("tran_store", "") or "").strip()
    if not store_id:
        raise InvalidWebhookSignature("إشعار الدفع بلا مُعرّف متجر")

    rows = (
        await session.scalars(
            select(ProviderCredential).where(
                ProviderCredential.provider_key == ProviderKey.TELR,
                ProviderCredential.is_active.is_(True),
            )
        )
    ).all()

    for row in rows:
        values = get_cipher().decrypt(row.credentials)
        if str(values.get("store_id") or "").strip() != store_id:
            continue
        gateway = build_gateway(values)
        # التحقق يرفع الاستثناء بنفسه — لا يُصمت ولا يُجرَّب عقدٌ بعده
        return gateway, gateway.verify_webhook(payload)

    raise InvalidWebhookSignature("لا عقد مفعّل لهذا المتجر")
