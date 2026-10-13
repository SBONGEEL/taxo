"""مبالغُ السوقين المغلقين (SPEC §٧٤-د) — **أسعارُ الجزائر ورسومُها وتقريبُها وفئاتُ بطاقاتها، ومبالغُ ليبيا التي كانت صفراً**.

**يُشغَّل على الإنتاج بعد الرفع**، في حاوية الخلفية — والأمرُ يذكر ملفاتِه كلَّها:

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps backend python -m scripts.market_amounts_74            # معاينةٌ لا تكتب
    … backend python -m scripts.market_amounts_74 --apply                         # الكتابة

## القاعدةُ الواحدة: **يُملأ الصفرُ والفارغ، ولا يُمسّ رقمٌ قائم**

* **ما كان صفراً أو فارغاً يُكتب** بقيمة الجدول في §٧٤-د؛ **وما كان رقماً غيرَ صفرٍ يبقى كما هو ويُقال** («قائمٌ — لم يُمسّ»)، ولو خالف
  الجدول: **الرقمُ القائمُ قرارُ من كتبه**، وهذا السكربتُ يملأ ما لم يُقرَّر لا ما قُرِّر.
* **والتقريبُ وحدةٌ واحدة**: إن كان مطفأً أُشعل بوحدته واتجاهه وخُتمت لحظتُه (`rounding_enabled_at`) — **وإن كان مشتعلاً لم يُمسّ**.
  ولا يصلح عليه «املأ الصفر» حقلاً حقلاً: وحدتُه الافتراضيّةُ ٠٫٥٠٠ ليست صفراً، **وتقريبُ ليبيا إلى نصف دينارٍ ليس ما قُرِّر**.
* **وما ليس في الجدول لا يُكتب**: العمولةُ وخططُ الاشتراك والإلغاءُ ومفاتيحُ الميزات — **ولا يُفتح سوق**. **والبلدان مغلقان** فلا يرى هذه
  الأرقامَ إلا حسابُ التجربة.

## وحرّاسُه

* **تجميدُ التسعير يُحترم** (`money_guards.require_pricing_writes`) — مجمَّدٌ ⇒ يقف قبل أن يكتب.
* **وكلُّ جدولٍ مسّه سطرٌ في التدقيق** بأسماء حقوله لا بمبالغها (SPEC القسم 14)، **بلا فاعل**: إنسانٌ على الخادم شغّل سكربتاً،
  **وقيدٌ يسمّي من لم يفعل أسوأُ من قيدٍ لا يسمّي أحداً**.
* **والمعاينةُ افتراضٌ**: بلا `--apply` يُطبع كلُّ ما سيُكتب ثمّ يُتراجع — **والكتابةُ قرارٌ ثانٍ لا أثرٌ جانبيٌّ للقراءة**.
* **ومعاملةٌ واحدة**: يسقط بندٌ ⇒ لا يُلتزم شيء.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.models.advance import AdvanceSetting  # noqa: E402
from app.models.enums import AuditAction, CountryCode  # noqa: E402
from app.models.facility import FACILITY_AIRPORT, Facility  # noqa: E402
from app.models.pricing import PricingRule  # noqa: E402
from app.models.referral import ReferralSetting  # noqa: E402
from app.models.service_setting import ServiceSetting  # noqa: E402
from app.models.taxo_card import CardDenomination  # noqa: E402
from app.services import audit, facilities, money_guards, settings_service  # noqa: E402

D = Decimal

#: **أسعارُ الرحلة** — الجزائرُ كاملةً، وليبيا ما كان صفراً (الوقوفُ والانتظار)؛ والقائمُ غيرُ الصفريّ لا يُمسّ
PRICING: dict[CountryCode, dict[str, dict[str, Any]]] = {
    CountryCode.DZ: {
        "economy": {
            "base_fare": D("100"), "price_per_km": D("40"), "price_per_min": D("8"), "minimum_fare": D("230"),
            "cancellation_fee": D("100"), "stop_fee": D("60"), "stop_free_minutes": 1, "stop_price_per_min": D("8"),
            "stop_max_wait_minutes": 2, "pause_price_per_min": D("15"), "arrival_free_minutes": 2, "pause_max_minutes": 10,
        },
        "comfort": {
            "base_fare": D("130"), "price_per_km": D("52"), "price_per_min": D("10"), "minimum_fare": D("300"),
            "cancellation_fee": D("130"), "stop_fee": D("100"), "stop_free_minutes": 1, "stop_price_per_min": D("10"),
            "stop_max_wait_minutes": 2, "pause_price_per_min": D("20"), "arrival_free_minutes": 2, "pause_max_minutes": 10,
        },
    },
    CountryCode.LY: {
        "economy": {
            "stop_fee": D("2"), "stop_free_minutes": 1, "stop_price_per_min": D("0.150"), "stop_max_wait_minutes": 2,
            "pause_price_per_min": D("0.300"), "arrival_free_minutes": 2, "pause_max_minutes": 10,
        },
        "comfort": {
            "stop_fee": D("3"), "stop_free_minutes": 1, "stop_price_per_min": D("0.300"), "stop_max_wait_minutes": 2,
            "pause_price_per_min": D("0.600"), "arrival_free_minutes": 2, "pause_max_minutes": 10,
        },
    },
}

SERVICE: dict[CountryCode, dict[str, Any]] = {
    CountryCode.DZ: {
        "guarantee_fee": D("120"), "parcel_fee": D("60"), "parcel_fetch_fee": D("60"), "hourly_rate": D("1000"),
        "commute_captain_incentive": D("30"), "commute_discount_percent": D("10"), "cashback_amount": D("130"),
    },
    CountryCode.LY: {
        "guarantee_fee": D("3"), "parcel_fee": D("2"), "parcel_fetch_fee": D("2"), "hourly_rate": D("24"),
        "commute_captain_incentive": D("1"), "commute_discount_percent": D("10"), "cashback_amount": D("3"),
    },
}

PAYMENT: dict[CountryCode, dict[str, Any]] = {
    CountryCode.DZ: {"driver_debt_ceiling": D("650"), "tip_preset_small": D("50"), "tip_preset_medium": D("100"), "tip_max": D("500")},
    CountryCode.LY: {"driver_debt_ceiling": D("15")},
}

#: **التقريب**: الجزائرُ إلى أقرب 10 د.ج (نصُّ المالك)، وليبيا إلى دينارٍ كامل (§٧٤-د)
ROUNDING: dict[CountryCode, tuple[Decimal, str]] = {
    CountryCode.DZ: (D("10"), "nearest"),
    CountryCode.LY: (D("1"), "nearest"),
}

WALLET: dict[CountryCode, dict[str, Any]] = {
    CountryCode.DZ: {
        "transfer_daily_limit": D("25000"), "transfer_monthly_limit": D("250000"),
        "min_withdrawal_amount": D("1000"), "withdrawal_reserve_amount": D("500"),
    },
    CountryCode.LY: {"withdrawal_reserve_amount": D("15")},
}

ADVANCE: dict[CountryCode, dict[str, Any]] = {CountryCode.LY: {"min_kept_amount": D("3")}}

#: نوعُ الإحالة ← حقولها
REFERRAL: dict[CountryCode, dict[str, dict[str, Any]]] = {
    CountryCode.LY: {
        "driver": {"reward_amount": D("15"), "female_bonus_amount": D("3")},
        "rider": {"reward_amount": D("6"), "female_bonus_amount": D("2")},
    },
}

#: **مطاراتُ الجزائر الثلاثة** — مستطيلٌ تقريبيٌّ حول كلٍّ `[[lng, lat], …]` (يُعدَّل رسمُه من اللوحة)، ورسمُه 130 د.ج
DZ_AIRPORTS: tuple[tuple[str, list[list[float]]], ...] = (
    ("مطار الجزائر الدولي هواري بومدين", [[3.180, 36.675], [3.245, 36.675], [3.245, 36.705], [3.180, 36.705]]),
    ("مطار وهران الدولي أحمد بن بلة", [[-0.645, 35.610], [-0.595, 35.610], [-0.595, 35.640], [-0.645, 35.640]]),
    ("مطار قسنطينة الدولي محمد بوضياف", [[6.600, 36.262], [6.645, 36.262], [6.645, 36.290], [6.600, 36.290]]),
)
AIRPORT_FEE: dict[CountryCode, Decimal] = {CountryCode.DZ: D("130"), CountryCode.LY: D("3")}

CARDS: dict[CountryCode, tuple[Decimal, ...]] = {CountryCode.DZ: (D("500"), D("1000"), D("2000"), D("5000"))}


class Plan:
    """**ما سيُكتب وما بقي** — يُطبع في المعاينة والكتابة بالشكل نفسِه."""

    def __init__(self, out: Callable[[str], None]) -> None:
        self.out = out
        self.written = 0
        self.kept = 0

    def fill(self, row: Any, where: str, values: dict[str, Any]) -> list[str]:
        touched = []
        for name, value in values.items():
            current = getattr(row, name)
            if current is None or current == 0:
                setattr(row, name, value)
                touched.append(name)
                self.written += 1
                self.out(f"  ✎ {where} · {name}: {current} ← {value}")
            elif current != value:
                self.kept += 1
                self.out(f"  = {where} · {name}: {current} قائمٌ — لم يُمسّ (الجدول {value})")
        return touched


async def _audit(session: AsyncSession, country: CountryCode, table: str, fields: list[str]) -> None:
    if fields:
        await audit.record(
            session,
            actor=None,
            action=AuditAction.UPDATE,
            entity_type="market_amounts_74",
            details={"country_code": country.value, "table": table, "fields": sorted(fields)},
        )


async def apply(session: AsyncSession, out: Callable[[str], None] = print) -> Plan:
    plan = Plan(out)
    now = datetime.now(UTC)
    for country in (CountryCode.DZ, CountryCode.LY):
        out(f"== {country.value}")
        await money_guards.require_pricing_writes(session, actor=None, country_code=country)

        for category, values in PRICING[country].items():
            rule = await session.scalar(
                select(PricingRule).where(PricingRule.country_code == country, PricingRule.vehicle_category == category)
            )
            if rule is None:
                missing = {"base_fare", "price_per_km", "price_per_min", "minimum_fare", "cancellation_fee"} - set(values)
                if missing:
                    raise SystemExit(f"✗ لا تسعيرةَ {category} في {country.value} والجدولُ لا يملأ {sorted(missing)} — يُوقَف")
                rule = PricingRule(country_code=country, vehicle_category=category, **values)
                session.add(rule)
                out(f"  ✚ pricing_rules · {category}: صفٌّ جديد")
                plan.written += len(values)
                await _audit(session, country, f"pricing_rules.{category}", list(values))
            else:
                await _audit(session, country, f"pricing_rules.{category}", plan.fill(rule, f"pricing_rules.{category}", values))

        service = await session.scalar(select(ServiceSetting).where(ServiceSetting.country_code == country))
        if service is None:
            service = ServiceSetting(country_code=country)
            session.add(service)
            await session.flush()
            out("  ✚ service_settings: صفٌّ جديدٌ بافتراضاته")
        await _audit(session, country, "service_settings", plan.fill(service, "service_settings", SERVICE[country]))

        payment = await settings_service.get_or_create_payment_settings(session, country)
        touched = plan.fill(payment, "payment_settings", PAYMENT[country])
        unit, mode = ROUNDING[country]
        if not payment.rounding_enabled:
            payment.rounding_enabled, payment.rounding_unit, payment.rounding_mode = True, unit, mode
            payment.rounding_enabled_at = now
            touched += ["rounding_enabled", "rounding_unit", "rounding_mode", "rounding_enabled_at"]
            plan.written += 1
            out(f"  ✎ payment_settings · التقريب: مطفأ ← مشتعلٌ إلى أقرب {unit} ({mode})")
        elif (payment.rounding_unit, payment.rounding_mode) != (unit, mode):
            plan.kept += 1
            out(f"  = payment_settings · التقريب: {payment.rounding_unit} {payment.rounding_mode} قائمٌ — لم يُمسّ")
        await _audit(session, country, "payment_settings", touched)

        wallet_row = await settings_service.get_or_create_wallet_settings(session, country)
        await _audit(session, country, "wallet_settings", plan.fill(wallet_row, "wallet_settings", WALLET[country]))

        if country in ADVANCE:
            advance = await session.scalar(select(AdvanceSetting).where(AdvanceSetting.country_code == country))
            if advance is None:
                raise SystemExit(f"✗ لا إعداداتِ سلفةٍ في {country.value} — يُوقَف")
            await _audit(session, country, "advance_settings", plan.fill(advance, "advance_settings", ADVANCE[country]))

        for kind, values in REFERRAL.get(country, {}).items():
            referral = await session.scalar(
                select(ReferralSetting).where(ReferralSetting.country_code == country, ReferralSetting.referral_type == kind)
            )
            if referral is None:
                raise SystemExit(f"✗ لا إعدادَ إحالة {kind} في {country.value} — يُوقَف")
            await _audit(session, country, f"referral_settings.{kind}", plan.fill(referral, f"referral_settings.{kind}", values))

        existing = {
            row.name: row
            for row in await session.scalars(
                select(Facility).where(Facility.country_code == country, Facility.kind == FACILITY_AIRPORT)
            )
        }
        for row in existing.values():
            await _audit(session, country, "facilities", plan.fill(row, f"facilities «{row.name}»", {"fee": AIRPORT_FEE[country]}))
        if country is CountryCode.DZ:
            for name, area in DZ_AIRPORTS:
                if name in existing:
                    continue
                await facilities.create(session, country_code=country, name=name, area=area, fee=AIRPORT_FEE[country], is_active=True)
                plan.written += 1
                out(f"  ✚ facilities «{name}»: رسمُ {AIRPORT_FEE[country]}")
                await _audit(session, country, "facilities", ["name", "area", "fee"])

        if country in CARDS:
            have = set(await session.scalars(select(CardDenomination.amount).where(CardDenomination.country_code == country)))
            added = [amount for amount in CARDS[country] if amount not in have]
            for amount in added:
                session.add(CardDenomination(country_code=country, amount=amount, is_active=True))
                plan.written += 1
                out(f"  ✚ card_denominations: {amount}")
            await _audit(session, country, "card_denominations", ["amount"] if added else [])
        await session.flush()
    return plan


async def main_async(*, write: bool, session_factory: Callable[[], AsyncSession] = SessionLocal) -> Plan:
    async with session_factory() as session:
        plan = await apply(session)
        print(f"— {plan.written} يُكتب · {plan.kept} قائمٌ لم يُمسّ")
        if write:
            await session.commit()
            print("✓ كُتب والتُزم")
        else:
            await session.rollback()
            print("معاينةٌ — لم يُكتب شيء (أعد بـ--apply)")
        return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="مبالغُ الجزائر وليبيا (SPEC §74-د)")
    parser.add_argument("--apply", action="store_true", help="اكتب والتزم — وبدونه معاينةٌ لا تكتب")
    args = parser.parse_args(argv)
    asyncio.run(main_async(write=args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
