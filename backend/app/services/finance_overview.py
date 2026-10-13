"""«المالية العامة» — **كلُّ الدول معاً، كلٌّ بعملته** (SPEC §٧٤-أ/٩). **قراءةٌ وحدَها.**

**بانٍ واحدٌ لكلِّ دولة**: `finance_summary.summary` نفسُه الذي يرسم «مالية الدولة» — فلا رقمَ هنا يُحسب بطريقٍ ثانٍ (الشكلُ الثامن)،
**والمطابقةُ مع الدفتر لكلِّ دولةٍ ومعها حكمٌ واحدٌ على الكلّ**.

**ولا يُجمع دينارٌ إلى دينار** — إلا في **مجموعٍ تقريبيٍّ اختياريّ** بعملةٍ مرجعيّةٍ وأسعارِ صرفٍ تضعها الإدارة، **موسوماً «تقريبي — بسعر صرف تضعه
الإدارة»** ومعه كلُّ سعرٍ وتاريخُه. **وعملةٌ بلا سعرٍ تُسمّى ولا تُخمَّن**: المجموعُ يُرسم ناقصاً بأسماء ما نقصه، لا كاملاً بصفرٍ مكان المجهول.

**ومالُ التجربة مستثنًى** كما في كلِّ صفحةٍ ماليّة — الاستثناءُ في `finance_summary` نفسِه.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import InvalidInput
from app.models.enums import AuditAction, CountryCode, Currency
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.services import audit
from app.services import finance_summary as fs

#: **دقّةُ المجموع التقريبيّ** — سنتٌ مرجعيّ: هو تقريبٌ معلَنٌ لا مالٌ يُقيَّد
APPROX_STEP = Decimal("0.01")
APPROX_NOTE = "تقريبي — بسعر صرف تضعه الإدارة"


@dataclass(frozen=True, slots=True)
class RateRow:
    currency: Currency
    rate: Decimal
    set_at: datetime


async def current_rates(session: AsyncSession, reference: str | None = None) -> tuple[str | None, list[RateRow]]:
    """**المرجعيّةُ السارية وأسعارُها** — أحدثُ ما ضُبط؛ و`(None, [])` حين لم يُضبط شيء."""
    if reference is None:
        reference = await session.scalar(select(ExchangeRate.reference).order_by(ExchangeRate.created_at.desc()).limit(1))
        if reference is None:
            return None, []
    rows: list[RateRow] = []
    for currency in Currency:
        row = await session.scalar(
            select(ExchangeRate)
            .where(ExchangeRate.reference == reference, ExchangeRate.currency == currency)
            .order_by(ExchangeRate.created_at.desc())
            .limit(1)
        )
        if row is not None:
            rows.append(RateRow(currency=Currency(row.currency), rate=row.rate, set_at=row.created_at))
    return reference, rows


async def set_rates(session: AsyncSession, *, reference: str, rates: dict[Currency, Decimal], actor: User) -> None:
    code = (reference or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise InvalidInput("العملةُ المرجعيّةُ رمزٌ من ثلاثة أحرف (USD · EUR)")
    if not rates:
        raise InvalidInput("اكتب سعراً واحداً على الأقلّ")
    stamp = datetime.now(UTC)
    for currency, rate in rates.items():
        if rate <= 0:
            raise InvalidInput("سعرُ الصرف أكبرُ من صفر")
        # **الطابعُ من الساعة لا من بداية المعاملة** (`now()` في القاعدة): ضبطان متتاليان قد يقعان في اللحظة نفسِها فيتساويان، **والأحدثُ
        # يجب أن يحكم** — قِيس: سعرٌ ثانٍ بعد الأوّل بلحظةٍ قُرئ الأوّلَ
        session.add(ExchangeRate(reference=code, currency=currency, rate=rate, set_by=actor.id, created_at=stamp))
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="exchange_rates",
        details={"reference": code, "rates": {currency.value: str(rate) for currency, rate in rates.items()}},
    )
    await session.flush()


@dataclass(frozen=True, slots=True)
class CombinedMetric:
    key: str
    label: str
    #: `None` حين نقص سعرُ عملةٍ لها مبلغٌ غيرُ صفريّ — **لا يُرسم ناقصٌ كاملاً**
    amount: Decimal | None
    missing: list[Currency]


@dataclass(frozen=True, slots=True)
class Overview:
    summaries: list[fs.Summary]
    reference: str | None
    rates: list[RateRow]
    combined: list[CombinedMetric] | None


async def overview(
    session: AsyncSession,
    *,
    now: datetime,
    period: fs.FinancePeriod,
    from_date: date | None,
    to_date: date | None,
    user_type: fs.FinanceUserType | None,
    method: fs.FinanceMethod | None,
    status: fs.FinanceStatus | None,
    reference: str | None = None,
) -> Overview:
    summaries: list[fs.Summary] = []
    for country in CountryCode:
        scope = await fs.build_scope(
            session,
            country=country,
            period=period,
            now=now,
            from_date=from_date,
            to_date=to_date,
            user_type=user_type,
            method=method,
            status=status,
        )
        summaries.append(await fs.summary(session, scope))
    ref, rates = await current_rates(session, reference)
    combined = None
    if ref is not None:
        by_currency = {row.currency: row.rate for row in rates}
        combined = []
        for metric in fs.METRICS.values():
            total = Decimal(0)
            missing: list[Currency] = []
            for summary in summaries:
                value = next(item for item in summary.values if item.metric.key == metric.key)
                if not value.amount:
                    continue
                currency = currency_for_country(summary.scope.country)
                rate = by_currency.get(currency)
                if rate is None:
                    missing.append(currency)
                    continue
                total += Decimal(value.amount) * rate
            combined.append(
                CombinedMetric(
                    key=metric.key,
                    label=metric.label,
                    amount=None if missing else total.quantize(APPROX_STEP, rounding=ROUND_HALF_UP),
                    missing=missing,
                )
            )
    return Overview(summaries=summaries, reference=ref, rates=rates, combined=combined)
