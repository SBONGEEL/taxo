"""الدفع بالبطاقة عبر مزود خارجي (SPEC القسم 6.4/7/14 — المرحلة 6-ب).

المزود هنا هو المزود الوهمي المُدار من عقد Telr نفسه (القسم 15)، فتبقى قراءةُ
العقد ومزامنةُ `card_enabled` وتوقيعُ الإشعار مسارات حقيقية — ولا يُستبدل إلا
ما وراء الشبكة. مُحوِّلُ أسلاك Telr تختبره `test_telr_gateway.py` وحده.

الثابت الذي تدور حوله هذه الاختبارات: **لا يتحرك الدفتر إلا بجواب المزود
للخلفية**، لا بحمولة إشعار ولا بقول عميل. ومنه تتفرع البقية: البطاقة لا تُخصم
من محفظة الراكب، وسقوطُ العملية يُرجع المبلغ ديناً على الرحلة، والردُّ يعود من
حيث جاء المال.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.payment import Payment, SavedCard
from app.models.provider_order import ProviderOrder
from tests.helpers import (
    DRIVER,
    EXPECTED_FARE,
    OTHER_RIDER,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    card_order_of,
    completed_ride,
    enable_card_provider,
    mock_webhook_payload,
    pay_ride,
    payments_of,
    register,
    simulate_card,
    topup_wallet,
    wallet_of,
)


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    body = await register(client, payload)
    return {"headers": auth(body), "user_id": body["user"]["id"]}


async def _ready_ride(client: AsyncClient, session_factory) -> tuple[dict, dict, dict]:
    rider = await _rider(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)
    return rider, driver, ride


def _only(body: dict) -> dict:
    assert len(body["payments"]) == 1, body["payments"]
    return body["payments"][0]


async def _card_payment(client: AsyncClient, session_factory) -> tuple[dict, dict, dict, dict]:
    """راكبٌ وكبتنٌ ورحلةٌ ودفعةُ بطاقةٍ مفتوحةٌ عند المزود بانتظار الدفع."""
    await enable_card_provider(session_factory)
    rider, driver, ride = await _ready_ride(client, session_factory)

    created = await pay_ride(client, rider["headers"], ride["id"], "card")
    assert created.status_code == 201, created.text
    return rider, driver, ride, created.json()


# ------------------------------------------------------------- صفحة الدفع


async def test_card_payment_opens_a_hosted_page_and_waits(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الدفعة `pending` والطلب `created`: لا مال قبل جواب المزود."""
    _rider_, _driver, _ride, body = await _card_payment(client, session_factory)

    payment = _only(body)
    assert payment["method"] == "card"
    assert payment["provider"] == "telr"
    assert payment["status"] == "pending"
    assert payment["amount"] == EXPECTED_FARE

    order = body["card_order"]
    assert order["status"] == "created"
    assert order["purpose"] == "ride_payment"
    assert order["amount"] == EXPECTED_FARE
    # ما تفتحه الواجهة فعلاً — بلا رابطٍ لا شيء يُفعل
    assert order["redirect_url"]
    # المبلغ محجوزٌ بدفعةٍ قائمة فلا تُدفع الرحلة بقناة ثانية في الوقت نفسه
    assert body["outstanding"] == "0.000"


async def test_card_needs_its_feature_flag(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """غياب عقد Telr = غياب `card_enabled` = رفض (SPEC القسم 4).

    وهذا ما يحل محل 501 من المرحلة 6-أ: القناة صارت مبنيّة، فمنعُها قرارٌ
    إداري (403) لا نقصٌ في التنفيذ.
    """
    rider, _driver, ride = await _ready_ride(client, session_factory)

    response = await pay_ride(client, rider["headers"], ride["id"], "card")
    assert response.status_code == 403
    assert response.json()["code"] == "feature_disabled"


async def test_card_payment_without_a_provider_contract_is_unavailable(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """مفتاحٌ مرفوعٌ بلا عقدٍ مفعّل: 503 لا 403 ولا 500.

    يقع فعلاً حين يعطّل المشرف العقد ويبقى المفتاح مرفوعاً يدوياً — فالرسالة
    تدل على العقد لا على البلد.
    """
    from tests.helpers import enable_features

    await enable_features(session_factory, "card_enabled")
    rider, _driver, ride = await _ready_ride(client, session_factory)

    response = await pay_ride(client, rider["headers"], ride["id"], "card")
    assert response.status_code == 503
    assert response.json()["code"] == "card_gateway_unavailable"

    # ولا يبقى صفٌّ معلّق: الدفعة والطلب يُنشآن قبل نداء المزود، فسقوطُه يجب أن
    # يُرجع المعاملة كلها. صفُّ دفعةٍ `pending` بلا طلبٍ عند أحدٍ يحجز أجرة
    # الرحلة إلى الأبد
    async with session_factory() as session:
        assert (await session.scalars(select(ProviderOrder))).all() == []
        assert (await session.scalars(select(Payment))).all() == []
    state = await payments_of(client, rider["headers"], ride["id"])
    assert state["outstanding"] == EXPECTED_FARE


# ---------------------------------------------------------------- التسوية


async def test_paying_the_hosted_page_settles_the_ride(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """الدفع عند المزود يثبّت الدفعة ويقيّد نصيب الكبتن (SPEC القسم 6.3)."""
    _rider_, driver, ride, body = await _card_payment(client, session_factory)
    cart_id = body["card_order"]["cart_id"]

    paid = await simulate_card(client, _rider_["headers"], cart_id)
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    state = await payments_of(client, _rider_["headers"], ride["id"])
    payment = _only(state)
    assert payment["status"] == "confirmed"
    assert payment["confirmed_by"] == "system"
    # مرجع الحركة لدى المزود — به يُطابَق الحساب معه
    assert payment["provider_payment_id"]
    assert (await wallet_of(client, driver["headers"]))["balance"] == EXPECTED_FARE


async def test_card_money_never_passes_through_the_riders_wallet(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """**الثابت الأهم في هذه القناة**: لا قيد `ride_payment` على الراكب.

    مالُه خرج من بطاقته لا من رصيده، فخصمُه من المحفظة يخصم منه مرتين. رصيدُه
    قبل الدفع وبعده واحد، ودفترُه بلا قيدٍ لهذه الرحلة — بخلاف الدفع بالمحفظة
    الذي يختبره `test_payments.py`.
    """
    _rider_, driver, ride, body = await _card_payment(client, session_factory)
    await topup_wallet(client, admin_headers, _rider_["user_id"], "20.000")

    await simulate_card(client, _rider_["headers"], body["card_order"]["cart_id"])

    assert (await wallet_of(client, _rider_["headers"]))["balance"] == "20.000"
    entries = (
        await client.get("/wallet/me/transactions", headers=_rider_["headers"])
    ).json()
    assert [entry["type"] for entry in entries] == ["topup"]
    # والكبتن يُقيَّد له كاملاً: المال مرّ بالمنصة فعلاً (بخلاف الكاش وكليك)
    assert (await wallet_of(client, driver["headers"]))["balance"] == EXPECTED_FARE


async def test_commission_applies_to_a_card_ride(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """`ride_earning` كاملاً ثم `commission` خصماً — سطران كما في المحفظة."""
    from tests.helpers import set_commission

    await set_commission(session_factory, "10")
    _rider_, driver, _ride, body = await _card_payment(client, session_factory)

    await simulate_card(client, _rider_["headers"], body["card_order"]["cart_id"])

    entries = (
        await client.get("/wallet/me/transactions", headers=driver["headers"])
    ).json()
    by_type = {entry["type"]: entry for entry in entries}
    assert by_type["ride_earning"]["amount"] == "8.000"
    assert by_type["commission"]["amount"] == "-0.800"
    assert (await wallet_of(client, driver["headers"]))["balance"] == "7.200"


async def test_a_declined_card_reopens_the_debt(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """رفضُ البنك يُسقط الدفعة فيعود المبلغ ديناً — يختار الراكب قناةً أخرى.

    نفس منطق `resolution=unpaid` في نزاع كليك: دفعةٌ سقطت مبلغُها ما زال
    مطلوباً. وبغير إسقاطها تبقى `pending` تحجز المبلغ فلا يُدفع أبداً.
    """
    rider, _driver, ride, body = await _card_payment(client, session_factory)
    cart_id = body["card_order"]["cart_id"]

    declined = await simulate_card(client, rider["headers"], cart_id, "declined")
    assert declined.json()["status"] == "failed"
    assert declined.json()["failure_reason"]

    state = await payments_of(client, rider["headers"], ride["id"])
    assert _only(state)["status"] == "failed"
    assert state["outstanding"] == EXPECTED_FARE
    # الطلب حُسم فلم يبق معلّقاً على الرحلة
    assert state["card_order"] is None

    retry = await pay_ride(client, rider["headers"], ride["id"], "cash", key="retry-k-1")
    assert retry.status_code == 201, retry.text


async def test_an_unsettled_order_stays_open_and_holds_the_amount(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """المزود لم يحسم بعد: لا تسوية ولا إسقاط، والطلب يبقى قابلاً للمتابعة.

    لا تخمين في الاتجاهين: عدّه مدفوعاً يُقيَّد مالاً لم يصل، وعدّه ساقطاً
    يفتح للراكب قناةً ثانية وهو على صفحة الأولى.
    """
    rider, _driver, ride, body = await _card_payment(client, session_factory)
    cart_id = body["card_order"]["cart_id"]

    order = await card_order_of(client, rider["headers"], cart_id)
    assert order["status"] == "created"

    state = await payments_of(client, rider["headers"], ride["id"])
    assert _only(state)["status"] == "pending"
    assert state["outstanding"] == "0.000"
    # ومنه تبني الواجهة زرّ «متابعة الدفع» بعد عودةٍ مقطوعة
    assert state["card_order"]["cart_id"] == cart_id


# ------------------------------------------------------------------ الإشعار


async def test_webhook_settles_the_payment(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """إشعار المزود يسوّي كما يسوّي استعلام العميل — بلا مصادقة، بتوقيع."""
    rider, driver, ride, body = await _card_payment(client, session_factory)
    cart_id = body["card_order"]["cart_id"]

    # الدافع أتمّ العملية عند المزود، والإشعار وصل قبل عودة المتصفح
    from app.core.redis_client import get_redis_client

    await get_redis_client().set(f"card:mock:{cart_id}", "paid")

    notified = await client.post(
        "/payments/card/webhook", data=mock_webhook_payload(cart_id)
    )
    assert notified.status_code == 200, notified.text
    assert notified.json()["status"] == "paid"

    state = await payments_of(client, rider["headers"], ride["id"])
    assert _only(state)["status"] == "confirmed"
    assert (await wallet_of(client, driver["headers"]))["balance"] == EXPECTED_FARE


async def test_webhook_with_a_bad_signature_moves_nothing(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """توقيعٌ لا يطابق = رفضٌ مغلق (SPEC القسم 14).

    ولو كان الطلب مدفوعاً عند المزود فعلاً: إشعارٌ لا نعرف مصدره لا يُقرأ منه
    شيء، ويبقى الحسم للاستعلام الذي تبدؤه الخلفية بنفسها.
    """
    rider, driver, ride, body = await _card_payment(client, session_factory)
    cart_id = body["card_order"]["cart_id"]

    from app.core.redis_client import get_redis_client

    await get_redis_client().set(f"card:mock:{cart_id}", "paid")

    forged = mock_webhook_payload(cart_id) | {"tran_check": "not-the-signature"}
    response = await client.post("/payments/card/webhook", data=forged)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_webhook_signature"

    state = await payments_of(client, rider["headers"], ride["id"])
    assert _only(state)["status"] == "pending"
    assert (await wallet_of(client, driver["headers"]))["balance"] == "0.000"


async def test_webhook_for_an_unknown_store_is_rejected(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """مُعرّف متجرٍ لا عقد له: لا يُبحث له عن عقدٍ آخر يقبل توقيعه."""
    _rider_, _driver, _ride, body = await _card_payment(client, session_factory)
    payload = mock_webhook_payload(body["card_order"]["cart_id"], store_id="someone-else")

    response = await client.post("/payments/card/webhook", data=payload)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_webhook_signature"


async def test_repeated_webhook_is_not_an_error(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """المزودون يعيدون الإرسال حتى يرَوا 200 — وطلبٌ محسومٌ ليس فشلاً.

    والقيود لا تتكرر: مفتاح عدم التكرار مشتقٌّ من مُعرّف الدفعة، وحالةُ الطلب
    تمنع الدخول أصلاً.
    """
    _rider_, driver, _ride, body = await _card_payment(client, session_factory)
    cart_id = body["card_order"]["cart_id"]
    await simulate_card(client, _rider_["headers"], cart_id)

    for _ in range(3):
        again = await client.post(
            "/payments/card/webhook", data=mock_webhook_payload(cart_id)
        )
        assert again.status_code == 200, again.text
        assert again.json()["status"] == "paid"

    assert (await wallet_of(client, driver["headers"]))["balance"] == EXPECTED_FARE
    entries = (
        await client.get("/wallet/me/transactions", headers=driver["headers"])
    ).json()
    assert [entry["type"] for entry in entries] == ["ride_earning"]


# ------------------------------------------------------------- شحن المحفظة


async def test_card_topup_credits_the_wallet_on_provider_confirmation(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """شحن فوريٌّ آلي بلا طلبٍ ينتظر إنساناً (SPEC القسم 7).

    ولذلك لا صفَّ له في `wallet_topup_requests`: ذاك بيتُ ما يؤكده إنسان.
    """
    await enable_card_provider(session_factory)
    rider = await _rider(client)

    created = await client.post(
        "/wallet/me/topups/card",
        json={"amount": "25.000"},
        headers=rider["headers"],
    )
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["purpose"] == "wallet_topup"
    assert order["status"] == "created"
    # لا رصيد قبل جواب المزود
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"

    paid = await simulate_card(client, rider["headers"], order["cart_id"])
    assert paid.json()["status"] == "paid"
    assert paid.json()["transaction_id"] is not None
    assert (await wallet_of(client, rider["headers"]))["balance"] == "25.000"

    entries = (
        await client.get("/wallet/me/transactions", headers=rider["headers"])
    ).json()
    assert [entry["type"] for entry in entries] == ["topup"]
    # ولا طلب شحنٍ معلّق يظهر في اللوحة لشحنةٍ لا تنتظر أحداً
    listed = (
        await client.get("/wallet/me/topups", headers=rider["headers"])
    ).json()
    assert listed == []


async def test_card_topup_needs_the_wallet_feature(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """شحنُ محفظةٍ لا يُدفع منها عبثٌ — نفس حكم بقية قنوات الشحن."""
    await enable_card_provider(session_factory)
    rider = await _rider(client)

    response = await client.post(
        "/wallet/me/topups/card",
        json={"amount": "25.000"},
        headers=rider["headers"],
    )
    assert response.status_code == 403
    assert response.json()["code"] == "feature_disabled"


async def test_frozen_wallet_cannot_be_topped_up_by_card(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    await enable_card_provider(session_factory)
    rider = await _rider(client)
    await client.post(
        f"/admin/wallets/{rider['user_id']}/freeze",
        json={"reason": "اشتباه"},
        headers=admin_headers,
    )

    response = await client.post(
        "/wallet/me/topups/card",
        json={"amount": "25.000"},
        headers=rider["headers"],
    )
    assert response.status_code == 403
    assert response.json()["code"] == "wallet_frozen"


# ------------------------------------------------------ البطاقات المحفوظة


async def test_saving_a_card_fills_saved_cards_without_any_pan(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """Tokenization: يُحفظ رمز المزود وما يكفي للعرض — ولا شيء يُدفع به.

    والرمزُ نفسه لا يخرج من الخلفية أبداً: عرضُه يبطل غرض الـ tokenization
    كله (SPEC القسم 4).
    """
    await enable_card_provider(session_factory)
    rider = await _rider(client)

    created = await client.post(
        "/wallet/me/topups/card",
        json={"amount": "25.000", "save_card": True},
        headers=rider["headers"],
    )
    await simulate_card(client, rider["headers"], created.json()["cart_id"])

    cards = (await client.get("/payments/cards", headers=rider["headers"])).json()
    assert len(cards) == 1
    card = cards[0]
    assert card["last4"] == "4242"
    assert card["brand"] == "Visa"
    assert card["is_default"] is True  # أولى البطاقات افتراضية بلا اختيار
    assert "provider_token" not in card

    async with session_factory() as session:
        stored = (await session.scalars(select(SavedCard))).all()
    assert len(stored) == 1
    # الرمز محفوظ في القاعدة ولا يمر بأي مخطط خروج
    assert stored[0].provider_token


async def test_a_card_is_not_saved_unless_asked(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """الحفظ قرارُ صاحب البطاقة لا افتراضُنا (SPEC القسم 6.4)."""
    await enable_card_provider(session_factory)
    rider = await _rider(client)

    created = await client.post(
        "/wallet/me/topups/card", json={"amount": "5.000"}, headers=rider["headers"]
    )
    await simulate_card(client, rider["headers"], created.json()["cart_id"])

    assert (await client.get("/payments/cards", headers=rider["headers"])).json() == []


async def test_one_tap_payment_settles_without_a_hosted_page(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """الدفع بضغطة: خصمٌ مباشر يُحسم في نداء واحد بلا رابطٍ يُفتح (القسم 6.4)."""
    await enable_card_provider(session_factory)
    rider, driver, ride = await _ready_ride(client, session_factory)

    # بطاقةٌ تُحفظ أولاً عبر شحن محفظة
    topup = await client.post(
        "/wallet/me/topups/card",
        json={"amount": "1.000", "save_card": True},
        headers=rider["headers"],
    )
    await simulate_card(client, rider["headers"], topup.json()["cart_id"])
    card_id = (
        await client.get("/payments/cards", headers=rider["headers"])
    ).json()[0]["id"]

    paid = await client.post(
        f"/rides/{ride['id']}/payments",
        json={
            "method": "card",
            "idempotency_key": "one-tap-key-1",
            "saved_card_id": card_id,
        },
        headers=rider["headers"],
    )
    assert paid.status_code == 201, paid.text
    body = paid.json()

    assert _only(body)["status"] == "confirmed"
    assert body["outstanding"] == "0.000"
    # حُسم فوراً فلا طلب معلّق ولا رابط يُفتح
    assert body["card_order"] is None
    assert (await wallet_of(client, driver["headers"]))["balance"] == EXPECTED_FARE


async def test_another_riders_saved_card_cannot_be_used(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """بطاقةٌ ليست لك غير موجودة بالنسبة إليك — لا IDOR (SPEC القسم 14)."""
    await enable_card_provider(session_factory)
    owner = await _rider(client)
    topup = await client.post(
        "/wallet/me/topups/card",
        json={"amount": "1.000", "save_card": True},
        headers=owner["headers"],
    )
    await simulate_card(client, owner["headers"], topup.json()["cart_id"])
    card_id = (
        await client.get("/payments/cards", headers=owner["headers"])
    ).json()[0]["id"]

    intruder = await _rider(client, OTHER_RIDER)
    assert (
        await client.get("/payments/cards", headers=intruder["headers"])
    ).json() == []

    response = await client.post(
        "/wallet/me/topups/card",
        json={"amount": "1.000", "saved_card_id": card_id},
        headers=intruder["headers"],
    )
    assert response.status_code == 404

    assert (
        await client.delete(
            f"/payments/cards/{card_id}", headers=intruder["headers"]
        )
    ).status_code == 404


async def test_deleting_the_default_card_promotes_another(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """محفظةُ بطاقاتٍ بلا افتراضية تجعل «الدفع بضغطة» بلا ضغطة تُعرض."""
    await enable_card_provider(session_factory)
    rider = await _rider(client)

    async with session_factory() as session:
        for index, last4 in enumerate(("1111", "2222")):
            session.add(
                SavedCard(
                    user_id=uuid.UUID(rider["user_id"]),
                    provider_token=f"token-{last4}",
                    brand="Visa",
                    last4=last4,
                    expiry_month=1,
                    expiry_year=2031,
                    is_default=index == 0,
                )
            )
        await session.commit()

    cards = (await client.get("/payments/cards", headers=rider["headers"])).json()
    default_id = next(card["id"] for card in cards if card["is_default"])

    assert (
        await client.delete(
            f"/payments/cards/{default_id}", headers=rider["headers"]
        )
    ).status_code == 204

    remaining = (await client.get("/payments/cards", headers=rider["headers"])).json()
    assert len(remaining) == 1
    assert remaining[0]["is_default"] is True


async def test_setting_a_default_card_unsets_the_others(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    async with session_factory() as session:
        for index, last4 in enumerate(("1111", "2222")):
            session.add(
                SavedCard(
                    user_id=uuid.UUID(rider["user_id"]),
                    provider_token=f"token-{last4}",
                    last4=last4,
                    expiry_month=1,
                    expiry_year=2031,
                    is_default=index == 0,
                )
            )
        await session.commit()

    cards = (await client.get("/payments/cards", headers=rider["headers"])).json()
    target = next(card["id"] for card in cards if not card["is_default"])

    promoted = await client.post(
        f"/payments/cards/{target}/default", headers=rider["headers"]
    )
    assert promoted.status_code == 200, promoted.text

    cards = (await client.get("/payments/cards", headers=rider["headers"])).json()
    assert [card["is_default"] for card in cards] == [True, False]
    assert cards[0]["id"] == target


# ------------------------------------------------------------------ الاسترداد


async def test_refunding_a_card_payment_goes_through_the_provider(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """الردُّ يعود من حيث جاء المال: إلى البطاقة لا إلى المحفظة (القسم 6.4).

    ولذلك لا قيد `refund` للراكب — رصيدُه لم يُخصم أصلاً، فردُّه إليه رصيداً
    يمنحه مرتين. وقيدُ الكبتن المضاد يبقى: أرباحُه هي ما قُيّد فعلاً فيُنقض.
    """
    rider, driver, ride, body = await _card_payment(client, session_factory)
    await simulate_card(client, rider["headers"], body["card_order"]["cart_id"])
    payment_id = _only(await payments_of(client, rider["headers"], ride["id"]))["id"]

    refunded = await client.post(
        f"/admin/payments/{payment_id}/refund",
        json={"reason": "شكوى الراكب"},
        headers=admin_headers,
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"

    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"
    assert (await wallet_of(client, driver["headers"]))["balance"] == "0.000"

    driver_entries = (
        await client.get("/wallet/me/transactions", headers=driver["headers"])
    ).json()
    assert {entry["type"] for entry in driver_entries} == {
        "ride_earning",
        "adjustment",
    }

    async with session_factory() as session:
        order = await session.scalar(select(ProviderOrder))
    # مرجع الردّ لدى المزود محفوظ — به يُطابَق الحساب معه
    assert order.refund_ref
    # والحالة تبقى `paid`: الطلب دُفع فعلاً، والردُّ حركةٌ تالية لا نقضٌ لتاريخه
    assert order.status.value == "paid"


async def test_an_unpaid_card_order_cannot_be_refunded(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """لا ردَّ لما لم يُدفع — والدفعة `pending` أصلاً لا تنتقل إلى `refunded`."""
    _rider_, _driver, ride, body = await _card_payment(client, session_factory)
    payment_id = _only(await payments_of(client, _rider_["headers"], ride["id"]))["id"]

    response = await client.post(
        f"/admin/payments/{payment_id}/refund",
        json={"reason": "تجربة"},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_payment_transition"


# -------------------------------------------------------------- الملكية


async def test_another_rider_cannot_read_a_card_order(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """404 لا 403: وجود طلبٍ ماليٍّ ليس معلومة يستحقها غير صاحبه."""
    _rider_, _driver, _ride, body = await _card_payment(client, session_factory)
    intruder = await _rider(client, OTHER_RIDER)

    response = await client.get(
        f"/payments/card/orders/{body['card_order']['cart_id']}",
        headers=intruder["headers"],
    )
    assert response.status_code == 404


async def test_mock_simulation_is_closed_when_the_contract_is_real(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """مسار المحاكاة لا يفتح باباً لا يفتحه العقد نفسه (SPEC القسم 15)."""
    _rider_, _driver, _ride, body = await _card_payment(client, session_factory)
    cart_id = body["card_order"]["cart_id"]

    # المشرف يبدّل العقد إلى مزود حقيقي بعد فتح الطلب
    await enable_card_provider(session_factory, use_mock=False)

    response = await simulate_card(client, _rider_["headers"], cart_id)
    assert response.status_code == 501
    assert response.json()["code"] == "feature_not_available"


async def test_amount_mismatch_opens_a_dispute_instead_of_crediting(
    client: AsyncClient,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
    monkeypatch,
) -> None:
    """مبلغُ المزود يخالف مبلغَنا: نزاعٌ تفصله الإدارة، لا قيدٌ بلا يقين.

    حالةٌ لا يجوز أن تُقفل بتخمين: عدُّها ناجحةً يقيّد مبلغاً لم يُتفق عليه،
    وعدُّها فاشلةً يفتح الرحلة للدفع مرتين ومالُ الراكب قد خرج.
    """
    from app.services.card_gateway import mock as mock_module

    _rider_, driver, ride, body = await _card_payment(client, session_factory)
    cart_id = body["card_order"]["cart_id"]

    original = mock_module.MockCardGateway.check_order

    async def _wrong_amount(self, provider_order_ref: str):
        from dataclasses import replace

        state = await original(self, provider_order_ref)
        return replace(state, amount=Decimal("999.000"))

    monkeypatch.setattr(mock_module.MockCardGateway, "check_order", _wrong_amount)

    settled = await simulate_card(client, _rider_["headers"], cart_id)
    assert settled.json()["status"] == "failed"
    assert "لا يطابق" in settled.json()["failure_reason"]

    state = await payments_of(client, _rider_["headers"], ride["id"])
    payment = _only(state)
    assert payment["status"] == "disputed"
    assert payment["dispute_reason"]
    # المبلغ يبقى محجوزاً: لا يُدفع مرتين ولا يُقيَّد بلا حكم
    assert state["outstanding"] == "0.000"
    assert (await wallet_of(client, driver["headers"]))["balance"] == "0.000"


# ------------------------------------------------ الغرضُ الذي لا يعرفه الفرع


async def test_a_paid_order_with_a_purpose_the_card_channel_does_not_settle_moves_nothing(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**كان كلُّ غرضٍ غيرِ الرحلة والاشتراك يُقيَّد شحناً للمحفظة** (`else:`).

    العطبُ مسمّى في `SPEC-DELIVERY.md` §D7: غرضٌ يُضاف بعده — اشتراكُ تاجر أولُها
    — كان سيصير مالاً في محفظة صاحب الطلب بلا خطأ. فالفرعُ صار تعداداً صريحاً،
    **والمجهولُ يُرفض ولا يُقيَّد**. و`debt` هنا غرضٌ قائمٌ لا تسوّيه قناةُ البطاقة
    (سدادُ الدَّين بكليك وحدَه)، فهو أقربُ مثالٍ حيٍّ على «غرضٍ لا يعرفه الفرع».
    """
    from app.core.exceptions import UnsupportedOrderPurpose
    from app.models.enums import CountryCode, Currency, ProviderOrderPurpose
    from app.services import card_payments
    from app.services.card_gateway.base import OrderState

    rider = await _rider(client)
    cart_id = f"t{uuid.uuid4().hex[:20]}"
    async with session_factory() as session:
        session.add(
            ProviderOrder(
                purpose=ProviderOrderPurpose.DEBT,
                cart_id=cart_id,
                user_id=uuid.UUID(rider["user_id"]),
                country_code=CountryCode.JO,
                amount=Decimal("25.000"),
                currency=Currency.JOD,
            )
        )
        await session.commit()

    async with session_factory() as session:
        try:
            await card_payments.apply_state(
                session,
                cart_id=cart_id,
                state=OrderState(
                    provider_order_ref="ref-unknown-purpose",
                    settled=True,
                    paid=True,
                    status_text="paid",
                    amount=Decimal("25.000"),
                ),
            )
        except UnsupportedOrderPurpose as error:
            assert error.code == "unsupported_order_purpose"
            await session.rollback()
        else:  # pragma: no cover - هو العطبُ نفسُه
            await session.commit()
            raise AssertionError("قُيِّد غرضٌ لا تعرفه قناةُ البطاقة")

    # لا قيدَ في المحفظة، والطلبُ لم يُعلَّم مدفوعاً
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"
    async with session_factory() as session:
        order = await session.scalar(
            select(ProviderOrder).where(ProviderOrder.cart_id == cart_id)
        )
        assert order is not None
        assert order.status.value == "created"
