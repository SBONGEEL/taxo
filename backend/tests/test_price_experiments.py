"""**تجاربُ الأسعار** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٤، SPEC §٩٧/٤).

مطفأً لا تُسعِّر تجربةٌ «تعمل» رحلةً · مشتعلاً يرى راكبُ ذراع التجربة نسبتَها في التقدير والطلب سطراً بذاته · النطاقُ يحكم · لا شيءَ يعمل
قبل «ابدأ» · الانتقالاتُ بحالها · «تطبيقُ الفائز» يضرب تسعيرةَ الدولة في النسبة مرّةً، ولا يصحّ لتجربةٍ على جزءٍ من الدولة.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import CountryCode, FeatureKey
from app.models.pricing import PricingRule
from app.models.ride import Ride
from tests.helpers import DROPOFF, PICKUP, enable_features, request_ride, rider_session


async def _make(client: AsyncClient, headers: dict, **extra) -> dict:
    body = {"name": "تجربة", "adjust_percent": "10", "share_percent": 100, "days": 7, **extra}
    answer = await client.post("/admin/price-experiments", params={"country_code": "JO"}, json=body, headers=headers)
    assert answer.status_code == 201, answer.text
    return answer.json()


async def _move(client: AsyncClient, headers: dict, experiment: dict, action: str):
    return await client.post(f"/admin/price-experiments/{experiment['id']}/{action}", headers=headers)


async def _estimate(client: AsyncClient, rider: dict) -> Decimal:
    answer = await client.post(
        "/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}, headers=rider["headers"]
    )
    assert answer.status_code == 200, answer.text
    return Decimal(answer.json()["estimated_fare"])


async def test_nothing_runs_off_or_before_start(client: AsyncClient, session_factory, jordan_settings: None, admin_headers: dict) -> None:
    rider = await rider_session(client)
    plain = await _estimate(client, rider)
    experiment = await _make(client, admin_headers)
    assert experiment["status"] == "draft"
    # **مسوّدةٌ ومفتاحٌ مشتعل** ⇐ لا أثر
    await enable_features(session_factory, FeatureKey.PRICE_EXPERIMENTS_ENABLED.value)
    assert await _estimate(client, rider) == plain
    # **تعمل والمفتاحُ مطفأ** ⇐ لا أثر
    assert (await _move(client, admin_headers, experiment, "start")).json()["status"] == "running"
    async with session_factory() as session:
        from app.models.feature_flag import FeatureFlag

        for flag in await session.scalars(
            select(FeatureFlag).where(FeatureFlag.feature_key == FeatureKey.PRICE_EXPERIMENTS_ENABLED.value)
        ):
            flag.enabled = False
        await session.commit()
    assert await _estimate(client, rider) == plain


async def test_a_test_arm_rider_sees_the_percent_in_the_estimate_and_the_ride(
    client: AsyncClient, session_factory, jordan_settings: None, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    plain = await _estimate(client, rider)
    experiment = await _make(client, admin_headers)
    await enable_features(session_factory, FeatureKey.PRICE_EXPERIMENTS_ENABLED.value)
    await _move(client, admin_headers, experiment, "start")

    priced = await _estimate(client, rider)
    assert priced == plain + (plain * Decimal("0.10")).quantize(Decimal("0.001"))
    ride = await request_ride(client, rider["headers"])
    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        assert row.price_experiment_id == uuid.UUID(experiment["id"])
        assert row.price_experiment_arm == "test"
        assert row.estimated_fare == priced
        assert [line["kind"] for line in row.fare_lines][-1] == "experiment"
        assert sum(Decimal(line["amount"]) for line in row.fare_lines) == row.estimated_fare

    listed = (await client.get("/admin/price-experiments", params={"country_code": "JO"}, headers=admin_headers)).json()
    arms = {arm["arm"]: arm for arm in listed[0]["arms"]}
    assert arms["test"]["requests"] == 1 and arms["control"]["requests"] == 0


async def test_an_area_experiment_leaves_riders_outside_it_alone(
    client: AsyncClient, session_factory, jordan_settings: None, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    plain = await _estimate(client, rider)
    # **دائرةٌ في العقبة** — والانطلاقُ في عمّان
    experiment = await _make(client, admin_headers, center_lat=29.53, center_lng=35.0, radius_km="5")
    await enable_features(session_factory, FeatureKey.PRICE_EXPERIMENTS_ENABLED.value)
    await _move(client, admin_headers, experiment, "start")
    assert await _estimate(client, rider) == plain
    # **ولا يُطبَّق على الدولة كلِّها**
    applied = await _move(client, admin_headers, experiment, "apply")
    assert applied.status_code == 422, applied.text


async def test_transitions_and_applying_the_winner(
    client: AsyncClient, session_factory, jordan_settings: None, admin_headers: dict
) -> None:
    experiment = await _make(client, admin_headers, adjust_percent="-20")
    assert (await _move(client, admin_headers, experiment, "stop")).status_code == 409
    assert (await _move(client, admin_headers, experiment, "start")).status_code == 200
    assert (await _move(client, admin_headers, experiment, "start")).status_code == 409
    assert (await _move(client, admin_headers, experiment, "stop")).json()["status"] == "stopped"
    await enable_features(session_factory, FeatureKey.PRICING_WRITES_ENABLED.value)
    done = await _move(client, admin_headers, experiment, "apply")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "applied"
    async with session_factory() as session:
        rule = await session.scalar(
            select(PricingRule).where(PricingRule.country_code == CountryCode.JO, PricingRule.vehicle_category == "economy")
        )
        assert rule.base_fare == Decimal("0.800")
        assert rule.price_per_km == Decimal("0.400")
        assert rule.minimum_fare == Decimal("1.600")
    assert (await _move(client, admin_headers, experiment, "cancel")).status_code == 409


async def test_bad_percents_are_refused(client: AsyncClient, admin_headers: dict) -> None:
    for percent in ("0", "60", "-51"):
        answer = await client.post(
            "/admin/price-experiments",
            params={"country_code": "JO"},
            json={"name": "تجربة", "adjust_percent": percent, "share_percent": 50, "days": 7},
            headers=admin_headers,
        )
        assert answer.status_code == 422, (percent, answer.text)
