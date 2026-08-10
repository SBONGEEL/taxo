"""الحسابات في اللوحة: الوسم والفلترة واعتماد الكباتن (SPEC القسم 13.2/13.3)."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.driver import Driver
from app.models.user import User
from tests.helpers import DRIVER, RIDER, register
from tests.test_phone_verification import _set_verification_flag


async def _driver_id(session_factory, phone: str) -> str:
    async with session_factory() as session:
        driver = await session.scalar(
            select(Driver).join(User, Driver.user_id == User.id).where(
                User.phone == phone
            )
        )
    return str(driver.id)


async def test_users_listing_is_staff_only(
    client: AsyncClient, support_headers: dict
) -> None:
    """الدعم يقرأ (القسم 13/8) — والقائمة قراءة."""
    assert (
        await client.get("/admin/users", headers=support_headers)
    ).status_code == 200
    assert (await client.get("/admin/users")).status_code == 401


async def test_unverified_accounts_are_flagged_and_filterable(
    client: AsyncClient, admin_headers: dict
) -> None:
    """لا تُعالَج الحالة الاستثنائية إن لم تُرَ (المرحلة 8-ب)."""
    await register(client, RIDER)

    await _set_verification_flag(client, admin_headers, False, reason="عطل مؤقت")
    unverified = await client.post(
        "/auth/register",
        json={
            "phone": "0799999999",
            "name": "راكب بلا تحقق",
            "password": "SuperSecret123",
            "country_code": "JO",
            "role": "rider",
        },
    )
    assert unverified.status_code == 201

    # `role=rider` يستثني حسابات الموظفين: تُنشأ من اللوحة لا بالتسجيل الذاتي،
    # فرقمُها غير مُثبَت بهذا المعنى — وظهورُها في الفلتر صحيحٌ لا خطأ
    listed = (
        await client.get(
            "/admin/users?phone_verified=false&role=rider", headers=admin_headers
        )
    ).json()
    assert [row["phone"] for row in listed] == ["+962799999999"]
    assert listed[0]["phone_verified"] is False

    verified = (
        await client.get(
            "/admin/users?phone_verified=true&role=rider", headers=admin_headers
        )
    ).json()
    assert [row["phone"] for row in verified] == [RIDER["phone"].replace("07", "+9627")]


async def test_driver_approval_requires_a_verified_phone(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**لا يعفيه إطفاء المفتاح**: رقم الكبتن يستلم عليه حوالات كليك."""
    await _set_verification_flag(client, admin_headers, False, reason="عطل مؤقت")
    body = await client.post(
        "/auth/register",
        json={
            "phone": "0791111222",
            "name": "كبتن بلا تحقق",
            "password": "SuperSecret123",
            "country_code": "JO",
            "role": "driver",
        },
    )
    assert body.status_code == 201
    driver_id = await _driver_id(session_factory, "+962791111222")

    denied = await client.post(
        f"/admin/drivers/{driver_id}/approve", headers=admin_headers
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "phone_not_verified"

    # وبعد أن يُثبت رقمه يمر الاعتماد
    from app.services.firebase_auth import mock_token

    headers = {"Authorization": f"Bearer {body.json()['tokens']['access_token']}"}
    await _set_verification_flag(client, admin_headers, True)
    verified = await client.post(
        "/auth/me/verify-phone",
        json={"verification_token": mock_token("+962791111222")},
        headers=headers,
    )
    assert verified.status_code == 200

    approved = await client.post(
        f"/admin/drivers/{driver_id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


async def test_verified_driver_is_approved_and_audited(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    await register(client, DRIVER)
    driver_id = await _driver_id(session_factory, "+962792222222")

    approved = await client.post(
        f"/admin/drivers/{driver_id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    logs = (
        await client.get(
            "/admin/settings/audit-logs?entity_type=driver", headers=admin_headers
        )
    ).json()
    assert logs[0]["details"]["status"] == "approved"


async def test_rejecting_a_driver_needs_no_verification(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """الرفض لا يُرسل مالاً إلى أحد — فلا يشترط ما يشترطه الاعتماد."""
    await _set_verification_flag(client, admin_headers, False, reason="عطل مؤقت")
    await client.post(
        "/auth/register",
        json={
            "phone": "0791111333",
            "name": "كبتن مرفوض",
            "password": "SuperSecret123",
            "country_code": "JO",
            "role": "driver",
        },
    )
    driver_id = await _driver_id(session_factory, "+962791111333")

    rejected = await client.post(
        f"/admin/drivers/{driver_id}/reject", headers=admin_headers
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


async def test_approval_is_admin_only(
    client: AsyncClient, admin_headers: dict, support_headers: dict, session_factory
) -> None:
    await register(client, DRIVER)
    driver_id = await _driver_id(session_factory, "+962792222222")

    denied = await client.post(
        f"/admin/drivers/{driver_id}/approve", headers=support_headers
    )
    assert denied.status_code == 403
