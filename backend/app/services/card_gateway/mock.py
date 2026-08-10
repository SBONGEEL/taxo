"""مزود بطاقات وهمي — ما تُختبر عليه المرحلة 6-ب كلها (SPEC القسم 15).

SPEC تنص على أن ميزات المزودين «تُبنى كاملة الآن ضد واجهة مزود موحدة مع مزود
وهمي mock للاختبار، وتتفعل تلقائياً بمجرد إدخال بيانات العقد الحقيقي». هذا هو
ذلك المزود: يُفعَّل بحقل `use_mock` في عقد Telr من صفحة العقود، فيصير مسار
البطاقة كاملاً قابلاً للتجربة والاختبار بلا حساب Sandbox ولا شبكة.

**ممنوع في الإنتاج** (`__init__.get_gateway`): مزودٌ يقول «دُفع» بلا مال بابٌ
لا يُترك مفتوحاً حيث يوجد مال حقيقي.

حالتُه في Redis لا في الذاكرة: عاملا uvicorn لا يتقاسمان ذاكرة، ومقبسٌ يقرأ
حالةً كتبها عاملٌ آخر يجب أن يراها. والمفتاح بعمرٍ محدود — طلبٌ وهميٌّ منسيٌّ
ليس بياناً يُحتفظ به.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from redis.asyncio import Redis

from app.models.enums import Currency, PaymentProvider
from app.services.card_gateway.base import (
    CardDetails,
    CardGatewayError,
    HostedPage,
    InvalidWebhookSignature,
    OrderRequest,
    OrderState,
    WebhookNotice,
)

# مفتاح الحال الوهمية لكل طلب، بعمر يكفي أطول جلسة دفع
_KEY = "card:mock:{cart_id}"
_TTL_SECONDS = 3600

# النتائج التي يمكن أن «يختارها» الدافع على الصفحة الوهمية
OUTCOME_PENDING = "pending"
OUTCOME_PAID = "paid"
OUTCOME_DECLINED = "declined"
OUTCOME_CANCELLED = "cancelled"

OUTCOMES: tuple[str, ...] = (
    OUTCOME_PENDING,
    OUTCOME_PAID,
    OUTCOME_DECLINED,
    OUTCOME_CANCELLED,
)

# بطاقة اختبارٍ ثابتة: أرقامٌ لا تُدفع بها، وآخرُ أربعةٍ وتاريخٌ يكفيان للعرض
MOCK_CARD = CardDetails(
    token="mock-card-token",
    brand="Visa",
    last4="4242",
    expiry_month=12,
    expiry_year=2030,
)

_STATUS_TEXT = {
    OUTCOME_PENDING: "بانتظار إتمام الدفع",
    OUTCOME_PAID: "تم الدفع (مزود وهمي)",
    OUTCOME_DECLINED: "رفض البنك العملية (مزود وهمي)",
    OUTCOME_CANCELLED: "ألغى الدافع العملية (مزود وهمي)",
}


def _ref(cart_id: str) -> str:
    return f"mock-{cart_id}"


class MockCardGateway:
    """يحاكي العقد كاملاً: صفحة، استعلام، خصمٌ بضغطة، استرداد، وتوقيع إشعار."""

    provider = PaymentProvider.TELR

    def __init__(self, redis: Redis, *, return_url_template: str | None = None) -> None:
        self._redis = redis
        self._return_url_template = return_url_template

    # -------------------------------------------------------------- الحالة

    async def _outcome(self, cart_id: str) -> str:
        raw = await self._redis.get(_KEY.format(cart_id=cart_id))
        if raw is None:
            return OUTCOME_PENDING
        value = raw.decode() if isinstance(raw, bytes) else str(raw)
        return value if value in OUTCOMES else OUTCOME_PENDING

    async def set_outcome(self, cart_id: str, outcome: str) -> None:
        """ما تستدعيه الصفحة الوهمية (أو الاختبار) نيابةً عن الدافع."""
        if outcome not in OUTCOMES:
            raise CardGatewayError(f"نتيجة غير معروفة للمزود الوهمي: {outcome}")
        await self._redis.set(
            _KEY.format(cart_id=cart_id), outcome, ex=_TTL_SECONDS
        )

    # ------------------------------------------------------------ العمليات

    async def create_hosted_page(self, order: OrderRequest) -> HostedPage:
        await self.set_outcome(order.cart_id, OUTCOME_PENDING)
        # رابطٌ يشير إلى مسار المحاكاة في الخلفية نفسها: لا شبكة خارجية أصلاً،
        # فتُجرّب الدورة كاملةً محلياً كما تُجرّب مع مزود حقيقي
        return HostedPage(
            provider_order_ref=_ref(order.cart_id),
            redirect_url=(
                self._return_url_template.format(cart_id=order.cart_id)
                if self._return_url_template
                else f"mock://card/{order.cart_id}"
            ),
        )

    async def check_order(self, provider_order_ref: str) -> OrderState:
        cart_id = provider_order_ref.removeprefix("mock-")
        outcome = await self._outcome(cart_id)
        return OrderState(
            provider_order_ref=provider_order_ref,
            settled=outcome != OUTCOME_PENDING,
            paid=outcome == OUTCOME_PAID,
            status_text=_STATUS_TEXT[outcome],
            card=MOCK_CARD if outcome == OUTCOME_PAID else None,
            transaction_ref=f"mock-tran-{cart_id}" if outcome == OUTCOME_PAID else None,
        )

    async def charge_saved_card(
        self, order: OrderRequest, card_token: str
    ) -> OrderState:
        """يُحسم فوراً: بطاقة محفوظة تنجح، وأيُّ رمزٍ غيرها يُرفض."""
        paid = card_token == MOCK_CARD.token
        await self.set_outcome(
            order.cart_id, OUTCOME_PAID if paid else OUTCOME_DECLINED
        )
        return await self.check_order(_ref(order.cart_id))

    async def refund_order(
        self, provider_order_ref: str, amount: Decimal, currency: Currency, reason: str
    ) -> str:
        return f"mock-refund-{provider_order_ref}"

    async def test_connection(self) -> str:
        return "المزود الوهمي جاهز — لا شبكة خارجية"

    # -------------------------------------------------------------- التوقيع

    def expected_check(self, payload: Mapping[str, str]) -> str:
        """توقيعٌ وهمي بشكلٍ ثابت — يُحسب كما يُتحقق منه، فيُختبر المسار نفسه."""
        return f"mock-check-{payload.get('tran_cartid', '')}"

    def verify_webhook(self, payload: Mapping[str, str]) -> WebhookNotice:
        cart_id = str(payload.get("tran_cartid", "") or "")
        if not cart_id:
            raise InvalidWebhookSignature("إشعار الدفع ناقص الحقول")
        if str(payload.get("tran_check", "") or "") != self.expected_check(payload):
            raise InvalidWebhookSignature()
        return WebhookNotice(
            cart_id=cart_id,
            provider_order_ref=str(payload.get("tran_ref") or _ref(cart_id)),
        )
