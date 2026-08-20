"""شكلُ مسار الرحلة (البند ٨) — يُطلب مرةً، ويُقرأ للطرفين، ولا يُفشل شيئاً.

**والحقنُ في `directions.fetch_route` وحده** كبقية اختبارات المشروع: تظلّ قراءةُ
التوكن من عقود المزودين حقيقيةً ولا يقع نداءُ شبكة.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import RoutingFailed
from app.models.ride import Ride
from app.services import directions, route_line

from tests import helpers

LINE = [[35.9106, 31.9539], [35.9150, 31.9560], [35.9200, 31.9600]]

# قربَ نقطة انطلاق `helpers.request_ride` — وإلا لم يبلغه العرض
NEAR_PICKUP = {"lat": 31.9539, "lng": 35.9106}

pytestmark = pytest.mark.usefixtures("jordan_settings")


@pytest.fixture
def drawn(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """يسجّل كلَّ نداءٍ ويعيد مساراً بشكلٍ حين يُطلب الشكل."""
    calls: list[dict] = []

    async def fake_fetch(token, *waypoints, with_geometry=False, with_steps=False):
        calls.append({
            "points": len(waypoints),
            "with_geometry": with_geometry,
            "with_steps": with_steps,
        })
        return directions.Route(
            distance_km=Decimal("5.000"),
            duration_min=Decimal("12.00"),
            geometry=[list(point) for point in LINE] if with_geometry else None,
        )

    monkeypatch.setattr(directions, "fetch_route", fake_fetch)
    return calls


async def test_the_estimate_never_asks_for_the_shape(
    client: AsyncClient, drawn: list[dict]
) -> None:
    """مسارُ التسعير يبقى بلا شكل — يُنادى مع كل تحريكِ دبوس، وحمولتُه تُرسل
    لمن لم يطلب رحلةً بعد."""
    rider = await helpers.rider_session(client)
    response = await client.post(
        "/rides/estimate",
        json={
            "pickup": {"lat": 31.9539, "lng": 35.9106},
            "dropoff": {"lat": 31.96, "lng": 35.92},
            "vehicle_category": "economy",
        },
        headers=rider["headers"],
    )
    assert response.status_code == 200, response.text
    assert drawn, "لم يقع نداءُ مسارٍ أصلاً"
    assert all(call["with_geometry"] is False for call in drawn)


async def test_accepting_stores_the_shape_once(
    client: AsyncClient, session_factory, drawn: list[dict]
) -> None:
    """القبولُ يكتب الشكلَ على الرحلة، وقراءةٌ بعده لا تطلبه ثانيةً.

    **وهذا هو التجميد**: طلبٌ ثانٍ قد يعطي مساراً آخرَ (زحمةٌ تبدّلت) فيرى
    الراكبُ خطاً والكبتنُ غيرَه على رحلةٍ واحدة.
    """
    rider = await helpers.rider_session(client)
    driver = await helpers.approved_driver(client, session_factory)
    # الكبتنُ لا يدخل التوزيع بـ`is_online` وحده — أوّلُ بثِّ موقعٍ هو ما يُدخله
    await helpers.bring_online(client, driver, NEAR_PICKUP)
    ride = await helpers.accepted_ride(client, rider["headers"], driver)

    async with session_factory() as session:
        stored = await session.scalar(
            select(Ride.route_polyline).where(Ride.id == ride["id"])
        )
    assert stored is not None, "القبولُ لم يكتب الشكل"
    assert json.loads(stored) == LINE

    asked = sum(1 for call in drawn if call["with_geometry"])
    for _ in range(2):
        response = await client.get(
            f"/rides/{ride['id']}/route-line", headers=rider["headers"]
        )
        assert response.status_code == 200
        assert response.json()["points"] == LINE
    assert sum(1 for call in drawn if call["with_geometry"]) == asked, (
        "أُعيد طلبُ الشكل بعد كتابته — ومسارٌ ثانٍ يعني خطَّين على رحلةٍ واحدة"
    )


async def test_both_parties_read_it_and_a_stranger_does_not(
    client: AsyncClient, session_factory, drawn: list[dict]
) -> None:
    rider = await helpers.rider_session(client)
    driver = await helpers.approved_driver(client, session_factory)
    # الكبتنُ لا يدخل التوزيع بـ`is_online` وحده — أوّلُ بثِّ موقعٍ هو ما يُدخله
    await helpers.bring_online(client, driver, NEAR_PICKUP)
    ride = await helpers.accepted_ride(client, rider["headers"], driver)

    for headers in (rider["headers"], driver["headers"]):
        response = await client.get(
            f"/rides/{ride['id']}/route-line", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["points"] == LINE

    stranger = await helpers.rider_session(
        client, {**helpers.RIDER, "phone": "790009999", "name": "غريبٌ عن الرحلة"}
    )
    forbidden = await client.get(
        f"/rides/{ride['id']}/route-line", headers=stranger["headers"]
    )
    assert forbidden.status_code in (403, 404)


async def test_a_failed_provider_call_leaves_the_ride_alone(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """سقوطُ Mapbox لا يُفشل القبولَ ولا القراءة — والجوابُ قائمةٌ فارغة.

    خريطةٌ بلا خطٍّ أهونُ من رحلةٍ لا تُقبل.
    """

    async def failing(token, *waypoints, with_geometry=False, with_steps=False):
        if with_geometry:
            raise RoutingFailed()
        return directions.Route(
            distance_km=Decimal("5.000"), duration_min=Decimal("12.00")
        )

    monkeypatch.setattr(directions, "fetch_route", failing)
    rider = await helpers.rider_session(client)
    driver = await helpers.approved_driver(client, session_factory)
    # الكبتنُ لا يدخل التوزيع بـ`is_online` وحده — أوّلُ بثِّ موقعٍ هو ما يُدخله
    await helpers.bring_online(client, driver, NEAR_PICKUP)
    ride = await helpers.accepted_ride(client, rider["headers"], driver)

    async with session_factory() as session:
        stored = await session.scalar(
            select(Ride.route_polyline).where(Ride.id == ride["id"])
        )
    assert stored is None

    response = await client.get(
        f"/rides/{ride['id']}/route-line", headers=rider["headers"]
    )
    assert response.status_code == 200
    assert response.json()["points"] == []
