"""واجهة مزود CliQ الآلي — عقدٌ واحد لشحن المحفظة بكليك (SPEC القسم 7/15-أ).

**نطاقُه شحنُ المحفظة وحده، وهذا قرارٌ لا تقصير.** حساب التاجر يشهد على ما
يدخل حساب الشركة؛ أما دفعُ الرحلة بكليك فمالُه ينتقل من الراكب إلى **alias
الكبتن** مباشرةً ولا يمر بالشركة أصلاً، فلا acquirer يشهد عليه ولا تأكيد آلي
له مهما فُعِّل من عقود (SPEC القسم 6). تفعيلُ هذا العقد لا يغيّر تصنيف
`cliq` في `models/payment.py`.

نفس بنية `card_gateway`: `mock.py` للتجربة والاختبار، ومزودٌ حقيقي واحد،
و`__init__` نقطةُ القرار — والمفاتيح من `provider_credentials` لا `.env`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.core.exceptions import AppError
from app.models.enums import Currency

REQUEST_TIMEOUT_SECONDS = 20.0


class CliqUnavailable(AppError):
    """لا عقد acquirer مُدخل أو مفعّل لهذه الدولة."""

    status_code = 503
    code = "cliq_acquirer_unavailable"
    message = "خدمة كليك الآلية غير مهيأة — راجع عقد CliQ في لوحة الإدارة"


class CliqError(AppError):
    status_code = 502
    code = "cliq_acquirer_error"
    message = "تعذّر إتمام العملية عند مزود كليك"


@dataclass(frozen=True, slots=True)
class CliqChargeRequest:
    """طلبُ تحصيلٍ واحد على alias الشركة."""

    reference: str
    amount: Decimal
    currency: Currency
    description: str
    customer_name: str
    customer_phone: str


@dataclass(frozen=True, slots=True)
class CliqCharge:
    """ما يُعرض للدافع: رمزُ استجابةٍ سريعة ورابطٌ يفتح تطبيق بنكه."""

    provider_ref: str
    qr_payload: str
    deep_link: str | None = None


@dataclass(frozen=True, slots=True)
class CliqChargeState:
    """حال التحصيل عند المزود — المصدر الوحيد الذي يحرّك الدفتر.

    `settled=False` تعني «لم يُحسم»: الحوالة لم تصل بعد. لا تخمين في اتجاه،
    ولا في الاتجاه الآخر — نفس قاعدة `card_gateway.OrderState`.
    """

    provider_ref: str
    settled: bool
    paid: bool
    status_text: str
    amount: Decimal | None = None


class CliqProvider(Protocol):
    async def create_charge(self, request: CliqChargeRequest) -> CliqCharge:
        """يفتح تحصيلاً ويعيد ما يُعرض للدافع."""
        ...

    async def check_charge(self, provider_ref: str) -> CliqChargeState:
        """يستعلم عن التحصيل — عليه وحده يتحرك الدفتر."""
        ...

    async def test_connection(self) -> str:
        """يختبر العقد أو يرفع `CliqError`."""
        ...
