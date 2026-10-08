"""المدفوعاتُ غيرُ المؤكَّدة (`design/PAYMENTS-UNCONFIRMED.md`، SPEC §٦٤-ج) — **الخطواتُ ١–٥ مقيسةً بثوابتها**.

**والاتجاهُ الأوّلُ هو ما يجعل الباقي آمناً**: مطفأً (`unconfirmed_payments_enabled`) لا يتغيّر شيءٌ مما كان — لا طريقةَ تُحفظ،
ولا صفَّ يولد، ولا حجبَ، ولا نزاعَ على الكاش. **وما يُبنى فوقه يُقاس بالمال**: الصفُّ يولد بلا قيد، والإقرارُ والتذكيرُ والتبديلُ
لا تكتب في الدفتر، و«مدفوع» من المشرف والإتمامُ الآليُّ يكتبان **ما يكتبه «استلمت» حرفاً** — مقارنةً لا وصفاً.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.models.audit import AdminAuditLog
from app.models.debt import DriverDebt
from app.models.enums import (
    CountryCode,
    Currency,
    DisputeResolution,
    PaymentMethod,
    PaymentStatus,
    VehicleCategory,
)
from app.models.feature_flag import FeatureFlag
from app.models.notification import UserNotification
from app.models.payment import Payment
from app.models.payment_setting import PaymentSetting
from app.models.ride import Ride
from app.models.wallet import WalletTransaction
from app.services import dispatch
from app.services import unconfirmed_payments as service
from tests.helpers import (
    DROPOFF,
    EXPECTED_FARE,
    NEAR_PICKUP,
    OTHER_RIDER,
    PICKUP,
    broadcast_location,
    enable_features,
    pay_ride,
    payments_of,
    set_cliq_alias,
    set_commission,
    topup_wallet,
    wait_for_offer,
)
from tests.test_payments import _online_driver, _rider

pytestmark = pytest.mark.asyncio

FLAG = "unconfirmed_payments_enabled"
AUTO_FLAG = "cash_auto_confirm_enabled"
#: أجرةُ رحلة الاختبار 8.000 والعمولةُ 10٪ ⇒ 0.800
COMMISSION = Decimal("0.800")


# ------------------------------------------------------------------ مساعدات


async def completed_with(
    client: AsyncClient, rider_headers: dict, driver: dict, method: str | None
) -> tuple[dict, dict]:
    """رحلةٌ **طُلبت بطريقة دفع** حتى الإنهاء — ويعيد ردَّ الطلب وردَّ الإنهاء.

    **ويعيد بثَّ موقع الكبتن قبل الطلب**: الحضورُ يعيش ستين ثانية، والاختبارُ الذي يُنهي رحلاتٍ متتالية يتجاوزها.
    """
    await broadcast_location(client, driver, NEAR_PICKUP["lat"], NEAR_PICKUP["lng"])
    body: dict = {"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}
    if method is not None:
        body["payment_method"] = method
    created = await client.post("/rides", json=body, headers=rider_headers)
    assert created.status_code == 201, created.text
    ride_id = created.json()["id"]
    for attempt in range(3):
        await wait_for_offer(ride_id, driver["driver_id"])
        accepted = await client.post(f"/rides/{ride_id}/accept", headers=driver["headers"])
        if accepted.status_code == 200:
            break
        assert accepted.json().get("code") == "ride_offer_expired", accepted.text
    assert accepted.status_code == 200, accepted.text
    for step in ("arrive", "start", "complete"):
        response = await client.post(f"/rides/{ride_id}/{step}", headers=driver["headers"])
        assert response.status_code == 200, response.text
    return created.json(), response.json()


async def rows_of(session_factory, ride_id: str) -> list[Payment]:
    async with session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(Payment)
                    .where(Payment.ride_id == uuid.UUID(ride_id))
                    .order_by(Payment.created_at)
                )
            ).all()
        )


async def ledger_count(session_factory) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count(WalletTransaction.id))))


async def shift_ride(session_factory, ride_id: str, *, minutes: int) -> datetime:
    """يُرجع نهايةَ الرحلة إلى الوراء — **والزمنُ مدخلٌ يملكه الاختبار** لا ساعةُ الجهاز."""
    async with session_factory() as session:
        ride = await session.get(Ride, uuid.UUID(ride_id))
        ride.completed_at = ride.completed_at - timedelta(minutes=minutes)
        await session.commit()
        return ride.completed_at


async def effects(session_factory, payment_id: uuid.UUID, ride_id: uuid.UUID) -> list[tuple]:
    """**ما كُتب في المال من تأكيد دفعة**: صفوفُ الدَّين وقيودُ الدفتر على رحلتها — شكلاً ومبلغاً، بلا معرّفات."""
    async with session_factory() as session:
        debts = (
            await session.scalars(select(DriverDebt).where(DriverDebt.payment_id == payment_id))
        ).all()
        entries = (
            await session.scalars(
                select(WalletTransaction).where(WalletTransaction.ride_id == ride_id)
            )
        ).all()
    return sorted(
        [("debt", debt.source.value, str(debt.amount), debt.status.value) for debt in debts]
        + [("ledger", entry.type.value, str(entry.amount)) for entry in entries]
    )


# ------------------------------------------------------------ المفتاح مطفأ


async def test_flag_off_keeps_every_path_as_today(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**مطفأً**: الطريقةُ تُتجاهل، ولا صفَّ يولد، والكاشُ بلا نزاع، والقوائمُ فارغة — **كما اليوم حرفاً**."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    requested, completed = await completed_with(client, rider["headers"], driver, "cash")

    assert requested["payment_method_hint"] is None
    assert completed["payment_method_hint"] is None
    assert await rows_of(session_factory, completed["id"]) == []

    # والمسارُ القائمُ يعمل كما كان، والكاشُ لا يُنازَع
    paid = await pay_ride(client, rider["headers"], completed["id"], "cash")
    assert paid.status_code == 201, paid.text
    payment = paid.json()["payments"][0]
    disputed = await client.post(
        f"/payments/{payment['id']}/dispute", json={"reason": "تجربة"}, headers=driver["headers"]
    )
    assert disputed.status_code == 409
    assert disputed.json()["code"] == "invalid_payment_transition"

    mine = await client.get("/payments/me/unconfirmed", headers=rider["headers"])
    assert mine.json() == {"blocked": False, "items": []}
    declared = await client.post(f"/payments/{payment['id']}/declare", headers=rider["headers"])
    assert declared.status_code == 403
    assert declared.json()["code"] == "feature_disabled"

    async with session_factory() as session:
        assert driver["driver_id"] in await dispatch.eligible_driver_ids(
            session, [driver["driver_id"]], VehicleCategory.ECONOMY
        )


# --------------------------------------------------- ١) الصفُّ يولد مع النهاية


async def test_cash_hint_opens_a_pending_row_at_completion_and_writes_nothing(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    before = await ledger_count(session_factory)

    requested, completed = await completed_with(client, rider["headers"], driver, "cash")

    assert requested["payment_method_hint"] == "cash"
    rows = await rows_of(session_factory, completed["id"])
    assert [(row.method.value, row.status.value, str(row.amount)) for row in rows] == [
        ("cash", "pending", EXPECTED_FARE)
    ]
    assert rows[0].idempotency_key == f"hint:{completed['id']}"
    # **لا قيدَ معه** (§٨)
    assert await ledger_count(session_factory) == before

    state = await payments_of(client, rider["headers"], completed["id"])
    assert state["outstanding"] == "0.000"
    assert state["settlement"] == "awaiting"
    # ولا يُفتح صفٌّ ثانٍ من شاشة الدفع — الراكبُ يبدّل الطريقةَ إن أراد
    again = await pay_ride(client, rider["headers"], completed["id"], "cash", key="pay-key-0002")
    assert again.status_code == 409
    assert again.json()["code"] == "ride_already_paid"


async def test_cliq_hint_opens_with_the_frozen_alias_only_when_the_captain_has_one(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG, "cliq_enabled")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)

    # بلا اسمٍ مستعارٍ لا وجهةَ لحوالة — **لا شيءَ كما اليوم**
    _requested, bare = await completed_with(client, rider["headers"], driver, "cliq")
    assert await rows_of(session_factory, bare["id"]) == []

    await set_cliq_alias(session_factory, driver["driver_id"], "ZAID.JO")
    paid = await pay_ride(client, rider["headers"], bare["id"], "cash")
    assert paid.status_code == 201, paid.text
    _requested, ride = await completed_with(client, rider["headers"], driver, "cliq")
    rows = await rows_of(session_factory, ride["id"])
    assert [(row.method.value, row.status.value, row.cliq_alias) for row in rows] == [
        ("cliq", "pending", "ZAID.JO")
    ]
    assert rows[0].cliq_reference is not None


async def test_wallet_and_card_hints_stay_as_today(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    requested, ride = await completed_with(client, rider["headers"], driver, "wallet")
    assert requested["payment_method_hint"] == "wallet"
    assert await rows_of(session_factory, ride["id"]) == []

    # **وطريقةٌ لا يختارها راكبٌ تُرفض**، وقناةٌ مطفأةٌ في السوق كذلك
    refused = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", "payment_method": "promo"},
        headers=rider["headers"],
    )
    assert refused.status_code == 422
    card = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", "payment_method": "card"},
        headers=rider["headers"],
    )
    assert card.status_code == 403
    assert card.json()["code"] == "feature_disabled"


async def test_declaring_cash_is_idempotent_and_writes_no_money(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    before = await ledger_count(session_factory)

    first = await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])
    assert first.status_code == 200, first.text
    declared_at = first.json()["payments"][0]["declared_at"]
    assert declared_at is not None
    second = await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])
    assert second.status_code == 200
    assert second.json()["payments"][0]["declared_at"] == declared_at
    assert await ledger_count(session_factory) == before

    # الكبتنُ لا يُقرّ عن الراكب، وغيرُ صاحبها لا يرى أنها موجودة
    stranger = await _rider(client, OTHER_RIDER)
    assert (
        await client.post(f"/payments/{payment.id}/declare", headers=stranger["headers"])
    ).status_code == 404

    mine = (await client.get("/payments/me/unconfirmed", headers=rider["headers"])).json()
    assert [item["state"] for item in mine["items"]] == ["awaiting_captain"]
    assert mine["items"][0]["captain_name"] == "كبتن الرحلات"
    awaiting = (
        await client.get("/drivers/me/payments/unconfirmed", headers=driver["headers"])
    ).json()
    assert [(item["state"], item["rider_first_name"], item["amount"]) for item in awaiting["items"]] == [
        ("awaiting_you", "راكب", EXPECTED_FARE)
    ]
    assert awaiting["items"][0]["declared_at"] is not None


async def _request(client: AsyncClient, headers: dict):
    return await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=headers,
    )


async def test_change_method_voids_and_reopens_in_one_step_and_the_block_stays(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**«يُلغى المعلَّقُ ويُنشأ غيرُه»** (§٢-١) في خطوةٍ واحدة — **فلا يرفع الراكبُ منعَه بضغطةٍ ولا يدفع** (مراجعةُ ٢٠٢٦-١٠-٠٧).

    كان التبديلُ يُلغي ولا يُنشئ: ٤٠٢ ← تبديل ← ٢٠١ بلا دفع، والرحلةُ خرجت من كلِّ قائمة، و«لم يدفع» من يد الكبتن.
    """
    await enable_features(session_factory, FLAG, "cliq_enabled")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    await set_cliq_alias(session_factory, driver["driver_id"], "ZAID.JO")
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    await shift_ride(session_factory, ride["id"], minutes=31)
    assert (await _request(client, rider["headers"])).status_code == 402

    # **دفعٌ جديدٌ سقط ⇒ لا إلغاء**: لا رصيدَ في المحفظة، والصفُّ القديمُ على حاله والمنعُ قائم
    broke = await client.post(
        f"/payments/{payment.id}/change-method",
        json={"method": "wallet", "idempotency_key": "change-key-0001"},
        headers=rider["headers"],
    )
    assert broke.status_code >= 400, broke.text
    assert [row.status.value for row in await rows_of(session_factory, ride["id"])] == ["pending"]
    # **والطريقةُ نفسُها لا تُبدِّل شيئاً**
    same = await client.post(
        f"/payments/{payment.id}/change-method",
        json={"method": "cash", "idempotency_key": "change-key-0002"},
        headers=rider["headers"],
    )
    assert same.status_code == 422, same.text

    changed = await client.post(
        f"/payments/{payment.id}/change-method",
        json={"method": "cliq", "idempotency_key": "change-key-0003"},
        headers=rider["headers"],
    )
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert [(row["method"], row["status"]) for row in body["payments"]] == [
        ("cash", "voided"),
        ("cliq", "pending"),
    ]
    assert body["payments"][0]["voided_at"] is not None
    assert body["outstanding"] == "0.000"
    # **الضغطةُ الثانيةُ بالمفتاح نفسِه تعيد الحال** — لا خطأ ولا صفٌّ ثالث
    again = await client.post(
        f"/payments/{payment.id}/change-method",
        json={"method": "cliq", "idempotency_key": "change-key-0003"},
        headers=rider["headers"],
    )
    assert again.status_code == 200, again.text
    assert len(await rows_of(session_factory, ride["id"])) == 2

    # **والمنعُ قائمٌ على الصفِّ الجديد** حتى يُدخل مرجعَه — ثمّ يُرفع
    cliq = (await rows_of(session_factory, ride["id"]))[1]
    still = await _request(client, rider["headers"])
    assert still.status_code == 402, still.text
    assert still.json()["payment_id"] == str(cliq.id)
    mine = (await client.get("/payments/me/unconfirmed", headers=rider["headers"])).json()
    assert [(item["method"], item["state"]) for item in mine["items"]] == [("cliq", "awaiting_you")]
    referenced = await client.post(
        f"/payments/{cliq.id}/cliq-reference",
        json={"transfer_reference": "FT24100001"},
        headers=rider["headers"],
    )
    assert referenced.status_code == 200, referenced.text
    assert (await _request(client, rider["headers"])).status_code == 201

    # وما أُدخل مرجعُه لا يُبدَّل
    refused = await client.post(
        f"/payments/{cliq.id}/change-method",
        json={"method": "cash", "idempotency_key": "change-key-0004"},
        headers=rider["headers"],
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "invalid_payment_transition"


async def test_pay_now_on_a_cash_dispute_voids_it_and_opens_the_new_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**«سأدفع الآن»** بعد «لم يدفع» (§٢-٣/§٦) — يُلغى المتنازَعُ عليه ويُفتح ما يدفع به، **ولو كاشاً ثانيةً**. ولا قيد."""
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    disputed = await client.post(
        f"/payments/{payment.id}/dispute", json={"reason": "نزل بلا أن يدفع"}, headers=driver["headers"]
    )
    assert disputed.status_code == 200, disputed.text
    before = await ledger_count(session_factory)

    paid_now = await client.post(
        f"/payments/{payment.id}/change-method",
        json={"method": "cash", "idempotency_key": "pay-now-0001"},
        headers=rider["headers"],
    )
    assert paid_now.status_code == 200, paid_now.text
    assert [(row["method"], row["status"]) for row in paid_now.json()["payments"]] == [
        ("cash", "voided"),
        ("cash", "pending"),
    ]
    assert await ledger_count(session_factory) == before
    # **والكبتنُ يؤكّد الجديدَ بيده** كما يؤكّد أيَّ كاش
    fresh = (await rows_of(session_factory, ride["id"]))[1]
    confirmed = await client.post(f"/payments/{fresh.id}/confirm", headers=driver["headers"])
    assert confirmed.status_code == 200, confirmed.text


async def test_captain_can_say_unpaid_on_cash_and_the_rider_is_asked(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]

    disputed = await client.post(
        f"/payments/{payment.id}/dispute",
        json={"reason": "نزل بلا أن يدفع"},
        headers=driver["headers"],
    )
    assert disputed.status_code == 200, disputed.text
    assert disputed.json()["status"] == "disputed"

    async with session_factory() as session:
        asked = (
            await session.scalars(
                select(UserNotification).where(
                    UserNotification.user_id == uuid.UUID(rider["user_id"]),
                    UserNotification.kind == service.DISPUTED_KIND,
                )
            )
        ).all()
    assert [row.title for row in asked] == ["الكبتنُ يقول إنه لم يستلم المبلغ"]
    assert set(asked[0].data) == {"type", "payment_id", "ride_id"}

    # **والراكبُ يردّ «سلّمتُه»** — يُختم إقرارُه ولا تتغيّر الحال
    told = await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])
    assert told.status_code == 200
    assert told.json()["payments"][0]["status"] == "disputed"


# ------------------------------------------------------------------ ٢) التذكيرات


async def test_reminders_follow_the_schedule_once_each_with_the_design_texts(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    async with session_factory() as session:
        ended = (await session.get(Ride, payment.ride_id)).completed_at

    async def at(minutes: int) -> list:
        async with session_factory() as session:
            notices = await service.remind_one(
                session, payment.id, now=ended + timedelta(minutes=minutes)
            )
            await session.commit()
        return [(notice.user_id, notice.title, notice.body) for notice in notices]

    captain = driver["user_id"]
    assert await at(5) == []
    first = await at(10)
    assert {(str(user), title, body) for user, title, body in first} == {
        (captain, "رحلةُ راكب بانتظار تأكيدك", "استلمتَ 8.000 د.أ؟"),
        (rider["user_id"], "سلّمتَ الكبتن 8.000 د.أ؟", "أكّد ذلك كي تُغلق الرحلة"),
    }
    # **لا يتكرّر**: الموعدُ مختومٌ على الصفّ
    assert await at(11) == []
    assert len(await at(121)) == 2
    third = await at(721)
    assert {(title, body) for _user, title, body in third} == {
        ("تأكيدٌ ينتظرك منذ 12 ساعة", "تُوقَف الطلباتُ الجديدةُ عند 24 ساعة"),
        ("دفعُ رحلتك غيرُ مؤكَّد", "لا يمكن طلبُ رحلةٍ جديدةٍ حتى يُحسم"),
    }
    fourth = await at(1381)
    assert {title for _user, title, _body in fourth} == {
        "بعد ساعةٍ تُحال الدفعةُ إلى فريق TAXO",
        "بعد ساعةٍ تُحال رحلتُك إلى فريق TAXO",
    }
    assert await at(2000) == []
    async with session_factory() as session:
        row = await session.get(Payment, payment.id)
        assert (row.driver_reminders, row.rider_reminders) == (4, 4)


async def shift_declaration(session_factory, payment_id: uuid.UUID, *, minutes: int) -> None:
    """يُرجع إقرارَ الراكب إلى الوراء — **ساعةُ الكبتن تبدأ منه** (`_captain_start`)."""
    async with session_factory() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(declared_at=Payment.declared_at - timedelta(minutes=minutes))
        )
        await session.commit()


async def test_a_late_sweep_sends_only_the_latest_due_reminder_and_counts_one(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**كنسٌ توقّف لا يرسل ثلاثةً دفعةً واحدة** — آخرُ مستحقٍّ وحدَه. **والعدّادُ عددُ ما أُرسل حقاً (١) لا مؤشّرُ الموعد (٣)**
    (مراجعةُ ٢٠٢٦-١٠-٠٧: كان يُختم ٣ فيُقرأ «تذكيراتٌ وصلته» لم تصل). **ومن أقرّ لا يُذكَّر**."""
    from app.tasks.unconfirmed_payments import remind_payment

    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])
    await shift_ride(session_factory, ride["id"], minutes=800)
    await shift_declaration(session_factory, payment.id, minutes=800)

    assert await remind_payment(payment.id) == 1
    assert await remind_payment(payment.id) == 0
    async with session_factory() as session:
        row = await session.get(Payment, payment.id)
        assert (row.driver_reminders, row.rider_reminders) == (1, 0)
        sent = (
            await session.scalars(
                select(UserNotification).where(UserNotification.kind == service.REMINDER_KIND)
            )
        ).all()
    assert [(str(item.user_id), item.title) for item in sent] == [
        (driver["user_id"], "تأكيدٌ ينتظرك منذ 12 ساعة")
    ]
    assert set(sent[0].data) == {"type", "payment_id", "ride_id"}


# ------------------------------------------------------------------ ٣) الحدود


async def test_a_rider_who_has_not_declared_cannot_request_after_thirty_minutes(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]

    async with session_factory() as session:
        user = await session.get(service.User, uuid.UUID(rider["user_id"]))
        assert await service.rider_blocking_payment(session, user) is None
    await shift_ride(session_factory, ride["id"], minutes=31)

    blocked = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=rider["headers"],
    )
    assert blocked.status_code == 402
    assert blocked.json()["code"] == "unconfirmed_payment_blocked"
    assert blocked.json()["message"] == "لا يمكن طلبُ رحلةٍ جديدةٍ حتى يُحسم دفعُ هذه الرحلة"
    assert blocked.json()["payment_id"] == str(payment.id)
    mine = (await client.get("/payments/me/unconfirmed", headers=rider["headers"])).json()
    assert mine["blocked"] is True and mine["items"][0]["blocks_requests"] is True

    # **يُرفع فور الإقرار** — وما ينتظر الكبتنَ لا يمنع الراكب
    await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])
    allowed = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=rider["headers"],
    )
    assert allowed.status_code == 201, allowed.text


async def test_a_captain_is_blocked_at_three_awaiting_and_released_the_moment_he_confirms(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)

    async def eligible() -> bool:
        async with session_factory() as session:
            return driver["driver_id"] in await dispatch.eligible_driver_ids(
                session, [driver["driver_id"]], VehicleCategory.ECONOMY
            )

    rides = []
    for _ in range(3):
        assert await eligible()
        rides.append((await completed_with(client, rider["headers"], driver, "cash"))[1])

    assert not await eligible()
    view = (await client.get("/drivers/me/payments/unconfirmed", headers=driver["headers"])).json()
    assert view["blocked"] is True
    assert (view["block_count"], view["block_hours"]) == (3, 24)
    assert len(view["items"]) == 3

    first = (await rows_of(session_factory, rides[0]["id"]))[0]
    confirmed = await client.post(f"/payments/{first.id}/confirm", headers=driver["headers"])
    assert confirmed.status_code == 200, confirmed.text
    assert await eligible(), "**يُرفع فور الحسم** — لا بعد دورة"


async def test_the_oldest_over_a_day_blocks_and_an_open_dispute_blocks_nobody(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    await shift_ride(session_factory, ride["id"], minutes=25 * 60)

    async with session_factory() as session:
        assert driver["driver_id"] not in await dispatch.eligible_driver_ids(
            session, [driver["driver_id"]], VehicleCategory.ECONOMY
        )
    disputed = await client.post(
        f"/payments/{payment.id}/dispute", json={"reason": "لم يدفع"}, headers=driver["headers"]
    )
    assert disputed.status_code == 200
    async with session_factory() as session:
        assert driver["driver_id"] in await dispatch.eligible_driver_ids(
            session, [driver["driver_id"]], VehicleCategory.ECONOMY
        )
        user = await session.get(service.User, uuid.UUID(rider["user_id"]))
        assert await service.rider_blocking_payment(session, user) is None


async def test_two_unpaid_rulings_turn_cash_off_for_the_rider(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    first = (await rows_of(session_factory, ride["id"]))[0]
    now = datetime.now(first.created_at.tzinfo)
    async with session_factory() as session:
        for _ in range(2):
            session.add(
                Payment(
                    ride_id=first.ride_id,
                    method=first.method,
                    amount=Decimal("1.000"),
                    currency=first.currency,
                    status=PaymentStatus.FAILED,
                    resolution=DisputeResolution.UNPAID,
                    resolved_at=now,
                )
            )
        await session.commit()

    refused = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", "payment_method": "cash"},
        headers=rider["headers"],
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "cash_channel_off"


# ------------------------------------------------------------------ ٤) الطابور


async def test_admin_queue_lists_oldest_first_and_its_actions_carry_a_reason(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    await set_commission(session_factory, "10")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _r, older = await completed_with(client, rider["headers"], driver, "cash")
    _r, newer = await completed_with(client, rider["headers"], driver, "cash")
    await shift_ride(session_factory, older["id"], minutes=26 * 60)
    old_payment = (await rows_of(session_factory, older["id"]))[0]
    new_payment = (await rows_of(session_factory, newer["id"]))[0]

    reminded = await client.post(
        f"/admin/payments/unconfirmed/{old_payment.id}/remind",
        json={"reason": "تذكير يدوي من المشرف"},
        headers=admin_headers,
    )
    assert reminded.status_code == 200, reminded.text
    assert sorted(reminded.json()["sent_to"]) == ["captain", "rider"]

    listed = await client.get("/admin/payments/unconfirmed", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert [row["payment_id"] for row in rows] == [str(old_payment.id), str(new_payment.id)]
    head = rows[0]
    assert head["state"] == "awaiting_rider"
    assert head["age_minutes"] >= 26 * 60
    assert head["rider"]["pending_count"] == 2 and head["driver"]["pending_count"] == 2
    assert head["rider"]["phone_masked"] != head["rider"].get("phone")
    assert "1111" not in head["rider"]["phone_masked"]
    assert sorted(stamp["to"] for stamp in head["reminder_trail"]) == ["captain", "rider"]
    # **مواعيدُ الجدول لم تتحرّك**
    assert head["driver_reminders"] == 0

    short = await client.post(
        f"/admin/payments/unconfirmed/{old_payment.id}/resolve",
        json={"outcome": "paid", "reason": "قصير"},
        headers=admin_headers,
    )
    assert short.status_code == 422

    paid = await client.post(
        f"/admin/payments/unconfirmed/{old_payment.id}/resolve",
        json={"outcome": "paid", "reason": "اتصلنا بالكبتن وأكّد الاستلام"},
        headers=admin_headers,
    )
    assert paid.status_code == 200, paid.text
    assert (paid.json()["status"], paid.json()["confirmed_by"]) == ("confirmed", "admin")
    # **ما يكتبه التأكيدُ حرفاً**: دَينُ العمولة
    assert await effects(session_factory, old_payment.id, old_payment.ride_id) == [
        ("debt", "ride_commission", str(COMMISSION), "outstanding")
    ]

    before = await ledger_count(session_factory)
    unpaid = await client.post(
        f"/admin/payments/unconfirmed/{new_payment.id}/resolve",
        json={"outcome": "unpaid", "reason": "لم يثبت أن الراكب دفع"},
        headers=admin_headers,
    )
    assert unpaid.status_code == 200, unpaid.text
    assert unpaid.json()["status"] == "failed"
    assert await ledger_count(session_factory) == before
    assert await effects(session_factory, new_payment.id, new_payment.ride_id) == []
    state = await payments_of(client, rider["headers"], newer["id"])
    assert state["outstanding"] == EXPECTED_FARE

    async with session_factory() as session:
        audits = (
            await session.scalars(
                select(AdminAuditLog).where(AdminAuditLog.entity_type == "payment").order_by(AdminAuditLog.created_at)
            )
        ).all()
    assert [entry.details["action"] for entry in audits] == ["remind", "resolve", "resolve"]
    assert audits[1].details["reason"] == "اتصلنا بالكبتن وأكّد الاستلام"


async def test_admin_can_turn_a_pending_payment_into_a_dispute(
    client: AsyncClient, support_headers: dict, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _r, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]

    disputed = await client.post(
        f"/admin/payments/unconfirmed/{payment.id}/dispute",
        json={"reason": "تعارض بين روايتي الطرفين"},
        headers=support_headers,
    )
    assert disputed.status_code == 200, disputed.text
    assert disputed.json()["status"] == "disputed"
    rows = (await client.get("/admin/payments/unconfirmed", headers=support_headers)).json()
    assert [row["state"] for row in rows] == ["disputed"]
    async with session_factory() as session:
        asked = (
            await session.scalars(
                select(UserNotification.user_id).where(UserNotification.kind == service.DISPUTED_KIND)
            )
        ).all()
    assert {str(user) for user in asked} == {rider["user_id"], driver["user_id"]}


# ------------------------------------------------------- ٥) الإتمامُ الآليُّ للكاش


async def _declared_due(client, session_factory, rider, driver) -> tuple[dict, Payment]:
    """كاشٌ أقرّ به الراكبُ قبل خمسٍ وعشرين ساعة، **وأربعةُ تذكيراتٍ وصلت الكبتن بعد إقراره آخرُها الإنذار** في موعده
    (الإقرار + ٢٣ س) — **وقد مضت بعده الساعةُ التي وعد بها**."""
    _r, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    declared = await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])
    assert declared.status_code == 200
    async with session_factory() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment.id)
            .values(
                declared_at=Payment.declared_at - timedelta(hours=25),
                driver_reminders=4,
                driver_reminded_at=Payment.declared_at - timedelta(hours=2),
            )
        )
        await session.commit()
    return ride, payment


async def test_auto_confirm_needs_every_condition_and_writes_what_confirm_writes(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    from app.tasks.unconfirmed_payments import auto_confirm_payment

    await enable_features(session_factory, FLAG)
    await set_commission(session_factory, "10")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride, payment = await _declared_due(client, session_factory, rider, driver)

    # **مفتاحُه المستقلُّ مطفأ** ⇒ لا شيء
    assert await auto_confirm_payment(payment.id) is False
    await enable_features(session_factory, AUTO_FLAG)

    # **أقلُّ من أربعة تذكيرات** ⇒ لا شيء
    async with session_factory() as session:
        await session.execute(update(Payment).where(Payment.id == payment.id).values(driver_reminders=3))
        await session.commit()
    assert await auto_confirm_payment(payment.id) is False
    # **فوق السقف** ⇒ لا شيء
    async with session_factory() as session:
        await session.execute(update(Payment).where(Payment.id == payment.id).values(driver_reminders=4))
        session.add(PaymentSetting(country_code=CountryCode.JO, cash_auto_confirm_max_amount=Decimal("5.000")))
        await session.commit()
    assert await auto_confirm_payment(payment.id) is False
    async with session_factory() as session:
        await session.execute(
            update(PaymentSetting).values(cash_auto_confirm_max_amount=Decimal("20.000"))
        )
        await session.commit()

    assert await auto_confirm_payment(payment.id) is True
    async with session_factory() as session:
        row = await session.get(Payment, payment.id)
    assert (row.status.value, row.confirmed_by.value) == ("confirmed", "auto_rule")
    criteria = row.auto_confirm_criteria
    assert (criteria["hours"], criteria["max_amount"], criteria["reminders_sent"]) == (24, "20.000", 4)
    assert criteria["objection_window_hours"] == 72

    # **ما يكتبه «استلمت» حرفاً** — رحلةٌ ثانيةٌ يؤكّدها الكبتنُ بيده، والأثران متطابقان
    _r, manual_ride = await completed_with(client, rider["headers"], driver, "cash")
    manual = (await rows_of(session_factory, manual_ride["id"]))[0]
    assert (await client.post(f"/payments/{manual.id}/confirm", headers=driver["headers"])).status_code == 200
    assert await effects(session_factory, payment.id, payment.ride_id) == await effects(
        session_factory, manual.id, manual.ride_id
    ) == [("debt", "ride_commission", str(COMMISSION), "outstanding")]

    # والكبتنُ يُخبَر بنافذة اعتراضه
    async with session_factory() as session:
        told = (
            await session.scalars(
                select(UserNotification.title).where(UserNotification.kind == service.AUTO_CONFIRMED_KIND)
            )
        ).all()
    assert told == ["عُدّ مبلغُ رحلة راكب مستلَماً"]


async def test_auto_confirm_is_refused_to_a_rider_with_an_unpaid_ruling(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG, AUTO_FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride, payment = await _declared_due(client, session_factory, rider, driver)
    async with session_factory() as session:
        session.add(
            Payment(
                ride_id=payment.ride_id,
                method=payment.method,
                amount=Decimal("1.000"),
                currency=payment.currency,
                status=PaymentStatus.FAILED,
                resolution=DisputeResolution.UNPAID,
                resolved_at=datetime.now(payment.created_at.tzinfo),
            )
        )
        await session.commit()
        assert await service.auto_confirm_one(session, payment.id) is None


async def test_the_captain_objects_within_the_window_and_no_entry_is_reversed(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    from app.tasks.unconfirmed_payments import auto_confirm_payment

    await enable_features(session_factory, FLAG, AUTO_FLAG)
    await set_commission(session_factory, "10")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _ride, payment = await _declared_due(client, session_factory, rider, driver)
    assert await auto_confirm_payment(payment.id) is True

    view = (await client.get("/drivers/me/payments/unconfirmed", headers=driver["headers"])).json()
    assert [item["state"] for item in view["items"]] == ["auto_confirmed"]
    assert view["items"][0]["objection_deadline"] is not None
    before = await effects(session_factory, payment.id, payment.ride_id)

    objected = await client.post(
        f"/payments/{payment.id}/object", json={"reason": "لم أستلم شيئاً"}, headers=driver["headers"]
    )
    assert objected.status_code == 200, objected.text
    assert objected.json()["status"] == "confirmed" and objected.json()["objected_at"] is not None
    again = await client.post(
        f"/payments/{payment.id}/object", json={"reason": "مرة أخرى"}, headers=driver["headers"]
    )
    assert again.status_code == 409
    assert await effects(session_factory, payment.id, payment.ride_id) == before

    rows = (await client.get("/admin/payments/unconfirmed", headers=admin_headers)).json()
    assert [row["state"] for row in rows] == ["auto_confirmed_objected"]
    pending_entry = await client.post(
        f"/admin/payments/unconfirmed/{payment.id}/resolve",
        json={"outcome": "unpaid", "reason": "الكبتن لم يستلم المبلغ"},
        headers=admin_headers,
    )
    assert pending_entry.status_code == 501
    assert pending_entry.json()["code"] == "objection_counter_entry_pending"
    upheld = await client.post(
        f"/admin/payments/unconfirmed/{payment.id}/resolve",
        json={"outcome": "paid", "reason": "الراكب أثبت التسليم بشاهد"},
        headers=admin_headers,
    )
    assert upheld.status_code == 200, upheld.text
    assert upheld.json()["resolution"] == "paid"
    assert await effects(session_factory, payment.id, payment.ride_id) == before
    assert (await client.get("/admin/payments/unconfirmed", headers=admin_headers)).json() == []


async def test_an_objection_after_the_window_is_refused(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    from app.tasks.unconfirmed_payments import auto_confirm_payment

    await enable_features(session_factory, FLAG, AUTO_FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _ride, payment = await _declared_due(client, session_factory, rider, driver)
    assert await auto_confirm_payment(payment.id) is True
    async with session_factory() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment.id)
            .values(confirmed_at=Payment.confirmed_at - timedelta(hours=73))
        )
        await session.commit()
    late = await client.post(
        f"/payments/{payment.id}/object", json={"reason": "متأخر"}, headers=driver["headers"]
    )
    assert late.status_code == 409
    assert late.json()["code"] == "objection_window_closed"


async def test_auto_confirm_waits_for_four_reminders_after_the_declaration_ending_with_the_warning(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**§٢-٥/٢ بحرفه** (مراجعةُ ٢٠٢٦-١٠-٠٧): «لم يعترض خلال ٢٤ ساعة **من الإقرار** رغم **أربعة تذكيرات وصلته**».

    - **إقرارٌ متأخّر**: الكبتنُ ذُكِّر حتى الرابع قبل أن يُقِرّ الراكب — **فلا يُحتسب منها شيء**، ولا إتمامَ بعد ٢٥ ساعة.
    - **ساعتُه تبدأ من الإقرار** والتذكيرُ الرابعُ هو الإنذار: «بعد ساعةٍ يُعدّ المبلغُ مستلَماً».
    - **إنذارٌ تأخّر كنسُه لا يُقصِّر ما وعد به**: الإتمامُ بعده بساعةٍ لا قبلها.
    - **وكنسٌ متأخّرٌ أرسل الإنذارَ وحدَه**: تذكيرٌ واحدٌ لا أربعة ⇒ لا إتمامَ أبداً — للطابور.
    """
    from app.tasks.unconfirmed_payments import remind_payment

    await enable_features(session_factory, FLAG, AUTO_FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _r, ride = await completed_with(client, rider["headers"], driver, "cash")
    _r, other = await completed_with(client, rider["headers"], driver, "cash")
    late = (await rows_of(session_factory, ride["id"]))[0]
    swept_late = (await rows_of(session_factory, other["id"]))[0]

    await shift_ride(session_factory, ride["id"], minutes=1386)
    assert await remind_payment(late.id) == 2  # الكبتنُ والراكبُ — الموعدُ الرابعُ قبل الإقرار
    for payment in (late, swept_late):
        declared = await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])
        assert declared.status_code == 200, declared.text

    async def stamps(payment_id: uuid.UUID) -> Payment:
        async with session_factory() as session:
            return await session.get(Payment, payment_id)

    async def remind(payment_id: uuid.UUID, minutes: int) -> list[str]:
        declared_at = (await stamps(payment_id)).declared_at
        async with session_factory() as session:
            notices = await service.remind_one(
                session, payment_id, now=declared_at + timedelta(minutes=minutes)
            )
            await session.commit()
        return [notice.title for notice in notices]

    async def auto(payment_id: uuid.UUID, minutes: int) -> Payment | None:
        declared_at = (await stamps(payment_id)).declared_at
        async with session_factory() as session:
            outcome = await service.auto_confirm_one(
                session, payment_id, now=declared_at + timedelta(minutes=minutes)
            )
            await session.commit()
            return outcome

    assert (await stamps(late.id)).driver_reminders == 0, "**العدّادُ يُصفَّر بالإقرار**"
    assert await auto(late.id, 25 * 60) is None

    assert await remind(late.id, 10) == ["رحلةُ راكب بانتظار تأكيدك"]
    assert len(await remind(late.id, 120)) == 1
    assert len(await remind(late.id, 720)) == 1
    # **الإنذارُ تأخّر خمسين دقيقة** (كنسٌ متعثّر) — ونصُّه يَعِد بساعة
    assert await remind(late.id, 1430) == ["بعد ساعةٍ يُعدّ المبلغُ مستلَماً كما أقرّ الراكب"]
    assert await auto(late.id, 1441) is None, "**ساعةُ الإنذار لم تمضِ** — ولو مضت ٢٤ ساعةً من الإقرار"
    confirmed = await auto(late.id, 1491)
    assert confirmed is not None
    criteria = (await stamps(late.id)).auto_confirm_criteria
    assert (criteria["reminders_sent"], criteria["warning_lead_minutes"]) == (4, 60)

    # **كنسٌ لم يدُر إلا عند الإنذار** ⇒ تذكيرٌ واحد ⇒ لا إتمام، ولا يُعاد ما فات
    assert len(await remind(swept_late.id, 1380)) == 1
    assert await remind(swept_late.id, 1400) == []
    assert (await stamps(swept_late.id)).driver_reminders == 1
    assert await auto(swept_late.id, 48 * 60) is None


# ------------------------------------------------- الحدودُ بعد المراجعة (§٧)


async def test_cash_off_is_enforced_on_the_doors_that_open_cash(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """**إطفاءُ الكاش يُفرض حيث يُفتح الكاش** (§٧، مراجعةُ ٢٠٢٦-١٠-٠٧) — لا على الطريقة المرسلة مع الطلب وحدَها.

    كان راكبٌ بحكمين يُردّ إن أرسل «كاش» مع الطلب، **ثمّ يدفع نقداً بعد الرحلة** — أو يرسل غيرَه، أو لا يرسل شيئاً (تطبيقٌ
    قديم). والآن: `POST /rides/{id}/payments` نقداً ⇒ ٤٠٩، **وباقي المحفظة لا يصير كاشاً**.
    """
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _r, ride = await completed_with(client, rider["headers"], driver, None)
    async with session_factory() as session:
        for _ in range(2):
            session.add(
                Payment(
                    ride_id=uuid.UUID(ride["id"]),
                    method=PaymentMethod.CASH,
                    amount=Decimal("1.000"),
                    currency=Currency.JOD,
                    status=PaymentStatus.FAILED,
                    resolution=DisputeResolution.UNPAID,
                    resolved_at=datetime.now(UTC),
                )
            )
        await session.commit()

    cash = await pay_ride(client, rider["headers"], ride["id"], "cash", key="cash-off-0001")
    assert cash.status_code == 409, cash.text
    assert cash.json()["code"] == "cash_channel_off"

    await topup_wallet(client, admin_headers, rider["user_id"], "3.000")
    partial = await pay_ride(client, rider["headers"], ride["id"], "wallet", key="cash-off-0002")
    assert partial.status_code == 409, partial.text
    assert partial.json()["code"] == "insufficient_balance"
    assert [row.status.value for row in await rows_of(session_factory, ride["id"])] == [
        "failed",
        "failed",
    ]


async def test_an_unpaid_ruling_keeps_the_rider_blocked_until_he_pays(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**«حكمُ "لم يدفع" ⇒ لا طلبَ جديدَ حتى يُسدَّد»** (§٧) — كان الحكمُ يرفع المنعَ لأن الصفَّ صار `failed` فخرج من كلِّ شرط."""
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _r, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    await shift_ride(session_factory, ride["id"], minutes=31)

    ruled = await client.post(
        f"/admin/payments/unconfirmed/{payment.id}/resolve",
        json={"outcome": "unpaid", "reason": "لم يثبت أن الراكب دفع"},
        headers=admin_headers,
    )
    assert ruled.status_code == 200, ruled.text

    blocked = await _request(client, rider["headers"])
    assert blocked.status_code == 402, blocked.text
    assert (blocked.json()["payment_id"], blocked.json()["ride_id"]) == (None, ride["id"])
    mine = (await client.get("/payments/me/unconfirmed", headers=rider["headers"])).json()
    assert mine["blocked"] is True
    assert [
        (item["state"], item["payment_id"], item["status"], item["amount"], item["method"])
        for item in mine["items"]
    ] == [("payment_due", None, None, EXPECTED_FARE, "cash")]

    # **يدفع** — صفٌّ جديدٌ ينتظر إقرارَه، والمنعُ ينتقل إليه حتى يُقِرّ
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash", key="after-ruling-01")
    assert paid.status_code == 201, paid.text
    fresh = (await rows_of(session_factory, ride["id"]))[1]
    still = await _request(client, rider["headers"])
    assert (still.status_code, still.json().get("payment_id")) == (402, str(fresh.id))
    assert (await client.post(f"/payments/{fresh.id}/declare", headers=rider["headers"])).status_code == 200
    assert (await _request(client, rider["headers"])).status_code == 201


async def test_rows_from_before_the_flag_go_to_the_queue_only(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**حدُّ الإطلاق** (مراجعةُ ٢٠٢٦-١٠-٠٧): معلَّقٌ سبق المفتاحَ لا يمنع راكباً ولا يحجب كبتناً ولا يُذكَّر به — **والطابورُ يراه**.

    كان كلُّ معلَّقٍ قديمٍ يقرؤه كلُّ شرط: لحظةَ الإشعال يُمنع كلُّ راكبٍ عليه صفٌّ قديم، ويخرج من التوزيع كلُّ كبتنٍ أقدمُ ما
    ينتظره فوق يوم، ويصل كلَّ صفٍّ التذكيرُ الأخير.
    """
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _r, ride = await completed_with(client, rider["headers"], driver, "cash")  # المفتاحُ مطفأ: لا طريقةَ تُحفظ
    assert (await pay_ride(client, rider["headers"], ride["id"], "cash")).status_code == 201
    payment = (await rows_of(session_factory, ride["id"]))[0]
    await enable_features(session_factory, FLAG)
    await shift_ride(session_factory, ride["id"], minutes=25 * 60)

    async with session_factory() as session:
        user = await session.get(service.User, uuid.UUID(rider["user_id"]))
        assert await service.rider_blocking_payment(session, user) is None
        assert driver["driver_id"] in await dispatch.eligible_driver_ids(
            session, [driver["driver_id"]], VehicleCategory.ECONOMY
        )
        assert await service.remind_one(session, payment.id) == []
        assert await service.reminder_candidate_ids(session) == []
    assert (await client.get("/payments/me/unconfirmed", headers=rider["headers"])).json() == {
        "blocked": False,
        "items": [],
    }
    assert (
        await client.get("/drivers/me/payments/unconfirmed", headers=driver["headers"])
    ).json()["items"] == []

    rows = (await client.get("/admin/payments/unconfirmed", headers=admin_headers)).json()
    assert [(row["payment_id"], row["state"], row["in_flow"]) for row in rows] == [
        (str(payment.id), "awaiting_rider", False)
    ]


async def test_an_objection_stays_in_the_queue_after_the_flag_is_turned_off(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**الاعتراضُ لا يضيع بإطفاء المفتاح** (مراجعةُ ٢٠٢٦-١٠-٠٧): بابُه يعمل مطفأً، فالطابورُ والحكمُ كذلك."""
    from app.tasks.unconfirmed_payments import auto_confirm_payment

    await enable_features(session_factory, FLAG, AUTO_FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _ride, payment = await _declared_due(client, session_factory, rider, driver)
    assert await auto_confirm_payment(payment.id) is True
    async with session_factory() as session:
        await session.execute(
            update(FeatureFlag).where(FeatureFlag.feature_key == FLAG).values(enabled=False)
        )
        await session.commit()

    objected = await client.post(
        f"/payments/{payment.id}/object", json={"reason": "لم أستلم شيئاً"}, headers=driver["headers"]
    )
    assert objected.status_code == 200, objected.text
    rows = (await client.get("/admin/payments/unconfirmed", headers=admin_headers)).json()
    assert [row["state"] for row in rows] == ["auto_confirmed_objected"]
    upheld = await client.post(
        f"/admin/payments/unconfirmed/{payment.id}/resolve",
        json={"outcome": "paid", "reason": "الراكب أثبت التسليم بشاهد"},
        headers=admin_headers,
    )
    assert upheld.status_code == 200, upheld.text
    assert (await client.get("/admin/payments/unconfirmed", headers=admin_headers)).json() == []


async def test_one_ruling_door_the_old_one_needs_a_reason_once_the_flag_is_on(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**بابُ حكمٍ واحد** (مراجعةُ ٢٠٢٦-١٠-٠٧): نزاعُ كاشٍ في الطابور لا يُحكم من البابِ القديم بلا سبب — «٨ أحرف على الأقل» (§٥)."""
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _r, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    disputed = await client.post(
        f"/payments/{payment.id}/dispute", json={"reason": "لم يدفع"}, headers=driver["headers"]
    )
    assert disputed.status_code == 200, disputed.text

    for body in ({"resolution": "unpaid"}, {"resolution": "unpaid", "note": "قصير"}):
        refused = await client.post(
            f"/admin/payments/{payment.id}/resolve", json=body, headers=admin_headers
        )
        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "invalid_input"
    ruled = await client.post(
        f"/admin/payments/{payment.id}/resolve",
        json={"resolution": "unpaid", "note": "لم يثبت التسليم بشاهد"},
        headers=admin_headers,
    )
    assert ruled.status_code == 200, ruled.text
    assert (ruled.json()["status"], ruled.json()["resolution_note"]) == (
        "failed",
        "لم يثبت التسليم بشاهد",
    )


async def test_admin_dispute_on_cliq_asks_about_a_transfer_not_a_handover(
    client: AsyncClient, support_headers: dict, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG, "cliq_enabled")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    await set_cliq_alias(session_factory, driver["driver_id"], "ZAID.JO")
    _r, ride = await completed_with(client, rider["headers"], driver, "cliq")
    payment = (await rows_of(session_factory, ride["id"]))[0]

    disputed = await client.post(
        f"/admin/payments/unconfirmed/{payment.id}/dispute",
        json={"reason": "كليك بلا مرجع منذ يوم"},
        headers=support_headers,
    )
    assert disputed.status_code == 200, disputed.text
    async with session_factory() as session:
        asked = (
            await session.execute(
                select(UserNotification.user_id, UserNotification.body).where(
                    UserNotification.kind == service.DISPUTED_KIND
                )
            )
        ).all()
    assert {(str(user), body) for user, body in asked} == {
        (rider["user_id"], "هل حوّلتَ 8.000 د.أ؟ أدخل مرجع الحوالة أو افتح التطبيق لتردّ"),
        (driver["user_id"], "هل وصلتك حوالةُ 8.000 د.أ؟ افتح التطبيق لتردّ"),
    }


async def test_a_due_booking_of_a_blocked_rider_is_missed_and_he_is_told_why(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**الحجزُ المجدولُ لراكبٍ ممنوع** (مراجعةُ ٢٠٢٦-١٠-٠٧): كان يسقط في كلِّ دورةٍ ويُكتب في السجلّ وحدَه — **والآن `missed`
    مرّةً بإشعارٍ يقول السبب**، كمن حلَّ موعدُه وهو في رحلة."""
    from app.core.redis_client import get_redis_client
    from app.models.booking import RideBooking
    from app.services import bookings as bookings_service

    await enable_features(session_factory, FLAG, "scheduled_rides_enabled")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _r, ride = await completed_with(client, rider["headers"], driver, "cash")
    await shift_ride(session_factory, ride["id"], minutes=31)
    booked = await client.post(
        "/me/bookings",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "scheduled_at": (datetime.now(UTC) + timedelta(minutes=60)).isoformat(),
        },
        headers=rider["headers"],
    )
    assert booked.status_code == 201, booked.text
    booking_id = uuid.UUID(booked.json()["id"])
    async with session_factory() as session:
        await session.execute(
            update(RideBooking)
            .where(RideBooking.id == booking_id)
            .values(scheduled_at=datetime.now(UTC) + timedelta(minutes=1))
        )
        await session.commit()

    async with session_factory() as session:
        assert await bookings_service.execute(session, get_redis_client(), booking_id) is None
    async with session_factory() as session:
        booking = await session.get(RideBooking, booking_id)
        told = (
            await session.scalars(
                select(UserNotification.body).where(
                    UserNotification.user_id == uuid.UUID(rider["user_id"]),
                    UserNotification.kind == "booking_missed",
                )
            )
        ).all()
    assert (booking.status.value, booking.notified_at is not None) == ("missed", True)
    assert told == ["حلَّ موعدُ حجزك ودفعُ رحلةٍ سابقةٍ لم يُحسم، فلم نطلب سيارة — افتح التطبيق لتحسمه."]


# ------------------------------------------------------------------ العتبات


async def test_thresholds_are_set_from_the_admin_payment_settings_door(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    updated = await client.patch(
        "/admin/settings/payments/JO",
        json={"payment_reminder_minutes": [15, 120, 600, 1300], "driver_unconfirmed_block_count": 4,
              "cash_auto_confirm_max_amount": "15.500"},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["payment_reminder_minutes"] == [15, 120, 600, 1300]
    assert body["driver_unconfirmed_block_count"] == 4
    assert body["cash_auto_confirm_max_amount"] == "15.500"
    assert (body["rider_unconfirmed_block_minutes"], body["dispute_window_hours"]) == (30, 72)

    descending = await client.patch(
        "/admin/settings/payments/JO",
        json={"payment_reminder_minutes": [10, 5, 600, 1300]},
        headers=admin_headers,
    )
    assert descending.status_code == 422
