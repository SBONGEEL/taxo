"""صندوق وارد الإشعارات داخل التطبيق (المرحلة 9-ب).

القاعدة التي يختبرها هذا الملف قبل أي شيء آخر: **الصفُّ أثرُ الحدث لا أثرُ
المزوّد**. لا عقد FCM، أو جهازٌ مفتوح فلا Push له — كلاهما لا يعني أن الحدث
لم يقع، والجرس يعرض ما جرى لا ما نجح إرسالُه.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.notification import UserNotification
from tests.helpers import (
    DRIVER,
    RIDER,
    accepted_ride,
    approved_driver,
    auth,
    bring_online,
    enable_push_provider,
    inbox_of,
    register,
    register_device,
)


async def _inbox(client: AsyncClient, headers: dict, **params) -> list[dict]:
    response = await client.get(
        "/me/notifications", headers=headers, params=params or None
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _unread(client: AsyncClient, headers: dict) -> int:
    response = await client.get("/me/notifications/unread-count", headers=headers)
    assert response.status_code == 200
    return response.json()["unread"]


# ------------------------------------------------- الكتابة من باب الإرسال


async def test_a_ride_event_lands_in_both_inboxes_without_any_push_contract(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """لا عقد FCM في هذا الاختبار — والصفّان يُكتبان مع ذلك."""
    rider = await register(client, RIDER)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await accepted_ride(client, auth(rider), driver)

    rider_entries = await inbox_of(session_factory, rider["user"]["id"])
    driver_entries = await inbox_of(session_factory, driver["user_id"])
    assert [entry.kind for entry in rider_entries] == ["driver_assigned"]
    assert rider_entries[0].data["ride_id"] == ride["id"]
    assert rider_entries[0].title == "تم قبول رحلتك"
    assert rider_entries[0].read_at is None

    # **وبطاقةُ الطلب ليست فيها**: عمرُها عشرون ثانية، وصفٌّ باقٍ يقول «طلب
    # رحلة جديد» لطلبٍ مضى يفتح عند الضغط لا شيء (`EPHEMERAL_KINDS`)
    assert [entry.kind for entry in driver_entries] == ["driver_assigned"]


async def test_the_kind_matches_the_push_payload_type(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """`kind` هو `data["type"]` نفسه — فلا يفترق ما يفتحه الضغط هنا وهناك."""
    await enable_push_provider(session_factory)
    rider = await register(client, RIDER)
    await register_device(client, auth(rider), token="rider-token")
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    await accepted_ride(client, auth(rider), driver)

    entries = await inbox_of(session_factory, rider["user"]["id"])
    assert entries[0].kind == entries[0].data["type"]


# ------------------------------------------------------------- القراءة


async def test_listing_paging_and_unread_filter(
    client: AsyncClient, session_factory
) -> None:
    rider = await register(client, RIDER)
    headers = auth(rider)
    user_id = uuid.UUID(rider["user"]["id"])

    now = datetime.now(UTC)
    async with session_factory() as session:
        for index in range(3):
            session.add(
                UserNotification(
                    user_id=user_id,
                    kind="test_event",
                    title=f"عنوان {index}",
                    body="نص",
                    # ترتيبٌ صريح: `created_at` الافتراضي واحدٌ للثلاثة
                    created_at=now - timedelta(minutes=index),
                    read_at=now if index == 2 else None,
                )
            )
        await session.commit()

    listed = await _inbox(client, headers)
    assert [entry["title"] for entry in listed] == ["عنوان 0", "عنوان 1", "عنوان 2"]

    unread = await _inbox(client, headers, unread_only=True)
    assert [entry["title"] for entry in unread] == ["عنوان 0", "عنوان 1"]
    assert await _unread(client, headers) == 2

    page = await _inbox(client, headers, limit=1, offset=1)
    assert [entry["title"] for entry in page] == ["عنوان 1"]


async def test_marking_all_read_empties_the_dot(
    client: AsyncClient, session_factory
) -> None:
    rider = await register(client, RIDER)
    headers = auth(rider)
    async with session_factory() as session:
        for index in range(2):
            session.add(
                UserNotification(
                    user_id=uuid.UUID(rider["user"]["id"]),
                    kind="test_event",
                    title=f"عنوان {index}",
                    body="نص",
                )
            )
        await session.commit()

    assert await _unread(client, headers) == 2
    response = await client.post("/me/notifications/read", json={}, headers=headers)
    assert response.status_code == 200
    assert response.json()["unread"] == 0
    assert await _unread(client, headers) == 0


async def test_marking_by_id_touches_nothing_that_is_not_yours(
    client: AsyncClient, session_factory
) -> None:
    """معرّفٌ لغير صاحبه لا يُعلَّم ولا يُبلَّغ عنه (لا IDOR — القسم 14)."""
    mine = await register(client, RIDER)
    theirs = await register(client, RIDER | {"phone": "0796666666", "name": "راكب آخر"})

    async with session_factory() as session:
        stranger = UserNotification(
            user_id=uuid.UUID(theirs["user"]["id"]),
            kind="test_event",
            title="ليس لك",
            body="نص",
        )
        session.add(stranger)
        await session.commit()
        stranger_id = str(stranger.id)

    response = await client.post(
        "/me/notifications/read", json={"ids": [stranger_id]}, headers=auth(mine)
    )
    # لا 403 ولا 404: الطلب صحيح ولم يُصب شيئاً
    assert response.status_code == 200
    assert response.json()["unread"] == 0
    assert await _unread(client, auth(theirs)) == 1


async def test_the_inbox_is_read_only_and_authenticated(client: AsyncClient) -> None:
    """لا مسار إنشاء: إشعارٌ يكتبه العميل ليس إشعاراً."""
    assert (await client.get("/me/notifications")).status_code == 401
    assert (await client.post("/me/notifications", json={})).status_code in (401, 405)


# ------------------------------------------------------------- الحملات


async def test_a_campaign_reaches_the_inbox_only_of_those_it_was_sent_to(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """من أطفأ إشعارات العروض أطفأها — ولا تدخل صندوقه من بابٍ آخر."""
    from app.services import campaigns

    await enable_push_provider(session_factory)
    reached = await register(client, RIDER)
    await register_device(client, auth(reached), token="reached-token")

    opted_out = await register(
        client, RIDER | {"phone": "0797777777", "name": "راكب رافض"}
    )
    await register_device(
        client, auth(opted_out), device_id="device-2", token="opted-out-token"
    )
    silenced = await client.put(
        "/me/notification-preferences",
        json={"marketing_push_enabled": False},
        headers=auth(opted_out),
    )
    assert silenced.status_code == 200

    created = await client.post(
        "/admin/campaigns",
        json={
            "title": "خصم نهاية الأسبوع",
            "body": "استخدم الرمز TAXO25",
            "audience": "all_riders",
            "scheduled_at": datetime.now(UTC).isoformat(),
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text

    async with session_factory() as session:
        campaign = await campaigns.get_campaign(
            session, uuid.UUID(created.json()["id"]), for_update=True
        )
        # وقتٌ خارج ساعات الهدوء الافتراضية (22:00 → 08:00) بتوقيت عمّان
        result = await campaigns.dispatch(
            session, campaign, now=datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
        )
        await session.commit()
    assert result.sent == 1 and result.skipped == 1

    assert [entry.kind for entry in await inbox_of(session_factory, reached["user"]["id"])] == [
        "campaign"
    ]
    assert await inbox_of(session_factory, opted_out["user"]["id"]) == []

    async with session_factory() as session:
        total = await session.scalar(
            select(func.count()).select_from(UserNotification)
        )
    assert total == 1
