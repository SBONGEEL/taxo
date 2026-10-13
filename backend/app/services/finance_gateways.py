"""**ما بقي لـTAXO عند وسيط البطاقات** — موقفُ المالك من مال البطاقات لكلِّ سوق (SPEC §٧٤-ط/٦، §٧٤-ي/٧).

سطرٌ لكلِّ عقدِ وسيطٍ مفعَّلٍ في السوق، بأمرين **لا يُجمعان**:
- **ما دخل عبره** (من الدفتر): مجموعُ ما اعتُمد من طلبات الدفع عند هذا الوسيط للحسابات الحقيقيّة — **ومالُ التجربة مستثنًى** كبقيّة
  صفحات المالية.
- **ما يقوله الوسيطُ عن رصيده** (`GET /balance` عند Chargily): الرصيدُ، والجاهزُ للتحويل إلى حساب TAXO، والمعلَّقُ عنده — **وهو ما
  يدين به الوسيطُ لـTAXO الآن**. يُقرأ في اللحظة **ومعه ساعتُه ووضعُ العقد**: وضعُ التجربة يقول رصيدَ تجربةٍ لا مالاً.

**ولا يُكتب شيء**: قراءةٌ من القاعدة ونداءُ قراءةٍ عند الوسيط. **وتعذُّرُ الوسيط يُقال** («تعذّرت القراءة») ولا يُرسم صفراً.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.models.enums import CountryCode, Currency, PaymentRequestStatus, ProviderKey
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.provider_credential import ProviderCredential
from app.services import payment_gateways, test_accounts
from app.services.pricing import as_money

LABELS = {"chargily": "Chargily Pay — الذهبية وCIB", "sofizpay": "SofizPay — CIB"}


@dataclass(frozen=True, slots=True)
class GatewayPosition:
    integration: str
    label: str
    currency: Currency
    test_mode: bool
    received_amount: Decimal
    received_count: int
    #: **رسومُ الوسيط على ما دخل** (§٧٤-ك/١) — ما حملته TAXO وما حمله الدافعون، من الطلبات نفسِها
    fees_taxo_amount: Decimal
    fees_payer_amount: Decimal
    #: ما يقوله الوسيط — `None` حين لا يُقرأ (وسيطٌ بلا بابِ رصيد، أو تعذّر)
    balance: Decimal | None
    ready_amount: Decimal | None
    on_hold_amount: Decimal | None
    read_at: datetime | None
    note: str | None


async def _received(session: AsyncSession, country: CountryCode, integration: str) -> tuple[Decimal, int, Decimal, Decimal]:
    total, count, taxo_fees, payer_fees = (
        await session.execute(
            select(
                func.coalesce(func.sum(func.coalesce(PaymentRequest.credited_amount, PaymentRequest.amount)), 0),
                func.count(),
                func.coalesce(func.sum(PaymentRequest.fee_amount).filter(PaymentRequest.fee_payer == "taxo"), 0),
                func.coalesce(func.sum(PaymentRequest.fee_amount).filter(PaymentRequest.fee_payer == "user"), 0),
            )
            .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
            .where(
                PaymentRequest.country_code == country,
                PayMethod.integration == integration,
                PaymentRequest.status.in_((PaymentRequestStatus.APPROVED, PaymentRequestStatus.REFUNDED)),
                test_accounts.real_user(PaymentRequest.user_id),
            )
        )
    ).one()
    return as_money(Decimal(total)), int(count), as_money(Decimal(taxo_fees)), as_money(Decimal(payer_fees))


async def positions(session: AsyncSession, country: CountryCode) -> list[GatewayPosition]:
    """**لكلِّ عقدٍ مفعَّلٍ في السوق سطرٌ** — بالترتيب الثابت للوسطاء."""
    currency = currency_for_country(country)
    out: list[GatewayPosition] = []
    for integration, key in payment_gateways.PROVIDER_KEYS.items():
        active = await session.scalar(
            select(func.count()).select_from(ProviderCredential).where(
                ProviderCredential.provider_key == ProviderKey(key),
                ProviderCredential.country_code == country,
                ProviderCredential.is_active.is_(True),
            )
        )
        if not active:
            continue
        received, count, taxo_fees, payer_fees = await _received(session, country, integration)
        balance = ready = on_hold = None
        read_at = None
        note: str | None = None
        test_mode = False
        try:
            gateway = await payment_gateways.gateway_for(session, integration, country)
            test_mode = bool(getattr(gateway, "test_mode", False))
            reader = getattr(gateway, "balance", None)
            if reader is None:
                note = "هذا الوسيطُ لا يُقرأ رصيدُه من بابه"
            else:
                wallet = await reader(currency.value.lower())
                read_at = datetime.now(UTC)
                if wallet is None:
                    note = "لا محفظةَ بهذه العملة عند الوسيط"
                else:
                    balance, ready, on_hold = wallet
        except (payment_gateways.GatewayUnavailable, payment_gateways.GatewayError):
            note = "تعذّرت قراءةُ الرصيد من الوسيط الآن"
        out.append(
            GatewayPosition(
                integration=integration, label=LABELS.get(integration, integration), currency=currency,
                test_mode=test_mode, received_amount=received, received_count=count,
                fees_taxo_amount=taxo_fees, fees_payer_amount=payer_fees,
                balance=balance, ready_amount=ready, on_hold_amount=on_hold, read_at=read_at, note=note,
            )
        )
    return out
