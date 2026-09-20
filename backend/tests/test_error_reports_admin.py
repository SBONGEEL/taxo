"""شاشةُ الأعطال في اللوحة — **والترتيبُ الافتراضيُّ هو الدعوى المقيسة** (2026-09-20).

`test_default_sort_is_by_affected_users` هو الاختبارُ الذي يحرس القرارَ الذي
بُنيت الشاشةُ عليه: **حلقةُ رسمٍ في هاتفٍ واحدٍ لا تتصدّر عطباً يمسّ الأسطول**.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.models.audit import AdminAuditLog
from app.models.error_report import ErrorEvent, ErrorGroup
from app.services import error_reports

pytestmark = pytest.mark.asyncio


def payload(**over) -> dict:
    body = {
        "app": "rider",
        "kind": "error",
        "platform": "android",
        "release": "1.4.0",
        "device_hash": "a" * 32,
        "route": "/rides/:rideId",
        "name": "TypeError",
        "message": "Cannot read properties of undefined",
        "stack": "at Payment (main.js:142:18)",
        "occurred_at": datetime.now(UTC).isoformat(),
        "online": True,
        "repeat": 1,
    }
    body.update(over)
    return body


async def _seed_two(client) -> None:
    """عطبان: **واحدٌ كثيرُ المرّات على جهازٍ واحد**، وآخرُ قليلُها على ثلاثة."""
    await client.post("/telemetry/errors", json=payload(repeat=500))

    for index in range(3):
        await client.post(
            "/telemetry/errors",
            json=payload(
                name="RangeError",
                message="حدٌّ تجاوزَ المدى",
                stack="at Wallet (main.js:9:1)",
                device_hash=f"{index}" * 32,
            ),
        )


# ------------------------------------------------------------- القائمة


async def test_default_sort_is_by_affected_users(client, admin_headers) -> None:
    """**القرارُ الذي بُنيت الشاشةُ عليه**: من أصابهم أكثرُ يتصدّر.

    والأولُ ٥٠٠ مرّةً على جهازٍ واحد، والثاني ٣ مرّاتٍ على ثلاثة — **والترتيبُ
    بالمرّات يقلبهما**، وهو ما يجعل الشاشةَ تكذب على من يقرؤها.
    """
    await _seed_two(client)

    rows = (await client.get("/admin/errors", headers=admin_headers)).json()
    assert [row["name"] for row in rows] == ["RangeError", "TypeError"]
    assert rows[0]["user_count"] == 3
    assert rows[1]["event_count"] == 500

    # **والترتيبُ بالمرّات يقلبه** — فالخيارُ موجودٌ ومقيسٌ أنه ليس الافتراض
    by_events = (
        await client.get("/admin/errors?sort=events", headers=admin_headers)
    ).json()
    assert [row["name"] for row in by_events] == ["TypeError", "RangeError"]


async def test_filters(client, admin_headers) -> None:
    await _seed_two(client)
    await client.post("/telemetry/errors", json=payload(app="driver", name="EvalError"))

    only_driver = (
        await client.get("/admin/errors?app=driver", headers=admin_headers)
    ).json()
    assert [row["name"] for row in only_driver] == ["EvalError"]

    by_release = (
        await client.get("/admin/errors?release=1.4.0", headers=admin_headers)
    ).json()
    assert len(by_release) == 3

    none_release = (
        await client.get("/admin/errors?release=9.9.9", headers=admin_headers)
    ).json()
    assert none_release == []

    searched = (
        await client.get("/admin/errors?q=RangeError", headers=admin_headers)
    ).json()
    assert [row["name"] for row in searched] == ["RangeError"]


async def test_support_is_denied(client, support_headers) -> None:
    """**`support` لا يملك `errors.read`** — والمصفوفةُ تحكم بالاسم."""
    assert (await client.get("/admin/errors", headers=support_headers)).status_code == 403


# ------------------------------------------------------------- التفصيل


async def test_detail_carries_the_latest_event(client, admin_headers) -> None:
    await client.post("/telemetry/errors", json=payload())
    row = (await client.get("/admin/errors", headers=admin_headers)).json()[0]

    detail = (
        await client.get(f"/admin/errors/{row['id']}", headers=admin_headers)
    ).json()
    assert detail["latest"]["name"] == "TypeError"
    assert detail["latest"]["route"] == "/rides/:rideId"
    # **مُعرِّفُ الجهاز مُعمّى** — اثنتا عشرةَ خانةً لا الاثنتان والثلاثون المُرسَلة
    assert len(detail["latest"]["device_hash"]) == 12


async def test_events_can_show_only_what_people_wrote(client, admin_headers) -> None:
    await client.post("/telemetry/errors", json=payload())
    await client.post(
        "/telemetry/errors",
        json=payload(kind="user_report", note="الشاشة بيضاء بعد الدفع"),
    )
    row = (await client.get("/admin/errors", headers=admin_headers)).json()[0]

    everything = (
        await client.get(f"/admin/errors/{row['id']}/events", headers=admin_headers)
    ).json()
    reported = (
        await client.get(
            f"/admin/errors/{row['id']}/events?reported_only=true",
            headers=admin_headers,
        )
    ).json()

    assert len(everything) >= len(reported) >= 1
    assert all(item["user_reported"] for item in reported)
    assert reported[0]["note"] == "الشاشة بيضاء بعد الدفع"


# --------------------------------------------------------------- الحسم


async def test_resolve_ignore_and_reopen(client, admin_headers, session_factory) -> None:
    """**والبابُ في اتجاهه الثاني**: حسمٌ بالخطأ يُعاد فتحُه."""
    await client.post("/telemetry/errors", json=payload())
    row = (await client.get("/admin/errors", headers=admin_headers)).json()[0]
    group_id = row["id"]

    resolved = await client.post(
        f"/admin/errors/{group_id}/resolve", headers=admin_headers
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    ignored = await client.post(
        f"/admin/errors/{group_id}/ignore", headers=admin_headers
    )
    assert ignored.json()["status"] == "ignored"

    reopened = await client.post(
        f"/admin/errors/{group_id}/reopen", headers=admin_headers
    )
    assert reopened.json()["status"] == "open"

    # **ولا حسمَ بلا قيدِ تدقيق** — ثلاثةُ إقراراتٍ ثلاثةُ قيود
    async with session_factory() as session:
        rows = await session.execute(
            select(AdminAuditLog).where(AdminAuditLog.entity_type == "error_group")
        )
        entries = list(rows.scalars())
    assert len(entries) == 3
    assert {entry.details["to"] for entry in entries} == {
        "resolved",
        "ignored",
        "open",
    }


# ------------------------------------------------------------- الاحتفاظ


async def test_sweep_keeps_the_group_and_what_people_wrote(
    client, session_factory
) -> None:
    """**الأحداثُ تُكنَس والمجموعةُ تبقى** — والعدّادُ خبرٌ عن الماضي لا يبطل."""
    await client.post("/telemetry/errors", json=payload(repeat=7))
    await client.post(
        "/telemetry/errors", json=payload(kind="user_report", note="جملةُ إنسان")
    )

    old = datetime.now(UTC) - timedelta(days=40)
    async with session_factory() as session:
        await session.execute(update(ErrorEvent).values(received_at=old))
        await session.commit()

        swept_events, swept_groups = await error_reports.sweep_retention(session)

    assert swept_events == 1, "كُنس غيرُ التلقائيّ أو لم يُكنس شيء"
    assert swept_groups == 0, "حُذفت مجموعةٌ ما زال فيها حدث"

    async with session_factory() as session:
        remaining = list((await session.execute(select(ErrorEvent))).scalars())
        groups = list((await session.execute(select(ErrorGroup))).scalars())

    # **ما كتبه إنسانٌ يبقى أطول** — تسعون يوماً لا ثلاثون
    assert len(remaining) == 1 and remaining[0].user_reported is True
    assert len(groups) >= 1
    assert sum(group.event_count for group in groups) == 8
