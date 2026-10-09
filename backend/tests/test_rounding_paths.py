"""لا كسورَ في المال (SPEC §٧٠) — **الجزءُ الثاني: كلُّ مسارِ مالٍ غيرِ الرحلة** (§٧٠-ج/٥ و/٦ و/٧).

ما يحرسه هذا الملفّ، **وكلُّه من الأبواب الحقيقيّة** (لا صفَّ مالٍ يُكتب بيد — `test_no_shortcut_fixtures`):

- **ما يُحسب يُقرَّب مرّةً ويُكتب فرقُه في السجلّ** (`money_roundings`): رسمُ الإلغاء · رسمُ الضمان وغرامتُه (للأدنى) · ثمنُ
  الاشتراك بعد العرض في القنوات الأربع واستردادُه النسبيّ (للأعلى) · سعرُ المشوار الثابت وحافزُ كبتنه · الاستردادُ الأسبوعيّ ·
  مكافأةُ الإحالة · حجزُ بين المدن · مركبةُ المتجر · سدادُ السلفة الكامل.
- **ما يختاره الشخصُ مضاعفٌ للوحدة وإلا رُدّ بـ`amount_not_multiple`**: الشحنُ (يدويّاً وبطاقةً وCliQ — **قبل فتح الطلب**) ·
  السحبُ (والمتاحُ مضاعفٌ — **المثال (ج)**) · التحويلُ · البقشيشُ (وأزرارُه مقرَّبة) · السلفةُ (وسقفُها مضاعف) · سدادُ الدَّين.
- **«ادفع الدَّين كلَّه» للأعلى والزائدُ يعود إلى المحفظة قيداً صريحاً** (`rounding`) — وسدادُ السلفة الكامل بالقاعدة نفسِها.
- **ما لا يُقرَّب**: تصحيحُ المشرف (فلسٌ بفلس) · وما وصل فعلاً كما قرأه المشرف · **وما يُردّ يُردّ كما أُخذ**.
- **ولا رصيدَ قائمٌ يتغيّر**: حجزٌ قبل الإشعال يُردّ بكسوره، وبصمةُ المال قبل الإشعال وبعده واحدة.

وحدةُ التقريب في كلِّ اختبارٍ `0.500` و«الأقرب» (نصفُه للأعلى) إلا ما يُقال خلافُه.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.booking import RideBooking
from app.models.cancellation import RideCancellationCharge
from app.models.driver_warning import DriverWarning
from app.models.enums import FeatureKey, WalletTransactionType
from app.models.provider_order import ProviderOrder
from app.models.debt import DriverDebt
from app.models.enums import DriverDebtSource
from app.models.referral import REFERRAL_TYPE_DRIVER
from app.models.ride import Ride
from app.models.rider_subscription import RiderSubscription
from app.models.rounding import MoneyRounding
from app.models.service_setting import ServiceSetting
from app.models.subscription import DriverSubscription
from app.models.vehicle import Vehicle
from app.models.vehicle_skin import DriverVehicleSkin
from app.models.wallet import WalletTransaction
from app.services import advances as advances_service
from app.services import bookings, commute
from app.services import referrals as referrals_service
from scripts import money_fingerprint
from tests import test_advances as advances_tests
from tests import test_cancellation_fee as cancellation_tests
from tests import test_guaranteed_booking as guaranteed_tests
from tests import test_referrals as referral_tests
from tests import test_rider_subscription as commute_tests
from tests import test_subscription_cancellation as cancellation_of_subscriptions
from tests import test_subscription_offers as offer_tests
from tests import test_vehicle_skins as skin_tests
from tests import test_weekly_cashback as cashback_tests
from tests.helpers import (
    DRIVER,
    NEAR_PICKUP,
    OTHER_RIDER,
    PICKUP,
    SECOND_DRIVER,
    accepted_ride,
    approved_driver,
    auth,
    bring_online,
    broadcast_location,
    completed_ride,
    enable_card_provider,
    enable_cliq_provider,
    enable_features,
    ensure_plan,
    pay_ride,
    payments_of,
    register,
    rider_session,
    set_commission,
    simulate_card,
    topup_wallet,
    wallet_of,
)
from tests.test_payments import _only, _online_driver, _rider

pytestmark = pytest.mark.asyncio

OFFERS = FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value


# ------------------------------------------------------------------ أدوات


async def _enable_rounding(
    client: AsyncClient, admin_headers: dict, *, unit: str = "0.500", mode: str = "nearest", **extra: str
) -> None:
    """**الإشعالُ من بابه** — `PATCH` اللوحة كما يضغطه المالك، لا كتابةٌ في الصفّ."""
    response = await client.patch(
        "/admin/settings/payments/JO",
        json={"rounding_enabled": True, "rounding_unit": unit, "rounding_mode": mode, **extra},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


async def _journal(session_factory, kind: str) -> list[MoneyRounding]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(MoneyRounding)
                .where(MoneyRounding.source_kind == kind)
                .order_by(MoneyRounding.created_at)
            )
        )


async def _all_journal(session_factory) -> list[MoneyRounding]:
    async with session_factory() as session:
        return list(await session.scalars(select(MoneyRounding).order_by(MoneyRounding.created_at)))


async def _journal_count(session_factory) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(MoneyRounding)) or 0)


async def _entries(session_factory, user_id, kind: WalletTransactionType) -> list[WalletTransaction]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(WalletTransaction)
                .where(
                    WalletTransaction.owner_id == uuid.UUID(str(user_id)),
                    WalletTransaction.type == kind,
                )
                .order_by(WalletTransaction.created_at)
            )
        )


async def _adjust(client: AsyncClient, admin_headers: dict, user_id, amount: str, *, wallet: str) -> None:
    """**تصحيحُ المشرف لا يُقرَّب** (§٧٠-ج/٧) — يُصحَّح الفلسُ بفلسه، فيُقبل `37.842` والتقريبُ مشتعل."""
    response = await client.post(
        f"/admin/wallets/{user_id}/adjustments",
        json={"amount": amount, "reason": "تصحيحُ اختبارٍ بكسوره", "wallet": wallet},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["amount"] == amount, "التصحيحُ قُرِّب — وهو يصحّح الفلسَ بفلسه"


def _refused_as_not_multiple(response, *, lower: str, upper: str) -> None:
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "amount_not_multiple", body
    assert (body["unit"], body["lower"], body["upper"]) == ("0.500", lower, upper), body
    assert lower in body["message"] and upper in body["message"], "الجملةُ لا تقول المضاعفين"


# ------------------------------------------------------------------ رسمُ الإلغاء


async def test_the_cancellation_fee_is_rounded_once_and_journalled_and_an_exempt_one_is_not(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**رسمُ الإلغاء `0.750 ⇐ 1.000`** — المجمَّدُ على الرحلة والمحصَّلُ والقيدان كلُّها المقرَّب، **وصفٌّ في السجلّ**. **والمعفى
    بالقرب لا صفَّ له**: يُقرَّب بعد الإعفاء، والسجلُّ لا يُمحى منه تقريبُ رسمٍ لم يُحصَّل."""
    await cancellation_tests._policy(session_factory, exempt_within_meters=300)
    await _enable_rounding(client, admin_headers)
    driver = await _online_driver(client, session_factory)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")

    ride = await accepted_ride(client, rider["headers"], driver)
    await broadcast_location(client, driver, **cancellation_tests.FAR_AWAY)
    cancelled = await client.post(f"/rides/{ride['id']}/cancel", json={"reason": "غيّرت رأيي"}, headers=rider["headers"])
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancellation_fee"] == "1.000"

    async with session_factory() as session:
        charge = await session.scalar(
            select(RideCancellationCharge).where(RideCancellationCharge.ride_id == uuid.UUID(ride["id"]))
        )
    assert charge is not None and charge.amount == Decimal("1.000")
    [paid] = await _entries(session_factory, rider["user"]["id"], WalletTransactionType.CANCELLATION_FEE)
    [earned] = await _entries(session_factory, driver["user_id"], WalletTransactionType.CANCELLATION_COMPENSATION)
    assert (paid.amount, earned.amount) == (Decimal("-1.000"), Decimal("1.000"))

    [row] = await _journal(session_factory, "cancellation_fee")
    assert (row.source_id, row.user_id) == (uuid.UUID(ride["id"]), uuid.UUID(rider["user"]["id"]))
    assert (row.precise, row.rounded, row.difference) == (Decimal("0.750"), Decimal("1.000"), Decimal("0.250"))

    # **والثاني معفى** — الكبتنُ لم يبرح مكانَه، فلا رسمَ ولا صفَّ. **ويعود قربَ الالتقاء قبل الطلب**: من بعيدٍ لا يصله عرض
    await broadcast_location(client, driver, **NEAR_PICKUP)
    second = await accepted_ride(client, rider["headers"], driver)
    await broadcast_location(client, driver, **PICKUP)
    exempt = await client.post(f"/rides/{second['id']}/cancel", json={"reason": "غيّرت رأيي"}, headers=rider["headers"])
    assert exempt.status_code == 200, exempt.text
    assert Decimal(exempt.json()["cancellation_fee"] or "0") == 0
    assert len(await _journal(session_factory, "cancellation_fee")) == 1


# ------------------------------------------------------------------ الحجزُ المضمون


async def _guarantee_fee(session_factory, fee: str) -> None:
    async with session_factory() as session:
        session.add_all(
            [ServiceSetting(country_code="JO", guarantee_fee=Decimal(fee)), ServiceSetting(country_code="LY")]
        )
        await session.commit()


async def test_the_guarantee_fee_is_rounded_at_hold_and_the_penalty_rounds_down_within_the_balance(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الحجز**: `1.250 ⇐ 1.500` يُحفظ من المحفظة مقرَّباً ويُجمَّد. **والغرامةُ للأدنى دائماً**: رصيدُ الكبتن `0.900` يحدّها
    فتصير كسراً، **فأكبرُ مضاعفٍ لا يتجاوز رصيدَه** `0.500` — والكسرُ `0.400` يبقى له، والباقي `1.000` مكتوبٌ نقصاً كما كان.
    **والكسرُ في موضعٍ واحد** (مراجعةُ المال البند ٩): داخلَ `penalty_shortfall` (= الرسم − المنقول) **ولا صفَّ له في السجلّ** —
    صفٌّ هناك كان يحمل الكسرَ نفسَه ثانيةً، فمن يجمع ما لم يُحصَّل من الموضعين يعدّه مرّتين."""
    await _guarantee_fee(session_factory, "1.250")
    await _enable_rounding(client, admin_headers)
    rider, driver = await guaranteed_tests._setup(client, admin_headers, session_factory)

    booked = await guaranteed_tests._book(client, rider)
    assert booked.status_code == 201, booked.text
    booking = booked.json()
    assert booking["guarantee_fee"] == "1.500"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "18.500"
    [hold] = await _journal(session_factory, "guarantee_hold")
    assert (hold.source_id, hold.precise, hold.rounded, hold.difference) == (
        uuid.UUID(booking["id"]),
        Decimal("1.250"),
        Decimal("1.500"),
        Decimal("0.250"),
    )

    await _adjust(client, admin_headers, driver["user_id"], "0.900", wallet="driver")
    accepted = await client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=driver["headers"])
    assert accepted.status_code == 200, accepted.text
    await guaranteed_tests._move_to(session_factory, booking["id"], minutes_from_now=50)
    ride = (await client.post(f"/drivers/me/guarantees/{booking['id']}/confirm", headers=driver["headers"])).json()
    gone = await client.post(f"/rides/{ride['id']}/cancel", json={"reason": "طرأ أمر"}, headers=driver["headers"])
    assert gone.status_code == 200, gone.text

    async with session_factory() as session:
        warning = await session.scalar(select(DriverWarning))
    assert (warning.penalty_amount, warning.penalty_shortfall) == (Decimal("0.500"), Decimal("1.000"))
    [penalty] = await _entries(session_factory, driver["user_id"], WalletTransactionType.GUARANTEE_PENALTY)
    assert penalty.amount == Decimal("-0.500") and penalty.balance_after == Decimal("0.400"), "أخذت أكثرَ من مضاعفٍ في رصيده"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "19.000"

    # **ولا صفَّ للغرامة في السجلّ** — الكسرُ `0.400` داخلَ النقص `1.000` أعلاه، والسجلُّ لا يحمل إلا تقريبَ الحجز
    assert await _journal(session_factory, "guarantee_penalty") == [], "الكسرُ مكتوبٌ في موضعين"
    assert all(row.source_id != warning.id for row in await _all_journal(session_factory))


async def test_a_hold_taken_before_ignition_is_refunded_exactly_and_ignition_changes_no_existing_money(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**شرطُ المالك**: «No existing balance or ledger entry changes». حجزٌ بـ`1.250` قبل الإشعال، ثمّ الإشعالُ — **بصمةُ المال
    لا تتغيّر** — **ثمّ يُردّ الحجزُ كما أُخذ** `1.250` بلا تقريبٍ ولا صفّ: ما يُردّ عكسُ ما أُخذ، وتقريبُه يغيّر مالاً قائماً."""
    monkeypatch.setattr(money_fingerprint, "SessionLocal", session_factory)
    await _guarantee_fee(session_factory, "1.250")
    rider, _driver = await guaranteed_tests._setup(client, admin_headers, session_factory)
    booking = (await guaranteed_tests._book(client, rider)).json()
    assert booking["guarantee_fee"] == "1.250", "مطفأً يُحفظ الرسمُ بدقّته كما كان"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "18.750"

    before = await money_fingerprint.fingerprint()
    await _enable_rounding(client, admin_headers)
    assert money_fingerprint.compare(before, await money_fingerprint.fingerprint()) == ([], [])

    cancelled = await client.delete(f"/me/bookings/{booking['id']}", headers=rider["headers"])
    assert cancelled.status_code == 200, cancelled.text
    [refund] = await _entries(session_factory, rider["user"]["id"], WalletTransactionType.GUARANTEE_REFUND)
    assert refund.amount == Decimal("1.250")
    assert (await wallet_of(client, rider["headers"]))["balance"] == "20.000"
    assert await _journal_count(session_factory) == 0


# ------------------------------------------------------------------ اشتراكُ الكبتن


async def _priced_plan(session_factory) -> uuid.UUID:
    """خطةٌ بـ`7.000` وعرضٌ ١٥٪ (`1.050`) ⇐ الدقيق `5.950` ⇐ **`6.000`** — العرضُ أوّلاً ثمّ التقريبُ مرّةً."""
    await enable_features(session_factory, OFFERS)
    plan_id = await ensure_plan(session_factory, name="خطةُ التقريب", price="7.000")
    await offer_tests.make_offer(session_factory, percent="15", plan_id=plan_id, name="عرضُ التقريب")
    return plan_id


async def _subscription_rows(session_factory, driver_id) -> list[DriverSubscription]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(DriverSubscription)
                .where(DriverSubscription.driver_id == driver_id)
                .order_by(DriverSubscription.created_at)
            )
        )


async def test_the_wallet_channel_pays_the_rounded_price_and_the_screen_shows_it(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**المحفظة**: ما تَعِد به شاشةُ الخطط (`6.000`) هو ما يُخصم، **والصفُّ يحمل خصمَ العرض كما قرّره** (`1.050`) والمدفوعَ
    المقرَّب — **والفرقُ `+0.050` صفٌّ في السجلّ بمعرّف الاشتراك**، فلا يُقرأ في تقرير العروض «تسويةً يدوية»."""
    plan_id = await _priced_plan(session_factory)
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "10.000")

    plans = (await client.get("/subscriptions/plans", headers=driver["headers"])).json()
    shown = next(row for row in plans if row["id"] == str(plan_id))
    assert (shown["offer_discount"], shown["price_after_discount"]) == ("1.050", "6.000")

    bought = await offer_tests.buy(client, driver, plan_id)
    assert bought.status_code == 201, bought.text
    assert bought.json()["amount_paid"] == "6.000"
    assert (await wallet_of(client, driver["headers"]))["balance"] == "4.000"

    [row] = await _subscription_rows(session_factory, driver["driver_id"])
    assert (row.amount_paid, row.offer_discount_amount, row.discount_amount) == (
        Decimal("6.000"),
        Decimal("1.050"),
        Decimal("1.000"),
    )
    [journal] = await _journal(session_factory, "subscription")
    assert (journal.source_id, journal.precise, journal.rounded, journal.difference) == (
        row.id,
        Decimal("5.950"),
        Decimal("6.000"),
        Decimal("0.050"),
    )

    offers = await client.get("/admin/subscription-offers", params={"country_code": "JO"}, headers=admin_headers)
    assert offers.status_code == 200, offers.text
    [offer] = [item for item in offers.json() if item["name"] == "عرضُ التقريب"]
    assert offer["manual_adjustments"] == 0, "فرقُ التقريب قُرئ تسويةً يدوية"


async def test_the_panel_records_the_rounded_price_and_refuses_a_fraction_typed_by_hand(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**كاشُ اللوحة وكليكُها**: المقترَحُ هو الثمنُ مقرَّباً وفرقُه في السجلّ؛ **وما يكتبه المشرفُ بيده مضاعفٌ وإلا رُدّ** —
    **ومضاعفٌ يخالف الثمنَ تسويةٌ لا تقريب**: يُقبل ولا صفَّ له."""
    plan_id = await _priced_plan(session_factory)
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory, subscribed=False)

    def body(**extra) -> dict:
        return {"driver_id": str(driver["driver_id"]), "plan_id": str(plan_id), "method": "cash", **extra}

    typed = await client.post("/admin/subscriptions", json=body(amount_paid="5.950"), headers=admin_headers)
    _refused_as_not_multiple(typed, lower="5.500", upper="6.000")
    assert typed.json()["field"] == "amount_paid"

    suggested = await client.post("/admin/subscriptions", json=body(), headers=admin_headers)
    assert suggested.status_code == 201, suggested.text
    assert suggested.json()["amount_paid"] == "6.000"
    [journal] = await _journal(session_factory, "subscription")
    assert (journal.source_id, journal.difference) == (uuid.UUID(suggested.json()["id"]), Decimal("0.050"))

    settled = await client.post("/admin/subscriptions", json=body(amount_paid="5.500"), headers=admin_headers)
    assert settled.status_code == 201, settled.text
    assert settled.json()["amount_paid"] == "5.500"
    assert len(await _journal(session_factory, "subscription")) == 1, "تسويةُ المشرف كُتبت تقريباً"


async def test_the_card_channel_opens_the_order_at_the_rounded_price(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**البطاقة**: الطلبُ يُفتح بـ`6.000` **قبل المزوّد** (ما يعود منه يُقارَن بالطلب حرفاً)، والصفُّ يولد بعد الدفع وفرقُه معه."""
    plan_id = await _priced_plan(session_factory)
    await enable_card_provider(session_factory)
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory, subscribed=False)

    opened = await client.post("/subscriptions/card", json={"plan_id": str(plan_id)}, headers=driver["headers"])
    assert opened.status_code == 201, opened.text
    assert opened.json()["amount"] == "6.000"
    paid = await simulate_card(client, driver["headers"], opened.json()["cart_id"])
    assert paid.status_code == 200 and paid.json()["status"] == "paid", paid.text

    [row] = await _subscription_rows(session_factory, driver["driver_id"])
    assert row.amount_paid == Decimal("6.000")
    [journal] = await _journal(session_factory, "subscription")
    assert (journal.source_id, journal.precise, journal.rounded) == (row.id, Decimal("5.950"), Decimal("6.000"))


async def test_a_card_order_records_its_rounding_from_the_price_frozen_when_it_was_opened(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**مراجعةُ المال البند ٦**: الطلبُ فُتح بـ`6.000` (الدقيقُ `5.950`) **ثمّ أُطفئ التقريبُ قبل أن يدفع المزوّد** — والكبتنُ دفع
    `6.000` فعلاً: **الفرقُ `+0.050` يُكتب من الثمن المجمَّد على الطلب** لا من إعداد لحظة الدفع (كان يُعاد حسابُه مطفأً `5.950`
    فلا يطابق المدفوع، فلا صفّ — ويُقرأ الفرقُ «تسويةً يدويّة»)."""
    plan_id = await _priced_plan(session_factory)
    await enable_card_provider(session_factory)
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory, subscribed=False)

    opened = await client.post("/subscriptions/card", json={"plan_id": str(plan_id)}, headers=driver["headers"])
    assert opened.status_code == 201, opened.text
    assert opened.json()["amount"] == "6.000"
    off = await client.patch("/admin/settings/payments/JO", json={"rounding_enabled": False}, headers=admin_headers)
    assert off.status_code == 200, off.text

    paid = await simulate_card(client, driver["headers"], opened.json()["cart_id"])
    assert paid.status_code == 200 and paid.json()["status"] == "paid", paid.text
    [row] = await _subscription_rows(session_factory, driver["driver_id"])
    assert row.amount_paid == Decimal("6.000")
    [journal] = await _journal(session_factory, "subscription")
    assert (journal.source_id, journal.precise, journal.rounded, journal.unit, journal.mode) == (
        row.id,
        Decimal("5.950"),
        Decimal("6.000"),
        Decimal("0.500"),
        "nearest",
    ), "التفعيلُ قرأ إعدادَ لحظة الدفع لا الثمنَ المجمَّد"


async def test_a_plan_without_an_offer_shows_its_rounded_price_unstruck(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**مراجعةُ المال البند ٧**: خطةٌ بـ`9.800` بلا عرض ⇐ يُخصم `10.000` — **فيُنشر في `price_to_pay`**، و`price_after_discount`
    يبقى `null`: الشاشاتُ تشطب السعرَ حين يُملأ وحدَه، **فلا يُرسم `9.800` مشطوباً بجانب `10.000` الأعلى منه**. ومع عرضٍ يُملآن معاً."""
    plain = await ensure_plan(session_factory, name="خطةٌ بلا عرض", price="9.800")
    with_offer = await _priced_plan(session_factory)
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory, subscribed=False)

    plans = {row["id"]: row for row in (await client.get("/subscriptions/plans", headers=driver["headers"])).json()}
    shown = plans[str(plain)]
    assert (shown["price"], shown["price_after_discount"], shown["price_to_pay"]) == ("9.800", None, "10.000"), shown
    offered = plans[str(with_offer)]
    assert (offered["price"], offered["price_after_discount"], offered["price_to_pay"]) == ("7.000", "6.000", "6.000")


async def test_the_manual_cliq_channel_claims_the_rounded_price(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**كليك اليدويّ**: المطالبةُ بـ`6.000`، وتأكيدُ المشرف بما وصل يفعّل — والفرقُ صفٌّ واحد."""
    plan_id = await _priced_plan(session_factory)
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory, subscribed=False)

    claim = await client.post("/subscriptions/cliq", json={"plan_id": str(plan_id)}, headers=driver["headers"])
    assert claim.status_code in (200, 201), claim.text
    assert claim.json()["amount"] == "6.000"
    confirmed = await client.post(
        f"/admin/cliq-claims/{claim.json()['id']}/confirm", json={"amount": "6.000"}, headers=admin_headers
    )
    assert confirmed.status_code == 200, confirmed.text

    [row] = await _subscription_rows(session_factory, driver["driver_id"])
    assert row.amount_paid == Decimal("6.000")
    [journal] = await _journal(session_factory, "subscription")
    assert journal.source_id == row.id and journal.difference == Decimal("0.050")


async def test_the_pro_rata_refund_rounds_up_in_the_captains_favour_and_is_journalled(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الاستردادُ النسبيّ للأعلى** — شرطُ المالك القائم «الكسورُ لصالح الكبتن»، بوحدة السوق: نحو `26.299` ⇐ **`26.500`**.
    **والمعاينةُ والتنفيذُ رقمٌ واحد**، والقيدُ المقرَّب، **وصفٌّ في السجلّ باتجاه «للأعلى»**."""
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    await cancellation_of_subscriptions._subscription(
        session_factory,
        driver["driver_id"],
        # **مضى ١٢٫٣٤٪ من الشهر** ⇐ بقي نحو `26.299` من `30.000` — كسرٌ لا يقع على الوحدة
        starts_at=datetime.now(UTC) - timedelta(days=30) * 0.1234,
        amount_paid="30.000",
    )
    row_id = (await client.get("/admin/subscriptions", headers=admin_headers)).json()[0]["id"]
    preview = await client.get(f"/admin/subscriptions/{row_id}/cancellation-preview", headers=admin_headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()["total_refund"] == "26.500"
    assert preview.json()["lines"][0]["refund"] == "26.500"

    done = await client.post(
        f"/admin/subscriptions/{row_id}/cancel", json={"reason": "إيقافٌ بطلب الكبتن"}, headers=admin_headers
    )
    assert done.status_code == 200, done.text
    assert done.json()["total_refund"] == "26.500"
    [refund] = await _entries(session_factory, driver["user_id"], WalletTransactionType.REFUND)
    assert refund.amount == Decimal("26.500")

    [journal] = await _journal(session_factory, "subscription_refund")
    assert journal.source_id == uuid.UUID(row_id) and journal.rounded == Decimal("26.500") and journal.mode == "up"
    assert Decimal("26.290") < journal.precise < Decimal("26.310"), journal.precise
    assert journal.difference == journal.rounded - journal.precise


# ------------------------------------------------------------------ المشوارُ الثابت


async def test_the_commute_price_is_rounded_once_per_ride_and_the_captain_incentive_too(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**سعرُ الرحلة بعد الخصم يُقرَّب مرّةً**: `8.000 × 0.9 = 7.200 ⇐ 7.000` — فالشهرُ مضاعفٌ بالبناء وفرقُه **صفٌّ واحدٌ للشهر
    كلِّه**. **والرحلةُ تُدفع بسعرها المقرَّب** فلا تُقرَّب عند الإنهاء، **وحافزُ الكبتن `0.300 ⇐ 0.500`** صفٌّ بمعرّف الرحلة.
    **وما لم يُستعمل يعود بالسعر المقرَّب حرفاً** — بلا تقريبٍ ثانٍ. **والعمولةُ على السعر المسعَّر `7.200` لا على المقرَّب `7.000`**
    (مراجعةُ المال البند ٥): `0.720` بعمولة ١٠٪ — والفرقُ للكبتن أو عليه ولا تمسّه العمولة."""
    async with session_factory() as session:
        session.add_all(
            [
                ServiceSetting(
                    country_code="JO",
                    commute_discount_percent=Decimal("10.00"),
                    commute_captain_incentive=Decimal("0.300"),
                ),
                ServiceSetting(country_code="LY"),
            ]
        )
        await session.commit()
    await set_commission(session_factory, "10")
    await _enable_rounding(client, admin_headers)
    await enable_features(session_factory, commute_tests.FLAG, commute_tests.BOOKINGS)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "600.000")

    plan = await commute_tests._plan(session_factory)
    quote = (await client.post("/me/commutes/quote", json=plan, headers=rider["headers"])).json()
    assert quote["price_per_ride"] == "7.000"
    rides = quote["rides_total"]
    assert Decimal(quote["total"]) == Decimal("7.000") * rides

    bought = await client.post("/me/commutes", json=plan, headers=rider["headers"])
    assert bought.status_code == 201, bought.text
    sub = bought.json()
    [price] = await _journal(session_factory, "commute_price")
    assert (price.source_id, price.precise, price.rounded, price.difference) == (
        uuid.UUID(sub["id"]),
        Decimal("7.200") * rides,
        Decimal("7.000") * rides,
        Decimal("-0.200") * rides,
    )

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    approved = await client.post(f"/drivers/me/commutes/{sub['id']}/approve", headers=driver["headers"])
    assert approved.status_code == 200, approved.text
    async with session_factory() as session:
        row = await session.get(RiderSubscription, uuid.UUID(sub["id"]))
        await commute.generate_for(session, row, date.fromisoformat(sub["starts_on"]))
        go = await session.scalar(
            select(RideBooking).where(RideBooking.commute_id == row.id).order_by(RideBooking.scheduled_at)
        )
        go.scheduled_at = datetime.now(UTC) + timedelta(minutes=5)
        await session.commit()
    async with session_factory() as session:
        await bookings.run_due(session, get_redis_client())
    async with session_factory() as session:
        ride_id = str(
            await session.scalar(
                select(RideBooking.ride_id).where(
                    RideBooking.commute_id == uuid.UUID(sub["id"]), RideBooking.ride_id.is_not(None)
                )
            )
        )
    for step in ("arrive", "start", "complete"):
        done = await client.post(f"/rides/{ride_id}/{step}", headers=driver["headers"])
        assert done.status_code == 200, done.text
    assert done.json()["final_fare"] == "7.000"
    assert "rounding" not in {line["kind"] for line in done.json()["fare_lines"] or []}, "المشوارُ قُرِّب مرّتين"
    payments = (await payments_of(client, rider["headers"], ride_id))["payments"]
    assert [(p["method"], p["amount"]) for p in payments] == [("commute", "7.000")]
    async with session_factory() as session:
        percent = (await session.get(Ride, uuid.UUID(ride_id))).commission_percent_at_ride
        commission = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.ride_id == uuid.UUID(ride_id),
                WalletTransaction.type == WalletTransactionType.COMMISSION,
            )
        )
    assert percent == Decimal("10")
    assert Decimal(commission) == Decimal("-0.720"), "العمولةُ على سعر الرحلة المقرَّب لا المسعَّر"

    [incentive] = await _entries(session_factory, driver["user_id"], WalletTransactionType.COMMUTE_INCENTIVE)
    assert incentive.amount == Decimal("0.500")
    [journal] = await _journal(session_factory, "commute_incentive")
    assert (journal.source_id, journal.precise, journal.rounded) == (
        uuid.UUID(ride_id),
        Decimal("0.300"),
        Decimal("0.500"),
    )

    before = Decimal((await wallet_of(client, rider["headers"]))["balance"])
    cancelled = await client.post(f"/me/commutes/{sub['id']}/cancel", headers=rider["headers"])
    assert cancelled.status_code == 200, cancelled.text
    after = Decimal((await wallet_of(client, rider["headers"]))["balance"])
    assert after - before == Decimal("7.000") * (rides - 1), "ما لم يُستعمل لم يعد بسعره المقرَّب حرفاً"
    assert len(await _journal(session_factory, "commute_price")) == 1


# ------------------------------------------------------------------ الاستردادُ الأسبوعيّ والإحالة


async def test_the_weekly_cashback_lands_rounded_and_the_fire_promises_the_same(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**`1.750 ⇐ 2.000`** — النارُ تَعِد بما سينزل، وينزل مقرَّباً لحظةَ نزوله، وفرقُه صفٌّ بمعرّف السلسلة."""
    async with session_factory() as session:
        session.add_all(
            [ServiceSetting(country_code="JO", cashback_amount=Decimal("1.750")), ServiceSetting(country_code="LY")]
        )
        await session.commit()
    await enable_features(session_factory, cashback_tests.FLAG)
    await _enable_rounding(client, admin_headers)
    rider = await rider_session(client)
    assert (await client.get("/me/cashback", headers=rider["headers"])).json()["amount"] == "2.000"

    for offset in range(6):
        streak = await cashback_tests._day(
            session_factory, rider["user"]["id"], cashback_tests.SATURDAY + timedelta(days=offset)
        )
    assert streak.status == "won"
    [credit] = await _entries(session_factory, rider["user"]["id"], WalletTransactionType.CASHBACK)
    assert credit.amount == Decimal("2.000")
    [journal] = await _journal(session_factory, "cashback")
    assert (journal.source_id, journal.precise, journal.rounded) == (streak.id, Decimal("1.750"), Decimal("2.000"))


async def test_the_referral_bonus_is_one_entry_rounded_once_and_shown_as_it_will_be_paid(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**الأساسُ والعلاوةُ قيدٌ واحدٌ يُقرَّب مرّةً**: `3.200 + 1.100 = 4.300 ⇐ 4.500` — لا `3.000 + 1.000`. **والشاشةُ تعرض ما
    سيُدفع**: الأساسُ `3.000`، والمجموعُ `4.500`، والعلاوةُ فرقُهما `1.500` — فيُجمعان إليه حرفاً."""
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await referral_tests._set_policy(client, admin_headers, amount="3.200", rides=0, female_bonus="1.100")
    await _enable_rounding(client, admin_headers)

    referrer = await register(client, DRIVER)
    mine = await referral_tests._my_referrals(client, auth(referrer))
    program = referral_tests._program(mine, REFERRAL_TYPE_DRIVER)
    assert (program["reward_amount"], program["female_bonus_amount"], program["female_total_amount"]) == (
        "3.000",
        "1.500",
        "4.500",
    )

    referred = await approved_driver(
        client, session_factory, SECOND_DRIVER | {"referral_code": mine["code"]}, plate_number="AMM-7001"
    )
    await referral_tests._stamp_female(session_factory, referred["driver_id"])
    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 1

    [bonus] = await _entries(session_factory, referrer["user"]["id"], WalletTransactionType.REFERRAL_BONUS)
    assert bonus.amount == Decimal("4.500")
    referral = await referral_tests._referral_of(session_factory, uuid.UUID(referred["user_id"]))
    assert referral.reward_amount == Decimal("4.500")
    [journal] = await _journal(session_factory, "referral_bonus")
    assert (journal.source_id, journal.precise, journal.rounded) == (referral.id, Decimal("4.300"), Decimal("4.500"))


async def test_a_referral_bonus_rounded_to_zero_is_journalled_and_closed_not_retried_forever(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**مراجعةُ المال البند ١٠**: مكافأةُ `0.200` ⇐ **`0.000`** بالأقرب — **صفٌّ صريحٌ في السجلّ** (`0.200 ⇐ 0.000`، الفرق `−0.200`)
    **وتُغلق**: لا تُدفع ولا تُسأل في الدورة التالية (كانت تبقى مستحقّةً تمرّ عليها المهمةُ إلى الأبد ولا يقيَّد ما ضاع). ولا قيدَ
    في الدفتر ولا `rewarded_at` — لم يُدفع شيء."""
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await referral_tests._set_policy(client, admin_headers, amount="0.200", rides=0)
    await _enable_rounding(client, admin_headers)

    referrer = await register(client, DRIVER)
    mine = await referral_tests._my_referrals(client, auth(referrer))
    referred = await approved_driver(
        client, session_factory, SECOND_DRIVER | {"referral_code": mine["code"]}, plate_number="AMM-7002"
    )
    async with session_factory() as session:
        assert await referrals_service.pay_due(session) == [], "أُشعر صاحبُها بمكافأةٍ لم تُدفع"
    referral = await referral_tests._referral_of(session_factory, uuid.UUID(referred["user_id"]))
    assert referral.rewarded_at is None and referral.reward_amount is None
    [journal] = await _journal(session_factory, "referral_bonus")
    assert (journal.source_id, journal.precise, journal.rounded, journal.difference) == (
        referral.id,
        Decimal("0.200"),
        Decimal("0.000"),
        Decimal("-0.200"),
    ), "مكافأةٌ قُرِّبت إلى صفرٍ بلا صفٍّ يقولها"
    assert await _entries(session_factory, referrer["user"]["id"], WalletTransactionType.REFERRAL_BONUS) == []

    # **ولا تُسأل ثانيةً** — والصفُّ واحدٌ ولو مرّت الدورة
    async with session_factory() as session:
        assert referral.id not in await referrals_service.due_ids(session)
        assert await referrals_service.pay_due(session) == []
    assert len(await _journal(session_factory, "referral_bonus")) == 1


# ------------------------------------------------------------------ بين المدن والمتجر


async def _intercity_route_and_driver(client: AsyncClient, admin_headers: dict, session_factory) -> tuple[dict, dict]:
    """طريقُ عمّان–إربد (سيارةٌ `22.700` · مقعدٌ `1.250`) وكبتنٌ بتصريحٍ لأربعة مقاعد."""
    async with session_factory() as session:
        session.add_all([ServiceSetting(country_code="JO"), ServiceSetting(country_code="LY")])
        await session.commit()
    await enable_features(session_factory, FeatureKey.INTERCITY_ENABLED.value)
    route = (
        await client.post(
            "/admin/intercity/routes",
            json={
                "country_code": "JO",
                "from_city": "عمّان",
                "to_city": "إربد",
                "from_lat": 31.95,
                "from_lng": 35.91,
                "from_point": "مجمّع الشمال",
                "to_lat": 32.55,
                "to_lng": 35.85,
                "to_point": "مجمّع عمّان الجديد",
                "price_car": "22.700",
                "price_seat": "1.250",
            },
            headers=admin_headers,
        )
    ).json()
    driver = await approved_driver(client, session_factory, DRIVER)
    async with session_factory() as session:
        vehicle_id = await session.scalar(select(Vehicle.id).where(Vehicle.driver_id == driver["driver_id"]))
    granted = await client.post(
        f"/admin/intercity/drivers/{driver['driver_id']}/permit",
        json={
            "vehicle_id": str(vehicle_id),
            "seats": 4,
            "insurance_expires_on": (date.today() + timedelta(days=200)).isoformat(),
        },
        headers=admin_headers,
    )
    assert granted.status_code == 201, granted.text
    return route, driver


async def test_intercity_commission_is_on_the_priced_bookings_and_listings_show_rounded_prices(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**مراجعةُ المال البند ٤**: الكبتنُ يقبض المقرَّب، **والعمولةُ على المسعَّر** — مقاعدُ المحفظة `3.750 ⇐ 4.000`: عمولتُها
    `0.375` لا `0.400`؛ والسيارةُ النقديّة `22.700 ⇐ 22.500`: دَينُ عمولتها `2.270` لا `2.250`. **والبند ١٣**: قائمةُ الراكب تعرض
    السعرين مقرَّبَين كما يُدفعان (`1.500` للمقعد · `22.500` للسيارة)، والمجمَّدُ على الرحلة بدقّته."""
    await set_commission(session_factory, "10")
    await _enable_rounding(client, admin_headers)
    route, driver = await _intercity_route_and_driver(client, admin_headers, session_factory)

    async def trip(hours: float) -> dict:
        posted = await client.post(
            "/drivers/me/intercity/trips",
            json={
                "route_id": route["id"],
                "departs_at": (datetime.now(UTC) + timedelta(hours=hours)).isoformat(),
                "seats": 4,
                "min_seats": 1,
            },
            headers=driver["headers"],
        )
        assert posted.status_code == 201, posted.text
        return posted.json()

    seats_trip, car_trip = await trip(10), await trip(12)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    listed = {row["id"]: row for row in (await client.get("/intercity/trips", headers=rider["headers"])).json()}
    assert (listed[seats_trip["id"]]["price_seat"], listed[seats_trip["id"]]["price_car"]) == ("1.500", "22.500")

    seats = await client.post(
        "/intercity/bookings", json={"trip_id": seats_trip["id"], "seats": 3}, headers=rider["headers"]
    )
    assert seats.status_code == 201 and seats.json()["amount"] == "4.000", seats.text
    car = await client.post(
        "/intercity/bookings", json={"trip_id": car_trip["id"], "whole_car": True}, headers=rider["headers"]
    )
    assert car.status_code == 201 and car.json()["amount"] == "22.500", car.text

    for trip_id in (seats_trip["id"], car_trip["id"]):
        for step in ("depart", "complete"):
            moved = await client.post(f"/drivers/me/intercity/trips/{trip_id}/{step}", headers=driver["headers"])
            assert moved.status_code == 200, moved.text

    [earning] = await _entries(session_factory, driver["user_id"], WalletTransactionType.INTERCITY_EARNING)
    [commission] = await _entries(session_factory, driver["user_id"], WalletTransactionType.COMMISSION)
    assert (earning.amount, commission.amount) == (Decimal("4.000"), Decimal("-0.375")), "عمولةُ المقاعد على المقرَّب"
    async with session_factory() as session:
        debt = await session.scalar(
            select(DriverDebt.amount).where(DriverDebt.source == DriverDebtSource.INTERCITY_COMMISSION)
        )
    assert debt == Decimal("2.270"), "دَينُ عمولة السيارة على المقرَّب"


async def test_an_intercity_booking_is_rounded_on_its_total_and_refunded_as_held(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**المجموعُ يُقرَّب لا المقعد**: ثلاثةُ مقاعد × `1.250 = 3.750 ⇐ 4.000` تُحفظ من المحفظة، **وتُردّ `4.000` كما أُخذت**؛
    **والسيارةُ النقديّةُ `22.700 ⇐ 22.500`** — وكلٌّ صفٌّ بمعرّف حجزه."""
    async with session_factory() as session:
        session.add_all([ServiceSetting(country_code="JO"), ServiceSetting(country_code="LY")])
        await session.commit()
    await enable_features(session_factory, FeatureKey.INTERCITY_ENABLED.value)
    await _enable_rounding(client, admin_headers)
    route = (
        await client.post(
            "/admin/intercity/routes",
            json={
                "country_code": "JO",
                "from_city": "عمّان",
                "to_city": "إربد",
                "from_lat": 31.95,
                "from_lng": 35.91,
                "from_point": "مجمّع الشمال",
                "to_lat": 32.55,
                "to_lng": 35.85,
                "to_point": "مجمّع عمّان الجديد",
                "price_car": "22.700",
                "price_seat": "1.250",
            },
            headers=admin_headers,
        )
    ).json()
    driver = await approved_driver(client, session_factory, DRIVER)
    async with session_factory() as session:
        vehicle_id = await session.scalar(select(Vehicle.id).where(Vehicle.driver_id == driver["driver_id"]))
    granted = await client.post(
        f"/admin/intercity/drivers/{driver['driver_id']}/permit",
        json={
            "vehicle_id": str(vehicle_id),
            "seats": 4,
            "insurance_expires_on": (date.today() + timedelta(days=200)).isoformat(),
        },
        headers=admin_headers,
    )
    assert granted.status_code == 201, granted.text

    async def trip(hours: float) -> dict:
        posted = await client.post(
            "/drivers/me/intercity/trips",
            json={
                "route_id": route["id"],
                "departs_at": (datetime.now(UTC) + timedelta(hours=hours)).isoformat(),
                "seats": 4,
                "min_seats": 1,
            },
            headers=driver["headers"],
        )
        assert posted.status_code == 201, posted.text
        return posted.json()

    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    seats = await client.post(
        "/intercity/bookings", json={"trip_id": (await trip(10))["id"], "seats": 3}, headers=rider["headers"]
    )
    assert seats.status_code == 201, seats.text
    assert seats.json()["amount"] == "4.000"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "16.000"

    car = await client.post(
        "/intercity/bookings", json={"trip_id": (await trip(12))["id"], "whole_car": True}, headers=rider["headers"]
    )
    assert car.status_code == 201, car.text
    assert (car.json()["amount"], car.json()["payment"]) == ("22.500", "cash")

    journal = {row.source_id: row for row in await _journal(session_factory, "intercity_booking")}
    assert (journal[uuid.UUID(seats.json()["id"])].precise, journal[uuid.UUID(seats.json()["id"])].difference) == (
        Decimal("3.750"),
        Decimal("0.250"),
    )
    assert journal[uuid.UUID(car.json()["id"])].difference == Decimal("-0.200")

    back = await client.post(f"/intercity/bookings/{seats.json()['id']}/cancel", headers=rider["headers"])
    assert back.status_code == 200, back.text
    assert (await wallet_of(client, rider["headers"]))["balance"] == "20.000", "الردُّ لم يكن ما أُخذ حرفاً"
    assert len(journal) == 2 and len(await _journal(session_factory, "intercity_booking")) == 2


async def test_a_vehicle_skin_is_shown_and_sold_at_its_rounded_price(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**`5.300 ⇐ 5.500`** — البطاقةُ تعرضه، والشراءُ يخصمه ويجمّده على صفِّ المِلكيّة، وفرقُه صفٌّ بمعرّفه."""
    await enable_features(session_factory, "wallet_enabled", "vehicle_skins_enabled")
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "20.000")
    skin = await skin_tests.make_skin(session_factory, name="مقرَّبة", price="5.300")

    store = (await client.get(f"{skin_tests.SKINS}/store", headers=driver["headers"])).json()
    assert [row["price"] for row in store["skins"] if row["id"] == str(skin)] == ["5.500"]
    bought = await client.post(f"{skin_tests.SKINS}/{skin}/buy", headers=driver["headers"])
    assert bought.status_code == 200, bought.text
    assert bought.json()["balance_after"] == "14.500"

    async with session_factory() as session:
        owned = await session.scalar(select(DriverVehicleSkin).where(DriverVehicleSkin.skin_id == skin))
    assert owned.price_paid == Decimal("5.500")
    [journal] = await _journal(session_factory, "skin_purchase")
    assert (journal.source_id, journal.precise, journal.rounded) == (owned.id, Decimal("5.300"), Decimal("5.500"))


# ------------------------------------------------------------------ السلفة


async def test_the_advance_cap_is_a_multiple_the_request_must_be_one_and_full_repayment_returns_its_excess(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**السقفُ أكبرُ مضاعفٍ لا يتجاوزه** (`2.700 ⇐ 2.500`)، **والمطلوبُ مضاعفٌ وإلا رُدّ**. ثمّ يقتطع رحلةٌ ٢٠٪ من `8.000`
    (`1.600`، نسبةٌ تبقى بدقّتها كالعمولة) فيبقى `0.400` — **والسدادُ الكاملُ `0.500` والزائدُ `0.100` يعود قيداً صريحاً**:
    المسدَّدُ `2.000` حرفاً، والكشفُ يقرؤه `2.000`، وصفٌّ في السجلّ «للأعلى»."""
    await ensure_plan(session_factory, name="يوميُّ التقريب", price="2.700", duration="daily")
    await advances_tests._enable(session_factory, min_kept_amount=Decimal("0"))
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    await advances_tests._qualify(session_factory, driver["driver_id"])

    state = await advances_tests._state(client, driver)
    assert state["cap"] == "2.500"
    _refused_as_not_multiple(
        await client.post("/drivers/me/advances", json={"amount": "2.300"}, headers=driver["headers"]),
        lower="2.000",
        upper="2.500",
    )
    taken = await client.post("/drivers/me/advances", json={"amount": "2.000"}, headers=driver["headers"])
    assert taken.status_code == 201, taken.text

    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "50.000")
    await bring_online(client, driver, NEAR_PICKUP)
    ride = await completed_ride(client, rider["headers"], driver)
    assert (await pay_ride(client, rider["headers"], ride["id"], "wallet")).status_code == 201
    [deducted] = await _entries(session_factory, driver["user_id"], WalletTransactionType.ADVANCE_REPAYMENT)
    assert deducted.amount == Decimal("-1.600")

    repaid = await client.post("/drivers/me/advances/repay", headers=driver["headers"])
    assert repaid.status_code == 200, repaid.text
    assert repaid.json()["status"] == "repaid"
    repayments = await _entries(session_factory, driver["user_id"], WalletTransactionType.ADVANCE_REPAYMENT)
    # **بالمبالغ لا بالترتيب**: `created_at` بداية المعاملة، وساعةُ WSL تقفز فلا يُبنى على ترتيب لحظتين
    assert sorted(entry.amount for entry in repayments) == [Decimal("-1.600"), Decimal("-0.500")]
    [returned] = await _entries(session_factory, driver["user_id"], WalletTransactionType.ROUNDING)
    assert returned.amount == Decimal("0.100") and returned.advance_id == repayments[0].advance_id
    async with session_factory() as session:
        assert await advances_service.repaid_amount(session, returned.advance_id) == Decimal("2.000")

    [journal] = await _journal(session_factory, "advance_repayment")
    assert (journal.source_id, journal.precise, journal.rounded, journal.mode) == (
        returned.advance_id,
        Decimal("0.400"),
        Decimal("0.500"),
        "up",
    )
    earnings = (await client.get("/drivers/me/earnings?period=month", headers=driver["headers"])).json()
    assert earnings["advance_repaid"] == "2.000", "الكشفُ قرأ المقرَّبَ لا المسدَّد"


# ------------------------------------------------------------------ دَينُ الكبتن


async def test_paying_the_whole_debt_rounds_up_and_the_excess_returns_to_the_wallet_explicitly(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**دَينٌ `0.800`** (عمولةُ رحلة كاش) **⇐ «ادفع الدَّين كلَّه» `1.000`**: يُقبل فوق الدَّين بأقلَّ من وحدة، **والزائدُ `0.200`
    يعود إلى محفظته قيداً من نوع `rounding`** — لا يُبتلع ولا يبقى «زائداً لا يُقيَّد». **وما ليس مضاعفاً يُردّ، وما زاد على
    الدَّين مقرَّباً يُردّ كما كان.**"""
    await set_commission(session_factory, "10")
    await _enable_rounding(client, admin_headers)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider["headers"], driver)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    assert (await client.post(f"/payments/{payment['id']}/confirm", headers=driver["headers"])).status_code == 200

    state = (await client.get("/drivers/me/debt", headers=driver["headers"])).json()
    assert (state["total"], state["pay_all_amount"]) == ("0.800", "1.000")

    _refused_as_not_multiple(
        await client.post("/drivers/me/debt/cliq", json={"amount": "0.700"}, headers=driver["headers"]),
        lower="0.500",
        upper="1.000",
    )
    over = await client.post("/drivers/me/debt/cliq", json={"amount": "1.500"}, headers=driver["headers"])
    assert over.status_code == 422 and over.json()["code"] == "invalid_input", over.text

    claim = await client.post("/drivers/me/debt/cliq", json={"amount": "1.000"}, headers=driver["headers"])
    assert claim.status_code == 201, claim.text
    confirmed = await client.post(
        f"/admin/drivers/debts/claims/{claim.json()['id']}/confirm", json={"credited": "1.000"}, headers=admin_headers
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["failure_reason"] is None, "الزائدُ رُدّ وما زال يُقرأ «لا يُقيَّد»"

    assert (await client.get("/drivers/me/debt", headers=driver["headers"])).json()["total"] == "0.000"
    [returned] = await _entries(session_factory, driver["user_id"], WalletTransactionType.ROUNDING)
    assert returned.amount == Decimal("0.200")
    assert (await wallet_of(client, driver["headers"]))["balance"] == "0.200"
    [journal] = await _journal(session_factory, "debt_settlement")
    assert (journal.source_id, journal.precise, journal.rounded, journal.difference, journal.mode) == (
        uuid.UUID(claim.json()["id"]),
        Decimal("0.800"),
        Decimal("1.000"),
        Decimal("0.200"),
        "up",
    )


# ------------------------------------------------------------------ ما يختاره الشخص


async def test_example_c_a_captain_withdraws_the_largest_multiple_and_the_fraction_stays_his(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**المثال (ج) من §٧٠-ج بأرقامه**: رصيدُه `37.842` ⇐ أقصى ما يُعرض **`37.500`** ⇐ يُحوَّل `37.500` ⇐ **يبقى `0.342` له**.
    **ولا فرقَ تقريبٍ ولا صفَّ في السجلّ** — المبلغُ اختيارُه."""
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory)
    await _adjust(client, admin_headers, driver["user_id"], "37.842", wallet="driver")

    mine = (await client.get("/wallet/me/driver", headers=driver["headers"])).json()
    assert (mine["balance"], mine["available_for_withdrawal"]) == ("37.842", "37.500")

    _refused_as_not_multiple(
        await client.post("/wallet/me/withdrawals", json={"amount": "37.842", "method": "bank"}, headers=driver["headers"]),
        lower="37.500",
        upper="38.000",
    )
    created = await client.post(
        "/wallet/me/withdrawals", json={"amount": "37.500", "method": "bank"}, headers=driver["headers"]
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert (await client.post(f"/admin/withdrawals/{request_id}/approve", headers=admin_headers)).status_code == 200
    paid = await client.post(
        f"/admin/withdrawals/{request_id}/paid", json={"reference": "BANK-37500"}, headers=admin_headers
    )
    assert paid.status_code == 200, paid.text

    mine = (await client.get("/wallet/me/driver", headers=driver["headers"])).json()
    assert (mine["balance"], mine["available_for_withdrawal"]) == ("0.342", "0.000")
    assert await _journal_count(session_factory) == 0


async def test_the_minimum_withdrawal_is_enforced_and_published_rounded_up_to_the_unit(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**مراجعةُ المال البند ١٢**: إعدادُ اللوحة `1.200` ⇐ **الحدُّ `1.500`** مشتعلاً — أصغرُ مضاعفٍ لا ينقص عنه، فبلاطةُ «الحد الأدنى»
    مضاعفٌ يُكتب ولا يُردّ (كانت `1.200` تُعرض فيُردّ ما يُكتب منها). **والإعدادُ نفسُه لا يُمسّ** — المشرفُ يرى ما ضبطه."""
    limits = await client.patch(
        "/admin/settings/wallet/JO", json={"min_withdrawal_amount": "1.200"}, headers=admin_headers
    )
    assert limits.status_code == 200, limits.text
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory)
    await _adjust(client, admin_headers, driver["user_id"], "5.000", wallet="driver")

    mine = (await client.get("/wallet/me/driver", headers=driver["headers"])).json()
    assert mine["min_withdrawal_amount"] == "1.500", "الحدُّ المنشورُ ليس مضاعفاً للوحدة"
    refused = await client.post(
        "/wallet/me/withdrawals", json={"amount": "1.000", "method": "bank"}, headers=driver["headers"]
    )
    assert refused.status_code == 409 and refused.json()["code"] == "wallet_limit_exceeded", refused.text
    assert "1.500" in refused.json()["message"], refused.json()
    created = await client.post(
        "/wallet/me/withdrawals", json={"amount": "1.500", "method": "bank"}, headers=driver["headers"]
    )
    assert created.status_code == 201, created.text
    assert limits.json()["min_withdrawal_amount"] == "1.200", "الإعدادُ نفسُه قُرِّب"


async def test_a_scheduled_booking_shows_its_estimate_rounded_to_rider_and_captain(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**مراجعةُ المال البند ١٣**: تقديرُ الحجز المجدول `3.364` يُعرض **`3.500`** — عند الراكب في حجزه، وعند الكبتن في «القادمة» —
    **والمحفوظُ بدقّته** (`estimated_fare_at_booking` في الصفّ)؛ والتقريبُ المحفوظُ مرّةً عند إنهاء رحلته."""
    from tests.test_rounding import _route

    _route(monkeypatch, "3.328", "7.00")
    await _guarantee_fee(session_factory, "1.500")
    await _enable_rounding(client, admin_headers)
    rider, driver = await guaranteed_tests._setup(client, admin_headers, session_factory)

    booked = await guaranteed_tests._book(client, rider)
    assert booked.status_code == 201, booked.text
    assert booked.json()["estimated_fare_at_booking"] == "3.500"
    listed = (await client.get("/me/bookings", headers=rider["headers"])).json()
    assert [row["estimated_fare_at_booking"] for row in listed] == ["3.500"]
    async with session_factory() as session:
        row = await session.get(RideBooking, uuid.UUID(booked.json()["id"]))
    assert row.estimated_fare_at_booking == Decimal("3.364"), "المحفوظُ قُرِّب — والتقريبُ للعرض وحدَه"

    accepted = await client.post(f"/drivers/me/guarantees/{booked.json()['id']}/accept", headers=driver["headers"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["estimated_fare_at_booking"] == "3.500"
    upcoming = (await client.get("/drivers/me/guarantees", headers=driver["headers"])).json()
    assert [row["estimated_fare_at_booking"] for row in upcoming] == ["3.500"]


async def test_tip_buttons_are_rounded_and_a_typed_fraction_is_refused(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**الأزرارُ مقرَّبة** (`0.300 ⇐ 0.500` · `1.100 ⇐ 1.000`) **والأقصى أكبرُ مضاعفٍ لا يتجاوز `2.700`** — `2.500`؛ ومبلغٌ
    مكتوبٌ بكسرٍ يُردّ، والمضاعفُ فوق السقف يُردّ بسقفه كما كان."""
    await enable_features(session_factory, "wallet_enabled", "tips_enabled")
    await _enable_rounding(
        client,
        admin_headers,
        tip_preset_small="0.300",
        tip_preset_medium="1.100",
        tip_max="2.700",
    )
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    ride = await completed_ride(client, rider["headers"], driver)

    options = (await client.get(f"/rides/{ride['id']}/tip", headers=rider["headers"])).json()
    assert options["offered"] is True
    assert (options["presets"], options["max_amount"]) == (["0.500", "1.000"], "2.500")

    _refused_as_not_multiple(
        await client.post(f"/rides/{ride['id']}/tip", json={"amount": "0.700"}, headers=rider["headers"]),
        lower="0.500",
        upper="1.000",
    )
    over = await client.post(f"/rides/{ride['id']}/tip", json={"amount": "3.000"}, headers=rider["headers"])
    assert over.status_code == 422 and over.json()["code"] == "invalid_input", over.text
    given = await client.post(f"/rides/{ride['id']}/tip", json={"amount": "2.500"}, headers=rider["headers"])
    assert given.status_code == 201, given.text


async def test_transfers_and_every_top_up_door_take_multiples_only_and_before_any_provider_order(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**التحويلُ والشحنُ بأبوابه الثلاثة**: الكسرُ يُردّ بـ`amount_not_multiple` **قبل أن يُفتح طلبٌ عند مزوّد**، والمضاعفُ يمرّ.
    **وما يؤكّده المشرفُ في الشحن اليدويّ هو ما وصل حرفاً** (`12.340`) — لا يُقرَّب ولا يُردّ."""
    await enable_card_provider(session_factory)
    await enable_cliq_provider(session_factory)
    await _enable_rounding(client, admin_headers)
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "10.000")

    def transfer(amount: str) -> dict:
        return {"recipient_phone": OTHER_RIDER["phone"], "amount": amount, "idempotency_key": uuid.uuid4().hex}

    refused = await client.post("/wallet/me/transfers", json=transfer("2.300"), headers=sender["headers"])
    _refused_as_not_multiple(refused, lower="2.000", upper="2.500")
    assert refused.json()["field"] == "amount"
    assert (await client.post("/wallet/me/transfers", json=transfer("2.500"), headers=sender["headers"])).status_code == 200

    _refused_as_not_multiple(
        await client.post(
            "/wallet/me/topups", json={"method": "cliq", "amount": "12.300", "reference": "CLQ-R1"}, headers=sender["headers"]
        ),
        lower="12.000",
        upper="12.500",
    )
    requested = await client.post(
        "/wallet/me/topups", json={"method": "cliq", "amount": "12.500", "reference": "CLQ-R2"}, headers=sender["headers"]
    )
    assert requested.status_code == 201, requested.text
    confirmed = await client.post(
        f"/admin/topups/{requested.json()['id']}/confirm", json={"amount": "12.340"}, headers=admin_headers
    )
    assert confirmed.status_code == 200, confirmed.text
    [topup] = [
        entry
        for entry in await _entries(session_factory, sender["user_id"], WalletTransactionType.TOPUP)
        if entry.amount == Decimal("12.340")
    ]
    assert topup.amount == Decimal("12.340"), "ما وصل قُرِّب"

    _refused_as_not_multiple(
        await client.post("/wallet/me/topups/card", json={"amount": "5.300"}, headers=sender["headers"]),
        lower="5.000",
        upper="5.500",
    )
    _refused_as_not_multiple(
        await client.post("/wallet/me/topups/cliq", json={"amount": "5.300"}, headers=sender["headers"]),
        lower="5.000",
        upper="5.500",
    )
    async with session_factory() as session:
        opened = await session.scalar(select(func.count()).select_from(ProviderOrder))
    assert opened == 0, "فُتح طلبٌ عند مزوّدٍ بمبلغٍ ليس مضاعفاً"

    card = await client.post("/wallet/me/topups/card", json={"amount": "5.500"}, headers=sender["headers"])
    assert card.status_code == 201 and card.json()["amount"] == "5.500", card.text
    cliq = await client.post("/wallet/me/topups/cliq", json={"amount": "5.500"}, headers=sender["headers"])
    assert cliq.status_code == 201 and cliq.json()["amount"] == "5.500", cliq.text
    assert await _journal_count(session_factory) == 0, "المبلغُ المختارُ لا تقريبَ له فلا صفّ"


async def test_switched_off_chosen_fractions_pass_and_nothing_is_journalled(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**مطفأً كما كان حرفاً** — وهو حالُ السوقين بعد `0104`: التحويلُ بكسوره، والمتاحُ للسحب بكسوره، و«ادفع الدَّين كلَّه» هو
    الدَّينُ نفسُه، ولا صفَّ في السجلّ."""
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "10.000")
    moved = await client.post(
        "/wallet/me/transfers",
        json={"recipient_phone": OTHER_RIDER["phone"], "amount": "2.345", "idempotency_key": uuid.uuid4().hex},
        headers=sender["headers"],
    )
    assert moved.status_code == 200, moved.text

    driver = await approved_driver(client, session_factory)
    await _adjust(client, admin_headers, driver["user_id"], "37.842", wallet="driver")
    mine = (await client.get("/wallet/me/driver", headers=driver["headers"])).json()
    assert mine["available_for_withdrawal"] == "37.842"
    state = (await client.get("/drivers/me/debt", headers=driver["headers"])).json()
    assert state["pay_all_amount"] == state["total"]
    assert await _journal_count(session_factory) == 0
