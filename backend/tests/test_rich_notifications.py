"""**الإشعاراتُ الغنيّة للراكب** (SPEC §١٠٣/12، أمرُ المالك ٢٠٢٦-١١-١٨).

ثلاثةُ أشياءَ تُقاس هنا:
1. **الشكلُ لكلِّ مجموعة** — الخامسةُ والمفتاحُ مشتعلٌ بياناتٌ ترسمها `RideNotice` على **قناة النغمة نفسِها**؛ وما دونها
   أو المفتاحُ مطفأٌ **كما كان حرفاً**.
2. **بابُ الصورة الموقَّع** — يفتح بالرمز لهذه الرحلة وكبتنها، **ويردّ ما يردّه بابُ التطبيق بايتاً**، ولا يفتح لرحلةٍ أخرى
   ولا برمز دخولٍ عاديّ ولا بعد انتهاء الرحلة.
3. **رمزُ الصورة لا يصلح رمزَ دخول** — نوعُه `push_photo` يرفضه كلُّ بابٍ يطلب `access`.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.core.security import create_push_photo_token
from app.services.push import PushMessage, channels
from tests.helpers import DRIVER, accepted_ride, approved_driver, bring_online, rider_session

RICH_DATA = {"driver_name": "كبتن", "plate": "12-34567", "vehicle": "تويوتا كامري أبيض", "photo_url": "https://x/p"}


def _assigned() -> PushMessage:
    return PushMessage(
        title="تم قبول رحلتك",
        body="الكبتن في طريقه إلى نقطة الانطلاق",
        data={"type": "driver_assigned", "ride_id": "r1"},
        native_data=dict(RICH_DATA),
    )


def test_fifth_level_with_switch_is_drawn_natively_on_the_tone_channel() -> None:
    shaped = channels.for_level(_assigned(), channels.CHANNELS_V5, "s1_2", rich=True)
    assert shaped is not None and shaped.data_only
    assert shaped.data["rich"] == "1"
    assert shaped.data["channel"] == "taxo.accepted.s1_2"
    assert shaped.data["title"] == "تم قبول رحلتك"
    assert shaped.data["plate"] == "12-34567"


def test_switch_off_or_older_levels_stay_as_they_were() -> None:
    for level, rich in ((channels.CHANNELS_V5, False), (channels.CHANNELS_V4, True), (channels.CHANNELS_V3, True)):
        shaped = channels.for_level(_assigned(), level, "s1_2", rich=rich)
        assert shaped is not None and not shaped.data_only
        assert "plate" not in shaped.data and "photo_url" not in shaped.data


def test_rich_without_card_falls_back_to_system_drawing() -> None:
    bare = PushMessage(title="t", body="b", data={"type": "driver_arrived", "ride_id": "r1"})
    shaped = channels.for_level(bare, channels.CHANNELS_V5, None, rich=True)
    assert shaped is not None and not shaped.data_only


def test_level_five_is_recognised() -> None:
    assert channels.level_of(5) == channels.CHANNELS_V5
    assert channels.level_of(9) == channels.CHANNELS_V6
    # **والسادسةُ تحمل الغنيَّ كالخامسة** — «بيب بيب» لا يُسقط إشعارَ الكبتن الغنيّ
    assert channels.for_level(_assigned(), channels.CHANNELS_V6, "s1_2", rich=True).data.get("rich") == "1"
    assert channels.level_of(4) == channels.CHANNELS_V4


async def test_signed_photo_door_matches_the_app_door_and_nothing_else(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)
    signed = create_push_photo_token(ride["id"], driver["driver_id"])

    via_app = await client.get(f"/rides/{ride['id']}/driver/photo", headers=rider["headers"])
    via_push = await client.get(f"/rides/{ride['id']}/driver/photo/push", params={"t": signed})
    assert via_push.status_code == 200
    assert via_push.content == via_app.content
    assert via_push.headers["cache-control"] == "private, no-store"

    # رمزٌ لرحلةٍ أخرى، أو لكبتنٍ آخر، أو رمزُ دخولٍ عاديّ — لا يفتح
    other = create_push_photo_token("00000000-0000-0000-0000-000000000000", driver["driver_id"])
    assert (await client.get(f"/rides/{ride['id']}/driver/photo/push", params={"t": other})).status_code == 404
    wrong_driver = create_push_photo_token(ride["id"], "00000000-0000-0000-0000-000000000000")
    assert (await client.get(f"/rides/{ride['id']}/driver/photo/push", params={"t": wrong_driver})).status_code == 404
    access = rider["token"]
    assert (await client.get(f"/rides/{ride['id']}/driver/photo/push", params={"t": access})).status_code == 404

    # ورمزُ الصورة لا يصلح رمزَ دخول
    assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {signed}"})).status_code == 401
