"""اختبارات تزامن على مسار البطاقة (SPEC القسم 6.4/14).

هذه القناة تُدخل متسابقين لا وجود لهم في بقية القنوات: **الإشعار واستعلامُ
العميل يصلان معاً**، والمزودون يعيدون إرسال الإشعار مرات. فسباقُها ليس احتمالاً
نظرياً بل تشغيلُها الطبيعي — وسباقٌ هنا لا يعني خطأً في صفٍّ بل قيداً مالياً
مكرراً.

الطلبات تُطلق معاً بـ `asyncio.gather` على نفس حلقة الأحداث: لكل طلبٍ جلستُه
ومعاملتُه واتصالُه، فينتظر أحدهما قفلَ الآخر في القاعدة فعلاً — كـ
`test_wallet_concurrency.py` و`test_payments_concurrency.py`.

والحكم على النتيجة لا على التوقيت: **عدد القيود مقروءاً من القاعدة مباشرة**،
وحالةُ الصف الواحدة، ورمزُ خطأ الخاسر بعينه، ولا `balance_after` سالب.

**تحقُّقٌ منفَّذ لا مُدّعى:** بحذف `for_update=True` من آخر سطر في
`card_payments._locked_order` تسقط `test_concurrent_webhooks_settle_the_payment_once`
بـ `Counter({409: 4, 200: 1})` بدل `Counter({200: 5})`، وتسقط معها
`test_webhook_and_client_lookup_racing_settle_once` — بينما تنجو كل الاختبارات
التسلسلية. والقيود تبقى واحدة في تلك الحالة لأن مفتاح عدم التكرار يمسكها: أي
أن **الحارس الأول سقط ولم يظهر إلا في سلوك الحارس الثاني**، وهو بالضبط العيب
الذي شُدِّد عليه في CLAUDE.md — مزودٌ يرى 409 على إشعارٍ صحيح يعيد الإرسال إلى
أن يستسلم، فيصير خللُ قفلٍ خللَ تسويةٍ عند المزود.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

from httpx import AsyncClient, Response
from sqlalchemy import func, select

from app.models.payment import Payment, SavedCard
from app.models.provider_order import ProviderOrder
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    EXPECTED_FARE,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    enable_card_provider,
    mock_webhook_payload,
    pay_ride,
    register,
    simulate_card,
    wallet_of,
)


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    body = await register(client, payload)
    return {"headers": auth(body), "user_id": body["user"]["id"]}


def _statuses(responses: list[Response]) -> Counter:
    return Counter(response.status_code for response in responses)


async def _count(session_factory, model, **filters) -> int:
    async with session_factory() as session:
        stmt = select(func.count(model.id))
        for column, value in filters.items():
            stmt = stmt.where(getattr(model, column) == value)
        return await session.scalar(stmt)


async def _entry_count(session_factory, tx_type: str) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.type == tx_type
            )
        )


async def _ledger_sum(session_factory, user_id: str) -> str:
    """الرصيد مقروءاً من القاعدة مباشرة — لا من الـ API الذي قد يخطئ معه."""
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == uuid.UUID(user_id)
            )
        )
    return str(total)


async def _mark_paid_at_provider(cart_id: str) -> None:
    """يجعل المزود الوهمي يقول «دُفع» بلا أن يمر أحدٌ بمسار التسوية.

    ضرورةٌ في هذه الاختبارات: لو استُدعي مسار المحاكاة لسوّى بنفسه، فما بعده
    لن يتسابق على شيء.
    """
    from app.core.redis_client import get_redis_client

    await get_redis_client().set(f"card:mock:{cart_id}", "paid")


async def _open_card_payment(
    client: AsyncClient, session_factory
) -> tuple[dict, dict, dict, str]:
    """رحلةٌ منتهية بدفعةِ بطاقةٍ مفتوحة، والمزود يقول «دُفع» ولم يُسوَّ بعد."""
    await enable_card_provider(session_factory)
    rider = await _rider(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    created = await pay_ride(client, rider["headers"], ride["id"], "card")
    assert created.status_code == 201, created.text
    cart_id = created.json()["card_order"]["cart_id"]
    await _mark_paid_at_provider(cart_id)
    return rider, driver, ride, cart_id


# ------------------------------------------------------------------ الإنشاء


async def test_concurrent_card_payments_open_one_order(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """أربع ضغطات بمفاتيح مختلفة على «ادفع بالبطاقة» — تنجح واحدة لا أكثر.

    قفل صف الرحلة هو ما يسلسلها: بدونه تُفتح أربع عمليات عند المزود بأربعة
    أضعاف الأجرة، ولا يعرف الراكب أيَّها دفع.
    """
    await enable_card_provider(session_factory)
    rider = await _rider(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    responses = await asyncio.gather(
        *(
            pay_ride(
                client, rider["headers"], ride["id"], "card", key=f"race-card-{index}"
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
    assert await _count(session_factory, ProviderOrder) == 1


async def test_same_key_under_race_opens_one_card_order(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """نفس المفتاح من خمسة طلبات متزامنة = عمليةٌ واحدة عند المزود (القسم 14).

    وهذا أخطر من تكرار صفٍّ: كل عملية زائدة صفحةُ دفعٍ حقيقية يمكن أن تُدفع.
    """
    await enable_card_provider(session_factory)
    rider = await _rider(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    responses = await asyncio.gather(
        *(
            pay_ride(client, rider["headers"], ride["id"], "card", key="one-card-key")
            for _ in range(5)
        )
    )

    assert _statuses(list(responses)) == Counter({201: 5})
    assert len({r.json()["payments"][0]["id"] for r in responses}) == 1
    assert len({r.json()["card_order"]["cart_id"] for r in responses}) == 1
    assert await _count(session_factory, ProviderOrder) == 1


# ------------------------------------------------------------------ التسوية


async def test_concurrent_webhooks_settle_the_payment_once(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """خمسة إشعارات متزامنة لنفس الطلب — قيدُ أرباحٍ واحد لا خمسة.

    هذا هو السباق الذي كُتب قفلُ صف الطلب من أجله: بدونه تقرأ الخمسة الحالةَ
    `created` معاً فتمر كلها من الحارس، ولا يبقى بين المنصة وخمسة أضعاف
    الأرباح إلا مفتاحُ عدم التكرار وحده — وحارسٌ لا يُترك حارساً وحيداً.
    """
    _rider_, driver, _ride, cart_id = await _open_card_payment(client, session_factory)
    payload = mock_webhook_payload(cart_id)

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(client.post("/payments/card/webhook", data=payload) for _ in range(5))
        ),
        # جمودٌ حقيقي لا ينكشف بخطأ بل بتعليقٍ إلى الأبد — فالمهلة هي الحكم
        timeout=30,
    )

    assert _statuses(list(responses)) == Counter({200: 5})
    assert {r.json()["status"] for r in responses} == {"paid"}

    assert await _entry_count(session_factory, "ride_earning") == 1
    assert (await wallet_of(client, driver["headers"]))["balance"] == EXPECTED_FARE
    assert await _count(session_factory, Payment) == 1


async def test_webhook_and_client_lookup_racing_settle_once(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """الإشعار واستعلامُ العميل يصلان معاً — وهو مسارٌ عادي لا استثناء.

    كلاهما يسأل المزود ثم يدخل نفس الباب. أيُّهما سبق سوّى، والآخر يجد الطلب
    محسوماً فلا يقيّد شيئاً — ولا يرتدّ بخطأ: عودةٌ ناجحة بحالةٍ نهائية.
    """
    rider, driver, _ride, cart_id = await _open_card_payment(client, session_factory)

    webhook, lookup = await asyncio.wait_for(
        asyncio.gather(
            client.post("/payments/card/webhook", data=mock_webhook_payload(cart_id)),
            client.get(
                f"/payments/card/orders/{cart_id}", headers=rider["headers"]
            ),
        ),
        timeout=30,
    )

    assert (webhook.status_code, lookup.status_code) == (200, 200)
    assert webhook.json()["status"] == "paid"
    assert lookup.json()["status"] == "paid"

    assert await _entry_count(session_factory, "ride_earning") == 1
    assert (await wallet_of(client, driver["headers"]))["balance"] == EXPECTED_FARE


async def test_concurrent_settlement_writes_one_commission_entry(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """العمولة سطرٌ واحد تحت السباق كما هي تحت التسلسل (SPEC القسم 6.3)."""
    from tests.helpers import set_commission

    await set_commission(session_factory, "10")
    _rider_, driver, _ride, cart_id = await _open_card_payment(client, session_factory)

    await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    "/payments/card/webhook", data=mock_webhook_payload(cart_id)
                )
                for _ in range(4)
            )
        ),
        timeout=30,
    )

    assert await _entry_count(session_factory, "ride_earning") == 1
    assert await _entry_count(session_factory, "commission") == 1
    assert (await wallet_of(client, driver["headers"]))["balance"] == "7.200"


# ------------------------------------------------------------- شحن المحفظة


async def test_concurrent_topup_notifications_credit_once(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """خمسة إشعارات على شحنةٍ واحدة = قيد `topup` واحد.

    الشحن أخطر من الدفع في التكرار: لا سقف له من مبلغ رحلة، فالخمسة تصير خمسة
    أضعاف الرصيد لو مرّت. الرصيد يُقرأ من القاعدة مباشرة لا من الـ API.
    """
    await enable_card_provider(session_factory)
    rider = await _rider(client)

    created = await client.post(
        "/wallet/me/topups/card",
        json={"amount": "25.000"},
        headers=rider["headers"],
    )
    cart_id = created.json()["cart_id"]
    await _mark_paid_at_provider(cart_id)

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    "/payments/card/webhook", data=mock_webhook_payload(cart_id)
                )
                for _ in range(5)
            )
        ),
        timeout=30,
    )

    assert _statuses(list(responses)) == Counter({200: 5})
    assert await _entry_count(session_factory, "topup") == 1
    assert await _ledger_sum(session_factory, rider["user_id"]) == "25.000"

    async with session_factory() as session:
        lowest = await session.scalar(select(func.min(WalletTransaction.balance_after)))
    assert lowest >= 0


async def test_concurrent_settlement_saves_the_card_once(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """البطاقة تُحفظ صفاً واحداً — والقيد الفريد يحرس ما لا يحرسه القفل."""
    await enable_card_provider(session_factory)
    rider = await _rider(client)

    created = await client.post(
        "/wallet/me/topups/card",
        json={"amount": "10.000", "save_card": True},
        headers=rider["headers"],
    )
    cart_id = created.json()["cart_id"]
    await _mark_paid_at_provider(cart_id)

    await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    "/payments/card/webhook", data=mock_webhook_payload(cart_id)
                )
                for _ in range(4)
            )
        ),
        timeout=30,
    )

    assert await _count(session_factory, SavedCard) == 1
    cards = (await client.get("/payments/cards", headers=rider["headers"])).json()
    assert len(cards) == 1
    assert cards[0]["is_default"] is True


# ------------------------------------------------------------------ الاسترداد


async def test_concurrent_refunds_hit_the_provider_once(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """ثلاث ضغطات متزامنة على «استرداد» — ردٌّ واحد عند المزود وقيدٌ واحد.

    الخاسران يرتدّان عن **آلة الحالات** لا عن مفتاح عدم التكرار: قفل صف الدفعة
    قبل فحص الانتقال هو ما يجعل الحارسين يعملان معاً. والترتيب هنا هو الترتيب
    المعاكس لمسار التسوية (دفعة ← طلب)، فلو اختلف الترتيبان تقابلا في جمود —
    والمهلة هي ما يكشفه.
    """
    rider, driver, ride, cart_id = await _open_card_payment(client, session_factory)
    await simulate_card(client, rider["headers"], cart_id)

    payments = (
        await client.get(f"/rides/{ride['id']}/payments", headers=rider["headers"])
    ).json()["payments"]
    payment_id = payments[0]["id"]

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    f"/admin/payments/{payment_id}/refund",
                    json={"reason": "شكوى الراكب"},
                    headers=admin_headers,
                )
                for _ in range(3)
            )
        ),
        timeout=30,
    )

    counts = _statuses(list(responses))
    assert counts == Counter({200: 1, 409: 2}), counts
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {
        "invalid_payment_transition"
    }

    # قيدٌ مضادٌّ واحد على الكبتن، ولا قيد استرداد للراكب (المال عاد للبطاقة)
    assert await _entry_count(session_factory, "adjustment") == 1
    assert await _entry_count(session_factory, "refund") == 0
    # ودفتر الراكب **خالٍ** لا صفرُ المجموع: مالُه لم يمر بمحفظته لا ذهاباً ولا
    # رجوعاً، فمجموعٌ صفريٌّ من قيدين متقابلين ليس هو المطلوب هنا
    assert await _count(session_factory, WalletTransaction, owner_id=uuid.UUID(rider["user_id"])) == 0
    assert (await wallet_of(client, driver["headers"]))["balance"] == "0.000"


async def test_settling_two_rides_at_once_credits_each_exactly_once(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """رحلتان تُسوّيان معاً على نفس محفظة الكبتن — قفلُ المحفظة يسلسل القيدين.

    القفل الاستشاري هو آخر قفلٍ في الترتيب، وهنا يتقابل عليه مساران لا يشتركان
    في صفٍّ واحد: طلبان مختلفان لدفعتين مختلفتين على رحلتين مختلفتين، ومحفظةٌ
    واحدة. المجموع هو الحكم — و`balance_after` لا يكون كاذباً في أيٍّ منهما.
    """
    await enable_card_provider(session_factory)
    rider = await _rider(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)

    carts = []
    for index in range(2):
        ride = await completed_ride(client, rider["headers"], driver)
        created = await pay_ride(
            client, rider["headers"], ride["id"], "card", key=f"two-rides-{index}"
        )
        cart_id = created.json()["card_order"]["cart_id"]
        await _mark_paid_at_provider(cart_id)
        carts.append(cart_id)

    await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    "/payments/card/webhook", data=mock_webhook_payload(cart_id)
                )
                for cart_id in carts
            )
        ),
        timeout=30,
    )

    assert await _entry_count(session_factory, "ride_earning") == 2
    expected = str(Decimal(EXPECTED_FARE) * 2)
    assert (await wallet_of(client, driver["headers"]))["balance"] == expected
    assert await _ledger_sum(session_factory, driver["user_id"]) == expected
