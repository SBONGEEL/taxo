"""**التذاكر** (البندان ٨ و٩) — المحادثةُ مع الدعم، و«نسيت شيئاً» بخيطٍ مع الكبتن بلا أرقام، والشكوى بفئتها، والحسمُ بسببٍ تحت قفل."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from tests.helpers import (
    NEAR_PICKUP,
    OTHER_RIDER,
    approved_driver,
    bring_online,
    completed_ride,
    inbox_of,
    real_jpeg,
    rider_session,
)


async def _ride(client: AsyncClient, session_factory):
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver, NEAR_PICKUP)
    rider = await rider_session(client)
    ride = await completed_ride(client, rider["headers"], driver)
    # **لا حسابَ تجربةٍ يبقى متّصلاً**
    await client.post("/drivers/me/offline", headers=driver["headers"])
    return rider, driver, ride


async def test_support_chat_without_a_ride_and_the_staff_reply(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    rider = await rider_session(client)
    opened = await client.post(
        "/support/tickets", data={"app": "rider", "kind": "support", "body": "التطبيقُ لا يفتح الخريطة"}, headers=rider["headers"]
    )
    assert opened.status_code == 201, opened.text
    ticket = opened.json()
    assert ticket["status"] == "open" and ticket["my_role"] == "user" and len(ticket["messages"]) == 1

    queue = await client.get("/admin/support/tickets", params={"waiting": "true"}, headers=admin_headers)
    assert queue.status_code == 200, queue.text
    assert any(item["id"] == ticket["id"] for item in queue.json()["items"])

    replied = await client.post(f"/admin/support/tickets/{ticket['id']}/messages", json={"body": "جرّب تحديث التطبيق"}, headers=admin_headers)
    assert replied.status_code == 200, replied.text
    detail = replied.json()
    assert detail["status"] == "in_review" and detail["needs_staff"] is False
    assert detail["account"]["name"]

    mine = await client.get(f"/support/tickets/{ticket['id']}", headers=rider["headers"])
    assert [m["author_role"] for m in mine.json()["messages"]] == ["user", "staff"]
    notes = await inbox_of(session_factory, uuid.UUID(rider["user"]["id"]))
    assert any(n.kind == "support_update" and n.data.get("ticket_id") == ticket["id"] for n in notes)

    # **غيرُ صاحبها لا يراها** — ٤٠٤ لا ٤٠٣
    other = await rider_session(client, OTHER_RIDER)
    assert (await client.get(f"/support/tickets/{ticket['id']}", headers=other["headers"])).status_code == 404

    # **الحسمُ بسبب**، والسببُ يصل صاحبَها
    no_reason = await client.patch(f"/admin/support/tickets/{ticket['id']}", json={"status": "resolved"}, headers=admin_headers)
    assert no_reason.status_code == 422
    done = await client.patch(
        f"/admin/support/tickets/{ticket['id']}", json={"status": "resolved", "reason": "أُصلح في الإصدار الأخير"}, headers=admin_headers
    )
    assert done.status_code == 200, done.text
    closed = await client.post(f"/support/tickets/{ticket['id']}/messages", json={"body": "شكراً"}, headers=rider["headers"])
    assert closed.status_code == 409 and closed.json()["code"] == "support_ticket_closed"


async def test_lost_item_thread_with_the_driver_and_no_phone_numbers(client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict) -> None:
    rider, driver, ride = await _ride(client, session_factory)
    opened = await client.post(
        "/support/tickets",
        data={"app": "rider", "kind": "lost_item", "ride_id": ride["id"], "body": "نسيتُ حقيبةً سوداء في المقعد الخلفيّ"},
        headers=rider["headers"],
    )
    assert opened.status_code == 201, opened.text
    ticket_id = opened.json()["id"]

    # **والثانيةُ على الرحلة نفسِها تُرفض** — طلبٌ قائمٌ واحد
    again = await client.post(
        "/support/tickets",
        data={"app": "rider", "kind": "lost_item", "ride_id": ride["id"], "body": "مرّةً ثانية"},
        headers=rider["headers"],
    )
    assert again.status_code == 409 and again.json()["code"] == "support_ticket_active"

    # الكبتنُ يعلم ويرى الخيط بصفة «طرف»
    driver_notes = await inbox_of(session_factory, uuid.UUID(str(driver["user_id"])))
    assert any(n.kind == "support_update" and n.data.get("ticket_id") == ticket_id for n in driver_notes)
    listed = (await client.get("/support/tickets", headers=driver["headers"])).json()
    assert [t["my_role"] for t in listed if t["id"] == ticket_id] == ["party"]

    phone = await client.post(f"/support/tickets/{ticket_id}/messages", json={"body": "كلّمني على 0791234567"}, headers=driver["headers"])
    assert phone.status_code == 422
    found = await client.post(f"/support/tickets/{ticket_id}/messages", json={"body": "وجدتُها، سأسلّمها للمكتب"}, headers=driver["headers"])
    assert found.status_code == 201, found.text
    seen = (await client.get(f"/support/tickets/{ticket_id}", headers=rider["headers"])).json()
    assert [m["author_role"] for m in seen["messages"]] == ["user", "party"]


async def test_complaint_needs_a_category_and_counts_against_the_driver(client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict) -> None:
    rider, driver, ride = await _ride(client, session_factory)
    missing = await client.post(
        "/support/tickets",
        data={"app": "rider", "kind": "complaint", "ride_id": ride["id"], "body": "قيادةٌ متهوّرة"},
        headers=rider["headers"],
    )
    assert missing.status_code == 422
    opened = await client.post(
        "/support/tickets",
        data={"app": "rider", "kind": "complaint", "ride_id": ride["id"], "category": "safety", "body": "قيادةٌ متهوّرة"},
        files={"photo": ("shot.jpg", real_jpeg(), "image/jpeg")},
        headers=rider["headers"],
    )
    assert opened.status_code == 201, opened.text
    ticket_id = opened.json()["id"]
    assert opened.json()["has_photo"] is True
    # **الكبتنُ لا يرى الشكوى عليه**
    assert (await client.get(f"/support/tickets/{ticket_id}", headers=driver["headers"])).status_code == 404
    photo = await client.get(f"/admin/support/tickets/{ticket_id}/photo", headers=admin_headers)
    assert photo.status_code == 200 and photo.headers["content-type"].startswith("image/")

    stats = (await client.get("/admin/support/tickets/stats", headers=admin_headers)).json()
    assert any(row["user_id"] == str(driver["user_id"]) and row["complaints"] == 1 for row in stats["drivers"])
    assert any(row["category"] == "safety" for row in stats["by_category"])
