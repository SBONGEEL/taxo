"""**الوسطاءُ الآليّون للنظام الجديد** — عقدٌ واحدٌ وسجلٌّ واحد (SPEC §٧٣-هـ/٣ و١٠).

**كلُّ وسيطٍ محوِّلٌ يحقّق هذا العقد**، ويُسجَّل باسمه في `REGISTRY`؛ وصفُّ الطريقة في `payment_providers` يحمل الاسمَ في `integration`.
**والـwebhook الموحّد** (`POST /payment-requests/webhook/{integration}`) **يسأل المحوِّلَ عن التوقيع قبل أن يقرأ شيئاً**، ثمّ يطبّق ما
قاله بالأبواب نفسِها التي يعتمد بها الموظّف (`payment_requests.apply_gateway_outcome`) — فلا مسارَ ثانياً للمال.

**والسجلُّ فارغٌ في المرحلة ١**: Chargily وSofizPay يُبنيان في المرحلة ٣ بوثائقهما المنشورة. وطلبٌ لوسيطٍ غيرِ مسجَّلٍ ٤٠٤.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.core.exceptions import AppError
from app.models.enums import PaymentRequestStatus


class WebhookSignatureInvalid(AppError):
    """**توقيعٌ لا يطابق** — لا يُقرأ من الجسم حرفٌ بعده، ولا يُقال لماذا (`401`)."""

    status_code = 401
    code = "webhook_signature_invalid"
    message = "توقيعٌ غيرُ صالح"


@dataclass(frozen=True, slots=True)
class GatewayEvent:
    """**ما قاله الوسيطُ عن دفعةٍ واحدة** بعد التحقّق من توقيعه — بلغة النظام لا بلغته."""

    external_id: str
    outcome: PaymentRequestStatus
    #: **ما وصل فعلاً بعملة الطلب** — `None` حين لا يذكره الوسيط (فيُقيَّد مبلغُ الطلب كما هو)
    amount: Decimal | None = None
    reason: str | None = None


class Gateway(Protocol):
    """**عقدُ المحوِّل** — يتحقّق من توقيع إشعارٍ ويترجمه؛ وفتحُ الدفع عنده (`checkout`) يُضاف في المرحلة ٣."""

    name: str

    async def parse_webhook(self, *, headers: dict[str, str], body: bytes) -> list[GatewayEvent]:
        """**يتحقّق من التوقيع أوّلاً** — `WebhookSignatureInvalid` إن لم يطابق — ثمّ يعيد ما في الإشعار من أحداث."""
        ...


#: الوسطاءُ المسجَّلون باسم محوِّلهم — **فارغٌ حتى المرحلة ٣**
REGISTRY: dict[str, Gateway] = {}


def gateway_for(integration: str) -> Gateway | None:
    return REGISTRY.get(integration)
