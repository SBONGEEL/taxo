"""**تزامنُ اشتراك الراكب** (البند ١٣) — قفلان، ولكلٍّ اختبارُه، **ويسقط كلٌّ بحذف قفله**:

١) **الشراء**: `rider_plans.purchase` يأخذ قفلَ المحفظة الاستشاريَّ **قبل** فحص «أله اشتراكٌ سارٍ؟». بلا هذا القفل يقرأ نقران «لا
   اشتراك» معاً فيُقتطع الثمنُ مرّتين — ولا يمسكه قفلُ `wallet.record` لأنه بعد الفحص.
٢) **الحدُّ الشهريّ**: `rider_plans.take_discount` يقفل صفَّ الاشتراك قبل قراءة ما خُصم. بلا القفل يقرأ إنهاءان «لم يُخصم شيء» معاً
   فيتجاوزان حدّاً يسع واحداً.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import FeatureKey, WalletTransactionType
from app.models.rider_plan import RiderPlanUse
from app.models.wallet import WalletTransaction
from app.services import rider_plans
from tests.helpers import enable_features, request_ride, rider_session, topup_wallet


async def _plan(client: AsyncClient, headers: dict) -> dict:
    answer = await client.post(
        "/admin/rider-plans",
        params={"country_code": "JO"},
        json={"name": "شهريّ", "days": 30, "price": "5.000", "discount_percent": "50", "per_ride_cap": "1.000",
              "monthly_cap": "1.000", "bearer": "taxo"},
        headers=headers,
    )
    assert answer.status_code == 201, answer.text
    return answer.json()


async def test_two_purchases_at_once_charge_once(client: AsyncClient, session_factory, admin_headers: dict, monkeypatch) -> None:
    plan = await _plan(client, admin_headers)
    await enable_features(session_factory, FeatureKey.RIDER_PLANS_ENABLED.value, FeatureKey.WALLET_ENABLED.value)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")

    # **التداخلُ مفروضٌ لا مأمول**: الأوّلُ يبقي معاملته مفتوحةً بعد الفحص، فيبدأ الثاني وهو في منتصفه
    real = rider_plans._latest_end

    async def slow(session, rider_id, now):
        found = await real(session, rider_id, now)
        await asyncio.sleep(0.4)
        return found

    monkeypatch.setattr(rider_plans, "_latest_end", slow)

    async def buy() -> int:
        return (await client.post(f"/rider-plans/{plan['id']}/subscribe", headers=rider["headers"])).status_code

    codes = await asyncio.wait_for(asyncio.gather(buy(), buy()), timeout=30)
    assert Counter(codes) == Counter({201: 1, 409: 1})
    async with session_factory() as session:
        paid = await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.owner_id == uuid.UUID(rider["user"]["id"]),
                WalletTransaction.type == WalletTransactionType.RIDER_PLAN_PAYMENT,
            )
        )
        assert paid == 1


async def test_two_discounts_at_once_stay_under_the_month_cap(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings: None, monkeypatch
) -> None:
    plan = await _plan(client, admin_headers)
    await enable_features(session_factory, FeatureKey.RIDER_PLANS_ENABLED.value, FeatureKey.WALLET_ENABLED.value)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "10.000")
    await client.post(f"/rider-plans/{plan['id']}/subscribe", headers=rider["headers"])
    # **رحلتان حقيقيّتان** (المفتاحُ الأجنبيّ) — تُطلب وتُلغى ثمّ تُطلب
    first = await request_ride(client, rider["headers"])
    await client.post(f"/rides/{first['id']}/cancel", json={}, headers=rider["headers"])
    second = await request_ride(client, rider["headers"])
    async with session_factory() as session:
        sub = await rider_plans.current(session, uuid.UUID(rider["user"]["id"]))
        sub_id = sub.id

    real_used = rider_plans.used

    async def slow_used(session, subscription_id, since=None):
        found = await real_used(session, subscription_id, since)
        await asyncio.sleep(0.4)
        return found

    monkeypatch.setattr(rider_plans, "used", slow_used)

    async def take(ride_id: str) -> Decimal:
        async with session_factory() as session:
            amount = await rider_plans.take_discount(
                session, subscription_id=sub_id, ride_id=uuid.UUID(ride_id), base=Decimal("4.000"), currency="JOD"
            )
            await session.commit()
            return amount

    amounts = await asyncio.wait_for(asyncio.gather(take(first["id"]), take(second["id"])), timeout=30)
    assert sorted(amounts) == [Decimal(0), Decimal("1.000")]
    async with session_factory() as session:
        total = await session.scalar(select(func.coalesce(func.sum(RiderPlanUse.amount), 0)))
        assert Decimal(total) == Decimal("1.000")
