"""حساباتُ التجربة في كلِّ سوق ومالُها (SPEC §٧٤-أ/١٠).

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**
١) **المُختارُ لحساب التجربة وحدَه**: أسواقُ إخوته بحالها، والدخولُ إلى أخيه بجلسةٍ جديدة — **وسوقُ الجلسة الجديدة سوقُ الأخ** (العملةُ تتبعه).
٢) **ولغيره لا شيء**: القائمةُ فارغة، والدخولُ يُردّ.
٣) **رصيدُ التجربة يُكمَّل إلى مبلغ سوقه ولا يتجاوزه**، بقيدٍ موسومٍ «رصيد تجريبي» — **وبصلاحية المالك وحدَه**.
٤) **ومالُ التجربة لا يغادر**: السحبُ والتحويلُ مغلقان عليه.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, WalletOwnerType, WalletTransactionType
from app.models.user import User
from app.models.wallet import WalletTransaction
from tests.conftest import _signup
from tests.helpers import RIDER, auth, register, rider_session
from tests.test_markets import markets_owner

pytestmark = pytest.mark.asyncio


async def _family(client: AsyncClient, session_factory) -> dict[str, dict]:
    """**راكبُ تجربةٍ أردنيّ وتوأماه** — تُنشأ بالتسجيل ثمّ تُوسَم وتُربط كما يفعل السكربت."""
    jordan = await register(client, _signup("0710000661", "Aldeeb", "JO", "rider"))
    libya = await register(client, _signup("0990000661", "Aldeeb", "LY", "rider"))
    algeria = await register(client, _signup("0599000661", "Aldeeb", "DZ", "rider"))
    primary = jordan["user"]["id"]
    async with session_factory() as session:
        await session.execute(update(User).where(User.id.in_([primary, libya["user"]["id"], algeria["user"]["id"]])).values(is_test=True))
        await session.execute(update(User).where(User.id.in_([libya["user"]["id"], algeria["user"]["id"]])).values(test_twin_of=primary))
        await session.commit()
    return {"JO": jordan, "LY": libya, "DZ": algeria}


async def test_a_test_account_sees_its_markets_and_switches_into_its_twin(client: AsyncClient, session_factory) -> None:
    family = await _family(client, session_factory)
    listed = await client.get("/auth/test-markets", headers=auth(family["JO"]))
    assert listed.status_code == 200, listed.text
    markets = {row["country_code"]: row for row in listed.json()["markets"]}
    assert set(markets) == {"JO", "LY", "DZ"} and markets["JO"]["current"] is True
    assert markets["DZ"]["name"] == "الجزائر"

    switched = await client.post("/auth/test-markets/DZ", headers=auth(family["JO"]))
    assert switched.status_code == 200, switched.text
    body = switched.json()
    assert body["user"]["id"] == family["DZ"]["user"]["id"] and body["user"]["country_code"] == "DZ"
    me = await client.get("/auth/me", headers=auth(body))
    assert me.json()["country_code"] == "DZ"
    # **ومن الأخ يُرى الإخوةُ أنفسُهم** — والحاليُّ الجزائر
    again = (await client.get("/auth/test-markets", headers=auth(body))).json()["markets"]
    assert {row["country_code"] for row in again} == {"JO", "LY", "DZ"}
    assert next(row for row in again if row["current"])["country_code"] == "DZ"

    async with session_factory() as session:
        rows = (await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "test_market_switch"))).all()
    assert [(row.details["from"], row.details["to"]) for row in rows] == [("JO", "DZ")]


async def test_a_real_account_has_no_selector(client: AsyncClient) -> None:
    rider = await rider_session(client)
    assert (await client.get("/auth/test-markets", headers=rider["headers"])).json() == {"markets": []}
    denied = await client.post("/auth/test-markets/LY", headers=rider["headers"])
    assert denied.status_code == 403, denied.text


async def test_test_funds_fill_to_the_market_amount_once_and_are_marked(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    family = await _family(client, session_factory)
    owner = await markets_owner(client, admin_headers)
    dz = family["DZ"]["user"]["id"]

    denied = await client.post(f"/admin/test-accounts/{dz}/refill", headers=admin_headers)
    assert denied.status_code == 403, "إعادةُ الملء للمالك وحدَه"

    first = await client.post(f"/admin/test-accounts/{dz}/refill", headers=owner["headers"])
    assert first.status_code == 200, first.text
    row = next(item for item in first.json()["accounts"] if item["id"] == dz)
    assert row["balance"] == "20000" and row["target_amount"] == "20000" and row["currency"] == "DZD"
    again = await client.post(f"/admin/test-accounts/{dz}/refill", headers=owner["headers"])
    assert next(item for item in again.json()["accounts"] if item["id"] == dz)["balance"] == "20000"

    jo = family["JO"]["user"]["id"]
    filled = await client.post(f"/admin/test-accounts/{jo}/refill", headers=owner["headers"])
    assert next(item for item in filled.json()["accounts"] if item["id"] == jo)["balance"] == "100.000"

    async with session_factory() as session:
        entries = (
            await session.scalars(select(WalletTransaction).where(WalletTransaction.owner_id.in_([dz, jo])))
        ).all()
    assert len(entries) == 2
    assert all(entry.type is WalletTransactionType.ADJUSTMENT for entry in entries)
    assert all(entry.reference.startswith("رصيد تجريبي") for entry in entries)
    assert {entry.owner_type for entry in entries} == {WalletOwnerType.RIDER}


async def test_a_real_account_is_never_refilled(client: AsyncClient, admin_headers: dict) -> None:
    owner = await markets_owner(client, admin_headers)
    rider = await rider_session(client)
    answer = await client.post(f"/admin/test-accounts/{rider['user']['id']}/refill", headers=owner["headers"])
    assert answer.status_code == 404, answer.text


async def test_test_money_never_leaves_by_transfer(client: AsyncClient, session_factory, jordan_wallet: None, admin_headers: dict) -> None:
    family = await _family(client, session_factory)
    owner = await markets_owner(client, admin_headers)
    await client.post(f"/admin/test-accounts/{family['JO']['user']['id']}/refill", headers=owner["headers"])
    await rider_session(client)
    sent = await client.post(
        "/wallet/me/transfers",
        json={"recipient_phone": RIDER["phone"], "country_code": "JO", "amount": "1.000"},
        headers=auth(family["JO"]),
    )
    assert sent.status_code >= 400, sent.text
