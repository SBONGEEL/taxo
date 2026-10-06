"""المسارُ الذي سارته الرحلة — `GET /rides/{id}/route` (§٦٢-ج/١١، R18 · C17).

**ثلاثةُ أسئلةٍ يجيبها هذا الملفّ**: أيقرأ الطرفان النقاطَ نفسَها **بترتيبها**؟ أيُردّ غيرُهما — **والمشرفُ منهم** — بـ٤٠٤ لا
بمسار؟ ومتى يُقرأ: بعد الانتهاء وحدَه، **وبلا نقاطٍ قائمةٌ فارغةٌ لا خطأ**.

**والنقاطُ تُكتب مباشرةً** (`add_route_points`) كما في `test_route.py`: الالتقاطُ من البثّ مختبَرٌ هناك بنافذته، وهنا يُسأل
البابُ عمّا كُتب — **بزمنٍ صريحٍ متصاعد** لا بـ`now()` واحدةٍ تجعل الترتيبَ عشوائياً بالمعرّف.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import (
    OTHER_RIDER,
    RIDER,
    SECOND_DRIVER,
    add_route_points,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    register,
    started_ride,
)

#: ثلاثُ نقاطٍ في عمّان بترتيبٍ معلوم — `(lat, lng)` كما يأخذها المساعد
_TRACK = [(31.9539, 35.9106), (31.9601, 35.9050), (31.9800, 35.8900)]


def _as_lng_lat(track: list[tuple[float, float]]) -> list[list[float]]:
    """ما يجب أن يخرج: `[lng, lat]` — ترتيبُ GeoJSON كـ`route-line`."""
    return [[lng, lat] for lat, lng in track]


async def _online_driver(client: AsyncClient, session_factory) -> dict:
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    return driver


def _close(points: list[list[float]], expected: list[list[float]]) -> bool:
    """النقاطُ تمرّ بـPostGIS ذهاباً وإياباً — فتُقارن إلى جزءٍ من المليون لا حرفاً."""
    return len(points) == len(expected) and all(
        abs(a - b) < 1e-6 for got, want in zip(points, expected) for a, b in zip(got, want)
    )


async def test_both_parties_read_the_route_in_its_order(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**الراكبُ والكبتنُ يقرآن الخطَّ نفسَه، بالترتيب الذي سار به** — لا بترتيب الإدراج ولا المعرّف."""
    rider = auth(await register(client, RIDER))
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)
    await add_route_points(session_factory, ride["id"], _TRACK)

    mine = await client.get(f"/rides/{ride['id']}/route", headers=rider)
    assert mine.status_code == 200, mine.text
    body = mine.json()
    assert _close(body["points"], _as_lng_lat(_TRACK)), body
    assert body["truncated"] is False

    theirs = await client.get(f"/rides/{ride['id']}/route", headers=driver["headers"])
    assert theirs.status_code == 200, theirs.text
    # **حقلاً حقلاً** — بابٌ واحدٌ وطرفان، فلا يرى أحدُهما غيرَ ما يرى الآخر
    assert theirs.json() == body


async def test_a_stranger_gets_404_not_a_route(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """**لا IDOR**: راكبٌ آخر، وكبتنٌ آخر، **والمشرفُ** — كلُّهم ٤٠٤.

    والمشرفُ بقصد: يقرأ المسارَ دليلَ نزاعٍ من `GET /admin/rides/{id}` تحت مصفوفة صلاحياته، **وهذا البابُ للطرفين وحدهما**.
    و٤٠٤ لا ٤٠٣: وجودُ الرحلة نفسُه ليس معلومةً يستحقّها غيرُ طرفيها.
    """
    rider = auth(await register(client, RIDER))
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)
    await add_route_points(session_factory, ride["id"], _TRACK)

    other_rider = auth(await register(client, OTHER_RIDER))
    other_driver = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-9999"
    )

    for headers in (other_rider, other_driver["headers"], admin_headers):
        response = await client.get(f"/rides/{ride['id']}/route", headers=headers)
        assert response.status_code == 404, response.text
        assert "points" not in response.json()


async def test_unknown_ride_is_404(client: AsyncClient) -> None:
    rider = auth(await register(client, RIDER))
    response = await client.get(
        "/rides/00000000-0000-0000-0000-000000000000/route", headers=rider
    )
    assert response.status_code == 404, response.text


async def test_a_ride_without_points_is_an_empty_route_not_an_error(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**تطبيقُ الكبتن صمت فلم تُكتب نقطة** — قائمةٌ فارغة، والتطبيقُ لا يرسم شيئاً ولا يُخترع خط."""
    rider = auth(await register(client, RIDER))
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)

    response = await client.get(f"/rides/{ride['id']}/route", headers=rider)
    assert response.status_code == 200, response.text
    assert response.json() == {"points": [], "truncated": False}


async def test_the_route_waits_for_the_ride_to_end(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**جاريةٌ ⇒ ٤٠٩**: خطٌّ ناقصٌ لا يُقرأ على أنه الرحلة — والطرفان يريان موضعَ السيارة حيّاً أصلاً."""
    rider = auth(await register(client, RIDER))
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider, driver)
    await add_route_points(session_factory, ride["id"], _TRACK[:2])

    response = await client.get(f"/rides/{ride['id']}/route", headers=rider)
    assert response.status_code == 409, response.text
    assert "points" not in response.json()


async def test_the_cap_cuts_the_tail_and_says_so(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**السقفُ سقفُ اللوحة نفسُه** (`ride_log.ROUTE_POINT_CAP`) — **والقصُّ يُقال** فلا يُقرأ الناقصُ كاملاً."""
    from app.services import ride_log

    monkeypatch.setattr(ride_log, "ROUTE_POINT_CAP", 2)
    rider = auth(await register(client, RIDER))
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)
    await add_route_points(session_factory, ride["id"], _TRACK)

    body = (await client.get(f"/rides/{ride['id']}/route", headers=rider)).json()
    assert body["truncated"] is True
    # **الرأسُ يبقى والذيلُ يُقصّ** — أوّلُ ما سار أولى من آخره
    assert _close(body["points"], _as_lng_lat(_TRACK[:2])), body
