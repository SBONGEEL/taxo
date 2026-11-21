"""**التحويلُ بين الدول** (أمرُ المالك ٢٠٢٦-١١-٢٢، `design/OWNER-2026-11-22-CROSS-TRANSFER.md`).

ما يُقاس هنا: **المفتاحُ مطفأٌ افتراضاً ويُشترط في الدولتين**، والعرضُ محسوبٌ في الخلفية بعملتَي الطرفين، **وثلاثةُ قيودٍ بسعرها** مع صفِّ
`cross_transfers` وقيدِ تدقيق، **والتحويلُ داخل الدولة كما كان**، والحدودُ والسعرُ الغائبُ يردّان. **والتزامنُ**: رصيدٌ يكفي اثنين وحدٌّ يكفي
اثنين — أربعةُ طلباتٍ معاً ينجح منها اثنان لا أكثر.

**والأسعارُ والحدودُ هنا قيمُ اختبارٍ في قاعدة الاختبار** — لا سعرَ حقيقيّاً يُكتب في أيِّ بيئةٍ أخرى (شرطُ المالك).
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.cross_transfer import CrossTransfer, CrossTransferLimit, FxRate
from app.models.enums import CountryCode, Currency, FeatureKey, WalletTransactionType
from app.models.feature_flag import FeatureFlag
from app.models.wallet import WalletTransaction
from tests.helpers import OTHER_RIDER, RIDER, rider_session, topup_wallet, wallet_of

ALGERIAN = RIDER | {"phone": "0551234567", "country_code": "DZ", "name": "سارة بن علي"}
ALGERIAN_INTL = "+213551234567"


async def _open(session_factory, *, cross: bool = True, rate: str | None = "190.5", fee: str = "2",
                daily: str = "50.000", monthly: str = "200.000") -> None:
    async with session_factory() as session:
        for country in (CountryCode.JO, CountryCode.DZ):
            session.add(FeatureFlag(country_code=country, feature_key=FeatureKey.CROSS_COUNTRY_TRANSFER.value, enabled=cross))
        session.add(FeatureFlag(country_code=CountryCode.DZ, feature_key=FeatureKey.WALLET_ENABLED.value, enabled=True))
        if rate is not None:
            session.add(FxRate(from_currency=Currency.JOD, to_currency=Currency.DZD, rate=Decimal(rate),
                               fee_percent=Decimal(fee), set_at=datetime.now(UTC)))
        session.add(CrossTransferLimit(country_code=CountryCode.JO, daily_limit=Decimal(daily), monthly_limit=Decimal(monthly)))
        await session.commit()


async def _pair(client: AsyncClient, admin_headers: dict, funds: str = "30.000") -> tuple[dict, dict]:
    sender = await rider_session(client, RIDER)
    recipient = await rider_session(client, ALGERIAN)
    await topup_wallet(client, admin_headers, sender["user"]["id"], funds)
    return sender, recipient


def _send(headers: dict, amount: str, key: str, expected: str | None = None) -> dict:
    body = {"recipient_phone": ALGERIAN_INTL, "amount": amount, "idempotency_key": key}
    if expected is not None:
        body["expected_received"] = expected
    return {"json": body, "headers": headers}


async def test_the_switch_is_off_by_default_and_the_name_stays_hidden(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    await _open(session_factory, cross=False)
    sender, _ = await _pair(client, admin_headers)
    lookup = await client.get("/wallet/transfer/recipient", params={"phone": ALGERIAN_INTL}, headers=sender["headers"])
    assert lookup.status_code == 403, lookup.text
    assert "سارة" not in lookup.text
    sent = await client.post("/wallet/me/transfers", **_send(sender["headers"], "10.000", "cross-off-1"))
    assert sent.status_code == 403, sent.text


async def test_one_country_on_is_not_enough(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    await _open(session_factory)
    async with session_factory() as session:
        flag = await session.scalar(select(FeatureFlag).where(
            FeatureFlag.country_code == CountryCode.DZ, FeatureFlag.feature_key == FeatureKey.CROSS_COUNTRY_TRANSFER.value))
        flag.enabled = False
        await session.commit()
    sender, _ = await _pair(client, admin_headers)
    lookup = await client.get("/wallet/transfer/recipient", params={"phone": ALGERIAN_INTL}, headers=sender["headers"])
    assert lookup.status_code == 403, lookup.text


async def test_lookup_and_quote_show_both_currencies_and_a_masked_name(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    await _open(session_factory)
    sender, _ = await _pair(client, admin_headers)
    lookup = await client.get("/wallet/transfer/recipient", params={"phone": "00213551234567"}, headers=sender["headers"])
    assert lookup.status_code == 200, lookup.text
    assert lookup.json() | {} == {"phone": ALGERIAN_INTL, "name": "سارة ب. ع.", "country_code": "DZ", "cross": True}

    quote = await client.get("/wallet/transfer/quote", params={"phone": ALGERIAN_INTL, "amount": "10.000"},
                             headers=sender["headers"])
    assert quote.status_code == 200, quote.text
    body = quote.json()
    assert body["send"] == {"currency": "JOD", "amount": "10.000", "fee": "0.200", "total": "10.200", "balance_after": "19.800"}
    # ‎10 × 190.5 = 1905 دينارٍ جزائريٍّ صحيح — **وبصيغة عملته** على السلك
    assert body["receive"] == {"currency": "DZD", "amount": "1905"}
    assert body["rate"] == "190.5" and body["fee_percent"] == "2" and body["recipient_name"] == "سارة ب. ع."


async def test_same_country_lookup_is_unchanged(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    await _open(session_factory)
    sender = await rider_session(client, RIDER)
    await rider_session(client, OTHER_RIDER)
    lookup = await client.get("/wallet/transfer/recipient", params={"phone": OTHER_RIDER["phone"]}, headers=sender["headers"])
    assert lookup.status_code == 200, lookup.text
    assert lookup.json()["name"] == OTHER_RIDER["name"] and lookup.json()["cross"] is False


async def test_a_transfer_writes_three_entries_with_its_rate_and_an_audit_row(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    await _open(session_factory)
    sender, recipient = await _pair(client, admin_headers)
    sent = await client.post("/wallet/me/transfers", **_send(sender["headers"], "10.000", "cross-ok-1", "1905"))
    assert sent.status_code == 200, sent.text
    assert sent.json()["type"] == "cross_transfer_out"
    # **والإعادةُ بالمفتاح نفسِه لا تحوّل مرّتين**
    again = await client.post("/wallet/me/transfers", **_send(sender["headers"], "10.000", "cross-ok-1", "1905"))
    assert again.status_code == 200 and again.json()["id"] == sent.json()["id"]

    assert (await wallet_of(client, sender["headers"]))["balance"] == "19.800"
    assert (await wallet_of(client, recipient["headers"]))["balance"] == "1905"
    async with session_factory() as session:
        rows = (await session.scalars(select(CrossTransfer))).all()
        assert len(rows) == 1
        row = rows[0]
        assert (row.amount, row.fee, row.received, row.rate) == (
            Decimal("10.000"), Decimal("0.200"), Decimal("1905.000"), Decimal("190.50000000"))
        types = Counter((await session.scalars(select(WalletTransaction.type).where(
            WalletTransaction.id.in_([row.out_transaction_id, row.in_transaction_id, row.fee_transaction_id])))).all())
        assert types == Counter({WalletTransactionType.CROSS_TRANSFER_OUT: 1, WalletTransactionType.CROSS_TRANSFER_IN: 1,
                                 WalletTransactionType.CROSS_TRANSFER_FEE: 1})
        audits = await session.scalar(select(func.count()).select_from(AdminAuditLog).where(
            AdminAuditLog.entity_type == "cross_transfer", AdminAuditLog.entity_id == row.id))
        assert audits == 1


async def test_a_changed_rate_refuses_instead_of_sending_a_different_amount(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    await _open(session_factory)
    sender, _ = await _pair(client, admin_headers)
    sent = await client.post("/wallet/me/transfers", **_send(sender["headers"], "10.000", "cross-moved-1", "1900"))
    assert sent.status_code == 409, sent.text
    assert (await wallet_of(client, sender["headers"]))["balance"] == "30.000"


@pytest.mark.parametrize("missing", ["rate", "limits"])
async def test_no_rate_or_no_limits_refuses(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory, missing: str
) -> None:
    await _open(session_factory, rate=None if missing == "rate" else "190.5",
                daily="0" if missing == "limits" else "50.000")
    sender, _ = await _pair(client, admin_headers)
    sent = await client.post("/wallet/me/transfers", **_send(sender["headers"], "10.000", f"cross-missing-{missing}"))
    assert sent.status_code in (409, 422), sent.text
    assert (await wallet_of(client, sender["headers"]))["balance"] == "30.000"


async def test_the_daily_limit_counts_cross_transfers_only(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    await _open(session_factory, daily="15.000", fee="0")
    sender, _ = await _pair(client, admin_headers)
    first = await client.post("/wallet/me/transfers", **_send(sender["headers"], "10.000", "cross-limit-1"))
    assert first.status_code == 200, first.text
    second = await client.post("/wallet/me/transfers", **_send(sender["headers"], "10.000", "cross-limit-2"))
    assert second.status_code == 409, second.text
    # **وحدُّ التحويل داخل الدولة لم يُستهلك** — تحويلٌ إلى أردنيٍّ يمرّ كما كان
    await rider_session(client, OTHER_RIDER)
    local = await client.post("/wallet/me/transfers", json={"recipient_phone": OTHER_RIDER["phone"], "amount": "5.000",
                                                              "idempotency_key": "local-after-cross"}, headers=sender["headers"])
    assert local.status_code == 200, local.text
    assert local.json()["type"] == "transfer_out"


async def test_the_panel_sets_a_rate_with_its_date_and_an_audit_row(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    listed = await client.get("/admin/cross-transfer/rates", headers=admin_headers)
    assert listed.status_code == 200 and len(listed.json()) == 6
    assert all(row["rate"] is None for row in listed.json())
    put = await client.put("/admin/cross-transfer/rates", headers=admin_headers,
                           json={"from_currency": "LYD", "to_currency": "JOD", "rate": "0.145", "fee_percent": "1.5"})
    assert put.status_code == 200, put.text
    assert put.json()["rate"] == "0.145" and put.json()["set_at"] is not None
    limits = await client.put("/admin/cross-transfer/limits/LY", headers=admin_headers,
                              json={"daily_limit": "100.000", "monthly_limit": "1000.000"})
    assert limits.status_code == 200, limits.text
    bad = await client.put("/admin/cross-transfer/limits/LY", headers=admin_headers,
                           json={"daily_limit": "500.000", "monthly_limit": "100.000"})
    assert bad.status_code == 422, bad.text
    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(AdminAuditLog).where(
            AdminAuditLog.entity_type.in_(["fx_rate", "cross_transfer_limit"])))
        assert count == 2


# ------------------------------------------------------------------ التزامن


async def _ledger_sum(session_factory, user_id: str) -> Decimal:
    async with session_factory() as session:
        return Decimal(await session.scalar(select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.owner_id == uuid.UUID(user_id))))


async def test_concurrent_cross_transfers_cannot_overdraw(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """رصيدٌ يكفي اثنين (٢٥ لعشرةٍ بلا رسم) — أربعةٌ معاً، ينجح اثنان، **ولا رصيدَ سالبٌ ولا واصلٌ بلا مرسَل**."""
    await _open(session_factory, fee="0", daily="1000.000", monthly="1000.000")
    sender, recipient = await _pair(client, admin_headers, funds="25.000")
    responses = await asyncio.wait_for(asyncio.gather(*(
        client.post("/wallet/me/transfers", **_send(sender["headers"], "10.000", f"cross-race-{i}")) for i in range(4)
    )), timeout=30)
    statuses = Counter(r.status_code for r in responses)
    assert statuses[200] == 2, statuses
    assert await _ledger_sum(session_factory, sender["user"]["id"]) == Decimal("5.000")
    assert await _ledger_sum(session_factory, recipient["user"]["id"]) == Decimal("3810.000")
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(CrossTransfer)) == 2
        negative = await session.scalar(select(func.count()).select_from(WalletTransaction).where(WalletTransaction.balance_after < 0))
        assert negative == 0


async def test_concurrent_cross_transfers_respect_the_daily_limit(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """حدٌّ يوميٌّ يكفي اثنين (٢٠ لعشرة) ورصيدٌ يكفي الأربعة — ينجح اثنان، **والحدُّ يُقرأ تحت القفل** لا قبله."""
    await _open(session_factory, fee="0", daily="20.000", monthly="1000.000")
    sender, _ = await _pair(client, admin_headers, funds="100.000")
    responses = await asyncio.wait_for(asyncio.gather(*(
        client.post("/wallet/me/transfers", **_send(sender["headers"], "10.000", f"cross-limit-race-{i}")) for i in range(4)
    )), timeout=30)
    statuses = Counter(r.status_code for r in responses)
    assert statuses == Counter({200: 2, 409: 2}), statuses
    assert await _ledger_sum(session_factory, sender["user"]["id"]) == Decimal("80.000")
