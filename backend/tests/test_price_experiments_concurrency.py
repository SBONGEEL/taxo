"""**تزامنُ «تطبيق الفائز»** (البند ٤) — `price_experiments.move` يقفل صفَّ التجربة قبل فحص حالها.

**يسقط بحذف القفل**: بلا `with_for_update` في `price_experiments.locked` يقرأ نقران «موقوفة» معاً فيضرب كلٌّ منهما تسعيرةَ الدولة في
النسبة — **فتصير الأجرةُ مضروبةً مرّتين** ويُقال للمالك إن الفائزَ طُبِّق مرّة.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import CountryCode, FeatureKey
from app.models.pricing import PricingRule
from app.services import price_experiments
from tests.helpers import enable_features


async def test_two_applies_at_once_change_the_pricing_once(
    client: AsyncClient, session_factory, jordan_settings: None, admin_headers: dict, monkeypatch
) -> None:
    made = await client.post(
        "/admin/price-experiments",
        params={"country_code": "JO"},
        json={"name": "تجربة", "adjust_percent": "10", "share_percent": 100, "days": 7},
        headers=admin_headers,
    )
    experiment_id = made.json()["id"]
    await client.post(f"/admin/price-experiments/{experiment_id}/start", headers=admin_headers)
    await enable_features(session_factory, FeatureKey.PRICING_WRITES_ENABLED.value)

    # **التداخلُ مفروضٌ لا مأمول**: الأوّلُ يبقي معاملته مفتوحةً بعد قراءة الحال، فيبدأ الثاني وهو في منتصفه
    real_rules = price_experiments._country_rules

    async def slow_rules(session, country):
        await asyncio.sleep(0.4)
        return await real_rules(session, country)

    monkeypatch.setattr(price_experiments, "_country_rules", slow_rules)

    async def apply() -> int:
        return (await client.post(f"/admin/price-experiments/{experiment_id}/apply", headers=admin_headers)).status_code

    codes = await asyncio.wait_for(asyncio.gather(apply(), apply()), timeout=30)
    assert Counter(codes) == Counter({200: 1, 409: 1})
    async with session_factory() as session:
        rule = await session.scalar(
            select(PricingRule).where(PricingRule.country_code == CountryCode.JO, PricingRule.vehicle_category == "economy")
        )
        assert rule.base_fare == Decimal("1.100")
