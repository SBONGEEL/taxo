"""**إيقافُ موظّفٍ — للمالك وحدَه** (جردُ اللوحة البند ٤، أمرُ المالك ٢٠٢٦-١١-١٨ السادس).

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**
١) المالكُ يوقف مشرفاً فيُردّ طلبُه التالي، ويعيده فيمرّ — **وصلاحيّاتُه كما كانت**، والقيدُ بالسبب.
٢) **مشرفٌ كاملٌ لا يوقف زميلاً** (العلّةُ الأصليّةُ لـ`_set_blocked` باقية).
٣) **لا يوقف المالكُ نفسَه ولا مالكاً آخر، ولا راكباً من هذا الباب، ولا بلا سبب.**
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.crypto import get_cipher
from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, UserRole
from app.models.totp import UserTotp
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.services import token_service

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("jordan_settings")]


async def _owner(session_factory, name: str = "مالك الاختبار") -> tuple[dict, str]:
    """**مالكٌ بعاملٍ ثانٍ مؤكَّد** — كما يُلزَم (§٨٢-ب/٥)."""
    async with session_factory() as session:
        user = User(
            phone=None, name=name, role=UserRole.ADMIN, country_code=CountryCode.JO,
            role_grants=[UserRoleGrant(role=UserRole.ADMIN), UserRoleGrant(role=UserRole.OWNER)],
        )
        session.add(user)
        await session.flush()
        session.add(UserTotp(
            user_id=user.id, secret_encrypted=get_cipher().encrypt({"secret": "JBSWY3DPEHPK3PXP"}),
            confirmed_at=datetime.now(UTC),
        ))
        await session.commit()
        tokens = await token_service.issue_token_pair(session, user)
        return {"Authorization": f"Bearer {tokens.access_token}"}, str(user.id)


async def _id(client: AsyncClient, headers: dict) -> str:
    return (await client.get("/auth/me", headers=headers)).json()["id"]


async def test_the_owner_suspends_an_admin_who_is_then_refused_and_restores_him_as_he_was(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    owner, _ = await _owner(session_factory)
    admin_id = await _id(client, admin_headers)
    before = next(r for r in (await client.get("/admin/permissions", headers=owner)).json() if r["user_id"] == admin_id)
    assert before["blocked"] is False

    done = await client.post(f"/admin/staff/{admin_id}/suspend", json={"reason": "ترك العمل"}, headers=owner)
    assert done.status_code == 200, done.text
    assert done.json()["blocked"] is True
    assert (await client.get("/admin/users", headers=admin_headers)).status_code in (401, 403)

    back = await client.post(f"/admin/staff/{admin_id}/unsuspend", json={"reason": "عاد إلى العمل"}, headers=owner)
    assert back.status_code == 200, back.text
    assert back.json()["blocked"] is False
    assert back.json()["permissions"] == before["permissions"], "الإعادةُ لا تُرجعه كما كان"
    assert (await client.get("/admin/users", headers=admin_headers)).status_code == 200

    async with session_factory() as session:
        rows = list(await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "staff")))
    assert sorted((row.details or {}).get("reason") for row in rows) == ["ترك العمل", "عاد إلى العمل"]


async def test_a_full_admin_cannot_suspend_a_colleague(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    support_id = await _id(client, support_headers)
    refused = await client.post(f"/admin/staff/{support_id}/suspend", json={"reason": "تجربة"}, headers=admin_headers)
    assert refused.status_code == 403, refused.text
    assert (await client.get("/auth/me", headers=support_headers)).status_code == 200


async def test_the_owner_cannot_suspend_himself_another_owner_a_rider_or_without_a_reason(
    client: AsyncClient, session_factory
) -> None:
    owner, owner_id = await _owner(session_factory)
    _, other_id = await _owner(session_factory, name="مالكٌ ثانٍ")
    async with session_factory() as session:
        rider = User(phone="+962790000555", name="راكب", role=UserRole.RIDER, country_code=CountryCode.JO)
        session.add(rider)
        await session.commit()
        rider_id = str(rider.id)

    for target in (owner_id, other_id, rider_id):
        answer = await client.post(f"/admin/staff/{target}/suspend", json={"reason": "تجربة"}, headers=owner)
        assert answer.status_code == 422, (target, answer.text)
    assert (await client.post(f"/admin/staff/{rider_id}/suspend", json={"reason": ""}, headers=owner)).status_code == 422
    async with session_factory() as session:
        assert not any(u.is_blocked for u in await session.scalars(select(User)))
