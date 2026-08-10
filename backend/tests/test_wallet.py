"""اختبارات دفتر المحفظة والشحن والتحويل (SPEC القسم 4/7/14)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text, update

from app.models.enums import CountryCode, FeatureKey, WalletOwnerType
from app.models.feature_flag import FeatureFlag
from app.models.wallet import WalletTransaction
from tests.helpers import (
    OTHER_RIDER,
    RIDER,
    TRANSFER_DAILY_LIMIT,
    auth,
    register,
    topup_wallet,
    wallet_of,
)

async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    body = await register(client, payload)
    return {"headers": auth(body), "user_id": body["user"]["id"], "body": body}


def _transfer_payload(phone: str, amount: str, key: str) -> dict:
    return {"recipient_phone": phone, "amount": amount, "idempotency_key": key}


# ------------------------------------------------------------------ الرصيد


async def test_new_wallet_is_empty(client: AsyncClient, jordan_wallet: None) -> None:
    rider = await _rider(client)
    body = await wallet_of(client, rider["headers"])

    assert body["balance"] == "0.000"
    assert body["currency"] == "JOD"
    assert body["owner_type"] == "rider"
    assert body["frozen"] is False


async def test_wallet_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/wallet/me")).status_code == 401


async def test_staff_account_has_no_wallet(
    client: AsyncClient, admin_headers: dict
) -> None:
    """المشرف يحرّك محافظ غيره ولا محفظة له."""
    response = await client.get("/wallet/me", headers=admin_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


# -------------------------------------------------------------------- الشحن


async def test_staff_topup_credits_balance_and_writes_ledger(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    rider = await _rider(client)
    await topup_wallet(client, admin_headers, rider["user_id"], "25.500")

    assert (await wallet_of(client, rider["headers"]))["balance"] == "25.500"

    entries = (await client.get("/wallet/me/transactions", headers=rider["headers"])).json()
    assert len(entries) == 1
    assert entries[0]["type"] == "topup"
    assert entries[0]["amount"] == "25.500"
    assert entries[0]["balance_after"] == "25.500"

    async with session_factory() as session:
        owner_type = await session.scalar(
            select(WalletTransaction.owner_type).where(
                WalletTransaction.owner_id == uuid.UUID(rider["user_id"])
            )
        )
    assert owner_type == WalletOwnerType.RIDER


async def test_rider_topup_request_credits_nothing_until_confirmed(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    rider = await _rider(client)

    created = await client.post(
        "/wallet/me/topups",
        json={"method": "cliq", "amount": "12.000", "reference": "CLQ-991"},
        headers=rider["headers"],
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["status"] == "pending"
    # الطلب المعلّق أثرٌ نصّي لا مالي
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"

    confirmed = await client.post(
        f"/admin/topups/{request_id}/confirm", headers=admin_headers
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["transaction_id"] is not None

    assert (await wallet_of(client, rider["headers"]))["balance"] == "12.000"


async def test_topup_request_needs_a_reference(
    client: AsyncClient, jordan_wallet: None
) -> None:
    rider = await _rider(client)
    response = await client.post(
        "/wallet/me/topups",
        json={"method": "cliq", "amount": "12.000", "reference": "  "},
        headers=rider["headers"],
    )
    assert response.status_code == 422


async def test_rider_cannot_open_a_cash_topup_request(
    client: AsyncClient, jordan_wallet: None
) -> None:
    """الكاش يُنشئه الموظف عند استلام المال — لا يعلنه الراكب عن نفسه."""
    rider = await _rider(client)
    response = await client.post(
        "/wallet/me/topups",
        json={"method": "cash", "amount": "12.000", "reference": "نقداً"},
        headers=rider["headers"],
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_rejected_topup_leaves_balance_untouched(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    rider = await _rider(client)
    created = await client.post(
        "/wallet/me/topups",
        json={"method": "cliq", "amount": "9.000", "reference": "CLQ-1"},
        headers=rider["headers"],
    )
    request_id = created.json()["id"]

    rejected = await client.post(
        f"/admin/topups/{request_id}/reject",
        json={"note": "لم تصل الحوالة"},
        headers=admin_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"

    # ولا يُؤكَّد بعد رفضه
    again = await client.post(
        f"/admin/topups/{request_id}/confirm", headers=admin_headers
    )
    assert again.status_code == 409
    assert again.json()["code"] == "invalid_status_transition"


async def test_topup_confirmation_is_not_repeatable(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    rider = await _rider(client)
    created = await client.post(
        "/wallet/me/topups",
        json={"method": "cliq", "amount": "9.000", "reference": "CLQ-2"},
        headers=rider["headers"],
    )
    request_id = created.json()["id"]

    assert (
        await client.post(f"/admin/topups/{request_id}/confirm", headers=admin_headers)
    ).status_code == 200
    repeat = await client.post(
        f"/admin/topups/{request_id}/confirm", headers=admin_headers
    )
    assert repeat.status_code == 409
    assert (await wallet_of(client, rider["headers"]))["balance"] == "9.000"


async def test_topup_blocked_where_wallet_feature_is_off(
    client: AsyncClient, driver_payload: dict
) -> None:
    """ليبيا كاش فقط: غياب صف المفتاح = معطّل، فلا شحن (SPEC القسم 4)."""
    body = await register(client, driver_payload)
    response = await client.post(
        "/wallet/me/topups",
        json={"method": "cliq", "amount": "5.000", "reference": "CLQ-LY-1"},
        headers=auth(body),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "feature_disabled"


# ------------------------------------------------------------------ التحويل


async def test_transfer_moves_money_between_riders(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    sender = await _rider(client)
    recipient = await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "30.000")

    response = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(OTHER_RIDER["phone"], "12.250", "key-transfer-1"),
        headers=sender["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["type"] == "transfer_out"
    assert response.json()["amount"] == "-12.250"
    assert response.json()["balance_after"] == "17.750"

    assert (await wallet_of(client, sender["headers"]))["balance"] == "17.750"
    assert (await wallet_of(client, recipient["headers"]))["balance"] == "12.250"

    incoming = (
        await client.get("/wallet/me/transactions", headers=recipient["headers"])
    ).json()
    assert incoming[0]["type"] == "transfer_in"
    assert incoming[0]["amount"] == "12.250"


async def test_transfer_is_idempotent(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    """إعادة إرسال نفس العملية لا تخصم مرتين (SPEC القسم 14)."""
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "30.000")

    payload = _transfer_payload(OTHER_RIDER["phone"], "10.000", "same-key-42")
    first = await client.post(
        "/wallet/me/transfers", json=payload, headers=sender["headers"]
    )
    second = await client.post(
        "/wallet/me/transfers", json=payload, headers=sender["headers"]
    )

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert (await wallet_of(client, sender["headers"]))["balance"] == "20.000"


async def test_transfer_rejected_when_balance_is_short(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "5.000")

    response = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(OTHER_RIDER["phone"], "6.000", "key-short"),
        headers=sender["headers"],
    )
    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_balance"
    assert (await wallet_of(client, sender["headers"]))["balance"] == "5.000"


async def test_transfer_respects_the_daily_limit(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "500.000")

    over_limit = Decimal(TRANSFER_DAILY_LIMIT) + Decimal("1.000")
    response = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(OTHER_RIDER["phone"], str(over_limit), "key-limit"),
        headers=sender["headers"],
    )
    assert response.status_code == 409
    assert response.json()["code"] == "wallet_limit_exceeded"

    # وما دون الحد يمر، ثم يستهلك ما بقي منه
    ok = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(OTHER_RIDER["phone"], TRANSFER_DAILY_LIMIT, "key-at-cap"),
        headers=sender["headers"],
    )
    assert ok.status_code == 200
    exhausted = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(OTHER_RIDER["phone"], "1.000", "key-after"),
        headers=sender["headers"],
    )
    assert exhausted.status_code == 409
    assert exhausted.json()["code"] == "wallet_limit_exceeded"


async def test_transfer_needs_its_feature_flag(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "30.000")

    async with session_factory() as session:
        await session.execute(
            update(FeatureFlag)
            .where(
                FeatureFlag.country_code == CountryCode.JO,
                FeatureFlag.feature_key == FeatureKey.WALLET_TRANSFER_ENABLED.value,
            )
            .values(enabled=False)
        )
        await session.commit()

    response = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(OTHER_RIDER["phone"], "5.000", "key-flagless"),
        headers=sender["headers"],
    )
    assert response.status_code == 403
    assert response.json()["code"] == "feature_disabled"


async def test_transfer_to_self_is_rejected(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    sender = await _rider(client)
    await topup_wallet(client, admin_headers, sender["user_id"], "30.000")

    response = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(RIDER["phone"], "5.000", "key-self"),
        headers=sender["headers"],
    )
    assert response.status_code == 422


async def test_transfer_to_a_driver_is_not_possible(
    client: AsyncClient,
    admin_headers: dict,
    jordan_wallet: None,
    session_factory,
) -> None:
    """راكب→راكب فقط (SPEC القسم 7) — ووجود الرقم ليس معلومة تُكشف."""
    from tests.helpers import DRIVER, approved_driver

    sender = await _rider(client)
    await approved_driver(client, session_factory)
    await topup_wallet(client, admin_headers, sender["user_id"], "30.000")

    response = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(DRIVER["phone"], "5.000", "key-driver"),
        headers=sender["headers"],
    )
    assert response.status_code == 404


async def test_recipient_lookup_shows_the_name_for_confirmation(
    client: AsyncClient, jordan_wallet: None
) -> None:
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)

    response = await client.get(
        "/wallet/transfer/recipient",
        params={"phone": OTHER_RIDER["phone"]},
        headers=sender["headers"],
    )
    assert response.status_code == 200
    assert response.json()["name"] == OTHER_RIDER["name"]
    assert response.json()["phone"] == "+962793333333"

    missing = await client.get(
        "/wallet/transfer/recipient",
        params={"phone": "0799999999"},
        headers=sender["headers"],
    )
    assert missing.status_code == 404


# ------------------------------------------------------------------ التجميد


async def test_frozen_wallet_can_neither_send_nor_be_topped_up(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "30.000")

    frozen = await client.post(
        f"/admin/wallets/{sender['user_id']}/freeze",
        json={"reason": "اشتباه"},
        headers=admin_headers,
    )
    assert frozen.status_code == 200
    assert frozen.json()["frozen"] is True

    transfer = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(OTHER_RIDER["phone"], "5.000", "key-frozen"),
        headers=sender["headers"],
    )
    assert transfer.status_code == 403
    assert transfer.json()["code"] == "wallet_frozen"

    topup = await client.post(
        "/wallet/me/topups",
        json={"method": "cliq", "amount": "5.000", "reference": "CLQ-9"},
        headers=sender["headers"],
    )
    assert topup.status_code == 403

    # الرصيد نفسه يبقى مقروءاً لصاحبه
    assert (await wallet_of(client, sender["headers"]))["balance"] == "30.000"

    unfrozen = await client.post(
        f"/admin/wallets/{sender['user_id']}/unfreeze",
        json={},
        headers=admin_headers,
    )
    assert unfrozen.json()["frozen"] is False
    assert (
        await client.post(
            "/wallet/me/transfers",
            json=_transfer_payload(OTHER_RIDER["phone"], "5.000", "key-thawed"),
            headers=sender["headers"],
        )
    ).status_code == 200


async def test_transfer_to_a_frozen_recipient_is_rejected(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    sender = await _rider(client)
    recipient = await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "30.000")
    await client.post(
        f"/admin/wallets/{recipient['user_id']}/freeze",
        json={},
        headers=admin_headers,
    )

    response = await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(OTHER_RIDER["phone"], "5.000", "key-frozen-in"),
        headers=sender["headers"],
    )
    assert response.status_code == 403
    assert response.json()["code"] == "wallet_frozen"


# ------------------------------------------------------------------ الدفتر


async def test_balance_after_follows_the_running_balance(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    """لا عمود رصيد: كل قيد يحمل لقطة الرصيد بعده، والمجموع هو المصدر."""
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "20.000")
    await topup_wallet(client, admin_headers, sender["user_id"], "5.000")
    await client.post(
        "/wallet/me/transfers",
        json=_transfer_payload(OTHER_RIDER["phone"], "7.000", "key-chain"),
        headers=sender["headers"],
    )

    entries = (
        await client.get("/wallet/me/transactions", headers=sender["headers"])
    ).json()
    assert [e["balance_after"] for e in entries] == ["18.000", "25.000", "20.000"]
    assert (await wallet_of(client, sender["headers"]))["balance"] == "18.000"


async def test_ledger_rows_cannot_be_updated_or_deleted(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """«سجل قيود غير قابل للتعديل» مفروضاً في القاعدة (SPEC القسم 4)."""
    rider = await _rider(client)
    await topup_wallet(client, admin_headers, rider["user_id"], "10.000")

    async with session_factory() as session:
        entry_id = await session.scalar(select(WalletTransaction.id))

    for statement in (
        text("UPDATE wallet_transactions SET amount = 1 WHERE id = :id"),
        text("DELETE FROM wallet_transactions WHERE id = :id"),
    ):
        async with session_factory() as session:
            with pytest.raises(Exception, match="append-only"):
                await session.execute(statement, {"id": entry_id})
            await session.rollback()
