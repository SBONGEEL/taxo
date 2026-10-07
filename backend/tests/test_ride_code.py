"""رمزُ الرحلة (§٦٢-ج/٥، RW4 · CW4) — **أربعُ خاناتٍ تراها الراكبةُ وحدَها، وتُدخلها الكبتنةُ لتبدأ**.

ثلاثُ قواعدَ يحرسها هذا الملف:

- **الرمزُ لا يصل الكبتنةَ في أيِّ تمثيل** — لا في جواب القبول ولا في قراءة الرحلة؛ وإلا صار الشرطُ زرّاً تضغطه وحدَها.
  و`RideOut` يحمل «أهو مطلوب» (`start_code_required`) وحدَه.
- **ولا بدءَ بلا الرمز**، **والتخمينُ مسقوف**: خمسُ محاولاتٍ كلَّ عشر دقائق — **والعدُّ ذرّيٌّ**، فمحاولاتٌ متزامنةٌ لا تمرّ من تحت
  السقف معاً (يُقاس بإطلاقها معاً).
- **ومطفأً أو لرحلةٍ لم تطلب كبتنةً: لا رمزَ ولا شرط** — البدءُ كما كان حرفاً.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from datetime import UTC, datetime

from httpx import AsyncClient

from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.enums import FeatureKey, Gender
from app.models.user import User
from tests.helpers import (
    DRIVER,
    NEAR_PICKUP,
    OTHER_RIDER,
    PICKUP,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    enable_features,
    register,
    wait_for_offer,
)

WOMEN = FeatureKey.WOMEN_SERVICE_ENABLED.value
CODE = FeatureKey.RIDE_CODE_ENABLED.value


async def _female_captain(client: AsyncClient, session_factory) -> dict:
    """كبتنةٌ مختومةٌ متصلةٌ قربَ نقطة الالتقاء — من تصلها الرحلةُ النسائية."""
    driver = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-5")
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        user = await session.get(User, row.user_id)
        user.gender = Gender.FEMALE
        user.gender_verified_at = datetime.now(UTC)
        await session.commit()
    await bring_online(client, driver, NEAR_PICKUP)
    return driver


async def _accepted(client: AsyncClient, rider_headers: dict, driver: dict, preference: str) -> dict:
    response = await client.post(
        "/rides",
        json={
            "pickup": PICKUP,
            "dropoff": {"lat": 31.9800, "lng": 35.8600},
            "vehicle_category": "economy",
            "gender_preference": preference,
        },
        headers=rider_headers,
    )
    assert response.status_code == 201, response.text
    ride = response.json()
    await wait_for_offer(ride["id"], driver["driver_id"])
    accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


async def _women_ride(client: AsyncClient, session_factory, *, code_on: bool = True) -> tuple[dict, dict, dict]:
    """رحلةٌ نسائيةٌ مقبولة — والراكبةُ والكبتنة."""
    driver = await _female_captain(client, session_factory)
    await enable_features(session_factory, WOMEN, *([CODE] if code_on else []))
    rider = auth(await register(client, RIDER | {"gender": "female"}))
    ride = await _accepted(client, rider, driver, "female")
    return ride, rider, driver


async def _start(client: AsyncClient, ride_id: str, driver: dict, code: str | None = None):
    body = {"code": code} if code is not None else None
    return await client.post(f"/rides/{ride_id}/start", headers=driver["headers"], json=body)


async def test_a_women_ride_gets_a_code_only_its_rider_can_read(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**القبولُ يولّده، والراكبةُ وحدَها تقرؤه** — وجوابُ القبول نفسُه (وهو للكبتنة) يقول «مطلوب» ولا يحمله."""
    ride, rider, driver = await _women_ride(client, session_factory)
    assert ride["start_code_required"] is True

    mine = await client.get(f"/rides/{ride['id']}/start-code", headers=rider)
    assert mine.status_code == 200, mine.text
    code = mine.json()["code"]
    assert len(code) == 4 and code.isdigit()

    # **ولا في أيِّ ما تقرؤه الكبتنة** — جوابُ القبول، وقراءةُ الرحلة، وبابُ الرمز نفسُه
    assert code not in str(ride)
    seen = await client.get(f"/rides/{ride['id']}", headers=driver["headers"])
    assert seen.status_code == 200 and code not in seen.text
    assert (await client.get(f"/rides/{ride['id']}/start-code", headers=driver["headers"])).status_code in (403, 404)

    # **ولا لراكبٍ غيرها** — ٤٠٤: وجودُ الرمز نفسُه ليس معلومةً له
    other = auth(await register(client, OTHER_RIDER))
    assert (await client.get(f"/rides/{ride['id']}/start-code", headers=other)).status_code == 404


async def test_the_ride_starts_only_with_its_code(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**بلا رمزٍ أو بغيره: لا بدء** — والرسالةُ رسالةُ CW4؛ وبه تبدأ، ثمّ يغيب الرمز (رحلةٌ بدأت لا رمزَ لها)."""
    ride, rider, driver = await _women_ride(client, session_factory)
    code = (await client.get(f"/rides/{ride['id']}/start-code", headers=rider)).json()["code"]
    assert (await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])).status_code == 200

    missing = await _start(client, ride["id"], driver)
    assert missing.status_code == 422 and missing.json()["code"] == "start_code_mismatch"
    wrong = await _start(client, ride["id"], driver, "0000" if code != "0000" else "1111")
    assert wrong.status_code == 422 and wrong.json()["code"] == "start_code_mismatch"

    right = await _start(client, ride["id"], driver, code)
    assert right.status_code == 200, right.text
    assert right.json()["status"] == "in_progress"
    assert (await client.get(f"/rides/{ride['id']}/start-code", headers=rider)).status_code == 404


async def test_five_wrong_codes_lock_the_start_even_for_the_right_one(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**السقفُ يحكم الرمزَ الصحيحَ أيضاً**: وإلا جرّب المخمِّنُ حتى يصيب ثم يمرّ — وبانقضاء النافذة يعود."""
    ride, rider, driver = await _women_ride(client, session_factory)
    code = (await client.get(f"/rides/{ride['id']}/start-code", headers=rider)).json()["code"]
    await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    wrong = "0000" if code != "0000" else "1111"
    for _ in range(5):
        assert (await _start(client, ride["id"], driver, wrong)).status_code == 422
    locked = await _start(client, ride["id"], driver, code)
    assert locked.status_code == 429 and locked.json()["code"] == "start_code_locked"

    # انقضاءُ النافذة — يُحاكى بمحو العدّاد
    await get_redis_client().delete(f"ride:{ride['id']}:start-code-tries")
    assert (await _start(client, ride["id"], driver, code)).status_code == 200


async def test_concurrent_guesses_cannot_slip_under_the_cap(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**ثمانُ محاولاتٍ خاطئةٍ معاً: خمسٌ تُرفض بالخطأ وثلاثٌ بالسقف** — العدُّ قبل المقارنة وبـ`INCR` ذرّيّ.

    ولو قُرئ العدّادُ ثمّ كُتب لقرأت الثمانُ «صفراً» معاً ومرّت كلُّها إلى المقارنة — وهو بعينه ما يجعل السقفَ اقتراحاً.
    """
    ride, rider, driver = await _women_ride(client, session_factory)
    code = (await client.get(f"/rides/{ride['id']}/start-code", headers=rider)).json()["code"]
    await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    wrong = "0000" if code != "0000" else "1111"
    responses = await asyncio.wait_for(
        asyncio.gather(*(_start(client, ride["id"], driver, wrong) for _ in range(8))), timeout=30
    )
    assert Counter(response.status_code for response in responses) == Counter({422: 5, 429: 3})


async def test_the_switch_off_means_no_code_and_the_old_start(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**مطفأً: لا رمزَ يُولَّد ولا شرط** — والبدءُ بلا جسمٍ كما يرسله التطبيقُ الأقدم."""
    ride, rider, driver = await _women_ride(client, session_factory, code_on=False)
    assert ride["start_code_required"] is False
    assert (await client.get(f"/rides/{ride['id']}/start-code", headers=rider)).status_code == 404
    await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    assert (await _start(client, ride["id"], driver)).status_code == 200


async def test_a_ride_that_asked_for_nobody_has_no_code(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**الرمزُ للرحلة النسائية وحدَها كما رُسم** — ومفتاحُه مشتعلٌ لا يمسّ رحلةً بلا تفضيل."""
    driver = await _female_captain(client, session_factory)
    await enable_features(session_factory, WOMEN, CODE)
    rider = auth(await register(client, RIDER | {"gender": "female"}))
    ride = await _accepted(client, rider, driver, "any")
    assert ride["start_code_required"] is False
    await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    assert (await _start(client, ride["id"], driver)).status_code == 200
    assert uuid.UUID(ride["id"])  # الرحلةُ نفسُها، لا أخرى
