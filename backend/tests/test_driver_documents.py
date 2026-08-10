"""مستندات الكبتن: الرفع والتخزين والمراجعة (SPEC القسم 12/1 و13/2 — المرحلة 9-ب)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.driver import Driver, DriverDocument
from app.models.user import User
from tests.helpers import (
    DRIVER,
    JPEG_BYTES,
    NOT_A_DOCUMENT,
    PDF_BYTES,
    PNG_BYTES,
    SECOND_DRIVER,
    WEBP_BYTES,
    approve_all_documents,
    auth,
    inbox_of,
    register,
    review_document,
    upload_document,
)


async def _driver_row(session_factory, phone: str) -> Driver:
    async with session_factory() as session:
        return await session.scalar(
            select(Driver).join(User, Driver.user_id == User.id).where(
                User.phone == phone
            )
        )


async def _stored_paths(session_factory) -> list[str]:
    async with session_factory() as session:
        return list(await session.scalars(select(DriverDocument.file_path)))


# --------------------------------------------------------------- الرفع


async def test_upload_lists_and_shrinks_what_is_missing(
    client: AsyncClient, session_factory
) -> None:
    body = await register(client, DRIVER)
    headers = auth(body)

    before = (await client.get("/drivers/me/documents", headers=headers)).json()
    assert before["documents"] == []
    assert before["missing_required"] == [
        "driving_license",
        "national_id",
        "vehicle_registration",
    ]

    document = await upload_document(client, headers)
    assert document["review_status"] == "pending"
    assert document["content_type"] == "image/png"
    assert document["size_bytes"] == len(PNG_BYTES)
    # المسار تفصيلُ تخزينٍ داخلي فلا يخرج في أي رد
    assert "file_path" not in document

    listed = (await client.get("/drivers/me/documents", headers=headers)).json()
    assert [d["doc_type"] for d in listed["documents"]] == ["driving_license"]
    # المفقود لا يتغير بالرفع وحده: القبول هو ما يُسقط النوع من القائمة
    assert "driving_license" in listed["missing_required"]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (PNG_BYTES, "image/png"),
        (JPEG_BYTES, "image/jpeg"),
        (PDF_BYTES, "application/pdf"),
        (WEBP_BYTES, "image/webp"),
    ],
)
async def test_type_is_read_from_bytes_not_from_the_client(
    client: AsyncClient, content: bytes, expected: str
) -> None:
    """العميل يقول «PNG» في كل مرة — والخلفية لا تصدّقه.

    `Content-Type` حقلٌ يكتبه العميل؛ قبولُه يعني قبول أي ملفٍ سمّى نفسه صورة.
    """
    headers = auth(await register(client, DRIVER))
    document = await upload_document(
        client,
        headers,
        content=content,
        filename="anything.png",
        content_type="image/png",
    )
    assert document["content_type"] == expected


async def test_a_disguised_script_is_refused(client: AsyncClient) -> None:
    headers = auth(await register(client, DRIVER))
    error = await client.put(
        "/drivers/me/documents/driving_license",
        files={"file": ("license.png", NOT_A_DOCUMENT, "image/png")},
        headers=headers,
    )
    assert error.status_code == 422
    assert error.json()["code"] == "unsupported_document"


async def test_empty_file_is_refused(client: AsyncClient) -> None:
    headers = auth(await register(client, DRIVER))
    error = await client.put(
        "/drivers/me/documents/driving_license",
        files={"file": ("license.png", b"", "image/png")},
        headers=headers,
    )
    assert error.status_code == 422


async def test_size_cap_is_enforced_by_reading_not_by_the_header(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """السقف يُفرض على ما قرأناه فعلاً — و`Content-Length` يكتبه العميل."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "document_max_bytes", 64)
    headers = auth(await register(client, DRIVER))

    too_big = await client.put(
        "/drivers/me/documents/driving_license",
        files={"file": ("license.png", PNG_BYTES + b"\x00" * 128, "image/png")},
        headers=headers,
    )
    assert too_big.status_code == 413
    assert too_big.json()["code"] == "document_too_large"


async def test_client_filename_never_reaches_the_disk(
    client: AsyncClient, session_factory, document_storage: Path
) -> None:
    """اسم الملف من عندنا: لا اجتياز مسار، ولا امتدادٌ يختاره الرافع."""
    headers = auth(await register(client, DRIVER))
    await upload_document(
        client, headers, filename="../../../../etc/passwd.php", content=PNG_BYTES
    )

    (path,) = await _stored_paths(session_factory)
    assert "passwd" not in path
    assert ".." not in path
    assert path.endswith(".png")

    stored = document_storage / path
    assert stored.is_file()
    # وداخل الجذر لا خارجه — والمجلد الفرعي هو مُعرّف الكبتن
    assert stored.resolve().is_relative_to(document_storage.resolve())


async def test_reupload_replaces_and_reopens_the_review(
    client: AsyncClient, admin_headers: dict, session_factory, document_storage: Path
) -> None:
    body = await register(client, DRIVER)
    headers = auth(body)
    driver = await _driver_row(session_factory, "+962792222222")

    first = await upload_document(client, headers)
    await review_document(
        client, admin_headers, driver_id=driver.id, document_id=first["id"]
    )
    (first_path,) = await _stored_paths(session_factory)

    second = await upload_document(client, headers, content=PDF_BYTES)
    # الصفُّ نفسه لا صفٌّ ثانٍ (`uq_driver_documents_driver_doc_type`)
    assert second["id"] == first["id"]
    assert second["review_status"] == "pending"
    assert second["review_note"] is None
    assert second["content_type"] == "application/pdf"

    paths = await _stored_paths(session_factory)
    assert len(paths) == 1 and paths[0] != first_path
    # الملف المُستبدَل يُحذف — **بعد** الـ commit لا قبله
    assert not (document_storage / first_path).exists()
    assert (document_storage / paths[0]).is_file()


# ------------------------------------------------------------- التحميل


async def test_owner_downloads_and_others_get_nothing(
    client: AsyncClient, admin_headers: dict, support_headers: dict, session_factory
) -> None:
    body = await register(client, DRIVER)
    headers = auth(body)
    driver = await _driver_row(session_factory, "+962792222222")
    document = await upload_document(client, headers)

    mine = await client.get(
        f"/drivers/me/documents/{document['id']}/file", headers=headers
    )
    assert mine.status_code == 200
    assert mine.headers["content-type"].startswith("image/png")
    assert mine.headers["x-content-type-options"] == "nosniff"
    assert mine.headers["cache-control"] == "private, no-store"
    assert mine.content == PNG_BYTES

    # كبتنٌ آخر: 404 لا 403 — الجهل بوجود الصف هو الجواب الصحيح
    other = auth(await register(client, SECOND_DRIVER))
    denied = await client.get(
        f"/drivers/me/documents/{document['id']}/file", headers=other
    )
    assert denied.status_code == 404

    # واللوحة تقرأ: المراجعة قراءةٌ فيراها الدعم أيضاً (SPEC القسم 13/8)
    for staff in (admin_headers, support_headers):
        seen = await client.get(
            f"/admin/drivers/{driver.id}/documents/{document['id']}/file",
            headers=staff,
        )
        assert seen.status_code == 200
        assert seen.content == PNG_BYTES

    # ولا يُقرأ مستندٌ عبر مُعرّف كبتنٍ لا يملكه
    async with session_factory() as session:
        stranger = await session.scalar(
            select(Driver).where(Driver.id != driver.id)
        )
    mismatched = await client.get(
        f"/admin/drivers/{stranger.id}/documents/{document['id']}/file",
        headers=admin_headers,
    )
    assert mismatched.status_code == 404


async def test_documents_need_authentication(client: AsyncClient) -> None:
    assert (await client.get("/drivers/me/documents")).status_code == 401


# ------------------------------------------------------------- المراجعة


async def test_approval_notifies_the_driver_and_is_audited(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    body = await register(client, DRIVER)
    headers = auth(body)
    driver = await _driver_row(session_factory, "+962792222222")
    document = await upload_document(client, headers)

    reviewed = await review_document(
        client, admin_headers, driver_id=driver.id, document_id=document["id"]
    )
    assert reviewed["review_status"] == "approved"
    assert reviewed["reviewed_at"] is not None

    entries = await inbox_of(session_factory, body["user"]["id"])
    assert [entry.kind for entry in entries] == ["document_approved"]
    assert entries[0].data["document_id"] == document["id"]

    logs = (
        await client.get(
            "/admin/settings/audit-logs?entity_type=driver_document",
            headers=admin_headers,
        )
    ).json()
    assert logs[0]["details"] == {
        "review_status": "approved",
        "doc_type": "driving_license",
    }


async def test_rejection_carries_its_reason_to_the_driver(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """رفضٌ بلا سبب يترك الكبتن يعيد رفع الصورة نفسها إلى الأبد."""
    body = await register(client, DRIVER)
    headers = auth(body)
    driver = await _driver_row(session_factory, "+962792222222")
    document = await upload_document(client, headers)

    blank = await review_document(
        client,
        admin_headers,
        driver_id=driver.id,
        document_id=document["id"],
        approved=False,
        expect=422,
    )
    assert blank

    reviewed = await review_document(
        client,
        admin_headers,
        driver_id=driver.id,
        document_id=document["id"],
        approved=False,
        note="الصورة غير واضحة",
    )
    assert reviewed["review_status"] == "rejected"
    assert reviewed["review_note"] == "الصورة غير واضحة"

    entries = await inbox_of(session_factory, body["user"]["id"])
    assert entries[0].kind == "document_rejected"
    assert "الصورة غير واضحة" in entries[0].body


async def test_the_same_verdict_twice_is_refused_and_a_change_is_not(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """قرارٌ يُكرَّر ضجيج، وقرارٌ يُصحَّح حق: مشرفٌ ضغط «رفض» خطأً يتراجع."""
    body = await register(client, DRIVER)
    driver = await _driver_row(session_factory, "+962792222222")
    document = await upload_document(client, auth(body))

    await review_document(
        client, admin_headers, driver_id=driver.id, document_id=document["id"]
    )
    again = await review_document(
        client,
        admin_headers,
        driver_id=driver.id,
        document_id=document["id"],
        expect=409,
    )
    assert again["code"] == "conflict"

    changed = await review_document(
        client,
        admin_headers,
        driver_id=driver.id,
        document_id=document["id"],
        approved=False,
        note="تبيّن أنها منتهية",
    )
    assert changed["review_status"] == "rejected"


async def test_review_is_admin_only(
    client: AsyncClient, admin_headers: dict, support_headers: dict, session_factory
) -> None:
    body = await register(client, DRIVER)
    driver = await _driver_row(session_factory, "+962792222222")
    document = await upload_document(client, auth(body))

    await review_document(
        client,
        support_headers,
        driver_id=driver.id,
        document_id=document["id"],
        expect=403,
    )


# ------------------------------------------------- حارس اعتماد الكبتن


async def test_a_driver_is_not_approved_before_his_documents_are(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """«لا يُعتمد الكبتن قبل مراجعة الإدارة للمستندات» (SPEC القسم 12/1)."""
    body = await register(client, DRIVER)
    headers = auth(body)
    driver = await _driver_row(session_factory, "+962792222222")

    empty = await client.post(
        f"/admin/drivers/{driver.id}/approve", headers=admin_headers
    )
    assert empty.status_code == 409
    assert empty.json()["code"] == "documents_incomplete"

    # مستندان من ثلاثة لا يكفيان، والرسالة تسمّي الناقص
    for doc_type in ("driving_license", "national_id"):
        document = await upload_document(client, headers, doc_type=doc_type)
        await review_document(
            client, admin_headers, driver_id=driver.id, document_id=document["id"]
        )
    partial = await client.post(
        f"/admin/drivers/{driver.id}/approve", headers=admin_headers
    )
    assert partial.status_code == 409
    assert "رخصة المركبة والتأمين" in partial.json()["detail"]

    # ومستندٌ مرفوض لا يُحسب مقبولاً
    rejected = await upload_document(
        client, headers, doc_type="vehicle_registration"
    )
    await review_document(
        client,
        admin_headers,
        driver_id=driver.id,
        document_id=rejected["id"],
        approved=False,
        note="منتهية الصلاحية",
    )
    still = await client.post(
        f"/admin/drivers/{driver.id}/approve", headers=admin_headers
    )
    assert still.status_code == 409

    await review_document(
        client, admin_headers, driver_id=driver.id, document_id=rejected["id"]
    )
    approved = await client.post(
        f"/admin/drivers/{driver.id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


async def test_vehicle_photo_is_not_required(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """صورةُ المركبة تُطمئن الراكب ولا تُثبت حقاً — فخارج المطلوب."""
    body = await register(client, DRIVER)
    driver = await _driver_row(session_factory, "+962792222222")
    await approve_all_documents(
        client, auth(body), admin_headers, driver_id=driver.id
    )

    listed = (
        await client.get(
            f"/admin/drivers/{driver.id}/documents", headers=admin_headers
        )
    ).json()
    assert listed["missing_required"] == []
    assert "vehicle_photo" not in [d["doc_type"] for d in listed["documents"]]
