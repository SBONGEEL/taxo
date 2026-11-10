"""الاعتمادُ الاستثنائيُّ ومتابعةُ الوثائق (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١).

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**

١) **الصلاحيّةُ منفصلةٌ ومطفأةٌ افتراضاً** — المشرفُ الكامل يُردّ بـ403 حتى تُمنح بالاسم.
٢) **الاعتمادُ بلا وثائق بسببٍ إلزاميٍّ مدقَّق** — والوسمُ في قائمة اللوحة وفلترها، **ولا يصل `DriverOut` الذي يقرؤه الكبتن**.
٣) **المهلةُ**: تذكيرٌ قبلها مرّةً لا مرّتين، **وتجميدٌ آليٌّ عندها** برسالةٍ تفتح شاشةَ الرفع، وإلغاءُ التجميد يعيده معتمداً.
٤) **الاعتمادُ العاديُّ يزيل الوسم**، و«طلب الوثائق» يصل الموسومين، والإعداداتُ لكلِّ دولةٍ بحدودها.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.driver import Driver, DriverDocument, required_document_types
from app.models.enums import DocumentReviewStatus, DriverStatus
from app.models.notification import UserNotification
from app.models.user import User
from tests.conftest import _staff_headers
from tests.helpers import DRIVER, SECOND_DRIVER, auth, register

pytestmark = pytest.mark.asyncio


async def _manager(client: AsyncClient, admin_headers: dict, phone: str = "+962790000091") -> dict:
    """**مشرفٌ مُنح «الاعتماد الاستثنائي» بالاسم** — كما تمنحها المصفوفة."""
    headers = await _staff_headers("admin", phone, "مدير الاعتماد")
    me = (await client.get("/auth/me", headers=headers)).json()
    rows = (await client.get("/admin/permissions", headers=admin_headers)).json()
    row = next(item for item in rows if item["user_id"] == me["id"])
    assert "drivers.exceptional" not in row["permissions"], "الصلاحيةُ وصلت بالافتراض — وهي «مطفأةٌ لغير المالك»"
    granted = await client.put(
        f"/admin/permissions/{me['id']}",
        json={"permissions": sorted(set(row["permissions"]) | {"drivers.exceptional"})},
        headers=admin_headers,
    )
    assert granted.status_code == 200, granted.text
    return {"headers": headers, "id": me["id"]}


async def _pending_driver(client: AsyncClient, session_factory, payload: dict = DRIVER) -> dict:
    body = await register(client, payload)
    async with session_factory() as session:
        driver = await session.scalar(select(Driver).where(Driver.user_id == uuid.UUID(body["user"]["id"])))
        assert driver.status is DriverStatus.PENDING
        return {"headers": auth(body), "driver_id": driver.id, "user_id": uuid.UUID(body["user"]["id"])}


async def _kinds(session_factory, user_id: uuid.UUID) -> list[str]:
    async with session_factory() as session:
        rows = await session.scalars(
            select(UserNotification.kind).where(UserNotification.user_id == user_id).order_by(UserNotification.created_at)
        )
        return list(rows)


async def _approve(client: AsyncClient, manager: dict, driver_id, reason: str = "سائقٌ معروف، وثائقه قيد الاستخراج"):
    return await client.post(
        f"/admin/drivers/{driver_id}/approve-exceptional", json={"reason": reason}, headers=manager["headers"]
    )


# ─────────────────────────────────────────── ١) الصلاحيّة


async def test_the_full_admin_cannot_approve_exceptionally_until_granted_by_name(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    driver = await _pending_driver(client, session_factory)
    refused = await client.post(
        f"/admin/drivers/{driver['driver_id']}/approve-exceptional", json={"reason": "سببٌ كافٍ"}, headers=admin_headers
    )
    assert refused.status_code == 403, refused.text
    # **والقراءةُ للفريق** — يرى الوسمَ ولا يفعل
    read = await client.get(f"/admin/drivers/{driver['driver_id']}/exceptional", headers=admin_headers)
    assert read.status_code == 200 and read.json()["exceptional"] is False


# ─────────────────────────────────────────── ٢) الاعتمادُ بلا وثائق


async def test_approval_without_documents_needs_a_reason_is_audited_and_marked_for_admins_only(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    manager = await _manager(client, admin_headers)
    driver = await _pending_driver(client, session_factory)

    short = await _approve(client, manager, driver["driver_id"], reason="لا")
    assert short.status_code == 422, short.text

    approved = await _approve(client, manager, driver["driver_id"])
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "approved" and body["exceptional"] is True
    assert body["approved_by_name"] == "مدير الاعتماد"
    assert body["missing_documents"], "الوثائقُ ناقصةٌ فعلاً — وهذا ما يجعله استثنائيّاً"
    deadline = datetime.fromisoformat(body["deadline_at"])
    assert timedelta(days=13) < deadline - datetime.now(UTC) <= timedelta(days=14), "المهلةُ الافتراضيّةُ ١٤ يوماً بنصّ المالك"

    flagged = (await client.get("/admin/drivers?exceptional=true", headers=admin_headers)).json()
    assert [row["driver_id"] for row in flagged] == [str(driver["driver_id"])]
    assert flagged[0]["exceptional"] is True and flagged[0]["documents_deadline_at"]
    others = (await client.get("/admin/drivers?exceptional=false", headers=admin_headers)).json()
    assert str(driver["driver_id"]) not in {row["driver_id"] for row in others}

    me = (await client.get("/drivers/me", headers=driver["headers"])).json()["driver"]
    assert me["status"] == "approved"
    assert not {"exceptional", "exceptional_reason", "documents_deadline_at"} & set(me), "الوسمُ للمشرفين وحدَهم"

    async with session_factory() as session:
        audit = await session.scalar(
            select(AdminAuditLog).where(
                AdminAuditLog.entity_type == "driver_exceptional_approval", AdminAuditLog.entity_id == driver["driver_id"]
            )
        )
    assert audit is not None and audit.details["reason"] == "سائقٌ معروف، وثائقه قيد الاستخراج"
    assert "driver_approved" in await _kinds(session_factory, driver["user_id"])


# ─────────────────────────────────────────── ٣) المهلةُ والتجميد


async def _set_deadline(session_factory, driver_id, when: datetime) -> None:
    async with session_factory() as session:
        driver = await session.get(Driver, driver_id)
        driver.documents_deadline_at = when
        await session.commit()


async def _sweep(session_factory, now: datetime | None = None) -> dict[str, int]:
    from app.core.redis_client import get_redis_client
    from app.services import exceptional_approval

    async with session_factory() as session:
        return await exceptional_approval.sweep(session, get_redis_client(), now=now)


async def test_a_warning_before_the_deadline_goes_once_and_the_deadline_freezes_then_unfreeze_restores(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    manager = await _manager(client, admin_headers)
    driver = await _pending_driver(client, session_factory)
    assert (await _approve(client, manager, driver["driver_id"])).status_code == 200

    await _set_deadline(session_factory, driver["driver_id"], datetime.now(UTC) + timedelta(days=2, hours=1))
    assert (await _sweep(session_factory))["warned"] == 1
    assert (await _sweep(session_factory))["warned"] == 0, "تذكيرُ اليوم نفسِه لا يتكرّر"
    assert "document_upload_requested" in await _kinds(session_factory, driver["user_id"])

    await _set_deadline(session_factory, driver["driver_id"], datetime.now(UTC) - timedelta(minutes=5))
    assert (await _sweep(session_factory))["frozen"] == 1
    async with session_factory() as session:
        frozen = await session.get(Driver, driver["driver_id"])
        assert frozen.status is DriverStatus.SUSPENDED
        assert frozen.exceptional_approved_at is not None, "التجميدُ لا يمحو الوسم — إلغاؤه يعيده استثنائيّاً"
        audit = await session.scalar(
            select(AdminAuditLog).where(AdminAuditLog.entity_type == "driver_freeze", AdminAuditLog.entity_id == frozen.id)
        )
        assert audit is not None and audit.details["automatic"] is True
    assert "document_deadline_frozen" in await _kinds(session_factory, driver["user_id"])

    no_reason = await client.post(
        f"/admin/drivers/{driver['driver_id']}/unfreeze", json={"reason": "  "}, headers=manager["headers"]
    )
    assert no_reason.status_code == 422, no_reason.text
    restored = await client.post(
        f"/admin/drivers/{driver['driver_id']}/unfreeze", json={"reason": "وعد برفعها هذا الأسبوع"}, headers=manager["headers"]
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "approved"
    assert datetime.fromisoformat(restored.json()["deadline_at"]) > datetime.now(UTC) + timedelta(days=6), "مهلةٌ منقضيةٌ تُمدّ أسبوعاً"
    assert "account_unfrozen" in await _kinds(session_factory, driver["user_id"])


async def test_a_manual_freeze_carries_its_reason_to_the_driver(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    manager = await _manager(client, admin_headers)
    driver = await _pending_driver(client, session_factory)
    assert (await _approve(client, manager, driver["driver_id"])).status_code == 200
    frozen = await client.post(
        f"/admin/drivers/{driver['driver_id']}/freeze", json={"reason": "شكوى قيد التحقيق"}, headers=manager["headers"]
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["status"] == "suspended"
    async with session_factory() as session:
        note = await session.scalar(
            select(UserNotification).where(
                UserNotification.user_id == driver["user_id"], UserNotification.kind == "account_frozen"
            )
        )
    assert note is not None and "شكوى قيد التحقيق" in note.body


# ─────────────────────────────────────────── ٤) الاعتمادُ العاديّ · الطلب · الإعدادات


async def test_normal_approval_once_documents_are_accepted_removes_the_mark(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    from app.services import drivers as drivers_service

    manager = await _manager(client, admin_headers)
    driver = await _pending_driver(client, session_factory)
    assert (await _approve(client, manager, driver["driver_id"])).status_code == 200
    async with session_factory() as session:
        for doc_type in required_document_types(gender_verified_female=False):
            session.add(
                DriverDocument(
                    driver_id=driver["driver_id"],
                    doc_type=doc_type,
                    file_path=f"test/{doc_type.value}.jpg",
                    content_type="image/jpeg",
                    size_bytes=10,
                    review_status=DocumentReviewStatus.APPROVED,
                )
            )
        await session.commit()
        row = await session.get(Driver, driver["driver_id"])
        actor = await session.get(User, uuid.UUID(manager["id"]))
        await drivers_service.approve(session, driver=row, actor=actor)
        await session.commit()
        await session.refresh(row)
        assert row.exceptional_approved_at is None and row.documents_deadline_at is None


async def test_request_documents_reaches_every_flagged_driver(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    manager = await _manager(client, admin_headers)
    first = await _pending_driver(client, session_factory, DRIVER)
    second = await _pending_driver(client, session_factory, SECOND_DRIVER)
    for item in (first, second):
        assert (await _approve(client, manager, item["driver_id"])).status_code == 200
    sent = await client.post("/admin/drivers/request-documents", json={"all_flagged": True}, headers=manager["headers"])
    assert sent.status_code == 200 and sent.json() == {"sent": 2}, sent.text
    for item in (first, second):
        assert "document_upload_requested" in await _kinds(session_factory, item["user_id"])
    empty = await client.post("/admin/drivers/request-documents", json={}, headers=manager["headers"])
    assert empty.status_code == 422


async def test_document_settings_are_per_country_bounded_and_need_the_grant(
    client: AsyncClient, admin_headers: dict
) -> None:
    default = (await client.get("/admin/document-settings/JO", headers=admin_headers)).json()
    assert default == {
        "country_code": "JO",
        "exceptional_deadline_days": 14,
        "exceptional_reminder_days": 3,
        "expiry_notice_days": [30, 7, 1],
    }
    body = {"exceptional_deadline_days": 10, "exceptional_reminder_days": 7, "expiry_notice_days": [14, 3]}
    refused = await client.put("/admin/document-settings/JO", json=body, headers=admin_headers)
    assert refused.status_code == 403
    manager = await _manager(client, admin_headers)
    saved = await client.put("/admin/document-settings/JO", json=body, headers=manager["headers"])
    assert saved.status_code == 200, saved.text
    assert saved.json()["expiry_notice_days"] == [14, 3]
    assert (await client.get("/admin/document-settings/DZ", headers=admin_headers)).json()["exceptional_deadline_days"] == 14
    bad = await client.put(
        "/admin/document-settings/JO", json=body | {"exceptional_reminder_days": 5}, headers=manager["headers"]
    )
    assert bad.status_code == 422


async def test_expiry_notice_days_follow_the_country_setting_and_the_panel_lists_what_expires(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**البند ٢**: أيامُ التنبيه من إعداد الدولة لا ثابتة — ١٤ مضبوطةٌ تُنبِّه، و٣٠ الافتراضيّةُ لا تُنبِّه لوثيقةٍ بعد ١٤ يوماً."""
    from app.services import document_expiry
    from app.services.stats import country_today
    from app.models.enums import CountryCode

    manager = await _manager(client, admin_headers)
    driver = await _pending_driver(client, session_factory)
    doc_type = required_document_types(gender_verified_female=False)[0]
    async with session_factory() as session:
        today = await country_today(session, CountryCode.JO)
        row = await session.get(Driver, driver["driver_id"])
        row.status = DriverStatus.APPROVED
        session.add(
            DriverDocument(
                driver_id=driver["driver_id"],
                doc_type=doc_type,
                file_path="test/expiring.jpg",
                content_type="image/jpeg",
                size_bytes=10,
                review_status=DocumentReviewStatus.APPROVED,
                expires_on=today + timedelta(days=14),
            )
        )
        await session.commit()
        assert await document_expiry.expiring_on(session, today=today, country=CountryCode.JO) == []

    saved = await client.put(
        "/admin/document-settings/JO",
        json={"exceptional_deadline_days": 14, "exceptional_reminder_days": 3, "expiry_notice_days": [14, 2]},
        headers=manager["headers"],
    )
    assert saved.status_code == 200, saved.text
    async with session_factory() as session:
        found = await document_expiry.expiring_on(session, today=today, country=CountryCode.JO)
    assert [(item.driver_id, item.days_left) for item in found] == [(driver["driver_id"], 14)]

    listed = (await client.get("/admin/documents/expiring?country_code=JO&days=30", headers=admin_headers)).json()
    assert [(row["driver_id"], row["days_left"]) for row in listed] == [(str(driver["driver_id"]), 14)]
    assert (await client.get("/admin/documents/expiring?country_code=JO&days=7", headers=admin_headers)).json() == []
