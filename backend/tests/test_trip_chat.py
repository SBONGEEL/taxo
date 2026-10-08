"""محادثةُ الرحلة (SPEC §٦٦-ب/١٤، `design/APPROVALS-DATA.md` §١) — **اختباراتُ المالك بنصّها، ومعها ما يجعلها صادقة**.

الأربعةُ المشروطة: **لا شيءَ يُرسل بعد انتهاء الرحلة** (مكتملةً وملغاة) · **لا رقمَ هاتفٍ يمرّ** (الكاشفُ بجدولٍ واسعٍ، والبابُ نفسُه) ·
**كلُّ قراءةٍ إداريةٍ مدقَّقة، ومن لا يملك الصلاحيةَ يُردّ ولو كان مشرفاً كاملاً** · **القديمُ يُحذف في موعده** (والمبلَّغُ عنه
حتى يُعالَج). **ومعها**: غيرُ الطرفين ٤٠٤، والمفتاحُ المطفأُ برمزه، وشرطُ نشر سطر الخصوصية قبل الإشعال، وإصلاحُ افتراض الصلاحيات.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.redis_client import get_redis_client
from app.models.audit import AdminAuditLog
from app.models.enums import AdminPermission, AuditAction, CountryCode, PolicyApp, PolicyDocType, UserRole
from app.models.trip_chat import RideMessage, RideMessageReport
from app.models.user import User
from app.services import account_deletion, chat_filter, trip_chat
from app.services import permissions as permissions_service
from app.services import policies as policies_service
from app.ws import events
from tests.conftest import _staff_headers
from tests.helpers import (
    OTHER_RIDER,
    accepted_ride,
    approved_driver,
    bring_online,
    enable_features,
    enable_push_provider,
    pushes_to,
    register_device,
    rider_session,
    started_ride,
)

pytestmark = pytest.mark.usefixtures("jordan_settings")

CHAT_FLAGS = ("trip_chat_enabled", "ride_calls_enabled")


# ═════════════════════════ مساعدات


async def _chat_ride(client: AsyncClient, session_factory, *, started: bool = False, flags=CHAT_FLAGS) -> dict:
    """راكبٌ وكبتنٌ في رحلةٍ قُبلت (أو بدأت) — **بالمسار الحقيقيّ**، والمفتاحان مشتعلان في الأردن."""
    if flags:
        await enable_features(session_factory, *flags)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await (started_ride if started else accepted_ride)(client, rider["headers"], driver)
    return {"rider": rider, "driver": driver, "ride": ride, "rider_id": rider["user"]["id"]}


async def _send(client: AsyncClient, headers: dict, ride_id: str, body: str):
    return await client.post(f"/rides/{ride_id}/chat", json={"body": body}, headers=headers)


async def _messages(session_factory, ride_id: str) -> list[RideMessage]:
    async with session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(RideMessage)
                    .where(RideMessage.ride_id == uuid.UUID(ride_id))
                    .order_by(RideMessage.created_at)
                )
            ).all()
        )


async def _audit_rows(session_factory, entity_type: str) -> list[AdminAuditLog]:
    async with session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(AdminAuditLog)
                    .where(AdminAuditLog.entity_type == entity_type)
                    .order_by(AdminAuditLog.created_at)
                )
            ).all()
        )


async def _staff(client: AsyncClient, role: str, phone: str, name: str) -> dict:
    headers = await _staff_headers(role, phone, name)
    me = (await client.get("/auth/me", headers=headers)).json()
    return {"headers": headers, "id": me["id"]}


async def _grant(client: AsyncClient, granter: dict, target_id: str, permission: str) -> dict:
    """**كما تمنح مصفوفةُ اللوحة** (`Users.tsx::toggle`): المجموعةُ **الفعّالة** من `GET /admin/permissions` ومعها الجديدة."""
    rows = (await client.get("/admin/permissions", headers=granter)).json()
    row = next(item for item in rows if item["user_id"] == target_id)
    response = await client.put(
        f"/admin/permissions/{target_id}",
        json={"permissions": sorted(set(row["permissions"]) | {permission})},
        headers=granter,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _chat_reader(client: AsyncClient, admin_headers: dict) -> dict:
    """مشرفٌ ثانٍ مُنح «قراءة محادثات الرحلات» من المصفوفة — **لا يملكها أحدٌ افتراضاً**."""
    reader = await _staff(client, "admin", "+962790000031", "قارئ المحادثات")
    await _grant(client, admin_headers, reader["id"], "trip_chats.read")
    return reader


async def _drain(pubsub, seconds: float = 0.6) -> list[dict]:
    """كلُّ ما وصل القناةَ في نافذةٍ قصيرة — والبثُّ بعد الالتزام فلا يتأخّر أكثر."""
    found: list[dict] = []
    deadline = asyncio.get_running_loop().time() + seconds
    while asyncio.get_running_loop().time() < deadline:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if message is not None:
            found.append(json.loads(message["data"]))
    return found


# ═════════════════════════ ١) الكاشف — دالّةٌ محضة بجدولٍ واسع


PHONES = [
    "0791234567",
    "رقمي 0791234567 كلمني",
    "079 123 4567",
    "079-123-4567",
    "079.123.4567",
    "(079) 123-4567",
    "079 - 123 - 4567",
    "079/123/4567",
    "07_91_23_45",
    "+962 79 123 4567",
    "+962791234567",
    "00962791234567",
    "0 7 9 1 2 3 4",
    "٠٧٩١٢٣٤٥٦٧",
    "٠٧٩ ١٢٣ ٤٥٦٧",
    "۰۷۹۱۲۳۴۵۶۷",
    "０７９１２３４５６７",
    "079 123 4567",
    "079​1234567",
    "07‏9‎1234567",
    "079 ١٢٣ 4567",
    "صفر سبعة تسعة واحد اتنين تلاتة اربعة",
    "اتصل على صفر سبعة تسعة خمسة خمسة خمسة خمسة",
    "صِفْر سَبْعَة تِسْعَة وَاحِد اِتْنَيْن ثَلَاثَة أَرْبَعَة",
    "ســبعة تسعة واحد اثنين ثلاثة أربعة خمسة",
    "صفر سبعة وتسعين خمسة وخمسين اربعة",
    "079 واحد اتنين تلاتة اربعة",
    "تسعة ستة اتنين سبعة تسعة واحد تمانية",
    "zero seven nine one two three four",
    "oh seven nine one two three four five",
    "Zero Seven Nine 1 2 3 4",
    "double seven nine one two three four",
    # **ما مرّ من الكاشف الأوّل — بنصِّ المراجعة** (قِيس ٢٠٢٦-١٠-٠٨): فاصلٌ أطول، أو رمزٌ لم يُكتب في قائمة، أو ربطٌ غيرُ «و»
    "079 -- 123 -- 4567",
    "079  -  123  -  4567",
    "079 .. 123 .. 4567",
    "079\n\n\n\n123\n\n\n\n4567",
    "079·123·4567",
    "079•123•4567",
    "079 123، 4567",
    "0791,234,567",
    "079*123*4567",
    "079|123|4567",
    "079~123~4567",
    "079🙂1234🙂567",
    "079 ثم 123 ثم 4567",
    "079 ثمّ 123 ثمّ 4567",
    "079 then 123 then 4567",
    "زيرو سبعة تسعة واحد اتنين تلاتة اربعة",
]

LINKS = [
    "https://x.com",
    "http://evil.io/a",
    "www.example.com",
    "WWW.EXAMPLE.COM",
    "t.me/someone",
    "wa.me/someone",
    "تابعني على taxo-free.com",
    "bit.ly/abc",
    "راسلني me@gmail.com",
    "ｗｗｗ．ｅｘａｍｐｌｅ．ｃｏｍ",
]

#: **ما يمرّ عمداً** — وكلُّه نصٌّ يُكتب في رحلةٍ حقيقية
NEAR_MISSES = [
    "الأجرة 12.500 دينار",
    "أصل الساعة 10:45",
    "لوحة السيارة AMM-1010",
    "الرمز 123456",
    "رمز ١٢٣٤٥٦",
    "12 34 56",
    "أنا عند البوابة رقم 3",
    "بعد 5 دقائق",
    "الطابق 12 الشقة 4",
    "عندي ٣ شنط",
    "سبعة أيام وأنا أستعمل التطبيق",
    "السعر 12.500 والوقت 10:45",
    "3.5 كم تقريباً",
    "نلتقي 9 a.m. عند الدوار",
    "وصلت، أنا عند الباب",
    "one more minute",
    # **والفاصلُ الأوسعُ لا يجمع ما بينه كلمة** — ولا وقتاً بنقطتيه
    "الأجرة 12.500، والانتظار 1.000",
    "من 10:45 إلى 11:30",
    "الأجرة 12.500\nأنا عند الباب بعد 5 دقائق",
]


@pytest.mark.parametrize("plate", ["13-12345", "13 12345", "1312345", "١٣-١٢٣٤٥"])
def test_the_rides_own_plate_passes_only_when_named(plate: str) -> None:
    """**اللوحةُ الأردنيةُ سبعُ خانات** («13-12345») — تُردّ رقماً إلا حين يمرّرها الباب لوحةَ مركبة الرحلة نفسِها، بأيِّ كتابة."""
    text = f"لوحتي {plate}"
    assert chat_filter.check(text) is chat_filter.Violation.PHONE
    assert chat_filter.check(text, allowed=["13-12345"]) is None
    # **ولا تصير غطاءً**: لوحةٌ أخرى تُردّ، ورقمٌ يُدسّ حولها يلتئم ويُردّ، ورقمٌ يحويها في وسطه لا يُقتطع منه
    assert chat_filter.check("لوحتي 22-33445", allowed=["13-12345"]) is chat_filter.Violation.PHONE
    assert chat_filter.check(f"0791 {plate} 234567", allowed=["13-12345"]) is chat_filter.Violation.PHONE
    assert chat_filter.check("0791312345", allowed=["13-12345"]) is chat_filter.Violation.PHONE


@pytest.mark.parametrize("text", PHONES)
def test_no_phone_number_passes_in_any_form(text: str) -> None:
    assert chat_filter.check(text) is chat_filter.Violation.PHONE, (text, chat_filter.longest_number_run(text))


@pytest.mark.parametrize("text", LINKS)
def test_links_are_refused(text: str) -> None:
    assert chat_filter.check(text) is chat_filter.Violation.LINK, text


@pytest.mark.parametrize("text", NEAR_MISSES)
def test_near_misses_pass(text: str) -> None:
    assert chat_filter.check(text) is None, (text, chat_filter.longest_number_run(text))


# ═════════════════════════ ٢) الطرفان — إرسالٌ وقراءةٌ وبثٌّ وإشعارٌ بلا نصّ


async def test_both_parties_chat_and_the_push_never_carries_the_text(
    client: AsyncClient, session_factory
) -> None:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    await enable_push_provider(session_factory)
    await register_device(client, trip["rider"]["headers"], device_id="rider-phone", token="fcm-rider")

    redis = get_redis_client()
    pubsub = redis.pubsub()
    await pubsub.subscribe(events.user_channel(trip["rider_id"]), events.user_channel(trip["driver"]["user_id"]))

    sent = await _send(client, trip["driver"]["headers"], ride_id, "وصلتُ إلى نقطة الانطلاق، أنا عند ٣ نخلات")
    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert body["sender_role"] == "driver" and body["mine"] is True
    # **الخاناتُ لاتينيةٌ عند الكتابة** — قرارُ المالك على النصِّ الحرّ
    assert body["body"] == "وصلتُ إلى نقطة الانطلاق، أنا عند 3 نخلات"

    seen = [event for event in await _drain(pubsub) if event["type"] == "chat_message"]
    # **للطرفين** على قناتيهما — والحمولةُ معرّفُ الرحلة والجانبُ والنصّ، لا رقمَ ولا اسم
    assert len(seen) == 2
    for event in seen:
        assert event["ride_id"] == ride_id
        assert set(event["message"]) == {"id", "sender_role", "body", "created_at", "read_at"}
    await pubsub.aclose()

    pushes = await pushes_to("fcm-rider")
    assert len(pushes) == 1
    push = pushes[0]
    assert push["title"] == "رسالةٌ جديدة من الكبتن"
    assert "نخلات" not in push["title"] + push["body"] + json.dumps(push["data"], ensure_ascii=False)
    assert push["data"] == {"type": "chat_message", "ride_id": ride_id, "sender_role": "driver"}

    # **الراكبُ يقرأ** — رسالةُ الكبتن جديدةٌ مرّةً واحدة، وفتحُها يعلّمها مقروءة
    thread = await client.get(f"/rides/{ride_id}/chat", headers=trip["rider"]["headers"])
    assert thread.status_code == 200, thread.text
    data = thread.json()
    assert data["open"] is True and data["can_call"] is True
    assert data["unread"] == 1
    assert data["notice"] == trip_chat.IN_CHAT_NOTICE
    assert [(m["sender_role"], m["mine"]) for m in data["messages"]] == [("driver", False)]
    again = (await client.get(f"/rides/{ride_id}/chat", headers=trip["rider"]["headers"])).json()
    assert again["unread"] == 0 and again["messages"][0]["read_at"] is not None


# ═════════════════════════ ٣) لا شيءَ بعد انتهاء الرحلة — مكتملةً وملغاة


async def test_nothing_is_sent_after_the_ride_completes(client: AsyncClient, session_factory) -> None:
    trip = await _chat_ride(client, session_factory, started=True)
    ride_id = trip["ride"]["id"]
    assert (await _send(client, trip["rider"]["headers"], ride_id, "في الطريق؟")).status_code == 201

    done = await client.post(f"/rides/{ride_id}/complete", headers=trip["driver"]["headers"])
    assert done.status_code == 200, done.text

    for headers in (trip["rider"]["headers"], trip["driver"]["headers"]):
        refused = await _send(client, headers, ride_id, "نسيتُ حقيبتي")
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "chat_closed"
        assert refused.json()["message"] == "انتهت الرحلة، وأُغلقت المحادثة."

    # **وتبقى مقروءةً للطرفين** — مفقوداتٌ أو خلافٌ على دفعة
    thread = (await client.get(f"/rides/{ride_id}/chat", headers=trip["driver"]["headers"])).json()
    assert thread["open"] is False and thread["can_call"] is False
    assert len(thread["messages"]) == 1
    assert len(await _messages(session_factory, ride_id)) == 1


async def test_nothing_is_sent_after_the_ride_is_cancelled(client: AsyncClient, session_factory) -> None:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    cancelled = await client.post(
        f"/rides/{ride_id}/cancel", json={"reason": "عطلٌ في السيارة"}, headers=trip["driver"]["headers"]
    )
    assert cancelled.status_code == 200, cancelled.text

    refused = await _send(client, trip["rider"]["headers"], ride_id, "لماذا ألغيت؟")
    assert refused.status_code == 409 and refused.json()["code"] == "chat_closed"
    assert await _messages(session_factory, ride_id) == []


async def test_the_chat_is_closed_before_a_captain_accepts(client: AsyncClient, session_factory) -> None:
    """**تُفتح حين يقبل الكبتن** — رحلةٌ تبحث لا طرفَ ثانياً فيها."""
    await enable_features(session_factory, *CHAT_FLAGS)
    rider = await rider_session(client)
    ride = (
        await client.post(
            "/rides",
            json={"pickup": {"lat": 31.9539, "lng": 35.9106}, "dropoff": {"lat": 31.98, "lng": 35.89}, "vehicle_category": "economy"},
            headers=rider["headers"],
        )
    ).json()
    refused = await _send(client, rider["headers"], ride["id"], "أين أنت؟")
    assert refused.status_code == 409 and refused.json()["code"] == "chat_closed"


# ═════════════════════════ ٤) لا رقمَ يمرّ — من الباب نفسِه، وقبل أن يُحفظ


@pytest.mark.parametrize(
    "body,code",
    [
        ("كلمني 0791234567", "chat_phone_number"),
        ("رقمي ٠٧٩ ١٢٣ ٤٥٦٧", "chat_phone_number"),
        ("صفر سبعة تسعة واحد اتنين تلاتة اربعة", "chat_phone_number"),
        ("+962 79 123 4567", "chat_phone_number"),
        ("راسلني على wa.me/someone", "chat_link"),
        ("https://example.com", "chat_link"),
    ],
)
async def test_the_door_refuses_numbers_and_links_before_saving(
    client: AsyncClient, session_factory, body: str, code: str
) -> None:
    trip = await _chat_ride(client, session_factory)
    refused = await _send(client, trip["rider"]["headers"], trip["ride"]["id"], body)
    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == code
    if code == "chat_phone_number":
        assert refused.json()["message"] == "لا تُرسَل أرقامُ الهواتف في المحادثة."
    # **لا يُحفظ رقمٌ ليُحذف بعدها**
    assert await _messages(session_factory, trip["ride"]["id"]) == []


async def test_the_assigned_vehicles_plate_passes_and_no_other(client: AsyncClient, session_factory) -> None:
    """**لوحةٌ أردنيةٌ حقيقية** «13-12345» سبعُ خانات — كانت تُردّ رقمَ هاتف (قِيس ٢٠٢٦-١٠-٠٨). **ولوحةُ مركبة الرحلة وحدَها تمرّ**."""
    await enable_features(session_factory, "trip_chat_enabled")
    driver = await approved_driver(client, session_factory, plate_number="13-12345")
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride_id = (await accepted_ride(client, rider["headers"], driver))["id"]

    for headers, body in (
        (driver["headers"], "لوحتي 13-12345"),
        (rider["headers"], "سيارتك ١٣-١٢٣٤٥؟ أنا عند الباب"),
    ):
        sent = await _send(client, headers, ride_id, body)
        assert sent.status_code == 201, sent.text
    for body in ("لوحتي 22-33445", "0791 13-12345 234567"):
        refused = await _send(client, rider["headers"], ride_id, body)
        assert refused.status_code == 422 and refused.json()["code"] == "chat_phone_number", refused.text
    assert len(await _messages(session_factory, ride_id)) == 2


async def test_an_empty_or_overlong_message_is_refused(client: AsyncClient, session_factory) -> None:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    blank = await _send(client, trip["rider"]["headers"], ride_id, "   ")
    assert blank.status_code == 422 and blank.json()["code"] == "chat_empty"
    long = await _send(client, trip["rider"]["headers"], ride_id, "ا" * 301)
    assert long.status_code == 422
    assert await _messages(session_factory, ride_id) == []


async def test_a_flood_is_rate_limited(client: AsyncClient, session_factory) -> None:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    codes = [
        (await _send(client, trip["rider"]["headers"], ride_id, f"رسالة رقم {index}")).status_code
        for index in range(trip_chat.SEND_LIMIT + 1)
    ]
    assert codes[:-1] == [201] * trip_chat.SEND_LIMIT
    assert codes[-1] == 429


# ═════════════════════════ ٥) غيرُ الطرفين ٤٠٤ — والمفتاحُ المطفأُ برمزه


async def test_a_third_user_gets_404_not_403(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    sent = (await _send(client, trip["driver"]["headers"], ride_id, "أنا قريب")).json()
    stranger = await rider_session(client, OTHER_RIDER)

    for headers in (stranger["headers"], admin_headers):
        assert (await client.get(f"/rides/{ride_id}/chat", headers=headers)).status_code == 404
        assert (await _send(client, headers, ride_id, "مرحبا")).status_code == 404
        reported = await client.post(
            f"/rides/{ride_id}/chat/{sent['id']}/report", json={"reason": "abuse"}, headers=headers
        )
        assert reported.status_code == 404
    assert len(await _messages(session_factory, ride_id)) == 1


async def test_with_the_flag_off_nothing_is_sent(client: AsyncClient, session_factory) -> None:
    trip = await _chat_ride(client, session_factory, flags=())
    refused = await _send(client, trip["rider"]["headers"], trip["ride"]["id"], "مرحبا")
    assert refused.status_code == 403 and refused.json()["code"] == "trip_chat_disabled"
    thread = (await client.get(f"/rides/{trip['ride']['id']}/chat", headers=trip["rider"]["headers"])).json()
    assert thread["open"] is False and thread["can_call"] is False


# ═════════════════════════ ٦) البلاغ — على رسالة الطرف الآخر، ومرّةً لكلِّ مُبلِّغ


async def test_a_report_is_on_the_other_partys_message_and_idempotent(
    client: AsyncClient, session_factory
) -> None:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    mine = (await _send(client, trip["rider"]["headers"], ride_id, "أنا عند الباب")).json()
    theirs = (await _send(client, trip["driver"]["headers"], ride_id, "كلامٌ مسيء")).json()

    own = await client.post(
        f"/rides/{ride_id}/chat/{mine['id']}/report", json={"reason": "abuse"}, headers=trip["rider"]["headers"]
    )
    assert own.status_code == 422 and own.json()["code"] == "chat_report_own_message"

    first = await client.post(
        f"/rides/{ride_id}/chat/{theirs['id']}/report",
        json={"reason": "harassment", "note": "أزعجني"},
        headers=trip["rider"]["headers"],
    )
    second = await client.post(
        f"/rides/{ride_id}/chat/{theirs['id']}/report", json={"reason": "abuse"}, headers=trip["rider"]["headers"]
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "open" and first.json()["reason"] == "harassment"


# ═════════════════════════ ٧) اللوحة — صلاحيةٌ مستقلّة، وكلُّ قراءةٍ مدقَّقة


async def test_default_admin_lacks_both_and_granting_one_keeps_the_rest(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**الإصلاحُ الخطر**: `admin` على افتراضه لا يملك الحسّاستين — **ومنحُ إحداهما من المصفوفة لا يُسقط ما سواها**."""
    assert permissions_service.DEFAULTS[UserRole.ADMIN] == permissions_service.ALL - permissions_service.SENSITIVE
    # **وصارت الحسّاسةُ ثلاثاً بالملخّصات المالية** (SPEC §٦٥-د/٧) — والاثنتان هنا منها، والعدُّ يُقرأ من المجموعة لا يُكتب بيد
    assert {AdminPermission.TRIP_CHATS_READ, AdminPermission.CALL_RECORDINGS_LISTEN} <= permissions_service.SENSITIVE

    target = await _staff(client, "admin", "+962790000032", "مشرفٌ على افتراضه")
    rows = (await client.get("/admin/permissions", headers=admin_headers)).json()
    row = next(item for item in rows if item["user_id"] == target["id"])
    assert row["explicit"] is False
    assert "trip_chats.read" not in row["permissions"] and "call_recordings.listen" not in row["permissions"]
    before = set(row["permissions"])
    assert len(before) == len(AdminPermission) - len(permissions_service.SENSITIVE)

    # **ولا يقرأ محادثةً** قبل المنح — ولو كان مشرفاً كاملاً
    trip = await _chat_ride(client, session_factory)
    refused = await client.get(f"/admin/rides/{trip['ride']['id']}/chat", headers=target["headers"])
    assert refused.status_code == 403, refused.text

    granted = await _grant(client, admin_headers, target["id"], "trip_chats.read")
    assert granted["explicit"] is True
    assert set(granted["permissions"]) == before | {"trip_chats.read"}

    # **وما كان يملكه بقي يعمل** — بابُ كتابةٍ يحرسه `settings.write` مثلاً
    kept = await client.patch(
        "/admin/settings/services/JO", json={"chat_retention_days": 90}, headers=target["headers"]
    )
    assert kept.status_code == 200, kept.text
    assert (await client.get(f"/admin/rides/{trip['ride']['id']}/chat", headers=target["headers"])).status_code == 200


async def test_every_admin_read_is_audited_and_refused_without_the_permission(
    client: AsyncClient, session_factory, admin_headers: dict, support_headers: dict
) -> None:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    await _send(client, trip["rider"]["headers"], ride_id, "أنا عند الباب")
    await _send(client, trip["driver"]["headers"], ride_id, "دقيقتان")

    for headers in (admin_headers, support_headers):
        refused = await client.get(f"/admin/rides/{ride_id}/chat", headers=headers)
        assert refused.status_code == 403, refused.text
        assert (await client.get("/admin/chat-reports", headers=headers)).status_code == 403
    assert await _audit_rows(session_factory, "ride_chat") == []

    reader = await _chat_reader(client, admin_headers)
    for _ in range(2):
        read = await client.get(f"/admin/rides/{ride_id}/chat", headers=reader["headers"])
        assert read.status_code == 200, read.text
    body = read.json()
    assert [m["sender_role"] for m in body["messages"]] == ["rider", "driver"]
    assert body["rider_name"] and body["driver_name"]

    # **كلُّ فتحٍ سطر** — من، وأيَّ محادثة، وكم رسالة، ومتى (`created_at`)؛ ولا نصَّ في السطر
    rows = await _audit_rows(session_factory, "ride_chat")
    assert len(rows) == 2
    for row in rows:
        assert row.action is AuditAction.READ
        assert str(row.actor_id) == reader["id"]
        assert str(row.entity_id) == ride_id
        assert row.details == {"ride_id": ride_id, "message_count": 2}
    # **وقراءةُ المشرف لا تعلّم الرسائلَ مقروءة**
    assert all(message.read_at is None for message in await _messages(session_factory, ride_id))


async def test_reports_list_and_handling_are_audited(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    theirs = (await _send(client, trip["driver"]["headers"], ride_id, "كلامٌ مسيء")).json()
    await client.post(
        f"/rides/{ride_id}/chat/{theirs['id']}/report", json={"reason": "abuse"}, headers=trip["rider"]["headers"]
    )
    reader = await _chat_reader(client, admin_headers)

    listed = await client.get("/admin/chat-reports?status=open&country_code=JO", headers=reader["headers"])
    assert listed.status_code == 200, listed.text
    [row] = listed.json()
    assert row["message"]["body"] == "كلامٌ مسيء" and row["message"]["sender_role"] == "driver"
    assert row["reporter_role"] == "rider" and row["reporter_name"]
    assert row["ride_id"] == ride_id and row["status"] == "open"

    handled = await client.post(
        f"/admin/chat-reports/{row['id']}/handle", json={"note": "نُبّه الكبتن"}, headers=reader["headers"]
    )
    assert handled.status_code == 200, handled.text
    assert handled.json()["status"] == "handled" and handled.json()["handled_by_name"] == "قارئ المحادثات"
    twice = await client.post(f"/admin/chat-reports/{row['id']}/handle", json={}, headers=reader["headers"])
    assert twice.status_code == 409 and twice.json()["code"] == "chat_report_already_handled"

    assert len(await _audit_rows(session_factory, "chat_reports")) == 1
    [handle_row] = await _audit_rows(session_factory, "ride_message_report")
    assert handle_row.action is AuditAction.UPDATE and str(handle_row.actor_id) == reader["id"]


# ═════════════════════════ ٨) القديمُ يُحذف في موعده — والمبلَّغُ عنه حتى يُعالَج


async def _finished_chat(client: AsyncClient, session_factory) -> dict:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    await _send(client, trip["rider"]["headers"], ride_id, "أنا عند الباب")
    trip["theirs"] = (await _send(client, trip["driver"]["headers"], ride_id, "دقيقة")).json()
    cancelled = await client.post(
        f"/rides/{ride_id}/cancel", json={"reason": "تأخّر"}, headers=trip["driver"]["headers"]
    )
    assert cancelled.status_code == 200, cancelled.text
    return trip


async def _purge(session_factory, *, days_from_now: int) -> dict[str, int]:
    async with session_factory() as session:
        result = await trip_chat.purge_expired(session, now=datetime.now(UTC) + timedelta(days=days_from_now))
        await session.commit()
    return result


async def test_old_messages_are_deleted_on_schedule(client: AsyncClient, session_factory) -> None:
    trip = await _finished_chat(client, session_factory)
    ride_id = trip["ride"]["id"]

    # **قبل الموعد لا شيء** — تسعون يوماً افتراضاً بعد انتهاء الرحلة
    assert (await _purge(session_factory, days_from_now=89))["messages"] == 0
    assert len(await _messages(session_factory, ride_id)) == 2

    assert (await _purge(session_factory, days_from_now=91))["messages"] == 2
    assert await _messages(session_factory, ride_id) == []


async def test_a_reported_chat_is_kept_until_handled_then_the_clock_runs(
    client: AsyncClient, session_factory, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    trip = await _finished_chat(client, session_factory)
    ride_id = trip["ride"]["id"]
    report = (
        await client.post(
            f"/rides/{ride_id}/chat/{trip['theirs']['id']}/report",
            json={"reason": "fraud"},
            headers=trip["rider"]["headers"],
        )
    ).json()

    # **مفتوحٌ ⇒ المحادثةُ كلُّها تبقى** ولو مضت سنة
    assert (await _purge(session_factory, days_from_now=400))["messages"] == 0
    assert len(await _messages(session_factory, ride_id)) == 2

    # **عولج بعد ثلاثين يوماً من الرحلة ⇒ العدّادُ من وقت المعالجة**
    reader = await _chat_reader(client, admin_headers)
    later = datetime.now(UTC) + timedelta(days=30)
    monkeypatch.setattr(trip_chat, "_now", lambda: later)
    handled = await client.post(f"/admin/chat-reports/{report['id']}/handle", json={}, headers=reader["headers"])
    assert handled.status_code == 200, handled.text
    monkeypatch.undo()

    assert (await _purge(session_factory, days_from_now=100))["messages"] == 0
    assert (await _purge(session_factory, days_from_now=121))["messages"] == 2
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(RideMessageReport)) == 0


async def test_the_market_retention_is_read_from_its_setting(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    patched = await client.patch(
        "/admin/settings/services/JO", json={"chat_retention_days": 7}, headers=admin_headers
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["chat_retention_days"] == 7
    assert patched.json()["call_recording_enabled"] is False
    trip = await _finished_chat(client, session_factory)
    assert (await _purge(session_factory, days_from_now=6))["messages"] == 0
    assert (await _purge(session_factory, days_from_now=8))["messages"] == 2
    assert await _messages(session_factory, trip["ride"]["id"]) == []


async def test_account_deletion_removes_the_users_messages_but_keeps_an_open_report(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    trip = await _chat_ride(client, session_factory)
    ride_id = trip["ride"]["id"]
    await _send(client, trip["rider"]["headers"], ride_id, "أنا عند الباب")
    reported = (await _send(client, trip["rider"]["headers"], ride_id, "كلامٌ مسيء")).json()
    await _send(client, trip["driver"]["headers"], ride_id, "دقيقة")
    report = (
        await client.post(
            f"/rides/{ride_id}/chat/{reported['id']}/report",
            json={"reason": "abuse", "note": "سطر"},
            headers=trip["driver"]["headers"],
        )
    ).json()
    await client.post(f"/rides/{ride_id}/cancel", json={"reason": "تأخّر"}, headers=trip["driver"]["headers"])

    rider_id = uuid.UUID(trip["rider_id"])
    async with session_factory() as session:
        await session.execute(
            update(User).where(User.id == rider_id).values(deletion_due_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()
    async with session_factory() as session:
        outcome = await account_deletion.process_one(session, rider_id)
        await session.commit()
    assert outcome is not None and outcome.anonymized

    left = await _messages(session_factory, ride_id)
    # **رسالتُه تحت البلاغ المفتوح بقيت، والأخرى ذهبت — ورسالةُ الكبتن لا تخصّه**
    assert sorted((m.sender_role.value, m.body) for m in left) == [("driver", "دقيقة"), ("rider", "كلامٌ مسيء")]

    reader = await _chat_reader(client, admin_headers)
    await client.post(f"/admin/chat-reports/{report['id']}/handle", json={}, headers=reader["headers"])
    # **عولج ⇒ يلحق بصاحبه** في الكنس التالي، بلا انتظار مدّة الرحلة
    assert (await _purge(session_factory, days_from_now=0))["deleted_accounts"] == 1
    assert [m.sender_role.value for m in await _messages(session_factory, ride_id)] == ["driver"]


# ═════════════════════════ ٩) سطرُ الخصوصية قبل الإشعال — بنيةً لا تذكّراً


async def _draft(client: AsyncClient, admin_headers: dict, app: str, body: str) -> str:
    created = await client.post(
        "/admin/policies",
        json={"country_code": "JO", "doc_type": "privacy_policy", "app": app, "body_ar": body},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _publish(client: AsyncClient, admin_headers: dict, app: str, body: str) -> str:
    policy_id = await _draft(client, admin_headers, app, body)
    published = await client.post(f"/admin/policies/{policy_id}/publish", headers=admin_headers)
    assert published.status_code == 200, published.text
    return policy_id


async def test_enabling_requires_the_published_privacy_line(
    client: AsyncClient, admin_headers: dict
) -> None:
    for key in CHAT_FLAGS:
        refused = await client.put(
            "/admin/settings/feature-flags",
            json={"country_code": "JO", "feature_key": key, "enabled": True},
            headers=admin_headers,
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "privacy_line_unpublished"
        assert trip_chat.CHAT_PRIVACY_MARKER in refused.json()["message"]

    # **سطرٌ عند الراكب وحدَه لا يكفي** — المحادثةُ تحفظ ما كتبه الطرفان
    await _publish(client, admin_headers, "rider", f"سياسةٌ\n\n{trip_chat.CHAT_PRIVACY_MARKER}\n- ما نحفظه")
    half = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "trip_chat_enabled", "enabled": True},
        headers=admin_headers,
    )
    assert half.status_code == 409 and half.json()["missing"] == ["الكبتن"]

    await _publish(client, admin_headers, "driver", f"سياسةٌ\n\n{trip_chat.CHAT_PRIVACY_MARKER}\n- ما نحفظه")
    for key in CHAT_FLAGS:
        enabled = await client.put(
            "/admin/settings/feature-flags",
            json={"country_code": "JO", "feature_key": key, "enabled": True},
            headers=admin_headers,
        )
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()["flags"][key] is True

    # **والتسجيلُ له سطرُه هو** — ولا يكفيه سطرُ المحادثة
    recording = await client.patch(
        "/admin/settings/services/JO", json={"call_recording_enabled": True}, headers=admin_headers
    )
    assert recording.status_code == 409 and recording.json()["code"] == "privacy_line_unpublished"
    assert trip_chat.RECORDING_PRIVACY_MARKER in recording.json()["message"]
    listed = (await client.get("/admin/settings/services", headers=admin_headers)).json()
    assert all(row["call_recording_enabled"] is False for row in listed)

    # **والإطفاءُ بلا شرط** — إيقافُ الجمع لا يحتاج إذناً
    off = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "trip_chat_enabled", "enabled": False},
        headers=admin_headers,
    )
    assert off.status_code == 200 and off.json()["flags"]["trip_chat_enabled"] is False


async def test_the_published_line_cannot_be_removed_while_its_switch_is_on(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**الشرطُ قائمٌ ما دام المفتاح، لا لحظةَ الإشعال وحدَها** (قِيس ٢٠٢٦-١٠-٠٨): كان الإشعالُ يُسأل مرّةً، ثمّ تُنشر نسخةٌ بلا
    السطر أو تُسحب المنشورة والمكالمةُ تحفظ. **والآن يُردّ الاثنان ما دام ما يحفظه مشتعلاً، ويمضيان بعد الإطفاء.**"""
    chat = trip_chat.CHAT_PRIVACY_MARKER
    recording = trip_chat.RECORDING_PRIVACY_MARKER
    await _publish(client, admin_headers, "rider", f"سياسةٌ\n\n{chat}\n- ما نحفظه")
    driver_policy = await _publish(client, admin_headers, "driver", f"سياسةٌ\n\n{chat}\n- ما نحفظه")
    # **مفتاحُ المكالمة وحدَه يكفي ليحرس السطر** — وهو يحفظ سجلَّ من اتصل بمن
    calls_on = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "ride_calls_enabled", "enabled": True},
        headers=admin_headers,
    )
    assert calls_on.status_code == 200, calls_on.text

    bare = await _draft(client, admin_headers, "rider", "سياسةٌ بلا القسم")
    replaced = await client.post(f"/admin/policies/{bare}/publish", headers=admin_headers)
    assert replaced.status_code == 409 and replaced.json()["code"] == "privacy_line_in_use", replaced.text
    assert chat in replaced.json()["message"]
    withdrawn = await client.post(f"/admin/policies/{driver_policy}/withdraw", headers=admin_headers)
    assert withdrawn.status_code == 409 and withdrawn.json()["code"] == "privacy_line_in_use", withdrawn.text
    async with session_factory() as session:
        for app in (PolicyApp.RIDER, PolicyApp.DRIVER):
            live = await policies_service.published(
                session, country=CountryCode.JO, doc_type=PolicyDocType.PRIVACY_POLICY, app=app
            )
            assert live is not None and chat in live.body_ar

    # **ونسخةٌ تحمل السطرَ تُنشر** — التصحيحُ طريقُه نسخةٌ فيها القسم
    await _publish(client, admin_headers, "rider", f"سياسةٌ مصحَّحة\n\n{chat}\n- ما نحفظه")

    # **والتسجيلُ يحرس سطرَه هو** — ولا يكفيه سطرُ المحادثة
    await _publish(client, admin_headers, "rider", f"سياسةٌ\n\n{chat}\n\n{recording}\n- ما نسجّله")
    await _publish(client, admin_headers, "driver", f"سياسةٌ\n\n{chat}\n\n{recording}\n- ما نسجّله")
    recording_on = await client.patch(
        "/admin/settings/services/JO", json={"call_recording_enabled": True}, headers=admin_headers
    )
    assert recording_on.status_code == 200, recording_on.text
    chat_only = await _draft(client, admin_headers, "driver", f"سياسةٌ\n\n{chat}\n- ما نحفظه")
    refused = await client.post(f"/admin/policies/{chat_only}/publish", headers=admin_headers)
    assert refused.status_code == 409 and refused.json()["code"] == "privacy_line_in_use", refused.text
    assert recording in refused.json()["message"]

    # **والإطفاءُ يُطلقهما** — إيقافُ الجمع لا يحتاج إذناً، ثمّ يُنشر ويُسحب ما شاء
    recording_off = await client.patch(
        "/admin/settings/services/JO", json={"call_recording_enabled": False}, headers=admin_headers
    )
    assert recording_off.status_code == 200, recording_off.text
    assert (await client.post(f"/admin/policies/{chat_only}/publish", headers=admin_headers)).status_code == 200
    calls_off = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "ride_calls_enabled", "enabled": False},
        headers=admin_headers,
    )
    assert calls_off.status_code == 200, calls_off.text
    released = await client.post(f"/admin/policies/{chat_only}/withdraw", headers=admin_headers)
    assert released.status_code == 200, released.text
