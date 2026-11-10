"""**نقاطُ الولاء** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٤، SPEC §٩٧/١٤).

مطفأً لا تُكسب نقطة · مشتعلاً تكسب المكتملةُ مرّةً (الكنسُ يُعاد فلا يتكرّر) · المستوى يزيد ما يُكسب · المنتهي لا يُحسب · الاستبدالُ
يستهلك الأقدمَ ويضع رصيداً مرّة · ولا استبدالَ فوق الرصيد.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import FeatureKey
from app.models.loyalty import LoyaltyEarning
from app.services import loyalty
from tests.helpers import NEAR_PICKUP, approved_driver, bring_online, completed_ride, enable_features, rider_session, wallet_of

RULE = {"points_per_ride": 10, "expiry_days": 180, "silver_threshold": 20, "gold_threshold": 100, "silver_bonus_percent": 50,
        "gold_bonus_percent": 100, "redeem_points": 10, "redeem_value": "0.500"}


async def _rule(client: AsyncClient, headers: dict, **extra) -> dict:
    answer = await client.put("/admin/loyalty", params={"country_code": "JO"}, json={**RULE, **extra}, headers=headers)
    assert answer.status_code == 200, answer.text
    return answer.json()


async def _rides(client, session_factory, count: int) -> tuple[dict, list[dict]]:
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver, NEAR_PICKUP)
    rider = await rider_session(client)
    done = [await completed_ride(client, rider["headers"], driver) for _ in range(count)]
    return rider, done


async def _sweep(session_factory) -> int:
    async with session_factory() as session:
        return await loyalty.sweep(session)


async def test_off_earns_nothing_and_on_earns_once(client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict) -> None:
    await _rule(client, admin_headers)
    rider, _ = await _rides(client, session_factory, 1)
    assert await _sweep(session_factory) == 0
    await enable_features(session_factory, FeatureKey.LOYALTY_ENABLED.value, FeatureKey.WALLET_ENABLED.value)
    assert await _sweep(session_factory) == 1
    assert await _sweep(session_factory) == 0
    mine = (await client.get("/loyalty/me", headers=rider["headers"])).json()
    assert mine["points"] == 10 and mine["tier"] == "bronze" and mine["to_next"] == 10


async def test_tier_bonus_and_expiry(client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict) -> None:
    await _rule(client, admin_headers)
    await enable_features(session_factory, FeatureKey.LOYALTY_ENABLED.value, FeatureKey.WALLET_ENABLED.value)
    rider, _ = await _rides(client, session_factory, 3)
    await _sweep(session_factory)
    async with session_factory() as session:
        rows = (await session.scalars(select(LoyaltyEarning).where(LoyaltyEarning.rider_id == uuid.UUID(rider["user"]["id"])))).all()
        # **في الكنس نفسِه**: الأولى والثانية برونزيّ (١٠ + ١٠)، والثالثة فضّيّ (٢٠ ⇐ +٥٠٪ = ١٥)
        assert sorted(row.points for row in rows) == [10, 10, 15]
        # **المنتهي لا يُحسب**: تنتهي الخمسَ عشرة فيبقى عشرون
        max(rows, key=lambda row: row.points).expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()
    mine = (await client.get("/loyalty/me", headers=rider["headers"])).json()
    assert mine["points"] == 20


async def test_redeem_uses_points_once_and_credits_the_wallet(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    await _rule(client, admin_headers)
    await enable_features(session_factory, FeatureKey.LOYALTY_ENABLED.value, FeatureKey.WALLET_ENABLED.value)
    rider, _ = await _rides(client, session_factory, 2)
    await _sweep(session_factory)
    before = Decimal((await wallet_of(client, rider["headers"]))["balance"])
    done = await client.post("/loyalty/me/redeem", json={"blocks": 2}, headers=rider["headers"])
    assert done.status_code == 200, done.text
    assert done.json()["points"] == 0
    assert Decimal((await wallet_of(client, rider["headers"]))["balance"]) == before + Decimal("1.000")
    again = await client.post("/loyalty/me/redeem", json={"blocks": 1}, headers=rider["headers"])
    assert again.status_code == 409, again.text


async def test_redeem_value_follows_the_currency(client: AsyncClient, admin_headers: dict) -> None:
    answer = await client.put("/admin/loyalty", params={"country_code": "DZ"}, json={**RULE, "redeem_value": "10.5"}, headers=admin_headers)
    assert answer.status_code == 422, answer.text
