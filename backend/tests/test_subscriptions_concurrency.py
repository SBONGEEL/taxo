"""اختبارات تزامن على شراء الاشتراك (SPEC القسم 8/14).

المرحلة تُحرّك مالاً وتفتح فترة تغطية، فحارساها قفلان: القفل الاستشاري على
محفظة الكبتن (ألّا يُشترى بمالٍ لا يملكه) وقفلُ صف الكبتن (ألّا يشتري شراءان
متزامنان **نفس الفترة** بثمنين). والثاني هو الجديد هنا: طلبٌ ثم تأكيدٌ متتاليان
لا يدخلان مساره أبداً، فلا يثبته إلا إطلاقُ الطلبين معاً على نفس حلقة الأحداث
— لكلٍّ جلسته ومعاملته، فينتظر أحدهما قفلَ الآخر في القاعدة فعلاً.

الثابت المُختبَر ليس التوقيت بل النتيجة: كم نجح، وبأي رمزٍ ارتدّ الخاسر، وكم
صفاً في الجدول، وكم قيداً في الدفتر، وهل تجاور الفترتان أم تراكبتا.
"""

from __future__ import annotations

import asyncio
from collections import Counter

from httpx import AsyncClient, Response
from sqlalchemy import func, select

from app.models.subscription import DriverSubscription
from app.models.wallet import WalletTransaction
from tests.helpers import (
    approved_driver,
    ensure_plan,
    topup_wallet,
    wallet_of,
)


def _statuses(responses: list[Response]) -> Counter:
    return Counter(response.status_code for response in responses)


async def _subscriptions(session_factory) -> list[DriverSubscription]:
    async with session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(DriverSubscription).order_by(DriverSubscription.starts_at)
                )
            ).all()
        )


async def _ledger_count(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.type == "subscription_payment"
            )
        )


async def test_same_key_under_race_buys_one_subscription(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """خمس ضغطات بنفس المفتاح = اشتراكٌ واحد وقيدٌ واحد (SPEC القسم 14).

    الفحص يقع **بعد** قفل صف الكبتن لا قبله، فيتسلسل المتسابقون ويجد التالي
    اشتراكَ الأول بدل أن يصطدم بالقيد الفريد.
    """
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "200.000")

    payload = {"plan_id": str(plan_id), "idempotency_key": "one-and-only-sub"}
    responses = await asyncio.gather(
        *(
            client.post("/subscriptions", json=payload, headers=driver["headers"])
            for _ in range(5)
        )
    )

    assert _statuses(list(responses)) == Counter({201: 5})
    assert len({response.json()["id"] for response in responses}) == 1
    assert len(await _subscriptions(session_factory)) == 1
    assert await _ledger_count(session_factory) == 1
    assert (await wallet_of(client, driver["headers"]))["balance"] == "170.000"


async def test_concurrent_purchases_cannot_overdraw_the_wallet(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """أربع عمليات بمفاتيح مختلفة من رصيدٍ يكفي اثنتين — تنجح اثنتان لا أكثر."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "65.000")

    responses = await asyncio.gather(
        *(
            client.post(
                "/subscriptions",
                json={
                    # مفاتيح مختلفة عمداً: هذا سباقٌ على الرصيد لا تكرارُ عملية
                    "plan_id": str(plan_id),
                    "idempotency_key": f"race-sub-{index}",
                },
                headers=driver["headers"],
            )
            for index in range(4)
        )
    )

    counts = _statuses(list(responses))
    assert counts[201] == 2, counts
    assert counts[409] == 2, counts
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {
        "insufficient_balance"
    }

    assert (await wallet_of(client, driver["headers"]))["balance"] == "5.000"
    assert await _ledger_count(session_factory) == 2
    async with session_factory() as session:
        lowest = await session.scalar(select(func.min(WalletTransaction.balance_after)))
    assert lowest >= 0


async def test_concurrent_manual_records_get_consecutive_periods(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """تسجيلان يدويان معاً = فترتان **متجاورتان** لا متطابقتان.

    هذا هو الثابت الذي كُتب قفلُ صف الكبتن لأجله وحده. المسار اليدوي (كما مسار
    البطاقة) لا يمر بقفل المحفظة أصلاً — لا قيد له في الدفتر — فلا حارس له
    غيره: بغيره يقرأ الطلبان «نهاية التغطية» نفسها قبل أن يكتب أيّهما صفَّه،
    فيخرج شهران مقبوضان بفترةٍ واحدة. خسارةٌ لا يكشفها مجموعُ الدفتر لأن لا
    قيد فيه أصلاً، ولا يكشفها اختبارٌ متتالٍ لأنه لا يدخل هذا المسار.

    والمهلة حكمٌ على الجمود: تقابلُ قفلين لا يرفع خطأً بل يعلّق إلى الأبد.
    """
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    "/admin/subscriptions",
                    json={
                        "driver_id": str(driver["driver_id"]),
                        "plan_id": str(plan_id),
                        "method": "cash",
                        "reference": f"إيصال {index}",
                    },
                    headers=admin_headers,
                )
                for index in range(2)
            )
        ),
        timeout=20,
    )

    assert _statuses(list(responses)) == Counter({201: 2})
    first, second = await _subscriptions(session_factory)
    assert first.expires_at == second.starts_at
    assert first.starts_at < first.expires_at < second.expires_at


async def test_concurrent_wallet_renewals_do_not_deadlock(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """تجديدان من المحفظة معاً: قفلُ الكبتن ثم قفلُ المحفظة — بهذا الترتيب دائماً.

    الترتيب الثابت هو ما يمنع الجمود، والمهلة هي الحكم عليه: الجمود لا يرفع
    خطأً بل يعلّق. والفترتان متجاورتان هنا كذلك.
    """
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "60.000")

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    "/subscriptions",
                    json={
                        "plan_id": str(plan_id),
                        "idempotency_key": f"stack-sub-{index}",
                    },
                    headers=driver["headers"],
                )
                for index in range(2)
            )
        ),
        timeout=20,
    )

    assert _statuses(list(responses)) == Counter({201: 2})
    first, second = await _subscriptions(session_factory)
    assert first.expires_at == second.starts_at
    assert first.starts_at < first.expires_at < second.expires_at

    mine = await client.get("/subscriptions/me", headers=driver["headers"])
    assert mine.json()["days_remaining"] == 60
