"""**ورقةُ طلب الراكب الجديدة — المسارُ المرسومُ هو مسارُ الأجرة** (SPEC §١٠٢، أمرُ المالك ٢٠٢٦-١١-١٦).

ثلاثةُ ثوابت:
- **مطفأً** (الافتراض): لا شكلَ يُطلب ولو طلبه التطبيق — الورقةُ القديمةُ وما قبلها كما هي حرفاً (`test_route_line` يحرس الباقي).
- **مشتعلاً**: **نداءُ مسارٍ واحدٌ** يُسعَّر منه ويُرسم منه — فلا يفترق الخطُّ عن الأجرة، **والسعرُ والمسافةُ هما هما** بالشكل وبدونه.
- **ولا يُطلب الشكلُ إلا لمن طلبه** (`with_route`) — تقديراتُ الفئات الأخرى تبقى بلا حمولة.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.enums import FeatureKey
from app.services import directions

from tests import helpers

FLAG = FeatureKey.RIDER_ORDER_SHEET_V2.value
LINE = [[35.9106, 31.9539], [35.9150, 31.9560], [35.9200, 31.9600]]
BODY = {
    "pickup": {"lat": 31.9539, "lng": 35.9106},
    "dropoff": {"lat": 31.96, "lng": 35.92},
    "vehicle_category": "economy",
}

pytestmark = pytest.mark.usefixtures("jordan_settings")


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    seen: list[dict] = []

    async def fake_fetch(token, *waypoints, with_geometry=False, with_steps=False):
        seen.append({"with_geometry": with_geometry})
        return directions.Route(
            distance_km=Decimal("7.400"),
            duration_min=Decimal("16.00"),
            geometry=[list(point) for point in LINE] if with_geometry else None,
        )

    monkeypatch.setattr(directions, "fetch_route", fake_fetch)
    return seen


async def _estimate(client: AsyncClient, headers: dict, **extra) -> dict:
    response = await client.post("/rides/estimate", json={**BODY, **extra}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_switched_off_no_shape_is_asked_even_when_the_app_asks(client: AsyncClient, calls: list[dict]) -> None:
    rider = await helpers.rider_session(client)
    quote = await _estimate(client, rider["headers"], with_route=True)
    assert quote["route_geometry"] is None
    assert calls and all(call["with_geometry"] is False for call in calls)


async def test_switched_on_one_call_prices_and_draws_and_the_fare_does_not_move(
    client: AsyncClient, session_factory, calls: list[dict]
) -> None:
    rider = await helpers.rider_session(client)
    plain = await _estimate(client, rider["headers"])
    await helpers.enable_features(session_factory, FLAG)

    calls.clear()
    drawn = await _estimate(client, rider["headers"], with_route=True)

    # **نداءٌ واحد** — منه السعرُ ومنه الخطّ
    assert calls == [{"with_geometry": True}]
    assert drawn["route_geometry"] == LINE
    # **والأجرةُ لا تتحرّك** بالشكل: المسافةُ والزمنُ والسعرُ هي هي
    for field in ("distance_km", "duration_min", "estimated_fare", "priced_fare"):
        assert drawn[field] == plain[field], field


async def test_switched_on_without_asking_there_is_no_payload(
    client: AsyncClient, session_factory, calls: list[dict]
) -> None:
    rider = await helpers.rider_session(client)
    await helpers.enable_features(session_factory, FLAG)
    quote = await _estimate(client, rider["headers"])
    assert quote["route_geometry"] is None
    assert all(call["with_geometry"] is False for call in calls)
