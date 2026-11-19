"""**تقريبُ الأسعار وعرضُها لكلِّ دولة من اللوحة** (أمرُ المالك ٢٠٢٦-١١-١٩، `design/OWNER-2026-11-19-FARE-ROUNDING.md`).

**مصدرٌ واحدٌ** تقرؤه الخلفيّةُ والتطبيقان واللوحة:
- **الخطوةُ والاتجاهُ ومفاتيحُ المواضع** على `payment_settings.fare_*` — تقرؤها الخلفيّةُ بـ`rounding.fare_policy_for`، **وتُجمَّد على الرحلة عند
  طلبها** فلا يمسّ تغييرُها رحلةً جاريةً ولا قديمة.
- **والخاناتُ المعروضة** هي `country_markets.display_decimals` القائمة (SPEC §٧٣-ج/٧) — في `/config` لكلِّ تطبيق، **ولا تُخفي خانةً غيرَ
  صفريّةٍ أبداً**: مبلغٌ قديمٌ بفلوسه (1.725) يُرسم بفلوسه، فلا يُقرَّب شيءٌ صامتاً في العرض.

**والمعاينةُ هنا لا في الواجهة** (§14): المبلغُ وعشرُ أجرٍ قبل/بعد تُحسب بالدوالّ نفسِها التي تحسب الأجرة (`pricing.fare_breakdown` ⇐
`rounding.round_amount`)، **فما تُريه الصفحةُ هو ما سيُحصَّل**.

**وما لا يمسّه هذا البابُ — بقرار المالك**: معادلةُ الأجرة وقيمُها، والاشتراكات، والعمولة، والتقريبُ العامّ (`rounding_*`: الإكراميّاتُ
والشحنُ والسحبُ والتحويلُ والسلف)، والمحافظُ والدفتر، وأيُّ رحلةٍ قائمة.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import STORAGE_DECIMALS, currency_for_country, decimals_of
from app.core.exceptions import InvalidInput
from app.models.enums import AuditAction, CountryCode, RoundingMode
from app.models.payment_setting import PaymentSetting
from app.models.pricing import PricingRule
from app.models.user import User
from app.services import audit, markets, money_guards, pricing, rounding, settings_service
from app.services.directions import Route

#: **عشرُ رحلاتٍ للمعاينة** (المسافةُ كم، الزمنُ دقيقة) — من مشوارٍ قصيرٍ إلى عبورِ مدينة
SAMPLE_TRIPS: tuple[tuple[Decimal, Decimal], ...] = tuple(
    (Decimal(km), Decimal(minutes))
    for km, minutes in (
        ("1.2", "4"), ("2.0", "6"), ("2.8", "7"), ("3.5", "9"), ("4.6", "11"),
        ("6.4", "15"), ("8.0", "18"), ("11.0", "22"), ("15.5", "28"), ("22.0", "35"),
    )
)
#: الفئةُ التي تُحسب بها المعاينة — الأولى الموجودةُ من هذه
SAMPLE_CATEGORIES = ("economy", "comfort", "standard")
SURFACES = ("on_estimate", "on_final", "on_negotiation", "on_cancellation")


@dataclass(frozen=True, slots=True)
class FareRounding:
    decimals: int
    step: Decimal | None
    mode: RoundingMode
    on_estimate: bool
    on_final: bool
    on_negotiation: bool
    on_cancellation: bool
    #: **الصحيحُ بلا كسور** (أمرُ المالك ٢٠٢٦-١١-١٩) — «8 د.ل» لا «8.000»؛ عرضٌ وحدَه
    trim_whole: bool = False

    def policy(self) -> rounding.RoundingPolicy:
        """سياسةُ الأجرة النهائيّة بهذه القيم — للمعاينة."""
        if self.step is None or not self.on_final:
            return rounding.DISABLED
        return rounding.RoundingPolicy(enabled=True, unit=self.step, mode=self.mode)


def shown(amount: Decimal, decimals: int, trim_whole: bool = False) -> str:
    """**المبلغُ كما يُرسم بهذه الخانات** — القاعدةُ نفسُها في `formatAmount` بالتطبيقين ولوحة `money()`: تُكمَل الأصفارُ أو تُحذف،
    **ولا تُحذف خانةٌ غيرُ صفريّة** (1.725 بخانتين ⇐ «1.725»)."""
    text = f"{amount.quantize(Decimal(1).scaleb(-STORAGE_DECIMALS)):f}"
    whole, _, fraction = text.partition(".")
    if trim_whole and not fraction.strip("0"):
        return whole
    if fraction[decimals:].strip("0"):
        return text
    return f"{whole}.{fraction[:decimals]}" if decimals > 0 else whole


async def current(session: AsyncSession, country: CountryCode) -> FareRounding:
    setting = await session.scalar(select(PaymentSetting).where(PaymentSetting.country_code == country))
    decimals = await markets.display_decimals(session, country)
    trim = await markets.display_trim_whole(session, country)
    if setting is None:
        return FareRounding(decimals, None, RoundingMode.NEAREST, False, False, False, False, trim)
    return FareRounding(
        decimals=decimals,
        step=setting.fare_step,
        mode=RoundingMode(setting.fare_mode),
        on_estimate=setting.fare_on_estimate,
        on_final=setting.fare_on_final,
        on_negotiation=setting.fare_on_negotiation,
        on_cancellation=setting.fare_on_cancellation,
        trim_whole=trim,
    )


def require_fit(country: CountryCode, value: FareRounding) -> None:
    """**الخاناتُ تلائم الخطوة وإلّا لا حفظ** (٢-و) — بالجملة العربيّة نفسِها التي تُريها المعاينة."""
    message = rounding.fit_message(value.decimals, value.step, currency_for_country(country), trim_whole=value.trim_whole)
    if message:
        raise InvalidInput(message, field="decimals")


async def _sample_rule(session: AsyncSession, country: CountryCode) -> PricingRule | None:
    for category in SAMPLE_CATEGORIES:
        rule = await session.scalar(
            select(PricingRule).where(PricingRule.country_code == country, PricingRule.vehicle_category == category)
        )
        if rule is not None:
            return rule
    return await session.scalar(
        select(PricingRule).where(PricingRule.country_code == country).order_by(PricingRule.vehicle_category)
    )


async def preview(
    session: AsyncSession, country: CountryCode, proposed: FareRounding, amount: Decimal | None = None
) -> dict:
    """**ما ستُريه الأجرةُ قبل الحفظ** — المبلغُ المكتوبُ وعشرُ أجرٍ (قبل = الإعدادُ القائم، بعد = المقترَح)، **وجملةُ المنع إن لم تلائم**."""
    before = await current(session, country)
    rule = await _sample_rule(session, country)
    samples = []
    if rule is not None:
        for km, minutes in SAMPLE_TRIPS:
            precise, _, _ = pricing.fare_breakdown(rule, Route(distance_km=km, duration_min=minutes), 0)
            old = rounding.rounded(precise, before.policy())
            new = rounding.rounded(precise, proposed.policy())
            samples.append({
                "distance_km": km,
                "duration_min": minutes,
                "precise": precise,
                "before": old,
                "after": new,
                "before_text": shown(old, before.decimals, before.trim_whole),
                "after_text": shown(new, proposed.decimals, proposed.trim_whole),
            })
    result = None
    if amount is not None:
        after = rounding.rounded(amount, proposed.policy())
        result = {"amount": amount, "after": after, "after_text": shown(after, proposed.decimals, proposed.trim_whole)}
    return {
        "fit_error": rounding.fit_message(
            proposed.decimals, proposed.step, currency_for_country(country), trim_whole=proposed.trim_whole
        ),
        "vehicle_category": rule.vehicle_category if rule is not None else None,
        "amount": result,
        "samples": samples,
    }


def _as_audit(value: FareRounding) -> dict:
    return {
        "decimals": value.decimals,
        "step": None if value.step is None else str(value.step),
        "mode": value.mode.value,
        **{name: getattr(value, name) for name in SURFACES},
    }


async def save(session: AsyncSession, country: CountryCode, value: FareRounding, actor: User) -> FareRounding:
    """**يحفظ ويكتب في سجلّ التدقيق** (من، متى، القديم، الجديد) — **للرحلات الجديدة وحدَها**: القائمةُ تحمل سياستَها المجمَّدة.

    يمرّ بقفل الأسعار (`require_pricing_writes`) — **التقريبُ يغيّر ما يدفعه الراكبُ في رحلةٍ جديدة**، فيُجمَّد حيث تُجمَّد الأسعار."""
    require_fit(country, value)
    await money_guards.require_pricing_writes(session, actor=actor, country_code=country)
    before = await current(session, country)
    setting = await settings_service.get_or_create_payment_settings(session, country)
    setting.fare_step = value.step
    setting.fare_mode = value.mode.value
    for name in SURFACES:
        setting.__setattr__(f"fare_{name}", getattr(value, name))
    if value.decimals != before.decimals or value.trim_whole != before.trim_whole:
        await markets.set_display_decimals(
            session, country=country, decimals=value.decimals, actor=actor, fare_step=value.step, trim_whole=value.trim_whole
        )
    old, new = _as_audit(before), _as_audit(value)
    changes = {key: {"from": old[key], "to": new[key]} for key in new if old[key] != new[key]}
    if changes:
        await audit.record(
            session,
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type="fare_rounding",
            details={"country_code": country.value, "changes": changes},
        )
    await session.flush()
    return value


def currency_decimals(country: CountryCode) -> int:
    return decimals_of(currency_for_country(country))
