"""واجهة مزود التحويلات الآلية للسحوبات (SPEC القسم 9/15-أ).

«payout API آلي للسحوبات — قبله: التحويل اليدوي الموصوف في القسم 9.» فهذه
الواجهة تُغني عن **يد المحاسب** لا عن حكمه: الطلب يبقى يمر بـ
`pending → approved`، والآلي يحل محل خطوة «حوّل ثم سجّل المرجع» وحدها.

والقاعدة المالية لا تتغير بتغيّر المزود: **قيد `withdrawal` يُكتب عند `paid`
وحدها**، و`paid` تعني أن المزود قال «حوّلت» — لا أننا طلبنا منه ذلك.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.core.exceptions import AppError
from app.models.enums import Currency, WithdrawalMethod

REQUEST_TIMEOUT_SECONDS = 20.0


class PayoutUnavailable(AppError):
    """لا عقد payout مُدخل أو مفعّل لهذه الدولة — والمسار اليدوي قائم."""

    status_code = 503
    code = "payout_unavailable"
    message = "التحويل الآلي غير مهيأ — راجع عقد payout في لوحة الإدارة"


class PayoutError(AppError):
    status_code = 502
    code = "payout_failed"
    message = "تعذّر تنفيذ التحويل عند المزود"


@dataclass(frozen=True, slots=True)
class PayoutRequest:
    """حوالةٌ واحدة إلى كبتن."""

    reference: str
    amount: Decimal
    currency: Currency
    method: WithdrawalMethod
    beneficiary_name: str
    # alias كليك أو رقم الحساب البنكي حسب القناة
    destination: str


@dataclass(frozen=True, slots=True)
class PayoutState:
    """حال الحوالة عند المزود.

    `settled=False` تعني «قيد التنفيذ»: لا قيد في الدفتر ولا تعليم بـ `paid`.
    والمالُ لم يخرج من رصيد الكبتن بعد لأن طلبه ما زال يحجزه — فلا خسارة في
    الانتظار، بخلاف الخسارة في تعليم ما لم يُحوَّل مدفوعاً.
    """

    provider_ref: str
    settled: bool
    paid: bool
    status_text: str


class PayoutProvider(Protocol):
    async def send_payout(self, request: PayoutRequest) -> PayoutState:
        """ينفّذ الحوالة ويعيد حالها كما قالها المزود."""
        ...

    async def check_payout(self, provider_ref: str) -> PayoutState:
        """يستعلم عن حوالةٍ لم تُحسم عند إرسالها."""
        ...

    async def test_connection(self) -> str:
        """يختبر العقد أو يرفع `PayoutError`."""
        ...
