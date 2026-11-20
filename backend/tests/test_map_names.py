"""**«أماكن بلا اسم عربي»** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ب).

* القائمةُ من `places-search` **وما كُتب له اسمٌ يُطوى منها**.
* الاسمُ عربيٌّ خالص (لا لاتينيّ)، ويُختم في التدقيق قبلاً وبعداً، والحذفُ كذلك.
* والتطبيقان يقرآن الأسماءَ بمفاتيحها — **ولا شيءَ والأماكنُ المفتوحةُ مطفأة**.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.models.audit import AdminAuditLog
from app.services import map_names
from tests.helpers import enable_features, rider_session

ITEMS = [
    {"okey": "n1", "city": "عمّان", "name": "Abdali Hospital", "tag": "amenity=hospital", "lat": 31.96, "lng": 35.91},
    {"okey": "w3", "city": "عمّان", "name": "Blom Bank", "tag": "amenity=bank", "lat": 31.95, "lng": 35.90},
]


@pytest.fixture
def places_service(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.path == "/missing-ar"
        return httpx.Response(200, json={"built": True, "cities": [{"city": "عمّان", "count": 2}], "total": 2, "items": ITEMS})

    monkeypatch.setattr(settings, "places_search_url", "http://places-search:8090")
    monkeypatch.setattr(map_names, "transport", httpx.MockTransport(handler))
    return seen


async def test_the_list_hides_what_was_named_and_the_name_is_audited(
    client: AsyncClient, admin_headers: dict, session_factory, places_service
) -> None:
    first = await client.get("/admin/map-names/missing", params={"country": "JO"}, headers=admin_headers)
    assert first.status_code == 200, first.text
    assert [i["okey"] for i in first.json()["items"]] == ["n1", "w3"]
    assert places_service[0].url.params["cc"] == "JO"

    put = await client.put(
        "/admin/map-names/n1",
        json={"country_code": "JO", "name_ar": "  مستشفى   العبدلي ", "original_name": "Abdali Hospital", "city": "عمّان"},
        headers=admin_headers,
    )
    assert put.status_code == 200, put.text
    assert put.json()["name_ar"] == "مستشفى العبدلي"

    after = await client.get("/admin/map-names/missing", params={"country": "JO"}, headers=admin_headers)
    assert [i["okey"] for i in after.json()["items"]] == ["w3"]
    fixes = await client.get("/admin/map-names/fixes", params={"country": "JO"}, headers=admin_headers)
    assert [(f["okey"], f["original_name"]) for f in fixes.json()] == [("n1", "Abdali Hospital")]

    again = await client.put(
        "/admin/map-names/n1", json={"country_code": "JO", "name_ar": "مستشفى العبدلي التخصصي"}, headers=admin_headers
    )
    assert again.status_code == 200
    gone = await client.delete("/admin/map-names/n1", headers=admin_headers)
    assert gone.status_code == 204
    assert (await client.delete("/admin/map-names/n1", headers=admin_headers)).status_code == 404

    async with session_factory() as session:
        trail = (await session.scalars(
            select(AdminAuditLog).where(AdminAuditLog.entity_type == "map_name_fix").order_by(AdminAuditLog.created_at)
        )).all()
    assert [(row.action.value, row.details["name_ar"]["before"], row.details["name_ar"]["after"]) for row in trail] == [
        ("create", None, "مستشفى العبدلي"),
        ("update", "مستشفى العبدلي", "مستشفى العبدلي التخصصي"),
        ("delete", "مستشفى العبدلي التخصصي", None),
    ]


@pytest.mark.parametrize("bad", ["Abdali", "مستشفى Abdali", "   ", "x" * 10])
async def test_only_a_pure_arabic_name_is_accepted(client: AsyncClient, admin_headers: dict, bad: str) -> None:
    response = await client.put("/admin/map-names/n9", json={"country_code": "JO", "name_ar": bad}, headers=admin_headers)
    assert response.status_code == 422, response.text


async def test_a_bad_key_is_refused(client: AsyncClient, admin_headers: dict) -> None:
    response = await client.put("/admin/map-names/x;drop", json={"country_code": "JO", "name_ar": "مكان"}, headers=admin_headers)
    assert response.status_code == 422


async def test_a_silent_places_service_is_a_503_not_an_empty_list(
    client: AsyncClient, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "places_search_url", "http://places-search:8090")
    monkeypatch.setattr(map_names, "transport", httpx.MockTransport(lambda request: httpx.Response(500)))
    response = await client.get("/admin/map-names/missing", params={"country": "JO"}, headers=admin_headers)
    assert response.status_code == 503
    assert response.json()["code"] == "places_service_unavailable"


async def test_the_apps_read_names_only_when_open_places_are_on(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None
) -> None:
    await client.put("/admin/map-names/n1", json={"country_code": "JO", "name_ar": "مستشفى العبدلي"}, headers=admin_headers)
    await client.put("/admin/map-names/n2", json={"country_code": "DZ", "name_ar": "مستشفى وهران"}, headers=admin_headers)
    rider = await rider_session(client)
    off = await client.get("/map/name-fixes", headers=rider["headers"])
    assert off.status_code == 200 and off.json() == {}

    await enable_features(session_factory, "map_open_places")
    on = await client.get("/map/name-fixes", headers=rider["headers"])
    assert on.json() == {"n1": "مستشفى العبدلي"}
