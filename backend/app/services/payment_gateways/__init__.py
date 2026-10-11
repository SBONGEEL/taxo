"""**الوسطاءُ الآليّون للنظام الجديد** — عقدٌ واحدٌ ومحوِّلٌ لكلِّ وسيط (SPEC §٧٣-هـ/٣ و١٠، والمرحلة ٣).

**وقاعدةُ مزوّد البطاقة القائم حرفاً** (`services/card_gateway/base.py`): **لا تُصدَّق حمولةُ الـwebhook** — هي إشارةُ استيقاظٍ لا مصدرُ
حقيقة. فالـwebhook يعيد **معرّفاتٍ** بعد التحقّق من توقيعه حيث يوثّقه الوسيط، **والحقيقةُ جوابُ `check`** من الوسيط إلى الخلفية مباشرة،
ويُسأل **قبل** أيِّ قفل (لا قفلَ صفٍّ عبر نداء شبكةٍ يمكن أن يسبقه — `CLAUDE.md`).

**والعقودُ في `provider_credentials`** (صفحةُ العقود، لكلِّ دولة) — لا في `.env` ولا في الشيفرة. **والوهميُّ ممنوعٌ في الإنتاج.**
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import get_cipher
from app.core.exceptions import AppError
from app.models.enums import CountryCode, PaymentRequestStatus, ProviderKey
from app.models.provider_credential import ProviderCredential
from app.services.providers import credentials as credentials_service

REQUEST_TIMEOUT_SECONDS = 20.0

#: **مَنفذُ نقلٍ للاختبار وحدَه** — `httpx.MockTransport` يُركَّب هنا فيُسأل الوسيطُ بلا شبكة؛ وفي التشغيل `None` (الشبكةُ الحقيقيّة)
http_transport: httpx.AsyncBaseTransport | None = None


class WebhookSignatureInvalid(AppError):
    """**توقيعٌ لا يطابق** — لا يُقرأ من الجسم حرفٌ بعده، ولا يُقال لماذا (`401`)."""

    status_code = 401
    code = "webhook_signature_invalid"
    message = "توقيعٌ غيرُ صالح"


class GatewayUnavailable(AppError):
    """**لا عقدَ مفعَّلٌ لهذا الوسيط في هذا السوق** — الميزةُ مبنيّةٌ والعقدُ غائب (`503`)، كـ`CardGatewayUnavailable`."""

    status_code = 503
    code = "payment_gateway_unavailable"
    message = "الدفعُ بهذه الطريقة غيرُ متاحٍ الآن — اختر طريقةً أخرى."


class GatewayError(AppError):
    """**الوسيطُ ردّ بخطأ أو تعذّر الوصولُ إليه أو جاء جوابُه بشكلٍ لا يُقرأ** (`502`)."""

    status_code = 502
    code = "payment_gateway_error"
    message = "تعذّر إتمامُ العملية عند وسيط الدفع"


@dataclass(frozen=True, slots=True)
class GatewayEvent:
    """**ما قاله الوسيطُ عن دفعةٍ** — من جوابه المباشر لا من حمولة إشعار، وبلغة النظام لا بلغته."""

    external_id: str
    outcome: PaymentRequestStatus
    #: ما وصل بعملة الطلب كما يقوله الوسيط — `None` حين لا يذكره
    amount: Decimal | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Checkout:
    external_id: str
    checkout_url: str


@dataclass(frozen=True, slots=True)
class CheckoutCustomer:
    """ما يطلبه وسيطٌ عن الدافع (SofizPay يشترطه) — **ولا نرسل غيرَه**."""

    full_name: str
    phone: str
    email: str | None


class Gateway(Protocol):
    name: str

    async def checkout(
        self,
        *,
        amount: Decimal,
        description: str,
        return_url: str,
        webhook_url: str,
        fee_bearer: str,
        customer: CheckoutCustomer,
    ) -> Checkout: ...

    async def check(self, external_id: str) -> GatewayEvent | None:
        """**الحالُ من الوسيط مباشرةً** — `None` ما دامت معلّقة."""
        ...

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        """**معرّفاتُ ما يُسأل عنه** بعد التحقّق من التوقيع حيث يوثّقه الوسيط — `WebhookSignatureInvalid` إن لم يطابق."""
        ...

    async def test_connection(self) -> str: ...


def _builders() -> dict[str, Callable[[Mapping[str, Any]], Gateway]]:
    from app.services.payment_gateways.chargily import build_chargily
    from app.services.payment_gateways.sofizpay import build_sofizpay

    return {"chargily": build_chargily, "sofizpay": build_sofizpay}


#: **اسمُ المحوِّل ⇐ عقدُه في صفحة العقود** — والوسيطُ في صفِّ الطريقة يُعرف بهذا الاسم (`integration`)
PROVIDER_KEYS: dict[str, ProviderKey] = {"chargily": ProviderKey.CHARGILY, "sofizpay": ProviderKey.SOFIZPAY}

#: **من يحمل رسومَ الوسيط** — ما يقبله كلُّ وسيطٍ بوثائقه؛ وSofizPay لا يوثّق تحميلَها على المشتري فيبقى على TAXO
FEE_BEARERS: dict[str, frozenset[str]] = {
    "chargily": frozenset({"taxo", "user", "split"}),
    "sofizpay": frozenset({"taxo"}),
}


def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, transport=http_transport)


def build(integration: str, values: Mapping[str, Any]) -> Gateway:
    builder = _builders().get(integration)
    if builder is None:
        raise GatewayUnavailable()
    if credentials_service.is_mock(values):
        if settings.is_production:
            # **الوهميُّ ممنوعٌ في الإنتاج** — وسيطٌ يقول «دُفع» بلا مال بابٌ لا يُترك مفتوحاً حيث مالٌ حقيقيّ
            raise GatewayUnavailable()
        from app.services.payment_gateways.mock import MockGateway

        return MockGateway(integration)
    return builder(values)


async def gateway_for(session: AsyncSession, integration: str, country: CountryCode) -> Gateway:
    """**الوسيطُ بعقده المفعَّل في السوق** — أو `503` باسمه."""
    key = PROVIDER_KEYS.get(integration)
    if key is None:
        raise GatewayUnavailable()
    values = await credentials_service.get_values(session, key, country)
    if values is None:
        raise GatewayUnavailable()
    return build(integration, values)


async def webhook_gateways(session: AsyncSession, integration: str) -> list[Gateway]:
    """**كلُّ عقدٍ مفعَّلٍ لهذا الوسيط في أيِّ سوق** — الإشعارُ لا يقول سوقَه، فيُجرَّب توقيعُه على كلِّ عقد."""
    key = PROVIDER_KEYS.get(integration)
    if key is None:
        return []
    rows = (
        await session.scalars(
            select(ProviderCredential).where(
                ProviderCredential.provider_key == key, ProviderCredential.is_active.is_(True)
            )
        )
    ).all()
    cipher = get_cipher()
    return [build(integration, credentials_service.normalize_toggles(cipher.decrypt(row.credentials))) for row in rows]


def webhook_url(integration: str) -> str:
    return f"{settings.public_api_base_url}{settings.api_v1_prefix}/payment-requests/webhook/{integration}"


def return_url(request_id: str, *, opened_from: str) -> str:
    """**صفحةُ العودة في التطبيق** — من عنوانَي عودة البطاقة القائمين (بنيةٌ تحتيّةٌ لا سرّ)، بالمسار الجديد. والتطبيقُ يقرأ المعرّفَ
    ويسأل الخلفيةَ عن الحال — ولا يُصدَّق في شيءٍ آخر."""
    from urllib.parse import urlsplit, urlunsplit

    base = settings.card_return_url_driver if opened_from == "driver" else settings.card_return_url
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/wallet/pay/return", f"r={request_id}", ""))
