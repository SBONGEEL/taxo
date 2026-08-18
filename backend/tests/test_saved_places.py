"""الأماكن المحفوظة (`FUTURE-FEATURES` بند 1).

**وأهمُّ ما يُختبر هنا الملكية**: مكانُ راكبٍ لا يقرؤه ولا يعدّله ولا يحذفه
غيرُه بمعرِّفه وحده (SPEC القسم 14 — لا IDOR). والجوابُ لمكانِ غيره هو جوابُ
مكانٍ غير موجود: وجودُ المعرِّف نفسُه خبر.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.models.place import MAX_SAVED_PLACES
from tests.helpers import RIDER, auth, register, rider_session

HOME = {"label": "المنزل", "lat": 31.95, "lng": 35.91, "address": "جبل عمّان", "icon": "home"}


async def _create(client: AsyncClient, headers: dict, **overrides) -> dict:
    response = await client.post("/me/places", json=HOME | overrides, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_a_place_round_trips_with_its_coordinates(
    client: AsyncClient, jordan_settings: None
) -> None:
    rider = await rider_session(client)
    place = await _create(client, rider["headers"])

    assert place["label"] == "المنزل"
    assert place["icon"] == "home"
    # الإحداثيات محسوبةٌ في القاعدة — وتعود مع الإنشاء لا بعد قراءةٍ ثانية
    assert round(place["lat"], 4) == 31.95
    assert round(place["lng"], 4) == 35.91

    listed = await client.get("/me/places", headers=rider["headers"])
    assert [row["id"] for row in listed.json()] == [place["id"]]


async def test_the_same_label_twice_is_refused(
    client: AsyncClient, jordan_settings: None
) -> None:
    """«المنزل» مكانٌ واحد — ومنزلان يجعلان الاختصار سؤالاً لا طريقاً."""
    rider = await rider_session(client)
    await _create(client, rider["headers"])

    again = await client.post("/me/places", json=HOME, headers=rider["headers"])
    assert again.status_code == 409, again.text


async def test_the_cap_is_enforced(client: AsyncClient, jordan_settings: None) -> None:
    rider = await rider_session(client)
    for index in range(MAX_SAVED_PLACES):
        await _create(client, rider["headers"], label=f"مكان {index}")

    extra = await client.post(
        "/me/places", json=HOME | {"label": "زائد"}, headers=rider["headers"]
    )
    assert extra.status_code == 409, extra.text
    assert str(MAX_SAVED_PLACES) in extra.json()["message"]


async def test_another_rider_cannot_read_edit_or_delete_it(
    client: AsyncClient, jordan_settings: None
) -> None:
    owner = await rider_session(client)
    place = await _create(client, owner["headers"])

    other = auth(
        await register(client, RIDER | {"phone": "0795550001", "name": "راكبٌ آخر"})
    )

    for method, kwargs in (
        ("patch", {"json": {"label": "مسروق"}}),
        ("delete", {}),
    ):
        response = await getattr(client, method)(
            f"/me/places/{place['id']}", headers=other, **kwargs
        )
        assert response.status_code == 404, (method, response.text)

    # ولا تظهر في قائمته أصلاً
    listed = await client.get("/me/places", headers=other)
    assert listed.json() == []

    # ومكانُ صاحبها سليم
    mine = await client.get("/me/places", headers=owner["headers"])
    assert mine.json()[0]["label"] == "المنزل"


async def test_partial_update_distinguishes_absent_from_empty(
    client: AsyncClient, jordan_settings: None
) -> None:
    """«لم يُرسل العنوان» ≠ «أُرسل فارغاً»: الأول يُبقيه والثاني يمحوه."""
    rider = await rider_session(client)
    place = await _create(client, rider["headers"])

    renamed = await client.patch(
        f"/me/places/{place['id']}", json={"label": "البيت"}, headers=rider["headers"]
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["label"] == "البيت"
    assert renamed.json()["address"] == "جبل عمّان"  # بقي

    cleared = await client.patch(
        f"/me/places/{place['id']}", json={"address": None}, headers=rider["headers"]
    )
    assert cleared.json()["address"] is None  # مُحي


async def test_moving_a_place_changes_both_coordinates(
    client: AsyncClient, jordan_settings: None
) -> None:
    """النقطةُ تتغيّر كوحدة — خطُّ عرضٍ بلا طوله ليس موقعاً."""
    rider = await rider_session(client)
    place = await _create(client, rider["headers"])

    moved = await client.patch(
        f"/me/places/{place['id']}",
        json={"lat": 32.01, "lng": 35.85},
        headers=rider["headers"],
    )
    assert round(moved.json()["lat"], 4) == 32.01
    assert round(moved.json()["lng"], 4) == 35.85


async def test_delete_removes_it(client: AsyncClient, jordan_settings: None) -> None:
    rider = await rider_session(client)
    place = await _create(client, rider["headers"])

    gone = await client.delete(f"/me/places/{place['id']}", headers=rider["headers"])
    assert gone.status_code == 204, gone.text
    assert (await client.get("/me/places", headers=rider["headers"])).json() == []


async def test_a_driver_has_no_door_here(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """شاشةُ راكب: الكبتنُ لا يطلب رحلةً من تطبيقه، فبابُه بابٌ بلا شاشة."""
    from tests.helpers import DRIVER, approved_driver

    driver = await approved_driver(client, session_factory, DRIVER)
    response = await client.get("/me/places", headers=driver["headers"])
    assert response.status_code == 403
