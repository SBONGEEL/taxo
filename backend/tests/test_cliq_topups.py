"""شحن المحفظة بكليك الآلي عبر حساب التاجر (SPEC القسم 7/15-أ)."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.enums import WalletTransactionType
from app.models.wallet import WalletTransaction
from tests.helpers import (
    COMPANY_CLIQ_ALIAS,
    OTHER_RIDER,
    RIDER,
    enable_cliq_provider,
    enable_features,
    rider_session,
    wallet_of,
)

AMOUNT = "25.000"


async def _start(client: AsyncClient, headers: dict, amount: str = AMOUNT) -> dict:
    response = await client.post(
        "/wallet/me/topups/cliq", json={"amount": amount}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _settle(cart_id: str, outcome: str = "paid", amount: str | None = None):
    """يحاكي وصول الحوالة (أو عدم وصولها) عند حساب التاجر."""
    from app.services.cliq.mock import MockCliqProvider

    provider = MockCliqProvider(get_redis_client(), company_alias=COMPANY_CLIQ_ALIAS)
    await provider.set_outcome(
        cart_id, outcome, amount=Decimal(amount) if amount else None
    )


async def _check(client: AsyncClient, headers: dict, cart_id: str) -> dict:
    response = await client.get(
        f"/wallet/me/topups/cliq/{cart_id}", headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _topup_entries(session_factory, owner_id: str) -> list[WalletTransaction]:
    import uuid

    async with session_factory() as session:
        return list(
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.owner_id == uuid.UUID(owner_id),
                    WalletTransaction.type == WalletTransactionType.TOPUP,
                )
            )
        )


# ------------------------------------------------------------------ البوابة


async def test_cliq_topup_needs_the_acquirer_contract(
    client: AsyncClient, session_factory
) -> None:
    """بلا عقد: القناة اليدوية هي الطريق، ولا يُخترع مسارٌ آلي بلا شاهد."""
    await enable_features(session_factory, "wallet_enabled", "cliq_enabled")
    rider = await rider_session(client)

    response = await client.post(
        "/wallet/me/topups/cliq", json={"amount": AMOUNT}, headers=rider["headers"]
    )
    assert response.status_code == 503
    assert response.json()["code"] == "cliq_acquirer_unavailable"


async def test_cliq_topup_needs_the_wallet_feature(
    client: AsyncClient, session_factory
) -> None:
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)

    response = await client.post(
        "/wallet/me/topups/cliq", json={"amount": AMOUNT}, headers=rider["headers"]
    )
    assert response.status_code == 403


# ------------------------------------------------------------------ التدفق


async def test_start_returns_a_qr_and_credits_nothing_yet(
    client: AsyncClient, session_factory
) -> None:
    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)

    order = await _start(client, rider["headers"])
    assert order["status"] == "created"
    assert COMPANY_CLIQ_ALIAS in order["qr_payload"]
    assert AMOUNT in order["qr_payload"]
    assert order["deep_link"]
    assert order["transaction_id"] is None

    # لا رصيد يتغيّر قبل شهادة المزود
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"


async def test_pending_transfer_credits_nothing(
    client: AsyncClient, session_factory
) -> None:
    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)

    order = await _start(client, rider["headers"])
    checked = await _check(client, rider["headers"], order["cart_id"])

    assert checked["status"] == "created"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"


async def test_arrived_transfer_credits_the_wallet_once(
    client: AsyncClient, session_factory
) -> None:
    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)
    me = (await client.get("/auth/me", headers=rider["headers"])).json()

    order = await _start(client, rider["headers"])
    await _settle(order["cart_id"])

    settled = await _check(client, rider["headers"], order["cart_id"])
    assert settled["status"] == "paid"
    assert settled["transaction_id"] is not None
    assert (await wallet_of(client, rider["headers"]))["balance"] == AMOUNT

    # استعلامٌ ثانٍ لا يشحن مرتين
    await _check(client, rider["headers"], order["cart_id"])
    assert len(await _topup_entries(session_factory, me["id"])) == 1
    assert (await wallet_of(client, rider["headers"]))["balance"] == AMOUNT


async def test_failed_transfer_marks_the_order_failed(
    client: AsyncClient, session_factory
) -> None:
    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)

    order = await _start(client, rider["headers"])
    await _settle(order["cart_id"], "failed")

    settled = await _check(client, rider["headers"], order["cart_id"])
    assert settled["status"] == "failed"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"


async def test_amount_mismatch_does_not_credit_a_guess(
    client: AsyncClient, session_factory
) -> None:
    """مبلغٌ غير الذي فُتح به الطلب لا يُقيَّد بتخمين (SPEC القسم 6.4)."""
    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)

    order = await _start(client, rider["headers"])
    await _settle(order["cart_id"], "paid", amount="5.000")

    settled = await _check(client, rider["headers"], order["cart_id"])
    assert settled["status"] == "failed"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"


async def test_another_rider_cannot_read_or_settle_the_order(
    client: AsyncClient, session_factory
) -> None:
    """لا IDOR — ووجودُ طلبٍ مالي ليس معلومة يستحقها غير صاحبه."""
    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)
    other = await rider_session(client, OTHER_RIDER)

    order = await _start(client, rider["headers"])
    await _settle(order["cart_id"])

    response = await client.get(
        f"/wallet/me/topups/cliq/{order['cart_id']}", headers=other["headers"]
    )
    assert response.status_code == 404
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"


async def test_frozen_wallet_cannot_open_a_cliq_topup(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)
    me = (await client.get("/auth/me", headers=rider["headers"])).json()

    frozen = await client.post(
        f"/admin/wallets/{me['id']}/freeze",
        json={"frozen": True, "reason": "اشتباه"},
        headers=admin_headers,
    )
    assert frozen.status_code == 200, frozen.text

    response = await client.post(
        "/wallet/me/topups/cliq", json={"amount": AMOUNT}, headers=rider["headers"]
    )
    assert response.status_code == 403


async def test_ledger_sum_matches_the_single_credit(
    client: AsyncClient, session_factory
) -> None:
    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client, RIDER)
    me = (await client.get("/auth/me", headers=rider["headers"])).json()

    order = await _start(client, rider["headers"])
    await _settle(order["cart_id"])
    await _check(client, rider["headers"], order["cart_id"])

    import uuid

    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == uuid.UUID(me["id"])
            )
        )
    assert Decimal(total) == Decimal(AMOUNT)
