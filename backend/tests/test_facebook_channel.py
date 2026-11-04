"""قناةُ فيسبوك (SPEC §٩٤/٢): الصلاحيّةُ الحسّاسة، وسلّمُ الحال، والقفلان — **وفيسبوك مُستبدَلٌ هنا، فلا نداءَ يخرج**."""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

import secrets

import pytest
from httpx import AsyncClient

from app.services.facebook import graph, posts as fb_posts
from tests.conftest import _staff_headers

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
#: رمزٌ **مولَّدٌ لا حرفيّ** (APPROVALS-62 §١٥) — ما يُختبر أنه لا يظهر في رسالة خطأ
FAKE_PAGE_KEY = secrets.token_urlsafe(24)
PAGE = graph.Page(page_id="111", token=FAKE_PAGE_KEY)


async def fb_manager(client: AsyncClient, admin_headers: dict, phone: str = "+962790000081") -> dict:
    headers = await _staff_headers("admin", phone, "مدير الصفحة")
    me = (await client.get("/auth/me", headers=headers)).json()
    rows = (await client.get("/admin/permissions", headers=admin_headers)).json()
    row = next(item for item in rows if item["user_id"] == me["id"])
    assert "facebook.manage" not in row["permissions"], "الصلاحيةُ وصلت بالافتراض — وهي لا تُعطى إلا بالاسم"
    granted = await client.put(
        f"/admin/permissions/{me['id']}",
        json={"permissions": sorted(set(row["permissions"]) | {"facebook.manage"})},
        headers=admin_headers,
    )
    assert granted.status_code == 200, granted.text
    return headers


@pytest.fixture(autouse=True)
def no_facebook(monkeypatch: pytest.MonkeyPatch) -> list:
    """**لا نداءَ يخرج**: الصفحةُ والجدولةُ مستبدَلتان، والمهمّةُ لا تُرسل إلى Celery."""
    calls: list = []

    async def fake_page(session):
        return PAGE

    async def fake_photo(p, image, caption, at):
        calls.append(("photo", image.name))
        await asyncio.sleep(0.2)
        return f"{p.page_id}_{len(calls)}"

    monkeypatch.setattr(graph, "page", fake_page)
    monkeypatch.setattr(graph, "schedule_photo", fake_photo)
    monkeypatch.setattr("app.routers.admin_facebook._enqueue", lambda post_id: None)
    return calls


async def _create(client: AsyncClient, headers: dict, **form) -> dict:
    at = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    data = {"title": "منشورٌ للتجربة", "caption": "نصّ", "lang": "ar", "kind": "photo", "scheduled_at": at, **form}
    r = await client.post("/admin/facebook/posts", data=data, files=[("files", ("a.png", PNG, "image/png"))],
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_plain_admin_is_refused(client: AsyncClient, admin_headers: dict) -> None:
    r = await client.get("/admin/facebook/posts", headers=admin_headers)
    assert r.status_code == 403


async def test_approve_then_push_schedules_on_facebook(client, admin_headers, session_factory, no_facebook) -> None:
    h = await fb_manager(client, admin_headers)
    post = await _create(client, h)
    assert post["status"] == "pending_review"
    r = await client.post(f"/admin/facebook/posts/{post['id']}/approve", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    async with session_factory() as s:
        assert await fb_posts.push(s, uuid.UUID(post["id"])) == "scheduled"
        await s.commit()
    listed = (await client.get("/admin/facebook/posts", headers=h)).json()
    row = next(p for p in listed if p["id"] == post["id"])
    assert row["status"] == "scheduled" and row["fb_post_id"] == "111_1"
    # **ما على فيسبوك لا يُرفض من القناة** — قاعدةُ «لا يُحذف منشور»
    r = await client.post(f"/admin/facebook/posts/{post['id']}/decide", json={"decision": "rejected"}, headers=h)
    assert r.status_code == 409


async def test_changes_need_a_note_and_rejected_never_publishes(client, admin_headers) -> None:
    h = await fb_manager(client, admin_headers)
    post = await _create(client, h)
    r = await client.post(f"/admin/facebook/posts/{post['id']}/decide", json={"decision": "changes_requested"}, headers=h)
    assert r.status_code == 400
    r = await client.post(f"/admin/facebook/posts/{post['id']}/decide",
                          json={"decision": "rejected", "note": "لا"}, headers=h)
    assert r.json()["status"] == "rejected"
    r = await client.post(f"/admin/facebook/posts/{post['id']}/approve", headers=h)
    assert r.status_code == 409


async def test_schedule_must_be_in_facebooks_window(client, admin_headers) -> None:
    h = await fb_manager(client, admin_headers)
    post = await _create(client, h, scheduled_at=(datetime.now(UTC) + timedelta(minutes=2)).isoformat())
    r = await client.post(f"/admin/facebook/posts/{post['id']}/approve", headers=h)
    assert r.status_code == 400


async def test_two_approvals_at_once_approve_once(client, admin_headers, monkeypatch) -> None:
    """**القفلُ يملك الحال**: بلا `FOR UPDATE` تقرأ الموافقتان «بانتظار المراجعة» معاً وتنجحان — فتُطلق جدولتان.

    **وتداخلٌ مقصود**: الأولى تمسك صفَّها ثلثَ ثانيةٍ بعد قراءته، فتبدأ الثانيةُ وهي ممسكة — بلا ذلك قد تنتهي الأولى قبل أن تبدأ
    الثانية فيخضرّ الاختبارُ والقفلُ محذوف (وقِيس ذلك)."""
    h = await fb_manager(client, admin_headers)
    post = await _create(client, h)
    real_locked = fb_posts._locked

    async def slow_locked(session, post_id):
        row = await real_locked(session, post_id)
        await asyncio.sleep(0.3)
        return row

    monkeypatch.setattr(fb_posts, "_locked", slow_locked)
    url = f"/admin/facebook/posts/{post['id']}/approve"
    results = await asyncio.wait_for(asyncio.gather(client.post(url, headers=h), client.post(url, headers=h)), 30)
    assert Counter(r.status_code for r in results) == Counter({200: 1, 409: 1})


async def test_two_pushes_at_once_create_one_facebook_post(client, admin_headers, session_factory, no_facebook) -> None:
    """**والقفلُ يمنع منشورين على فيسبوك**: مهمّتان معاً لموافقةٍ واحدة — نداءٌ واحدٌ يخرج."""
    h = await fb_manager(client, admin_headers)
    post = await _create(client, h)
    await client.post(f"/admin/facebook/posts/{post['id']}/approve", headers=h)

    async def push() -> str:
        async with session_factory() as s:
            result = await fb_posts.push(s, uuid.UUID(post["id"]))
            await s.commit()
            return result

    results = await asyncio.wait_for(asyncio.gather(push(), push()), 30)
    assert sorted(results) == ["scheduled", "skip"]
    assert len(no_facebook) == 1


async def test_group_approval_and_requests(client, admin_headers) -> None:
    h = await fb_manager(client, admin_headers)
    await _create(client, h, group_key="g1", lang="ar")
    await _create(client, h, group_key="g1", lang="fr")
    r = await client.post("/admin/facebook/groups/g1/approve", headers=h)
    assert r.status_code == 200 and {p["status"] for p in r.json()} == {"approved"} and len(r.json()) == 2
    r = await client.post("/admin/facebook/requests", json={"body": "ثلاثةُ منشوراتٍ عن المطار", "count": 3}, headers=h)
    assert r.status_code == 201
    rid = r.json()["id"]
    r = await client.post(f"/admin/facebook/requests/{rid}/done", json={"answer": "رُفعت للمراجعة"}, headers=h)
    assert r.json()["status"] == "done"


async def test_sync_imports_and_tracks_publication(client, admin_headers, monkeypatch) -> None:
    h = await fb_manager(client, admin_headers)

    async def scheduled(p):
        return [{"id": "111_5", "message": "Votre course", "scheduled_publish_time": 1800000000}]

    async def published(p, limit=100):
        return [{"id": "111_6", "message": "منشورٌ قديم", "created_time": "2026-11-04T01:27:00+0000",
                 "permalink_url": "https://www.facebook.com/x", "reactions": {"summary": {"total_count": 4}},
                 "comments": {"summary": {"total_count": 1}}, "shares": {"count": 2}},
                {"id": "999_7", "message": "صفحةٌ أخرى"}]

    monkeypatch.setattr(graph, "scheduled_posts", scheduled)
    monkeypatch.setattr(graph, "published_posts", published)
    r = await client.post("/admin/facebook/sync", headers=h)
    assert r.status_code == 200 and r.json()["imported"] == 2, r.text
    rows = {p["fb_post_id"]: p for p in (await client.get("/admin/facebook/posts", headers=h)).json()}
    assert rows["111_5"]["status"] == "scheduled" and rows["111_5"]["lang"] == "fr"
    assert rows["111_6"]["status"] == "published" and rows["111_6"]["stats"] == {"reactions": 4, "comments": 1, "shares": 2}
    # **منشورُ صفحةٍ أخرى لا يدخل القناة** — الرمزُ لصفحةٍ واحدة
    assert "999_7" not in rows


def test_token_never_leaves_in_an_error() -> None:
    assert FAKE_PAGE_KEY not in PAGE.scrub(f"bad {FAKE_PAGE_KEY} here")
    assert not PAGE.owns("999_1") and PAGE.owns("111_1")
