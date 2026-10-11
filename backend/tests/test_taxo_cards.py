"""بطاقاتُ شحن TAXO — المرحلة ٢ (SPEC §٧٣-هـ): **رمزٌ لا يُخزَّن، ويشحن مرّةً، والتخمينُ مسقوف، ولا حذف**."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text

from app.core.config import settings
from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, PaymentProviderKind, WalletTransactionType
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.taxo_card import CardGuessAlert, TaxoCard
from app.models.wallet import WalletTransaction
from app.services import taxo_cards
from tests.helpers import RIDER, register, rider_session
from tests.money_format import offenders
from tests.test_payment_requests import (
    ALGERIAN_DRIVER,
    ALGERIAN_RIDER,
    SECOND_ALGERIAN,
    algeria_market,
    balance,
)


@pytest.fixture(autouse=True)
def card_pepper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "taxo_card_code_pepper", "test-pepper-for-cards")


async def card_market(session_factory) -> dict[str, uuid.UUID]:
    """سوقُ الجزائر بنظامه الجديد، **ومعه طريقةُ «بطاقات TAXO» مفعَّلة**."""
    ids = await algeria_market(session_factory)
    async with session_factory() as session:
        provider = PayMethod(country_code=CountryCode.DZ, kind=PaymentProviderKind.PURCHASE_CODE, code="taxo_card",
                                   name="بطاقة TAXO", enabled=True, sort_order=5)
        session.add(provider)
        await session.commit()
        ids["cards"] = provider.id
    return ids


async def issue(client: AsyncClient, admin_headers: dict, *, quantity: int = 3, discount: str = "10",
                mode: str = "before_receipt", starts_in: timedelta = timedelta(0), lasts: timedelta = timedelta(days=90)) -> dict:
    denom = await client.post("/admin/taxo-cards/denominations", json={"country_code": "DZ", "amount": "1000"}, headers=admin_headers)
    denom_id = denom.json()["id"] if denom.status_code == 201 else (
        await client.get("/admin/taxo-cards/denominations?country=DZ", headers=admin_headers)).json()[0]["id"]
    shop = await client.post("/admin/taxo-cards/shops", json={
        "country_code": "DZ", "name": "مكتبةُ الأمل", "discount_percent": discount, "payment_mode": mode}, headers=admin_headers)
    assert shop.status_code == 201, shop.text
    start = datetime.now(UTC) - timedelta(minutes=1) + starts_in
    created = await client.post("/admin/taxo-cards/batches", json={
        "country_code": "DZ", "denomination_id": denom_id, "quantity": quantity, "shop_id": shop.json()["id"],
        "valid_from": start.isoformat(), "expires_at": (start + lasts).isoformat()}, headers=admin_headers)
    assert created.status_code == 201, created.text
    return created.json() | {"shop_id": shop.json()["id"]}


async def redeem(client: AsyncClient, headers: dict, code: str, **extra):
    return await client.post("/taxo-cards/redeem", json={"code": code} | extra, headers=headers)


# ------------------------------------------------------------------ الفئاتُ والدفعات


async def test_denominations_are_whole_dinars_and_never_invented(client: AsyncClient, admin_headers: dict) -> None:
    assert (await client.get("/admin/taxo-cards/denominations?country=DZ", headers=admin_headers)).json() == []
    fraction = await client.post("/admin/taxo-cards/denominations", json={"country_code": "DZ", "amount": "1000.5"}, headers=admin_headers)
    assert fraction.status_code == 422
    made = await client.post("/admin/taxo-cards/denominations", json={"country_code": "DZ", "amount": "1000"}, headers=admin_headers)
    assert made.status_code == 201 and made.json()["amount"] == "1000" and made.json()["currency"] == "DZD"
    again = await client.post("/admin/taxo-cards/denominations", json={"country_code": "DZ", "amount": "1000"}, headers=admin_headers)
    assert again.status_code == 409


async def test_codes_are_shown_once_and_only_their_fingerprint_is_kept(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=3)
    codes = body["codes"]
    assert [c["serial"] for c in codes] == ["DZ-B0001-000001", "DZ-B0001-000002", "DZ-B0001-000003"]
    for row in codes:
        plain = row["code"].replace("-", "")
        assert len(plain) == 16 and set(plain) <= set(taxo_cards.ALPHABET)
    async with session_factory() as session:
        stored = (await session.scalars(select(TaxoCard).order_by(TaxoCard.serial))).all()
        for card, row in zip(stored, codes, strict=True):
            plain = row["code"].replace("-", "")
            assert card.code_hash != plain and plain not in card.code_hash and len(card.code_hash) == 64
        # **ولا رمزَ في التدقيق**
        details = (await session.scalars(select(AdminAuditLog.details).where(AdminAuditLog.entity_type == "card_batch"))).all()
        assert details and not any(row["code"] in str(details) for row in codes)
    # **ولا بابَ يعيدها**: القائمةُ بلا رموز
    listed = (await client.get("/admin/taxo-cards/batches?country=DZ", headers=admin_headers)).json()
    assert "codes" not in listed[0] and listed[0]["active"] == 3


async def test_the_shop_owes_by_its_frozen_terms(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    before = await issue(client, admin_headers, quantity=3, discount="10", mode="before_receipt")
    batch = before["batch"]
    # **قبل الاستلام**: ما سُلِّم ناقصاً خصمَه — ٣×١٠٠٠×٩٠٪
    assert batch["due_amount"] == "2700" and batch["live_amount"] == "3000" and offenders(batch) == []
    # **وتعديلُ المحلّ بعد الإصدار لا يغيّر ما سُلِّم**
    await client.patch(f"/admin/taxo-cards/shops/{before['shop_id']}", json={"discount_percent": "50"}, headers=admin_headers)
    listed = (await client.get("/admin/taxo-cards/batches?country=DZ", headers=admin_headers)).json()
    assert listed[0]["due_amount"] == "2700"
    report = (await client.get("/admin/taxo-cards/report/shops?country=DZ", headers=admin_headers)).json()
    assert report[0]["due_amount"] == "2700" and report[0]["cards"] == 3


async def test_after_sale_shops_owe_what_was_used(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=2, discount="5", mode="after_sale")
    assert body["batch"]["due_amount"] == "0"
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await redeem(client, rider["headers"], body["codes"][0]["code"])).status_code == 200
    listed = (await client.get("/admin/taxo-cards/batches?country=DZ", headers=admin_headers)).json()
    assert listed[0]["redeemed"] == 1 and listed[0]["due_amount"] == "950"


# ------------------------------------------------------------------ الاستعمال


async def test_a_code_tops_up_once_under_its_own_name(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=1)
    code = body["codes"][0]["code"]
    rider = await rider_session(client, ALGERIAN_RIDER)
    # **بمسافاتٍ وحروفٍ صغيرة** — الرمزُ كما يُكتب بإصبع
    used = await redeem(client, rider["headers"], " " + code.lower().replace("-", " ") + " ")
    assert used.status_code == 200, used.text
    assert used.json() == {"serial": "DZ-B0001-000001", "amount": "1000", "currency": "DZD"}
    assert await balance(client, rider["headers"]) == "1000"
    async with session_factory() as session:
        entry = await session.scalar(select(WalletTransaction).where(WalletTransaction.type == WalletTransactionType.TAXO_CARD))
        assert entry is not None and entry.amount == Decimal("1000.000")
        request = await session.scalar(select(PaymentRequest).where(PaymentRequest.reference == "DZ-B0001-000001"))
        assert request.status.value == "approved" and request.kind is PaymentProviderKind.PURCHASE_CODE
        assert request.transaction_id == entry.id
    second = await rider_session(client, SECOND_ALGERIAN)
    again = await redeem(client, second["headers"], code)
    assert again.status_code == 422 and "استُعملت" in again.json()["message"]
    assert await balance(client, second["headers"]) == "0"


async def test_the_captain_tops_up_his_own_wallet(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=1)
    captain = await register(client, ALGERIAN_DRIVER)
    from tests.helpers import auth

    used = await redeem(client, auth(captain), body["codes"][0]["code"], wallet="driver")
    assert used.status_code == 200, used.text
    wallet = (await client.get("/wallet/me?wallet=driver", headers=auth(captain))).json()
    assert wallet["balance"] == "1000"


async def test_wrong_codes_are_capped_per_account_and_raise_an_alert(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=1)
    await client.put("/admin/taxo-cards/limits", json={"country_code": "DZ", "max_wrong_per_account": 3}, headers=admin_headers)
    rider = await rider_session(client, ALGERIAN_RIDER)
    for _ in range(3):
        wrong = await redeem(client, rider["headers"], "ABCD-EFGH-JKMN-PQRS")
        assert wrong.status_code == 422
    # **بلغ السقفَ — فلا يُقرأ رمزٌ ولو صحيح** حتى تنقضي النافذة
    locked = await redeem(client, rider["headers"], body["codes"][0]["code"])
    assert locked.status_code == 429
    alerts = (await client.get("/admin/taxo-cards/alerts?country=DZ", headers=admin_headers)).json()
    assert [(a["scope"], a["attempts"]) for a in alerts] == [("account", 3)]
    reviewed = await client.post(f"/admin/taxo-cards/alerts/{alerts[0]['id']}/review", headers=admin_headers)
    assert reviewed.json()["reviewed_at"] is not None


async def test_wrong_codes_are_capped_per_address_across_accounts(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    await client.put("/admin/taxo-cards/limits", json={"country_code": "DZ", "max_wrong_per_ip": 2}, headers=admin_headers)
    first = await rider_session(client, ALGERIAN_RIDER)
    second = await rider_session(client, SECOND_ALGERIAN)
    shared = {"x-forwarded-for": "203.0.113.9"}
    await client.post("/taxo-cards/redeem", json={"code": "ABCD-EFGH-JKMN-PQRS"}, headers=first["headers"] | shared)
    await client.post("/taxo-cards/redeem", json={"code": "ABCD-EFGH-JKMN-PQRT"}, headers=second["headers"] | shared)
    blocked = await client.post("/taxo-cards/redeem", json={"code": "ABCD-EFGH-JKMN-PQRU"}, headers=first["headers"] | shared)
    assert blocked.status_code == 429
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(CardGuessAlert).where(CardGuessAlert.scope == "ip")) == 1


async def test_cancelled_cards_and_batches_never_top_up(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=3)
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await redeem(client, rider["headers"], body["codes"][0]["code"])).status_code == 200
    card = (await client.get("/admin/taxo-cards/cards?country=DZ&serial=000002", headers=admin_headers)).json()[0]
    bare = await client.post(f"/admin/taxo-cards/cards/{card['id']}/cancel", json={"reason": "  "}, headers=admin_headers)
    assert bare.status_code == 422
    cancelled = await client.post(f"/admin/taxo-cards/cards/{card['id']}/cancel", json={"reason": "ضاعت من المحلّ"}, headers=admin_headers)
    assert cancelled.json()["status"] == "cancelled"
    assert (await redeem(client, rider["headers"], body["codes"][1]["code"])).json()["message"] == "هذه البطاقةُ ملغاة"

    batch_id = body["batch"]["id"]
    whole = await client.post(f"/admin/taxo-cards/batches/{batch_id}/cancel", json={"reason": "سُرقت الدفعة"}, headers=admin_headers)
    assert whole.json()["status"] == "cancelled"
    # **المستعمَلةُ تبقى مستعمَلة** — مالُها في محفظة صاحبها
    assert whole.json()["redeemed"] == 1 and whole.json()["cancelled"] == 2 and whole.json()["active"] == 0
    assert (await redeem(client, rider["headers"], body["codes"][2]["code"])).status_code == 422


async def test_a_card_outside_its_window_is_refused_without_counting(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    await client.put("/admin/taxo-cards/limits", json={"country_code": "DZ", "max_wrong_per_account": 1}, headers=admin_headers)
    later = await issue(client, admin_headers, quantity=1, starts_in=timedelta(days=2))
    rider = await rider_session(client, ALGERIAN_RIDER)
    early = await redeem(client, rider["headers"], later["codes"][0]["code"])
    assert early.status_code == 409 and early.json()["code"] == "taxo_card_not_usable_now"
    # **لم يُعدّ خطأً** — والسقفُ واحد: لو عُدّ لأُقفل الحسابُ الآن
    early_again = await redeem(client, rider["headers"], later["codes"][0]["code"])
    assert early_again.status_code == 409


async def test_without_the_secret_no_card_is_issued_or_used(
    client: AsyncClient, session_factory, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    await card_market(session_factory)
    monkeypatch.setattr(settings, "taxo_card_code_pepper", None)
    denom = await client.post("/admin/taxo-cards/denominations", json={"country_code": "DZ", "amount": "500"}, headers=admin_headers)
    made = await client.post("/admin/taxo-cards/batches", json={
        "country_code": "DZ", "denomination_id": denom.json()["id"], "quantity": 1,
        "valid_from": datetime.now(UTC).isoformat(), "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        headers=admin_headers)
    assert made.status_code == 503 and made.json()["code"] == "taxo_cards_not_configured"
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await redeem(client, rider["headers"], "ABCD-EFGH-JKMN-PQRS")).status_code == 503


async def test_cards_are_never_deleted(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    await issue(client, admin_headers, quantity=1)
    for table in ("taxo_cards", "card_batches"):
        async with session_factory() as session:
            with pytest.raises(Exception, match="never deleted"):
                await session.execute(text(f"DELETE FROM {table}"))


async def test_jordan_cannot_use_a_card(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=1)
    jordanian = await rider_session(client, RIDER)
    # **رمزٌ جزائريٌّ في يد أردنيّ رمزٌ غيرُ صحيح** — ولا يُعرف أنه موجودٌ في سوقٍ آخر
    refused = await redeem(client, jordanian["headers"], body["codes"][0]["code"])
    assert refused.status_code == 422 and refused.json()["message"] == "الرمزُ غيرُ صحيح"


def test_codes_are_drawn_from_an_unambiguous_alphabet() -> None:
    assert not set("0O1IL") & set(taxo_cards.ALPHABET)
    assert taxo_cards.normalize_code("abcd-efgh-jkmn-pqrs") == "ABCDEFGHJKMNPQRS"
    assert taxo_cards.normalize_code("ABCD-EFGH-JKMN-PQR0") is None
    assert taxo_cards.normalize_code("short") is None
