"""**كلُّ عمودِ ملفٍّ في القائمة الواحدة، والكنسُ يقرؤها** (`services/stored_files.py`، قِيس ٢٠٢٦-١٠-١٤).

كان الكنسُ الأسبوعيُّ يعرف عمودين من عشرة — فكان سيمحو صورَ المستخدمين وأشكالَ المركبات واللافتاتِ ورموزَ QR والإيصالات.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import String, select

from app.core import storage
from app.models.base import Base
from app.models.feedback import AppFeedback
from app.models.user import User
from app.services.stored_files import STORED_FILE_COLUMNS
from tests.helpers import RIDER, auth, real_jpeg, register

pytestmark = pytest.mark.asyncio


def test_every_path_column_is_registered() -> None:
    """**عمودٌ اسمُه `…_path` خارجَ القائمة يُسقط المجموعة** — فعمودُ الملفّ الحادي عشر لا يُنسى كما نُسيت السبعة."""
    registered = {(column.class_.__tablename__, column.key) for column in STORED_FILE_COLUMNS}
    found = {
        (table.name, column.name)
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if column.name.endswith("_path") and isinstance(column.type, String)
    }
    # إثباتُ الصمت: المسحُ يرى ما نعرفه على الأقلّ
    assert len(found) >= 10, found
    missing = sorted(found - registered)
    assert not missing, (
        "أعمدةُ ملفّاتٍ لا يعرفها الكنسُ الأسبوعيّ — **سيمحو ملفّاتِها**:\n  "
        + "\n  ".join(f"{t}.{c}" for t, c in missing)
        + "\n  أضفها إلى `STORED_FILE_COLUMNS` في `services/stored_files.py`."
    )


async def test_the_sweep_keeps_every_registered_file_and_removes_the_stray(
    client: AsyncClient, session_factory, document_storage
) -> None:
    from app.tasks.maintenance import _sweep_orphan_documents

    rider = auth(await register(client, RIDER))
    assert (await client.put("/auth/me/photo", files={"file": ("me.jpg", real_jpeg(), "image/jpeg")}, headers=rider)).status_code == 200
    sent = await client.post(
        "/feedback",
        data={"app": "rider", "message": "مع صورة"},
        files={"screenshot": ("s.jpg", real_jpeg((10, 200, 10)), "image/jpeg")},
        headers=rider,
    )
    assert sent.status_code == 201, sent.text
    stray = document_storage / "00000000000000000000000000000000" / "stray.bin"
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"orphan")

    async with session_factory() as session:
        photo = await session.scalar(select(User.photo_path).where(User.photo_path.is_not(None)))
        shot = await session.scalar(select(AppFeedback.screenshot_path))

    removed = await _sweep_orphan_documents()

    assert removed == "1"
    assert not stray.exists()
    root = storage.root().resolve()
    assert (root / photo).is_file(), "صورةُ المستخدم مُحيت — والكنسُ لا يعرف عمودَها"
    assert (root / shot).is_file(), "صورةُ الملاحظة مُحيت — والكنسُ لا يعرف عمودَها"
