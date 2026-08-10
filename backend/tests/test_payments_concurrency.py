"""اختبارات تزامن حقيقية على مسار الدفع (SPEC القسم 6/14).

بقية اختبارات الدفع تُرسل طلباً ثم تنتظر جوابه، فلا تمر أبداً بالمسار الذي
كُتبت الأقفال من أجله. هذه تُطلق الطلبات معاً بـ `asyncio.gather` على نفس حلقة
الأحداث: لكل طلبٍ جلستُه ومعاملتُه واتصالُه من المجمّع، فينتظر أحدهما قفلَ
الآخر في القاعدة فعلاً لا نظرياً — تماماً كـ `test_wallet_concurrency.py`.

الثوابت المُختبَرة ثلاثة: **رحلةٌ لا تُحصَّل مرتين**، و**قيدٌ واحد لكل دفعة**
مهما تكررت الضغطة، و**لا رصيد سالب** تحت أي سباق. والحكم على النتيجة لا على
التوقيت: عددُ من نجح، ورمزُ خطأ من خسر بعينه، ومجموعُ الدفتر مقروءاً من
القاعدة مباشرة.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

from httpx import AsyncClient, Response
from sqlalchemy import func, select

from app.models.payment import Payment
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    EXPECTED_FARE,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    pay_ride,
    register,
    set_commission,
    topup_wallet,
    wallet_of,
)


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    body = await register(client, payload)
    return {"headers": auth(body), "user_id": body["user"]["id"]}


async def _online_driver(client: AsyncClient, session_factory) -> dict:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    return driver


def _statuses(responses: list[Response]) -> Counter:
    return Counter(response.status_code for response in responses)


async def _count(session_factory, model, **filters) -> int:
    async with session_factory() as session:
        stmt = select(func.count(model.id))
        for column, value in filters.items():
            stmt = stmt.where(getattr(model, column) == value)
        return await session.scalar(stmt)


async def _ledger_sum(session_factory, user_id: str) -> str:
    """الرصيد مقروءاً من القاعدة مباشرة — لا من الـ API الذي قد يخطئ معه."""
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == uuid.UUID(user_id)
            )
        )
    return str(total)


# ------------------------------------------------------------------ الإنشاء


async def test_concurrent_payments_do_not_charge_the_ride_twice(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """أربع ضغطاتٍ بمفاتيح مختلفة على رحلة واحدة — تنجح واحدة لا أكثر.

    قفل صف الرحلة هو ما يسلسلها: بدونه تقرأ الأربع «المتبقي = 8.000» معاً
    فتفتح أربع دفعات بأربعة أضعاف الأجرة.
    """
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider["headers"], driver)

    responses = await asyncio.gather(
        *(
            pay_ride(
                client, rider["headers"], ride["id"], "cash", key=f"race-pay-{index}"
            )
            for index in range(4)
        )
    )

    counts = _statuses(list(responses))
    assert counts == Counter({201: 1, 409: 3}), counts
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {
        "ride_already_paid"
    }
    assert await _count(session_factory, Payment, ride_id=uuid.UUID(ride["id"])) == 1


async def test_same_key_under_race_creates_one_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """نفس المفتاح من خمسة طلبات متزامنة = دفعةٌ واحدة (SPEC القسم 14).

    الفحص يقع **بعد** أخذ قفل الرحلة لا قبله، فيتسلسل المتسابقون ويجد التالي
    دفعةَ الأول بدل أن يصطدم بالقيد الفريد.
    """
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider["headers"], driver)

    responses = await asyncio.gather(
        *(
            pay_ride(client, rider["headers"], ride["id"], "cash", key="one-true-key")
            for _ in range(5)
        )
    )

    assert _statuses(list(responses)) == Counter({201: 5})
    ids = {r.json()["payments"][0]["id"] for r in responses}
    assert len(ids) == 1
    assert await _count(session_factory, Payment, ride_id=uuid.UUID(ride["id"])) == 1


# ------------------------------------------------------------------ التأكيد


async def test_concurrent_confirmations_write_one_commission_entry(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """ثلاث ضغطات متزامنة على «استلمت المبلغ» — تفوز واحدة وتُخصم عمولة واحدة.

    الخاسران يرتدّان عن **آلة الحالات** لا عن مفتاح عدم التكرار وحده: قفل صف
    الدفعة هو ما يجعل الحارسين يعملان معاً بدل أن يتّكل أحدهما على الآخر.
    """
    await set_commission(session_factory, "10")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider["headers"], driver)
    await topup_wallet(client, admin_headers, driver["user_id"], "5.000")

    created = await pay_ride(client, rider["headers"], ride["id"], "cash")
    payment_id = created.json()["payments"][0]["id"]

    responses = await asyncio.gather(
        *(
            client.post(
                f"/payments/{payment_id}/confirm", headers=driver["headers"]
            )
            for _ in range(3)
        )
    )

    counts = _statuses(list(responses))
    assert counts == Counter({200: 1, 409: 2}), counts
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {
        "invalid_payment_transition"
    }

    async with session_factory() as session:
        commissions = await session.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.type == "commission"
            )
        )
    assert commissions == 1
    assert (await wallet_of(client, driver["headers"]))["balance"] == "4.200"


# ------------------------------------------------------------------- المحفظة


async def test_concurrent_wallet_payments_cannot_overdraw(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """رحلتان تُدفعان معاً من رصيدٍ يكفي واحدة ونصفاً — لا رصيد سالب.

    الراكب لا يملك رحلتين جاريتين، لكنه يملك رحلتين منتهيتين بلا دفع. الرصيد
    12 والأجرتان 8 و8: القفل الاستشاري يسلسلهما فتُدفع الأولى كاملةً وتنقسم
    الثانية إلى محفظةٍ وكاش — والمجموع المخصوم لا يتجاوز الرصيد أبداً.
    """
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    first = await completed_ride(client, rider["headers"], driver)
    second = await completed_ride(client, rider["headers"], driver)
    await topup_wallet(client, admin_headers, rider["user_id"], "12.000")

    responses = await asyncio.wait_for(
        asyncio.gather(
            pay_ride(client, rider["headers"], first["id"], "wallet", key="wallet-r-1"),
            pay_ride(client, rider["headers"], second["id"], "wallet", key="wallet-r-2"),
        ),
        # جمودٌ حقيقي لا ينكشف بخطأ بل بتعليقٍ إلى الأبد — فالمهلة هي الحكم
        timeout=20,
    )

    assert _statuses(list(responses)) == Counter({201: 2})
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"
    assert await _ledger_sum(session_factory, rider["user_id"]) == "0.000"

    # الكبتن لم يقبض من المنصة إلا ما خرج من المحفظة فعلاً
    assert (await wallet_of(client, driver["headers"]))["balance"] == "12.000"

    async with session_factory() as session:
        lowest = await session.scalar(select(func.min(WalletTransaction.balance_after)))
    assert lowest >= 0


async def test_paying_two_rides_at_once_leaves_the_remainder_as_cash(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """المجموع المطلوب على الرحلتين يبقى 16 مهما انقسم بين القناتين."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    first = await completed_ride(client, rider["headers"], driver)
    second = await completed_ride(client, rider["headers"], driver)
    await topup_wallet(client, admin_headers, rider["user_id"], "12.000")

    await asyncio.gather(
        pay_ride(client, rider["headers"], first["id"], "wallet", key="split-r-1"),
        pay_ride(client, rider["headers"], second["id"], "wallet", key="split-r-2"),
    )

    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
        )
        cash_total = await session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.method == "cash"
            )
        )
    assert str(total) == str(Decimal(EXPECTED_FARE) * 2)
    assert str(cash_total) == "4.000"
