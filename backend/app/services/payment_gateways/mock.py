"""**وسيطٌ وهميٌّ بلا شبكةٍ ولا حساب** (SPEC القسم 15/أ) — يُشغّل مسارَ الدفع الآليّ كاملاً للتجربة قبل وصول مفاتيح Chargily وSofizPay.

**ممنوعٌ في الإنتاج** (`payment_gateways.build`). «صفحةُ الدفع» صفحةٌ في هذه الخلفية نفسِها بزرّين — «نجح» و«فشل» — **ونتيجتُها في Redis**
يقرؤها `check` كما يقرأ الوسيطُ الحقيقيُّ حالَه: الإشعارُ يوقظ والفحصُ يقرّر، بالعقد نفسِه.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from decimal import Decimal

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base

_KEY = "paymock:{}"
_TTL = 24 * 3600


def page_url(external_id: str) -> str:
    return f"{settings.public_api_base_url}{settings.api_v1_prefix}/payment-requests/mock/{external_id}"


async def settle(external_id: str, outcome: str) -> None:
    """ما تكتبه صفحةُ الوهميّ عند الضغط — و`check` يقرؤه."""
    await get_redis_client().set(_KEY.format(external_id), outcome, ex=_TTL)


class MockGateway:
    #: **الوهميُّ للتطوير وحدَه** — يُحسم من صفحته بسؤال `refresh`، ولا مالَ حقيقيٌّ فيه ولا تجربةٌ عند وسيط
    test_mode = False
    confirms_by_webhook = False

    def __init__(self, integration: str) -> None:
        self.name = integration
        self.last_status: str | None = None

    async def health(self) -> None:
        """**الوهميُّ صحيحٌ دائماً** — إلا إن كُتب في Redis أنه متوقّف (للتطوير: «انقطاعٌ» يُجرَّب بلا شبكة)."""
        if await get_redis_client().get("paymock:down"):
            raise base.GatewayDown()

    async def checkout(
        self,
        *,
        amount: Decimal,
        description: str,
        return_url: str,
        webhook_url: str,
        fee_bearer: str,
        customer: base.CheckoutCustomer,
        locale: str = "ar",
    ) -> base.Checkout:
        external_id = f"mock_{self.name}_{secrets.token_hex(8)}"
        await get_redis_client().set(_KEY.format(external_id), f"pending|{amount}|{return_url}", ex=_TTL)
        return base.Checkout(external_id=external_id, checkout_url=page_url(external_id))

    async def resume_url(self, external_id: str) -> str | None:
        state = await get_redis_client().get(_KEY.format(external_id))
        value = state.decode() if isinstance(state, bytes) else state
        return page_url(external_id) if value and value.startswith("pending|") else None

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        state = await get_redis_client().get(_KEY.format(external_id))
        value = state.decode() if isinstance(state, bytes) else state
        if value == "paid":
            return base.GatewayEvent(external_id, PaymentRequestStatus.APPROVED)
        if value == "failed":
            return base.GatewayEvent(external_id, PaymentRequestStatus.REJECTED, reason="فشل الدفعُ في الوسيط الوهميّ")
        self.last_status = "pending" if value and value.startswith("pending|") else None
        return None

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        return []

    async def test_connection(self) -> str:
        return "وسيطٌ وهميٌّ — للتطوير والاختبار وحدَهما، ولا يعمل في الإنتاج"


async def return_url_of(external_id: str) -> str | None:
    state = await get_redis_client().get(_KEY.format(external_id))
    value = state.decode() if isinstance(state, bytes) else state
    if value and value.startswith("pending|"):
        return value.split("|", 2)[2]
    return None
