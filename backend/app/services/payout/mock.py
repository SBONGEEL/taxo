"""مزود تحويلات وهمي — ما بُني عليه مسار السحب الآلي واختُبر (القسم 15/أ).

يُحسم فوراً بالنجاح ما لم يُضبط غير ذلك، فتُجرّب الدورة كاملةً بلا حساب بنكي.
والنتيجة قابلة للضبط من الاختبار: مسارُ «المزود رفض» يجب أن يمر به اختبارٌ
حقيقي لا أن يبقى فرعاً ميتاً.

**ممنوع في الإنتاج** (`__init__.build_provider`): مزودٌ يقول «حوّلت» بلا
تحويل يكتب قيد سحبٍ من رصيد كبتنٍ لم يقبض شيئاً.
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.services.payout.base import PayoutError, PayoutRequest, PayoutState

_KEY = "payout:mock:{reference}"
_TTL_SECONDS = 3600

OUTCOME_PAID = "paid"
OUTCOME_PENDING = "pending"
OUTCOME_FAILED = "failed"
OUTCOMES: tuple[str, ...] = (OUTCOME_PAID, OUTCOME_PENDING, OUTCOME_FAILED)

_STATUS_TEXT = {
    OUTCOME_PAID: "نُفّذت الحوالة (مزود وهمي)",
    OUTCOME_PENDING: "الحوالة قيد التنفيذ (مزود وهمي)",
    OUTCOME_FAILED: "رفض المزود الحوالة (مزود وهمي)",
}


def _ref(reference: str) -> str:
    return f"mock-payout-{reference}"


class MockPayoutProvider:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def set_outcome(self, reference: str, outcome: str) -> None:
        if outcome not in OUTCOMES:
            raise PayoutError(f"نتيجة غير معروفة للمزود الوهمي: {outcome}")
        await self._redis.set(
            _KEY.format(reference=reference), outcome, ex=_TTL_SECONDS
        )

    async def _outcome(self, reference: str) -> str:
        raw = await self._redis.get(_KEY.format(reference=reference))
        if raw is None:
            return OUTCOME_PAID
        value = raw.decode() if isinstance(raw, bytes) else str(raw)
        return value if value in OUTCOMES else OUTCOME_PAID

    def _state(self, reference: str, outcome: str) -> PayoutState:
        return PayoutState(
            provider_ref=_ref(reference),
            settled=outcome != OUTCOME_PENDING,
            paid=outcome == OUTCOME_PAID,
            status_text=_STATUS_TEXT[outcome],
        )

    async def send_payout(self, request: PayoutRequest) -> PayoutState:
        return self._state(request.reference, await self._outcome(request.reference))

    async def check_payout(self, provider_ref: str) -> PayoutState:
        reference = provider_ref.removeprefix("mock-payout-")
        return self._state(reference, await self._outcome(reference))

    async def test_connection(self) -> str:
        return "المزود الوهمي جاهز — لا شبكة خارجية"
