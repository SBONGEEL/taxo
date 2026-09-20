"""تقاريرُ الأعطال — **والاختبارُ الأولُ هو الذي يُقرأ قبل غيره** (2026-09-20).

`test_nothing_sensitive_survives` يحمل **واحداً من كلِّ صنفٍ** اتُّفق على
حجبه، ويؤكّد أن **لا شيءَ منه يبلغ الجدول**. وهو الاختبارُ الذي يُحذف الحارسُ
تحته فيسقط — وقد جُرِّب كذلك، لا كُتب ثمّ صُدِّق.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models.error_report import ErrorEvent, ErrorGroup, ErrorGroupDevice

pytestmark = pytest.mark.asyncio


# ------------------------------------------------------------------ أدوات

#: **قيمٌ من العالم الحقيقيِّ بأصنافها** — لا نصٌّ مخترعٌ يمرّ لأنه مخترع
SECRET_PHONE = "+962791234567"
SECRET_PHONE_LOCAL = "0791234567"
SECRET_UUID = "3f2c1a4e-9b7d-4c2a-8e11-77aa0b1c2d3e"
SECRET_MONEY = "12.500"
SECRET_EMAIL = "rider@example.com"
SECRET_COORDS = "31.95391, 35.91062"
SECRET_TOKEN = "eyJhbGciOiJIUzI1NiJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
SECRET_PLATE = "22-88221"

ALL_SECRETS = (
    SECRET_PHONE,
    SECRET_PHONE_LOCAL,
    SECRET_UUID,
    SECRET_MONEY,
    SECRET_EMAIL,
    SECRET_EMAIL.split("@")[0],
    SECRET_COORDS,
)


def payload(**over) -> dict:
    """حمولةٌ صالحةٌ — ويُبدَّل منها ما يخصّ كلَّ اختبار."""
    body = {
        "app": "rider",
        "kind": "error",
        "platform": "android",
        "release": "1.4.0",
        "channel": "public",
        "os_version": "Android 13",
        "device_hash": "a" * 32,
        "route": "/rides/:rideId/pay",
        "name": "TypeError",
        "message": "Cannot read properties of undefined",
        "stack": "at Payment (main.js:142:18)\nat renderWithHooks (vendor.js:99:7)",
        "occurred_at": datetime.now(UTC).isoformat(),
        "online": True,
        "repeat": 1,
    }
    body.update(over)
    return body


async def _groups(session_factory) -> list[ErrorGroup]:
    async with session_factory() as session:
        rows = await session.execute(select(ErrorGroup))
        return list(rows.scalars())


async def _events(session_factory) -> list[ErrorEvent]:
    async with session_factory() as session:
        rows = await session.execute(select(ErrorEvent))
        return list(rows.scalars())


# ------------------------------------------- الاختبارُ الذي يُقرأ قبل غيره


async def test_nothing_sensitive_survives(client, session_factory) -> None:
    """**واحدٌ من كلِّ صنف، ولا واحدٌ منها يبلغ الجدول.**

    والفحصُ على **كلِّ نصٍّ خُزِّن**، لا على حقلٍ بعينه: عطبُ التسريب يقع حين
    تذهب القيمةُ إلى حقلٍ لم يخطر لكاتب الفحص — فيُقرأ الصفُّ كلُّه.
    """
    response = await client.post(
        "/telemetry/errors",
        json=payload(
            kind="user_report",
            message=f"فشل الدفع للراكب {SECRET_PHONE} برصيد {SECRET_MONEY}",
            stack=(
                f"at pay (main.js:10:2) ride={SECRET_UUID}\n"
                f"at fetch ({SECRET_EMAIL})\n"
                f"at map ({SECRET_COORDS})"
            ),
            component_stack=f"in Payment (at {SECRET_PHONE_LOCAL})",
            route=f"/rides/{SECRET_UUID}/pay",
            note=f"رقمي {SECRET_PHONE_LOCAL} ولوحتي {SECRET_PLATE} ولم يصلني شيء",
            breadcrumbs=[
                {
                    "at": 1,
                    "kind": "nav",
                    "route": f"/rides/{SECRET_UUID}",
                    "authorization": f"Bearer {SECRET_TOKEN}",
                    "body": {"phone": SECRET_PHONE, "amount": SECRET_MONEY},
                    "lat": 31.95391,
                    "lng": 35.91062,
                }
            ],
            # **حقولٌ لم تُسمَّ في القائمة البيضاء** — تُسقَط قبل أن يراها كودُنا
            phone=SECRET_PHONE,
            user_id=SECRET_UUID,
            lat=31.95391,
            lng=35.91062,
            authorization=f"Bearer {SECRET_TOKEN}",
            wallet_balance=SECRET_MONEY,
        ),
    )
    assert response.status_code == 202

    events = await _events(session_factory)
    assert len(events) == 1
    event = events[0]

    haystack = " | ".join(
        str(value)
        for value in (
            event.message,
            event.stack,
            event.component_stack,
            event.route,
            event.note,
            event.name,
            event.breadcrumbs,
            event.device_hash,
            event.os_version,
            event.release,
            event.channel,
        )
    )

    for secret in ALL_SECRETS:
        assert secret not in haystack, f"تسرّب إلى الجدول: {secret!r}"
    assert SECRET_TOKEN not in haystack, "توكنٌ في الجدول"
    assert "Bearer" not in haystack, "رأسُ تفويضٍ في الجدول"

    # **ولا الحقولُ الزائدةُ نفسُها** — القائمةُ البيضاء أسقطتها
    assert "a" * 32 != event.device_hash, "مُعرِّفُ الجهاز خُزِّن كما وصل"
    assert len(event.device_hash) == 12

    # **وما يجب أن يبقى باقٍ** — وإلا كان الحجبُ تعقيماً لا تنظيفاً
    assert "main.js:10:2" in (event.stack or ""), "رقمُ السطر مُحي — وهو المُشخِّص"
    assert "TypeError" == event.name
    assert event.route == "/rides/:id/pay"
    assert event.note and "ولم يصلني شيء" in event.note


async def test_extra_fields_never_reach_the_model(client, session_factory) -> None:
    """القائمةُ البيضاء بنيويّة: ما لم يُسمَّ لا يصل الخدمةَ أصلاً."""
    response = await client.post(
        "/telemetry/errors",
        json=payload(national_id="9901234567", plate=SECRET_PLATE, ip="41.2.3.4"),
    )
    assert response.status_code == 202
    events = await _events(session_factory)
    stored = " ".join(str(v) for v in events[0].__dict__.values())
    assert "9901234567" not in stored
    assert SECRET_PLATE not in stored
    assert "41.2.3.4" not in stored


# ------------------------------------------------------------- التجميع


async def test_same_defect_groups_and_counts(client, session_factory) -> None:
    """أربعون مرّةً لجهازين = **مجموعةٌ واحدة، ٤٠ حدثاً، متأثّران**."""
    for index in range(3):
        assert (
            await client.post("/telemetry/errors", json=payload(repeat=10))
        ).status_code == 202
        assert index >= 0
    assert (
        await client.post(
            "/telemetry/errors", json=payload(repeat=10, device_hash="b" * 32)
        )
    ).status_code == 202

    groups = await _groups(session_factory)
    assert len(groups) == 1, "العطبُ الواحدُ انقسم"
    assert groups[0].event_count == 40
    assert groups[0].user_count == 2, "الأجهزةُ عُدّت خطأً"


async def test_same_device_counts_once(client, session_factory) -> None:
    for _ in range(5):
        await client.post("/telemetry/errors", json=payload())
    groups = await _groups(session_factory)
    assert groups[0].event_count == 5
    assert groups[0].user_count == 1, "جهازٌ واحدٌ عُدّ أكثرَ من مرّة"


async def test_release_does_not_split_the_group(client, session_factory) -> None:
    """**أدقُّ قرارٍ في البصمة**: العطبُ يعيش عبر النسخ ولا ينقسم بها."""
    await client.post("/telemetry/errors", json=payload(release="1.4.0"))
    await client.post("/telemetry/errors", json=payload(release="1.5.0"))

    groups = await _groups(session_factory)
    assert len(groups) == 1, "الإصدارُ قسم المجموعة — وهو ما بُنيت البصمةُ لتمنعه"
    assert groups[0].first_seen_release == "1.4.0"
    assert groups[0].last_seen_release == "1.5.0"


async def test_shifting_line_numbers_do_not_split(client, session_factory) -> None:
    """سطرٌ يُضاف فوق الدالّة يزحف بما تحته — **والعطبُ لم يتغيّر**."""
    await client.post("/telemetry/errors", json=payload())
    await client.post(
        "/telemetry/errors",
        json=payload(
            stack="at Payment (main.js:171:18)\nat renderWithHooks (vendor.js:120:7)"
        ),
    )
    assert len(await _groups(session_factory)) == 1


async def test_different_defects_stay_apart(client, session_factory) -> None:
    await client.post("/telemetry/errors", json=payload())
    await client.post(
        "/telemetry/errors",
        json=payload(name="RangeError", message="حدٌّ تجاوزَ المدى"),
    )
    assert len(await _groups(session_factory)) == 2


async def test_user_report_is_flagged(client, session_factory) -> None:
    await client.post(
        "/telemetry/errors",
        json=payload(kind="user_report", note="الشاشة بيضاء بعد الدفع"),
    )
    events = await _events(session_factory)
    assert events[0].user_reported is True
    assert events[0].note == "الشاشة بيضاء بعد الدفع"


# ------------------------------------------------------------- السدود


async def test_device_bucket_stops_a_loop(client) -> None:
    """**٤٢٩ تعني «توقّف»** — وحلقةُ رسمٍ لا تملأ الجدول."""
    codes = Counter()
    for _ in range(25):
        codes[
            (await client.post("/telemetry/errors", json=payload())).status_code
        ] += 1
    assert codes[202] == 20, codes
    assert codes[429] == 5, codes


# --------------------------------------------------------- تسابقُ الإنشاء


async def test_concurrent_first_events_make_one_group(client, session_factory) -> None:
    """**الحالةُ المتسابقةُ الحقيقيّة**: أوّلُ حدثين لعطبٍ جديدٍ معاً.

    ولا يُقاس الوقتُ بل الثابت: **مجموعةٌ واحدةٌ** و`event_count` يساوي عددَ
    ما قُبل — فلا صفٌّ ثانٍ بالبصمة نفسِها، ولا عدٌّ ضاع في التسابق.

    **ويُلفّ بمهلة**: التعارضُ يُعلَّق ولا يرفع، فلا يُسقطه إلا انتهاءُ مهلة.
    """
    count = 8
    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post("/telemetry/errors", json=payload(device_hash="c" * 32))
                for _ in range(count)
            )
        ),
        timeout=30,
    )
    accepted = sum(1 for r in responses if r.status_code == 202)
    assert accepted == count, Counter(r.status_code for r in responses)

    groups = await _groups(session_factory)
    assert len(groups) == 1, "تسابقٌ أنشأ مجموعتين بالبصمة نفسِها"
    assert groups[0].event_count == count, "عدٌّ ضاع في التسابق"
    assert groups[0].user_count == 1, "جهازٌ واحدٌ عُدّ أكثرَ من مرّة تحت التسابق"

    async with session_factory() as session:
        devices = await session.execute(
            select(func.count()).select_from(ErrorGroupDevice)
        )
        assert devices.scalar_one() == 1
