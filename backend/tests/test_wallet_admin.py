"""اختبارات السحب وإدارة المحافظ من اللوحة (SPEC القسم 9/13.3/13.5)."""

from __future__ import annotations

from httpx import AsyncClient, Response

from tests.helpers import (
    MIN_WITHDRAWAL,
    RIDER,
    approved_driver,
    auth,
    register,
    topup_wallet,
    wallet_of,
)


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    body = await register(client, payload)
    return {"headers": auth(body), "user_id": body["user"]["id"]}


async def _funded_driver(
    client: AsyncClient, session_factory, admin_headers: dict, amount: str = "100.000"
) -> dict:
    driver = await approved_driver(client, session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], amount)
    return driver


async def _request_withdrawal(
    client: AsyncClient, driver: dict, amount: str, method: str = "bank"
) -> Response:
    return await client.post(
        "/wallet/me/withdrawals",
        json={"amount": amount, "method": method},
        headers=driver["headers"],
    )


# ------------------------------------------------------------------ الصلاحيات


async def test_wallet_admin_requires_staff(
    client: AsyncClient, jordan_wallet: None
) -> None:
    rider = await _rider(client)
    blocked = await client.get(
        f"/admin/wallets/{rider['user_id']}", headers=rider["headers"]
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "permission_denied"


async def test_support_reads_wallets_but_cannot_move_money(
    client: AsyncClient, admin_headers: dict, support_headers: dict, jordan_wallet: None
) -> None:
    rider = await _rider(client)
    await topup_wallet(client, admin_headers, rider["user_id"], "10.000")

    readable = await client.get(
        f"/admin/wallets/{rider['user_id']}", headers=support_headers
    )
    assert readable.status_code == 200
    assert readable.json()["balance"] == "10.000"

    assert (
        await client.get(
            f"/admin/wallets/{rider['user_id']}/transactions", headers=support_headers
        )
    ).status_code == 200

    for path, payload in (
        (f"/admin/wallets/{rider['user_id']}/freeze", {}),
        (f"/admin/wallets/{rider['user_id']}/topups", {"method": "cash", "amount": "5.000"}),
        (
            f"/admin/wallets/{rider['user_id']}/adjustments",
            {"amount": "5.000", "reason": "تصحيح"},
        ),
    ):
        response = await client.post(path, json=payload, headers=support_headers)
        assert response.status_code == 403, path


# -------------------------------------------------------------------- السحب


async def test_withdrawal_debits_only_when_marked_paid(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await _funded_driver(client, session_factory, admin_headers)

    created = await _request_withdrawal(client, driver, "40.000")
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["status"] == "pending"
    # المال لم يخرج بعد — لا قيد قبل `paid` (SPEC القسم 9)
    assert (await wallet_of(client, driver["headers"]))["balance"] == "100.000"

    approved = await client.post(
        f"/admin/withdrawals/{request_id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200
    assert (await wallet_of(client, driver["headers"]))["balance"] == "100.000"

    paid = await client.post(
        f"/admin/withdrawals/{request_id}/paid",
        json={"reference": "CLQ-TRX-77"},
        headers=admin_headers,
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["reference"] == "CLQ-TRX-77"
    assert paid.json()["transaction_id"] is not None

    assert (await wallet_of(client, driver["headers"]))["balance"] == "60.000"
    entries = (
        await client.get("/wallet/me/transactions", headers=driver["headers"])
    ).json()
    assert entries[0]["type"] == "withdrawal"
    assert entries[0]["amount"] == "-40.000"


async def test_pending_withdrawal_reserves_the_balance(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """طلبان مفتوحان لا يسحبان نفس المال مرتين."""
    driver = await _funded_driver(client, session_factory, admin_headers)

    assert (await _request_withdrawal(client, driver, "70.000")).status_code == 201

    second = await _request_withdrawal(client, driver, "40.000")
    assert second.status_code == 409
    assert second.json()["code"] == "insufficient_balance"

    # وما يبقى ضمن المتاح يمر
    assert (await _request_withdrawal(client, driver, "30.000")).status_code == 201

    wallet = (await client.get("/wallet/me/driver", headers=driver["headers"])).json()
    assert wallet["balance"] == "100.000"
    assert wallet["available_for_withdrawal"] == "0.000"


async def test_withdrawal_below_the_minimum_is_rejected(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await _funded_driver(client, session_factory, admin_headers)

    response = await _request_withdrawal(client, driver, "1.000")
    assert response.status_code == 409
    assert response.json()["code"] == "wallet_limit_exceeded"

    assert (
        await _request_withdrawal(client, driver, MIN_WITHDRAWAL)
    ).status_code == 201


async def test_cliq_withdrawal_needs_an_alias(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await _funded_driver(client, session_factory, admin_headers)

    response = await _request_withdrawal(client, driver, "20.000", method="cliq")
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_rider_has_no_withdrawal_path(
    client: AsyncClient, jordan_wallet: None
) -> None:
    """الراكب يشحن ولا يسحب نهائياً (SPEC القسم 7)."""
    rider = await _rider(client)
    response = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": "10.000", "method": "bank"},
        headers=rider["headers"],
    )
    assert response.status_code == 403


async def test_rejected_withdrawal_frees_the_reserved_balance(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await _funded_driver(client, session_factory, admin_headers)
    created = await _request_withdrawal(client, driver, "100.000")
    request_id = created.json()["id"]

    rejected = await client.post(
        f"/admin/withdrawals/{request_id}/reject",
        json={"note": "بيانات الحساب ناقصة"},
        headers=admin_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    wallet = (await client.get("/wallet/me/driver", headers=driver["headers"])).json()
    assert wallet["available_for_withdrawal"] == "100.000"


async def test_withdrawal_transitions_are_guarded(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await _funded_driver(client, session_factory, admin_headers)
    request_id = (await _request_withdrawal(client, driver, "20.000")).json()["id"]

    # لا دفع قبل الاعتماد
    early = await client.post(
        f"/admin/withdrawals/{request_id}/paid",
        json={"reference": "X-1"},
        headers=admin_headers,
    )
    assert early.status_code == 409
    assert early.json()["code"] == "invalid_status_transition"

    await client.post(f"/admin/withdrawals/{request_id}/approve", headers=admin_headers)
    await client.post(
        f"/admin/withdrawals/{request_id}/paid",
        json={"reference": "X-1"},
        headers=admin_headers,
    )

    # ولا دفع مرتين
    repeat = await client.post(
        f"/admin/withdrawals/{request_id}/paid",
        json={"reference": "X-1"},
        headers=admin_headers,
    )
    assert repeat.status_code == 409
    assert (await wallet_of(client, driver["headers"]))["balance"] == "80.000"


async def test_admin_lists_withdrawals_by_status(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await _funded_driver(client, session_factory, admin_headers)
    await _request_withdrawal(client, driver, "20.000")

    listed = await client.get(
        "/admin/withdrawals", params={"status": "pending"}, headers=admin_headers
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    empty = await client.get(
        "/admin/withdrawals", params={"status": "paid"}, headers=admin_headers
    )
    assert empty.json() == []


# ---------------------------------------------------------------- التصحيح


async def test_adjustment_moves_the_balance_both_ways(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    rider = await _rider(client)
    await topup_wallet(client, admin_headers, rider["user_id"], "20.000")

    credit = await client.post(
        f"/admin/wallets/{rider['user_id']}/adjustments",
        json={"amount": "5.000", "reason": "تعويض"},
        headers=admin_headers,
    )
    assert credit.status_code == 200
    assert credit.json()["balance_after"] == "25.000"

    debit = await client.post(
        f"/admin/wallets/{rider['user_id']}/adjustments",
        json={"amount": "-10.000", "reason": "تصحيح شحنة"},
        headers=admin_headers,
    )
    assert debit.json()["balance_after"] == "15.000"


async def test_adjustment_cannot_push_the_balance_negative(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    rider = await _rider(client)
    await topup_wallet(client, admin_headers, rider["user_id"], "5.000")

    response = await client.post(
        f"/admin/wallets/{rider['user_id']}/adjustments",
        json={"amount": "-9.000", "reason": "تصحيح"},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_balance"


async def test_admin_actions_are_audited(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    rider = await _rider(client)
    await client.post(
        f"/admin/wallets/{rider['user_id']}/freeze",
        json={"reason": "اشتباه"},
        headers=admin_headers,
    )

    logs = await client.get(
        "/admin/settings/audit-logs",
        params={"entity_type": "wallet"},
        headers=admin_headers,
    )
    assert logs.status_code == 200
    assert logs.json()[0]["details"]["wallet_frozen"] is True


# ------------------------------------------------------------ حدود المحفظة


async def test_admin_edits_wallet_limits(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    updated = await client.patch(
        "/admin/settings/wallet/JO",
        json={"transfer_daily_limit": "75.000", "min_withdrawal_amount": "3.000"},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["transfer_daily_limit"] == "75.000"
    assert updated.json()["min_withdrawal_amount"] == "3.000"
    # ما لم يُرسل لا يُمس
    assert updated.json()["transfer_monthly_limit"] == "0.000"

    listed = await client.get("/admin/settings/wallet", headers=support_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    blocked = await client.patch(
        "/admin/settings/wallet/JO",
        json={"transfer_daily_limit": "1.000"},
        headers=support_headers,
    )
    assert blocked.status_code == 403


async def test_transfer_blocked_while_limits_are_unset(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """حدٌّ صفريٌّ يعني «لم يُضبط» — والرسالة تقول ذلك بدل «تجاوزت صفراً»."""
    from app.models.enums import CountryCode, FeatureKey
    from app.models.feature_flag import FeatureFlag
    from tests.helpers import OTHER_RIDER

    async with session_factory() as session:
        for key in (FeatureKey.WALLET_ENABLED, FeatureKey.WALLET_TRANSFER_ENABLED):
            session.add(
                FeatureFlag(
                    country_code=CountryCode.JO, feature_key=key.value, enabled=True
                )
            )
        await session.commit()

    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "30.000")

    response = await client.post(
        "/wallet/me/transfers",
        json={
            "recipient_phone": OTHER_RIDER["phone"],
            "amount": "5.000",
            "idempotency_key": "key-unset-limits",
        },
        headers=sender["headers"],
    )
    assert response.status_code == 409
    assert response.json()["code"] == "wallet_limit_exceeded"
    assert "غير مضبوطة" in response.json()["message"]


async def test_a_staff_topup_needs_a_written_reference(
    client, admin_headers, jordan_wallet
) -> None:
    """**مالٌ يدخل رصيداً بقرارِ موظف** — فما يُطابَق به الإيصالُ الورقيُّ إلزاميّ.

    وحرسُه في المخطط لا في الشاشة: قاعدةٌ تعيش في زرٍّ وحدَه يلتفّ عليها أيُّ
    نداءٍ آخر — وهو الشكلُ الذي أغلقناه في `detail` وفي قواعد التحقق.
    """
    rider = await _rider(client)

    bare = await client.post(
        f"/admin/wallets/{rider['user_id']}/topups",
        json={"method": "cash", "amount": "5.000"},
        headers=admin_headers,
    )
    assert bare.status_code == 422, bare.text

    short = await client.post(
        f"/admin/wallets/{rider['user_id']}/topups",
        json={"method": "cash", "amount": "5.000", "reference": "أ"},
        headers=admin_headers,
    )
    assert short.status_code == 422, short.text

    ok = await client.post(
        f"/admin/wallets/{rider['user_id']}/topups",
        json={"method": "cash", "amount": "5.000", "reference": "إيصال 4471"},
        headers=admin_headers,
    )
    assert ok.status_code == 200, ok.text


async def test_a_staff_topup_lands_in_the_audit_log(
    client, admin_headers, session_factory, jordan_wallet
) -> None:
    """قرارُ موظفٍ يحرّك مالاً يُسأل عنه بعد شهر — فله صفٌّ باسم فاعله."""
    from sqlalchemy import select

    from app.models.audit import AdminAuditLog
    from tests.helpers import topup_wallet

    rider = await _rider(client)
    await topup_wallet(client, admin_headers, rider["user_id"], "7.000")

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "wallet_topup_request"
                )
            )
        ).all()
    assert rows, "شحنٌ إداريٌّ بلا صفِّ تدقيق"
    assert rows[-1].actor_id is not None


async def test_an_adjustment_needs_a_written_reason_and_is_audited(
    client, admin_headers, session_factory, jordan_wallet
) -> None:
    """**المخرجُ الوحيد لتصحيح دفترٍ لا يُعدَّل** — ولا يُفتح بلا «لماذا».

    و`wallet_transactions` عليها مُطلِقٌ يرفض `UPDATE` و`DELETE` (هجرة `0006`)،
    فهذا البابُ هو كلُّ ما يملكه المشرفُ لتصحيح خطأ. وزرٌّ يقيّد بلا سببٍ يجعل
    الدفترَ صحيحاً حسابياً وغيرَ مقروءٍ بشرياً.
    """
    from sqlalchemy import select

    from app.models.audit import AdminAuditLog
    from tests.helpers import topup_wallet

    rider = await _rider(client)
    await topup_wallet(client, admin_headers, rider["user_id"], "10.000")

    bare = await client.post(
        f"/admin/wallets/{rider['user_id']}/adjustments",
        json={"amount": "2.000"},
        headers=admin_headers,
    )
    assert bare.status_code == 422, bare.text

    ok = await client.post(
        f"/admin/wallets/{rider['user_id']}/adjustments",
        json={"amount": "2.000", "reason": "تصحيح خطأ إدخال"},
        headers=admin_headers,
    )
    assert ok.status_code == 200, ok.text

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "wallet_transaction"
                )
            )
        ).all()
    assert rows, "قيدُ تصحيحٍ بلا صفِّ تدقيق"
    # **ولا قيمةَ في `details`** — أسماءُ الحقول وحدَها (SPEC القسم ١٤)
    assert "amount" not in rows[-1].details
    assert "2.000" not in str(rows[-1].details)
