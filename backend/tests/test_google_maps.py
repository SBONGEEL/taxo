"""**Google أوّلاً وMapbox احتياطاً** (قرارُ المالك ٢٠٢٦-١١-١٥). **ما يُقاس هنا شروطُه بلفظها**:

- «if Google fails (errors, quota exceeded, key problem, timeout), the apps switch to Mapbox by themselves, and I get an alert»
  — كلُّ فشلٍ يُعاد على Mapbox في الطلب نفسِه، والمالكُ يُشعَر مرّةً لا في كلِّ طلب.
- «a panel switch per country and per feature» — مطفأٌ ⇐ Mapbox حرفاً ولا يُطرق Google.
- «daily quotas so no bug can run up a big bill» — السقفُ اليوميُّ يوقف Google قبل أن يُنادى.
- «typo-tolerant … «ستي مول» = «سيتي مول»» — أماكنُ TAXO بأسمائها البديلة ومسافةِ تحريرٍ صغيرة.

**والشبكةُ وحدَها مزيّفة**: Google بأشكال وثائقه المنشورة، وMapbox بنقطة حقنه (`directions.fetch_route`).
"""

from __future__ import annotations

import secrets
from decimal import Decimal
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.models.enums import CountryCode
from app.models.map_place import MapPlace
from app.services import directions, google_maps, maps
from tests.helpers import RIDER, _enable_provider, enable_features, rider_session

pytestmark = pytest.mark.asyncio

SERVER_VALUE = "gk_" + secrets.token_hex(12)
AMMAN = directions.Coordinates(31.9539, 35.9106)
ABDALI = directions.Coordinates(31.9632, 35.9087)


def _encode(points: list[tuple[float, float]]) -> str:
    """**ترميزُ Google المنشور** — لاختبار فكّه بالقيم نفسِها."""
    out, prev = [], (0, 0)
    for lat, lng in points:
        cur = (round(lat * 1e5), round(lng * 1e5))
        for value in (cur[0] - prev[0], cur[1] - prev[1]):
            value = ~(value << 1) if value < 0 else value << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev = cur
    return "".join(out)


class GoogleFake:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail: int | None = None
        self.timeout = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.host + request.url.path)
        if request.url.host != "api.mapbox.com" and self.timeout:
            raise httpx.ReadTimeout("slow", request=request)
        if request.url.host != "api.mapbox.com" and self.fail:
            return httpx.Response(self.fail, json={"error": {"message": "denied"}})
        host, path = request.url.host, request.url.path
        if host == "routes.googleapis.com":
            body = {"routes": [{"distanceMeters": 2450, "duration": "420s",
                                "polyline": {"encodedPolyline": _encode([(31.9539, 35.9106), (31.9632, 35.9087)])},
                                "legs": [{"steps": [{"distanceMeters": 2450,
                                                     "polyline": {"encodedPolyline": _encode([(31.9539, 35.9106), (31.9632, 35.9087)])},
                                                     "navigationInstruction": {"maneuver": "TURN_LEFT", "instructions": "انعطف يساراً"}}]}]}]}
            return httpx.Response(200, json=body)
        if host == "places.googleapis.com" and path.endswith(":autocomplete"):
            return httpx.Response(200, json={"suggestions": [{"placePrediction": {
                "placeId": "ChIJcity", "text": {"text": "سيتي مول، عمّان"},
                "structuredFormat": {"mainText": {"text": "سيتي مول"}, "secondaryText": {"text": "عمّان"}}}}]})
        if host == "places.googleapis.com":
            assert request.headers["X-Goog-FieldMask"] == google_maps.DETAILS_FIELDS
            return httpx.Response(200, json={"id": "ChIJcity", "formattedAddress": "شارع الملك عبدالله الثاني، عمّان",
                                             "location": {"latitude": 31.978, "longitude": 35.834}})
        if host == "maps.googleapis.com":
            return httpx.Response(200, json={"status": "OK", "results": [{"formatted_address": "العبدلي، عمّان"}]})
        if host == "api.mapbox.com":
            return httpx.Response(200, json={"features": [{"properties": {
                "mapbox_id": "mb1", "name": "City Mall", "full_address": "Amman",
                "coordinates": {"latitude": 31.97, "longitude": 35.83}}}]})
        return httpx.Response(404)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> GoogleFake:
    fake = GoogleFake()
    monkeypatch.setattr(google_maps, "transport", httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture
def mapbox_route(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    calls: list[Any] = []

    async def fake_fetch(token: str, *points: Any, with_geometry: bool = False, with_steps: bool = False) -> directions.Route:
        calls.append(points)
        return directions.Route(distance_km=Decimal("2.600"), duration_min=Decimal("8.00"))

    monkeypatch.setattr(directions, "fetch_route", fake_fetch)
    return calls


async def _contract(session_factory, **extra: str) -> None:
    await _enable_provider(session_factory, "google_maps", {"server_key": SERVER_VALUE, **extra})
    await _enable_provider(session_factory, "mapbox", {"public_token": "pk.test", "secret_token": "sk.test"})


async def _route(session_factory) -> directions.Route:
    async with session_factory() as session:
        return await directions.route_between(session, AMMAN, ABDALI, CountryCode.JO, with_geometry=True, with_steps=True)


# ------------------------------------------------------------------ المسار


async def test_routes_come_from_google_when_its_switch_is_on(session_factory, fake: GoogleFake, mapbox_route: list) -> None:
    await _contract(session_factory)
    await enable_features(session_factory, "google_routes")
    found = await _route(session_factory)
    assert found.distance_km == Decimal("2.450") and found.duration_min == Decimal("7.00")
    assert found.geometry == [[35.9106, 31.9539], [35.9087, 31.9632]]
    assert found.steps and found.steps[0]["maneuver"] == "turn" and found.steps[0]["modifier"] == "left"
    assert mapbox_route == []


async def test_switch_off_means_mapbox_and_google_is_never_called(session_factory, fake: GoogleFake, mapbox_route: list) -> None:
    await _contract(session_factory)
    found = await _route(session_factory)
    assert found.distance_km == Decimal("2.600")
    assert fake.calls == [] and len(mapbox_route) == 1


@pytest.mark.parametrize("failure", ["403", "429", "500", "timeout"])
async def test_google_failing_falls_back_to_mapbox_in_the_same_request_and_alerts_once(
    session_factory, fake: GoogleFake, mapbox_route: list, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    alerts: list[tuple] = []
    from app.services import alert_capture

    monkeypatch.setattr(alert_capture, "ship_after_commit", lambda *a, **k: alerts.append((a, k)))
    await _contract(session_factory)
    await enable_features(session_factory, "google_routes")
    if failure == "timeout":
        fake.timeout = True
    else:
        fake.fail = int(failure)

    first = await _route(session_factory)
    second = await _route(session_factory)
    assert first.distance_km == second.distance_km == Decimal("2.600")
    # **الثانيةُ لا تطرق Google** — معلَّمٌ متوقّفاً عشرَ دقائق، **والإشعارُ مرّةٌ واحدة**
    assert len(fake.calls) == 1
    assert [a[0][1] for a in alerts] == ["maps_fallback"]
    assert await maps.is_down("routes")


async def test_the_daily_cap_stops_google_before_it_is_called(session_factory, fake: GoogleFake, mapbox_route: list) -> None:
    await _contract(session_factory, cap_routes="1")
    await enable_features(session_factory, "google_routes")
    await maps.note("routes", up=True)
    assert (await _route(session_factory)).distance_km == Decimal("2.450")
    assert (await _route(session_factory)).distance_km == Decimal("2.600")
    assert len(fake.calls) == 1


# ------------------------------------------------------------------ البحث الموحَّد


async def _city_mall(session_factory) -> None:
    await enable_features(session_factory, "map_places_enabled")
    async with session_factory() as session:
        session.add(MapPlace(country_code=CountryCode.JO, name_ar="سيتي مول", name_en="City Mall", category="mall",
                             lat=31.9785, lng=35.8337, aliases=["ستي مول"]))
        await session.commit()


@pytest.mark.parametrize("typed", ["سيتي مول", "ستي مول", "سيتى مول", "city mall", "citymal"])
async def test_taxo_places_are_found_with_aliases_and_misspellings(
    client: AsyncClient, session_factory, fake: GoogleFake, typed: str
) -> None:
    await _city_mall(session_factory)
    rider = await rider_session(client, RIDER)
    found = (await client.get("/places/search", params={"q": typed}, headers=rider["headers"])).json()
    assert found["items"] and found["items"][0]["source"] == "taxo" and found["items"][0]["name"] == "سيتي مول"


async def test_google_suggestions_follow_ours_and_resolve_by_session(
    client: AsyncClient, session_factory, fake: GoogleFake
) -> None:
    await _contract(session_factory)
    await enable_features(session_factory, "google_places_search")
    rider = await rider_session(client, RIDER)
    found = (await client.get("/places/search", params={"q": "مول", "session_token": "s1"}, headers=rider["headers"])).json()
    assert found["attribution"] == "google"
    google = [item for item in found["items"] if item["source"] == "google"]
    assert google and google[0]["place_id"] == "ChIJcity" and google[0]["lat"] is None
    resolved = (await client.get("/places/resolve", params={"place_id": "ChIJcity", "session_token": "s1"},
                                 headers=rider["headers"])).json()
    assert resolved["lat"] == pytest.approx(31.978)
    # **الثانيةُ من الذاكرة** — لا Details ثانٍ
    before = len(fake.calls)
    await client.get("/places/resolve", params={"place_id": "ChIJcity"}, headers=rider["headers"])
    assert len(fake.calls) == before


async def test_search_falls_back_to_mapbox_when_google_fails(client: AsyncClient, session_factory, fake: GoogleFake) -> None:
    await _contract(session_factory)
    await enable_features(session_factory, "google_places_search")
    fake.fail = 403
    rider = await rider_session(client, RIDER)
    found = (await client.get("/places/search", params={"q": "city mall"}, headers=rider["headers"])).json()
    assert found["attribution"] == "mapbox" and [i["source"] for i in found["items"]] == ["mapbox"]


async def test_providers_report_the_live_choice(client: AsyncClient, session_factory, fake: GoogleFake) -> None:
    rider = await rider_session(client, RIDER)
    assert (await client.get("/places/providers", headers=rider["headers"])).json() == {
        "display": "mapbox", "search": "mapbox", "routes": "mapbox"}
    await _contract(session_factory)
    await enable_features(session_factory, "google_maps_display", "google_places_search", "google_routes")
    assert set((await client.get("/places/providers", headers=rider["headers"])).json().values()) == {"google"}
    # **التطبيقُ لم يرسم خريطة Google** — العرضُ وحدَه يرجع إلى Mapbox
    assert (await client.post("/places/health", json={"feature": "display", "reason": "tiles 403"},
                              headers=rider["headers"])).status_code == 204
    assert (await client.get("/places/providers", headers=rider["headers"])).json() == {
        "display": "mapbox", "search": "google", "routes": "google"}


def test_polyline_decodes_to_lng_lat() -> None:
    assert google_maps.decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [
        [-120.2, 38.5], [-120.95, 40.7], [-126.453, 43.252]]
