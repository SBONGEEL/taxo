"""**أماكنُ الخريطة** (SPEC §٧١-د) — اللوحةُ تضيف وتعدّل وتُخفي، والتطبيقان يرسمان ويبحثان، **والمفتاحُ مطفأً يُبقي كلَّ شيءٍ كما كان**."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.map_place import MAP_PLACE_CATEGORIES
from app.services import map_places
from tests.helpers import enable_features, rider_session

pytestmark = pytest.mark.usefixtures("jordan_settings")

#: عمّان — نقطةُ البحث
NEAR = {"lat": 31.9539, "lng": 35.9106}


async def _add(client: AsyncClient, headers: dict, **fields) -> dict:
    body = {"country_code": "JO", "category": "mall", "lat": 31.97, "lng": 35.90, **fields}
    response = await client.post("/admin/map-places", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_the_migration_constraint_lists_every_category() -> None:
    """**الترحيلةُ منسوخةٌ لا مستوردة** — فتُطابَق بالتعداد: فئةٌ تُضاف إليه بلا ترحيلة قيدٍ تُرفض في القاعدة لا في المخطَّط."""
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0107_map_places.py"
    spec = importlib.util.spec_from_file_location("m0107", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    assert set(module._CATEGORIES) == set(MAP_PLACE_CATEGORIES)


def test_arabic_is_folded_for_matching_only() -> None:
    assert map_places.normalize("مكّة مول") == map_places.normalize("مكه مول")
    assert map_places.normalize("الأردنيّة") == map_places.normalize("الاردنيه")
    assert map_places.normalize("City  Mall") == "city mall"


async def test_nothing_is_drawn_or_found_while_the_key_is_off(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _add(client, admin_headers, name_ar="مكة مول", name_en="Mecca Mall")
    rider = await rider_session(client)
    assert (await client.get("/map-places", headers=rider["headers"])).json() == []
    found = await client.get("/map-places/search", params={"q": "مكة"}, headers=rider["headers"])
    assert found.status_code == 200 and found.json() == []


async def test_owner_places_are_drawn_and_lead_the_search_nearest_first(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await enable_features(session_factory, "map_places_enabled")
    far = await _add(client, admin_headers, name_ar="مكة مول — فرع بعيد", lat=32.55, lng=35.85)
    near = await _add(client, admin_headers, name_ar="مكة مول", name_en="Mecca Mall", lat=31.976, lng=35.844)
    hidden = await _add(client, admin_headers, name_ar="مكة القديمة", is_hidden=True)
    contains = await _add(client, admin_headers, name_ar="سوق مكة", category="market", lat=31.955, lng=35.911)
    rider = await rider_session(client)

    drawn = {row["id"] for row in (await client.get("/map-places", headers=rider["headers"])).json()}
    assert {far["id"], near["id"], contains["id"]} <= drawn and hidden["id"] not in drawn

    # **«مكه» بلا تاء مربوطة تجد «مكة»** — كلُّها تبدأ كلمةً بالنصّ، فالأقربُ أوّلاً: السوقُ جوارَ النقطة، ثمّ المولُ، ثمّ إربد
    found = (await client.get("/map-places/search", params={"q": "مكه", **NEAR}, headers=rider["headers"])).json()
    assert [row["id"] for row in found] == [contains["id"], near["id"], far["id"]]
    assert found[0]["distance_m"] < found[1]["distance_m"] < found[2]["distance_m"]

    # **وما يبدأ بالنصّ قبل ما يحويه في وسط كلمة**: «ول» داخل «مول» يأتي بعد ما يبدأ به
    middle = await _add(client, admin_headers, name_ar="ولائم", category="restaurant", lat=32.4, lng=35.9)
    found = (await client.get("/map-places/search", params={"q": "ول", **NEAR}, headers=rider["headers"])).json()
    assert found[0]["id"] == middle["id"]

    # **والإنجليزيُّ يُبحث به**
    english = (await client.get("/map-places/search", params={"q": "mecca"}, headers=rider["headers"])).json()
    assert [row["id"] for row in english] == [near["id"]]


async def test_the_panel_edits_hides_and_audits_and_refuses_an_empty_name(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    place = await _add(client, admin_headers, name_ar="  الجامعة   الأردنية ", name_en="University of Jordan", category="university")
    assert place["name_ar"] == "الجامعة الأردنية"

    unknown = await client.post(
        "/admin/map-places",
        json={"country_code": "JO", "name_ar": "مكان", "category": "spaceport", "lat": 31.9, "lng": 35.9},
        headers=admin_headers,
    )
    assert unknown.status_code == 422, unknown.text

    blank = await client.patch(f"/admin/map-places/{place['id']}", json={"name_ar": None}, headers=admin_headers)
    assert blank.status_code in (400, 422), blank.text

    hidden = await client.patch(f"/admin/map-places/{place['id']}", json={"is_hidden": True}, headers=admin_headers)
    assert hidden.status_code == 200 and hidden.json()["is_hidden"] is True
    listed = (await client.get("/admin/map-places", params={"country": "JO"}, headers=admin_headers)).json()
    assert [row["id"] for row in listed] == [place["id"]]

    async with session_factory() as session:
        audits = (
            await session.scalars(
                select(AdminAuditLog).where(AdminAuditLog.entity_type == "map_place").order_by(AdminAuditLog.created_at)
            )
        ).all()
    assert [entry.action.value for entry in audits] == ["create", "update"]
    assert audits[1].details["changes"] == {"is_hidden": {"before": False, "after": True}}
