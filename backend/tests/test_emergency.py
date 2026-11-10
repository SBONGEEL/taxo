"""**زرُّ الطوارئ ومشاركةُ الرحلة وأرقامُ التواصل** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٧ و٨)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.support import EmergencyAlert
from tests.helpers import (
    DRIVER,
    OTHER_RIDER,
    accepted_ride,
    approved_driver,
    auth,
    bring_online,
    broadcast_location,
    register,
    rider_session,
)

pytestmark = pytest.mark.asyncio


async def _ride(client: AsyncClient, session_factory) -> tuple[dict, dict, dict]:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = (await rider_session(client))["headers"]
    ride = await accepted_ride(client, rider, driver)
    return rider, driver, ride


async def test_own_ride_share_link_shows_first_name_and_ends_with_the_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**«شارك رحلتك» لرحلة الراكب نفسِه** — بلا مفتاح «لغيرك»، **والاسمُ الأوّلُ وحدَه**، ويتوقّف بانتهاء الرحلة."""
    rider, driver, ride = await _ride(client, session_factory)
    made = await client.post(f"/rides/{ride['id']}/track-link", headers=rider)
    assert made.status_code == 200, made.text
    token = made.json()["token"]

    await broadcast_location(client, driver, lat=31.9600, lng=35.9106)
    view = (await client.get(f"/public/track/{token}")).json()
    assert view["state"] == "coming"
    assert view["captain_name"] == DRIVER["name"].split()[0]
    assert view["position"] is not None

    for step in ("arrive", "start", "complete"):
        assert (await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])).status_code == 200
    assert (await client.get(f"/public/track/{token}")).json()["state"] == "ended"


async def test_emergency_press_from_both_sides_reaches_the_panel_and_is_handled_once(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    rider, driver, ride = await _ride(client, session_factory)

    # **غريبٌ لا يضغط على رحلةٍ ليست له** — ٤٠٤ لا ٤٠٣
    stranger = auth(await register(client, OTHER_RIDER))
    refused = await client.post("/emergency", json={"app": "rider", "ride_id": ride["id"]}, headers=stranger)
    assert refused.status_code == 404

    first = await client.post(
        "/emergency", json={"app": "rider", "ride_id": ride["id"], "lat": 31.95, "lng": 35.91}, headers=rider
    )
    assert first.status_code == 200, first.text
    assert first.json()["emergency_number"] == "911", "الرقمُ الرسميُّ قبل أن يضع المالكُ شيئاً"
    # **ضغطتان في ذعرٍ حالةٌ واحدة**
    again = await client.post("/emergency", json={"app": "rider", "ride_id": ride["id"]}, headers=rider)
    assert again.json()["id"] == first.json()["id"]

    from_captain = await client.post(
        "/emergency", json={"app": "driver", "ride_id": ride["id"]}, headers=driver["headers"]
    )
    assert from_captain.status_code == 200, from_captain.text
    assert from_captain.json()["id"] != first.json()["id"]

    rows = (await client.get("/admin/emergencies", headers=admin_headers)).json()
    assert len(rows) == 2
    mine = next(row for row in rows if row["id"] == first.json()["id"])
    assert mine["role"] == "rider" and mine["status"] == "open"
    assert mine["rider"]["name"] and mine["driver"]["name"] == DRIVER["name"]
    assert mine["plate_number"] and mine["lat"] == 31.95

    short = await client.post(f"/admin/emergencies/{mine['id']}/handle", json={"note": "x"}, headers=admin_headers)
    assert short.status_code == 422
    done = await client.post(
        f"/admin/emergencies/{mine['id']}/handle", json={"note": "اتّصلنا بالراكب وهو بخير"}, headers=admin_headers
    )
    assert done.status_code == 204, done.text
    twice = await client.post(
        f"/admin/emergencies/{mine['id']}/handle", json={"note": "مرّةٌ ثانية"}, headers=admin_headers
    )
    assert twice.status_code == 422

    open_rows = (await client.get("/admin/emergencies", headers=admin_headers)).json()
    assert [row["id"] for row in open_rows] == [from_captain.json()["id"]]
    handled = (await client.get("/admin/emergencies?status=handled", headers=admin_headers)).json()
    assert handled[0]["note"] == "اتّصلنا بالراكب وهو بخير" and handled[0]["handled_by_name"]

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(EmergencyAlert))
    assert count == 2


async def test_emergency_outside_a_ride_and_rider_cannot_press_as_captain(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider, _driver, ride = await _ride(client, session_factory)
    loose = await client.post("/emergency", json={"app": "rider"}, headers=rider)
    assert loose.status_code == 200, loose.text
    # الراكبُ ليس كبتنَ هذه الرحلة
    posing = await client.post("/emergency", json={"app": "driver", "ride_id": ride["id"]}, headers=rider)
    assert posing.status_code == 404


async def test_support_contacts_from_the_panel(client: AsyncClient, admin_headers: dict) -> None:
    """**رقمُ الطوارئ وواتسابُ الدعم لكلِّ دولة** — بلا صفٍّ: الرسميُّ وواتسابٌ غائب؛ والصيغةُ الدوليّةُ تُفحص."""
    before = (await client.get("/support/contacts?country_code=DZ")).json()
    assert before == {"country_code": "DZ", "emergency_number": "17", "whatsapp_number": None}
    assert (await client.get("/support/contacts?country_code=LY")).json()["emergency_number"] is None

    bad = await client.put(
        "/admin/support-settings/DZ", json={"emergency_number": "17", "whatsapp_number": "0555"}, headers=admin_headers
    )
    assert bad.status_code == 422
    saved = await client.put(
        "/admin/support-settings/DZ",
        json={"emergency_number": "1548", "whatsapp_number": "+213 555 12 34 56"},
        headers=admin_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["whatsapp_number"] == "213555123456"
    after = (await client.get("/support/contacts?country_code=DZ")).json()
    assert after["emergency_number"] == "1548" and after["whatsapp_number"] == "213555123456"


async def test_unknown_alert_cannot_be_handled(client: AsyncClient, admin_headers: dict) -> None:
    missing = await client.post(
        f"/admin/emergencies/{uuid.uuid4()}/handle", json={"note": "لا شيء هنا"}, headers=admin_headers
    )
    assert missing.status_code == 404
