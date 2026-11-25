"""«قبول جميع الوثائق» و«اعتماد كامل» وإشعارُ «أكمل وثائقه» (أمرُ المالك الحادي عشر ٢٠٢٦-١١-٢٥).

**العطبُ الذي بُنيت له**: كبتنٌ «معتمدٌ دون وثائق» رفع بقيّةَ وثائقه، واللوحةُ تقول «لا وثيقة مطلوبة ناقصة» — **ولا زرَّ لإكمال
اعتماده**: الاعتمادُ العاديُّ لا يُعرض لمعتمَد، فلم يبقَ إلا «تجميد» و«تمديد»، ووسمُه ومهلتُه وتذكيراتُه باقية.

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**
١) **«قبول جميع الوثائق» يقبل ما عُرض وحدَه** — المرفوضةُ تبقى مرفوضة، والمرفوعةُ بعد العرض تبقى منتظِرة، وتُسمّى كلُّها في `remaining`؛
   **ولا يعتمد الحساب**؛ وقيدُ تدقيقٍ جامعٌ باسم المشرف وقائمة الوثائق.
٢) **رفعُ آخر وثيقةٍ مطلوبة يُشعر المشرفين** («كبتنٌ أكمل وثائقه — يحتاج مراجعة»)، ورفعُ ما قبلها لا.
٣) **«اعتماد كامل»** يرفض ما لم تُقبل وثائقُه المطلوبة ويسمّيها، ثمّ يزيل الوسمَ والمهلةَ والتذكيرات ويُدقَّق باسم المشرف،
   **والدورةُ اليوميّة لا تجمّده بعدها** ولو مضى موعدُ مهلته القديمة.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.redis_client import get_redis_client
from app.models.admin_alert import AdminAlert
from app.models.audit import AdminAuditLog
from app.models.driver import Driver, DriverDocument
from app.models.enums import DocumentReviewStatus, DocumentType, DriverStatus
from app.services import admin_alerts, alert_capture, documents, exceptional_approval
from tests.conftest import _staff_headers
from tests.helpers import DRIVER, auth, register, upload_document

pytestmark = pytest.mark.asyncio

LAST = DocumentType.DRIVING_LICENSE


async def _pending_driver(client: AsyncClient, session_factory) -> dict:
    body = await register(client, DRIVER)
    async with session_factory() as session:
        driver = await session.scalar(select(Driver).where(Driver.user_id == uuid.UUID(body["user"]["id"])))
        required = list(await documents.required_for(session, driver.id))
    assert LAST in required
    return {"headers": auth(body), "driver_id": driver.id, "required": required}


async def _insert(session_factory, driver_id, doc_type: DocumentType, status: DocumentReviewStatus) -> uuid.UUID:
    async with session_factory() as session:
        row = DriverDocument(
            driver_id=driver_id, doc_type=doc_type, file_path=f"test/{doc_type.value}.jpg",
            content_type="image/jpeg", size_bytes=10, review_status=status,
        )
        session.add(row)
        await session.commit()
        return row.id


async def _alerts(session_factory) -> list[str]:
    await alert_capture.settle()
    async with session_factory() as session:
        await admin_alerts.drain(session, get_redis_client(), push=False)
    async with session_factory() as session:
        kinds = sorted(await session.scalars(select(AdminAlert.kind)))
        await session.execute(delete(AdminAlert))
        await session.commit()
    return kinds


async def _manager(client: AsyncClient, admin_headers: dict) -> dict:
    headers = await _staff_headers("admin", "+962790000093", "مدير الاعتماد")
    me = (await client.get("/auth/me", headers=headers)).json()
    rows = (await client.get("/admin/permissions", headers=admin_headers)).json()
    row = next(item for item in rows if item["user_id"] == me["id"])
    granted = await client.put(
        f"/admin/permissions/{me['id']}",
        json={"permissions": sorted(set(row["permissions"]) | {"drivers.exceptional"})},
        headers=admin_headers,
    )
    assert granted.status_code == 200, granted.text
    return {"headers": headers}


async def _audit(session_factory, entity_type: str) -> list[AdminAuditLog]:
    async with session_factory() as session:
        return list(await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == entity_type)))


async def test_accept_all_takes_what_was_shown_names_what_remains_and_does_not_approve(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    driver = await _pending_driver(client, session_factory)
    others = [item for item in driver["required"] if item is not LAST]
    rejected_type = others[0]
    rejected = await _insert(session_factory, driver["driver_id"], rejected_type, DocumentReviewStatus.REJECTED)
    shown = [await _insert(session_factory, driver["driver_id"], item, DocumentReviewStatus.PENDING) for item in others[1:]]
    # **رُفعت بعد أن عرض التأكيدُ قائمتَه** — فلا تُقبل بلا نظر
    late = (await upload_document(client, driver["headers"], doc_type=LAST.value))["id"]

    answer = await client.post(
        f"/admin/drivers/{driver['driver_id']}/documents/accept-all",
        json={"document_ids": [str(item) for item in shown]},
        headers=admin_headers,
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert sorted(item["id"] for item in body["accepted"]) == sorted(str(item) for item in shown)
    assert any(documents.label_for(rejected_type) in text and "مرفوضة" in text for text in body["remaining"]), body
    assert any(documents.label_for(LAST) in text and "بعد العرض" in text for text in body["remaining"]), body

    async with session_factory() as session:
        statuses = {
            row.id: row.review_status
            for row in await session.scalars(select(DriverDocument).where(DriverDocument.driver_id == driver["driver_id"]))
        }
        assert statuses[rejected] is DocumentReviewStatus.REJECTED
        assert statuses[uuid.UUID(late)] is DocumentReviewStatus.PENDING
        assert all(statuses[item] is DocumentReviewStatus.APPROVED for item in shown)
        # **يَسِم الوثائقَ ولا يعتمد الحساب** — الاعتمادُ قرارٌ منفصل
        assert (await session.get(Driver, driver["driver_id"])).status is DriverStatus.PENDING

    [entry] = await _audit(session_factory, "driver_documents_accept_all")
    me = (await client.get("/auth/me", headers=admin_headers)).json()
    assert str(entry.actor_id) == me["id"]
    assert sorted(entry.details["accepted"]) == sorted(item.value for item in others[1:])
    assert rejected_type.value in entry.details["remaining"] and LAST.value in entry.details["remaining"]


async def test_the_last_required_upload_alerts_the_admins_and_full_approval_clears_the_mark(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    manager = await _manager(client, admin_headers)
    driver = await _pending_driver(client, session_factory)
    approved = await client.post(
        f"/admin/drivers/{driver['driver_id']}/approve-exceptional",
        json={"reason": "سائقٌ معروف، وثائقه قيد الاستخراج"},
        headers=manager["headers"],
    )
    assert approved.status_code == 200, approved.text
    await _alerts(session_factory)

    # **ليس كاملاً بعد**: «اعتماد كامل» يرفض ويسمّي، والوسمُ باقٍ
    early = await client.post(f"/admin/drivers/{driver['driver_id']}/complete-approval", headers=admin_headers)
    assert early.status_code == 409, early.text

    for item in driver["required"]:
        if item is not LAST:
            await _insert(session_factory, driver["driver_id"], item, DocumentReviewStatus.PENDING)
    assert "documents_completed" not in await _alerts(session_factory)
    await upload_document(client, driver["headers"], doc_type=LAST.value)
    # **الرفعُ لا يُسقط اعتمادَه** — ويصل المشرفين «أكمل وثائقه»
    assert "documents_completed" in await _alerts(session_factory)

    state = (await client.get(f"/admin/drivers/{driver['driver_id']}/exceptional", headers=admin_headers)).json()
    assert state["status"] == "approved" and state["exceptional"] is True
    assert state["awaiting_upload"] == [] and state["missing_documents"], state
    refused = await client.post(f"/admin/drivers/{driver['driver_id']}/complete-approval", headers=admin_headers)
    assert refused.status_code == 409 and "لم تُقبل" in refused.text, refused.text

    listed = (await client.get(f"/admin/drivers/{driver['driver_id']}/documents", headers=admin_headers)).json()
    pending = [item["id"] for item in listed["documents"] if item["review_status"] == "pending"]
    accepted = await client.post(
        f"/admin/drivers/{driver['driver_id']}/documents/accept-all", json={"document_ids": pending}, headers=admin_headers
    )
    assert accepted.status_code == 200 and accepted.json()["remaining"] == [], accepted.text

    done = await client.post(f"/admin/drivers/{driver['driver_id']}/complete-approval", headers=admin_headers)
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["exceptional"] is False and body["deadline_at"] is None and body["reminders_enabled"] is False
    assert body["status"] == "approved" and body["missing_documents"] == []
    [entry] = await _audit(session_factory, "driver_full_approval")
    me = (await client.get("/auth/me", headers=admin_headers)).json()
    assert str(entry.actor_id) == me["id"] and entry.details["cancelled_deadline"]

    # **لا تجميدَ آليّاً معلَّق**: الدورةُ بعد موعد المهلة القديمة لا تمسّه
    async with session_factory() as session:
        counts = await exceptional_approval.sweep(session, get_redis_client(), now=datetime.now(UTC) + timedelta(days=400))
        assert counts["frozen"] == 0
        assert (await session.get(Driver, driver["driver_id"])).status is DriverStatus.APPROVED

    # **ومرّةً ثانيةً لا معنى لها** — لم يعد موسوماً
    again = await client.post(f"/admin/drivers/{driver['driver_id']}/complete-approval", headers=admin_headers)
    assert again.status_code == 422, again.text
