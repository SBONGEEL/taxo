"""«أرسل ملاحظة» (SPEC §٧٦/٤) — **من أرسل · أيُّ تطبيق · أيُّ إصدار · متى**، والصورةُ الاختياريّة، والحدّ، والمحوُ مع صاحبها."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core import storage
from app.core.redis_client import get_redis_client
from app.models.audit import AdminAuditLog
from app.models.feedback import AppFeedback
from app.models.user import User
from app.services import account_deletion
from app.services import feedback as feedback_service
from tests.helpers import RIDER, auth, real_jpeg, register

pytestmark = pytest.mark.asyncio


def _form(**over) -> dict:
    body = {
        "app": "rider",
        "message": "زرُّ الدفع لا يظهر بعد الرحلة",
        "app_version": "1.1+517",
        "web_build": "index-CNIiPnnL.js",
        "platform": "android",
        "route": "/rides/:rideId",
    }
    body.update(over)
    return body


async def _send(client: AsyncClient, headers: dict, *, screenshot: bytes | None = None, **over):
    files = {"screenshot": ("shot.jpg", screenshot, "image/jpeg")} if screenshot is not None else None
    return await client.post("/feedback", data=_form(**over), files=files, headers=headers)


def _on_disk(relative_path: str) -> bool:
    return (storage.root().resolve() / relative_path).is_file()


async def _count(session_factory) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(AppFeedback)))


# ------------------------------------------------------------------ الإرسال


async def test_a_note_reaches_the_panel_with_who_which_app_which_version_and_when(
    client: AsyncClient, admin_headers
) -> None:
    rider = auth(await register(client, RIDER))
    sent = await _send(client, rider)
    assert sent.status_code == 201, sent.text

    page = await client.get("/admin/feedback", headers=admin_headers)
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total"] == 1 and body["new_count"] == 1
    item = body["items"][0]
    assert item["user_name"] == RIDER["name"]
    assert item["user_phone"].endswith(RIDER["phone"][-9:])
    assert item["app"] == "rider"
    assert item["app_version"] == "1.1+517" and item["web_build"] == "index-CNIiPnnL.js"
    assert item["platform"] == "android" and item["route"] == "/rides/:rideId"
    assert item["message"] == "زرُّ الدفع لا يظهر بعد الرحلة"
    assert item["has_screenshot"] is False and item["handled_at"] is None
    assert datetime.fromisoformat(item["created_at"]) > datetime.now(UTC) - timedelta(minutes=5)


async def test_the_screenshot_is_served_to_staff_with_document_headers(
    client: AsyncClient, admin_headers
) -> None:
    rider = auth(await register(client, RIDER))
    image = real_jpeg()
    sent = await _send(client, rider, screenshot=image, app="driver")
    assert sent.status_code == 201, sent.text

    item = (await client.get("/admin/feedback", headers=admin_headers)).json()["items"][0]
    assert item["has_screenshot"] is True and item["app"] == "driver"
    shot = await client.get(f"/admin/feedback/{item['id']}/screenshot", headers=admin_headers)
    assert shot.status_code == 200
    assert shot.content == image
    assert shot.headers["content-type"] == "image/jpeg"
    assert shot.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in shot.headers["cache-control"]


async def test_a_pdf_is_refused_and_leaves_no_file(client: AsyncClient, session_factory, document_storage) -> None:
    rider = auth(await register(client, RIDER))
    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    refused = await client.post(
        "/feedback", data=_form(), files={"screenshot": ("a.pdf", pdf, "application/pdf")}, headers=rider
    )
    assert refused.status_code == 422, refused.text
    assert await _count(session_factory) == 0
    assert not [p for p in document_storage.rglob("*") if p.is_file()]


async def test_an_empty_note_is_refused(client: AsyncClient) -> None:
    rider = auth(await register(client, RIDER))
    refused = await _send(client, rider, message="   ")
    assert refused.status_code == 422, refused.text


async def test_an_unknown_app_is_refused(client: AsyncClient) -> None:
    rider = auth(await register(client, RIDER))
    refused = await _send(client, rider, app="panel")
    assert refused.status_code == 422, refused.text


async def test_sending_needs_a_session(client: AsyncClient) -> None:
    refused = await client.post("/feedback", data=_form())
    assert refused.status_code == 401


async def test_ten_an_hour_then_refused(client: AsyncClient, session_factory) -> None:
    rider = auth(await register(client, RIDER))
    for _ in range(feedback_service.PER_HOUR):
        assert (await _send(client, rider)).status_code == 201
    refused = await _send(client, rider)
    assert refused.status_code == 429, refused.text
    assert await _count(session_factory) == feedback_service.PER_HOUR


# ------------------------------------------------------------------ اللوحة


async def test_riders_cannot_read_the_list(client: AsyncClient) -> None:
    rider = auth(await register(client, RIDER))
    assert (await client.get("/admin/feedback", headers=rider)).status_code == 403


async def test_support_can_read_the_list(client: AsyncClient, support_headers) -> None:
    assert (await client.get("/admin/feedback", headers=support_headers)).status_code == 200


async def test_marking_handled_filters_and_is_audited(client: AsyncClient, admin_headers, session_factory) -> None:
    rider = auth(await register(client, RIDER))
    await _send(client, rider)
    await _send(client, rider, message="ملاحظةٌ ثانية")
    first = (await client.get("/admin/feedback", headers=admin_headers)).json()["items"][0]

    done = await client.patch(f"/admin/feedback/{first['id']}", json={"handled": True}, headers=admin_headers)
    assert done.status_code == 200, done.text
    assert done.json()["handled_at"] is not None and done.json()["user_name"] == RIDER["name"]

    new = (await client.get("/admin/feedback?status=new", headers=admin_headers)).json()
    handled = (await client.get("/admin/feedback?status=handled", headers=admin_headers)).json()
    assert new["total"] == 1 and new["new_count"] == 1
    assert [i["id"] for i in handled["items"]] == [first["id"]]

    async with session_factory() as session:
        audited = await session.scalar(
            select(func.count()).select_from(AdminAuditLog).where(AdminAuditLog.entity_type == "app_feedback")
        )
    assert audited == 1

    reopened = await client.patch(f"/admin/feedback/{first['id']}", json={"handled": False}, headers=admin_headers)
    assert reopened.json()["handled_at"] is None


async def test_filter_by_app(client: AsyncClient, admin_headers) -> None:
    rider = auth(await register(client, RIDER))
    await _send(client, rider, app="rider")
    await _send(client, rider, app="driver")
    only = (await client.get("/admin/feedback?app=driver", headers=admin_headers)).json()
    assert only["total"] == 1 and only["items"][0]["app"] == "driver"


# ------------------------------------------------------------------ المحو


async def test_anonymizing_the_account_erases_its_notes_and_screenshots(
    client: AsyncClient, session_factory
) -> None:
    body = await register(client, RIDER)
    rider = auth(body)
    assert (await _send(client, rider, screenshot=real_jpeg())).status_code == 201
    async with session_factory() as session:
        path = await session.scalar(select(AppFeedback.screenshot_path))
    assert path and _on_disk(path)

    requested = await client.post("/account/deletion", json={}, headers=rider)
    assert requested.status_code == 201, requested.text
    uid = uuid.UUID(str(body.get("user_id") or body["user"]["id"]))
    async with session_factory() as session:
        await session.execute(
            update(User).where(User.id == uid).values(deletion_due_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()
    await account_deletion.anonymize_due(session_factory, get_redis_client())

    assert await _count(session_factory) == 0
    assert not _on_disk(path)


async def test_notes_older_than_a_year_expire_with_their_files(client: AsyncClient, session_factory) -> None:
    rider = auth(await register(client, RIDER))
    await _send(client, rider, screenshot=real_jpeg())
    await _send(client, rider, message="حديثة")
    async with session_factory() as session:
        old = await session.scalar(select(AppFeedback).where(AppFeedback.screenshot_path.is_not(None)))
        old.created_at = datetime.now(UTC) - timedelta(days=feedback_service.RETENTION_DAYS + 1)
        path = old.screenshot_path
        await session.commit()

    async with session_factory() as session:
        files = await feedback_service.expired_rows(session)
        await session.commit()
    await feedback_service.delete_files(files)

    assert files == [path] and not _on_disk(path)
    assert await _count(session_factory) == 1
