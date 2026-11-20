"""**صورةُ الملفّ** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-هـ).

* **الكبتنُ يغيّر صورتَه ولا يُسقَط اعتمادُه**: الجديدةُ تنتظر المراجعة، **والمعتمَدةُ السابقةُ باقيةٌ للركّاب** حتى تُعتمد — والرفضُ يُبقيها.
* **الذكرُ لا يحذف صورتَه، والمُعفاةُ (أنثى بختم الإدارة) تحذفها.**
* **ولا EXIF يُخزَّن** — إحداثيّاتُ مكان الالتقاط تسقط بإعادة الترميز في الخادم، للراكب والكبتن.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select

from app.core import storage
from app.core.exceptions import DocumentFileMissing
from app.models.driver import Driver, DriverDocument
from app.models.enums import DocumentType
from app.models.user import User
from app.services import documents as documents_service
from tests.helpers import DRIVER, approved_driver, real_jpeg, review_document, rider_session, upload_document


def _jpeg_with_exif(colour: tuple[int, int, int] = (10, 120, 200)) -> bytes:
    """صورةٌ حقيقيّةٌ تحمل EXIF — صانعُ الهاتف واتّجاهُه، **كما تحمل الإحداثيّاتِ صورةُ الهاتف الحقيقيّة**."""
    image = Image.new("RGB", (80, 60), colour)
    exif = Image.Exif()
    exif[0x010F] = "TestPhoneMaker"  # Make
    exif[0x0112] = 1  # Orientation
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())
    data = buffer.getvalue()
    assert Image.open(io.BytesIO(data)).getexif(), "العيّنةُ بلا EXIF — الاختبارُ أعمى"
    return data


def _exists(relative_path: str) -> bool:
    """`storage.resolve` يرفع لملفٍّ غائب — فالغيابُ استثناءٌ لا `False`."""
    try:
        return storage.resolve(relative_path).exists()
    except DocumentFileMissing:
        return False


def _exif_of(relative_path: str) -> dict:
    with Image.open(storage.resolve(relative_path)) as opened:
        return dict(opened.getexif())


async def _visible(session_factory, driver_id) -> str | None:
    async with session_factory() as session:
        return await documents_service.visible_photo_path(session, uuid.UUID(str(driver_id)))


async def _photo_row(session_factory, driver_id) -> DriverDocument | None:
    async with session_factory() as session:
        return await session.scalar(
            select(DriverDocument).where(
                DriverDocument.driver_id == uuid.UUID(str(driver_id)),
                DriverDocument.doc_type == DocumentType.PROFILE_PHOTO,
            )
        )


async def _approved_with_photo(client, admin_headers, session_factory, payload=DRIVER) -> tuple[dict, str]:
    driver = await approved_driver(client, session_factory, payload)
    first = await upload_document(
        client, driver["headers"], doc_type="profile_photo", content=real_jpeg((200, 40, 40)), filename="a.jpg"
    )
    await review_document(client, admin_headers, driver_id=driver["driver_id"], document_id=first["id"])
    path = await _visible(session_factory, driver["driver_id"])
    assert path is not None
    return driver, path


async def test_a_changed_photo_waits_and_the_old_one_stays_with_riders(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None
) -> None:
    driver, old_path = await _approved_with_photo(client, admin_headers, session_factory)

    changed = await upload_document(
        client, driver["headers"], doc_type="profile_photo", content=real_jpeg((40, 200, 40)),
        filename="b.jpg", envelope=True,
    )
    # **لا يُسقَط اعتمادُه** — والقديمةُ ما زالت ما يراه الركّاب
    assert changed["approval_reverted"] is False
    assert changed["driver_status"] == "approved"
    assert changed["document"]["review_status"] == "pending"
    assert await _visible(session_factory, driver["driver_id"]) == old_path
    assert _exists(old_path)
    # وصاحبُها يرى ما يراه الركّاب
    mine = await client.get("/drivers/me/photo", headers=driver["headers"])
    assert mine.status_code == 200
    assert mine.content == storage.resolve(old_path).read_bytes()

    # **تُعتمد ⇐ تتقاعد القديمةُ وملفُّها**
    await review_document(client, admin_headers, driver_id=driver["driver_id"], document_id=changed["document"]["id"])
    new_path = await _visible(session_factory, driver["driver_id"])
    assert new_path is not None and new_path != old_path
    assert not _exists(old_path)
    row = await _photo_row(session_factory, driver["driver_id"])
    assert row is not None and row.live_file_path is None


async def test_a_rejected_change_keeps_the_approved_photo(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None
) -> None:
    driver, old_path = await _approved_with_photo(client, admin_headers, session_factory)
    changed = await upload_document(
        client, driver["headers"], doc_type="profile_photo", content=real_jpeg((40, 40, 200)), filename="c.jpg"
    )
    await review_document(
        client, admin_headers, driver_id=driver["driver_id"], document_id=changed["id"], approved=False,
        note="الوجهُ غيرُ واضح",
    )
    assert await _visible(session_factory, driver["driver_id"]) == old_path

    # **وتغييرٌ ثانٍ قبل المراجعة يحلّ محلَّ المعلَّقة لا المعتمَدة**
    again = await upload_document(
        client, driver["headers"], doc_type="profile_photo", content=real_jpeg((90, 90, 90)), filename="d.jpg"
    )
    assert again["review_status"] == "pending"
    assert await _visible(session_factory, driver["driver_id"]) == old_path
    assert _exists(old_path)


async def test_a_male_driver_cannot_delete_his_photo(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None
) -> None:
    driver, old_path = await _approved_with_photo(client, admin_headers, session_factory)
    refused = await client.delete("/drivers/me/photo", headers=driver["headers"])
    assert refused.status_code == 409, refused.text
    assert await _visible(session_factory, driver["driver_id"]) == old_path


async def test_a_stamped_female_driver_can_delete_hers(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None
) -> None:
    driver, old_path = await _approved_with_photo(client, admin_headers, session_factory)
    async with session_factory() as session:
        user = await session.scalar(
            select(User).join(Driver, Driver.user_id == User.id).where(Driver.id == uuid.UUID(str(driver["driver_id"])))
        )
        user.gender = "female"
        user.gender_verified_at = datetime.now(UTC)
        await session.commit()

    deleted = await client.delete("/drivers/me/photo", headers=driver["headers"])
    assert deleted.status_code == 204, deleted.text
    assert await _photo_row(session_factory, driver["driver_id"]) is None
    assert not _exists(old_path)
    assert (await client.get("/drivers/me/photo", headers=driver["headers"])).status_code == 404


async def test_driver_photo_is_stored_without_exif(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    await upload_document(
        client, driver["headers"], doc_type="profile_photo", content=_jpeg_with_exif(), filename="gps.jpg"
    )
    row = await _photo_row(session_factory, driver["driver_id"])
    assert row is not None
    assert _exif_of(row.file_path) == {}


async def test_rider_photo_is_stored_without_exif_and_readable_by_its_owner(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    rider = await rider_session(client)
    put = await client.put(
        "/auth/me/photo", files={"file": ("gps.jpg", _jpeg_with_exif(), "image/jpeg")}, headers=rider["headers"]
    )
    assert put.status_code == 200, put.text
    async with session_factory() as session:
        path = await session.scalar(select(User.photo_path).where(User.id == uuid.UUID(str(rider["user"]["id"]))))
    assert path is not None
    assert _exif_of(path) == {}

    mine = await client.get("/auth/me/photo", headers=rider["headers"])
    assert mine.status_code == 200
    assert mine.content == storage.resolve(path).read_bytes()

    assert (await client.delete("/auth/me/photo", headers=rider["headers"])).status_code == 200
    assert (await client.get("/auth/me/photo", headers=rider["headers"])).status_code == 404
