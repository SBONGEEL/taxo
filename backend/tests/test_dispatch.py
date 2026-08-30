"""التوزيع: من يُعرض عليه الطلب، بأي ترتيب، وبأي مهلة (SPEC القسم 5.3)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, VehicleCategory
from app.services import dispatch, geo
from tests.helpers import (
    DRIVER,
    FAR_PICKUP,
    NEAR_PICKUP,
    PICKUP,
    RIDER,
    SECOND_DRIVER,
    accepted_ride,
    approved_driver,
    auth,
    bring_online,
    register,
    request_ride,
    wait_for_offer,
    wait_for_status,
    wait_until,
)


async def _rider(client: AsyncClient) -> dict:
    return auth(await register(client, RIDER))


async def _driver(
    client: AsyncClient,
    session_factory,
    payload: dict = DRIVER,
    *,
    plate_number: str,
    category: str = "economy",
    location: dict | None = NEAR_PICKUP,
) -> dict:
    driver = await approved_driver(
        client, session_factory, payload, plate_number=plate_number, category=category
    )
    if location is not None:
        await bring_online(client, driver, location)
    return driver


# ---------------------------------------------------------------- الترتيب


async def test_request_moves_the_ride_to_searching(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    ride = await request_ride(client, headers)

    assert ride["status"] == "requested"
    await wait_for_status(client, headers, ride["id"], "searching")


async def test_offer_goes_to_the_nearest_driver_first(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    far = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7", location=FAR_PICKUP
    )
    near = await _driver(client, session_factory, plate_number="AMM-1")

    ride = await request_ride(client, await _rider(client))
    offered = await wait_for_offer(ride["id"])

    assert offered == near["driver_id"]
    assert offered != far["driver_id"]


async def test_search_expands_to_the_wider_radius(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """كبتن على ~5 كم خارج الدائرة الأولى — يُعرض عليه بعد التوسّع لسبعة."""
    far = await _driver(
        client, session_factory, plate_number="AMM-9", location=FAR_PICKUP
    )

    ride = await request_ride(client, await _rider(client))
    assert await wait_for_offer(ride["id"]) == far["driver_id"]


# ------------------------------------------------------------- دور الكبتن


async def test_only_the_offered_driver_can_accept(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    near = await _driver(client, session_factory, plate_number="AMM-1")
    other = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7", location=FAR_PICKUP
    )

    ride = await request_ride(client, await _rider(client))
    await wait_for_offer(ride["id"], near["driver_id"])

    stolen = await client.post(
        f"/rides/{ride['id']}/accept", headers=other["headers"]
    )
    assert stolen.status_code == 409
    assert stolen.json()["code"] == "ride_offer_expired"

    accepted = await client.post(
        f"/rides/{ride['id']}/accept", headers=near["headers"]
    )
    assert accepted.status_code == 200


async def test_declining_hands_the_offer_to_the_next_driver(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    near = await _driver(client, session_factory, plate_number="AMM-1")
    far = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7", location=FAR_PICKUP
    )

    ride = await request_ride(client, await _rider(client))
    await wait_for_offer(ride["id"], near["driver_id"])

    declined = await client.post(
        f"/rides/{ride['id']}/decline", headers=near["headers"]
    )
    assert declined.status_code == 204

    assert await wait_for_offer(ride["id"], far["driver_id"]) == far["driver_id"]
    # ولا يُعاد الطلب على من رفضه
    assert (
        await client.post(f"/rides/{ride['id']}/accept", headers=near["headers"])
    ).status_code == 409


async def test_silence_expires_the_offer_and_moves_on(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """لا يقبل ولا يرفض — تنقضي المهلة فينتقل الطلب للتالي.

    **والمهلةُ تُضبط هنا لا في `fast_dispatch`**: هي **موضوعُ** هذا الاختبار لا
    ظرفُه، فمن يعدّل المشتركةَ غداً لا يُبطل قياسَه من حيث لا يدري. وقد وقع ذلك
    فعلاً مرةً: رُفعت المشتركةُ إلى عشرٍ مقابل كلّيةٍ خمسٍ فلم يعد العرضُ يدور
    على كبتنٍ ثانٍ أصلاً — واختبارٌ يقرأ ظرفَه من ملفٍ آخر يصمت حين يتغيّر.
    """
    # **ومصدرُها الواحدُ صار `dispatch_settings.DEFAULTS`** (2026-08-30): ضبطُ
    # ثابتٍ في `dispatch` صار يضبط اسماً لا يقرؤه السلوك
    from dataclasses import replace

    from app.services import dispatch_settings

    monkeypatch.setattr(
        dispatch_settings,
        "DEFAULTS",
        replace(dispatch_settings.DEFAULTS, offer_timeout_seconds=1),
    )
    near = await _driver(client, session_factory, plate_number="AMM-1")
    far = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7", location=FAR_PICKUP
    )

    ride = await request_ride(client, await _rider(client))
    await wait_for_offer(ride["id"], near["driver_id"])

    assert await wait_for_offer(ride["id"], far["driver_id"]) == far["driver_id"]


async def test_declining_a_ride_not_offered_to_you_is_rejected(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    near = await _driver(client, session_factory, plate_number="AMM-1")
    other = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7", location=FAR_PICKUP
    )

    ride = await request_ride(client, await _rider(client))
    await wait_for_offer(ride["id"], near["driver_id"])

    response = await client.post(
        f"/rides/{ride['id']}/decline", headers=other["headers"]
    )
    assert response.status_code == 409


# ------------------------------------------------------------------ الأهلية


async def test_offline_driver_is_never_offered_a_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    assert (
        await client.post("/drivers/me/offline", headers=driver["headers"])
    ).status_code == 200

    headers = await _rider(client)
    ride = await request_ride(client, headers)
    await wait_for_status(client, headers, ride["id"], "no_driver_found")


async def test_driver_without_a_location_is_not_dispatchable(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """رفع مفتاح Online وحده لا يضع الكبتن على الخريطة."""
    driver = await approved_driver(client, session_factory, plate_number="AMM-1")
    assert (
        await client.post("/drivers/me/online", headers=driver["headers"])
    ).status_code == 200

    headers = await _rider(client)
    ride = await request_ride(client, headers)
    await wait_for_status(client, headers, ride["id"], "no_driver_found")


async def test_eligibility_filters_out_every_disqualified_driver(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """شروط SPEC القسم 5.3 مجتمعة، بلا انتظار مهل التوزيع."""
    approved = await approved_driver(client, session_factory, plate_number="AMM-1")
    pending = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7"
    )

    async with session_factory() as session:
        row = await session.get(Driver, pending["driver_id"])
        row.status = DriverStatus.PENDING
        row.is_online = True
        await session.commit()

    async with session_factory() as session:
        online = await session.get(Driver, approved["driver_id"])
        online.is_online = True
        await session.commit()

        candidates = [approved["driver_id"], pending["driver_id"]]
        eligible = await dispatch.eligible_driver_ids(
            session, candidates, VehicleCategory.ECONOMY
        )
        assert eligible == {approved["driver_id"]}

        # فئة مركبة أخرى: لا أحد
        assert not await dispatch.eligible_driver_ids(
            session, candidates, VehicleCategory.COMFORT
        )

        # إنزال مفتاح Online يخرجه من الأهلية وإن بقي حاضراً على الخريطة
        online.is_online = False
        await session.commit()
        assert not await dispatch.eligible_driver_ids(
            session, candidates, VehicleCategory.ECONOMY
        )


async def test_vehicle_category_must_match_the_request(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await _driver(client, session_factory, plate_number="AMM-1", category="comfort")

    headers = await _rider(client)
    ride = await request_ride(client, headers, category="economy")
    await wait_for_status(client, headers, ride["id"], "no_driver_found")


async def test_a_busy_driver_is_not_offered_a_second_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    first_rider = await _rider(client)
    await accepted_ride(client, first_rider, driver)

    second_rider = auth(
        await register(client, RIDER | {"phone": "0793333333", "name": "راكب ثانٍ"})
    )
    ride = await request_ride(client, second_rider)
    await wait_for_status(client, second_rider, ride["id"], "no_driver_found")


async def test_silent_driver_falls_out_of_the_index(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """انقضاء الحضور يخرج الكبتن من نتائج البحث ويُنظّف عضويته في الـ zset."""
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    redis = get_redis_client()

    # محاكاة الصمت: نُسقط مفتاح الحضور كما يفعل انقضاء عمره
    await redis.delete(geo.presence_key(driver["driver_id"]))

    found = await geo.nearby(
        redis, country_code=CountryCode.JO, lat=PICKUP["lat"], lng=PICKUP["lng"]
    )
    assert found == []
    assert await redis.zscore(geo.geo_key(CountryCode.JO), str(driver["driver_id"])) is None


# ------------------------------------------------------------------ الإلغاء


async def test_cancelling_while_searching_stops_the_dispatch(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    headers = await _rider(client)

    ride = await request_ride(client, headers)
    await wait_for_offer(ride["id"], driver["driver_id"])

    cancelled = await client.post(
        f"/rides/{ride['id']}/cancel", json={}, headers=headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled_by_rider"

    redis = get_redis_client()
    assert await dispatch.current_offer(redis, uuid.UUID(ride["id"])) is None
    # الكبتن تحرر: لا عرض عالق باسمه يمنع عنه الطلب التالي
    assert await redis.get(dispatch.driver_offer_key(driver["driver_id"])) is None


async def test_accepting_clears_the_offer_keys(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    ride = await accepted_ride(client, await _rider(client), driver)

    redis = get_redis_client()
    assert await dispatch.current_offer(redis, uuid.UUID(ride["id"])) is None
    assert await redis.get(dispatch.driver_offer_key(driver["driver_id"])) is None


# ------------------------------------------------ خريطة الراكب (بيانات مجهّلة)


async def test_nearby_drivers_are_anonymous(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    headers = await _rider(client)

    response = await client.get(
        "/drivers/nearby",
        params={"lat": PICKUP["lat"], "lng": PICKUP["lng"]},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    cars = response.json()
    assert len(cars) == 1
    car = cars[0]
    assert car["vehicle_category"] == "economy"
    assert car["heading"] == 90
    # لا هوية ولا لوحة (SPEC القسم 10)
    assert str(driver["driver_id"]) not in str(car)
    # **و`skin` أُضيف بقرار المالك** (§28.3/١، 2026-08-22): النادرةُ لا تصل
    # هنا أبداً، والمنشورُ هو البديلُ الذي يملكه الجميع — فلا يفرّق من يعدّ
    # السيارات. **وما يحرس ذلك المعنى** هو
    # `test_vehicle_skins::test_a_rare_skin_is_not_published_on_the_free_map`،
    # يقارن حمولةَ صاحبِ النادرة بحمولة صاحبِ العادية **شكلاً وقيمة**.
    # وهذا السطرُ يحرس شيئاً آخرَ لا يحرسه ذاك: **ألّا يتسلّل حقلٌ جديدٌ
    # إلى الحمولة المجهَّلة بلا أن يمرّ أحدٌ من هنا** — وهو ما أمسك `skin`
    # نفسَه يومَ دُمج.
    assert set(car) == {"ref", "lat", "lng", "heading", "vehicle_category", "skin"}
    # **والرسمةُ رسمٌ لا هوية**: أربعةُ حقولٍ لا اسمَ فيها ولا ندرة —
    # و«أسطورية» كلمةٌ تكفي وحدَها لنقض التجهيل.
    if car["skin"] is not None:
        assert set(car["skin"]) == {"skin_id", "image_url", "scale_percent", "rotates"}


async def test_nearby_hides_drivers_who_are_on_a_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    rider_headers = await _rider(client)
    await accepted_ride(client, rider_headers, driver)

    watcher = auth(
        await register(client, RIDER | {"phone": "0793333333", "name": "راكب ثانٍ"})
    )
    response = await client.get(
        "/drivers/nearby",
        params={"lat": PICKUP["lat"], "lng": PICKUP["lng"]},
        headers=watcher,
    )

    assert response.json() == []


async def test_only_riders_read_the_nearby_map(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, plate_number="AMM-1")
    response = await client.get(
        "/drivers/nearby",
        params={"lat": PICKUP["lat"], "lng": PICKUP["lng"]},
        headers=driver["headers"],
    )
    assert response.status_code == 403


async def test_unapproved_driver_cannot_go_online(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = auth(await register(client, SECOND_DRIVER))
    response = await client.post("/drivers/me/online", headers=headers)
    assert response.status_code == 403


async def test_driver_without_a_vehicle_cannot_go_online(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    body = await register(client, SECOND_DRIVER)
    headers = auth(body)
    async with session_factory() as session:
        driver = await session.scalar(
            select(Driver).where(Driver.user_id == uuid.UUID(body["user"]["id"]))
        )
        driver.status = DriverStatus.APPROVED
        await session.commit()

    response = await client.post("/drivers/me/online", headers=headers)
    assert response.status_code == 409


async def test_rest_location_is_rate_limited_per_driver(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """سقف بثّ الموقع عبر REST لكل كبتن على حدة (SPEC القسم 10)."""
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    other = await _driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7", location=FAR_PICKUP
    )
    body = {**NEAR_PICKUP, "heading": 90}

    # `bring_online` استهلك طلباً واحداً من نافذة كل كبتن
    for _ in range(settings.location_rate_limit_requests - 1):
        response = await client.post(
            "/drivers/me/location", json=body, headers=driver["headers"]
        )
        assert response.status_code == 204, response.text

    blocked = await client.post(
        "/drivers/me/location", json=body, headers=driver["headers"]
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) > 0

    # السقف لكل كبتن لا للمسار: زميله لم يُعاقَب بذنبه
    assert (
        await client.post(
            "/drivers/me/location", json=body, headers=other["headers"]
        )
    ).status_code == 204


async def test_going_offline_removes_the_driver_from_the_map(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await _driver(client, session_factory, plate_number="AMM-1")
    headers = await _rider(client)

    await client.post("/drivers/me/offline", headers=driver["headers"])

    async def _empty() -> bool:
        response = await client.get(
            "/drivers/nearby",
            params={"lat": PICKUP["lat"], "lng": PICKUP["lng"]},
            headers=headers,
        )
        return response.json() == []

    await wait_until(_empty, message="بقي الكبتن على الخريطة بعد خروجه")
