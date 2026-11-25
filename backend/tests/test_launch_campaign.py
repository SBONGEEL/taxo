"""**حملةُ إطلاق الأردن** (§١١٤-ج، أمرُ المالك ٢٠٢٦-١١-٢٤ السادس) — مطفأةٌ لا تكتب، وقبل الإطلاق ٦٠ يوماً من يومه، وبعده ٧ من الاعتماد.

* **المنحةُ اشتراكٌ بصفر مالٍ وصفر عمولة**، يمرّ بـ`subscriptions._create` نفسِه فيُكتب أثرُه كأيِّ اشتراك.
* **ومسحان متزامنان يمنحان مرّةً**: المنحةُ تُفحص تحت قفل صفِّ الكبتن — وبدونه يكتب الثاني اشتراكاً ثانياً قبل أن يصطدم بقيد المنحة.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.driver import Driver
from app.models.enums import CountryCode, PaymentMethod
from app.models.launch_campaign import LaunchCampaignGrant
from app.models.subscription import DriverSubscription
from app.services import launch_campaign
from tests.helpers import DRIVER, approved_driver, ensure_plan

#: **هذه الوحدةُ تقيس افتراضاتِ الحملة** — فلا يُثبَّت يومُ الإطلاق في الماضي (`conftest._launched_market`)
CAMPAIGN_DEFAULTS = True


async def _campaign(client: AsyncClient, admin_headers: dict, **body) -> dict:
    response = await client.patch("/admin/launch-campaign", params={"country_code": "JO"}, json=body, headers=admin_headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _approved_at(session_factory, driver_id: uuid.UUID, moment: datetime) -> None:
    async with session_factory() as session:
        row = await session.get(Driver, driver_id)
        row.first_approved_at = moment
        await session.commit()


async def test_the_campaign_is_off_and_writes_nothing(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    view = (await client.get("/admin/launch-campaign", params={"country_code": "JO"}, headers=admin_headers)).json()
    assert view["enabled"] is False and view["launch_date"] == "2027-01-01"
    assert (view["pre_launch_free_days"], view["post_launch_free_days"]) == (60, 7)
    assert view["banner"] == "سجّل قبل الإطلاق واحصل على 60 يوماً مجاناً بدون عمولة — بعد الإطلاق 7 أيام فقط"
    await ensure_plan(session_factory)
    await approved_driver(client, session_factory)
    async with session_factory() as session:
        done = await launch_campaign.sweep(session, now=datetime(2027, 1, 2, tzinfo=UTC))
        await session.commit()
        grants = await session.scalar(select(func.count()).select_from(LaunchCampaignGrant))
    assert done == {} and grants == 0


async def test_before_and_after_launch_grant_sixty_and_seven_days_with_zero_commission(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    await ensure_plan(session_factory)
    launch = date.today() - timedelta(days=1)
    await _campaign(client, admin_headers, is_enabled=True, launch_date=launch.isoformat())
    # **بلا اشتراكٍ مدفوع** — فالمنحةُ تبدأ من يومها لا بعد اشتراكٍ قائم
    early = await approved_driver(client, session_factory, subscribed=False)
    late = await approved_driver(
        client, session_factory, {**DRIVER, "phone": "0792222299"}, plate_number="AMM-4243", subscribed=False
    )
    async with session_factory() as session:
        start = await launch_campaign.launch_at(session, await launch_campaign.get(session, CountryCode.JO))
    await _approved_at(session_factory, early["driver_id"], start - timedelta(days=3))
    await _approved_at(session_factory, late["driver_id"], start + timedelta(hours=2))

    # **قبل منتصف ليل الإطلاق لا شيء**
    async with session_factory() as session:
        assert await launch_campaign.sweep(session, now=start - timedelta(minutes=1)) == {}
        await session.commit()

    async with session_factory() as session:
        done = await launch_campaign.sweep(session, now=start + timedelta(hours=3))
        await session.commit()
    assert done["JO"] == 2
    async with session_factory() as session:
        rows = {
            grant.driver_id: (grant, await session.get(DriverSubscription, grant.subscription_id))
            for grant in (await session.scalars(select(LaunchCampaignGrant))).all()
        }
    pre_grant, pre_sub = rows[early["driver_id"]]
    post_grant, post_sub = rows[late["driver_id"]]
    assert pre_grant.kind == "pre" and pre_sub.starts_at >= start
    assert pre_sub.expires_at - pre_sub.starts_at == timedelta(days=60)
    assert post_grant.kind == "post" and post_sub.starts_at >= start + timedelta(hours=2)
    assert post_sub.expires_at - post_sub.starts_at == timedelta(days=7)
    for sub in (pre_sub, post_sub):
        assert sub.payment_method == PaymentMethod.PROMO
        assert sub.amount_paid == Decimal("0.000") and sub.commission_percent_at_purchase == Decimal("0")

    mine = (await client.get("/drivers/me/launch-campaign", headers=early["headers"])).json()
    assert mine["status"] == "granted" and mine["ack_required"] is True
    ack = await client.post("/drivers/me/launch-campaign/ack", headers=early["headers"])
    assert ack.status_code == 200
    mine = (await client.get("/drivers/me/launch-campaign", headers=early["headers"])).json()
    assert mine["ack_required"] is False


async def test_two_concurrent_sweeps_grant_once(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    await ensure_plan(session_factory)
    launch = date.today() - timedelta(days=1)
    await _campaign(client, admin_headers, is_enabled=True, launch_date=launch.isoformat())
    driver = await approved_driver(client, session_factory, subscribed=False)
    async with session_factory() as session:
        start = await launch_campaign.launch_at(session, await launch_campaign.get(session, CountryCode.JO))
    await _approved_at(session_factory, driver["driver_id"], start - timedelta(days=1))

    async def one() -> None:
        async with session_factory() as session:
            await launch_campaign.sweep(session, now=start + timedelta(hours=1))
            await session.commit()

    await asyncio.wait_for(asyncio.gather(one(), one(), one()), timeout=30)
    async with session_factory() as session:
        grants = await session.scalar(select(func.count()).select_from(LaunchCampaignGrant).where(
            LaunchCampaignGrant.driver_id == driver["driver_id"]))
        subs = await session.scalar(select(func.count()).select_from(DriverSubscription).where(
            DriverSubscription.driver_id == driver["driver_id"], DriverSubscription.payment_method == PaymentMethod.PROMO))
    assert grants == 1 and subs == 1
