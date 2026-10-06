"""تفصيلُ الأجرة سطراً سطراً (R10 — SPEC §٦٢-ج/٢٥).

**القاعدةُ الوحيدة التي تُحرس هنا**: مجموعُ الأسطر يساوي المبلغَ الذي بجانبها **حرفاً** — `estimated_fare` قبل الإنهاء،
و`final_fare` بعده (ومعه الانتظارُ والوقفات وإعادةُ الحساب حين ينحرف الطريق). **تفصيلٌ لا يُجمع إلى مبلغه أسوأُ من غيابه**:
يقرؤه الراكبُ حسابَ مالٍ فيجد خطأً لم يقع.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.pricing import PricingRule
from app.models.ride import Ride, RideStop
from app.services import pricing
from app.services.directions import Route
from tests.helpers import (
    DRIVER,
    EXPECTED_FARE,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    register,
    request_ride,
    started_ride,
)


def _rule(**values: str) -> PricingRule:
    base = {
        "base_fare": "1.000",
        "price_per_km": "0.500",
        "price_per_min": "0.100",
        "minimum_fare": "2.000",
        "stop_fee": "0.000",
    }
    base.update(values)
    return PricingRule(**{key: Decimal(value) for key, value in base.items()})


def _sum(lines) -> Decimal:
    return sum((line.amount for line in lines), Decimal(0))


def test_the_lines_add_up_to_the_fare_for_every_route() -> None:
    """ألفُ مسارٍ ومعدّلٍ عشوائيّ — **المجموعُ هو السعرُ حرفاً**، والسعرُ هو ما يعطيه `calculate_fare` كما كان."""
    rng = random.Random(62)
    for _ in range(1000):
        rule = _rule(
            base_fare=f"{rng.randint(0, 3000) / 1000:.3f}",
            price_per_km=f"{rng.randint(0, 999) / 1000:.3f}",
            price_per_min=f"{rng.randint(0, 333) / 1000:.3f}",
            minimum_fare=f"{rng.randint(0, 5000) / 1000:.3f}",
            stop_fee=f"{rng.randint(0, 900) / 1000:.3f}",
        )
        route = Route(
            distance_km=Decimal(f"{rng.randint(1, 60000) / 1000:.3f}"),
            duration_min=Decimal(f"{rng.randint(1, 9000) / 100:.2f}"),
        )
        stops = rng.randint(0, 3)
        fare, minimum_applied, lines = pricing.fare_breakdown(rule, route, stops)
        assert _sum(lines) == fare
        assert (fare, minimum_applied) == pricing.calculate_fare(rule, route, stops)
        assert all(line.amount != 0 for line in lines)
        assert all(line.amount == pricing.round_money(line.amount) for line in lines)


def test_the_minimum_is_its_own_line() -> None:
    """**جبرُ الحدّ الأدنى سطرٌ بنفسه** لا تعديلٌ صامتٌ في سطرٍ آخر."""
    fare, applied, lines = pricing.fare_breakdown(
        _rule(minimum_fare="5.000"), Route(distance_km=Decimal("1.000"), duration_min=Decimal("2.00"))
    )
    assert applied and fare == Decimal("5.000")
    assert [line.kind for line in lines] == ["base", "distance", "time", "minimum"]
    assert lines[-1].amount == Decimal("5.000") - Decimal("1.000") - Decimal("0.500") - Decimal("0.200")
    assert lines[1].quantity == Decimal("1.000") and lines[2].quantity == Decimal("2.00")


def test_the_rounding_residual_lands_on_a_variable_line() -> None:
    """الفرقُ بين «تقريب المجموع» و«مجموع المقرَّبات» يُحمَل على المسافة أو الزمن — لا على الأجرة الأساسية الثابتة."""
    # ٠٫٠٠٠٥ في المسافة و٠٫٠٠٠٥ في الزمن: كلٌّ يُقرَّب صعوداً (٠٫٠٠١ + ٠٫٠٠١)، ومجموعُهما ٠٫٠٠١ وحده
    rule = _rule(base_fare="1.000", price_per_km="0.001", price_per_min="0.001", minimum_fare="0.000")
    route = Route(distance_km=Decimal("0.5"), duration_min=Decimal("0.5"))
    fare, _, lines = pricing.fare_breakdown(rule, route)
    assert fare == Decimal("1.001")
    assert _sum(lines) == fare
    assert next(line for line in lines if line.kind == "base").amount == Decimal("1.000")


async def _rider(client: AsyncClient) -> dict:
    return auth(await register(client, RIDER))


async def _online_driver(client: AsyncClient, session_factory) -> dict:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    return driver


def _api_sum(ride: dict) -> Decimal:
    return sum((Decimal(line["amount"]) for line in ride["fare_lines"]), Decimal(0))


async def test_a_new_ride_carries_the_lines_of_its_estimate(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    ride = await request_ride(client, rider)
    assert ride["estimated_fare"] == EXPECTED_FARE
    assert [line["kind"] for line in ride["fare_lines"]] == ["base", "distance", "time"]
    assert _api_sum(ride) == Decimal(ride["estimated_fare"])
    # المبلغُ نصٌّ بثلاث خانات كبقية المال، والكمّيةُ كما قيست
    assert ride["fare_lines"][1] == {"kind": "distance", "amount": "5.000", "quantity": "10.000"}


async def test_the_completed_ride_lines_add_up_to_the_final_fare(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)
    assert ride["final_fare"] is not None
    assert _api_sum(ride) == Decimal(ride["final_fare"])


async def test_a_pause_becomes_its_own_line_and_the_sum_still_holds(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الوقفةُ غيرُ المخطَّطة سطرٌ مستقلّ — والمجموعُ `final_fare` حرفاً."""
    from app.models.pause import PAUSE_KIND_PAUSE, RidePause

    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider, driver)
    async with session_factory() as session:
        # **وقفةٌ منتهيةٌ عشرَ دقائق بسعرها المجمَّد** — كما يكتبها بابُ الوقوف نفسُه (`pauses._start` ثمّ الاستئناف)
        session.add(
            RidePause(
                ride_id=ride["id"],
                kind=PAUSE_KIND_PAUSE,
                started_at=datetime.now(UTC) - timedelta(minutes=12),
                ended_at=datetime.now(UTC) - timedelta(minutes=2),
                price_per_min_at_pause=Decimal("0.050"),
                free_minutes_at_pause=0,
            )
        )
        await session.commit()

    done = await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    assert done.status_code == 200, done.text
    body = done.json()
    pauses = [line for line in body["fare_lines"] if line["kind"] == "pause"]
    assert pauses and Decimal(pauses[0]["amount"]) == Decimal(body["pause_charge"]) > 0
    assert _api_sum(body) == Decimal(body["final_fare"])


async def test_a_ride_without_frozen_lines_shows_none_rather_than_inventing_them(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """رحلةٌ أقدمُ من العمود (`NULL`) تُنهى بلا تفصيل — **لا يُعاد بناؤه من تسعيرةٍ قد تغيّرت**."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider, driver)
    async with session_factory() as session:
        row = await session.get(Ride, ride["id"])
        row.fare_lines = None
        await session.commit()

    done = await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    assert done.status_code == 200, done.text
    assert done.json()["fare_lines"] == []


async def test_waiting_at_a_stop_is_a_line_and_the_sum_holds(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    from app.models.enums import FeatureKey
    from tests.helpers import enable_features

    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    async with session_factory() as session:
        for rule in (await session.scalars(select(PricingRule))).all():
            rule.stop_fee = Decimal("0.250")
            rule.stop_free_minutes = 3
            rule.stop_price_per_min = Decimal("0.100")
        await session.commit()

    stop = {"lat": 31.96, "lng": 35.92, "address": "محطة"}
    ride = await started_ride(client, rider, driver, stops=[stop])
    assert "stops" in [line["kind"] for line in ride["fare_lines"]]
    stop_id = ride["stops"][0]["id"]
    await client.post(f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"])
    async with session_factory() as session:
        row = await session.get(RideStop, stop_id)
        row.arrived_at = datetime.now(UTC) - timedelta(minutes=13)
        await session.commit()
    await client.post(f"/rides/{ride['id']}/stops/{stop_id}/resume", headers=driver["headers"])

    done = await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    assert done.status_code == 200, done.text
    body = done.json()
    waiting = [line for line in body["fare_lines"] if line["kind"] == "waiting"]
    assert waiting and Decimal(waiting[0]["amount"]) == Decimal("1.000")
    assert _api_sum(body) == Decimal(body["final_fare"])
