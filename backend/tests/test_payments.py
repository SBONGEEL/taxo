"""تحصيل أجرة الرحلة بقنواتها الأربع (SPEC القسم 6/9/13.4).

الثابت الذي تدور حوله كل هذه الاختبارات: **لا مبلغ يصل من العميل**، والمبلغ
هو المتبقي من `final_fare` محسوباً في الخلفية؛ ولا يتحرك الدفتر إلا عند
`confirmed`.
"""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from tests.helpers import (
    DRIVER,
    EXPECTED_FARE,
    OTHER_RIDER,
    RIDER,
    SECOND_DRIVER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    pay_ride,
    payments_of,
    register,
    set_cliq_alias,
    set_commission,
    enable_features,
    started_ride,
    topup_wallet,
    wallet_of,
)


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    body = await register(client, payload)
    return {"headers": auth(body), "user_id": body["user"]["id"]}


async def _online_driver(
    client: AsyncClient, session_factory, payload: dict = DRIVER, **kwargs
) -> dict:
    driver = await approved_driver(client, session_factory, payload, **kwargs)
    await bring_online(client, driver)
    return driver


async def _ready_ride(client: AsyncClient, session_factory) -> tuple[dict, dict, dict]:
    """راكبٌ وكبتنٌ ورحلةٌ منتهية بأجرة 8.000 — نقطة بداية كل اختبار دفع."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider["headers"], driver)
    return rider, driver, ride


def _only(body: dict) -> dict:
    assert len(body["payments"]) == 1, body["payments"]
    return body["payments"][0]


# ---------------------------------------------------------------------- الكاش


async def test_cash_payment_waits_for_the_driver_to_confirm(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الكاش يبقى `pending` حتى يضغط الكبتن «استلمت المبلغ» (SPEC القسم 6.1)."""
    rider, driver, ride = await _ready_ride(client, session_factory)

    created = await pay_ride(client, rider["headers"], ride["id"], "cash")
    assert created.status_code == 201, created.text
    body = created.json()
    payment = _only(body)
    assert payment["status"] == "pending"
    assert payment["amount"] == EXPECTED_FARE
    assert payment["currency"] == "JOD"
    assert body["outstanding"] == "0.000"  # محجوزة بدفعةٍ قائمة

    confirmed = await client.post(
        f"/payments/{payment['id']}/confirm", headers=driver["headers"]
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["confirmed_by"] == "driver"


async def test_cash_ride_does_not_touch_the_driver_wallet(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """الكبتن قبض المال بيده، فلا قيد `ride_earning` له (SPEC القسم 9)."""
    rider, driver, ride = await _ready_ride(client, session_factory)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    await client.post(f"/payments/{payment['id']}/confirm", headers=driver["headers"])

    assert (await wallet_of(client, driver["headers"]))["balance"] == "0.000"
    entries = (
        await client.get("/wallet/me/transactions", headers=driver["headers"])
    ).json()
    assert entries == []


async def test_cannot_pay_a_ride_that_has_not_completed(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """شاشة الدفع تلي الإنهاء في تدفق القسم 5."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider["headers"], driver)

    response = await pay_ride(client, rider["headers"], ride["id"], "cash")
    assert response.status_code == 409
    assert response.json()["code"] == "ride_not_payable"


async def test_a_ride_is_not_paid_twice(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider, _driver, ride = await _ready_ride(client, session_factory)
    await pay_ride(client, rider["headers"], ride["id"], "cash", key="first-key-1")

    second = await pay_ride(
        client, rider["headers"], ride["id"], "cash", key="second-key-2"
    )
    assert second.status_code == 409
    assert second.json()["code"] == "ride_already_paid"


async def test_same_idempotency_key_returns_the_same_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """ضغطة مكررة لا تُحصّل مرتين (SPEC القسم 14)."""
    rider, _driver, ride = await _ready_ride(client, session_factory)

    first = await pay_ride(client, rider["headers"], ride["id"], "cash", key="same-key-1")
    second = await pay_ride(
        client, rider["headers"], ride["id"], "cash", key="same-key-1"
    )

    assert (first.status_code, second.status_code) == (201, 201)
    assert _only(first.json())["id"] == _only(second.json())["id"]


# -------------------------------------------------------------------- المحفظة


async def test_wallet_payment_debits_rider_and_credits_driver(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    rider, driver, ride = await _ready_ride(client, session_factory)
    await topup_wallet(client, admin_headers, rider["user_id"], "20.000")

    body = (await pay_ride(client, rider["headers"], ride["id"], "wallet")).json()
    payment = _only(body)

    # المحفظة لا تنتظر أحداً: القناة الوحيدة التي يشهد عليها الدفتر
    assert payment["status"] == "confirmed"
    assert payment["confirmed_by"] == "system"
    assert payment["transaction_id"] is not None
    assert (await wallet_of(client, rider["headers"]))["balance"] == "12.000"
    assert (await wallet_of(client, driver["headers"]))["balance"] == "8.000"


async def test_partial_balance_splits_into_wallet_plus_cash(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """الدفع المختلط: صفّان على رحلة واحدة (SPEC القسم 6)."""
    rider, driver, ride = await _ready_ride(client, session_factory)
    await topup_wallet(client, admin_headers, rider["user_id"], "3.000")

    body = (await pay_ride(client, rider["headers"], ride["id"], "wallet")).json()
    by_method = {entry["method"]: entry for entry in body["payments"]}

    assert set(by_method) == {"wallet", "cash"}
    assert by_method["wallet"]["amount"] == "3.000"
    assert by_method["wallet"]["status"] == "confirmed"
    assert by_method["cash"]["amount"] == "5.000"
    assert by_method["cash"]["status"] == "pending"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.000"
    # الكبتن يقبض الخمسة الباقية بيده، فلا يدخل محفظته إلا ما مرّ بالمنصة
    assert (await wallet_of(client, driver["headers"]))["balance"] == "3.000"

    await client.post(
        f"/payments/{by_method['cash']['id']}/confirm", headers=driver["headers"]
    )
    assert (await wallet_of(client, driver["headers"]))["balance"] == "3.000"


async def test_empty_wallet_is_rejected_rather_than_split(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """رصيدٌ صفر ليس «دفعاً مختلطاً» بل اختيارُ قناةٍ خاطئة."""
    rider, _driver, ride = await _ready_ride(client, session_factory)

    response = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_balance"


async def test_wallet_payment_requires_the_feature_flag(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """غياب الصف = معطّل. لا افتراض تفعيل أبداً (SPEC القسم 4)."""
    rider, _driver, ride = await _ready_ride(client, session_factory)

    response = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert response.status_code == 403
    assert response.json()["code"] == "feature_disabled"


async def test_frozen_wallet_cannot_pay(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    rider, _driver, ride = await _ready_ride(client, session_factory)
    await topup_wallet(client, admin_headers, rider["user_id"], "20.000")
    await client.post(
        f"/admin/wallets/{rider['user_id']}/freeze",
        json={"reason": "اشتباه"},
        headers=admin_headers,
    )

    response = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert response.status_code == 403
    assert response.json()["code"] == "wallet_frozen"


# ---------------------------------------------------------------------- كليك


async def test_cliq_payment_exposes_the_driver_alias(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """شاشة الدفع تعرض alias الكبتن مع المبلغ (SPEC القسم 6.2)."""
    await enable_features(session_factory, "cliq_enabled")
    rider, driver, ride = await _ready_ride(client, session_factory)
    await set_cliq_alias(session_factory, driver["driver_id"], "0799999999")

    body = (await pay_ride(client, rider["headers"], ride["id"], "cliq")).json()
    assert _only(body)["status"] == "pending"
    assert body["cliq_alias"] == "0799999999"


async def test_cliq_without_an_alias_has_nowhere_to_send_the_money(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, "cliq_enabled")
    rider, _driver, ride = await _ready_ride(client, session_factory)

    response = await pay_ride(client, rider["headers"], ride["id"], "cliq")
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_cliq_requires_the_feature_flag(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider, _driver, ride = await _ready_ride(client, session_factory)
    response = await pay_ride(client, rider["headers"], ride["id"], "cliq")
    assert response.status_code == 403


# -------------------------------------------------------------------- النزاع


async def _disputed_payment(client: AsyncClient, session_factory) -> tuple[dict, dict, dict]:
    await enable_features(session_factory, "cliq_enabled")
    rider, driver, ride = await _ready_ride(client, session_factory)
    await set_cliq_alias(session_factory, driver["driver_id"])

    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cliq")).json())
    disputed = await client.post(
        f"/payments/{payment['id']}/dispute",
        json={"reason": "لم تصلني الحوالة"},
        headers=driver["headers"],
    )
    assert disputed.status_code == 200, disputed.text
    return rider, driver, disputed.json()


async def test_driver_can_dispute_a_cliq_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    _rider_, _driver, payment = await _disputed_payment(client, session_factory)
    assert payment["status"] == "disputed"
    assert payment["dispute_reason"] == "لم تصلني الحوالة"
    assert payment["disputed_at"] is not None


async def test_cash_cannot_be_disputed(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الكاش يقع يداً بيد فلا فراغ فيه يفصل فيه إنسان (SPEC القسم 6)."""
    rider, driver, ride = await _ready_ride(client, session_factory)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())

    response = await client.post(
        f"/payments/{payment['id']}/dispute",
        json={"reason": "تجربة"},
        headers=driver["headers"],
    )
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_payment_transition"


async def test_support_resolves_a_dispute_in_the_drivers_favour(
    client: AsyncClient, support_headers: dict, jordan_settings: None, session_factory
) -> None:
    """`support` يفصل في النزاعات — نصُّ القسم 13.8."""
    _rider_, _driver, payment = await _disputed_payment(client, session_factory)

    resolved = await client.post(
        f"/admin/payments/{payment['id']}/resolve",
        json={"resolution": "paid", "note": "تأكد وصول الحوالة"},
        headers=support_headers,
    )
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["status"] == "confirmed"
    assert body["confirmed_by"] == "admin"
    assert body["resolution"] == "paid"
    assert body["resolved_at"] is not None


async def test_resolving_against_the_driver_reopens_the_debt(
    client: AsyncClient, support_headers: dict, jordan_settings: None, session_factory
) -> None:
    """دفعةٌ سقطت مبلغُها ما زال مطلوباً — يفتح الراكب قناةً أخرى."""
    rider, _driver, payment = await _disputed_payment(client, session_factory)
    ride_id = payment["ride_id"]

    await client.post(
        f"/admin/payments/{payment['id']}/resolve",
        json={"resolution": "unpaid"},
        headers=support_headers,
    )

    state = await payments_of(client, rider["headers"], ride_id)
    assert state["payments"][0]["status"] == "failed"
    assert state["outstanding"] == EXPECTED_FARE

    retry = await pay_ride(client, rider["headers"], ride_id, "cash", key="retry-key-1")
    assert retry.status_code == 201, retry.text


# ------------------------------------------------------------------- العمولة


async def test_commission_is_a_visible_line_beside_the_earning(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """`ride_earning` بالكامل ثم `commission` خصماً — الصافي والسطر معاً."""
    await set_commission(session_factory, "10")
    rider, driver, ride = await _ready_ride(client, session_factory)
    await topup_wallet(client, admin_headers, rider["user_id"], "20.000")

    await pay_ride(client, rider["headers"], ride["id"], "wallet")

    entries = (
        await client.get("/wallet/me/transactions", headers=driver["headers"])
    ).json()
    by_type = {entry["type"]: entry for entry in entries}
    assert by_type["ride_earning"]["amount"] == "8.000"
    assert by_type["commission"]["amount"] == "-0.800"
    assert (await wallet_of(client, driver["headers"]))["balance"] == "7.200"


async def test_cashless_scope_spares_cash_rides(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """`cashless_rides` = ما تمر أمواله بالمنصة وحده (SPEC القسم 4)."""
    await set_commission(session_factory, "10", applies_to="cashless_rides")
    rider, driver, ride = await _ready_ride(client, session_factory)

    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    await client.post(f"/payments/{payment['id']}/confirm", headers=driver["headers"])

    assert (await wallet_of(client, driver["headers"]))["balance"] == "0.000"


async def test_commission_on_a_cash_ride_needs_a_funded_wallet(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """نطاق `all_rides` يستحق عمولةً على الكاش — تُخصم من محفظة الكبتن.

    ومحفظةٌ فارغة تعني رفضَ التأكيد لا خصماً على المكشوف (SPEC القسم 4):
    المحفظة مسبقة الدفع. هذا قيدٌ تشغيلي على من يرفع النطاق إلى `all_rides`.
    """
    await set_commission(session_factory, "10")
    rider, driver, ride = await _ready_ride(client, session_factory)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())

    blocked = await client.post(
        f"/payments/{payment['id']}/confirm", headers=driver["headers"]
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "insufficient_balance"

    await topup_wallet(client, admin_headers, driver["user_id"], "5.000")
    confirmed = await client.post(
        f"/payments/{payment['id']}/confirm", headers=driver["headers"]
    )
    assert confirmed.status_code == 200, confirmed.text
    assert (await wallet_of(client, driver["headers"]))["balance"] == "4.200"


async def test_commission_is_frozen_at_ride_creation(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """رفعُ النسبة بعد إنشاء الرحلة لا يمسّها (SPEC القسم 4)."""
    rider, driver, ride = await _ready_ride(client, session_factory)
    await set_commission(session_factory, "25")  # بعد الرحلة
    await topup_wallet(client, admin_headers, rider["user_id"], "20.000")

    await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert (await wallet_of(client, driver["headers"]))["balance"] == "8.000"


# ----------------------------------------------------------------- الاسترداد


async def test_admin_refunds_a_wallet_payment_with_opposing_entries(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """الردّ قيدان جديدان لا محوٌ لقيد — الدفتر لا يُعدَّل (SPEC القسم 4)."""
    rider, driver, ride = await _ready_ride(client, session_factory)
    await topup_wallet(client, admin_headers, rider["user_id"], "20.000")
    payment = _only(
        (await pay_ride(client, rider["headers"], ride["id"], "wallet")).json()
    )

    refunded = await client.post(
        f"/admin/payments/{payment['id']}/refund",
        json={"reason": "شكوى الراكب"},
        headers=admin_headers,
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "20.000"
    assert (await wallet_of(client, driver["headers"]))["balance"] == "0.000"


async def test_cash_cannot_be_refunded_by_the_platform(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """مالٌ لم يدخل المنصة لا تملك ردّه (SPEC القسم 9)."""
    rider, driver, ride = await _ready_ride(client, session_factory)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    await client.post(f"/payments/{payment['id']}/confirm", headers=driver["headers"])

    response = await client.post(
        f"/admin/payments/{payment['id']}/refund",
        json={"reason": "تجربة"},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_payment_transition"


async def test_support_cannot_refund(
    client: AsyncClient,
    admin_headers: dict,
    support_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """`support` يفصل في النزاعات ولا يحرّك مالاً (SPEC القسم 13.8)."""
    rider, _driver, ride = await _ready_ride(client, session_factory)
    await topup_wallet(client, admin_headers, rider["user_id"], "20.000")
    payment = _only(
        (await pay_ride(client, rider["headers"], ride["id"], "wallet")).json()
    )

    response = await client.post(
        f"/admin/payments/{payment['id']}/refund",
        json={"reason": "تجربة"},
        headers=support_headers,
    )
    assert response.status_code == 403


# ------------------------------------------------------------------- البطاقة


async def test_card_needs_a_provider_contract_not_just_the_flag(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """البطاقة صارت مبنيّة في المرحلة 6-ب، فلم يبق لها 501.

    مفتاحٌ مرفوعٌ بلا عقدٍ مفعّل يردّ 503 يدل على العقد، وغيابُ المفتاح يردّ 403
    قراراً إدارياً. تدفّقُها كله في `test_card_payments.py`.
    """
    await enable_features(session_factory, "card_enabled")
    rider, _driver, ride = await _ready_ride(client, session_factory)

    response = await pay_ride(client, rider["headers"], ride["id"], "card")
    assert response.status_code == 503
    assert response.json()["code"] == "card_gateway_unavailable"


# ------------------------------------------------------------------ الملكية


async def test_another_rider_cannot_pay_someone_elses_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """404 لا 403: وجود الرحلة ليس معلومة يستحقها غير أطرافها."""
    _rider_, _driver, ride = await _ready_ride(client, session_factory)
    intruder = await _rider(client, OTHER_RIDER)

    response = await pay_ride(client, intruder["headers"], ride["id"], "cash")
    assert response.status_code == 404


async def test_another_driver_cannot_confirm_the_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider, _driver, ride = await _ready_ride(client, session_factory)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    intruder = await _online_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-9999"
    )

    response = await client.post(
        f"/payments/{payment['id']}/confirm", headers=intruder["headers"]
    )
    assert response.status_code == 403


async def test_rider_cannot_confirm_their_own_cash_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """التأكيد إقرارُ الكبتن بالاستلام، لا إقرارُ الراكب بالدفع."""
    rider, _driver, ride = await _ready_ride(client, session_factory)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())

    response = await client.post(
        f"/payments/{payment['id']}/confirm", headers=rider["headers"]
    )
    assert response.status_code == 403


async def test_outstanding_reflects_what_is_still_owed(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider, _driver, ride = await _ready_ride(client, session_factory)

    before = await payments_of(client, rider["headers"], ride["id"])
    assert before["outstanding"] == EXPECTED_FARE
    assert before["final_fare"] == EXPECTED_FARE
    assert before["payments"] == []

    await pay_ride(client, rider["headers"], ride["id"], "cash")
    after = await payments_of(client, rider["headers"], ride["id"])
    assert after["outstanding"] == "0.000"
    assert Decimal(after["payments"][0]["amount"]) == Decimal(EXPECTED_FARE)
