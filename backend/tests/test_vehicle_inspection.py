"""§٦١-ط/٥: فحصُ المركبة — موعدٌ يضعه المشرفُ ويراه الكبتن، **ولا يشترطه الاعتماد**.

**ما يُقاس**: الأبوابُ الثلاثة تكتب ما تقول وتُدقَّق · الكبتنُ يرى موعدَه في ملفّه **ويصله إشعار** · موعدٌ جديدٌ يُسقط اجتيازاً سابقاً ·
**موعدٌ بلا منطقةٍ زمنيةٍ يُردّ** · **ولا يملكها إلا مديرُ المستخدمين** · **والاعتمادُ لا ينتظرها** (مسارُه القائمُ كما هو).
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from tests.helpers import approved_driver, inbox_of

AT = "2026-10-12T10:30:00+03:00"


async def _schedule(client: AsyncClient, headers: dict, driver_id, place: str = "مركز الفحص — ماركا") -> dict:
    response = await client.put(
        f"/admin/drivers/{driver_id}/inspection", json={"at": AT, "place": place}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_captain_sees_the_appointment_and_is_told(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory)
    body = await _schedule(client, admin_headers, driver["driver_id"])
    assert body["inspection_place"] == "مركز الفحص — ماركا"
    assert body["inspection_passed_at"] is None

    profile = (await client.get("/drivers/me", headers=driver["headers"])).json()["driver"]
    assert profile["inspection_at"] is not None
    assert profile["inspection_place"] == "مركز الفحص — ماركا"

    kinds = [row.kind for row in await inbox_of(session_factory, driver["user_id"])]
    assert "inspection_scheduled" in kinds


async def test_every_door_is_audited(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    from app.models.audit import AdminAuditLog

    driver = await approved_driver(client, session_factory)
    driver_id = driver["driver_id"]
    await _schedule(client, admin_headers, driver_id)
    assert (await client.post(f"/admin/drivers/{driver_id}/inspection/pass", headers=admin_headers)).status_code == 200
    assert (await client.delete(f"/admin/drivers/{driver_id}/inspection", headers=admin_headers)).status_code == 200

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_id == uuid.UUID(str(driver_id)),
                    AdminAuditLog.entity_type == "driver",
                )
            )
        ).all()
    inspections = [row for row in rows if (row.details or {}).get("inspection")]
    assert len(inspections) == 3, [row.details for row in rows]


async def test_a_new_appointment_drops_a_previous_pass_and_clearing_resets_everything(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory)
    driver_id = driver["driver_id"]
    await _schedule(client, admin_headers, driver_id)
    passed = (await client.post(f"/admin/drivers/{driver_id}/inspection/pass", headers=admin_headers)).json()
    assert passed["inspection_passed_at"] is not None

    # **فحصٌ يُعاد يُقرأ من جديد**
    again = await _schedule(client, admin_headers, driver_id, place="مركز الفحص — الزرقاء")
    assert again["inspection_passed_at"] is None
    assert again["inspection_place"] == "مركز الفحص — الزرقاء"

    cleared = (await client.delete(f"/admin/drivers/{driver_id}/inspection", headers=admin_headers)).json()
    assert (cleared["inspection_at"], cleared["inspection_place"], cleared["inspection_passed_at"]) == (None, None, None)


async def test_a_time_without_a_zone_is_refused(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory)
    response = await client.put(
        f"/admin/drivers/{driver['driver_id']}/inspection",
        json={"at": "2026-10-12T10:30:00", "place": "ماركا"},
        headers=admin_headers,
    )
    assert response.status_code == 422, response.text


async def test_only_a_users_manager_sets_it(
    client: AsyncClient, jordan_settings: None, session_factory, support_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory)
    driver_id = driver["driver_id"]
    for call in (
        client.put(f"/admin/drivers/{driver_id}/inspection", json={"at": AT, "place": "ماركا"}, headers=support_headers),
        client.post(f"/admin/drivers/{driver_id}/inspection/pass", headers=support_headers),
        client.delete(f"/admin/drivers/{driver_id}/inspection", headers=support_headers),
        # **والكبتنُ لا يضع موعدَه لنفسه**
        client.put(f"/admin/drivers/{driver_id}/inspection", json={"at": AT, "place": "ماركا"}, headers=driver["headers"]),
    ):
        assert (await call).status_code == 403


async def test_approval_does_not_wait_for_an_inspection(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**مسارُ الاعتماد القائمُ كما هو** (§٦١-و/٢-أ): كبتنٌ بلا موعدٍ ولا اجتيازٍ يُعتمد كما كان."""
    driver = await approved_driver(client, session_factory)
    profile = (await client.get("/drivers/me", headers=driver["headers"])).json()["driver"]
    assert profile["status"] == "approved"
    assert (profile["inspection_at"], profile["inspection_passed_at"]) == (None, None)
