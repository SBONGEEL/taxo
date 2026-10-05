"""قنواتُ الإشعار وظهورُ التطبيق (SPEC §٦١-ل/٣–٥، ٢٠٢٦-١٠-٠٥).

ثلاثةُ أشياء تُقاس هنا:

١. **القناةُ تتبع ما يحمله الجهاز**: جهازٌ بلّغ بالمجموعة الثانية يصله الطلبُ على `taxo.offer.v2` وأحداثُ
   الرحلة على قنواتها، **وجهازٌ لم يبلّغ يصله ما يصله اليومَ حرفاً** — في إرسالٍ واحد.
٢. **المفتوحُ في الخلفية يصله الإشعار** — إلا الطلبَ، فتنبيهُه الأصليُّ يرنّ من المقبس.
٣. **والمفتوحُ أمامَ صاحبه يصله بلاغٌ بصوته** لما لا يرسمه التطبيقُ من حدثٍ له.
"""

from __future__ import annotations

import asyncio
import uuid

from httpx import AsyncClient
from httpx_ws import aconnect_ws
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.device import DeviceToken
from app.services import notifications, presence
from app.services.push import PushMessage
from tests.conftest import ws_client
from tests.helpers import (
    accepted_ride,
    approved_driver,
    bring_online,
    enable_push_provider,
    pushes_to,
    register_device,
    request_ride,
    rider_session,
    wait_for_offer,
    wait_until,
)

WS_RIDER = "http://test/api/v1/ws/rider"
RECEIVE_TIMEOUT = 12.0


async def _receive(ws, of_type: str) -> dict:
    async def _read() -> dict:
        while True:
            message = await ws.receive_json()
            if message.get("type") == of_type:
                return message

    return await asyncio.wait_for(_read(), timeout=RECEIVE_TIMEOUT)


# ------------------------------------------------------------- القناة بالجهاز


async def test_the_offer_channel_follows_what_the_device_carries(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """**الأقدمُ على منبّه الهاتف كما اليوم، والأحدثُ على صوت الطلب الجديد** — والحمولةُ واحدة."""
    await enable_push_provider(session_factory)
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory)
    await register_device(client, driver["headers"], device_id="old-phone", token="fcm-old-1")
    await register_device(
        client, driver["headers"], device_id="new-phone", token="fcm-new-1", push_channels=2
    )
    await bring_online(client, driver)

    ride = await request_ride(client, rider["headers"])
    await wait_for_offer(ride["id"], driver["driver_id"])

    old = await wait_until(lambda: pushes_to("fcm-old-1"), message="لم يصل العرضُ الجهازَ الأقدم")
    new = await wait_until(lambda: pushes_to("fcm-new-1"), message="لم يصل العرضُ الجهازَ الأحدث")
    assert old[0]["android_channel_id"] == "taxo.offer"
    assert new[0]["android_channel_id"] == "taxo.offer.v2"
    # **لا يفترق ما يصل الجهازين إلا قناتُه**
    assert old[0]["data"] == new[0]["data"]
    assert old[0]["high_priority"] is new[0]["high_priority"] is True


async def test_ride_events_get_their_channel_only_where_it_exists(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """**قناةٌ غائبةٌ تُسقط الإشعارَ إلى الاحتياطية** — فلا تُسمّى لجهازٍ لم يبلّغ بها."""
    await enable_push_provider(session_factory)
    rider = await rider_session(client)
    await register_device(client, rider["headers"], device_id="old-phone", token="fcm-r-old")
    await register_device(
        client, rider["headers"], device_id="new-phone", token="fcm-r-new", push_channels=2
    )
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    await accepted_ride(client, rider["headers"], driver)

    [old] = await pushes_to("fcm-r-old")
    [new] = await pushes_to("fcm-r-new")
    assert old["android_channel_id"] is None
    assert new["android_channel_id"] == "taxo.accepted"
    assert old["title"] == new["title"] == "تم قبول رحلتك"


async def test_a_device_that_stops_reporting_returns_to_todays_channels(
    client: AsyncClient, session_factory
) -> None:
    """حزمةٌ أقدمُ عادت إلى الجهاز نفسِه لا يبقى لها ما بلّغت به الأحدث."""
    rider = await rider_session(client)
    await register_device(client, rider["headers"], token="fcm-x-token", push_channels=2)
    await register_device(client, rider["headers"], token="fcm-x-token")

    async with session_factory() as session:
        row = await session.scalar(select(DeviceToken))
    assert row is not None and row.push_channels is None


async def test_an_impossible_channel_set_is_refused(client: AsyncClient) -> None:
    rider = await rider_session(client)
    for value in (0, 100):
        response = await client.put(
            "/me/devices",
            json={
                "device_id": "device-1",
                "token": "fcm-token-1",
                "platform": "android",
                "push_channels": value,
            },
            headers=rider["headers"],
        )
        assert response.status_code == 422, response.text


# --------------------------------------------------------- المفتوحُ في الخلفية


async def test_a_socket_in_the_background_no_longer_hides_the_push(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """**هاتفٌ في الجيب مقبسُه حيّ** — كان لا يصله شيء، والآن يصله إشعارُه."""
    await enable_push_provider(session_factory)
    rider = await rider_session(client)
    await register_device(client, rider["headers"], device_id="pocket", token="fcm-pocket")
    await presence.heartbeat(
        get_redis_client(), uuid.UUID(rider["user"]["id"]), "pocket", background=True
    )
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    await accepted_ride(client, rider["headers"], driver)

    assert [m["title"] for m in await pushes_to("fcm-pocket")] == ["تم قبول رحلتك"]


async def test_the_offer_keeps_the_socket_rule_in_the_background(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """**تنبيهُ الطلب الأصليُّ يرنّ من المقبس** — فإشعارٌ معه بلاغان لطلبٍ واحد."""
    await enable_push_provider(session_factory)
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory)
    await register_device(client, driver["headers"], device_id="dash", token="fcm-dash")
    await register_device(client, driver["headers"], device_id="spare", token="fcm-spare")
    await presence.heartbeat(
        get_redis_client(), uuid.UUID(driver["user_id"]), "dash", background=True
    )
    await bring_online(client, driver)

    ride = await request_ride(client, rider["headers"])
    await wait_for_offer(ride["id"], driver["driver_id"])

    # الجهازُ الذي لا مقبسَ له يصله — **وفي الإرسال نفسِه** يُحجب عن ذي المقبس
    await wait_until(lambda: pushes_to("fcm-spare"), message="لم يصل العرضُ الجهازَ المغلق")
    assert await pushes_to("fcm-dash") == []


async def test_the_app_reports_its_visibility_over_the_socket(
    client: AsyncClient, jordan_settings
) -> None:
    rider = await rider_session(client)
    user_id = uuid.UUID(rider["user"]["id"])
    redis = get_redis_client()

    async def _foreground() -> bool:
        return "phone-1" in await presence.foreground_devices(redis, user_id)

    async def _background() -> bool:
        return "phone-1" in await presence.active_devices(redis, user_id) and not (
            await _foreground()
        )

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_RIDER}?token={rider['token']}&device_id=phone-1", client=sockets
        ) as ws:
            await _receive(ws, "connected")
            # **ما لم يبلّغ يُحسب أمامَ صاحبه** — حكمُ اليوم حرفاً
            await wait_until(_foreground, message="لم يُحسب المقبسُ أمامَ صاحبه")

            await ws.send_json({"type": "visibility", "visible": False})
            await wait_until(_background, message="لم تُكتب علامةُ الخلفية")

            await ws.send_json({"type": "visibility", "visible": True})
            await wait_until(_foreground, message="لم تُرفع علامةُ الخلفية بالعودة")

            # **والتالفةُ تُبلَع** — لا تُسقط مقبساً ولا تُخمَّن خلفيةً
            await ws.send_json({"type": "visibility", "visible": "no"})
            await ws.send_json({"type": "viewport", "lat": 31.95, "lng": 35.91})
            await asyncio.sleep(0.2)
            assert await _foreground()

    async def _gone() -> bool:
        return not await presence.active_devices(redis, user_id)

    await wait_until(_gone, message="لم يُسقط إغلاقُ المقبس أثرَه")


# ------------------------------------------------------- البلاغُ داخل التطبيق


async def test_an_open_app_gets_a_notice_for_what_it_does_not_draw(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """**البقشيشُ لا حدثَ له على المقبس** — فكان يُحجب إشعارُه ولا يُرسم شيء."""
    rider = await rider_session(client)
    user_id = uuid.UUID(rider["user"]["id"])
    redis = get_redis_client()

    async with ws_client() as sockets:
        async with aconnect_ws(f"{WS_RIDER}?token={rider['token']}", client=sockets) as ws:
            await _receive(ws, "connected")
            async with session_factory() as session:
                # يرسمه التطبيقُ من حدثه هو — **فلا بلاغَ ثانٍ له**
                await notifications._safe_notify(
                    session,
                    redis,
                    user_id=user_id,
                    message=PushMessage(
                        title="تم قبول رحلتك", body="…", data={"type": "driver_assigned"}
                    ),
                )
                await notifications._safe_notify(
                    session,
                    redis,
                    user_id=user_id,
                    message=PushMessage(
                        title="بقشيش من راكب",
                        body="أُضيف إلى محفظتك.",
                        data={"type": "tip_received", "amount": "1.000", "currency": "JOD"},
                    ),
                )

            # **الترتيبُ محفوظٌ على القناة**: لو بُثّ بلاغٌ للأول لوصل قبل الثاني
            notice = await _receive(ws, "notice")
            assert notice == {
                "type": "notice",
                "title": "بقشيش من راكب",
                "body": "أُضيف إلى محفظتك.",
                "data": {"type": "tip_received", "amount": "1.000", "currency": "JOD"},
            }


def test_every_drawn_kind_is_a_known_event() -> None:
    """**ما يُستثنى من البلاغ أحداثٌ لها اسمٌ في الخلفية** — لا نصٌّ يُكتب بيدٍ فيفترق."""
    from app.ws import events

    known = {event.value for event in events.RideEvent} | {
        event.value for event in events.PaymentEvent
    }
    assert notifications.RENDERED_IN_APP <= known
    # **وما لا يُحفظ يُرسم** — العابرُ بلا صفٍّ في الصندوق، فبلا بلاغٍ يمرّ بلا أثر
    assert notifications.EPHEMERAL_KINDS <= notifications.RENDERED_IN_APP
