"""حملات الإشعارات الإدارية/التسويقية (SPEC القسم 13 — المرحلة 8)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, time, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import CampaignStatus
from app.models.notification import NotificationCampaign
from tests.helpers import (
    DRIVER,
    RIDER,
    auth,
    enable_push_provider,
    pushes_to,
    register,
    register_device,
)

async def _create(
    client: AsyncClient, headers: dict, **overrides
) -> dict:
    payload = {
        "title": "عرض اليوم",
        "body": "خصم 20% على رحلاتك",
        "audience": "all_riders",
    } | overrides
    response = await client.post("/admin/campaigns", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _dispatch(session_factory, campaign_id: str, *, now: datetime | None = None):
    """يستدعي الخدمة مباشرةً كما تفعل مهمة Celery — بلا عاملٍ يعمل."""
    import uuid

    from app.services import campaigns

    async with session_factory() as session:
        campaign = await campaigns.get_campaign(
            session, uuid.UUID(campaign_id), for_update=True
        )
        result = await campaigns.dispatch(session, campaign, now=now)
        await session.commit()
    return result


# ------------------------------------------------------------- الصلاحيات


async def test_campaigns_are_admin_only(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    """حملةٌ تصل عشرات الآلاف ليست إجراء دعمٍ فني (SPEC القسم 13/8)."""
    assert (
        await client.get("/admin/campaigns", headers=support_headers)
    ).status_code == 403
    assert (
        await client.get("/admin/campaigns", headers=admin_headers)
    ).status_code == 200


# ---------------------------------------------------------------- الحياة


async def test_create_draft_then_schedule_then_cancel(
    client: AsyncClient, admin_headers: dict
) -> None:
    campaign = await _create(client, admin_headers)
    assert campaign["status"] == "draft"

    scheduled_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    scheduled = await client.patch(
        f"/admin/campaigns/{campaign['id']}",
        json={"scheduled_at": scheduled_at},
        headers=admin_headers,
    )
    assert scheduled.status_code == 200
    assert scheduled.json()["status"] == "scheduled"

    cancelled = await client.post(
        f"/admin/campaigns/{campaign['id']}/cancel", headers=admin_headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # ولا تُعدَّل بعد الإلغاء
    late = await client.patch(
        f"/admin/campaigns/{campaign['id']}",
        json={"title": "عنوان آخر"},
        headers=admin_headers,
    )
    assert late.status_code == 409


async def test_country_audience_requires_a_country(
    client: AsyncClient, admin_headers: dict
) -> None:
    response = await client.post(
        "/admin/campaigns",
        json={"title": "عنوان", "body": "نص الحملة", "audience": "by_country"},
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_segment_audience_waits_for_stage_twelve(
    client: AsyncClient, admin_headers: dict
) -> None:
    """لا يُخترع للشريحة معنى قبل أن تُعرَّف (SPEC القسم 15/ب)."""
    response = await client.post(
        "/admin/campaigns",
        json={"title": "عنوان", "body": "نص الحملة", "audience": "segment"},
        headers=admin_headers,
    )
    assert response.status_code == 501


async def test_campaign_writes_are_audited(
    client: AsyncClient, admin_headers: dict
) -> None:
    await _create(client, admin_headers)
    logs = (
        await client.get(
            "/admin/settings/audit-logs?entity_type=notification_campaign",
            headers=admin_headers,
        )
    ).json()
    assert len(logs) == 1
    assert logs[0]["details"]["audience"] == "all_riders"


# ---------------------------------------------------------------- الإرسال


async def _quiet_hours(session_factory, country: str, start: str, end: str) -> None:
    from app.models.enums import CountryCode
    from app.services import campaigns

    async with session_factory() as session:
        setting = await campaigns.get_or_create_settings(
            session, CountryCode(country)
        )
        setting.quiet_hours_start = time.fromisoformat(start)
        setting.quiet_hours_end = time.fromisoformat(end)
        setting.timezone = "UTC"
        await session.commit()


async def test_dispatch_sends_to_the_audience_and_records_deliveries(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    await enable_push_provider(session_factory)
    await _quiet_hours(session_factory, "JO", "00:00", "00:00")  # لا هدوء

    rider = auth(await register(client, RIDER))
    await register_device(client, rider, token="fcm-rider-token")
    driver = auth(await register(client, DRIVER))
    await register_device(client, driver, token="fcm-driver-token")

    campaign = await _create(
        client,
        admin_headers,
        scheduled_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )
    result = await _dispatch(session_factory, campaign["id"])

    assert result.completed is True
    assert result.sent == 1  # الركاب وحدهم
    assert [m["title"] for m in await pushes_to("fcm-rider-token")] == ["عرض اليوم"]
    assert await pushes_to("fcm-driver-token") == []

    deliveries = (
        await client.get(
            f"/admin/campaigns/{campaign['id']}/deliveries", headers=admin_headers
        )
    ).json()
    assert [row["status"] for row in deliveries] == ["sent"]


async def test_opted_out_user_is_skipped_and_the_skip_is_recorded(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """احترامُ الإطفاء مُثبَتٌ في السجل لا مزعوم."""
    await enable_push_provider(session_factory)
    await _quiet_hours(session_factory, "JO", "00:00", "00:00")

    rider = auth(await register(client, RIDER))
    await register_device(client, rider, token="fcm-rider-token")
    await client.put(
        "/me/notification-preferences",
        json={"marketing_push_enabled": False},
        headers=rider,
    )

    campaign = await _create(
        client,
        admin_headers,
        scheduled_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )
    result = await _dispatch(session_factory, campaign["id"])

    assert result.sent == 0
    assert result.skipped == 1
    assert await pushes_to("fcm-rider-token") == []

    deliveries = (
        await client.get(
            f"/admin/campaigns/{campaign['id']}/deliveries", headers=admin_headers
        )
    ).json()
    assert [row["status"] for row in deliveries] == ["skipped"]


async def test_quiet_hours_defer_the_campaign_to_the_next_window(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """لا يُلغى الإرسال ولا يُرسل ناقصاً — يُؤجَّل (SPEC القسم 13/6)."""
    await enable_push_provider(session_factory)
    # نافذة هدوء تعبر منتصف الليل بتوقيت UTC، واللحظة داخلها
    await _quiet_hours(session_factory, "JO", "22:00", "08:00")

    rider = auth(await register(client, RIDER))
    await register_device(client, rider, token="fcm-rider-token")

    campaign = await _create(
        client,
        admin_headers,
        scheduled_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )
    quiet_moment = datetime(2026, 8, 10, 23, 30, tzinfo=UTC)
    result = await _dispatch(session_factory, campaign["id"], now=quiet_moment)

    assert result.deferred is True
    assert result.sent == 0
    assert await pushes_to("fcm-rider-token") == []

    async with session_factory() as session:
        stored = await session.scalar(select(NotificationCampaign))
    assert stored.status is CampaignStatus.SCHEDULED  # ما زالت تنتظر نافذتها

    # وفي النافذة التالية تُرسل وتكتمل
    open_moment = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    again = await _dispatch(session_factory, campaign["id"], now=open_moment)
    assert again.completed is True
    assert again.sent == 1


async def test_a_second_run_does_not_send_twice(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """الفريدُ على `(campaign_id, user_id)` هو الحارس، لا ذاكرةُ المهمة."""
    await enable_push_provider(session_factory)
    await _quiet_hours(session_factory, "JO", "00:00", "00:00")

    rider = auth(await register(client, RIDER))
    await register_device(client, rider, token="fcm-rider-token")

    campaign = await _create(
        client,
        admin_headers,
        scheduled_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )
    await _dispatch(session_factory, campaign["id"])

    # الحملة صارت `sent` فلا تُرسل ثانيةً أصلاً
    import uuid

    from app.core.exceptions import Conflict
    from app.services import campaigns

    async with session_factory() as session:
        stored = await campaigns.get_campaign(session, uuid.UUID(campaign["id"]))
        try:
            await campaigns.dispatch(session, stored)
        except Conflict:
            pass
        else:  # pragma: no cover - يعني أن الحارس سقط
            raise AssertionError("أُرسلت حملة مكتملة مرة ثانية")

    assert len(await pushes_to("fcm-rider-token")) == 1


async def test_dispatch_without_a_push_contract_keeps_the_campaign_scheduled(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """تعليمُها «مُرسلة» بصفر متلقٍّ كذبٌ في سجلٍّ يُقرأ لاحقاً."""
    await _quiet_hours(session_factory, "JO", "00:00", "00:00")
    auth(await register(client, RIDER))

    campaign = await _create(
        client,
        admin_headers,
        scheduled_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )
    result = await _dispatch(session_factory, campaign["id"])

    assert result.completed is False
    async with session_factory() as session:
        stored = await session.scalar(select(NotificationCampaign))
    assert stored.status is CampaignStatus.SCHEDULED


# ------------------------------------------------------------ إشعار تجريبي


async def test_test_push_reaches_the_named_token(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """مِجَسٌّ يتخطى جدول الأجهزة وقاعدة الاستثناء عمداً."""
    await enable_push_provider(session_factory)

    response = await client.post(
        "/admin/campaigns/test-push",
        json={"token": "fcm-probe-token", "title": "تجربة"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["delivered"] == 1
    assert body["invalid_token"] is False

    assert [m["title"] for m in await pushes_to("fcm-probe-token")] == ["تجربة"]


async def test_test_push_reports_a_dead_token_without_failing(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    from app.services.push.mock import INVALID_TOKEN

    await enable_push_provider(session_factory)

    response = await client.post(
        "/admin/campaigns/test-push",
        json={"token": INVALID_TOKEN},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["invalid_token"] is True
    assert response.json()["delivered"] == 0


async def test_test_push_needs_a_contract_and_an_admin(
    client: AsyncClient, admin_headers: dict, support_headers: dict, session_factory
) -> None:
    denied = await client.post(
        "/admin/campaigns/test-push",
        json={"token": "fcm-probe-token"},
        headers=support_headers,
    )
    assert denied.status_code == 403

    missing = await client.post(
        "/admin/campaigns/test-push",
        json={"token": "fcm-probe-token"},
        headers=admin_headers,
    )
    assert missing.status_code == 503
    assert missing.json()["code"] == "push_unavailable"


async def test_test_push_is_audited_without_the_token(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    await enable_push_provider(session_factory)
    await client.post(
        "/admin/campaigns/test-push",
        json={"token": "fcm-probe-token"},
        headers=admin_headers,
    )

    logs = (
        await client.get(
            "/admin/settings/audit-logs?entity_type=push_test", headers=admin_headers
        )
    ).json()
    assert len(logs) == 1
    assert "fcm-probe-token" not in json.dumps(logs, ensure_ascii=False)


# ------------------------------------------------------------ ساعات الهدوء


async def test_quiet_hours_settings_round_trip(
    client: AsyncClient, admin_headers: dict
) -> None:
    default = (
        await client.get("/admin/campaigns/settings/JO", headers=admin_headers)
    ).json()
    assert default["timezone"] == "Asia/Amman"
    assert default["quiet_hours_start"].startswith("22:00")

    updated = await client.put(
        "/admin/campaigns/settings/JO",
        json={
            "quiet_hours_start": "23:00",
            "quiet_hours_end": "07:00",
            "timezone": "Asia/Amman",
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["quiet_hours_start"].startswith("23:00")


async def test_unknown_timezone_is_rejected(
    client: AsyncClient, admin_headers: dict
) -> None:
    """مِنطقةٌ لا تُعرف تجعل كل حساب هدوءٍ بعدها خاطئاً بصمت."""
    response = await client.put(
        "/admin/campaigns/settings/JO",
        json={
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "timezone": "Mars/Olympus",
        },
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_a_scheduled_campaign_can_be_edited_and_a_sent_one_cannot(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**حملةٌ مجدولةٌ لا تُعدَّل تعني حذفاً وإعادةَ إنشاء** (قرارُ المالك 2026-08-19).

    فيفقد المشرفُ نصَّه وجدولتَه ليصلح حرفاً. والبابُ مبنيٌّ منذ المرحلة ٨
    ومصرَّحٌ به في `endpoints.ts` **ولم ينادِه أحد** حتى وُصل له زرّ.

    **وما انطلق لا يُعدَّل**: نصٌّ وصل هواتفَ الناس لا يُغيَّر بعد وصوله، وتعديلُ
    صفِّه يجعل السجلَّ يقول غيرَ ما قُرئ.
    """
    import uuid

    from app.models.enums import CampaignStatus
    from app.models.notification import NotificationCampaign

    created = await client.post(
        "/admin/campaigns",
        json={
            "title": "عرضُ الجمعة",
            "body": "خصمٌ على رحلات اليوم",
            "audience": "all_riders",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]

    edited = await client.patch(
        f"/admin/campaigns/{campaign_id}",
        json={"title": "عرضُ السبت", "body": "خصمٌ على رحلات الغد"},
        headers=admin_headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["title"] == "عرضُ السبت"

    # وما انطلق يُرفض تعديلُه — والشاشةُ لا تعرض الزرَّ عليه أصلاً
    async with session_factory() as session:
        row = await session.get(NotificationCampaign, uuid.UUID(campaign_id))
        row.status = CampaignStatus.SENT
        await session.commit()

    refused = await client.patch(
        f"/admin/campaigns/{campaign_id}",
        json={"title": "بعد الإرسال"},
        headers=admin_headers,
    )
    assert refused.status_code == 409, refused.text
