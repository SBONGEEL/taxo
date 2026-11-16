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
             "lat": 31.9785, "lng": 35.8337, "distance_m": 7200, "src": "osm", "score": 1.2, "cat": "mall"}


class OpenFake:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.status = 200
        self.items = [OPEN_ITEM]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(dict(request.url.params))
        if self.status == 0:
            raise httpx.ReadTimeout("slow", request=request)
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


async def test_one_slow_answer_is_not_a_dead_service(client: AsyncClient, open_fake: OpenFake, mapbox: list) -> None:
    """**مهلةٌ واحدةٌ لا تُسقط البحثَ عشرَ دقائق** — كانت تُعلِّمها ساقطةً فيذهب كلُّ بحثٍ بعدها إلى Mapbox؛ والثالثةُ في دقيقةٍ تُعلِّم"""
    from app.core.redis_client import get_redis_client

    await get_redis_client().delete(maps._SLOW)
    open_fake.status = 0
    assert (await _search(client))["attribution"] == "mapbox"
    assert not await maps.is_down("open")
    open_fake.status = 200
    assert (await _search(client))["attribution"] == "open", "السؤالُ التالي يطرق الخدمةَ ثانيةً"
    open_fake.status = 0
    await _search(client)
    assert not await maps.is_down("open")
    await _search(client)
    assert await maps.is_down("open"), "ثلاثُ مهلاتٍ في دقيقةٍ خدمةٌ معلَّقةٌ لا سؤالٌ بطيء"


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


async def test_the_panel_searches_in_the_screen_country(
    client: AsyncClient, open_fake: OpenFake, mapbox: list, admin_headers: dict[str, str], support_headers: dict[str, str]
) -> None:
    """**بحثُ اللوحة بالخدمة نفسِها** (`GET /admin/map-places/search`) — **بدولة الشاشة لا بدولة حساب المشرف**، وبالنسبة نفسِها؛
    **وقراءةٌ** فيفتحها كلُّ موظّفٍ كالقائمة جارتِها، ولا يفتحها راكب."""
    found = (await client.get("/admin/map-places/search", params={"country": "DZ", "q": "سيتي مول"}, headers=admin_headers)).json()
    assert [i["source"] for i in found["items"]] == ["open"] and found["attribution"] == "open"
    assert "OpenStreetMap" in found["attribution_text"]
    assert open_fake.calls[-1]["cc"] == "DZ"

    assert (await client.get("/admin/map-places/search", params={"country": "JO", "q": "مول"}, headers=support_headers)).status_code == 200
    rider = (await rider_session(client, RIDER))["headers"]
    assert (await client.get("/admin/map-places/search", params={"country": "JO", "q": "مول"}, headers=rider)).status_code == 403


async def test_each_result_carries_its_icon_category(client: AsyncClient, open_fake: OpenFake, mapbox: list) -> None:
    """**أيقونةٌ بصنف المكان** (أمرُ المالك §١٠٤/١١) — الصنفُ من الخدمة يصل كما هو، والطلبُ يسأل عشراً."""
    found = await _search(client)
    assert found["items"][0]["category"] == "mall"
    assert open_fake.calls[0]["limit"] == "10"


async def test_the_same_place_twice_is_shown_once(client: AsyncClient, open_fake: OpenFake, mapbox: list) -> None:
    """**لا تكرار** (§١٠٤/٧) — الاسمُ نفسُه في كيلومترٍ مكانٌ واحد، **وفرعٌ بالاسم نفسِه بعيدٌ يبقى**."""
    near_copy = {**OPEN_ITEM, "id": "ovt:1", "lat": 31.9790, "lng": 35.8340, "src": "overture"}
    far_branch = {**OPEN_ITEM, "id": "osm:2", "lat": 32.0600, "lng": 36.0900, "context": "الزرقاء"}
    open_fake.items = [OPEN_ITEM, near_copy, far_branch]
    found = await _search(client)
    assert [i["id"] for i in found["items"]] == ["o-osm:15315", "o-osm:2"]


async def test_a_saved_place_hides_the_same_provider_result_and_gets_a_distance(
    client: AsyncClient, open_fake: OpenFake, mapbox: list
) -> None:
    """**المحفوظةُ أوّلاً ومرّةً واحدة** — ونتيجتُها تحمل مسافتَها من الراكب كنتائج الخدمة، **ولا يراها غيرُ صاحبها**."""
    await _search(client)  # يُنشئ الراكب
    headers = client._open_rider  # type: ignore[attr-defined]
    created = await client.post("/me/places", json={"label": "سيتي مول", "lat": 31.9786, "lng": 35.8338, "address": "أم السماق"},
                                headers=headers)
    assert created.status_code == 201
    found = await _search(client)
    assert [(i["source"], i["category"]) for i in found["items"]] == [("saved", "saved")]
    assert 7000 < found["items"][0]["distance_m"] < 9000

    from tests.helpers import OTHER_RIDER

    other = (await rider_session(client, OTHER_RIDER))["headers"]
    theirs = (await client.get("/places/search", params={"q": "سيتي مول", "lat": 31.95, "lng": 35.91}, headers=other)).json()
    assert [i["source"] for i in theirs["items"]] == ["open"]
