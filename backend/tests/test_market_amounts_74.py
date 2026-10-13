"""سكربتُ مبالغ السوقين المغلقين (SPEC §٧٤-د) — **يُملأ الصفرُ والفارغ، ولا يُمسّ رقمٌ قائم**.

١) **المعاينةُ لا تكتب** شيئاً.
٢) **الجزائرُ كاملة**: التسعيرتان، والخدمات، والتقريبُ إلى 10، والمحفظة، والمطاراتُ الثلاثة، وفئاتُ البطاقات.
٣) **ليبيا: صفرُها وحدَه** — أسعارُ الرحلة والبقشيشُ وحدودُ المحفظة كما هي، **ورقمٌ غيرُ صفريٍّ يخالف الجدولَ يبقى ويُقال**.
٤) **والتدقيقُ بأسماء الحقول لا مبالغها**، **وإعادةُ التشغيل لا تكتب شيئاً**.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.advance import AdvanceSetting
from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode
from app.models.facility import Facility
from app.models.payment_setting import PaymentSetting
from app.models.pricing import PricingRule
from app.models.referral import ReferralSetting
from app.models.service_setting import ServiceSetting
from app.models.taxo_card import CardDenomination
from app.models.wallet_setting import WalletSetting
from app.services import facilities
from scripts import market_amounts_74 as script

pytestmark = pytest.mark.asyncio

D = Decimal
LY = CountryCode.LY
DZ = CountryCode.DZ


async def _libya_as_on_production(session_factory) -> None:
    """**ليبيا كما قُرئت على الإنتاج** (٢٠٢٦-١٠-١٣): أسعارٌ قائمة وأصفارٌ في الوقوف والخدمات، وبلا سقفٍ ولا تقريب — **ورسمُ ضمانٍ 5
    مكتوبٌ بيدٍ** ليُقاس أن القائمَ لا يُمسّ."""
    async with session_factory() as session:
        for category, (base, km, minute, minimum, cancel) in {
            "economy": ("3", "1", "0.15", "5", "2"),
            "comfort": ("5", "1.5", "0.2", "8", "3"),
        }.items():
            session.add(
                PricingRule(
                    country_code=LY, vehicle_category=category, base_fare=D(base), price_per_km=D(km),
                    price_per_min=D(minute), minimum_fare=D(minimum), cancellation_fee=D(cancel),
                )
            )
        session.add(ServiceSetting(country_code=LY, guarantee_fee=D("5")))
        session.add(PaymentSetting(country_code=LY, tip_preset_small=D("1"), tip_preset_medium=D("2"), tip_max=D("10")))
        session.add(
            WalletSetting(
                country_code=LY, transfer_daily_limit=D("500"), transfer_monthly_limit=D("5000"), min_withdrawal_amount=D("50")
            )
        )
        session.add(AdvanceSetting(country_code=LY))
        session.add(ReferralSetting(country_code=LY, referral_type="driver", reward_amount=D("0"), required_rides=3))
        session.add(ReferralSetting(country_code=LY, referral_type="rider", reward_amount=D("0"), required_rides=1))
        await facilities.create(
            session, country_code=LY, name="مطار معيتيقة الدولي",
            area=[[13.26, 32.88], [13.30, 32.88], [13.30, 32.90], [13.26, 32.90]], fee=D("0"), is_active=True,
        )
        await session.commit()


async def test_the_script_fills_zeros_only_and_writes_algeria_whole(session_factory) -> None:
    await _libya_as_on_production(session_factory)

    # ── المعاينة: لا شيء ──
    preview = await script.main_async(write=False, session_factory=session_factory)
    assert preview.written > 0
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PricingRule).where(PricingRule.country_code == DZ)) == 0

    plan = await script.main_async(write=True, session_factory=session_factory)
    assert plan.kept == 1, "رسمُ الضمان الليبيُّ القائمُ (5) يبقى ويُقال"

    async with session_factory() as session:
        rules = {
            (row.country_code, row.vehicle_category): row for row in await session.scalars(select(PricingRule))
        }
        economy = rules[(DZ, "economy")]
        assert (economy.base_fare, economy.price_per_km, economy.minimum_fare, economy.pause_price_per_min) == (
            D("100"), D("40"), D("230"), D("15"),
        )
        assert rules[(DZ, "comfort")].cancellation_fee == D("130")
        # ليبيا: الصفرُ مُلئ، والقائمُ كما هو
        assert rules[(LY, "economy")].stop_fee == D("2") and rules[(LY, "economy")].base_fare == D("3")
        assert rules[(LY, "comfort")].pause_price_per_min == D("0.600") and rules[(LY, "comfort")].stop_free_minutes == 1

        services = {row.country_code: row for row in await session.scalars(select(ServiceSetting))}
        assert services[DZ].hourly_rate == D("1000") and services[DZ].cashback_amount == D("130")
        assert services[LY].guarantee_fee == D("5"), "القائمُ لا يُمسّ"
        assert services[LY].parcel_fee == D("2") and services[LY].hourly_rate == D("24")

        payments = {row.country_code: row for row in await session.scalars(select(PaymentSetting))}
        assert (payments[DZ].rounding_enabled, payments[DZ].rounding_unit, payments[DZ].rounding_enabled_at is not None) == (
            True, D("10"), True,
        )
        assert payments[DZ].driver_debt_ceiling == D("650") and payments[DZ].tip_max == D("500")
        assert (payments[LY].rounding_unit, payments[LY].driver_debt_ceiling, payments[LY].tip_max) == (D("1"), D("15"), D("10"))

        wallets = {row.country_code: row for row in await session.scalars(select(WalletSetting))}
        assert wallets[DZ].min_withdrawal_amount == D("1000") and wallets[DZ].withdrawal_reserve_amount == D("500")
        assert wallets[LY].withdrawal_reserve_amount == D("15") and wallets[LY].min_withdrawal_amount == D("50")

        assert (await session.scalar(select(AdvanceSetting).where(AdvanceSetting.country_code == LY))).min_kept_amount == D("3")
        referrals = {
            row.referral_type: row for row in await session.scalars(select(ReferralSetting).where(ReferralSetting.country_code == LY))
        }
        assert (referrals["driver"].reward_amount, referrals["rider"].female_bonus_amount) == (D("15"), D("2"))

        airports = {row.country_code: [] for row in await session.scalars(select(Facility))}
        for row in await session.scalars(select(Facility)):
            airports[row.country_code].append(row.fee)
        assert airports[DZ] == [D("130")] * 3 and airports[LY] == [D("3")]
        assert sorted(await session.scalars(select(CardDenomination.amount).where(CardDenomination.country_code == DZ))) == [
            D("500"), D("1000"), D("2000"), D("5000"),
        ]

        # ── التدقيق: أسماءُ حقولٍ لا مبالغ ──
        logs = list(await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "market_amounts_74")))
        assert logs and all(row.actor_id is None for row in logs)
        assert all(set(row.details) == {"country_code", "table", "fields"} for row in logs)

    # ── إعادةُ التشغيل: لا شيء يُكتب ──
    again = await script.main_async(write=True, session_factory=session_factory)
    assert again.written == 0
