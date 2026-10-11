"""سحبُ الكابتن الجزائريّ (SPEC §٧٣-هـ المرحلة ٤) — **قنواتُه الأربع على نمط السحب القائم وحالاته، والقيدُ في الدفتر عند الدفع وحدَه**.

**وما يُقاس هنا ثلاثة**: الجزائرُ تقبل قنواتِها ووجهتُها مجمَّدةٌ على الطلب · **الأردنُ وليبيا كما كانا حرفاً** (كليك والبنك، ولا وجهةَ تُكتب)
· **ودفعتان متزامنتان لطلبٍ واحدٍ تقيّدان مرّةً** — بقفل صفِّ الطلب القائم لا بشيءٍ جديد.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import CountryCode, FeatureKey, WalletTransactionType
from app.models.feature_flag import FeatureFlag
from app.models.wallet import WalletTransaction, WithdrawalRequest
from tests.helpers import approved_driver, auth, register, set_cliq_alias, topup_wallet
from tests.test_payment_requests import ALGERIAN_DRIVER

RIP = "00799999001234567890"
RIB = "00100123 0012345678 90"
CCP = "0012345678 clé 90"


async def _algerian_captain(client: AsyncClient, session_factory, admin_headers: dict, balance: str = "20000") -> dict:
    async with session_factory() as session:
        session.add(FeatureFlag(country_code=CountryCode.DZ, feature_key=FeatureKey.WALLET_ENABLED.value, enabled=True))
        await session.commit()
    # **كابتنٌ مسجَّلٌ يكفي**: السحبُ لا يشترط الاعتماد (`CurrentDriver`)، والمركبةُ لا شأنَ لها بالمال
    body = await register(client, ALGERIAN_DRIVER)
    captain = {"headers": auth(body), "user_id": body["user"]["id"]}
    await topup_wallet(client, admin_headers, captain["user_id"], balance)
    return captain


async def _withdraw(client: AsyncClient, captain: dict, method: str, amount: str = "5000", **destination: str):
    return await client.post(
        "/wallet/me/withdrawals", json={"amount": amount, "method": method, **destination}, headers=captain["headers"]
    )


async def _withdrawal_entries(session_factory, user_id: str) -> list[WalletTransaction]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.owner_id == uuid.UUID(user_id),
                    WalletTransaction.type == WalletTransactionType.WITHDRAWAL,
                )
            )
        )


async def test_the_algerian_captain_sees_his_four_channels_and_no_cliq(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    captain = await _algerian_captain(client, session_factory, admin_headers)
    wallet = (await client.get("/wallet/me/driver", headers=captain["headers"])).json()
    assert wallet["withdrawal_methods"] == ["baridimob", "ccp", "bank", "cash_office"]
    refused = await _withdraw(client, captain, "cliq")
    assert refused.status_code == 422 and "لا تُتاح في بلدك" in refused.json()["message"]


async def test_each_channel_freezes_its_destination_on_the_request(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    captain = await _algerian_captain(client, session_factory, admin_headers)
    made = {
        "baridimob": await _withdraw(client, captain, "baridimob", "1000", payout_account=RIP, payout_holder="  أمين   بن علي "),
        "ccp": await _withdraw(client, captain, "ccp", "1000", payout_account=CCP, payout_holder="أمين بن علي"),
        "bank": await _withdraw(client, captain, "bank", "1000", payout_account=RIB, payout_holder="أمين بن علي"),
        "cash_office": await _withdraw(client, captain, "cash_office", "1000", payout_account="ignored", payout_holder="x"),
    }
    for method, response in made.items():
        assert response.status_code == 201, (method, response.text)
    assert made["baridimob"].json()["payout_account"] == RIP
    assert made["baridimob"].json()["payout_holder"] == "أمين بن علي"
    assert made["ccp"].json()["payout_account"] == "0012345678 90"
    assert made["bank"].json()["payout_account"] == "00100123001234567890"
    assert made["cash_office"].json()["payout_account"] is None and made["cash_office"].json()["payout_holder"] is None
    listed = (await client.get("/admin/withdrawals", headers=admin_headers)).json()
    assert {row["method"]: row["payout_account"] for row in listed} == {
        "baridimob": RIP, "ccp": "0012345678 90", "bank": "00100123001234567890", "cash_office": None,
    }


async def test_a_wrong_or_missing_destination_is_refused_before_anything_is_written(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    captain = await _algerian_captain(client, session_factory, admin_headers)
    short_rip = await _withdraw(client, captain, "baridimob", payout_account=RIP[:-1], payout_holder="أمين بن علي")
    assert short_rip.status_code == 422 and "RIP" in short_rip.json()["message"]
    letters = await _withdraw(client, captain, "bank", payout_account="FR76 3000 6000 0112 3456 7890 189", payout_holder="أمين")
    assert letters.status_code == 422 and "RIB" in letters.json()["message"]
    no_holder = await _withdraw(client, captain, "ccp", payout_account=CCP)
    assert no_holder.status_code == 422 and "صاحب الحساب" in no_holder.json()["message"]
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(WithdrawalRequest)) == 0


async def test_the_full_cycle_debits_the_ledger_once_at_paid(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    captain = await _algerian_captain(client, session_factory, admin_headers)
    request_id = (await _withdraw(client, captain, "baridimob", payout_account=RIP, payout_holder="أمين بن علي")).json()["id"]
    assert await _withdrawal_entries(session_factory, captain["user_id"]) == []
    approved = await client.post(f"/admin/withdrawals/{request_id}/approve", headers=admin_headers)
    assert approved.status_code == 200, approved.text
    # **وكليكُ وحدَها آليّة** — قناةٌ جزائريّةٌ تُصرف بيد الموظّف ثمّ تُعلَّم مدفوعة
    automatic = await client.post(f"/admin/withdrawals/{request_id}/payout", headers=admin_headers)
    assert automatic.status_code == 422
    paid = await client.post(
        f"/admin/withdrawals/{request_id}/paid", json={"reference": "BM-REF-77"}, headers=admin_headers
    )
    assert paid.status_code == 200, paid.text
    entries = await _withdrawal_entries(session_factory, captain["user_id"])
    assert [str(entry.amount) for entry in entries] == ["-5000.000"]
    wallet = (await client.get("/wallet/me/driver", headers=captain["headers"])).json()
    assert wallet["balance"] == "15000"


async def test_cash_at_the_office_follows_the_same_statuses(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    captain = await _algerian_captain(client, session_factory, admin_headers)
    request_id = (await _withdraw(client, captain, "cash_office", "3000")).json()["id"]
    assert (await client.post(f"/admin/withdrawals/{request_id}/approve", headers=admin_headers)).status_code == 200
    paid = await client.post(
        f"/admin/withdrawals/{request_id}/paid", json={"reference": "وصلُ المكتب 12"}, headers=admin_headers
    )
    assert paid.status_code == 200 and paid.json()["status"] == "paid"
    assert [str(e.amount) for e in await _withdrawal_entries(session_factory, captain["user_id"])] == ["-3000.000"]


async def test_two_paid_marks_at_once_debit_once(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    captain = await _algerian_captain(client, session_factory, admin_headers)
    request_id = (await _withdraw(client, captain, "ccp", payout_account=CCP, payout_holder="أمين بن علي")).json()["id"]
    assert (await client.post(f"/admin/withdrawals/{request_id}/approve", headers=admin_headers)).status_code == 200
    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(f"/admin/withdrawals/{request_id}/paid", json={"reference": f"CCP-{n}"}, headers=admin_headers)
                for n in range(3)
            )
        ),
        timeout=30,
    )
    assert Counter(r.status_code for r in responses) == Counter({200: 1, 409: 2})
    assert len(await _withdrawal_entries(session_factory, captain["user_id"])) == 1


async def test_jordan_is_unchanged_cliq_and_bank_and_no_destination_written(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    driver = await approved_driver(client, session_factory)
    await set_cliq_alias(session_factory, driver["driver_id"])
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")
    wallet = (await client.get("/wallet/me/driver", headers=driver["headers"])).json()
    assert wallet["withdrawal_methods"] == ["cliq", "bank"]
    for method in ("cliq", "bank"):
        made = await _withdraw(client, driver, method, "10.000", payout_account=RIP, payout_holder="أحد")
        assert made.status_code == 201, made.text
        assert made.json()["payout_account"] is None and made.json()["payout_holder"] is None
    for method in ("ccp", "baridimob", "cash_office"):
        refused = await _withdraw(client, driver, method, "10.000")
        assert refused.status_code == 422 and "لا تُتاح في بلدك" in refused.json()["message"]
