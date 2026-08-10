"""التحويل الآلي للسحوبات عبر مزود payout (SPEC القسم 9/15-أ)."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.enums import WalletTransactionType
from app.models.wallet import WalletTransaction
from tests.helpers import (
    approved_driver,
    enable_payout_provider,
    set_cliq_alias,
    topup_wallet,
)

BALANCE = "80.000"
AMOUNT = "30.000"


async def _approved_request(
    client: AsyncClient, driver: dict, admin_headers: dict, *, method: str = "cliq"
) -> str:
    created = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": AMOUNT, "method": method},
        headers=driver["headers"],
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    approved = await client.post(
        f"/admin/withdrawals/{request_id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200, approved.text
    return request_id


async def _ready_driver(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> dict:
    driver = await approved_driver(client, session_factory)
    await set_cliq_alias(session_factory, driver["driver_id"])
    await topup_wallet(client, admin_headers, driver["user_id"], BALANCE)
    return driver


async def _withdrawal_entries(session_factory, user_id: str) -> list[WalletTransaction]:
    import uuid

    async with session_factory() as session:
        return list(
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.owner_id == uuid.UUID(user_id),
                    WalletTransaction.type == WalletTransactionType.WITHDRAWAL,
                )
            )
        )


async def test_payout_pays_and_writes_one_ledger_entry(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    await enable_payout_provider(session_factory)
    driver = await _ready_driver(client, session_factory, admin_headers, jordan_wallet)
    request_id = await _approved_request(client, driver, admin_headers)

    response = await client.post(
        f"/admin/withdrawals/{request_id}/payout", headers=admin_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["paid"] is True
    assert body["request"]["status"] == "paid"
    # مرجعُ المزود هو ما يُحفظ: التحويل حدث عنده لا عندنا
    assert body["request"]["reference"].startswith("mock-payout-")

    entries = await _withdrawal_entries(session_factory, driver["user_id"])
    assert len(entries) == 1
    assert entries[0].amount == Decimal(f"-{AMOUNT}")


async def test_payout_requires_the_contract(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    """بلا عقد يبقى المسار اليدوي — ولا يُعلَّم الطلب مدفوعاً بحال."""
    driver = await _ready_driver(client, session_factory, admin_headers, jordan_wallet)
    request_id = await _approved_request(client, driver, admin_headers)

    response = await client.post(
        f"/admin/withdrawals/{request_id}/payout", headers=admin_headers
    )
    assert response.status_code == 503
    assert response.json()["code"] == "payout_unavailable"
    assert await _withdrawal_entries(session_factory, driver["user_id"]) == []


async def test_provider_rejection_leaves_the_request_approved(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    from app.services.payout.mock import MockPayoutProvider

    await enable_payout_provider(session_factory)
    driver = await _ready_driver(client, session_factory, admin_headers, jordan_wallet)
    request_id = await _approved_request(client, driver, admin_headers)

    provider = MockPayoutProvider(get_redis_client())
    await provider.set_outcome(f"withdrawal:{request_id}", "failed")

    response = await client.post(
        f"/admin/withdrawals/{request_id}/payout", headers=admin_headers
    )
    assert response.status_code == 502
    assert await _withdrawal_entries(session_factory, driver["user_id"]) == []

    listed = (
        await client.get("/admin/withdrawals", headers=admin_headers)
    ).json()
    assert listed[0]["status"] == "approved"


async def test_pending_payout_writes_no_entry(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    """«طلبنا التحويل» ليست «حوّلنا» — لا قيد على ما لم يُحسم."""
    from app.services.payout.mock import MockPayoutProvider

    await enable_payout_provider(session_factory)
    driver = await _ready_driver(client, session_factory, admin_headers, jordan_wallet)
    request_id = await _approved_request(client, driver, admin_headers)

    provider = MockPayoutProvider(get_redis_client())
    await provider.set_outcome(f"withdrawal:{request_id}", "pending")

    response = await client.post(
        f"/admin/withdrawals/{request_id}/payout", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["paid"] is False
    assert response.json()["request"]["status"] == "approved"
    assert await _withdrawal_entries(session_factory, driver["user_id"]) == []


async def test_payout_needs_an_approved_request(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    await enable_payout_provider(session_factory)
    driver = await _ready_driver(client, session_factory, admin_headers, jordan_wallet)

    created = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": AMOUNT, "method": "cliq"},
        headers=driver["headers"],
    )
    request_id = created.json()["id"]

    response = await client.post(
        f"/admin/withdrawals/{request_id}/payout", headers=admin_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_status_transition"


async def test_bank_withdrawals_stay_manual(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    """لا عمود لحسابٍ بنكي في `drivers` — ووجهةٌ نخترعها حوالةٌ إلى لا مكان."""
    await enable_payout_provider(session_factory)
    driver = await _ready_driver(client, session_factory, admin_headers, jordan_wallet)
    request_id = await _approved_request(client, driver, admin_headers, method="bank")

    response = await client.post(
        f"/admin/withdrawals/{request_id}/payout", headers=admin_headers
    )
    assert response.status_code == 422
    assert await _withdrawal_entries(session_factory, driver["user_id"]) == []


async def test_payout_is_admin_only(
    client: AsyncClient,
    session_factory,
    admin_headers: dict,
    support_headers: dict,
    jordan_wallet,
) -> None:
    await enable_payout_provider(session_factory)
    driver = await _ready_driver(client, session_factory, admin_headers, jordan_wallet)
    request_id = await _approved_request(client, driver, admin_headers)

    denied = await client.post(
        f"/admin/withdrawals/{request_id}/payout", headers=support_headers
    )
    assert denied.status_code == 403


async def test_balance_after_payout_matches_the_ledger(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    import uuid

    await enable_payout_provider(session_factory)
    driver = await _ready_driver(client, session_factory, admin_headers, jordan_wallet)
    request_id = await _approved_request(client, driver, admin_headers)
    await client.post(
        f"/admin/withdrawals/{request_id}/payout", headers=admin_headers
    )

    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == uuid.UUID(driver["user_id"])
            )
        )
    assert Decimal(total) == Decimal(BALANCE) - Decimal(AMOUNT)
