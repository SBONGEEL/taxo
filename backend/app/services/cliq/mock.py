"""مزود CliQ وهمي — ما بُني عليه شحنُ المحفظة الآلي واختُبر (القسم 15/أ).

نفس بنية `card_gateway/mock.py`: الحال في Redis لا في الذاكرة (عاملان لا
يتقاسمان ذاكرة)، وبعمرٍ محدود، والنتيجة تُختار كما يختارها الدافع في الواقع
حين يحوّل أو لا يحوّل.

**ممنوع في الإنتاج** (`__init__.build_provider`): مزودٌ يقول «وصلت الحوالة»
بلا حوالة يشحن محفظةً بمالٍ لم يصل.
"""

from __future__ import annotations

from decimal import Decimal

from redis.asyncio import Redis

from app.services.cliq.base import (
    CliqCharge,
    CliqChargeRequest,
    CliqChargeState,
    CliqError,
)

_KEY = "cliq:mock:{reference}"
_AMOUNT_KEY = "cliq:mock:amount:{reference}"
_TTL_SECONDS = 3600

OUTCOME_PENDING = "pending"
OUTCOME_PAID = "paid"
OUTCOME_FAILED = "failed"
OUTCOMES: tuple[str, ...] = (OUTCOME_PENDING, OUTCOME_PAID, OUTCOME_FAILED)

_STATUS_TEXT = {
    OUTCOME_PENDING: "بانتظار وصول الحوالة",
    OUTCOME_PAID: "وصلت الحوالة (مزود وهمي)",
    OUTCOME_FAILED: "لم تصل الحوالة (مزود وهمي)",
}


def _ref(reference: str) -> str:
    return f"mock-cliq-{reference}"


class MockCliqProvider:
    def __init__(self, redis: Redis, *, company_alias: str) -> None:
        self._redis = redis
        self._company_alias = company_alias

    async def _outcome(self, reference: str) -> str:
        raw = await self._redis.get(_KEY.format(reference=reference))
        if raw is None:
            return OUTCOME_PENDING
        value = raw.decode() if isinstance(raw, bytes) else str(raw)
        return value if value in OUTCOMES else OUTCOME_PENDING

    async def set_outcome(
        self, reference: str, outcome: str, *, amount: Decimal | None = None
    ) -> None:
        """ما يستدعيه الاختبار (أو المطوّر) نيابةً عن حوالةٍ وصلت أو لم تصل."""
        if outcome not in OUTCOMES:
            raise CliqError(f"نتيجة غير معروفة للمزود الوهمي: {outcome}")
        await self._redis.set(
            _KEY.format(reference=reference), outcome, ex=_TTL_SECONDS
        )
        if amount is not None:
            await self._redis.set(
                _AMOUNT_KEY.format(reference=reference), str(amount), ex=_TTL_SECONDS
            )

    async def create_charge(self, request: CliqChargeRequest) -> CliqCharge:
        await self.set_outcome(request.reference, OUTCOME_PENDING)
        await self._redis.set(
            _AMOUNT_KEY.format(reference=request.reference),
            str(request.amount),
            ex=_TTL_SECONDS,
        )
        payload = (
            f"CLIQ|{self._company_alias}|{request.amount}|"
            f"{request.currency.value}|{request.reference}"
        )
        return CliqCharge(
            provider_ref=_ref(request.reference),
            qr_payload=payload,
            deep_link=f"cliq://pay?ref={request.reference}",
        )

    async def check_charge(self, provider_ref: str) -> CliqChargeState:
        reference = provider_ref.removeprefix("mock-cliq-")
        outcome = await self._outcome(reference)
        raw_amount = await self._redis.get(_AMOUNT_KEY.format(reference=reference))
        amount = None
        if raw_amount is not None and outcome == OUTCOME_PAID:
            text = (
                raw_amount.decode()
                if isinstance(raw_amount, bytes)
                else str(raw_amount)
            )
            amount = Decimal(text)

        return CliqChargeState(
            provider_ref=provider_ref,
            settled=outcome != OUTCOME_PENDING,
            paid=outcome == OUTCOME_PAID,
            status_text=_STATUS_TEXT[outcome],
            amount=amount,
        )

    async def test_connection(self) -> str:
        return "المزود الوهمي جاهز — لا شبكة خارجية"
