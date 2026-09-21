"""أرقامُ شاشة الأعطال والارتداد — **والدعوى الأهمُّ أن المكتومة لا تُفتح**.

`test_ignored_is_not_reopened` هو الاختبارُ الذي يفرّق الحسمَ من الكتم: الحسمُ
**دعوى إصلاحٍ** تكذّبها عودةُ العطب، والكتمُ **قرارُ ألّا تُرى** لا تنقضه.
وخلطُهما يجعل كلَّ مكتومٍ يعود إلى الوجه كلَّ ساعة.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.models.audit import AdminAuditLog
from app.models.error_report import ErrorEvent, ErrorGroup

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


async def _first(client, admin_headers) -> dict:
    """**بلا مرشّحِ حال** — وغيابُه يعني «كلَّها»، و`status=all` ليست قيمةً في التعداد."""
    rows = (await client.get("/admin/errors", headers=admin_headers)).json()
    assert isinstance(rows, list) and rows, f"لا صفوف: {rows}"
    return rows[0]


# ------------------------------------------------------------- الارتداد


async def test_resolved_group_regresses_when_it_happens_again(
    client, admin_headers
) -> None:
    """**محسومةٌ عادت تقع تُفتح من نفسها وتُوسَم** — ولا تنتظر أحداً."""
    await client.post("/telemetry/errors", json=payload())
    row = await _first(client, admin_headers)

    resolved = await client.post(
        f"/admin/errors/{row['id']}/resolve", headers=admin_headers
    )
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["regressed_at"] is None

    # العطبُ نفسُه يقع ثانيةً — البصمةُ واحدةٌ فالمجموعةُ واحدة
    await client.post("/telemetry/errors", json=payload())

    after = await _first(client, admin_headers)
    assert after["id"] == row["id"], "انقسمت المجموعةُ — البصمةُ لم تعد واحدة"
    assert after["status"] == "open", "عادت تقع ولم تُفتح"
    assert after["regressed_at"] is not None, "فُتحت ولم تُوسَم ارتداداً"


async def test_ignored_is_not_reopened(client, admin_headers) -> None:
    """**الكتمُ قرارٌ قائم** — ولا ينقضه وقوعٌ جديد.

    وهو الفرقُ عن الحسم: **الحسمُ دعوى أنه أُصلح فتكذّبها العودة**، والكتمُ
    «أعرفه ولا أريد أن أراه» — **وحدثٌ جديدٌ ليس خبراً جديداً**.
    """
    await client.post("/telemetry/errors", json=payload(name="RangeError"))
    row = await _first(client, admin_headers)
    await client.post(f"/admin/errors/{row['id']}/ignore", headers=admin_headers)

    await client.post("/telemetry/errors", json=payload(name="RangeError"))

    after = await _first(client, admin_headers)
    assert after["status"] == "ignored", "فُتحت المكتومةُ بوقوعٍ جديد"
    assert after["regressed_at"] is None


async def test_resolving_again_clears_the_regression_mark(
    client, admin_headers
) -> None:
    """**الحسمُ الجديدُ دعوى جديدة** — فتُقاس من الآن، ويُمحى الوسمُ القديم."""
    await client.post("/telemetry/errors", json=payload(name="EvalError"))
    row = await _first(client, admin_headers)
    await client.post(f"/admin/errors/{row['id']}/resolve", headers=admin_headers)
    await client.post("/telemetry/errors", json=payload(name="EvalError"))
    assert (await _first(client, admin_headers))["regressed_at"] is not None

    again = await client.post(
        f"/admin/errors/{row['id']}/resolve", headers=admin_headers
    )
    assert again.json()["regressed_at"] is None


# --------------------------------------------------------------- اللمحة


async def test_summary_counts_devices_not_events(
    client, admin_headers, session_factory
) -> None:
    """**«أجهزةٌ متأثرة» تعدّ الأجهزةَ لا الأحداث** — والفرقُ هو الخبر."""
    # جهازٌ واحدٌ يُطلق أربعين مرّة
    await client.post("/telemetry/errors", json=payload(repeat=40))
    # وثلاثةُ أجهزةٍ تُطلق مرّةً لكلٍّ
    for index in range(3):
        await client.post(
            "/telemetry/errors",
            json=payload(name="RangeError", device_hash=f"{index}" * 32),
        )

    body = (await client.get("/admin/errors/summary", headers=admin_headers)).json()
    assert body["devices_24h"] == 4, "عُدَّت الأحداثُ لا الأجهزة"
    assert body["open"] == 2
    assert body["new_24h"] == 2
    assert body["regressed_24h"] == 0


async def test_summary_reported_waiting(client, admin_headers) -> None:
    await client.post(
        "/telemetry/errors",
        json=payload(kind="user_report", note="الشاشة بيضاء بعد الدفع"),
    )
    body = (await client.get("/admin/errors/summary", headers=admin_headers)).json()
    assert body["reported_open"] == 1
    assert body["oldest_reported_at"] is not None


async def test_support_is_denied_the_summary(client, support_headers) -> None:
    """**`errors.read` تحرس الأرقامَ كما تحرس الصفوف**."""
    assert (
        await client.get("/admin/errors/summary", headers=support_headers)
    ).status_code == 403


# -------------------------------------------------------------- المنحنى


async def test_trend_has_a_bucket_per_hour_with_no_holes(
    client, admin_headers, session_factory
) -> None:
    """**ساعةٌ صامتةٌ صفرٌ لا فجوة** — ورسمٌ يقفز فوقها يكذب على قارئه."""
    await client.post("/telemetry/errors", json=payload(repeat=5))
    row = await _first(client, admin_headers)

    # حدثٌ ثانٍ يُزاح إلى ثلاث ساعاتٍ خلت
    await client.post("/telemetry/errors", json=payload(repeat=2))
    async with session_factory() as session:
        await session.execute(
            update(ErrorEvent)
            .where(ErrorEvent.repeat == 2)
            .values(received_at=datetime.now(UTC) - timedelta(hours=3))
        )
        await session.commit()

    body = (
        await client.get(
            f"/admin/errors/trend?ids={row['id']}&hours=6", headers=admin_headers
        )
    ).json()

    assert len(body) == 1
    series = body[0]
    assert series["hours"] == 6
    assert len(series["buckets"]) == 6, "عددُ الدِّلاء يخالف الساعاتِ المطلوبة"
    # **المجموعُ بالتكرار لا بعدد الصفوف**
    assert sum(series["buckets"]) == 7, "جُمعت الصفوفُ بدل التكرار"
    assert series["buckets"][-1] == 5, "آخرُ ساعةٍ ليست الأحدث"


async def test_trend_ignores_a_broken_id_and_still_answers(
    client, admin_headers
) -> None:
    """**مُعرِّفٌ فاسدٌ يُسقَط ولا يُسقط النداء** — الرسمُ زينةٌ لا شرط."""
    await client.post("/telemetry/errors", json=payload())
    row = await _first(client, admin_headers)
    response = await client.get(
        f"/admin/errors/trend?ids=not-a-uuid,{row['id']},", headers=admin_headers
    )
    assert response.status_code == 200
    assert [item["group_id"] for item in response.json()] == [row["id"]]


# ------------------------------------------------------------- الجماعيّ


async def test_bulk_resolve_writes_one_audit_row_per_group(
    client, admin_headers, session_factory
) -> None:
    """**قيدٌ لكلِّ مجموعةٍ لا قيدٌ للدفعة** — والسجلُّ يُقرأ بالكيان."""
    for name in ("TypeError", "RangeError", "EvalError"):
        await client.post("/telemetry/errors", json=payload(name=name))
    rows = (await client.get("/admin/errors", headers=admin_headers)).json()
    ids = [row["id"] for row in rows]
    assert len(ids) == 3

    response = await client.post(
        "/admin/errors/bulk/resolve", json={"ids": ids}, headers=admin_headers
    )
    assert response.status_code == 200
    assert {item["status"] for item in response.json()} == {"resolved"}

    async with session_factory() as session:
        entries = list(
            (
                await session.execute(
                    select(AdminAuditLog).where(
                        AdminAuditLog.entity_type == "error_group"
                    )
                )
            ).scalars()
        )
    assert len(entries) == 3, "الدفعةُ كتبت قيداً واحداً بدل ثلاثة"
    assert {entry.entity_id for entry in entries} == {__import__("uuid").UUID(i) for i in ids}


async def test_bulk_refuses_an_empty_list(client, admin_headers) -> None:
    """**ولا دفعةَ فارغة** — إقرارٌ بلا موضوعٍ يُقرأ عملاً وقع."""
    response = await client.post(
        "/admin/errors/bulk/ignore", json={"ids": []}, headers=admin_headers
    )
    assert response.status_code == 422


async def test_support_is_denied_bulk(client, support_headers) -> None:
    response = await client.post(
        "/admin/errors/bulk/resolve",
        json={"ids": ["3f2c1a4e-9b7d-4c2a-8e11-77aa0b1c2d3e"]},
        headers=support_headers,
    )
    assert response.status_code == 403


# -------------------------------------------------------------- المرشّح


async def test_hours_filter_is_on_last_seen(
    client, admin_headers, session_factory
) -> None:
    """**النافذةُ على «آخر ظهور»** — والسؤالُ «أما زال يقع؟» لا «متى بدأ؟»."""
    await client.post("/telemetry/errors", json=payload(name="OldError"))
    async with session_factory() as session:
        await session.execute(
            update(ErrorGroup)
            .where(ErrorGroup.name == "OldError")
            .values(last_seen_at=datetime.now(UTC) - timedelta(days=5))
        )
        await session.commit()
    await client.post("/telemetry/errors", json=payload(name="FreshError"))

    recent = (
        await client.get("/admin/errors?hours=24", headers=admin_headers)
    ).json()
    assert [row["name"] for row in recent] == ["FreshError"]

    wide = (await client.get("/admin/errors?hours=240", headers=admin_headers)).json()
    assert {row["name"] for row in wide} == {"FreshError", "OldError"}
