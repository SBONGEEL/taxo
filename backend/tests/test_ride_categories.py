"""فئاتُ الرحلة من اللوحة (SPEC §٦٧-ب/٩) — **وكلٌّ يسقط بحذف ما يحرسه**.

- **«اقتصادي» و«مريحة» كما اليوم**: تُطلبان وتُعرضان وكباتنُهما هم.
- **فئةٌ جديدةٌ تولد مطفأة**: لا تُرى ولا تُطلب، **ولا تُشعَل بلا أسعارٍ موجبة**، ولا يصير سعرُها صفراً وهي مشتعلة.
- **مشتعلةً**: تُرى في `/config` بوجهها، **وتُسعَّر من صفِّها وحدَه**، وتُطلب وتُقبل وتُنهى.
- **من يأخذها**: من تستوفي مركبتُه شروطَها، أو مُنحها — **ومن لا يستوفيها لا يصله طلبُها أبداً**، **ومن نُزعت منه لا تصله ولو استوفاها**.
- **إطفاؤها يخفيها ويرفض الجديد، ورحلتُها الجارية تكمل.**
- **تزامن**: منحٌ ونزعٌ لكبتنٍ واحدٍ معاً ⇒ صفٌّ واحدٌ متّسق.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import CountryCode
from app.models.pricing import PricingRule
from app.models.ride_category import DriverCategoryAccess
from app.services import dispatch
from tests.helpers import DRIVER, DROPOFF, PICKUP, approved_driver, bring_online, rider_session, wait_for_offer

pytestmark = pytest.mark.usefixtures("jordan_settings")

FAMILY = {"country_code": "JO", "key": "family", "name": "عائلية", "icon": "airport_shuttle", "description": "سبعة مقاعد",
          "seats": 7, "min_seats": 7}


async def _family(client: AsyncClient, admin_headers: dict, **fields) -> dict:
    created = await client.post("/admin/settings/ride-categories", json=FAMILY | fields, headers=admin_headers)
    assert created.status_code == 201, created.text
    assert created.json()["is_active"] is False
    return created.json()


async def _price(session_factory, key: str = "family", base: str = "3.000") -> None:
    async with session_factory() as session:
        session.add(PricingRule(country_code=CountryCode.JO, vehicle_category=key, base_fare=Decimal(base),
                                price_per_km=Decimal("0.800"), price_per_min=Decimal("0.200"),
                                minimum_fare=Decimal("4.000"), cancellation_fee=Decimal("1.000")))
        await session.commit()


async def _activate(client, admin_headers, category_id: str, on: bool = True):
    return await client.patch(f"/admin/settings/ride-categories/{category_id}", json={"is_active": on}, headers=admin_headers)


async def _jordan(client: AsyncClient, headers: dict) -> dict:
    body = (await client.get("/config", headers=headers)).json()
    return next(country for country in body["countries"] if country["country_code"] == "JO")


async def _config_keys(client: AsyncClient, headers: dict) -> list[str]:
    return [row["key"] for row in (await _jordan(client, headers))["ride_categories"]]


async def _eligible(session_factory, driver_id: str, key: str = "family") -> bool:
    async with session_factory() as session:
        levels = await dispatch._eligible_levels(session, [uuid.UUID(str(driver_id))], key, country=CountryCode.JO)
        return uuid.UUID(str(driver_id)) in levels


async def test_builtins_stay_as_today_and_a_new_category_is_born_off_unpriced_and_unrequestable(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    rider = (await rider_session(client))["headers"]
    assert await _config_keys(client, rider) == ["economy", "comfort"]

    family = await _family(client, admin_headers)
    assert await _config_keys(client, rider) == ["economy", "comfort"]
    refused = await client.post("/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "family"},
                                headers=rider)
    assert refused.status_code == 403 and refused.json()["code"] == "category_unavailable"

    # **لا تُشعَل بلا أسعار، ولا بسعرٍ صفر**
    unpriced = await _activate(client, admin_headers, family["id"])
    assert unpriced.status_code == 422
    await _price(session_factory, base="0.000")
    zero = await _activate(client, admin_headers, family["id"])
    assert zero.status_code == 422 and "صفر" in zero.json()["message"]
    # **ولا تُنشأ مدمجةٌ ثانيةٌ بمفتاحها**
    builtin = await client.post("/admin/settings/ride-categories", json=FAMILY | {"key": "economy"}, headers=admin_headers)
    assert builtin.status_code == 422


async def test_an_active_category_is_shown_priced_from_its_own_row_and_cannot_drop_to_a_zero_price(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    family = await _family(client, admin_headers)
    await _price(session_factory)
    on = await _activate(client, admin_headers, family["id"])
    assert on.status_code == 200 and on.json()["is_active"] is True

    rider = (await rider_session(client))["headers"]
    body = await _jordan(client, rider)
    assert body["vehicle_categories"] == ["economy", "comfort", "family"]
    face = next(row for row in body["ride_categories"] if row["key"] == "family")
    assert face == {"key": "family", "name": "عائلية", "icon": "airport_shuttle", "description": "سبعة مقاعد", "seats": 7}

    route = {"pickup": PICKUP, "dropoff": DROPOFF}
    economy = (await client.post("/rides/estimate", json=route | {"vehicle_category": "economy"}, headers=rider)).json()
    fam = (await client.post("/rides/estimate", json=route | {"vehicle_category": "family"}, headers=rider)).json()
    assert Decimal(fam["priced_fare"]) > Decimal(economy["priced_fare"])
    lines = {line["kind"]: Decimal(line["amount"]) for line in fam.get("fare_lines") or []}
    if lines:
        assert lines["base"] == Decimal("3.000")

    async with session_factory() as session:
        rule_id = await session.scalar(select(PricingRule.id).where(PricingRule.vehicle_category == "family"))
    zeroed = await client.patch(f"/admin/settings/pricing/{rule_id}", json={"base_fare": "0.000"}, headers=admin_headers)
    assert zeroed.status_code == 422


async def test_only_a_qualifying_or_granted_captain_gets_it_and_a_revoked_one_never_does(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    family = await _family(client, admin_headers)
    await _price(session_factory)
    await _activate(client, admin_headers, family["id"])
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    driver_id = str(driver["driver_id"])

    # مركبةٌ لم تُراجَع صفاتُها لا تستوفي «سبعة مقاعد» — **ولا تصلها العائلية**؛ والاقتصاديُّ كما كان
    assert not await _eligible(session_factory, driver_id)
    assert await _eligible(session_factory, driver_id, "economy")

    vehicles = (await client.get(f"/admin/drivers/{driver_id}/vehicles", headers=admin_headers)).json()
    attrs = await client.patch(f"/admin/drivers/{driver_id}/vehicles/{vehicles[0]['id']}/attributes",
                               json={"body_type": "minivan", "seats": 7}, headers=admin_headers)
    assert attrs.status_code == 200 and attrs.json()["seats"] == 7
    assert await _eligible(session_factory, driver_id)

    revoke = await client.put(f"/admin/settings/ride-categories/{family['id']}/access",
                              json={"driver_id": driver_id, "granted": False, "reason": "شكوى عائلة"}, headers=admin_headers)
    assert revoke.status_code == 200 and revoke.json()[0]["granted"] is False
    assert not await _eligible(session_factory, driver_id)

    # **والمنحُ يوصلها لمن لا يستوفيها**
    await client.patch(f"/admin/drivers/{driver_id}/vehicles/{vehicles[0]['id']}/attributes",
                       json={"body_type": None, "seats": None}, headers=admin_headers)
    grant = await client.put(f"/admin/settings/ride-categories/{family['id']}/access",
                             json={"driver_id": driver_id, "granted": True, "reason": "مركبةٌ عائليّة رُوجعت هاتفيّاً"},
                             headers=admin_headers)
    assert grant.status_code == 200
    assert await _eligible(session_factory, driver_id)


async def test_a_family_ride_is_requested_accepted_and_completed_then_switching_off_hides_it_without_breaking_it(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    family = await _family(client, admin_headers)
    await _price(session_factory)
    await _activate(client, admin_headers, family["id"])
    driver = await approved_driver(client, session_factory, DRIVER)
    await client.put(f"/admin/settings/ride-categories/{family['id']}/access",
                     json={"driver_id": str(driver["driver_id"]), "granted": True, "reason": "تجربة الفئة"}, headers=admin_headers)
    await bring_online(client, driver)
    rider = (await rider_session(client))["headers"]

    created = await client.post("/rides", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "family"},
                                headers=rider)
    assert created.status_code == 201, created.text
    ride = created.json()
    assert ride["vehicle_category"] == "family"
    for attempt in range(3):
        await wait_for_offer(ride["id"], driver["driver_id"])
        accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
        if accepted.status_code == 200 or accepted.json().get("code") != "ride_offer_expired" or attempt == 2:
            break
    assert accepted.status_code == 200, accepted.text

    # **الإطفاءُ والرحلةُ جارية**: تختفي من `/config` ويُرفض الجديد، **وهذه تكمل**
    off = await _activate(client, admin_headers, family["id"], on=False)
    assert off.status_code == 200
    assert "family" not in await _config_keys(client, rider)
    for step in ("arrive", "start", "complete"):
        done = await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])
        assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed" and done.json()["vehicle_category"] == "family"
    again = await client.post("/rides", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "family"}, headers=rider)
    assert again.status_code == 403 and again.json()["code"] == "category_unavailable"


async def test_a_grant_and_a_revoke_at_once_leave_one_coherent_row(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    family = await _family(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    url = f"/admin/settings/ride-categories/{family['id']}/access"
    results = await asyncio.wait_for(
        asyncio.gather(
            client.put(url, json={"driver_id": str(driver["driver_id"]), "granted": True, "reason": "منحٌ يدويّ"}, headers=admin_headers),
            client.put(url, json={"driver_id": str(driver["driver_id"]), "granted": False, "reason": "نزعٌ يدويّ"}, headers=admin_headers),
        ),
        timeout=20,
    )
    assert [r.status_code for r in results] == [200, 200]
    async with session_factory() as session:
        rows = (await session.scalars(select(DriverCategoryAccess))).all()
        assert len(rows) == 1
        assert await session.scalar(select(func.count()).select_from(DriverCategoryAccess)) == 1


async def test_a_grant_waits_for_the_captain_row_lock(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    """**القفلُ نفسُه مقيس** — من يمسك صفَّ الكبتن (إيقافٌ أو تعديلُ مركبة) يجعل المنحَ ينتظره، فلا يكتب أحدُهما فوق قراءةٍ قديمة."""
    from sqlalchemy import text

    family = await _family(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    async with session_factory() as holder:
        await holder.execute(text("SELECT id FROM drivers WHERE id = :d FOR NO KEY UPDATE"), {"d": str(driver["driver_id"])})
        pending = asyncio.create_task(
            client.put(f"/admin/settings/ride-categories/{family['id']}/access",
                       json={"driver_id": str(driver["driver_id"]), "granted": True, "reason": "منحٌ ينتظر القفل"},
                       headers=admin_headers)
        )
        await asyncio.sleep(1.0)
        assert not pending.done(), "المنحُ لم ينتظر قفلَ صفِّ الكبتن"
        await holder.rollback()
    response = await asyncio.wait_for(pending, timeout=20)
    assert response.status_code == 200 and response.json()[0]["granted"] is True
