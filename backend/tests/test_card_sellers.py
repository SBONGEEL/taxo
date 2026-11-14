"""بائعو البطاقات والبيعُ لحظةَ الطلب (SPEC §١٠٠-ب/٤–٥، أمرُ المالك ٢٠٢٦-١١-١٢).

**المالكُ وحدَه ينشئ البائعَ ويفتح البيع** · **مطفأٌ افتراضاً** · **المحلُّ من ربط الحساب لا من الطلب** · **الرمزُ في الردِّ مرّةً ولا
يُخزَّن ولا يُدقَّق** · **السقفُ اليوميُّ يصمد أمام التزامن** · والموقوفُ لا يبيع · ومن باع ومتى يُقرأ في اللوحة.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.crypto import get_cipher
from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, UserRole
from app.models.taxo_card import CardBatch, CardShopStaff, TaxoCard
from app.models.totp import UserTotp
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.services import token_service
from tests.helpers import rider_session
from tests.test_taxo_cards import ALGERIAN_RIDER, card_market, card_pepper, redeem  # noqa: F401

pytestmark = pytest.mark.asyncio


async def _staff(session_factory, *, roles: list[UserRole], name: str, factor: bool = True) -> tuple[dict, uuid.UUID]:
    async with session_factory() as session:
        user = User(
            phone=None, name=name, role=roles[0], country_code=CountryCode.DZ,
            role_grants=[UserRoleGrant(role=role) for role in roles],
        )
        session.add(user)
        await session.flush()
        if factor:
            session.add(UserTotp(
                user_id=user.id, secret_encrypted=get_cipher().encrypt({"secret": "JBSWY3DPEHPK3PXP"}),
                confirmed_at=datetime.now(UTC),
            ))
        await session.commit()
        tokens = await token_service.issue_token_pair(session, user)
        return {"Authorization": f"Bearer {tokens.access_token}"}, user.id


async def _owner(session_factory) -> dict:
    return (await _staff(session_factory, roles=[UserRole.ADMIN, UserRole.OWNER], name="مالك الاختبار"))[0]


async def _shop_and_denomination(client: AsyncClient, admin_headers: dict) -> tuple[str, str]:
    denom = await client.post("/admin/taxo-cards/denominations", json={"country_code": "DZ", "amount": "1000"}, headers=admin_headers)
    assert denom.status_code == 201, denom.text
    shop = await client.post("/admin/taxo-cards/shops", json={
        "country_code": "DZ", "name": "مكتبةُ النور", "discount_percent": "5", "payment_mode": "after_sale"}, headers=admin_headers)
    assert shop.status_code == 201, shop.text
    return shop.json()["id"], denom.json()["id"]


async def _seller(session_factory, shop_id: str, *, factor: bool = True, name: str = "بائع الاختبار") -> tuple[dict, uuid.UUID]:
    """**بائعٌ بعاملٍ مؤكَّدٍ مربوطٌ بمحلّ** — بلا كلمة: الدخولُ نفسُه يقيسه اختبارُ الإنشاء."""
    headers, user_id = await _staff(session_factory, roles=[UserRole.CARD_SELLER], name=name, factor=factor)
    async with session_factory() as session:
        session.add(CardShopStaff(user_id=user_id, shop_id=uuid.UUID(shop_id), is_active=True))
        await session.commit()
    return headers, user_id


async def _open(client: AsyncClient, owner: dict, **extra) -> None:
    opened = await client.put("/admin/taxo-cards/pos-settings", json={"country_code": "DZ", "pos_enabled": True} | extra, headers=owner)
    assert opened.status_code == 200, opened.text


async def test_the_owner_creates_the_seller_who_enters_the_panel_only(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    owner = await _owner(session_factory)
    shop_id, _denom = await _shop_and_denomination(client, admin_headers)
    body = {"shop_id": shop_id, "name": "سمير البائع", "username": "nour.seller1", "password": "Temp-Pass-2026!x"}
    assert (await client.post("/admin/taxo-cards/sellers", json=body, headers=admin_headers)).status_code == 403
    created = await client.post("/admin/taxo-cards/sellers", json=body, headers=owner)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["must_change_password"] is True and row["has_factor"] is False and row["shop_name"] == "مكتبةُ النور"
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(row["user_id"]))
        assert set(user.roles) == {UserRole.CARD_SELLER} and user.phone is None and user.country_code is CountryCode.DZ
    login = await client.post("/auth/login", json={"username": "nour.seller1", "password": body["password"], "app": "panel"})
    assert login.status_code == 200, login.text
    rider_app = await client.post("/auth/login", json={"username": "nour.seller1", "password": body["password"], "app": "rider"})
    assert rider_app.status_code == 403
    listed = (await client.get("/admin/taxo-cards/sellers?country=DZ", headers=admin_headers)).json()
    assert [r["username"] for r in listed] == ["nour.seller1"]


async def test_selling_is_closed_until_the_owner_opens_it(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    owner = await _owner(session_factory)
    shop_id, denom_id = await _shop_and_denomination(client, admin_headers)
    seller, _ = await _seller(session_factory, shop_id)
    me = (await client.get("/reseller/me", headers=seller)).json()
    assert me["enabled"] is False and me["shop_name"] == "مكتبةُ النور" and me["denominations"][0]["amount"] == "1000"
    closed = await client.post("/reseller/sell", json={"denomination_id": denom_id}, headers=seller)
    assert closed.status_code == 409 and closed.json()["code"] == "card_selling_closed"
    # **ولا يفتحه غيرُ المالك**
    refused = await client.put("/admin/taxo-cards/pos-settings", json={"country_code": "DZ", "pos_enabled": True}, headers=admin_headers)
    assert refused.status_code == 403
    await _open(client, owner)
    assert (await client.get("/reseller/me", headers=seller)).json()["enabled"] is True


async def test_a_sale_issues_one_card_for_the_sellers_own_shop_and_keeps_no_code(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    owner = await _owner(session_factory)
    shop_id, denom_id = await _shop_and_denomination(client, admin_headers)
    seller, seller_id = await _seller(session_factory, shop_id)
    await _open(client, owner)
    sold = await client.post("/reseller/sell", json={"denomination_id": denom_id}, headers=seller)
    assert sold.status_code == 201, sold.text
    sale = sold.json()
    code, serial = sale["code"], sale["serial"]
    assert serial.startswith("DZ-P") and sale["amount"] == "1000" and sale["currency"] == "DZD"
    async with session_factory() as session:
        card = await session.scalar(select(TaxoCard).where(TaxoCard.serial == serial))
        batch = await session.get(CardBatch, card.batch_id)
        assert batch.kind == "pos" and batch.quantity == 1 and str(batch.shop_id) == shop_id and batch.created_by == seller_id
        assert card.code_envelope is None and code not in str(card.__dict__)
        audit_text = str((await session.scalars(select(AdminAuditLog.details))).all())
        assert code not in audit_text and code.replace("-", "") not in audit_text and serial in audit_text
    # **يشحن كأيِّ بطاقة** — ثمّ يُقرأ في مبيعات البائع وفي اللوحة: من باعها ومتى
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await redeem(client, rider["headers"], code)).status_code == 200
    sales = (await client.get("/reseller/sales", headers=seller)).json()
    assert sales[0]["serial"] == serial and sales[0]["state"] == "redeemed" and "code" not in sales[0]
    found = (await client.get(f"/admin/taxo-cards/cards?country=DZ&serial={serial}", headers=admin_headers)).json()[0]
    assert found["batch_kind"] == "pos" and found["shop_name"] == "مكتبةُ النور"
    assert found["issued_by_name"] == "بائع الاختبار" and found["issued_at"]
    figures = (await client.get("/admin/taxo-cards/sellers?country=DZ", headers=admin_headers)).json()[0]
    assert figures["sold"] == 1 and figures["redeemed"] == 1 and figures["sold_amount"] == "1000"


async def test_the_daily_cap_holds_against_concurrent_sales(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    owner = await _owner(session_factory)
    shop_id, denom_id = await _shop_and_denomination(client, admin_headers)
    seller, _ = await _seller(session_factory, shop_id)
    await _open(client, owner, pos_daily_cap=2)
    results = await asyncio.wait_for(
        asyncio.gather(*(client.post("/reseller/sell", json={"denomination_id": denom_id}, headers=seller) for _ in range(4))),
        timeout=30,
    )
    assert Counter(r.status_code for r in results) == Counter({201: 2, 429: 2})
    assert {r.json()["code"] for r in results if r.status_code == 429} == {"card_seller_daily_cap"}
    async with session_factory() as session:
        assert len((await session.scalars(select(CardBatch).where(CardBatch.kind == "pos"))).all()) == 2


async def test_a_stopped_seller_cannot_sell_and_a_seller_needs_a_second_factor(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    owner = await _owner(session_factory)
    shop_id, denom_id = await _shop_and_denomination(client, admin_headers)
    seller, _ = await _seller(session_factory, shop_id)
    await _open(client, owner)
    staff_id = (await client.get("/admin/taxo-cards/sellers?country=DZ", headers=admin_headers)).json()[0]["id"]
    stopped = await client.post(f"/admin/taxo-cards/sellers/{staff_id}/active", json={"is_active": False}, headers=owner)
    assert stopped.status_code == 200 and stopped.json()["is_active"] is False
    refused = await client.post("/reseller/sell", json={"denomination_id": denom_id}, headers=seller)
    assert refused.status_code == 403 and refused.json()["code"] == "card_seller_not_bound"
    # **والبائعُ لا يدخل غيرَ بابه** — ولا يبيع بلا عاملٍ ثانٍ
    assert (await client.get("/admin/taxo-cards/batches?country=DZ", headers=seller)).status_code == 403
    bare, _ = await _seller(session_factory, shop_id, factor=False, name="بائعٌ بلا عامل")
    no_factor = await client.get("/reseller/me", headers=bare)
    assert no_factor.status_code == 403 and no_factor.json()["code"] == "totp_enrollment_required"


async def test_other_roles_cannot_use_the_seller_door(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    assert (await client.get("/reseller/me", headers=admin_headers)).status_code == 403
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await client.get("/reseller/me", headers=rider["headers"])).status_code == 403
