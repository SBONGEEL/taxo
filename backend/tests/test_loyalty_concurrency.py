"""**تزامنُ استبدال النقاط** (البند ١٤) — `loyalty.redeem` يأخذ قفلَ المحفظة الاستشاريَّ **قبل** قراءة رصيد النقاط.

**يسقط بحذف القفل**: يقرأ استبدالان رصيداً يسع واحداً معاً فيُصرف الرصيدُ مرّتين — ولا يمسكه قفلُ `wallet.record` لأنه بعد القراءة.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import FeatureKey, WalletTransactionType
from app.models.wallet import WalletTransaction
from app.services import loyalty
from tests.helpers import NEAR_PICKUP, approved_driver, bring_online, completed_ride, enable_features, rider_session


async def test_two_redeems_at_once_pay_once(client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict, monkeypatch) -> None:
    await client.put(
        "/admin/loyalty",
        params={"country_code": "JO"},
        json={"points_per_ride": 10, "expiry_days": 180, "silver_threshold": 100, "gold_threshold": 200, "silver_bonus_percent": 0,
              "gold_bonus_percent": 0, "redeem_points": 10, "redeem_value": "0.500"},
        headers=admin_headers,
    )
    await enable_features(session_factory, FeatureKey.LOYALTY_ENABLED.value, FeatureKey.WALLET_ENABLED.value)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver, NEAR_PICKUP)
    rider = await rider_session(client)
    await completed_ride(client, rider["headers"], driver)
    async with session_factory() as session:
        await loyalty.sweep(session)

    # **التداخلُ مفروضٌ لا مأمول**: الأوّلُ يبقي معاملته مفتوحةً بعد قراءة الرصيد، فيبدأ الثاني وهو في منتصفه
    real = loyalty.balance

    async def slow(session, rider_id, now=None):
        found = await real(session, rider_id, now)
        await asyncio.sleep(0.4)
        return found

    monkeypatch.setattr(loyalty, "balance", slow)

    async def redeem() -> int:
        return (await client.post("/loyalty/me/redeem", json={"blocks": 1}, headers=rider["headers"])).status_code

    codes = await asyncio.wait_for(asyncio.gather(redeem(), redeem()), timeout=30)
    assert Counter(codes) == Counter({200: 1, 409: 1})
    async with session_factory() as session:
        paid = await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.owner_id == uuid.UUID(rider["user"]["id"]),
                WalletTransaction.type == WalletTransactionType.LOYALTY_REWARD,
            )
        )
        assert paid == 1
