"""بطاقاتُ TAXO يبيعها الكباتن (أمرُ المالك ٢٠٢٦-١١-٢٣، `design/CAPTAIN-CARDS-2026-11-23.md`، الترحيلة `0189`).

**مغلقٌ بشرطين** · **الكلفةُ من الخلفية والخصمُ مجمَّد** · **قيدٌ واحدٌ في الدفتر ولو أُعيد الطلب** · **رصيدٌ ناقصٌ يُردّ بلا صفّ** ·
**السقفُ اليوميُّ يصمد أمام التزامن** (وهو ما يملكه قفلُ الكبتن وحدَه) · **لا يرى كبتنٌ بطاقاتِ غيره** · **الشحنُ يمحو المعمّى** ·
**وبطاقةُ الكبتن لمحفظة راكبٍ غيرِه** · والتقريرُ يجمع في الخلفية.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, FeatureKey, WalletOwnerType, WalletTransactionType
from app.models.feature_flag import FeatureFlag
from app.models.taxo_card import CardBatch, TaxoCard
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import wallet
from tests.helpers import auth, register, rider_session
from tests.test_card_sellers import _owner
from tests.test_payment_requests import ALGERIAN_DRIVER, ALGERIAN_RIDER, balance
from tests.test_taxo_cards import card_market, card_pepper, redeem  # noqa: F401

pytestmark = pytest.mark.asyncio

SECOND_DRIVER = ALGERIAN_DRIVER | {"phone": "0662345678", "name": "كابتنٌ من وهران"}


async def _captain(client: AsyncClient, session_factory, payload: dict = ALGERIAN_DRIVER, *, funds: str = "5000") -> dict:
    """**كبتنٌ معتمدٌ برصيدٍ في محفظة الكبتن** — الاعتمادُ يُكتب كما يكتبه `approved_driver`، والرصيدُ قيدُ شحنٍ في الدفتر."""
    body = await register(client, payload)
    user_id = uuid.UUID(body["user"]["id"])
    async with session_factory() as session:
        driver = await session.scalar(select(Driver).where(Driver.user_id == user_id))
        driver.status = DriverStatus.APPROVED
        user = await session.get(User, user_id)
        if Decimal(funds):
            await wallet.record(
                session, owner=user, owner_type=WalletOwnerType.DRIVER, tx_type=WalletTransactionType.TOPUP,
                amount=Decimal(funds), reference="شحن اختبار", idempotency_key=f"test-fund:{user_id}",
            )
        await session.commit()
        return {"headers": auth(body), "user_id": user_id, "driver_id": driver.id}


async def _market(client: AsyncClient, session_factory, admin_headers: dict, *, flag: bool = True,
                  discount: str | None = "10", cap: int | None = None) -> tuple[dict, str]:
    await card_market(session_factory)
    denom = await client.post("/admin/taxo-cards/denominations", json={"country_code": "DZ", "amount": "1000"}, headers=admin_headers)
    assert denom.status_code == 201, denom.text
    owner = await _owner(session_factory)
    if flag:
        async with session_factory() as session:
            session.add(FeatureFlag(country_code=CountryCode.DZ, feature_key=FeatureKey.TAXO_CARDS_CAPTAIN_SALES.value, enabled=True))
            await session.commit()
    if discount is not None:
        saved = await client.put("/admin/taxo-cards/captain-discount",
                                 json={"country_code": "DZ", "captain_discount_percent": discount}, headers=owner)
        assert saved.status_code == 200, saved.text
    if cap is not None:
        capped = await client.put("/admin/taxo-cards/pos-settings", json={"country_code": "DZ", "pos_daily_cap": cap}, headers=owner)
        assert capped.status_code == 200, capped.text
    return owner, denom.json()["id"]


async def _buy(client: AsyncClient, captain: dict, denom: str, quantity: int, key: str | None = None):
    return await client.post("/taxo-cards/captain/purchase", json={
        "denomination_id": denom, "quantity": quantity, "idempotency_key": key or uuid.uuid4().hex}, headers=captain["headers"])


async def _driver_balance(client: AsyncClient, captain: dict) -> str:
    return (await client.get("/wallet/me?wallet=driver", headers=captain["headers"])).json()["balance"]


async def _ledger(session_factory, user_id: uuid.UUID) -> list[WalletTransaction]:
    async with session_factory() as session:
        return list((await session.scalars(select(WalletTransaction).where(
            WalletTransaction.owner_id == user_id, WalletTransaction.type == WalletTransactionType.CARD_PURCHASE))).all())


# ------------------------------------------------------------------ مغلقٌ بشرطين


async def test_sales_stay_closed_without_the_switch_or_the_discount(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    owner, denom = await _market(client, session_factory, admin_headers, flag=False, discount="10")
    captain = await _captain(client, session_factory)
    page = (await client.get("/taxo-cards/captain", headers=captain["headers"])).json()
    assert page["open"] is False and page["denominations"] == [] and page["discount_percent"] is None
    refused = await _buy(client, captain, denom, 1)
    assert refused.status_code == 409 and refused.json()["code"] == "captain_card_sales_closed"
    # **والمفتاحُ وحدَه لا يكفي**: خصمٌ فارغٌ يُغلق
    async with session_factory() as session:
        session.add(FeatureFlag(country_code=CountryCode.DZ, feature_key=FeatureKey.TAXO_CARDS_CAPTAIN_SALES.value, enabled=True))
        await session.commit()
    cleared = await client.put("/admin/taxo-cards/captain-discount",
                               json={"country_code": "DZ", "captain_discount_percent": None}, headers=owner)
    assert cleared.status_code == 200 and cleared.json()["captain_discount_percent"] is None
    assert (await _buy(client, captain, denom, 1)).status_code == 409
    assert await _ledger(session_factory, captain["user_id"]) == []


async def test_only_the_owner_sets_the_discount(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    refused = await client.put("/admin/taxo-cards/captain-discount",
                               json={"country_code": "DZ", "captain_discount_percent": "10"}, headers=admin_headers)
    assert refused.status_code == 403
    owner = await _owner(session_factory)
    too_much = await client.put("/admin/taxo-cards/captain-discount",
                                json={"country_code": "DZ", "captain_discount_percent": "51"}, headers=owner)
    assert too_much.status_code == 422


# ------------------------------------------------------------------ الشراء


async def test_a_purchase_charges_the_frozen_discounted_cost_once(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    owner, denom = await _market(client, session_factory, admin_headers)
    captain = await _captain(client, session_factory)
    page = (await client.get("/taxo-cards/captain", headers=captain["headers"])).json()
    assert page["open"] is True and page["denominations"][0]["unit_cost_amount"] == "900"
    quote = await client.post("/taxo-cards/captain/quote", json={"denomination_id": denom, "quantity": 2}, headers=captain["headers"])
    assert quote.status_code == 200 and quote.json()["cost_amount"] == "1800" and quote.json()["face_amount"] == "2000"

    key = uuid.uuid4().hex
    bought = await _buy(client, captain, denom, 2, key)
    assert bought.status_code == 200, bought.text
    assert bought.json()["cost_amount"] == "1800" and bought.json()["balance_amount"] == "3200"
    # **الإعادةُ بالمفتاح نفسِه تجد دفعتَها** — لا قيدَ ثانٍ ولا بطاقاتٍ ثانية
    again = await _buy(client, captain, denom, 2, key)
    assert again.status_code == 200 and again.json()["replayed"] is True and again.json()["batch_id"] == bought.json()["batch_id"]
    assert await _driver_balance(client, captain) == "3200"
    entries = await _ledger(session_factory, captain["user_id"])
    assert len(entries) == 1 and entries[0].amount == Decimal("-1800.000")
    assert entries[0].idempotency_key == f"cardbuy:{bought.json()['batch_id']}"

    # **والخصمُ مجمَّدٌ على الدفعة**: تغييرُه بعدها لا يمسّ ما بيع
    await client.put("/admin/taxo-cards/captain-discount", json={"country_code": "DZ", "captain_discount_percent": "20"}, headers=owner)
    async with session_factory() as session:
        batch = await session.get(CardBatch, uuid.UUID(bought.json()["batch_id"]))
        assert batch.kind == "captain" and batch.seller_driver_id == captain["driver_id"]
        assert batch.discount_percent_at_issue == Decimal("10.00")
        cards = (await session.scalars(select(TaxoCard).where(TaxoCard.batch_id == batch.id))).all()
        assert len(cards) == 2 and all(card.code_envelope for card in cards)
        assert all(card.serial.startswith("DZ-C") for card in cards)
        # **ولا رمزَ في التدقيق**
        details = (await session.scalars(select(AdminAuditLog.details).where(
            AdminAuditLog.entity_type == "taxo_card.captain_purchase"))).all()
        assert len(details) == 1 and details[0]["cost"] == "1800.000"
    codes = [(await client.get(f"/taxo-cards/captain/cards/{card.id}/code", headers=captain["headers"])).json()["code"] for card in cards]
    assert not any(code.replace("-", "") in str(details) for code in codes)


async def test_a_short_balance_is_refused_before_any_row(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    _, denom = await _market(client, session_factory, admin_headers)
    captain = await _captain(client, session_factory, funds="1000")
    refused = await _buy(client, captain, denom, 2)
    assert refused.status_code == 409 and refused.json()["code"] == "insufficient_balance"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(CardBatch).where(CardBatch.kind == "captain")) == 0
    assert await _driver_balance(client, captain) == "1000"


async def test_the_daily_cap_counts_cards(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    _, denom = await _market(client, session_factory, admin_headers, cap=3)
    captain = await _captain(client, session_factory)
    assert (await _buy(client, captain, denom, 2)).status_code == 200
    capped = await _buy(client, captain, denom, 2)
    assert capped.status_code == 429 and capped.json()["code"] == "captain_card_daily_cap"
    assert (await client.get("/taxo-cards/captain", headers=captain["headers"])).json()["remaining_today"] == 1


async def test_a_suspended_captain_cannot_buy(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    _, denom = await _market(client, session_factory, admin_headers)
    captain = await _captain(client, session_factory)
    async with session_factory() as session:
        driver = await session.get(Driver, captain["driver_id"])
        driver.status = DriverStatus.SUSPENDED
        await session.commit()
    assert (await _buy(client, captain, denom, 1)).status_code == 409
    assert await _ledger(session_factory, captain["user_id"]) == []


# ------------------------------------------------------------------ البيعُ للراكب


async def test_a_captain_sees_only_his_own_cards(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    _, denom = await _market(client, session_factory, admin_headers)
    first = await _captain(client, session_factory)
    second = await _captain(client, session_factory, SECOND_DRIVER)
    assert (await _buy(client, first, denom, 1)).status_code == 200
    mine = (await client.get("/taxo-cards/captain/cards", headers=first["headers"])).json()
    assert len(mine) == 1 and mine[0]["state"] == "unused" and "code" not in mine[0]
    assert (await client.get("/taxo-cards/captain/cards", headers=second["headers"])).json() == []
    stolen = await client.get(f"/taxo-cards/captain/cards/{mine[0]['id']}/code", headers=second["headers"])
    assert stolen.status_code == 404


async def test_the_rider_redeems_and_the_envelope_is_erased(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    _, denom = await _market(client, session_factory, admin_headers)
    captain = await _captain(client, session_factory)
    assert (await _buy(client, captain, denom, 1)).status_code == 200
    card = (await client.get("/taxo-cards/captain/cards", headers=captain["headers"])).json()[0]
    shown = (await client.get(f"/taxo-cards/captain/cards/{card['id']}/code", headers=captain["headers"])).json()
    assert shown["redeem_url"] == "https://app.tajora.ly/redeem#" + shown["code"].replace("-", "")
    assert shown["qr_svg"].startswith("data:image/svg+xml")
    # **بائعُها لا يشحن بها** — لا محفظةَ كبتنه ولا محفظةَ راكبه
    own = await redeem(client, captain["headers"], shown["code"], wallet="driver")
    assert own.status_code == 409
    rider = await rider_session(client, ALGERIAN_RIDER)
    used = await redeem(client, rider["headers"], shown["code"])
    assert used.status_code == 200, used.text
    assert await balance(client, rider["headers"]) == "1000"
    async with session_factory() as session:
        stored = await session.get(TaxoCard, uuid.UUID(card["id"]))
        assert stored.code_envelope is None and stored.status.value == "redeemed"
    gone = await client.get(f"/taxo-cards/captain/cards/{card['id']}/code", headers=captain["headers"])
    assert gone.status_code == 404
    listed = (await client.get("/taxo-cards/captain/cards", headers=captain["headers"])).json()
    assert listed[0]["state"] == "redeemed"


async def test_another_captain_cannot_redeem_into_a_withdrawable_wallet(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    _, denom = await _market(client, session_factory, admin_headers)
    seller = await _captain(client, session_factory)
    other = await _captain(client, session_factory, SECOND_DRIVER, funds="0")
    assert (await _buy(client, seller, denom, 1)).status_code == 200
    card = (await client.get("/taxo-cards/captain/cards", headers=seller["headers"])).json()[0]
    code = (await client.get(f"/taxo-cards/captain/cards/{card['id']}/code", headers=seller["headers"])).json()["code"]
    refused = await redeem(client, other["headers"], code, wallet="driver")
    assert refused.status_code == 409 and "الراكب" in refused.json()["message"]
    assert await _driver_balance(client, other) == "0"


async def test_the_report_sums_each_captain_in_the_backend(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    owner, denom = await _market(client, session_factory, admin_headers)
    captain = await _captain(client, session_factory)
    assert (await _buy(client, captain, denom, 2)).status_code == 200
    card = (await client.get("/taxo-cards/captain/cards", headers=captain["headers"])).json()[0]
    code = (await client.get(f"/taxo-cards/captain/cards/{card['id']}/code", headers=captain["headers"])).json()["code"]
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await redeem(client, rider["headers"], code)).status_code == 200
    report = (await client.get("/admin/taxo-cards/report/captains?country=DZ", headers=admin_headers)).json()
    assert len(report) == 1
    row = report[0]
    assert row["cards"] == 2 and row["redeemed"] == 1 and row["unused"] == 1
    assert row["face_amount"] == "2000" and row["paid_amount"] == "1800" and row["currency"] == "DZD"
    kinds = {k["kind"]: k for k in (await client.get("/admin/taxo-cards/report/kinds?country=DZ", headers=admin_headers)).json()}
    assert kinds["captain"]["cards"] == 2 and kinds["captain"]["redeemed"] == 1
