"""**إشعارُ «جديد: ودجات TAXO لشاشتك»** (أمرُ المالك ٢٠٢٦-١١-٢١ الثالث، البند ٦، الترحيلة `0185`).

ثلاثةُ ثوابت: **يصل من حدّث وحدَه** (جهازٌ قال إن غلافَه يحمل الودجات، لا جهازُه القديم)، **ويُنشأ مرّةً لكلِّ دولة** (إطفاءُ المفتاح وإشعالُه
لا يعيده)، **ولا يُشعَل وودجاتُ الراكب مطفأة** (إشعارٌ عن ودجاتٍ لا تظهر وعدٌ بلا باب).
"""

from __future__ import annotations

from datetime import time

from httpx import AsyncClient
from sqlalchemy import select

from app.models.notification import NotificationCampaign
from tests.helpers import RIDER, auth, enable_push_provider, pushes_to, register

FLAGS = "/admin/settings/feature-flags"


async def _flag(client: AsyncClient, headers: dict, key: str, enabled: bool, country: str = "JO"):
    return await client.put(
        FLAGS, json={"country_code": country, "feature_key": key, "enabled": enabled}, headers=headers
    )


async def _device(client: AsyncClient, headers: dict, *, device_id: str, token: str, widgets: bool | None) -> None:
    payload: dict = {"device_id": device_id, "token": token, "platform": "android"}
    # **كما يرسله التطبيق**: غائباً من غلافٍ أقدم، `true` من غلافٍ يحمل الودجات
    if widgets is not None:
        payload["shell_widgets"] = widgets
    response = await client.put("/me/devices", json=payload, headers=headers)
    assert response.status_code == 200, response.text


async def _no_quiet_hours(session_factory) -> None:
    from app.models.enums import CountryCode
    from app.services import campaigns

    async with session_factory() as session:
        setting = await campaigns.get_or_create_settings(session, CountryCode("JO"))
        setting.quiet_hours_start = time(0, 0)
        setting.quiet_hours_end = time(0, 0)
        setting.timezone = "UTC"
        await session.commit()


async def _announce_campaigns(session_factory) -> list[NotificationCampaign]:
    async with session_factory() as session:
        return list(await session.scalars(select(NotificationCampaign).where(NotificationCampaign.widgets_only.is_(True))))


async def _dispatch(session_factory, campaign_id) -> object:
    from app.services import campaigns

    async with session_factory() as session:
        campaign = await campaigns.get_campaign(session, campaign_id, for_update=True)
        result = await campaigns.dispatch(session, campaign)
        await session.commit()
    return result


async def test_the_switch_waits_for_the_rider_widgets(client: AsyncClient, admin_headers: dict, session_factory) -> None:
    response = await _flag(client, admin_headers, "widgets_announce", True)
    assert response.status_code == 422, response.text
    assert await _announce_campaigns(session_factory) == []


async def test_it_reaches_only_the_updated_device_and_is_created_once(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    await enable_push_provider(session_factory)
    await _no_quiet_hours(session_factory)

    updated = auth(await register(client, RIDER))
    await _device(client, updated, device_id="new-phone", token="fcm-updated-new", widgets=True)
    # **وهاتفُه الثاني لم يُحدَّث** — لا يصله
    await _device(client, updated, device_id="old-phone", token="fcm-updated-old", widgets=None)
    stale = auth(await register(client, RIDER | {"phone": "0794444444"}))
    await _device(client, stale, device_id="stale-phone", token="fcm-stale", widgets=None)

    assert (await _flag(client, admin_headers, "rider_widgets_plus", True)).status_code == 200
    assert (await _flag(client, admin_headers, "widgets_announce", True)).status_code == 200

    created = await _announce_campaigns(session_factory)
    assert len(created) == 1
    assert created[0].title == "جديد: ودجات TAXO لشاشتك"

    result = await _dispatch(session_factory, created[0].id)
    assert result.sent == 1
    assert [m["title"] for m in await pushes_to("fcm-updated-new")] == ["جديد: ودجات TAXO لشاشتك"]
    assert await pushes_to("fcm-updated-old") == []
    assert await pushes_to("fcm-stale") == []

    # **إطفاءٌ ثمّ إشعالٌ لا يعيده**
    assert (await _flag(client, admin_headers, "widgets_announce", False)).status_code == 200
    assert (await _flag(client, admin_headers, "widgets_announce", True)).status_code == 200
    assert len(await _announce_campaigns(session_factory)) == 1


async def test_a_device_that_goes_back_to_an_older_shell_loses_the_mark(
    client: AsyncClient, session_factory
) -> None:
    from app.models.device import DeviceToken

    rider = auth(await register(client, RIDER))
    await _device(client, rider, device_id="phone", token="fcm-phone-1", widgets=True)
    await _device(client, rider, device_id="phone", token="fcm-phone-1", widgets=None)
    async with session_factory() as session:
        device = await session.scalar(select(DeviceToken).where(DeviceToken.device_id == "phone"))
        assert device is not None and device.shell_widgets is False
