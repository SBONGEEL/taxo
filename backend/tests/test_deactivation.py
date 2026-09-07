"""إلغاءُ تفعيل الحساب والرصيدُ المحتجَز (البند ١٣).

**والمحتجَزُ شرطٌ لا قيد**: الاختبارُ يقرأ الدفترَ كما يقرأ المتاح — فلو كُتب
قيدٌ لحجزه لظهر هنا، ولانكشف أن الرصيدَ يكذب على صاحبه.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.deactivation import DeactivationRequest
from app.models.driver import Driver
from app.models.enums import (
    DeactivationStatus,
    DriverStatus,
    WalletTransactionType,
)
from app.models.wallet import WalletTransaction
from app.models.wallet_setting import WalletSetting
from app.services import wallet as wallet_service

from tests.helpers import (
    DRIVER,
    approved_driver,
    auth,
    rider_session,
    topup_wallet,
)

pytestmark = pytest.mark.usefixtures("jordan_settings", "jordan_wallet")


async def _set_reserve(session_factory, amount: str) -> None:
    async with session_factory() as session:
        await session.execute(
            update(WalletSetting).values(withdrawal_reserve_amount=Decimal(amount))
        )
        await session.commit()


async def _set_alias(client: AsyncClient, headers: dict) -> None:
    """alias كليك شرطٌ قائمٌ منذ المرحلة 5 — يُضبط كي يصل الاختبارُ إلى شرطه هو."""
    response = await client.patch(
        "/drivers/me", json={"cliq_alias": "taxo.test"}, headers=headers
    )
    assert response.status_code == 200, response.text


async def _credit(session_factory, user_id: str, amount: str) -> None:
    async with session_factory() as session:
        from app.models.user import User

        user = await session.get(User, uuid.UUID(str(user_id)))
        assert user is not None
        await wallet_service.record(
            session,
            owner=user,
            tx_type=WalletTransactionType.RIDE_EARNING,
            amount=Decimal(amount),
            reference="أرباحٌ للاختبار",
            idempotency_key=f"test-earn:{uuid.uuid4()}",
        )
        await session.commit()


async def test_the_reserve_is_a_condition_not_a_ledger_entry(
    client: AsyncClient, session_factory
) -> None:
    """يُطرح من المتاح ولا يُكتب له قيد — وإلا كذب الرصيدُ على صاحبه."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    await _credit(session_factory, driver["user_id"], "30.000")
    await _set_reserve(session_factory, "5.000")
    await _set_alias(client, driver["headers"])

    body = (await client.get("/wallet/me", headers=driver["headers"])).json()
    assert Decimal(body["balance"]) == Decimal("30.000")

    # سحبُ ما فوق المتاح يُرفض، وما دونه يمرّ
    too_much = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": "26.000", "method": "cliq"},
        headers=driver["headers"],
    )
    assert too_much.status_code == 409, too_much.text

    async with session_factory() as session:
        rows = await session.scalars(
            select(WalletTransaction).where(
                WalletTransaction.owner_id == uuid.UUID(str(driver["user_id"]))
            )
        )
        kinds = [row.type for row in rows]
    assert all(kind is not WalletTransactionType.ADJUSTMENT for kind in kinds), (
        "كُتب قيدٌ لحجز المحتجَز — والرصيدُ حينها يقرأ رقماً لم يُدفع"
    )


async def test_a_ride_in_progress_blocks_the_request(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """لا يُغلق حسابٌ وراكبٌ في سيارته — والموانعُ تُقرأ حيّةً."""
    from tests.helpers import NEAR_PICKUP, accepted_ride, bring_online, register

    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver, NEAR_PICKUP)
    rider = auth(await register(client, {**DRIVER, "phone": "0791110001",
                                         "name": "راكبُ المانع", "role": "rider"}))
    await accepted_ride(client, rider, driver)

    blocked = await client.post(
        "/account/deactivation", json={"reason": "أنهيتُ العمل"},
        headers=driver["headers"],
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "deactivation_blocked"

    state = (
        await client.get("/account/deactivation", headers=driver["headers"])
    ).json()
    assert "active_ride" in state["blockers"]
    assert state["request"] is None


async def test_the_request_is_reviewed_and_releases_the_reserve(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """الموافقةُ تُلغي التفعيل **ويسقط شرطُ المحتجَز** — فيُسحب الرصيد كلُّه."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    await _credit(session_factory, driver["user_id"], "30.000")
    await _set_reserve(session_factory, "5.000")
    await _set_alias(client, driver["headers"])

    opened = await client.post(
        "/account/deactivation", json={"reason": "سافرتُ"},
        headers=driver["headers"],
    )
    assert opened.status_code == 201, opened.text

    # طلبٌ ثانٍ يُرفض — الفهرسُ الجزئي في القاعدة هو الحارس
    again = await client.post(
        "/account/deactivation", json={}, headers=driver["headers"]
    )
    assert again.status_code == 409

    listed = (
        await client.get("/admin/deactivations", headers=admin_headers)
    ).json()
    assert listed and listed[0]["status"] == "pending"

    decided = await client.patch(
        f"/admin/deactivations/{listed[0]['id']}",
        json={"approved": True},
        headers=admin_headers,
    )
    assert decided.status_code == 200, decided.text

    async with session_factory() as session:
        row = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
        assert row is not None and row.status is DriverStatus.DEACTIVATED

    # وبعدها يُسحب الرصيد كلُّه: المحتجَزُ وُجد ليخرج في هذه اللحظة
    full = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": "30.000", "method": "cliq"},
        headers=driver["headers"],
    )
    assert full.status_code == 201, full.text


async def test_rejecting_needs_a_written_reason(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    driver = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": "0796660013", "name": "كبتنُ الرفض"},
        plate_number="AMM-1313",
        subscribed=False,
    )
    opened = (
        await client.post(
            "/account/deactivation", json={}, headers=driver["headers"]
        )
    ).json()

    bare = await client.patch(
        f"/admin/deactivations/{opened['id']}",
        json={"approved": False},
        headers=admin_headers,
    )
    assert bare.status_code in (400, 422)

    with_note = await client.patch(
        f"/admin/deactivations/{opened['id']}",
        json={"approved": False, "note": "عليه مستحقاتٌ لم تُسوَّ"},
        headers=admin_headers,
    )
    assert with_note.status_code == 200
    assert with_note.json()["status"] == DeactivationStatus.REJECTED.value

    async with session_factory() as session:
        row = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
        assert row is not None and row.status is DriverStatus.APPROVED


async def test_the_driver_can_change_his_mind(
    client: AsyncClient, session_factory
) -> None:
    driver = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": "0796660016", "name": "كبتنٌ عدل"},
        plate_number="AMM-1616",
        subscribed=False,
    )
    await client.post("/account/deactivation", json={}, headers=driver["headers"])
    cancelled = await client.delete(
        "/account/deactivation", headers=driver["headers"]
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == DeactivationStatus.CANCELLED.value

    async with session_factory() as session:
        rows = await session.scalars(
            select(DeactivationRequest).where(
                DeactivationRequest.user_id == uuid.UUID(str(driver["user_id"]))
            )
        )
        assert len(list(rows)) == 1

    # وبعد العدول يستطيع أن يطلب من جديد — الفهرسُ يمنع القائمَ لا المنتهي
    again = await client.post(
        "/account/deactivation", json={}, headers=driver["headers"]
    )
    assert again.status_code == 201


# ═══════════════════ إغلاقُ حساب الراكب — البابُ نفسُه (٢٠٢٦-٠٩-٠٧)
#
# **شرطُ المتجر**: «an in-app path to delete their app accounts». **ولم يكن
# للراكب مسار**، ووُسِّع موضوعُ الجدول من الكبتن إلى الحساب (الترحيلة `0075`)
# **ولم يُبنَ بابٌ ثانٍ**.


async def test_a_rider_closes_his_account_and_is_locked_out(
    client, session_factory, admin_headers
) -> None:
    """الطلبُ ← الموافقةُ ← البابُ يُردّ **برمزه هو** لا برمز الحظر.

    **و`account_closed` غيرُ `account_blocked`**: الأولُ قرارُ صاحبه، والثاني
    قرارُ مشرفٍ فيه — **ورمزٌ واحدٌ لهما يقول لمن أغلق حسابَه إنه محظور**.
    """
    from app.models.user import User

    rider = await rider_session(client)

    opened = await client.post(
        "/account/deactivation", json={"reason": "لم أعد أحتاجه"},
        headers=rider["headers"],
    )
    assert opened.status_code == 201, opened.text

    listed = (
        await client.get("/admin/deactivations", headers=admin_headers)
    ).json()
    mine = [row for row in listed if row["user_id"] == rider["user"]["id"]]
    assert len(mine) == 1, listed

    decided = await client.patch(
        f"/admin/deactivations/{mine[0]['id']}",
        json={"approved": True},
        headers=admin_headers,
    )
    assert decided.status_code == 200, decided.text

    async with session_factory() as session:
        row = await session.get(User, uuid.UUID(rider["user"]["id"]))
        assert row is not None and row.deactivated_at is not None

    # **والتوكنُ الذي بيده يبطل من الطلب التالي** — لا حين ينتهي أجلُه
    after = await client.get("/wallet/me", headers=rider["headers"])
    assert after.status_code == 403, after.text
    assert after.json()["code"] == "account_closed"


async def test_closing_a_rider_account_erases_his_saved_places(
    client, session_factory, admin_headers
) -> None:
    """**«حذفٌ» كلمةٌ تكذب إن بقي كلُّ شيء** — فما يجوز محوُه يُمحى فعلاً.

    **ويبقى الدفترُ وشواهدُ الرحلات**: القاعدةُ تمنع محوَهما، **وفيهما حقُّ
    طرفٍ آخر شارك الرحلة**.
    """
    from app.models.place import SavedPlace

    rider = await rider_session(client)
    saved = await client.post(
        "/me/places",
        json={"label": "المنزل", "address": "عمّان", "lat": 31.95, "lng": 35.91},
        headers=rider["headers"],
    )
    assert saved.status_code == 201, saved.text

    opened = await client.post(
        "/account/deactivation", json={}, headers=rider["headers"]
    )
    assert opened.status_code == 201, opened.text
    await client.patch(
        f"/admin/deactivations/{opened.json()['id']}",
        json={"approved": True},
        headers=admin_headers,
    )

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(SavedPlace).where(
                    SavedPlace.user_id == uuid.UUID(rider["user"]["id"])
                )
            )
        ).all()
        assert rows == [], rows


async def test_a_rider_with_money_is_stopped_and_told_what_to_do(
    client, admin_headers
) -> None:
    """**الراكبُ لا يسحب** (§7) — وإغلاقُ حسابٍ فيه رصيدٌ مصادرةٌ لا خدمة.

    **والمانعُ قابلٌ للإزالة بيده**: ينفقه أو يحوّله.
    """
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "5.000")

    state = await client.get("/account/deactivation", headers=rider["headers"])
    assert state.status_code == 200, state.text
    assert "wallet_balance" in state.json()["blockers"]

    refused = await client.post(
        "/account/deactivation", json={}, headers=rider["headers"]
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "deactivation_blocked"


async def test_a_driver_with_money_is_not_stopped_by_it(
    client, session_factory, admin_headers
) -> None:
    """**نقضُ العطب الذي وقع في البناء** (§56٫1).

    مانعُ الرصيد **للراكب وحدَه**: الكبتنُ له مسارُ سحب، **وهذا البابُ نفسُه
    هو ما يُطلق محتجَزَه** — فمنعُه برصيدٍ موجبٍ **يُبطل البابَ الذي بُني له**،
    ويقول له «أفرغ رصيدَك» وهو لا يستطيع حتى يُغلق حسابَه.

    **واحذف الشرطَ `driver is None` من `blockers` فيسقط هذا الاختبارُ وحدَه**
    — وهو ما يجعله حارساً لا زينة.
    """
    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "40.000")

    state = await client.get("/account/deactivation", headers=driver["headers"])
    assert state.status_code == 200, state.text
    assert "wallet_balance" not in state.json()["blockers"], state.json()

    opened = await client.post(
        "/account/deactivation", json={}, headers=driver["headers"]
    )
    assert opened.status_code == 201, opened.text
