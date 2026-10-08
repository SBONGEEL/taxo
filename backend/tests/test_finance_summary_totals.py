"""مجاميعُ الملخّصات المالية (SPEC §٦٥-د/٢ و٩) — **كلُّ بطاقةٍ بمسارها الحقيقيّ، لا بصفِّ مالٍ يُبنى بيد** (`test_no_shortcut_fixtures`).

**وكلُّ اختبارٍ يشترط المطابقةَ في آخره**: الرقمُ الصحيحُ في البطاقة لا يكفي إن خالف الدفترَ الخامَ في سطرٍ آخر.

**وما لا يُقاد هنا بمساره — يُقال**: خصمُ المشاركة (`share_discounts`) يحتاج راكبين على ممرٍّ جغرافيٍّ واحد (`test_ride_sharing*`
يبنيان رحلتيه بيدٍ مصنَّفة)، **وبانيه هو بانيه الكوبون نفسُه** (`_payments` بقناةٍ أخرى) — فيُقاس البانيُ هنا بالكوبون.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import update

from app.models.booking import RideBooking
from app.models.cancellation import CancellationSetting
from app.models.enums import CountryCode, FeatureKey, PromoDiscountType
from app.models.facility import Facility
from app.models.payment_setting import PaymentSetting
from app.models.promo import PromoCode
from app.models.service_setting import ServiceSetting
from app.models.user import User
from app.models.wallet_setting import WalletSetting
from app.services import cashback
from app.services import referrals as referrals_service
from tests.helpers import (
    DRIVER,
    DROPOFF,
    NEAR_PICKUP,
    OTHER_RIDER,
    PICKUP,
    RIDER,
    SECOND_DRIVER,
    SUBSCRIPTION_PLAN_NAME,
    THIRD_DRIVER,
    accepted_ride,
    approved_driver,
    auth,
    bring_online,
    broadcast_location,
    completed_ride,
    enable_card_provider,
    enable_features,
    ensure_plan,
    pay_ride,
    payments_of,
    register,
    rider_session,
    set_cliq_alias,
    set_commission,
    simulate_card,
    topup_wallet,
    wait_for_offer,
)
from tests.test_finance_summary import amount, assert_reconciled, drill, finance_reader, metric, summary
from tests.test_referrals import _my_referrals, _set_policy, _stamp_female
from tests.test_subscription_offers import make_offer
from tests.test_wallet_freeze_per_wallet import _dual_driver, _freeze

THIRD_RIDER = RIDER | {"phone": "0796666666", "name": "راكبٌ ثالث"}
FOURTH_RIDER = RIDER | {"phone": "0797777777", "name": "راكبٌ رابع"}
FIFTH_RIDER = RIDER | {"phone": "0798888888", "name": "راكبٌ خامس"}
FAR_AWAY = {"lat": 32.0060, "lng": 35.9106}


async def _adjust(client: AsyncClient, admin_headers: dict, user_id: str, value: str, wallet: str) -> None:
    """**بابُ التصحيح في اللوحة** — البابُ الحقيقيُّ الوحيدُ لرصيدٍ بلا شحن (قيدُ `adjustment` باسم المشرف)."""
    done = await client.post(
        f"/admin/wallets/{user_id}/adjustments",
        json={"amount": value, "reason": "رصيدُ اختبار الملخّصات", "wallet": wallet},
        headers=admin_headers,
    )
    assert done.status_code == 200, done.text


async def _drive(client: AsyncClient, rider_headers: dict, driver: dict, body: dict) -> dict:
    """طلبٌ بجسمٍ يكتبه الاختبار (مطار · طرد · كوبون) ثمّ المسارُ كلُّه حتى الإنهاء — كما يفعل التطبيقان."""
    created = await client.post("/rides", json=body, headers=rider_headers)
    assert created.status_code == 201, created.text
    ride_id = created.json()["id"]
    await wait_for_offer(ride_id, driver["driver_id"])
    for step in ("accept", "arrive", "start", "complete"):
        response = await client.post(f"/rides/{ride_id}/{step}", headers=driver["headers"])
        assert response.status_code == 200, (step, response.text)
    return response.json()


async def _cash(client: AsyncClient, rider: dict, ride: dict, driver: dict | None) -> dict:
    """دفعةُ كاشٍ على رحلةٍ منتهية — **ويؤكّدها الكبتنُ إن مُرِّر**، وإلا بقيت «غيرَ مؤكَّدة»."""
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash", key=f"pay-{ride['id']}")
    assert paid.status_code == 201, paid.text
    payment = next(row for row in paid.json()["payments"] if row["method"] == "cash")
    if driver is not None:
        confirmed = await client.post(f"/payments/{payment['id']}/confirm", headers=driver["headers"])
        assert confirmed.status_code == 200, confirmed.text
    return payment


# ═════════════════════════════════════════════════════════════ الدفترُ: الأرصدةُ والشحنُ والعمولة


async def test_wallet_balances_topups_and_commission_come_from_the_ledger(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    """راكبٌ يشحن ٢٠ ويدفع رحلةً بـ٨ من محفظته بعمولة ١٠٪: **له ١٢، وللكبتن ٧٫٢٠٠، والعمولةُ ٠٫٨٠٠** — كلُّها من الدفتر."""
    reader = await finance_reader(client, admin_headers)
    await set_commission(session_factory, "10")
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    ride = await completed_ride(client, rider["headers"], driver)
    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert paid.status_code == 201, paid.text

    body = await summary(client, reader)
    assert amount(body, "rider_balances") == Decimal("12.000")
    assert metric(body, "rider_balances")["users"] == 1
    assert metric(body, "rider_balances")["stock"] is True
    assert amount(body, "captain_balances") == Decimal("7.200")
    assert amount(body, "captain_balances_other") == Decimal("7.200")
    assert amount(body, "captain_balances_cliq") == Decimal("0.000")
    # **لا احتجازَ في السوق ولا طلبَ سحب** ⇒ الرصيدُ كلُّه يُصرف الآن
    assert amount(body, "captain_payable_now") == Decimal("7.200")
    assert amount(body, "captain_not_due") == Decimal("0.000")
    assert amount(body, "topups") == Decimal("20.000") == amount(body, "topups_cash")
    assert amount(body, "commission_collected") == Decimal("0.800")
    assert metric(body, "commission_collected")["count"] == 1
    # **لا ردَّ في الفترة** ⇒ الصافي هو المحصَّل
    assert amount(body, "commission_refunded") == Decimal("0.000")
    assert amount(body, "commission_net") == Decimal("0.800")
    # **والاشتراكُ الذي يكتبه `approved_driver` بيعٌ في الفترة** — صفٌّ وصل مالُه نقداً
    assert amount(body, "subscriptions_sold") == Decimal("30.000")
    for key, expected in (
        ("ledger.ride_payment", "-8.000"),
        ("ledger.ride_earning", "8.000"),
        ("ledger.commission", "-0.800"),
        ("ledger.topup", "20.000"),
    ):
        assert amount(body, key) == Decimal(expected), key
    assert_reconciled(body)

    users = await drill(client, reader, "rider_balances", "users")
    assert [(row["user_id"], row["amount"], row["role"]) for row in users["rows"]] == [
        (rider["user"]["id"], "12.000", "rider")
    ]
    lines = await drill(client, reader, "commission_collected", "transactions")
    assert [(row["amount"], row["ride_id"], row["kind"], row["kind_label"]) for row in lines["rows"]] == [
        ("0.800", ride["id"], "commission", "عمولة")
    ]
    # **مرشِّحٌ لا ينطبق يُقال ولا يُصفَّر**: أرصدةُ الركّاب لا تخصّ الكباتن
    as_captain = await summary(client, reader, user_type="driver")
    assert metric(as_captain, "rider_balances")["applicable"] is False
    assert metric(as_captain, "rider_balances")["reason"]
    refused = await drill(client, reader, "rider_balances", "users", user_type="driver")
    assert refused["metric"]["applicable"] is False and refused["rows"] == []


async def test_topups_are_split_by_the_channel_of_their_source_row(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    """**كليكٌ يدويٌّ يؤكّده مشرف، وبطاقةٌ عند Telr، وكاشٌ من اللوحة** — كلٌّ بقناته من صفِّ مصدره لا من نصّ."""
    reader = await finance_reader(client, admin_headers)
    await enable_card_provider(session_factory)
    rider = await rider_session(client)

    requested = await client.post(
        "/wallet/me/topups",
        json={"method": "cliq", "amount": "12.000", "reference": "CLQ-991"},
        headers=rider["headers"],
    )
    assert requested.status_code == 201, requested.text
    confirmed = await client.post(f"/admin/topups/{requested.json()['id']}/confirm", json={}, headers=admin_headers)
    assert confirmed.status_code == 200, confirmed.text

    order = await client.post("/wallet/me/topups/card", json={"amount": "25.000"}, headers=rider["headers"])
    assert order.status_code == 201, order.text
    assert (await simulate_card(client, rider["headers"], order.json()["cart_id"])).json()["status"] == "paid"

    await topup_wallet(client, admin_headers, rider["user"]["id"], "7.000")

    body = await summary(client, reader)
    assert amount(body, "topups") == Decimal("44.000")
    assert metric(body, "topups")["count"] == 3
    assert (amount(body, "topups_cliq"), amount(body, "topups_card"), amount(body, "topups_cash")) == (
        Decimal("12.000"),
        Decimal("25.000"),
        Decimal("7.000"),
    )
    assert amount(body, "rider_balances") == Decimal("44.000")
    assert_reconciled(body)

    lines = await drill(client, reader, "topups", "transactions")
    assert [(row["amount"], row["method"], row["method_label"]) for row in lines["rows"]] == [
        ("25.000", "card", "بطاقة"),
        ("12.000", "cliq", "كليك"),
        ("7.000", "cash", "كاش"),
    ]
    by_card = await summary(client, reader, method="card")
    assert amount(by_card, "topups") == Decimal("25.000")
    assert metric(by_card, "topups_cliq")["applicable"] is False


# ═════════════════════════════════════════════════════════════ رحلاتُ الكاش وكليك، وديونُ الكباتن


async def test_cash_and_cliq_rides_by_status_and_debts_by_the_ceiling(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    """كاشٌ مؤكَّدٌ بعمولة ١٥٪ على كبتنٍ بلا رصيد ⇒ **دَينٌ ١٫٢٠٠ فوق سقف ١٫٠٠٠**؛ وكليكٌ متنازَعٌ عليه؛ وكاشٌ لم يُؤكَّد."""
    reader = await finance_reader(client, admin_headers)
    await set_commission(session_factory, "15")
    await enable_features(session_factory, FeatureKey.CLIQ_ENABLED.value)
    async with session_factory() as session:
        await session.execute(
            update(PaymentSetting).where(PaymentSetting.country_code == CountryCode.JO).values(driver_debt_ceiling=Decimal("1.000"))
        )
        await session.commit()

    first = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-3001")
    await bring_online(client, first)
    rider_one = await rider_session(client)
    await _cash(client, rider_one, await completed_ride(client, rider_one["headers"], first), first)
    # **فوق السقف يُحجب** — ويُطفأ كي لا يُعرض عليه ما بعده
    await client.post("/drivers/me/offline", headers=first["headers"])

    second = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-3002")
    await set_cliq_alias(session_factory, second["driver_id"])
    await bring_online(client, second)
    rider_two = await rider_session(client, OTHER_RIDER)
    ride_two = await completed_ride(client, rider_two["headers"], second)
    cliq = await pay_ride(client, rider_two["headers"], ride_two["id"], "cliq", key=f"pay-{ride_two['id']}")
    assert cliq.status_code == 201, cliq.text
    disputed = await client.post(
        f"/payments/{cliq.json()['payments'][0]['id']}/dispute",
        json={"reason": "لم تصلني الحوالة"},
        headers=second["headers"],
    )
    assert disputed.status_code == 200, disputed.text
    rider_three = await rider_session(client, THIRD_RIDER)
    await _cash(client, rider_three, await completed_ride(client, rider_three["headers"], second), None)

    body = await summary(client, reader)
    for key in ("ride_payments_confirmed", "ride_payments_unconfirmed", "ride_payments_disputed"):
        assert amount(body, key) == Decimal("8.000"), key
        assert metric(body, key)["count"] == 1, key
    assert amount(body, "captain_debts") == Decimal("1.200")
    assert amount(body, "captain_debts_over_ceiling") == Decimal("1.200")
    assert metric(body, "captain_debts_over_ceiling")["users"] == 1
    assert metric(body, "captain_debts_over_ceiling")["warn"] is True
    assert amount(body, "commission_accrued_direct") == Decimal("1.200")
    # **له حسابُ كليك ولا رصيد** — فلا يُعدّ في «صرفٌ بكليك»
    assert amount(body, "captain_balances_cliq") == Decimal("0.000")
    assert metric(body, "captain_balances_cliq")["users"] == 0
    assert_reconciled(body)

    # **صاحبُ الصفّ بحسب النوع**: الكبتنُ الذي قبض افتراضاً، والراكبُ الذي دفع حين يُختار
    captains = await drill(client, reader, "ride_payments_confirmed", "users")
    assert [row["user_id"] for row in captains["rows"]] == [first["user_id"]]
    assert captains["rows"][0]["driver_id"] == str(first["driver_id"])
    riders = await drill(client, reader, "ride_payments_confirmed", "users", user_type="rider")
    assert [row["user_id"] for row in riders["rows"]] == [rider_one["user"]["id"]]
    debts = await drill(client, reader, "captain_debts_over_ceiling", "transactions")
    assert [(row["amount"], row["method"], row["status_label"]) for row in debts["rows"]] == [("1.200", "cash", "قائم")]

    by_cliq = await summary(client, reader, method="cliq")
    assert amount(by_cliq, "ride_payments_disputed") == Decimal("8.000")
    assert amount(by_cliq, "ride_payments_confirmed") == Decimal("0.000")
    assert metric(by_cliq, "commission_collected")["applicable"] is False
    by_status = await summary(client, reader, status="disputed")
    assert metric(by_status, "ride_payments_confirmed")["applicable"] is False
    assert amount(by_status, "ride_payments_disputed") == Decimal("8.000")
    assert metric(by_status, "captain_debts")["applicable"] is False


async def test_payable_now_and_not_due_follow_the_withdrawal_rule(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    """رصيدُ ٣٠ واحتجازُ ٥ وطلبُ سحبٍ بـ١٠ ⇒ **يُصرف الآن ٢٥ ولم يحِن ٥**؛ وكبتنٌ رصيدُه ٤ تحت الاحتجاز ⇒ **كلُّه لم يحِن**؛
    **وكبتنٌ رصيدُه ٦ فوق الاحتجاز ومحفظتُه مجمَّدة ⇒ كلُّه لم يحِن** — بابُ السحب يردّه (`require_not_frozen`)، فلا يُعدّ «يُصرف الآن»."""
    reader = await finance_reader(client, admin_headers)
    async with session_factory() as session:
        await session.execute(
            update(WalletSetting).where(WalletSetting.country_code == CountryCode.JO).values(withdrawal_reserve_amount=Decimal("5.000"))
        )
        await session.commit()
    first = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    await set_cliq_alias(session_factory, first["driver_id"])
    await _adjust(client, admin_headers, first["user_id"], "30.000", "driver")
    asked = await client.post(
        "/wallet/me/withdrawals", json={"amount": "10.000", "method": "cliq"}, headers=first["headers"]
    )
    assert asked.status_code == 201, asked.text
    second = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-4002", subscribed=False)
    await _adjust(client, admin_headers, second["user_id"], "4.000", "driver")
    frozen = await approved_driver(client, session_factory, THIRD_DRIVER, plate_number="AMM-4003", subscribed=False)
    await _adjust(client, admin_headers, frozen["user_id"], "6.000", "driver")
    await _freeze(client, admin_headers, frozen["user_id"], "driver")
    refused = await client.post(
        "/wallet/me/withdrawals", json={"amount": "1.000", "method": "bank"}, headers=frozen["headers"]
    )
    assert refused.status_code == 403 and refused.json()["code"] == "wallet_frozen", refused.text

    body = await summary(client, reader)
    assert amount(body, "captain_balances") == Decimal("40.000")
    assert amount(body, "captain_balances_cliq") == Decimal("30.000")
    assert amount(body, "captain_balances_other") == Decimal("10.000")
    assert amount(body, "captain_payable_now") == Decimal("25.000")
    assert metric(body, "captain_payable_now")["users"] == 1
    assert amount(body, "captain_not_due") == Decimal("15.000")
    assert metric(body, "captain_not_due")["users"] == 3
    # **والمطابقةُ تقرأ التجميدَ من SQL خامٍ مستقلّ** — فتخضرّ هنا لأن الاثنين قرآه، لا لأن القسمين يجمعان إلى الأصل
    assert_reconciled(body)

    rows = (await drill(client, reader, "captain_not_due", "users"))["rows"]
    assert [(row["user_id"], row["amount"]) for row in rows] == [
        (frozen["user_id"], "6.000"),
        (first["user_id"], "5.000"),
        (second["user_id"], "4.000"),
    ]
    lines = (await drill(client, reader, "captain_payable_now", "transactions"))["rows"]
    assert [(row["kind"], row["kind_label"], row["amount"]) for row in lines] == [("payable_now", "يُصرف الآن", "25.000")]


# ═════════════════════════════════════════════════════════════ الاشتراكاتُ وردودُ الكباتن


async def test_subscriptions_sold_by_plan_and_the_refund_of_a_cancelled_one(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    reader = await finance_reader(client, admin_headers)
    plan_id = await ensure_plan(session_factory)
    first = await approved_driver(client, session_factory, DRIVER)
    second = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-5002", subscribed=False)
    await _adjust(client, admin_headers, second["user_id"], "30.000", "driver")
    # **عرضُ ١٠٪ بعد أن اشترى الأوّلُ بسعر خطّته** — فالثاني يدفع ٢٧ ويتنازل TAXO عن ٣ (`discount_amount`)
    await enable_features(session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value)
    await make_offer(session_factory, percent="10")
    bought = await client.post(
        "/subscriptions", json={"plan_id": str(plan_id), "idempotency_key": uuid.uuid4().hex}, headers=second["headers"]
    )
    assert bought.status_code in (200, 201), bought.text

    rows = (await client.get("/admin/subscriptions", headers=admin_headers)).json()
    mine = next(row for row in rows if row["driver_id"] == str(first["driver_id"]))
    cancelled = await client.post(
        f"/admin/subscriptions/{mine['id']}/cancel", json={"reason": "إيقافٌ بطلبه"}, headers=admin_headers
    )
    assert cancelled.status_code == 200, cancelled.text
    refund = Decimal(cancelled.json()["total_refund"])
    assert refund > 0

    body = await summary(client, reader)
    # **المُلغى بيعٌ وقع** — يبقى في «المباعة»، وردُّه في «ردودٌ للكباتن»
    assert amount(body, "subscriptions_sold") == Decimal("57.000")
    assert metric(body, "subscriptions_sold")["count"] == 2
    assert [(line["label"], line["amount"], line["count"]) for line in metric(body, "subscriptions_sold")["breakdown"]] == [
        (SUBSCRIPTION_PLAN_NAME, "57.000", 2)
    ]
    # **وخصمُ العرض في «الخصومات»** — البيعُ بسعره (الأوّل) لا يُعدّ خصماً
    assert amount(body, "subscription_discounts") == Decimal("3.000")
    assert metric(body, "subscription_discounts")["count"] == 1
    discounted = (await drill(client, reader, "subscription_discounts", "users"))["rows"]
    assert [(row["user_id"], row["amount"]) for row in discounted] == [(second["user_id"], "3.000")]
    assert amount(body, "refunds_captains") == refund
    assert amount(body, "ledger.subscription_payment") == Decimal("-27.000")
    assert_reconciled(body)
    by_wallet = await summary(client, reader, method="wallet")
    assert (amount(by_wallet, "subscriptions_sold"), amount(by_wallet, "subscription_discounts")) == (
        Decimal("27.000"),
        Decimal("3.000"),
    )
    by_cash = await summary(client, reader, method="cash")
    assert (amount(by_cash, "subscriptions_sold"), amount(by_cash, "subscription_discounts")) == (
        Decimal("30.000"),
        Decimal("0.000"),
    )


# ═════════════════════════════════════════════════════════════ الردودُ والتصحيحات


async def test_refunds_reversals_and_adjustments_keep_their_sign(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    """رحلةُ محفظةٍ ورحلةُ بطاقةٍ تُردّان، وتصحيحاتٌ بالاتجاهين — **الردُّ للراكب موجب، وعكسُ أجر الكبتن سالب، والتصحيحُ بإشارته**."""
    reader = await finance_reader(client, admin_headers)
    await set_commission(session_factory, "10")
    await enable_card_provider(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")

    by_wallet = await completed_ride(client, rider["headers"], driver)
    wallet_payment = (await pay_ride(client, rider["headers"], by_wallet["id"], "wallet")).json()["payments"][0]
    by_card = await completed_ride(client, rider["headers"], driver)
    card = (await pay_ride(client, rider["headers"], by_card["id"], "card", key="pay-card-0001")).json()
    await simulate_card(client, rider["headers"], card["card_order"]["cart_id"])
    card_payment = (await payments_of(client, rider["headers"], by_card["id"]))["payments"][0]
    for payment in (wallet_payment, card_payment):
        refunded = await client.post(
            f"/admin/payments/{payment['id']}/refund", json={"reason": "شكوى الراكب"}, headers=admin_headers
        )
        assert refunded.status_code == 200, refunded.text

    await _adjust(client, admin_headers, rider["user"]["id"], "5.000", "rider")
    await _adjust(client, admin_headers, driver["user_id"], "3.000", "driver")
    await _adjust(client, admin_headers, driver["user_id"], "-1.000", "driver")

    body = await summary(client, reader)
    assert amount(body, "refunds_riders") == Decimal("8.000")
    assert amount(body, "refunds_card") == Decimal("8.000")
    assert metric(body, "refunds_card")["count"] == 1
    assert amount(body, "earning_reversals") == Decimal("-14.400")
    assert metric(body, "earning_reversals")["count"] == 2
    assert amount(body, "adjustments") == Decimal("7.000")
    assert [(line["key"], line["label"], line["amount"], line["count"]) for line in metric(body, "adjustments")["breakdown"]] == [
        ("credit", "إضافة", "8.000", 2),
        ("debit", "خصم", "-1.000", 1),
    ]
    # **قيدا `commission` باقيان في الدفتر** (المحصَّلة تطابق `ledger.commission`)، **لكن الردَّين أعادا للراكب ١٦ كاملةً واستعادا
    # من الكبتن ١٤٫٤٠٠ وحدَها** — فالعمولةُ رجعت كلُّها، **والصافي صفر**: ما بقي لـTAXO من هاتين الرحلتين لا شيء
    assert amount(body, "commission_collected") == Decimal("1.600")
    assert amount(body, "commission_refunded") == Decimal("-1.600")
    assert metric(body, "commission_refunded")["count"] == 2
    assert amount(body, "commission_net") == Decimal("0.000")
    assert [(line["key"], line["amount"], line["count"]) for line in metric(body, "commission_net")["breakdown"]] == [
        ("commission", "1.600", 2),
        ("commission_returned", "-1.600", 2),
    ]
    returned = (await drill(client, reader, "commission_refunded", "transactions"))["rows"]
    assert sorted((row["ref_id"], row["amount"], row["kind_label"], row["method"]) for row in returned) == sorted(
        [
            (wallet_payment["id"], "-0.800", "عمولةٌ رُدّت مع الاسترداد", "wallet"),
            (card_payment["id"], "-0.800", "عمولةٌ رُدّت مع الاسترداد", "card"),
        ]
    )
    assert amount(body, "ledger.adjustment") == Decimal("-7.400")
    assert amount(body, "rider_balances") == Decimal("25.000")
    assert amount(body, "captain_balances") == Decimal("2.000")
    assert_reconciled(body)

    # **الأكبرُ قيمةً أوّلاً بالقيمة المطلقة** — خصمُ ٧٫٢٠٠ قبل إضافة ٥
    lines = (await drill(client, reader, "ledger.adjustment", "transactions"))["rows"]
    assert [row["amount"] for row in lines] == ["-7.200", "-7.200", "5.000", "3.000", "-1.000"]
    # **والمستخدمون كذلك** — الكبتنُ بصافي −١٢٫٤٠٠ قبل الراكب بـ٥: الترتيبُ بالإشارة كان يضع الراكبَ أوّلاً
    users = (await drill(client, reader, "ledger.adjustment", "users"))["rows"]
    assert [(row["user_id"], row["role"], row["amount"]) for row in users] == [
        (driver["user_id"], "driver", "-12.400"),
        (rider["user"]["id"], "rider", "5.000"),
    ]


async def test_one_account_with_both_wallets_is_two_rows_not_one_captain(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    """**حاملُ الدورين له محفظتان** — تصحيحٌ في كلٍّ منهما ⇒ **سطران**: راكبٌ بمال محفظة الراكب يفتح ملفَّ الراكب، وكبتنٌ بمال
    محفظته يفتح ملفَّ الكبتن. **وكان سطراً واحداً اسمُه «كبتن» بالمالين معاً.**"""
    reader = await finance_reader(client, admin_headers)
    both = await _dual_driver(client, session_factory, DRIVER)
    await _adjust(client, admin_headers, both["user_id"], "5.000", "rider")
    await _adjust(client, admin_headers, both["user_id"], "3.000", "driver")

    body = await summary(client, reader)
    assert amount(body, "adjustments") == Decimal("8.000")
    assert metric(body, "adjustments")["users"] == 2
    assert amount(body, "rider_balances") == Decimal("5.000")
    assert amount(body, "captain_balances") == Decimal("3.000")
    assert_reconciled(body)

    rows = (await drill(client, reader, "adjustments", "users"))["rows"]
    assert [(row["user_id"], row["role"], row["role_label"], row["amount"], row["driver_id"]) for row in rows] == [
        (both["user_id"], "rider", "راكب", "5.000", None),
        (both["user_id"], "driver", "كبتن", "3.000", str(both["driver_id"])),
    ]


# ═════════════════════════════════════════════════════════════ الرسوم


QUEEN_ALIA = "SRID=4326;POLYGON((35.965 31.700, 36.010 31.700, 36.010 31.745, 35.965 31.745, 35.965 31.700))"
AIRPORT = {"lat": 31.7226, "lng": 35.9932}
NEAR_AIRPORT = {"lat": 31.7300, "lng": 35.9932}
CITY = {"lat": 31.9539, "lng": 35.9106}
RECIPIENT = {"recipient_name": "أبو سالم", "recipient_phone": "0792223333", "recipient_address": "جبل الحسين، بناية ٤"}


async def _service_settings(session_factory, **jordan) -> None:
    """صفُّ إعدادات الخدمات كما تبذره الترحيلات — والاختباراتُ تفرّغ الجداولَ قبل كلٍّ منها."""
    async with session_factory() as session:
        session.add_all([ServiceSetting(country_code="JO", **jordan), ServiceSetting(country_code="LY")])
        await session.commit()


async def test_airport_and_parcel_fees_inside_completed_fares(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None
) -> None:
    reader = await finance_reader(client, admin_headers)
    await _service_settings(session_factory, parcel_fee=Decimal("0.500"))
    async with session_factory() as session:
        session.add(Facility(country_code="JO", name="مطار الملكة علياء الدولي", area=QUEEN_ALIA, fee=Decimal("1.000")))
        await session.commit()
    await enable_features(session_factory, FeatureKey.AIRPORT_ENABLED.value, FeatureKey.PARCEL_ENABLED.value)

    driver = await approved_driver(client, session_factory, DRIVER)
    switched = await client.patch("/drivers/me", json={"accepts_airport": True}, headers=driver["headers"])
    assert switched.status_code == 200, switched.text
    await bring_online(client, driver, NEAR_AIRPORT)
    from_airport = await rider_session(client)
    await _drive(
        client, from_airport["headers"], driver, {"pickup": AIRPORT, "dropoff": CITY, "vehicle_category": "economy"}
    )

    await broadcast_location(client, driver, **NEAR_PICKUP)
    sender = await rider_session(client, OTHER_RIDER)
    await _drive(
        client,
        sender["headers"],
        driver,
        {
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "parcel": RECIPIENT | {"payer": "requester", "accepted_terms": True},
        },
    )

    body = await summary(client, reader)
    assert amount(body, "fee_airport") == Decimal("1.000")
    assert metric(body, "fee_airport")["count"] == 1
    assert amount(body, "fee_parcel") == Decimal("0.500")
    assert metric(body, "fee_parcel")["count"] == 1
    assert_reconciled(body)
    # **الرسمُ للكبتن** — صاحبُ الصفّ افتراضاً، والراكبُ حين يُختار
    assert [row["user_id"] for row in (await drill(client, reader, "fee_airport", "users"))["rows"]] == [driver["user_id"]]
    riders = await drill(client, reader, "fee_parcel", "users", user_type="rider")
    assert [row["user_id"] for row in riders["rows"]] == [sender["user"]["id"]]


async def test_guarantee_and_cancellation_fees(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    """حجزٌ مضمونٌ تمّ في وقته ⇒ **رسمُه للكبتن**؛ وإلغاءان بعد تحرّك الكبتن — **واحدٌ سُدِّد من المحفظة وآخرُ معلَّق**."""
    reader = await finance_reader(client, admin_headers)
    await _service_settings(session_factory, guarantee_fee=Decimal("1.000"))
    await enable_features(
        session_factory, FeatureKey.GUARANTEED_BOOKING_ENABLED.value, FeatureKey.SCHEDULED_RIDES_ENABLED.value
    )
    async with session_factory() as session:
        session.add(CancellationSetting(country_code=CountryCode.JO, exempt_within_meters=300))
        await session.commit()
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)

    booker = await rider_session(client)
    await topup_wallet(client, admin_headers, booker["user"]["id"], "20.000")
    booked = await client.post(
        "/me/bookings",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "scheduled_at": (datetime.now(UTC) + timedelta(hours=3)).isoformat(),
            "guaranteed": True,
        },
        headers=booker["headers"],
    )
    assert booked.status_code == 201, booked.text
    booking_id = booked.json()["id"]
    assert (await client.post(f"/drivers/me/guarantees/{booking_id}/accept", headers=driver["headers"])).status_code == 200
    async with session_factory() as session:
        row = await session.get(RideBooking, uuid.UUID(booking_id))
        row.scheduled_at = datetime.now(UTC) + timedelta(minutes=50)
        await session.commit()
    confirmed = await client.post(f"/drivers/me/guarantees/{booking_id}/confirm", headers=driver["headers"])
    assert confirmed.status_code == 200, confirmed.text
    for step in ("arrive", "start", "complete"):
        assert (await client.post(f"/rides/{confirmed.json()['id']}/{step}", headers=driver["headers"])).status_code == 200

    cancelled_by: dict[str, dict] = {}
    for payload, balance in ((OTHER_RIDER, "20.000"), (THIRD_RIDER, None), (FOURTH_RIDER, None), (FIFTH_RIDER, None)):
        rider = await rider_session(client, payload)
        cancelled_by[payload["phone"]] = rider
        if balance:
            await topup_wallet(client, admin_headers, rider["user"]["id"], balance)
        await broadcast_location(client, driver, **NEAR_PICKUP)
        ride = await accepted_ride(client, rider["headers"], driver)
        await broadcast_location(client, driver, **FAR_AWAY)
        cancelled = await client.post(f"/rides/{ride['id']}/cancel", json={"reason": "غيّرت رأيي"}, headers=rider["headers"])
        assert cancelled.status_code == 200, cancelled.text

    # **رسمان معلَّقان تُنهيهما الإدارةُ بلا مال**: إعفاءٌ وشطب — بابا اللوحة نفسُهما
    for payload, verb in ((FOURTH_RIDER, "waive"), (FIFTH_RIDER, "write-off")):
        listed = await client.get(
            "/admin/cancellation-charges",
            params={"user_id": cancelled_by[payload["phone"]]["user"]["id"], "status": "pending"},
            headers=admin_headers,
        )
        assert listed.status_code == 200, listed.text
        (charge,) = listed.json()
        done = await client.post(
            f"/admin/cancellation-charges/{charge['id']}/{verb}", json={"reason": "قرارُ الإدارة"}, headers=admin_headers
        )
        assert done.status_code == 200, done.text

    body = await summary(client, reader)
    assert amount(body, "fee_guarantee") == Decimal("1.000")
    assert amount(body, "ledger.guarantee_hold") == Decimal("-1.000")
    # **«الإلغاء» ما وصل وما يُطلب وحدَهما** — المُعفى والمشطوبُ لم يُحصَّلا، فجمعُهما هنا كان يجعل الرقمَ ٣٫٠٠٠ بأربعة رسوم
    assert amount(body, "fee_cancellation") == Decimal("1.500")
    assert metric(body, "fee_cancellation")["count"] == 2
    assert sorted(
        (line["key"], line["label"], line["amount"]) for line in metric(body, "fee_cancellation")["breakdown"]
    ) == [("pending", "لم يُحصَّل", "0.750"), ("settled", "وصل الكبتن", "0.750")]
    assert amount(body, "fee_cancellation_forgiven") == Decimal("1.500")
    assert metric(body, "fee_cancellation_forgiven")["count"] == 2
    assert sorted(
        (line["key"], line["label"], line["amount"]) for line in metric(body, "fee_cancellation_forgiven")["breakdown"]
    ) == [("waived", "أُعفي", "0.750"), ("written_off", "شُطب", "0.750")]
    assert amount(body, "ledger.cancellation_fee") == Decimal("-0.750")
    assert amount(body, "ledger.cancellation_compensation") == Decimal("0.750")
    assert_reconciled(body)
    by_confirmed = await summary(client, reader, status="confirmed")
    assert amount(by_confirmed, "fee_cancellation") == Decimal("0.750")
    assert metric(by_confirmed, "fee_cancellation_forgiven")["applicable"] is False
    assert amount(await summary(client, reader, status="unconfirmed"), "fee_cancellation") == Decimal("0.750")


# ═════════════════════════════════════════════════════════════ الخصوماتُ والمكافآت


async def test_coupons_and_the_weekly_cashback(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None
) -> None:
    reader = await finance_reader(client, admin_headers)
    await _service_settings(session_factory, cashback_amount=Decimal("2.000"))
    await enable_features(session_factory, FeatureKey.PROMO_CODES_ENABLED.value, FeatureKey.WEEKLY_CASHBACK_ENABLED.value)
    async with session_factory() as session:
        session.add(
            PromoCode(
                code="WELCOME",
                country_code=CountryCode.JO,
                discount_type=PromoDiscountType.FIXED,
                discount_value=Decimal("1.000"),
                budget_total=Decimal("100.000"),
            )
        )
        await session.commit()
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await _drive(
        client,
        rider["headers"],
        driver,
        {"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", "promo_code": "WELCOME"},
    )

    # **سلسلةُ ستّة أيامٍ بلا جمعة** — بابُ اليوم نفسُه الذي يناديه الإنهاء (`cashback.record_day`). **وبراكبٍ ثانٍ**: رحلةُ الكوبون
    # بدأت لراكبها سلسلةً باليوم، وأيامٌ قبلها لا تُلحق بها
    streaker = await rider_session(client, OTHER_RIDER)
    saturday = date(2026, 10, 3)
    for offset in range(6):
        async with session_factory() as session:
            row = await cashback.settings_for(session, CountryCode.JO)
            owner = await session.get(User, uuid.UUID(streaker["user"]["id"]))
            await cashback.record_day(session, rider=owner, day=saturday + timedelta(days=offset), row=row)
            await session.commit()

    body = await summary(client, reader)
    assert amount(body, "coupons") == Decimal("1.000")
    assert metric(body, "coupons")["count"] == 1
    assert [row["user_id"] for row in (await drill(client, reader, "coupons", "users"))["rows"]] == [rider["user"]["id"]]
    assert amount(body, "cashback") == Decimal("2.000")
    assert amount(body, "ledger.cashback") == Decimal("2.000")
    assert_reconciled(body)


async def test_the_referral_bonus_is_counted_for_its_referrer(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    reader = await finance_reader(client, admin_headers)
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(client, admin_headers, amount="4.000", rides=0)
    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]
    referred = await approved_driver(
        client, session_factory, SECOND_DRIVER | {"referral_code": code}, plate_number="AMM-9002"
    )
    await _stamp_female(session_factory, referred["driver_id"])
    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 1
        await session.commit()

    body = await summary(client, reader)
    assert amount(body, "referral_bonuses") == Decimal("4.000")
    assert [row["user_id"] for row in (await drill(client, reader, "referral_bonuses", "users"))["rows"]] == [
        referrer["user"]["id"]
    ]
    assert_reconciled(body)
