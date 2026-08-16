"""سدادُ رسم الإلغاء مع رحلةٍ لاحقة، ومسارُ الحامل، ومآلُ ما لا يُسدَّد.

(`design/CANCELLATION-FEE.md` §5 و§6 و§7 و§10، وقائمةُ اختباراتها في §12)

**وكلُّ اختبارٍ هنا يسأل الدفتر لا رمزَ الاستجابة**: الميزةُ التي وُجد لها هذا
الملفُّ كانت رقماً يُعرض ولا يُحصَّل، ورقمُ استجابةٍ ٢٠٠ هو بالضبط ما كان
يظهر يومَها.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.cancellation import CancellationSetting, RideCancellationCharge
from app.models.driver import Driver
from app.models.enums import (
    CancellationChargeStatus,
    CountryCode,
    UnpaidCancellationOutcome,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    DROPOFF,
    PICKUP,
    accepted_ride,
    approved_driver,
    bring_online,
    broadcast_location,
    completed_ride,
    pay_ride,
    rider_session,
    set_commission,
    topup_wallet,
)

# نقطةٌ بعيدةٌ عن الالتقاء بما يتجاوز أيَّ عتبةِ إعفاء (~5 كم)
FAR_AWAY = {"lat": 32.0060, "lng": 35.9106}

SECOND_DRIVER = {
    "phone": "+962790000077",
    "password": "SecondCaptain1",
    "name": "كبتنُ الرحلة الثانية",
    "role": "driver",
    "country_code": "JO",
}


async def _policy(session_factory, **values) -> None:
    async with session_factory() as session:
        row = await session.get(CancellationSetting, CountryCode.JO)
        if row is None:
            row = CancellationSetting(country_code=CountryCode.JO)
            session.add(row)
        for key, value in values.items():
            setattr(row, key, value)
        await session.commit()


async def _charge(session_factory, ride_id: str) -> RideCancellationCharge | None:
    async with session_factory() as session:
        return await session.scalar(
            select(RideCancellationCharge).where(
                RideCancellationCharge.ride_id == uuid.UUID(ride_id)
            )
        )


async def _entries(session_factory, owner_id: str) -> dict[str, Decimal]:
    """مجموعُ كلِّ نوعٍ في دفتر صاحبٍ واحد — الحكمُ الذي تُقاس عليه كلُّ حالة."""
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    WalletTransaction.type,
                    func.coalesce(func.sum(WalletTransaction.amount), 0),
                )
                .where(WalletTransaction.owner_id == uuid.UUID(owner_id))
                .group_by(WalletTransaction.type)
            )
        ).all()
    return {row[0].value: Decimal(row[1]) for row in rows}


async def _owe(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    *,
    balance: str = "0",
) -> dict:
    """يصنع ديناً حقيقياً: رحلةٌ تُقبل، والكبتنُ يتحرك، والراكبُ يُلغي.

    **ولا يُحقن الصفُّ في القاعدة**: الدَّينُ الذي لم يمرّ من باب الإلغاء دَينٌ
    يوافق افتراضاتِ من كتبه — وهي العلّةُ التي أجازت `awaiting_confirmation`.
    """
    await _policy(session_factory, exempt_within_meters=300)
    injured = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, injured)
    rider = await rider_session(client)
    if balance != "0":
        await topup_wallet(client, admin_headers, rider["user"]["id"], balance)

    ride = await accepted_ride(client, rider["headers"], injured)
    await broadcast_location(client, injured, **FAR_AWAY)
    cancelled = await client.post(
        f"/rides/{ride['id']}/cancel",
        json={"reason": "غيّرت رأيي"},
        headers=rider["headers"],
    )
    assert cancelled.status_code == 200, cancelled.text

    charge = await _charge(session_factory, ride["id"])
    assert charge is not None and charge.status is CancellationChargeStatus.PENDING
    # الكبتنُ الأول يخرج من الخدمة كي لا يُسنَد إليه الطلبُ التالي
    await client.post("/drivers/me/offline", headers=injured["headers"])
    return {"rider": rider, "injured": injured, "charge": charge}


# --------------------------------------------------------------- الكاش (§6-أ)


async def test_the_ledger_tells_the_truth_at_three(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """§12: الراكبُ سلّم، والمتضررُ زاد، **والحاملُ لم يربح شيئاً** ممّا مرّ بيده.

    والقيدان على الحامل والمتضرر لا قيدٌ صافٍ واحد: صافٍ يعطي الرقمَ نفسَه
    ويُخفي أن للمال طرفَين — وأن أحدهما كبتنٌ آخر لا المنصّة.
    """
    setup = await _owe(client, admin_headers, session_factory)
    rider, injured, charge = setup["rider"], setup["injured"], setup["charge"]

    carrier = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, carrier)
    # رصيدٌ يكفي التحويل: الكاشُ في يده، والتحويلُ من محفظته
    await topup_wallet(client, admin_headers, carrier["user_id"], "20.000")

    ride = await completed_ride(client, rider["headers"], carrier)
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    assert paid.status_code == 201, paid.text
    payment_id = paid.json()["payments"][0]["id"]
    confirmed = await client.post(
        f"/payments/{payment_id}/confirm", headers=carrier["headers"]
    )
    assert confirmed.status_code == 200, confirmed.text

    settled = await _charge(session_factory, str(charge.ride_id))
    assert settled.status is CancellationChargeStatus.SETTLED
    assert settled.carrier_driver_id == carrier["driver_id"]
    assert settled.collected_from_ride_id == uuid.UUID(ride["id"])

    # ١) الراكب: لا قيدَ رسمٍ عليه أصلاً — سلّمه نقداً بيده
    assert "cancellation_fee" not in await _entries(
        session_factory, rider["user"]["id"]
    )
    # ٢) المتضرر: تعويضٌ بقيمة الرسم كاملاً
    injured_ledger = await _entries(session_factory, injured["user_id"])
    assert injured_ledger["cancellation_compensation"] == settled.amount
    # ٣) **والحاملُ لم يربح شيئاً**: خُصم منه ما ليس له، ولا `ride_earning`
    #    على رحلةٍ نقدية أصلاً (القسم 9) — فمرورُ المال بيده لم يزده ديناراً
    carrier_ledger = await _entries(session_factory, carrier["user_id"])
    assert carrier_ledger["cancellation_fee"] == -settled.amount
    assert "cancellation_compensation" not in carrier_ledger
    assert "ride_earning" not in carrier_ledger


async def test_no_commission_falls_on_money_that_is_not_his(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """§5: عمولةُ الرحلة اللاحقة على **أجرتها وحدها**، لا على المجموع.

    وهذا هو نصُّ قرار المالك في ثلاثة أسباب: ضمُّ المبلغ للأجرة يجعل أرقامَ
    الكبتن تكذب عليه، ويحسب عمولةً على مالٍ لا يخصّه، ويُخفي أن صاحبَ الدَّين
    كبتنٌ آخر.
    """
    await set_commission(session_factory, percent="10", applies_to="all_rides")
    setup = await _owe(client, admin_headers, session_factory)
    rider = setup["rider"]

    carrier = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, carrier)
    await topup_wallet(client, admin_headers, carrier["user_id"], "20.000")

    ride = await completed_ride(client, rider["headers"], carrier)
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    payment_id = paid.json()["payments"][0]["id"]
    await client.post(f"/payments/{payment_id}/confirm", headers=carrier["headers"])

    fare = Decimal(paid.json()["payments"][0]["amount"])
    ledger = await _entries(session_factory, carrier["user_id"])
    assert ledger["commission"] == -(fare * Decimal("0.10")).quantize(
        Decimal("0.001")
    )


async def test_a_carried_charge_stops_being_the_riders_debt(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """من سلّم المبلغَ نقداً برئت ذمّتُه — ولو لم يحوّله الحاملُ بعد.

    وبقاؤه «على الراكب» يمنعه من الطلب بدَينٍ دفعه بيده، وهو أسوأُ ما يمكن أن
    يفعله حدُّ الإيقاف.
    """
    setup = await _owe(client, admin_headers, session_factory)
    rider = setup["rider"]

    carrier = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, carrier)
    # **بلا رصيد**: التحويلُ يتعذّر فيبقى الصفُّ معلّقاً على الحامل لا الراكب
    ride = await completed_ride(client, rider["headers"], carrier)
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    payment_id = paid.json()["payments"][0]["id"]
    await client.post(f"/payments/{payment_id}/confirm", headers=carrier["headers"])

    charge = await _charge(session_factory, str(setup["charge"].ride_id))
    assert charge.status is CancellationChargeStatus.PENDING
    assert charge.carrier_driver_id == carrier["driver_id"]

    wallet = await client.get("/wallet/me", headers=rider["headers"])
    assert Decimal(wallet.json()["cancellation_debt"]) == Decimal("0.000")

    # وحدُّ الإيقاف لا يعدّه عليه: طلبٌ جديدٌ يمرّ ولو كان الحدُّ واحداً
    await _policy(session_factory, block_after_unpaid=1)
    again = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=rider["headers"],
    )
    assert again.status_code == 201, again.text


async def test_what_he_carries_leaves_his_available_balance(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """§12: طلبُ سحبٍ بقيمة الرصيد الظاهر يُرفض ما دام في يده مالُ غيره."""
    setup = await _owe(client, admin_headers, session_factory)
    rider = setup["rider"]

    carrier = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, carrier)
    ride = await completed_ride(client, rider["headers"], carrier)
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    payment_id = paid.json()["payments"][0]["id"]
    await client.post(f"/payments/{payment_id}/confirm", headers=carrier["headers"])

    async with session_factory() as session:
        balance = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == uuid.UUID(carrier["user_id"]),
                WalletTransaction.owner_type == WalletOwnerType.DRIVER,
            )
        )

    wallet = await client.get("/wallet/me/driver", headers=carrier["headers"])
    body = wallet.json()
    dues = Decimal(body["carrier_dues"])
    assert dues > 0
    assert Decimal(body["available_for_withdrawal"]) == Decimal(balance) - dues


async def test_a_topup_transfers_what_the_carrier_holds(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """§7: «لحظةَ اكتمال الشحن» — بلا مراجعةٍ إداريةٍ وبلا دورةٍ مجدولة."""
    setup = await _owe(client, admin_headers, session_factory)
    rider, injured = setup["rider"], setup["injured"]

    carrier = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, carrier)
    ride = await completed_ride(client, rider["headers"], carrier)
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    payment_id = paid.json()["payments"][0]["id"]
    await client.post(f"/payments/{payment_id}/confirm", headers=carrier["headers"])

    before = await _entries(session_factory, injured["user_id"])
    assert "cancellation_compensation" not in before

    await topup_wallet(client, admin_headers, carrier["user_id"], "20.000")

    charge = await _charge(session_factory, str(setup["charge"].ride_id))
    assert charge.status is CancellationChargeStatus.SETTLED
    after = await _entries(session_factory, injured["user_id"])
    assert after["cancellation_compensation"] == charge.amount


# ------------------------------------------------------------ المحفظة (§6-ب)


async def test_the_wallet_channel_settles_the_debt_inside_the_settlement(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """§5 على قناة المحفظة: الأجرةُ أولاً ثم الدَّينُ ممّا بقي، **في المعاملة نفسِها**.

    والرصيدُ هنا يدخل بـ**تصحيحٍ إداري** لا بشحن، وذلك مقصود: الشحنُ يسدّد
    بنفسه (§7) فلا يبقى للرحلة ما تُسدّده — والاختبارُ الذي يمرّ لأن بابَ
    غيرِه سبقه اختبارٌ لا يملك ما يدّعيه (درسُ الأقفال المتكررة في هذا المشروع).
    """
    setup = await _owe(client, admin_headers, session_factory)
    rider, injured = setup["rider"], setup["injured"]

    driver = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    # رصيدٌ يغطّي الأجرةَ والدَّينَ معاً — يدخل من بابٍ لا يُحصّل بنفسه
    funded = await client.post(
        f"/admin/wallets/{rider['user']['id']}/adjustments",
        json={"amount": "40.000", "reason": "تصحيحٌ لاختبار السداد مع الرحلة"},
        headers=admin_headers,
    )
    assert funded.status_code == 200, funded.text
    assert (
        await _charge(session_factory, str(setup["charge"].ride_id))
    ).status is CancellationChargeStatus.PENDING

    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert paid.status_code == 201, paid.text
    # **ولا صفَّ دفعةٍ ثانٍ للدَّين**: قيدان في الدفتر لا دفعةٌ على الرحلة —
    # وصفٌّ ثانٍ يُقيَّد `ride_earning` لكبتن هذه الرحلة لا للمتضرر
    assert len(paid.json()["payments"]) == 1

    charge = await _charge(session_factory, str(setup["charge"].ride_id))
    assert charge.status is CancellationChargeStatus.SETTLED
    assert charge.carrier_driver_id is None
    assert charge.collected_from_ride_id == uuid.UUID(ride["id"])

    rider_ledger = await _entries(session_factory, rider["user"]["id"])
    assert rider_ledger["cancellation_fee"] == -charge.amount
    assert (await _entries(session_factory, injured["user_id"]))[
        "cancellation_compensation"
    ] == charge.amount


async def test_the_debt_rides_on_the_payment_screen(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """الرقمُ يصل الشاشةَ **بجانب** المتبقّي لا داخله.

    وداخلَه يُحسب على `payment.amount` فتقع عليه عمولةٌ ونصيبُ كبتن — وهو ما
    يمنعه §5 حرفاً. وبلا رقمٍ يراه الراكبُ لا يعرف كم يسلّم نقداً.
    """
    setup = await _owe(client, admin_headers, session_factory)
    rider = setup["rider"]

    driver = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    screen = await client.get(f"/rides/{ride['id']}/payments", headers=rider["headers"])
    body = screen.json()
    assert Decimal(body["cancellation_debt"]) == setup["charge"].amount
    assert Decimal(body["outstanding"]) == Decimal(ride["final_fare"])


async def test_the_offer_carries_what_the_captain_will_be_asked_to_hand_over(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """§6-أ: **الشرحُ قبل أن يقبل الرحلة لا بعدها** — حجّةُ شارة «مشتركة» بعينها.

    وحقلٌ يقرؤه التطبيقُ ولا يرسله أحدٌ شارةٌ لا تظهر أبداً، وهو شكلُ عطبٍ شحنه
    هذا المشروعُ من قبل — فيُقاس في **مخرج المسار** لا في الصف وحده.
    """
    setup = await _owe(client, admin_headers, session_factory)
    rider = setup["rider"]

    driver = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)
    assert Decimal(ride["carried_cancellation_fee"]) == setup["charge"].amount

    detail = await client.get(f"/rides/{ride['id']}", headers=driver["headers"])
    assert Decimal(detail.json()["carried_cancellation_fee"]) == setup["charge"].amount


# ------------------------------------------------------------ اللوحة و§10


async def test_waiving_closes_the_row_and_writes_no_ledger_entry(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """الإعفاءُ بابُ الاعتراض بعد الحدث (§3) — **ولا مالَ يتحرك به**.

    قيدٌ يقول «سُدِّد» يجعل الكشفَ يكذب على الطرفين، وهي قاعدةُ شطب السلفة.
    """
    setup = await _owe(client, admin_headers, session_factory)
    charge = setup["charge"]

    naked = await client.post(
        f"/admin/cancellation-charges/{charge.id}/waive",
        json={"reason": ""},
        headers=admin_headers,
    )
    assert naked.status_code == 422, naked.text

    waived = await client.post(
        f"/admin/cancellation-charges/{charge.id}/waive",
        json={"reason": "اعترض الراكب وأثبت أن الكبتن لم يتحرك"},
        headers=admin_headers,
    )
    assert waived.status_code == 200, waived.text
    assert waived.json()["status"] == "waived"

    row = await _charge(session_factory, str(charge.ride_id))
    assert row.waived_by_user_id is not None and row.waive_reason
    assert (await _entries(session_factory, setup["injured"]["user_id"])) == {}

    # ولا يُعفى مرتين: الصفُّ لم يعد معلّقاً
    again = await client.post(
        f"/admin/cancellation-charges/{charge.id}/waive",
        json={"reason": "مرةً أخرى"},
        headers=admin_headers,
    )
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "cancellation_charge_not_open"


async def test_writing_off_names_who_decided(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """§10: الخسارةُ المعترَفُ بها تحمل اسمَ صاحبها — ولا قيدَ في الدفتر."""
    setup = await _owe(client, admin_headers, session_factory)
    charge = setup["charge"]

    response = await client.post(
        f"/admin/cancellation-charges/{charge.id}/write-off",
        json={"reason": "مضت المدّة ولم يعد الراكب"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    row = await _charge(session_factory, str(charge.ride_id))
    assert row.status is CancellationChargeStatus.WRITTEN_OFF
    assert row.written_off_at is not None
    assert row.written_off_by_user_id is not None
    assert (await _entries(session_factory, setup["injured"]["user_id"])) == {}


async def test_the_company_bears_it_and_only_the_injured_is_credited(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """§10: دائنٌ بلا مدينٍ مقابل — شكلُ `referral_bonus` وخصمِ الكوبون.

    **ولا يُخصم من الراكب**: لو خُصم منه لما تحمّلت الشركةُ شيئاً.
    """
    from app.tasks.cancellation import _apply_unpaid_outcome

    setup = await _owe(client, admin_headers, session_factory)
    await _policy(
        session_factory,
        unpaid_after_days=1,
        unpaid_outcome=UnpaidCancellationOutcome.COMPANY_BEARS,
    )
    # الصفُّ يُقدَّم في الزمن بدل الانتظار يوماً — الشرطُ عمرُه لا حالتُه
    async with session_factory() as session:
        row = await session.get(RideCancellationCharge, setup["charge"].id)
        row.created_at = row.created_at.replace(year=row.created_at.year - 1)
        await session.commit()

    assert await _apply_unpaid_outcome() == 1

    row = await _charge(session_factory, str(setup["charge"].ride_id))
    assert row.status is CancellationChargeStatus.SETTLED
    injured = await _entries(session_factory, setup["injured"]["user_id"])
    assert injured["cancellation_compensation"] == row.amount
    assert "cancellation_fee" not in await _entries(
        session_factory, setup["rider"]["user"]["id"]
    )


async def test_admin_decides_leaves_the_row_for_a_human(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """«تشطبه الإدارة» ليست فعلاً للدورة — وإلا صار الخياران واحداً.

    وفرقُ الخيارين هو القرارُ نفسُه: إعدادٌ يقول «افعل» وإعدادٌ يقول «اعرضه على
    إنسان»، ودورةٌ تشطب في الحالتين تُلغي ما وُضع الإعدادُ له.
    """
    from app.tasks.cancellation import _apply_unpaid_outcome

    setup = await _owe(client, admin_headers, session_factory)
    await _policy(
        session_factory,
        unpaid_after_days=1,
        unpaid_outcome=UnpaidCancellationOutcome.ADMIN_DECIDES,
    )
    async with session_factory() as session:
        row = await session.get(RideCancellationCharge, setup["charge"].id)
        row.created_at = row.created_at.replace(year=row.created_at.year - 1)
        await session.commit()

    assert await _apply_unpaid_outcome() == 0
    row = await _charge(session_factory, str(setup["charge"].ride_id))
    assert row.status is CancellationChargeStatus.PENDING


async def test_the_grace_blocks_the_carrier_and_the_topup_frees_him(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """§6-أ: مهلةٌ ثم منعٌ من التوزيع — **والشحنُ يفكّه في مساره لا بدورةٍ تالية**.

    ومن شحن وبقي ممنوعاً عشر دقائق يقرأ الشحنَ بلا أثر، فيشحن مرةً أخرى أو
    يتّصل بالدعم (قاعدةُ `advances._settle_if_clear`).
    """
    from app.tasks.cancellation import _block_overdue_carriers

    await _policy(session_factory, carrier_grace_hours=1)
    setup = await _owe(client, admin_headers, session_factory)
    rider = setup["rider"]

    carrier = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, carrier)
    ride = await completed_ride(client, rider["headers"], carrier)
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    payment_id = paid.json()["payments"][0]["id"]
    await client.post(f"/payments/{payment_id}/confirm", headers=carrier["headers"])

    charge = await _charge(session_factory, str(setup["charge"].ride_id))
    assert charge.carrier_due_at is not None
    async with session_factory() as session:
        row = await session.get(RideCancellationCharge, charge.id)
        row.carrier_due_at = row.carrier_due_at.replace(
            year=row.carrier_due_at.year - 1
        )
        await session.commit()

    assert await _block_overdue_carriers() == 1
    async with session_factory() as session:
        assert (await session.get(Driver, carrier["driver_id"])).cancellation_carry_blocked

    await topup_wallet(client, admin_headers, carrier["user_id"], "20.000")
    async with session_factory() as session:
        driver = await session.get(Driver, carrier["driver_id"])
        assert not driver.cancellation_carry_blocked
