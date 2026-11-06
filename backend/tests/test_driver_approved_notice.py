"""**اعتمادُ الكبتن يُبلغه** (أمرُ المالك ٢٠٢٦-١١-٠٦) — شاشةُ الانتظار تقول «سيصلك إشعار عند اعتماد الحساب».

**ما يُقاس**: الاعتمادُ من اللوحة يكتب صفّاً في صندوق الكبتن بنوع `driver_approved` · **وضغطةٌ ثانيةٌ لا تكتب ثانياً**.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from tests.helpers import approve_all_documents, approved_driver, inbox_of


async def test_approval_reaches_the_captain_once(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    from app.models.driver import Driver
    from app.models.enums import DriverStatus

    driver = await approved_driver(client, session_factory)
    async with session_factory() as session:
        row = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
        row.status = DriverStatus.PENDING
        await session.commit()
    await approve_all_documents(client, driver["headers"], admin_headers, driver_id=driver["driver_id"])

    first = await client.post(f"/admin/drivers/{driver['driver_id']}/approve", headers=admin_headers)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "approved"
    again = await client.post(f"/admin/drivers/{driver['driver_id']}/approve", headers=admin_headers)
    assert again.status_code == 200, again.text

    kinds = [row.kind for row in await inbox_of(session_factory, driver["user_id"])]
    assert kinds.count("driver_approved") == 1
