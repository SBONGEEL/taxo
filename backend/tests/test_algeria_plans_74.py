"""خططُ الجزائر وعرضُ إطلاقها (SPEC §٧٤-ل/٢) — **200 · 1,400 · 6,000 مفتوحة، والموقوفةُ هي الشهريّةُ نفسُها، والعرضُ بعمولةٍ صفر**."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.models.enums import CountryCode, SubscriptionDurationType
from app.models.subscription import SubscriptionPlan
from app.models.subscription_offer import SubscriptionOffer
from scripts import algeria_plans_74 as script

pytestmark = pytest.mark.asyncio


async def test_the_three_plans_open_and_the_launch_offer_is_free_with_zero_commission(session_factory) -> None:
    async with session_factory() as session:
        session.add(SubscriptionPlan(country_code=CountryCode.DZ, name="TAXO X30", duration_type=SubscriptionDurationType.MONTHLY,
                                     price=Decimal("6000"), currency=currency_for_country(CountryCode.DZ), is_active=False))
        await session.commit()
    preview = await script.main_async(write=False, session_factory=session_factory)
    assert any("1,400" in line for line in preview)
    await script.main_async(write=True, session_factory=session_factory)
    await script.main_async(write=True, session_factory=session_factory)
    async with session_factory() as session:
        plans = list(await session.scalars(select(SubscriptionPlan).where(SubscriptionPlan.country_code == CountryCode.DZ)))
        offers = list(await session.scalars(select(SubscriptionOffer).where(SubscriptionOffer.country_code == CountryCode.DZ)))
    assert sorted((p.duration_type.value, p.price, p.is_active) for p in plans) == [
        ("daily", Decimal("200"), True), ("monthly", Decimal("6000"), True), ("weekly", Decimal("1400"), True)]
    assert {p.name for p in plans} == {"TAXO X1 — يومي", "TAXO X7 — أسبوعي", "TAXO X30 — شهري"}
    [offer] = offers
    weekly = next(p for p in plans if p.duration_type is SubscriptionDurationType.WEEKLY)
    assert (offer.plan_id, offer.discount_value, offer.audience, offer.max_uses_per_driver, offer.commission_percent) == (
        weekly.id, Decimal("100"), "new_driver", 1, Decimal("0"))
