"""إشعاراتُ المالك بنشاط المستخدمين (SPEC §٨١) — **نوعٌ نوعٌ من بابه الحقيقيّ**، ثمّ الجمعُ والصلاحيةُ والإعدادُ والإرسالُ والخصوصيّة.

**والقياسُ بعد الالتزام** كما يقع على الإنتاج: البابُ يكتب ويلتزم، والمستمعُ يرمي الحدثَ في القائمة، **والعاملُ يقرؤها** (`drain`). فما
لم يمرّ بالالتزام لا يُرى هنا — وهو بعينه ما يُختبر في `test_a_rolled_back_write_announces_nothing`.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.redis_client import get_redis_client
from app.models.admin_alert import AdminAlert
from app.models.admin_permission import AdminPermissionGrant
from app.models.driver import Driver, DriverDocument
from app.models.enums import (
    AdminPermission,
    CountryCode,
    Currency,
    DocumentReviewStatus,
    DocumentType,
    PaymentProvider,
    PaymentStatus,
    ProviderOrderPurpose,
    ProviderOrderSource,
    ProviderOrderStatus,
    RatingRaterType,
    TopupMethod,
    UserRole,
    WalletOwnerType,
    WalletTransactionType,
    WithdrawalMethod,
    WithdrawalStatus,
)
from app.models.payment import Payment
from app.models.photo_report import UserPhotoReport
from app.models.provider_order import ProviderOrder
from app.models.rating import Rating
from app.models.ride import Ride
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.models.wallet import WalletTopupRequest, WithdrawalRequest
from app.services import admin_alerts, alert_capture, wallet
from app.services.push.mock import sent_messages
from tests.helpers import (
    DRIVER,
    RIDER,
    approved_driver,
    bring_online,
    completed_ride,
    enable_push_provider,
    pay_ride,
    register,
    request_ride,
    rider_session,
    topup_wallet,
)

BACKEND = Path(__file__).resolve().parents[1]


async def _take(session_factory, *, now: datetime | None = None) -> list[AdminAlert]:
    """**دورةُ العامل ثمّ ما كتبت** — وتُمحى بعدها فيقيس ما بعدها جديدَه وحدَه."""
    await alert_capture.settle()
    async with session_factory() as session:
        await admin_alerts.drain(session, get_redis_client(), now=now, push=False)
    async with session_factory() as session:
        rows = list(await session.scalars(select(AdminAlert).order_by(AdminAlert.created_at, AdminAlert.kind)))
        await session.execute(delete(AdminAlert))
        await session.commit()
    return rows


def _kinds(rows: list[AdminAlert]) -> list[str]:
    return sorted(row.kind for row in rows)


def _one(rows: list[AdminAlert], kind: str) -> AdminAlert:
    found = [row for row in rows if row.kind == kind]
    assert len(found) == 1, (kind, _kinds(rows))
    return found[0]


async def _receiver(session_factory, client: AsyncClient, admin_headers: dict) -> dict:
    """مشرفٌ مُنح الصلاحيةَ بالاسم — **المالكُ يملكها ولا يدخل بلا عاملٍ ثانٍ**، فيُقاس البابُ بمن مُنحها."""
    me = (await client.get("/auth/me", headers=admin_headers)).json()
    async with session_factory() as session:
        session.add(
            AdminPermissionGrant(
                user_id=uuid.UUID(me["id"]), permission=AdminPermission.ACTIVITY_ALERTS_RECEIVE, granted_by=None
            )
        )
        await session.commit()
    return me


# ═════════════════════════ الحسابات


async def test_rider_signup_is_announced_with_its_market(client: AsyncClient, rider_payload: dict, session_factory) -> None:
    body = await register(client, rider_payload)
    rows = await _take(session_factory)
    alert = _one(rows, "rider_signup")
    assert _kinds(rows) == ["rider_signup"]
    assert alert.country_code is CountryCode.JO
    assert (alert.record_type, alert.record_id) == ("rider", body["user"]["id"])
    assert alert.category == "accounts" and alert.tone == "account"


async def test_captain_signup_subscription_and_documents(client: AsyncClient, session_factory) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    rows = await _take(session_factory)
    # **حسابُ الكبتن لا يُعدّ راكباً** — يُرى من صفِّ الكبتن وحدَه، واشتراكُه مالٌ وصل
    assert _kinds(rows) == ["captain_signup", "subscription_purchased"]
    assert _one(rows, "captain_signup").record_id == str(driver["driver_id"])
    assert _one(rows, "subscription_purchased").amount is not None

    async with session_factory() as session:
        for doc_type in (DocumentType.DRIVING_LICENSE, DocumentType.NATIONAL_ID):
            session.add(
                DriverDocument(
                    driver_id=driver["driver_id"], doc_type=doc_type, file_path=f"x/{doc_type.value}.jpg",
                    content_type="image/jpeg", size_bytes=10, review_status=DocumentReviewStatus.PENDING,
                )
            )
        await session.commit()
    rows = await _take(session_factory)
    # **وثائقُ كبتنٍ واحدٍ في معاملةٍ واحدةٍ إشعارٌ واحد** بعددها
    submitted = _one(rows, "documents_submitted")
    assert submitted.data["count_docs"] == 2 and submitted.record_id == str(driver["driver_id"])

    async with session_factory() as session:
        docs = list(await session.scalars(select(DriverDocument).where(DriverDocument.driver_id == driver["driver_id"])))
        docs[0].review_status = DocumentReviewStatus.APPROVED
        await session.commit()
        docs[1].review_status = DocumentReviewStatus.REJECTED
        await session.commit()
    assert _kinds(await _take(session_factory)) == ["documents_approved", "documents_rejected"]


# ═════════════════════════ الرحلاتُ والمال


async def test_ride_lifecycle_wallet_topup_and_payment(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    await _take(session_factory)

    ride = await completed_ride(client, rider["headers"], driver)
    rows = await _take(session_factory)
    assert _kinds(rows) == ["ride_accepted", "ride_completed", "ride_requested"]
    completed = _one(rows, "ride_completed")
    assert (completed.record_type, completed.record_id) == ("ride", ride["id"])
    assert completed.currency is Currency.JOD and completed.amount is not None

    await topup_wallet(client, admin_headers, rider["user"]["id"], "50.000")
    topped = _one(await _take(session_factory), "wallet_topup")
    assert topped.amount == Decimal("50.000") and topped.record_type == "rider"

    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert paid.status_code == 201, paid.text
    payment = _one(await _take(session_factory), "payment_succeeded")
    assert payment.data["method"] == "wallet" and payment.record_id == ride["id"]
    assert payment.tone == "money_in"


async def test_a_rider_cancel_names_who_cancelled(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    rider = await rider_session(client)
    ride = await request_ride(client, rider["headers"])
    await _take(session_factory)
    cancelled = await client.post(f"/rides/{ride['id']}/cancel", json={}, headers=rider["headers"])
    assert cancelled.status_code == 200, cancelled.text
    alert = _one(await _take(session_factory), "ride_cancelled")
    assert alert.data["by"] == "rider"
    title, body = admin_alerts.tray_text(alert)
    assert "ألغاها الراكب" in body and "الأردن" in title


async def _ride_with_payment(
    client: AsyncClient, session_factory, status: PaymentStatus, method: str = "cash", *, phone: str = RIDER["phone"]
) -> tuple[Ride, Payment]:
    rider = await rider_session(client, {**RIDER, "phone": phone})
    ride_body = await request_ride(client, rider["headers"])
    async with session_factory() as session:
        ride = await session.get(Ride, uuid.UUID(ride_body["id"]))
        payment = Payment(ride_id=ride.id, method=method, amount=Decimal("4.750"), currency=Currency.JOD, status=status)
        session.add(payment)
        await session.commit()
    await _take(session_factory)
    return ride, payment


@pytest.mark.parametrize(
    ("target", "kind", "tone"),
    [
        (PaymentStatus.FAILED, "payment_failed", "problem"),
        (PaymentStatus.VOIDED, "payment_cancelled", "money_out"),
        (PaymentStatus.DISPUTED, "complaint", "problem"),
    ],
)
async def test_payment_outcomes(
    client: AsyncClient, jordan_settings: None, session_factory, target: PaymentStatus, kind: str, tone: str
) -> None:
    _ride, payment = await _ride_with_payment(client, session_factory, PaymentStatus.PENDING)
    async with session_factory() as session:
        row = await session.get(Payment, payment.id)
        row.status = target
        await session.commit()
    alert = _one(await _take(session_factory), kind)
    assert alert.tone == tone and alert.amount == Decimal("4.750")


async def test_refund_and_the_platform_paid_channels(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    _ride, payment = await _ride_with_payment(client, session_factory, PaymentStatus.CONFIRMED)
    async with session_factory() as session:
        row = await session.get(Payment, payment.id)
        row.status = PaymentStatus.REFUNDED
        await session.commit()
    assert _kinds(await _take(session_factory)) == ["refund"]

    # **خصمُ الكوبون لا يدفعه أحدٌ من جيبه** — دفعةٌ تُنشئها المنصّةُ وتؤكّدها لا تُشعِر
    ride, _payment = await _ride_with_payment(client, session_factory, PaymentStatus.PENDING, phone="+962790000095")
    async with session_factory() as session:
        session.add(Payment(ride_id=ride.id, method="promo", amount=Decimal("1.000"), currency=Currency.JOD, status=PaymentStatus.CONFIRMED))
        await session.commit()
    assert await _take(session_factory) == []


@pytest.mark.parametrize(
    ("status", "reason", "kind"),
    [
        (ProviderOrderStatus.FAILED, "declined by issuer", "payment_failed"),
        (ProviderOrderStatus.FAILED, "expired", "payment_expired"),
        (ProviderOrderStatus.CANCELLED, None, "payment_cancelled"),
    ],
)
async def test_gateway_order_outcomes(
    client: AsyncClient, session_factory, status: ProviderOrderStatus, reason: str | None, kind: str
) -> None:
    rider = await rider_session(client)
    async with session_factory() as session:
        order = ProviderOrder(
            provider=PaymentProvider.TELR, source=ProviderOrderSource.ACQUIRER, purpose=ProviderOrderPurpose.WALLET_TOPUP,
            status=ProviderOrderStatus.CREATED, cart_id=f"cart-{uuid.uuid4().hex[:10]}", user_id=uuid.UUID(rider["user"]["id"]),
            country_code=CountryCode.JO, amount=Decimal("10.000"), currency=Currency.JOD,
        )
        session.add(order)
        await session.commit()
    await _take(session_factory)
    async with session_factory() as session:
        row = await session.get(ProviderOrder, order.id)
        row.status = status
        row.failure_reason = reason
        await session.commit()
    alert = _one(await _take(session_factory), kind)
    assert alert.amount == Decimal("10.000") and alert.record_type == "rider"


async def test_withdrawals_topup_requests_adjustments_and_debt_cap(client: AsyncClient, session_factory) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    await _take(session_factory)
    async with session_factory() as session:
        request = WithdrawalRequest(driver_id=driver["driver_id"], amount=Decimal("12.000"), method=WithdrawalMethod.CLIQ, status=WithdrawalStatus.PENDING)
        topup = WalletTopupRequest(owner_id=uuid.UUID(driver["user_id"]), owner_type=WalletOwnerType.DRIVER, method=TopupMethod.CLIQ, amount=Decimal("8.000"))
        session.add_all([request, topup])
        await session.commit()
    rows = await _take(session_factory)
    assert _kinds(rows) == ["topup_requested", "withdrawal_requested"]
    assert _one(rows, "withdrawal_requested").amount == Decimal("12.000")

    async with session_factory() as session:
        row = await session.get(WithdrawalRequest, request.id)
        row.status = WithdrawalStatus.PAID
        await session.commit()
    assert _kinds(await _take(session_factory)) == ["withdrawal_paid"]

    async with session_factory() as session:
        owner = await session.get(User, uuid.UUID(driver["user_id"]))
        await wallet.record(
            session, owner=owner, owner_type=WalletOwnerType.DRIVER, tx_type=WalletTransactionType.ADJUSTMENT,
            amount=Decimal("2.000"), reference="تسوية اختبار",
        )
        await session.commit()
    assert _one(await _take(session_factory), "manual_adjustment").amount == Decimal("2.000")

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        row.debt_blocked = True
        await session.commit()
    assert _one(await _take(session_factory), "debt_cap_reached").tone == "problem"


# ═════════════════════════ الدعم


async def test_photo_reports_and_feedback(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    rider = await rider_session(client)
    ride = await request_ride(client, rider["headers"])
    rider_id = uuid.UUID(rider["user"]["id"])
    await _take(session_factory)

    async with session_factory() as session:
        session.add(UserPhotoReport(subject_id=rider_id, reported_by=rider_id, ride_id=uuid.UUID(ride["id"])))
        await session.commit()
    complaint = _one(await _take(session_factory), "complaint")
    assert complaint.data["source"] == "photo" and complaint.record_type == "photo_report"

    sent = await client.post("/feedback", data={"app": "rider", "message": "ملاحظة"}, headers=rider["headers"])
    assert sent.status_code == 201, sent.text
    feedback = _one(await _take(session_factory), "feedback")
    assert feedback.data["guest"] is False and feedback.country_code is CountryCode.JO


async def test_a_low_rating_is_announced(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    rider = await rider_session(client)
    ride = await request_ride(client, rider["headers"])
    await _take(session_factory)
    async with session_factory() as session:
        session.add(Rating(ride_id=uuid.UUID(ride["id"]), rater_type=RatingRaterType.RIDER, rater_id=uuid.UUID(rider["user"]["id"]), stars=2))
        await session.commit()
    alert = _one(await _take(session_factory), "low_rating")
    assert alert.data["stars"] == 2 and "نجمتان" in admin_alerts.tray_text(alert)[1]

    # **وثلاثُ نجومٍ فما فوق لا تُشعِر** — من الجهة الأخرى للرحلة نفسِها
    driver_side = await register(client, {**DRIVER, "phone": "+962790000096"})
    async with session_factory() as session:
        session.add(Rating(ride_id=uuid.UUID(ride["id"]), rater_type=RatingRaterType.DRIVER, rater_id=uuid.UUID(driver_side["user"]["id"]), stars=3))
        await session.commit()
    assert _kinds(await _take(session_factory)) == ["captain_signup"]


async def test_guest_feedback_is_labelled_guest(client: AsyncClient, admin_headers: dict, session_factory) -> None:
    assert (await client.put("/admin/guest-mode", json={"rider": True}, headers=admin_headers)).status_code == 200
    started = await client.post("/guest/sessions", json={"app": "rider", "device_id": "device-guest-1"})
    assert started.status_code == 201, started.text
    token = started.json()["token"]
    await _take(session_factory)
    sent = await client.post("/guest/feedback", data={"app": "rider", "message": "تجربة ضيف"}, headers={"Authorization": f"Bearer {token}"})
    assert sent.status_code == 201, sent.text
    rows = await _take(session_factory)
    # **الضيفُ لا رحلةَ له ولا مال** — ملاحظتُه وحدَها تُرى، بوسم «ضيف»
    assert _kinds(rows) == ["feedback"]
    assert rows[0].data["guest"] is True
    assert "من ضيف" in admin_alerts.tray_text(rows[0])[1]


# ═════════════════════════ الالتزامُ والجمع


async def test_a_rolled_back_write_announces_nothing(client: AsyncClient, session_factory) -> None:
    rider = await rider_session(client)
    await _take(session_factory)
    async with session_factory() as session:
        session.add(Rating(ride_id=uuid.uuid4(), rater_type=RatingRaterType.RIDER, rater_id=uuid.UUID(rider["user"]["id"]), stars=1))
        with pytest.raises(Exception):
            await session.flush()  # لا رحلةَ بهذا المعرّف — يسقط القيد
        await session.rollback()
    assert await _take(session_factory) == []


async def test_bursts_group_into_one_alert_with_a_count(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    first = await rider_session(client)
    second = await rider_session(client, {**RIDER, "phone": "+962790000099", "name": "راكب ثانٍ"})
    await _take(session_factory)
    one = await request_ride(client, first["headers"])
    await alert_capture.settle()
    async with session_factory() as session:
        await admin_alerts.drain(session, get_redis_client(), push=False)
    await request_ride(client, second["headers"])
    rows = await _take(session_factory)
    # **الثاني في نافذة الأوّل يُضمّ إليه** — صفٌّ واحدٌ بعددين، ومجموعُ الأجرتين، ويفتح القائمةَ لا رحلةً
    alert = _one(rows, "ride_requested")
    assert alert.count == 2 and alert.record_id is None and alert.data.get("grouped") is True
    assert alert.amount is not None and alert.amount > Decimal(one["estimated_fare"])
    assert admin_alerts.tray_text(alert)[0].startswith("2 طلبات رحلة")


async def test_outside_the_window_is_a_new_alert(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    first = await rider_session(client)
    second = await rider_session(client, {**RIDER, "phone": "+962790000098", "name": "راكب ثالث"})
    await _take(session_factory)
    await request_ride(client, first["headers"])
    await alert_capture.settle()
    async with session_factory() as session:
        await admin_alerts.drain(session, get_redis_client(), push=False)
        alert = await session.scalar(select(AdminAlert))
        alert.last_event_at = datetime.now(UTC) - timedelta(minutes=10)
        await session.commit()
    await request_ride(client, second["headers"])
    rows = await _take(session_factory)
    # **ما بعد نافذة الجمع صفٌّ جديد** بسجلّه — والأوّلُ باقٍ كما هو
    assert [row.count for row in rows if row.kind == "ride_requested"] == [1, 1]
    assert all(row.record_type == "ride" for row in rows)


# ═════════════════════════ الصلاحيةُ والإعدادُ والقراءة


async def test_only_holders_of_the_permission_read_alerts(
    client: AsyncClient, admin_headers: dict, support_headers: dict, session_factory
) -> None:
    # **المشرفُ الكاملُ لا يملكها افتراضاً** — نصُّ المالك «دورُ المالك وحدَه»
    assert (await client.get("/admin/alerts", headers=admin_headers)).status_code == 403
    assert (await client.get("/admin/alerts", headers=support_headers)).status_code == 403
    await _receiver(session_factory, client, admin_headers)
    assert (await client.get("/admin/alerts", headers=admin_headers)).status_code == 200


async def test_the_owner_receives_by_default_and_the_blocked_do_not(session_factory) -> None:
    async with session_factory() as session:
        owner = User(phone=None, name="owner", role=UserRole.ADMIN, country_code=CountryCode.JO,
                     role_grants=[UserRoleGrant(role=UserRole.ADMIN), UserRoleGrant(role=UserRole.OWNER)])
        plain = User(phone=None, name="plain", role=UserRole.ADMIN, country_code=CountryCode.JO,
                     role_grants=[UserRoleGrant(role=UserRole.ADMIN)])
        blocked = User(phone=None, name="blocked-owner", role=UserRole.ADMIN, country_code=CountryCode.JO, is_blocked=True,
                       role_grants=[UserRoleGrant(role=UserRole.ADMIN), UserRoleGrant(role=UserRole.OWNER)])
        session.add_all([owner, plain, blocked])
        await session.commit()
        names = sorted(user.name for user in await admin_alerts.recipients(session))
    assert names == ["owner"]


async def test_list_filters_read_state_and_settings(
    client: AsyncClient, rider_payload: dict, admin_headers: dict, session_factory
) -> None:
    me = await _receiver(session_factory, client, admin_headers)
    await register(client, rider_payload)
    await alert_capture.settle()
    async with session_factory() as session:
        await admin_alerts.drain(session, get_redis_client(), push=False)

    page = (await client.get("/admin/alerts", headers=admin_headers)).json()
    assert page["unread"] == 1 and page["items"][0]["kind"] == "rider_signup"
    item = page["items"][0]
    # **العنوانُ والسطرُ كما على شاشة القفل** — ولا اسمَ ولا رقم
    assert item["title"] == "راكبٌ جديد · الأردن"
    assert rider_payload["name"] not in item["title"] + item["body"] and rider_payload["phone"] not in str(item)

    assert (await client.get("/admin/alerts", params={"category": "money"}, headers=admin_headers)).json()["items"] == []
    assert (await client.get("/admin/alerts", params={"country_code": "LY"}, headers=admin_headers)).json()["items"] == []

    # **إطفاءُ النوع في «اللوحة» يُخفيه من الجرس والقائمة**
    settings = (await client.get("/admin/alerts/settings", headers=admin_headers)).json()
    assert all(all(channels.values()) for channels in settings["kinds"].values())  # **الافتراضُ: الكلُّ مشغَّل**
    settings["kinds"]["rider_signup"]["panel"] = False
    assert (await client.put("/admin/alerts/settings", json=settings, headers=admin_headers)).status_code == 200
    assert (await client.get("/admin/alerts/summary", headers=admin_headers)).json()["unread"] == 0
    settings["kinds"]["rider_signup"]["panel"] = True
    await client.put("/admin/alerts/settings", json=settings, headers=admin_headers)

    bad = {**settings, "kinds": {**settings["kinds"], "invented_kind": {"panel": True}}}
    assert (await client.put("/admin/alerts/settings", json=bad, headers=admin_headers)).status_code in (400, 422)

    read = (await client.post("/admin/alerts/read", json={"ids": [item["id"]]}, headers=admin_headers)).json()
    assert read == {"marked": 1, "unread": 0}

    # **«مقروء» من زرِّ الإشعار** — برمزه وحدَه بلا جلسة، ورمزٌ مزوَّرٌ لا يجد شيئاً
    async with session_factory() as session:
        await session.execute(delete(admin_alerts.AdminAlertRead))
        await session.commit()
    alert_id = uuid.UUID(item["id"])
    forged = await client.post(f"/alerts/{alert_id}/read-by-token", json={"user_id": me["id"], "token": "0" * 40})
    assert forged.status_code == 404
    token = admin_alerts.read_token(uuid.UUID(me["id"]), alert_id)
    assert (await client.post(f"/alerts/{alert_id}/read-by-token", json={"user_id": me["id"], "token": token})).status_code == 204
    assert (await client.get("/admin/alerts/summary", headers=admin_headers)).json()["unread"] == 0


# ═════════════════════════ الإرسال


async def test_push_reaches_web_and_phone_with_the_right_shape(
    client: AsyncClient, rider_payload: dict, admin_headers: dict, session_factory
) -> None:
    await enable_push_provider(session_factory)
    await _receiver(session_factory, client, admin_headers)
    devices = {
        "web-token-0001": {"platform": "web"},
        "phone-native-01": {"platform": "android", "push_channels": admin_alerts.ADMIN_NATIVE},
        "phone-legacy-01": {"platform": "android"},
    }
    for index, (token, extra) in enumerate(devices.items()):
        answer = await client.put("/me/devices", json={"device_id": f"device-{index:04d}", "token": token, **extra}, headers=admin_headers)
        assert answer.status_code == 200, answer.text

    await register(client, rider_payload)
    await alert_capture.settle()
    async with session_factory() as session:
        await admin_alerts.drain(session, get_redis_client())

    redis = get_redis_client()
    web = (await sent_messages(redis, "web-token-0001"))[-1]
    native = (await sent_messages(redis, "phone-native-01"))[-1]
    legacy = (await sent_messages(redis, "phone-legacy-01"))[-1]
    # **المتصفّحُ وتطبيقُ الإدارة الجديدُ يرسمان بأنفسهما** (أيقونةُ النوع وأزرارُه) — **والأقدمُ يرسمه النظامُ كما اليوم**
    assert web["data_only"] and native["data_only"] and not legacy["data_only"]
    assert native["high_priority"]
    assert native["data"]["tone"] == "account" and native["data"]["kind"] == "rider_signup"
    assert native["data"]["read_token"] and native["data"]["record_type"] == "rider"
    for message in (web, native, legacy):
        assert message["title"] == "راكبٌ جديد · الأردن"
        text = message["title"] + message["body"] + str(message["data"])
        assert rider_payload["name"] not in text and rider_payload["phone"] not in text

    # **إطفاءُ «الهاتف» للنوع لا يُطفئ «المتصفّح»**
    settings = (await client.get("/admin/alerts/settings", headers=admin_headers)).json()
    settings["kinds"]["rider_signup"]["phone"] = False
    await client.put("/admin/alerts/settings", json=settings, headers=admin_headers)
    before = {token: len(await sent_messages(redis, token)) for token in devices}
    await register(client, {**RIDER, "phone": "+962790000097"})
    await alert_capture.settle()
    async with session_factory() as session:
        await admin_alerts.drain(session, get_redis_client())
    after = {token: len(await sent_messages(redis, token)) for token in devices}
    assert after["web-token-0001"] == before["web-token-0001"] + 1
    assert after["phone-native-01"] == before["phone-native-01"]


async def test_preview_sends_every_kind_to_my_devices_only(client: AsyncClient, admin_headers: dict, session_factory) -> None:
    await enable_push_provider(session_factory)
    await _receiver(session_factory, client, admin_headers)
    await client.put("/me/devices", json={"device_id": "device-9001", "token": "web-token-9001", "platform": "web"}, headers=admin_headers)
    catalog = (await client.get("/admin/alerts/catalog", headers=admin_headers)).json()
    assert {item["kind"] for item in catalog["kinds"]} == set(admin_alerts.CATALOG)
    for item in catalog["kinds"]:
        answer = await client.post("/admin/alerts/test", json={"kind": item["kind"]}, headers=admin_headers)
        assert answer.status_code == 200, answer.text
        assert answer.json()["web"] == 1 and answer.json()["title"].startswith("معاينة · ")
    samples = (await client.get("/admin/alerts/samples", headers=admin_headers)).json()
    assert len(samples) == 2 * len(admin_alerts.CATALOG)
    assert {"kind": "payment_succeeded", "count": 1, "title": "دفعةٌ ناجحة · الأردن", "body": "4.750 د.أ · نقداً"}.items() <= next(
        sample for sample in samples if sample["kind"] == "payment_succeeded" and sample["count"] == 1
    ).items()
    grouped = (await client.post("/admin/alerts/test", json={"kind": "ride_requested", "count": 12}, headers=admin_headers)).json()
    assert grouped["title"] == "معاينة · 12 طلبات رحلة · الأردن"
    async with session_factory() as session:
        # **المعاينةُ لا تُكتب** — لا صفَّ في الجرس من زرِّ المعاينة
        assert (await session.scalars(select(AdminAlert))).all() == []


# ═════════════════════════ الحدود


async def test_a_broken_queue_never_blocks_a_ride(
    client: AsyncClient, jordan_settings: None, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**إشعارٌ تعطّل لا يؤخّر رحلةً** (شرطُ المالك): Redis القائمة ساقطٌ والطلبُ يمضي."""
    rider = await rider_session(client)

    def boom(_events) -> None:
        raise ConnectionError("redis down")

    # **أسوأُ ما يقع: التسليمُ نفسُه يرمي** — والمستمعُ بعد الالتزام، فيصل الاستثناءُ من نادى `commit()` إن لم يُبتلع
    monkeypatch.setattr(alert_capture, "ship", boom)
    ride = await request_ride(client, rider["headers"])
    assert ride["status"] in ("requested", "searching")
    async with session_factory() as session:
        assert await session.get(Ride, uuid.UUID(ride["id"])) is not None


def test_no_core_update_writes_a_watched_status() -> None:
    """**المستمعُ يرى ما يمرّ بالـORM وحدَه** — فـ`update(Model).values(status=…)` على جدولٍ مراقَبٍ يُفلت منه بصمت. **ولا بابَ يفعل ذلك
    اليوم** (قِيس ٢٠٢٦-١٠-٢١)، وهذا ما يُبقيه كذلك: من كتب واحداً يكتب حدثَه بيده، أو يكتبه بالـORM."""
    names = {model.__name__ for model in alert_capture.watched_models()}
    watched_columns = ("status", "review_status", "debt_blocked")
    offenders: list[str] = []
    pattern = re.compile(r"update\(\s*(%s)\s*\)(.{0,600}?)\.values\((.{0,300}?)\)" % "|".join(sorted(names)), re.S)
    for path in (BACKEND / "app").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for match in pattern.finditer(source):
            if any(re.search(rf"\b{column}\s*=", match.group(3)) for column in watched_columns):
                offenders.append(f"{path.relative_to(BACKEND)}: update({match.group(1)})")
    assert offenders == []


def test_every_kind_has_a_known_category_and_tone() -> None:
    for spec in admin_alerts.CATALOG.values():
        assert spec.category in admin_alerts.CATEGORIES
        assert spec.tone in admin_alerts.TONES
    # **الأنواعُ التي سمّاها المالكُ كلُّها في الفهرس**
    named = {
        "rider_signup", "captain_signup", "documents_submitted", "documents_approved", "documents_rejected",
        "payment_succeeded", "payment_failed", "payment_cancelled", "payment_expired", "wallet_topup",
        "withdrawal_requested", "withdrawal_paid", "subscription_purchased", "refund", "manual_adjustment",
        "debt_cap_reached", "ride_requested", "ride_accepted", "ride_completed", "ride_cancelled",
        "complaint", "low_rating", "feedback",
    }
    assert named <= set(admin_alerts.CATALOG)
