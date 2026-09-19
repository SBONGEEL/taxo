"""المحفظةُ تُعلَن بخريطةٍ كاملة — 1-أ/2 (`SPEC-DELIVERY.md` §D6 و§D9.1).

`wallet.owner_type_for` كانت تفحص كلَّ إعلانٍ ليس `rider` بدور الكبتن، فأيُّ غرضٍ
يُضاف كان سيُفحص بدورٍ خاطئ صامتاً. وبابا العرض والكشف في اللوحة يعلنان منذ
§46٫٦ (`test_admin_wallet_side.py`)؛ وبقي بابُ التجميد بلا إعلان — فحاملُ الدورين
لا يُجمَّد من اللوحة أصلاً. والسكوتُ في كلِّ ذلك كما كان.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from app.models.enums import UserRole, WalletOwnerType
from app.models.user_role_grant import UserRoleGrant
from app.services import wallet as wallet_service
from tests.helpers import OTHER_RIDER, rider_session


async def _grant(session_factory, user_id: str, role: UserRole) -> None:
    """صفُّ الدور يُكتب مباشرةً — لا بابَ يمنح دوراً (`test_no_route_grants_a_role`)."""
    async with session_factory() as session:
        session.add(UserRoleGrant(user_id=uuid.UUID(user_id), role=role))
        await session.commit()


def test_every_wallet_type_names_the_role_that_owns_it() -> None:
    """**الخريطةُ كاملةٌ على التعداد** — فمن أضاف غرضاً أضاف دورَه معه."""
    assert set(wallet_service.WALLET_ROLE) == set(WalletOwnerType)


async def test_the_panel_freezes_a_dual_role_account_by_declaring_a_wallet(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """التجميدُ **على الحساب** حتى الخطوة 6 — والإعلانُ يختار المحفظةَ المعروضة."""
    rider = await rider_session(client)
    user_id = rider["user"]["id"]
    await _grant(session_factory, user_id, UserRole.DRIVER)

    frozen = await client.post(
        f"/admin/wallets/{user_id}/freeze",
        params={"wallet": "rider"},
        json={"reason": "اشتباه"},
        headers=admin_headers,
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["owner_type"] == "rider"
    assert frozen.json()["frozen"] is True

    thawed = await client.post(
        f"/admin/wallets/{user_id}/unfreeze",
        params={"wallet": "driver"},
        json={"reason": "زال الاشتباه"},
        headers=admin_headers,
    )
    assert thawed.status_code == 200, thawed.text
    assert thawed.json()["owner_type"] == "driver"
    assert thawed.json()["frozen"] is False


async def test_freezing_without_a_declaration_behaves_as_before(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**السكوتُ كما كان** في الاتجاهين: ذو الدور الواحد يُجمَّد، وذو الدورين يرتدّ."""
    single = await rider_session(client)
    ok = await client.post(
        f"/admin/wallets/{single['user']['id']}/freeze",
        json={"reason": "اشتباه"},
        headers=admin_headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["owner_type"] == "rider"

    dual = await rider_session(client, OTHER_RIDER)
    await _grant(session_factory, dual["user"]["id"], UserRole.DRIVER)
    refused = await client.post(
        f"/admin/wallets/{dual['user']['id']}/freeze",
        json={"reason": "اشتباه"},
        headers=admin_headers,
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "wallet_owner_undecided"
