"""**البحثُ ببياناتٍ مفتوحة** (قرارُ المالك ٢٠٢٦-١١-١٥) — ما يُقاس هنا شروطُه بلفظها:

- «keep Mapbox as automatic fallback» — خدمةٌ ساقطةٌ أو بلا نتيجةٍ ⇐ Mapbox في الطلب نفسِه، والمالكُ يُشعَر مرّة؛ **ومشغولةٌ (503) لا تُعلَّم ساقطة**.
- «follow each open-source licence and attribution» — جوابٌ من البيانات المفتوحة يحمل نسبةَ OpenStreetMap وOverture.
- «Recent and saved places first» — وجهةُ رحلةٍ مكتملةٍ للراكب تسبق نتائجَ الخدمة.
- الزرُّ لكلِّ دولة: مطفأٌ ⇐ لا تُطرق الخدمة.

**والخدمةُ نفسُها مزيّفةٌ بشكل ردّها** (`places-search/server.py`)؛ ودقّتُها مقيسةٌ باختبار الـ١٠٥ (`places-search/run105.py`) لا هنا.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.config import settings
from app.models.feature_flag import FeatureFlag
from app.services import maps
from tests.helpers import RIDER, _enable_provider, rider_session

pytestmark = pytest.mark.asyncio

OPEN_ITEM = {"id": "osm:15315", "name": "سيتي مول", "name_en": "City Mall", "kind": "poi", "context": "أم السماق، عمّان",
             "lat": 31.9785, "lng": 35.8337, "distance_m": 7200, "src": "osm", "score": 1.2}


class OpenFake:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.status = 200
        self.items = [OPEN_ITEM]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(dict(request.url.params))
        if self.status != 200:
            return httpx.Response(self.status, json={"detail": "x"})
        return httpx.Response(200, json={"items": self.items})


@pytest.fixture
def open_fake(monkeypatch: pytest.MonkeyPatch) -> OpenFake:
    fake = OpenFake()
    monkeypatch.setattr(settings, "places_search_url", "http://places-search:8090")
    monkeypatch.setattr(maps, "open_transport", httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture
def mapbox(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def fake_forward(session, country, query, near):
        calls.append(query)
        return [maps.Result(id="m-1", source="mapbox", name="Mapbox Place", address="Amman", lat=31.9, lng=35.9)]

    monkeypatch.setattr(maps, "_mapbox_forward", fake_forward)
    return calls


async def _search(client: AsyncClient, q: str = "سيتي مول") -> dict:
    """**راكبٌ واحدٌ لكلِّ عميل** — التسجيلُ مرّتين يُرفض برقمٍ مسجَّل، فتُحفظ ترويستُه على العميل نفسِه."""
    headers = getattr(client, "_open_rider", None)
    if headers is None:
        headers = (await rider_session(client, RIDER))["headers"]
        client._open_rider = headers  # type: ignore[attr-defined]
    return (await client.get("/places/search", params={"q": q, "lat": 31.95, "lng": 35.91}, headers=headers)).json()


async def test_open_data_answers_first_with_its_attribution(client: AsyncClient, open_fake: OpenFake, mapbox: list) -> None:
    found = await _search(client)
    assert found["attribution"] == "open" and "OpenStreetMap" in found["attribution_text"]
    assert [i["source"] for i in found["items"]] == ["open"]
    assert found["items"][0]["name"] == "سيتي مول" and found["items"][0]["address"] == "أم السماق، عمّان"
    assert open_fake.calls[0]["cc"] == "JO" and open_fake.calls[0]["lat"] == "31.95"
    assert mapbox == []


@pytest.mark.parametrize("status", [500, 404])
async def test_a_failing_service_falls_back_to_mapbox_and_alerts_once(
    client: AsyncClient, open_fake: OpenFake, mapbox: list, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    alerts: list = []
    from app.services import alert_capture

    monkeypatch.setattr(alert_capture, "ship_after_commit", lambda *a, **k: alerts.append(a[1]))
    open_fake.status = status
    first = await _search(client)
    second = await _search(client)
    assert first["attribution"] == second["attribution"] == "mapbox"
    assert len(open_fake.calls) == 1, "الثانيةُ لا تطرق خدمةً معلَّمةً ساقطة"
    assert alerts == ["maps_fallback"] and await maps.is_down("open")


async def test_a_busy_service_is_not_marked_down(client: AsyncClient, open_fake: OpenFake, mapbox: list) -> None:
    open_fake.status = 503
    assert (await _search(client))["attribution"] == "mapbox"
    assert not await maps.is_down("open")
    open_fake.status = 200
    assert (await _search(client))["attribution"] == "open"


async def test_no_results_fall_through_to_mapbox(client: AsyncClient, open_fake: OpenFake, mapbox: list) -> None:
    open_fake.items = []
    found = await _search(client)
    assert found["attribution"] == "mapbox" and mapbox == ["سيتي مول"]


async def test_switch_off_for_the_country_means_the_service_is_never_called(
    client: AsyncClient, session_factory, open_fake: OpenFake, mapbox: list
) -> None:
    from app.models.enums import CountryCode
    from tests.helpers import enable_features  # noqa: F401 — يُنشئ الصفوف بالشكل نفسِه

    async with session_factory() as session:
        session.add(FeatureFlag(country_code=CountryCode.JO, feature_key="open_places_search", enabled=False))
        await session.commit()
    found = await _search(client)
    assert found.get("attribution") == "mapbox", found
    assert open_fake.calls == []


async def test_no_url_means_mapbox_as_before(client: AsyncClient, mapbox: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "places_search_url", "")
    assert (await _search(client))["attribution"] == "mapbox"


async def test_google_on_still_comes_before_open_data(
    client: AsyncClient, session_factory, open_fake: OpenFake, mapbox: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import google_maps
    from tests.helpers import enable_features

    async def fake_auto(*a, **k):
        return [google_maps.Suggestion(place_id="ChIJx", name="سيتي مول", address="عمّان")]

    monkeypatch.setattr(google_maps, "autocomplete", fake_auto)
    await _enable_provider(session_factory, "google_maps", {"server_key": "gk_test"})
    await enable_features(session_factory, "google_places_search")
    found = await _search(client)
    assert found["attribution"] == "google" and open_fake.calls == []
