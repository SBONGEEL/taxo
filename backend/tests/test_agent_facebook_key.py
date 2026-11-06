"""**مفتاحُ وكيل فيسبوك** (SPEC §٩٤/٧) — يفتح قناةَ فيسبوك وحدَها، ولا يحكم، ولا يفتح شيئاً آخر."""

from __future__ import annotations

import hashlib
import secrets

import pytest
from httpx import AsyncClient

from app.routers import agent_facebook
from tests.test_facebook_channel import fb_manager

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def agent_key(monkeypatch: pytest.MonkeyPatch) -> dict:
    """مفتاحٌ مولَّدٌ للاختبار وبصمتُه — لا حرفيّ."""
    key = "fbk_" + secrets.token_urlsafe(32)
    monkeypatch.setattr(agent_facebook, "FACEBOOK_AGENT_KEY_SHA256", hashlib.sha256(key.encode()).hexdigest())
    return {"X-TAXO-Agent-Key": key}


async def test_no_key_or_a_wrong_key_is_refused(client: AsyncClient, agent_key: dict) -> None:
    assert (await client.get("/agent/facebook/posts")).status_code == 401
    wrong = {"X-TAXO-Agent-Key": "fbk_" + secrets.token_urlsafe(32)}
    assert (await client.get("/agent/facebook/posts", headers=wrong)).status_code == 401


async def test_a_draft_enters_review_and_the_owners_decision_is_read_back(
    client: AsyncClient, agent_key: dict, admin_headers: dict
) -> None:
    created = await client.post(
        "/agent/facebook/posts",
        data={"title": "مسوّدة", "caption": "نصّ", "lang": "ar", "kind": "photo"},
        files=[("files", ("a.png", PNG, "image/png"))],
        headers=agent_key,
    )
    assert created.status_code == 201, created.text
    post = created.json()
    assert post["status"] == "pending_review"
    # **القرارُ للمالك من اللوحة** (مشرفٌ بصلاحيّة فيسبوك) — والوكيلُ يقرؤه
    manager = await fb_manager(client, admin_headers)
    decided = await client.post(
        f"/admin/facebook/posts/{post['id']}/decide",
        json={"decision": "changes_requested", "note": "قصّر النصّ"},
        headers=manager,
    )
    assert decided.status_code == 200, decided.text
    listed = (await client.get("/agent/facebook/posts", headers=agent_key)).json()
    mine = next(p for p in listed if p["id"] == post["id"])
    assert mine["status"] == "changes_requested" and mine["review_note"] == "قصّر النصّ"


async def test_a_published_or_scheduled_post_is_recorded_once(client: AsyncClient, agent_key: dict) -> None:
    body = {"status": "published", "fb_post_id": "123_456", "title": "منشورٌ قائم", "published_at": "2026-11-06T10:00:00Z"}
    first = await client.post("/agent/facebook/posts/record", json=body, headers=agent_key)
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "published" and first.json()["fb_post_id"] == "123_456"
    again = await client.post("/agent/facebook/posts/record", json=body, headers=agent_key)
    assert again.status_code == 409
    scheduled = {"status": "scheduled", "fb_post_id": "123_789", "title": "مجدول"}
    assert (await client.post("/agent/facebook/posts/record", json=scheduled, headers=agent_key)).status_code == 400
    scheduled["scheduled_at"] = "2026-11-08T17:00:00Z"
    assert (await client.post("/agent/facebook/posts/record", json=scheduled, headers=agent_key)).status_code == 201


async def test_the_key_decides_nothing_and_opens_no_other_door(client: AsyncClient, agent_key: dict) -> None:
    """**لا حكمَ ولا بابَ غيرُ القناة**: أبوابُ اللوحة — فيسبوكُ نفسُه والمالُ والمستخدمون والإعدادات — لا تقبل المفتاح."""
    for path in ("/admin/facebook/posts", "/admin/users", "/admin/drivers", "/admin/settings/commission",
                 "/admin/finance/summary", "/auth/me", "/drivers/me/earnings"):
        response = await client.get(path, headers=agent_key)
        assert response.status_code in (401, 403), (path, response.status_code)
    # **ولا بابَ قرارٍ تحت `/agent`**
    assert (await client.post("/agent/facebook/posts/00000000-0000-0000-0000-000000000000/approve",
                              headers=agent_key)).status_code in (404, 405)
