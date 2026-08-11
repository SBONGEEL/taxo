"""الإشعارات المعاملاتية وأجهزتها (SPEC القسم 4/10 — المرحلة 8)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.device import DeviceToken
from tests.helpers import (
    DRIVER,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    enable_push_provider,
    pushes_to,
    register,
    register_device,
    rider_session,
    wait_until,
)

RIDER_TOKEN = "fcm-rider-1"
DRIVER_TOKEN = "fcm-driver-1"


# ------------------------------------------------------------ تسجيل الجهاز


async def test_device_registration_never_returns_the_token(
    client: AsyncClient
) -> None:
    """الرمز يسمح بإرسال إشعارٍ باسمنا — فلا يخرج من الخلفية."""
    rider = await rider_session(client)
    body = await register_device(client, rider["headers"], token=RIDER_TOKEN)

    assert "token" not in body
    assert body["is_active"] is True
    listed = (await client.get("/me/devices", headers=rider["headers"])).json()
    assert len(listed) == 1
    assert "token" not in listed[0]


async def test_registering_again_updates_the_same_device(
    client: AsyncClient, session_factory
) -> None:
    rider = await rider_session(client)
    await register_device(client, rider["headers"], token="fcm-token-old")
    await register_device(client, rider["headers"], token="fcm-token-new")

    async with session_factory() as session:
        rows = (await session.scalars(select(DeviceToken))).all()
    assert [row.token for row in rows] == ["fcm-token-new"]


async def test_a_token_follows_its_last_owner(
    client: AsyncClient, session_factory
) -> None:
    """نفس الهاتف سجّل عليه حسابٌ آخر: لا يبقى الرمز للأول."""
    first = await rider_session(client)
    second = await rider_session(client, RIDER | {"phone": "0799999999"})

    await register_device(client, first["headers"], token="shared-token")
    await register_device(client, second["headers"], token="shared-token")

    async with session_factory() as session:
        rows = (await session.scalars(select(DeviceToken))).all()
    assert len(rows) == 1


async def test_unregister_removes_the_device(client: AsyncClient) -> None:
    rider = await rider_session(client)
    await register_device(client, rider["headers"], device_id="device-1")

    deleted = await client.delete("/me/devices/device-1", headers=rider["headers"])
    assert deleted.status_code == 204
    assert (await client.get("/me/devices", headers=rider["headers"])).json() == []


async def test_devices_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/me/devices")).status_code == 401


# ----------------------------------------------------------- أحداث الرحلة


async def test_ride_events_reach_a_closed_app_over_push(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    await enable_push_provider(session_factory)

    rider = await rider_session(client)
    await register_device(client, rider["headers"], token=RIDER_TOKEN)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    from tests.helpers import accepted_ride

    ride = await accepted_ride(client, rider["headers"], driver)

    messages = await pushes_to(RIDER_TOKEN)
    assert [message["title"] for message in messages] == ["تم قبول رحلتك"]
    # الحمولةُ عقدٌ (القسم 10): معرّفاتٌ وقيمٌ **خام** تصوغ بها الواجهةُ
    # جملتها — لا نصَّ مصوغاً ولا رقماً منسّقاً
    assert messages[0]["data"] == {
        "type": "driver_assigned",
        "ride_id": ride["id"],
        "amount": ride["estimated_fare"],
        "currency": ride["currency"],
        "status": ride["status"],
    }
    # حدث الرحلة ليس مستعجلاً كبطاقة الطلب — أولوية عادية
    assert messages[0]["high_priority"] is False


async def test_ride_offer_is_high_priority(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """مهلة القبول عشرون ثانية ولا تحتمل تأجيل Doze mode (SPEC القسم 10)."""
    await enable_push_provider(session_factory)

    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory)
    await register_device(client, driver["headers"], token=DRIVER_TOKEN)
    await bring_online(client, driver)

    from tests.helpers import request_ride, wait_for_offer

    ride = await request_ride(client, rider["headers"])
    await wait_for_offer(ride["id"], driver["driver_id"])

    async def _arrived() -> list[dict]:
        return await pushes_to(DRIVER_TOKEN)

    messages = await wait_until(_arrived, message="لم يصل إشعار بطاقة الطلب")
    assert messages[0]["title"] == "طلب رحلة جديد"
    assert messages[0]["high_priority"] is True
    assert messages[0]["data"]["ride_id"] == ride["id"]


async def test_open_socket_suppresses_push_for_that_device(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """الجهاز المفتوح وصله الحدث على المقبس — فلا إشعار ثانٍ له."""
    from app.services import presence

    await enable_push_provider(session_factory)

    rider_body = await register(client, RIDER)
    rider_headers = auth(rider_body)
    await register_device(
        client, rider_headers, device_id="open-device", token=RIDER_TOKEN
    )
    # نفس ما يكتبه المقبس عند فتحه
    await presence.heartbeat(
        get_redis_client(), uuid.UUID(rider_body["user"]["id"]), "open-device"
    )

    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    from tests.helpers import accepted_ride

    await accepted_ride(client, rider_headers, driver)
    assert await pushes_to(RIDER_TOKEN) == []

    # وبإغلاق المقبس يعود Push فوراً
    await presence.leave(
        get_redis_client(), uuid.UUID(rider_body["user"]["id"]), "open-device"
    )
    cancelled = await client.post(
        f"/rides/{await _active_ride(client, rider_headers)}/cancel",
        json={"reason": "غيّرت رأيي"},
        headers=rider_headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert [m["title"] for m in await pushes_to(RIDER_TOKEN)] == ["أُلغيت الرحلة"]


async def _active_ride(client: AsyncClient, headers: dict) -> str:
    response = await client.get("/rides/me/active", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def test_dead_tokens_are_deactivated_not_deleted(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    from app.services.push.mock import INVALID_TOKEN

    await enable_push_provider(session_factory)

    rider = await rider_session(client)
    await register_device(client, rider["headers"], token=INVALID_TOKEN)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    from tests.helpers import accepted_ride

    await accepted_ride(client, rider["headers"], driver)

    async with session_factory() as session:
        row = await session.scalar(select(DeviceToken))
    assert row is not None  # الصفُّ باقٍ
    assert row.is_active is False  # ولا يُعاد الإرسال إليه


async def test_no_push_contract_is_not_an_error(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """قبل عقد FCM يكفي الـ WebSocket — والرحلة لا تتعثر لغيابه."""
    rider = await rider_session(client)
    await register_device(client, rider["headers"], token=RIDER_TOKEN)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    from tests.helpers import accepted_ride

    ride = await accepted_ride(client, rider["headers"], driver)
    assert ride["status"] == "accepted"
    assert await pushes_to(RIDER_TOKEN) == []


# ------------------------------------------------------------- التفضيلات


async def test_marketing_preference_defaults_on_and_can_be_switched(
    client: AsyncClient,
) -> None:
    driver_body = await register(client, DRIVER)
    headers = auth(driver_body)

    assert (
        await client.get("/me/notification-preferences", headers=headers)
    ).json() == {"marketing_push_enabled": True}

    updated = await client.put(
        "/me/notification-preferences",
        json={"marketing_push_enabled": False},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json() == {"marketing_push_enabled": False}


async def test_marketing_switch_does_not_touch_transactional_push(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """من أطفأ الإعلانات لم يطفئ «وصل الكبتن» (SPEC القسم 10)."""
    await enable_push_provider(session_factory)

    rider = await rider_session(client)
    await register_device(client, rider["headers"], token=RIDER_TOKEN)
    await client.put(
        "/me/notification-preferences",
        json={"marketing_push_enabled": False},
        headers=rider["headers"],
    )

    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    from tests.helpers import accepted_ride

    await accepted_ride(client, rider["headers"], driver)
    assert [m["title"] for m in await pushes_to(RIDER_TOKEN)] == ["تم قبول رحلتك"]
