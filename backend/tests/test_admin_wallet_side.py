"""محفظةُ حاملِ الدورين في اللوحة — **الإعلانُ يفتحها، وغيابُه يرتدّ** (§46٫٦).

## العطبُ الذي يقيسه هذا الملفّ

**درجُ الملفِّ الشخصيّ كان ينادي `GET /admin/wallets/{id}` بلا إعلان أيِّ
محفظة**، **فحسابٌ يحمل الدورين يرتدّ `409 wallet_owner_undecided`** وتبقى
بطاقةُ المحفظة على دوّارةٍ أبداً. **والخلفيةُ كانت مُحقّة** — «كودٌ لكلِّ
موضع» من نموذج الأدوار (§21/§22)، **والناقصُ إعلانُ الجانب في نداء اللوحة**.

## وثلاثةٌ تُقاس، والأولى هي الشرط

1. **أن غيابَ الإعلان يبقى ٤٠٩ لحاملِ الدورين** — **فالإضافةُ اختياريةٌ لا
   تبديلُ سلوك**، ومن نادى بلا `wallet` يجد ما كان يجده حرفاً.
2. **وأن الإعلانَ يفتحها**، والبطاقةُ تعود بنوع المحفظة المعلَنة لا بغيرها.
3. **وأن الدفترَ يعلن جانبَه كما تعلنه البطاقة**: **سطحان لشيءٍ واحد**،
   وإعلانُ أحدهما دون الآخر يعرض رصيدَ محفظةٍ فوق دفترِ الأخرى — **وهو أسوأُ
   من ٤٠٩** لأنه يُقرأ صحيحاً.

**ولا يُقاس هذا بحسابِ دورٍ واحد**: صاحبُ الدور الواحد يمرّ بلا إعلانٍ أصلاً،
**فاختبارٌ عليه يخضرّ والعطبُ قائم**.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import UserRole
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from tests.helpers import DRIVER, approved_driver, rider_session


async def _dual_role(client: AsyncClient, session_factory) -> str:
    """حسابُ كبتنٍ يحمل دورَ الراكب أيضاً — **كما يقع في السوق حقّاً**.

    **والدورُ يُضاف على الحساب نفسِه** لا بحسابٍ ثانٍ: نموذجُ الأدوار مجموعةٌ
    على المستخدم (§21)، **وحسابان مختلفان لا يعيدان إنتاج العطب**.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    async with session_factory() as session:
        user = await session.scalar(
            select(User).where(User.id == uuid.UUID(driver["user_id"]))
        )
        # **والدورُ يُمنح صفّاً في `user_role_grants`** — `User.roles` خاصّيةٌ
        # مشتقّةٌ بلا واضع، **والمجموعةُ مصدرُها المنحُ لا عمودٌ يُكتب**
        if not user.has_role(UserRole.RIDER):
            session.add(UserRoleGrant(user_id=user.id, role=UserRole.RIDER))
        await session.commit()
    return driver["user_id"]


async def test_without_a_declaration_a_dual_role_wallet_still_refuses(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**النداءُ بلا `wallet` يبقى كما كان** — والإضافةُ اختياريةٌ لا تبديل."""
    user_id = await _dual_role(client, session_factory)

    answer = await client.get(f"/admin/wallets/{user_id}", headers=admin_headers)
    assert answer.status_code == 409, answer.text
    assert answer.json()["code"] == "wallet_owner_undecided"


@pytest.mark.parametrize("side", ["driver", "rider"])
async def test_a_declaration_opens_the_wallet_it_names(
    client: AsyncClient, session_factory, admin_headers: dict, side: str
) -> None:
    """**والإعلانُ يفتحها، وبنوعها هي لا بغيره.**"""
    user_id = await _dual_role(client, session_factory)

    answer = await client.get(
        f"/admin/wallets/{user_id}", params={"wallet": side}, headers=admin_headers
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["owner_type"] == side
    assert body["owner_id"] == user_id


@pytest.mark.parametrize("side", ["driver", "rider"])
async def test_the_ledger_declares_the_same_side_as_the_card(
    client: AsyncClient, session_factory, admin_headers: dict, side: str
) -> None:
    """**سطحان لشيءٍ واحد** — وإعلانُ أحدهما دون الآخر يعرض رصيداً فوق دفترٍ
    ليس له. **وهذا أسوأُ من ٤٠٩** لأنه يُقرأ صحيحاً."""
    user_id = await _dual_role(client, session_factory)

    bare = await client.get(
        f"/admin/wallets/{user_id}/transactions", headers=admin_headers
    )
    assert bare.status_code == 409, bare.text

    declared = await client.get(
        f"/admin/wallets/{user_id}/transactions",
        params={"wallet": side},
        headers=admin_headers,
    )
    assert declared.status_code == 200, declared.text
    assert isinstance(declared.json(), list)


async def test_a_single_role_account_needs_no_declaration(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**ولا يُطالَب صاحبُ الدور الواحد بما لا معنى له** — وهو ما يجعل
    المُعامِلَ اختيارياً لا مطلوباً."""
    rider = await rider_session(client)

    answer = await client.get(
        f"/admin/wallets/{rider['user']['id']}", headers=admin_headers
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["owner_type"] == "rider"


async def test_declaring_a_wallet_the_account_does_not_own_is_refused(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**والإعلانُ لا يمنح شيئاً**: راكبٌ يُعلَن كبتناً يُرفض — يُفحص أن صاحبَه
    يملك دورَ تلك المحفظة."""
    rider = await rider_session(client)

    answer = await client.get(
        f"/admin/wallets/{rider['user']['id']}",
        params={"wallet": "driver"},
        headers=admin_headers,
    )
    assert answer.status_code == 403, answer.text
