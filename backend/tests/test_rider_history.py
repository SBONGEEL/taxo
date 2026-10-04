"""§٦١-ط/١–٢: مرشّحُ «رحلاتي» في الخلفية، وملخّصُ الراكب على بطاقة «حسابي».

**ما يُقاس هنا هو العقدُ لا الشاشة**: المرشّحُ يصفّي في القاعدة لا في صفحةٍ محمَّلة، وبدونه لا يتغيّر الجوابُ عمّا كان؛
**ولا يرى راكبٌ رحلةَ غيره** بمرشّحٍ ولا بدونه؛ **والمتوسّطُ من تقييمات الكباتن وحدها** — تقييمُ الراكب للكبتن لا يدخله.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import (
    OTHER_RIDER,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    register,
    request_ride,
    wait_for_status,
)


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    return auth(await register(client, payload))


async def _online_driver(client: AsyncClient, session_factory) -> dict:
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    return driver


async def _ids(client: AsyncClient, headers: dict, query: str = "") -> list[str]:
    response = await client.get(f"/rides/me{query}", headers=headers)
    assert response.status_code == 200, response.text
    return [row["ride"]["id"] for row in response.json()]


async def test_the_history_filters_in_the_database(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)

    done = (await completed_ride(client, rider, driver))["id"]
    cancelled = (await request_ride(client, rider))["id"]
    response = await client.post(f"/rides/{cancelled}/cancel", json={}, headers=rider)
    assert response.status_code == 200, response.text
    active = (await request_ride(client, rider))["id"]

    # **بلا مرشّحٍ كما كان حرفاً** — ومنه الرحلةُ الجارية
    assert await _ids(client, rider) == [active, cancelled, done]
    assert await _ids(client, rider, "?group=completed") == [done]
    assert await _ids(client, rider, "?group=cancelled") == [cancelled]

    # **والصفحةُ تُعدّ على المرشَّح**: الأولى من «الملغاة» هي الملغاةُ لا ثالثةُ الكلّ
    assert await _ids(client, rider, "?group=cancelled&limit=1&offset=0") == [cancelled]
    assert await _ids(client, rider, "?group=completed&limit=1&offset=1") == []


async def test_a_ride_nobody_took_is_counted_as_cancelled(
    client: AsyncClient, jordan_settings: None
) -> None:
    """«لم نجد كبتناً» نهايةٌ لم تكتمل — فهي في «ملغاة» كما تقول بطاقتُها اليوم («لم نجد كبتناً متاحاً»)."""
    rider = await _rider(client)
    ride = await request_ride(client, rider)  # لا كبتنَ متصلاً
    await wait_for_status(client, rider, ride["id"], "no_driver_found")

    assert await _ids(client, rider, "?group=cancelled") == [ride["id"]]
    assert await _ids(client, rider, "?group=completed") == []


async def test_an_unknown_group_is_refused(client: AsyncClient, jordan_settings: None) -> None:
    rider = await _rider(client)
    response = await client.get("/rides/me?group=scheduled", headers=rider)
    assert response.status_code == 422, response.text


async def test_a_filter_never_shows_another_riders_rides(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    other = await _rider(client, OTHER_RIDER)
    driver = await _online_driver(client, session_factory)

    mine = (await completed_ride(client, rider, driver))["id"]
    theirs = (await completed_ride(client, other, driver))["id"]

    assert await _ids(client, rider, "?group=completed") == [mine]
    assert await _ids(client, other, "?group=completed") == [theirs]


async def test_the_summary_counts_completed_rides_and_averages_the_captains_ratings(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)

    first = (await completed_ride(client, rider, driver))["id"]
    second = (await completed_ride(client, rider, driver))["id"]
    cancelled = (await request_ride(client, rider))["id"]
    await client.post(f"/rides/{cancelled}/cancel", json={}, headers=rider)

    for ride_id, stars in ((first, 5), (second, 4)):
        rated = await client.post(
            f"/rides/{ride_id}/ratings", json={"stars": stars}, headers=driver["headers"]
        )
        assert rated.status_code in (200, 201), rated.text
    # **وتقييمُ الراكب للكبتن لا يدخل متوسّطَه هو**
    mine = await client.post(f"/rides/{first}/ratings", json={"stars": 1}, headers=rider)
    assert mine.status_code in (200, 201), mine.text

    summary = (await client.get("/rides/me/summary", headers=rider)).json()
    assert summary == {"completed_rides": 2, "rating_avg": "4.50", "ratings_count": 2}


async def test_a_new_rider_has_no_rating_rather_than_zero(
    client: AsyncClient, jordan_settings: None
) -> None:
    rider = await _rider(client)
    summary = (await client.get("/rides/me/summary", headers=rider)).json()
    assert summary == {"completed_rides": 0, "rating_avg": None, "ratings_count": 0}


async def test_the_summary_is_the_riders_own(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """بابٌ للراكب وحدَه: الكبتنُ يُردّ، ولا معرّفَ في المسار يُسأل به عن غيره."""
    driver = await approved_driver(client, session_factory)
    response = await client.get("/rides/me/summary", headers=driver["headers"])
    assert response.status_code == 403, response.text
    assert (await client.get("/rides/me/summary")).status_code == 401
