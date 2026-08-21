"""رمزُ الحضور — **بابٌ واحدٌ، والاختبارُ يمسح لا يثق** (§23.4).

**العلّةُ التي وُجد لها**: الخدمةُ الأمامية تبثّ موقعَ الكبتن ساعاتٍ، ورمزُ
الوصول عمرُه ٣٠ دقيقة — **ولا يُسلَّم رمزُ التجديد لأنه أحاديُّ الاستعمال**
(§23)، وحاملان له يخرجان صاحبَه من حسابه.

**وما يحرسه هذا الملف ليس أن الرمز يعمل، بل أنه لا يعمل في غير بابه.** بابٌ
ضيّقٌ يتّسع **بالسهو لا بالقرار**: يكفي أن تُعلَّق `BroadcastingDriver` على
مسارٍ ثانٍ. فالمسحُ هنا يمرّ على **كلِّ مسارات الكبتن** ويشترط الردَّ.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.core.redis_client import get_redis_client
from app.services import presence_token
from tests.helpers import DRIVER, approved_driver, bring_online

BROADCAST = "/drivers/me/location"
POSITION = {"lat": 31.95, "lng": 35.91, "heading": 90}


async def _token(client: AsyncClient, session_factory) -> tuple[dict, str]:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    issued = await client.post(
        "/drivers/me/presence-token", headers=driver["headers"]
    )
    assert issued.status_code == 200, issued.text
    return driver, issued.json()["token"]


async def test_the_token_broadcasts_and_the_session_still_does(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**البابان معاً**: الخدمةُ بالرمز، والويبُ بجلسته — ولا يُلغي أحدُهما الآخر."""
    driver, token = await _token(client, session_factory)

    by_token = await client.post(
        BROADCAST, json=POSITION, headers={"X-Presence-Token": token}
    )
    assert by_token.status_code == 204, by_token.text

    by_session = await client.post(BROADCAST, json=POSITION, headers=driver["headers"])
    assert by_session.status_code == 204, by_session.text


async def test_the_token_opens_no_other_driver_route(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**المسحُ هو الحارس**: كلُّ مسارات الكبتن تُطرق بالرمز وتُردّ.

    وبتعليق `BroadcastingDriver` على مسارٍ ثانٍ يسقط هذا الاختبار — وهو
    بالضبط الشكلُ الذي يتّسع فيه بابٌ ضيّقٌ بلا أن يقرّره أحد.
    """
    _driver, token = await _token(client, session_factory)
    headers = {"X-Presence-Token": token}

    probes = [
        ("GET", "/drivers/me", None),
        ("GET", "/drivers/me/earnings", None),
        ("GET", "/drivers/me/documents", None),
        ("GET", "/drivers/me/vehicles", None),
        ("GET", "/drivers/me/advances", None),
        ("GET", "/wallet/me/driver", None),
        ("GET", "/rides/me", None),
        ("GET", "/auth/me", None),
        ("POST", "/drivers/me/online", {}),
        ("POST", "/drivers/me/offline", {}),
        ("POST", "/drivers/me/presence-token", {}),
    ]

    refused: list[str] = []
    for verb, path, body in probes:
        response = await client.request(verb, path, headers=headers, json=body)
        assert response.status_code in (401, 403), (
            f"{verb} {path} فُتح برمز الحضور — الردُّ {response.status_code}"
        )
        refused.append(path)

    # **`assert` قبل النتيجة**: قائمةٌ فارغةٌ تمرّ ولا تحرس شيئاً
    assert len(refused) == len(probes)


async def test_going_offline_kills_the_token(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**يُلغى لحظةَ الفصل** — لا بعد دقيقة، ولا بانتهاء مهلة."""
    driver, token = await _token(client, session_factory)

    await client.post("/drivers/me/offline", headers=driver["headers"])

    after = await client.post(
        BROADCAST, json=POSITION, headers={"X-Presence-Token": token}
    )
    assert after.status_code == 401, after.text


async def test_logging_out_kills_the_token(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**والخروجُ كذلك**: من سجّل خروجَه لا يبقى جهازُه على الخريطة."""
    driver, token = await _token(client, session_factory)

    await client.post("/auth/logout", json={"refresh_token": driver["refresh"]})

    after = await client.post(
        BROADCAST, json=POSITION, headers={"X-Presence-Token": token}
    )
    assert after.status_code == 401, after.text


async def test_a_second_issue_kills_the_first(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**رمزٌ واحدٌ لكلِّ كبتن**: جهازٌ أُخذ منه لا يبقى يبثّ بعد دخوله من غيره."""
    driver, first = await _token(client, session_factory)
    second = (
        await client.post("/drivers/me/presence-token", headers=driver["headers"])
    ).json()["token"]
    assert second != first

    stale = await client.post(
        BROADCAST, json=POSITION, headers={"X-Presence-Token": first}
    )
    assert stale.status_code == 401

    fresh = await client.post(
        BROADCAST, json=POSITION, headers={"X-Presence-Token": second}
    )
    assert fresh.status_code == 204


async def test_the_raw_token_is_not_stored(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**يُخزَّن مُلخَّصُه لا هو**: من قرأ Redis لا يخرج منه برمزٍ صالح."""
    _driver, token = await _token(client, session_factory)
    redis = get_redis_client()

    found = [key async for key in redis.scan_iter(match="presence:*")]
    assert found, "لا مفتاحَ للحضور — الاختبارُ يقيس فراغاً"
    for key in found:
        name = key.decode() if isinstance(key, bytes) else str(key)
        assert token not in name
        value = await redis.get(name)
        if value is not None:
            text = value.decode() if isinstance(value, bytes) else str(value)
            assert token not in text


async def test_a_garbage_token_is_refused(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**وقيمةُ الترويسة لاتينيةٌ بحكم HTTP**: نصٌّ عربيٌّ لا يصل الخادمَ
    أصلاً بل يسقط عند العميل — فالمِسبارُ ASCII، و`token_urlsafe` كذلك."""
    response = await client.post(
        BROADCAST, json=POSITION, headers={"X-Presence-Token": "not-a-real-token"}
    )
    assert response.status_code == 401


async def test_resolve_extends_the_life_of_a_working_token(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**وردياتٌ أطولُ من عمر الرمز لا تنقطع** ما دام صاحبُها يعمل."""
    _driver, token = await _token(client, session_factory)
    redis = get_redis_client()

    digest_key = f"presence:token:{presence_token._digest(token)}"
    await redis.expire(digest_key, 60)
    assert await redis.ttl(digest_key) <= 60

    await client.post(BROADCAST, json=POSITION, headers={"X-Presence-Token": token})
    assert await redis.ttl(digest_key) > 60
