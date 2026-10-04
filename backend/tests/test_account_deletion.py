"""حذفُ الحساب حذفاً حقيقياً بعد مهلة (SPEC §59، قراراتُ المالك ٢٠٢٦-٠٩-٢٩).

**ما يُقاس هنا وما لماذا**:

- **كلُّ مانعٍ باسمه** — والموانعُ كلُّها معاً لا أوّلُها.
- **رصيدُ الراكب يُقرّ به كما هو** أو يُحوَّل — ولا يمنع الحذف.
- **المهلةُ تُغلق العملَ الجديد وتُبقي طريقَ العودة** — والعودةُ إلى ما كان لا إلى «معتمَد».
- **التجهيلُ عموداً عموداً**: ما في جدول «يُمحى» يُقاس فارغاً أو مجهَّلاً، وما
  في «يبقى» يُقاس باقياً — **ولوحةُ المركبة باقيةٌ بقرار المالك** حتى تُحفظ نسختُها.
- **الملفّاتُ بعد الالتزام**: تُحذف حين يثبت التجهيل، وتبقى إن سقط.
- **حسابٌ عليه مالٌ لا يُجهَّل**: يُؤجَّل ويُنبَّه المشرف مرّةً.
- **وسباقُ الشحن مع التجهيل** في `test_account_deletion_concurrency.py`.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core import storage
from app.core.exceptions import AccountDeleted
from app.core.redis_client import get_redis_client
from app.models.audit import AdminAuditLog
from app.models.deactivation import DeactivationRequest
from app.models.device import DeviceToken
from app.models.driver import Driver, DriverDocument
from app.models.enums import (
    CampaignAudience,
    CampaignStatus,
    CountryCode,
    DeactivationStatus,
    DevicePlatform,
    DeliveryStatus,
    DriverStatus,
    FeatureKey,
    PaymentProvider,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.feature_flag import FeatureFlag
from app.models.notification import (
    NotificationCampaign,
    NotificationDelivery,
    UserNotification,
)
from app.models.payment import Payment, SavedCard
from app.models.photo_report import UserPhotoReport
from app.models.place import SavedPlace
from app.models.rating import Rating
from app.models.ride import Ride, RideRoutePoint
from app.models.totp import UserRecoveryCode, UserTotp
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wallet import WalletTransaction
from app.services import account_deletion
from app.services import wallet as wallet_service
from tests.helpers import (
    DRIVER,
    DROPOFF,
    NEAR_PICKUP,
    PICKUP,
    RIDER,
    accepted_ride,
    add_route_points,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    inbox_of,
    real_jpeg,
    register,
    register_device,
    rider_session,
    topup_wallet,
    upload_document,
)

pytestmark = pytest.mark.usefixtures("jordan_settings", "jordan_wallet")



# ------------------------------------------------------------------ مساعدات


async def _due_now(session_factory, user_id: uuid.UUID) -> None:
    """يُحِلّ الموعدَ الآن — **المهلةُ نفسُها لا تُنتظر في اختبار**."""
    async with session_factory() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(deletion_due_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()


async def _user(session_factory, user_id: uuid.UUID) -> User:
    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        return user


async def _count(session_factory, model, *where) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(select(func.count()).select_from(model).where(*where))
        )


async def _ledger(session_factory, user_id: uuid.UUID) -> tuple[int, Decimal]:
    async with session_factory() as session:
        row = (
            await session.execute(
                select(
                    func.count(WalletTransaction.id),
                    func.coalesce(func.sum(WalletTransaction.amount), 0),
                ).where(WalletTransaction.owner_id == user_id)
            )
        ).one()
        return int(row[0]), Decimal(row[1])


async def _run(session_factory) -> dict[str, int]:
    return await account_deletion.anonymize_due(session_factory, get_redis_client())


def _signup_body(payload: dict) -> dict:
    """حمولةُ تسجيلٍ بإثبات الرقم — **لنقرأ الردَّ لا لنفترض نجاحَه** كما يفعل `register`."""
    from app.core.phone import normalize_phone
    from app.services.firebase_auth import mock_token

    return payload | {
        "verification_token": mock_token(
            normalize_phone(payload["phone"], payload["country_code"])
        )
    }


def _on_disk(relative_path: str) -> bool:
    """**أهو على القرص الآن؟** — و`storage.resolve` يرمي حين يغيب، فلا يُسأل به عن الغياب."""
    return (storage.root().resolve() / relative_path).is_file()


def _uid(body: dict) -> uuid.UUID:
    return uuid.UUID(str(body.get("user_id") or body["user"]["id"]))


async def _login_again(client: AsyncClient, payload: dict) -> dict[str, str]:
    """**دخولٌ جديدٌ بعد الطلب** (SPEC §60، قرارُ المالك ٢٠٢٦-١٠-٠٤).

    الطلبُ يُبطل الجلساتِ كلَّها، **وتوكنُ الوصول يُسأل عن جلسته في كلِّ طلب** —
    فيسقط القديمُ عند طلبه التالي. **وكان قبل §60 يبقى يعمل حتى ينتهي**، فكانت
    هذه الاختباراتُ تتابع به. والتطبيقُ نفسُه يخرج بعد الطلب ثمّ يدخل إلى شاشة
    الاستعادة (`DeleteAccount.tsx`) — **وهذا ما يفعله الاختبارُ الآن**.
    """
    response = await client.post(
        "/auth/login",
        json={
            "phone": payload["phone"],
            "password": payload["password"],
            "country_code": payload["country_code"],
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}


# ------------------------------------------------------------------ الموانع


async def test_an_active_ride_blocks_and_is_named(client: AsyncClient, session_factory) -> None:
    """**لا يُحذف حسابٌ وراكبٌ في سيارته** — والمانعُ باسمه في الجواب وفي الحال."""
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver, NEAR_PICKUP)
    rider = auth(await register(client, RIDER))
    await accepted_ride(client, rider, driver)

    for headers in (driver["headers"], rider):
        refused = await client.post("/account/deletion", json={}, headers=headers)
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "deletion_blocked"
        assert "active_ride" in refused.json()["blockers"]
        state = (await client.get("/account/deletion", headers=headers)).json()
        assert "active_ride" in state["blockers"] and state["due_at"] is None


async def test_an_open_dispute_blocks(client: AsyncClient, session_factory) -> None:
    """نزاعٌ على دفعةٍ سؤالٌ عن مالٍ لم يُحسم — **للطرفين**."""
    from tests.test_payments import _disputed_payment

    rider, driver, _ = await _disputed_payment(client, session_factory)
    for headers in (rider["headers"], driver["headers"]):
        refused = await client.post("/account/deletion", json={}, headers=headers)
        assert refused.status_code == 409, refused.text
        assert "open_dispute" in refused.json()["blockers"]


async def test_an_unpaid_cancellation_fee_blocks(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """رسمُ إلغاءٍ مستحقٌّ عليه — **مالُ كبتنٍ آخر في ذمّته**."""
    from tests.test_cancellation_collection import _owe

    owed = await _owe(client, admin_headers, session_factory)
    refused = await client.post(
        "/account/deletion", json={}, headers=owed["rider"]["headers"]
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["blockers"] == ["unpaid_charge"]


async def test_staff_accounts_are_not_deleted_from_the_app(
    client: AsyncClient, admin_headers: dict
) -> None:
    refused = await client.post("/account/deletion", json={}, headers=admin_headers)
    assert refused.status_code == 403, refused.text


# ------------------------------------------------------------------ رصيدُ الراكب


async def test_a_rider_balance_is_acknowledged_as_it_is_and_the_ledger_stays(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """قرارُ المالك ١: **لا يمنع الحذف** — يُقَرّ بضياعه بالمبلغ نفسِه، ولا يُمسّ الدفتر."""
    rider = await rider_session(client)
    uid = _uid(rider)
    await topup_wallet(client, admin_headers, str(uid), "5.000")

    state = (await client.get("/account/deletion", headers=rider["headers"])).json()
    assert state["rider_balance"] == "5.000" and state["blockers"] == []
    assert state["transfer_enabled"] is True

    for sent in ({}, {"forfeit_amount": "4.999"}, {"forfeit_amount": "5.001"}):
        refused = await client.post("/account/deletion", json=sent, headers=rider["headers"])
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "deletion_balance_unacknowledged"
        assert refused.json()["balance"] == "5.000"

    accepted = await client.post(
        "/account/deletion", json={"forfeit_amount": "5.000"}, headers=rider["headers"]
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["forfeit_amount"] == "5.000"
    assert await _ledger(session_factory, uid) == (1, Decimal("5.000"))


async def test_the_transfer_option_follows_the_country_switch(
    client: AsyncClient, session_factory
) -> None:
    """**خيارُ التحويل يظهر حين يكون مفعّلاً في دولته وحدَه** (قرارُ المالك ١)."""
    rider = await rider_session(client)
    async with session_factory() as session:
        await session.execute(
            update(FeatureFlag)
            .where(
                FeatureFlag.country_code == CountryCode.JO,
                FeatureFlag.feature_key == FeatureKey.WALLET_TRANSFER_ENABLED.value,
            )
            .values(enabled=False)
        )
        await session.commit()
    state = (await client.get("/account/deletion", headers=rider["headers"])).json()
    assert state["transfer_enabled"] is False


# ------------------------------------------------------------------ المهلة


async def test_the_grace_period_closes_new_work_and_keeps_the_way_back(
    client: AsyncClient, session_factory
) -> None:
    """**لا رحلةَ ولا جهازَ ولا تسجيلَ ثانٍ** — والدخولُ ثمّ الاستعادةُ يعيدان كلَّ شيء."""
    rider = await rider_session(client)
    uid = _uid(rider)
    await register_device(client, rider["headers"])

    opened = await client.post("/account/deletion", json={}, headers=rider["headers"])
    assert opened.status_code == 201, opened.text
    due = datetime.fromisoformat(opened.json()["due_at"])
    assert timedelta(days=29, hours=23) < due - datetime.now(UTC) <= timedelta(days=30)
    # **رموزُ الأجهزة تُمحى لحظةَ الطلب** — لا إشعارَ في المهلة
    assert await _count(session_factory, DeviceToken, DeviceToken.user_id == uid) == 0
    # **وجلساتُه كلُّها تسقط لحظتَها** (SPEC §60) — والتوكنُ الذي طلب بها منها
    assert (await client.get("/auth/me", headers=rider["headers"])).status_code == 401

    # **والدخولُ يُقبل**، والجلسةُ تقول الموعدَ فيرسم التطبيقُ شاشةَ الاستعادة
    login = await client.post(
        "/auth/login",
        json={"phone": RIDER["phone"], "password": RIDER["password"], "country_code": "JO"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["deletion_due_at"] is not None
    headers = {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}

    # **والعملُ الجديدُ مغلقٌ على الجلسة الجديدة أيضاً** — الحارسُ في الحساب لا في التوكن
    ride = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=headers,
    )
    assert ride.status_code == 403, ride.text
    assert ride.json()["code"] == "account_deletion_pending"

    device = await client.put(
        "/me/devices",
        json={"device_id": "device-2", "token": "fcm-token-2", "platform": "android"},
        headers=headers,
    )
    assert device.status_code == 403 and device.json()["code"] == "account_deletion_pending"

    again = await client.post("/auth/register", json=_signup_body(RIDER))
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "phone_scheduled_for_deletion"

    restored = await client.delete("/account/deletion", headers=headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["due_at"] is None
    await register_device(client, headers, device_id="device-3", token="fcm-token-3")
    assert (await _user(session_factory, uid)).deletion_due_at is None


async def test_a_driver_leaves_dispatch_and_comes_back_to_what_he_was(
    client: AsyncClient, session_factory
) -> None:
    """**يخرج من التوزيع لحظةَ الطلب**، ويعود إلى حاله **لا إلى «معتمَد»**."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    driver_id = uuid.UUID(str(driver["driver_id"]))

    assert (await client.post("/account/deletion", json={}, headers=driver["headers"])).status_code == 201
    async with session_factory() as session:
        row = await session.get(Driver, driver_id)
        assert row is not None and row.status is DriverStatus.DEACTIVATED

    headers = await _login_again(client, DRIVER)
    assert (await client.delete("/account/deletion", headers=headers)).status_code == 200
    async with session_factory() as session:
        row = await session.get(Driver, driver_id)
        assert row is not None and row.status is DriverStatus.APPROVED


async def test_a_suspended_driver_comes_back_suspended(
    client: AsyncClient, session_factory
) -> None:
    """**الاستعادةُ لا تفتح باباً أغلقه مشرف** — من كان موقوفاً يعود موقوفاً."""
    suspended = DRIVER | {"phone": "0796660121", "name": "كبتنٌ موقوف"}
    driver = await approved_driver(
        client,
        session_factory,
        suspended,
        plate_number="AMM-0121",
        subscribed=False,
    )
    driver_id = uuid.UUID(str(driver["driver_id"]))
    async with session_factory() as session:
        await session.execute(
            update(Driver).where(Driver.id == driver_id).values(status=DriverStatus.SUSPENDED)
        )
        await session.commit()

    assert (await client.post("/account/deletion", json={}, headers=driver["headers"])).status_code == 201
    headers = await _login_again(client, suspended)
    assert (await client.delete("/account/deletion", headers=headers)).status_code == 200
    async with session_factory() as session:
        row = await session.get(Driver, driver_id)
        assert row is not None and row.status is DriverStatus.SUSPENDED


# ------------------------------------------------------------------ التجهيل


async def test_anonymizing_a_rider_erases_what_identifies_and_keeps_the_records(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**جدولُ §59-هـ عموداً عموداً**: ما يُمحى يُقاس فارغاً، وما يبقى يُقاس باقياً."""
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver, NEAR_PICKUP)
    rider = await rider_session(client)
    uid = _uid(rider)
    driver_user = uuid.UUID(str(driver["user_id"]))

    photo = await client.put(
        "/auth/me/photo",
        files={"file": ("me.jpg", real_jpeg(), "image/jpeg")},
        headers=rider["headers"],
    )
    assert photo.status_code == 200, photo.text
    photo_path = (await _user(session_factory, uid)).photo_path
    assert photo_path and _on_disk(photo_path)

    placed = await client.post(
        "/me/places",
        json={"label": "المنزل", "address": "عمّان", "lat": 31.95, "lng": 35.91},
        headers=rider["headers"],
    )
    assert placed.status_code == 201, placed.text

    ride = await completed_ride(client, rider["headers"], driver)
    ride_id = uuid.UUID(ride["id"])
    await add_route_points(session_factory, ride["id"], [(31.9601, 35.9107), (31.9612, 35.9119)])
    rated = await client.post(
        f"/rides/{ride['id']}/ratings",
        json={"stars": 5, "comment": "كبتنٌ لطيف"},
        headers=rider["headers"],
    )
    assert rated.status_code == 201, rated.text
    await topup_wallet(client, admin_headers, str(uid), "2.000")

    async with session_factory() as session:
        await session.execute(
            update(Ride)
            .where(Ride.id == ride_id)
            .values(
                pickup_address="بيتي في الجبيهة",
                dropoff_address="عملي في الشميساني",
                route_polyline="encoded-polyline",
                route_steps="[]",
            )
        )
        campaign = NotificationCampaign(
            title="عرض", body="نصّ", audience=list(CampaignAudience)[0],
            status=list(CampaignStatus)[0], sent_count=0,
        )
        session.add(campaign)
        await session.flush()
        session.add_all(
            [
                NotificationDelivery(campaign_id=campaign.id, user_id=uid, status=list(DeliveryStatus)[0]),
                UserTotp(user_id=uid, secret_encrypted={"v": 1, "ciphertext": "x"}),
                UserRecoveryCode(user_id=uid, code_hash="c" * 64),
                SavedCard(
                    user_id=uid, provider=list(PaymentProvider)[0], provider_token="tok",
                    last4="4242", expiry_month=12, expiry_year=2030,
                ),
                UserPhotoReport(subject_id=uid, reported_by=driver_user, ride_id=ride_id),
                DeactivationRequest(
                    user_id=uid, reason="سببٌ كتبه", status=DeactivationStatus.CANCELLED
                ),
            ]
        )
        await session.commit()

    ledger_before = await _ledger(session_factory, uid)
    audits_before = await _count(session_factory, AdminAuditLog)
    payments_before = await _count(session_factory, Payment, Payment.ride_id == ride_id)
    assert await _count(session_factory, UserNotification, UserNotification.user_id == uid) > 0

    opened = await client.post(
        "/account/deletion", json={"forfeit_amount": "2.000"}, headers=rider["headers"]
    )
    assert opened.status_code == 201, opened.text
    # **وجهازٌ كُتب بعد الطلب يُمحى في التجهيل أيضاً** — لا يُفترض أن الطلبَ مسحه
    async with session_factory() as session:
        session.add(DeviceToken(user_id=uid, device_id="late", token="late", platform=DevicePlatform.ANDROID))
        await session.commit()
    await _due_now(session_factory, uid)

    counts = await _run(session_factory)
    assert counts["anonymized"] == 1, counts

    # ── يُمحى أو يُجهَّل
    user = await _user(session_factory, uid)
    assert user.name == account_deletion.DELETED_NAME
    assert user.phone is None and user.email is None
    assert user.phone_verified_at is None and user.email_verified_at is None
    assert user.photo_path is None and user.photo_hidden_at is None
    assert user.gender is None and user.gender_verified_at is None
    assert user.referral_code is None and user.gender_mismatch_reports == 0
    assert user.deleted_at is not None and user.deactivated_at is not None
    assert user.deletion_deferred_reason is None
    assert not _on_disk(photo_path), "الصورةُ باقيةٌ على القرص"
    for model, column in (
        (DeviceToken, DeviceToken.user_id), (SavedCard, SavedCard.user_id),
        (SavedPlace, SavedPlace.user_id), (UserTotp, UserTotp.user_id),
        (UserRecoveryCode, UserRecoveryCode.user_id),
        (UserNotification, UserNotification.user_id),
        (NotificationDelivery, NotificationDelivery.user_id),
        (UserPhotoReport, UserPhotoReport.subject_id),
    ):
        assert await _count(session_factory, model, column == uid) == 0, model.__name__
    assert await _count(session_factory, RideRoutePoint, RideRoutePoint.ride_id == ride_id) == 0

    async with session_factory() as session:
        rating = await session.scalar(select(Rating).where(Rating.rater_id == uid))
        assert rating is not None and rating.comment is None and rating.stars == 5
        legacy = await session.scalar(select(DeactivationRequest).where(DeactivationRequest.user_id == uid))
        assert legacy is not None and legacy.reason is None
        row = await session.get(Ride, ride_id)
        assert row is not None
        assert row.pickup_address is None and row.dropoff_address is None
        assert row.route_polyline is None and row.route_steps is None
        # **النقطةُ مقرَّبةٌ لا ممحوّة** — منزلتان
        for value in (row.pickup_lat, row.pickup_lng, row.dropoff_lat, row.dropoff_lng):
            assert abs(value * 100 - round(value * 100)) < 1e-6, value

    # ── يبقى كما هو
    assert await _ledger(session_factory, uid) == ledger_before, "الدفترُ تغيّر"
    assert await _count(session_factory, AdminAuditLog) == audits_before
    assert await _count(session_factory, Payment, Payment.ride_id == ride_id) == payments_before
    async with session_factory() as session:
        row = await session.get(Ride, ride_id)
        assert row is not None and row.final_fare is not None and row.rider_id == uid


async def test_anonymizing_a_driver_erases_his_documents_and_keeps_the_plate(
    client: AsyncClient, session_factory
) -> None:
    """الوثائقُ وملفّاتُها تُمحى، و`cliq_alias` على صفِّه — **واللوحةُ باقيةٌ بقرار المالك**.

    **ولمَ باقية**: الرحلةُ لا تحفظ نسخةً منها، **وسجلُّ الراكب يقرؤها حيّةً من
    صفِّ المركبة** (`ride_log.plate_of`) — فمحوُها يمحوها من سجلِّ الركّاب.
    """
    driver = await approved_driver(client, session_factory, subscribed=False)
    uid = _uid(driver)
    driver_id = uuid.UUID(str(driver["driver_id"]))
    document = await upload_document(client, driver["headers"])
    async with session_factory() as session:
        stored = await session.get(DriverDocument, uuid.UUID(document["id"]))
        assert stored is not None
        doc_path = stored.file_path
        await session.execute(update(Driver).where(Driver.id == driver_id).values(cliq_alias="taxo.captain"))
        await session.commit()
    assert _on_disk(doc_path)

    assert (await client.post("/account/deletion", json={}, headers=driver["headers"])).status_code == 201
    await _due_now(session_factory, uid)
    assert (await _run(session_factory))["anonymized"] == 1

    assert await _count(session_factory, DriverDocument, DriverDocument.driver_id == driver_id) == 0
    assert not _on_disk(doc_path), "ملفُّ الوثيقة باقٍ على القرص"
    async with session_factory() as session:
        row = await session.get(Driver, driver_id)
        assert row is not None and row.cliq_alias is None
        plate = await session.scalar(select(Vehicle.plate_number).where(Vehicle.driver_id == driver_id))
        assert plate == "AMM-4242", "اللوحةُ مُحيت — وقرارُ المالك أن تبقى في سجلِّ الركّاب"


async def test_files_stay_when_the_anonymization_does_not_commit(
    client: AsyncClient, session_factory
) -> None:
    """**الملفُّ بعد الالتزام لا قبله**: تجهيلٌ يسقط يترك الصورةَ وصاحبَها كما هما."""
    rider = await rider_session(client)
    uid = _uid(rider)
    await client.put(
        "/auth/me/photo",
        files={"file": ("me.jpg", real_jpeg(), "image/jpeg")},
        headers=rider["headers"],
    )
    photo_path = (await _user(session_factory, uid)).photo_path
    assert photo_path
    assert (await client.post("/account/deletion", json={}, headers=rider["headers"])).status_code == 201
    await _due_now(session_factory, uid)

    async with session_factory() as session:
        outcome = await account_deletion.process_one(session, uid)
        assert outcome is not None and outcome.anonymized and photo_path in outcome.files
        await session.rollback()

    assert _on_disk(photo_path)
    user = await _user(session_factory, uid)
    assert user.deleted_at is None and user.phone is not None and user.photo_path == photo_path


async def test_after_anonymization_the_token_is_refused_and_the_number_is_free(
    client: AsyncClient, session_factory
) -> None:
    rider = await rider_session(client)
    uid = _uid(rider)
    assert (await client.post("/account/deletion", json={}, headers=rider["headers"])).status_code == 201
    # جلسةٌ فُتحت في المهلة — **وهي ما يبقى حيّاً حتى التجهيل** منذ §60
    in_grace = await _login_again(client, RIDER)
    await _due_now(session_factory, uid)
    assert (await _run(session_factory))["anonymized"] == 1

    refused = await client.get("/wallet/me", headers=in_grace)
    assert refused.status_code == 403 and refused.json()["code"] == "account_closed"
    # **والتوكنُ الذي طلب الحذفَ سقط لحظةَ الطلب** (SPEC §60) لا بعد التجهيل
    assert (await client.get("/wallet/me", headers=rider["headers"])).status_code == 401
    # **الرقمُ يعود حرّاً**: حسابٌ جديدٌ لا صلةَ له بالمجهَّل
    fresh = await client.post("/auth/register", json=_signup_body(RIDER))
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["user"]["id"] != str(uid)


# ------------------------------------------------------------------ التأجيل


async def test_a_balance_that_moved_after_consent_defers_and_tells_the_admins_once(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """قرارُ المالك ١: **شحنٌ في المهلة بعد الموافقة لا يُجهَّل معه الحساب** — ويُنبَّه المشرف."""
    rider = await rider_session(client)
    uid = _uid(rider)
    await topup_wallet(client, admin_headers, str(uid), "5.000")
    assert (
        await client.post("/account/deletion", json={"forfeit_amount": "5.000"}, headers=rider["headers"])
    ).status_code == 201
    await topup_wallet(client, admin_headers, str(uid), "1.000")
    await _due_now(session_factory, uid)

    assert (await _run(session_factory))["deferred"] == 1
    user = await _user(session_factory, uid)
    assert user.deleted_at is None and user.phone is not None
    assert user.deletion_deferred_reason == account_deletion.DEFER_RIDER_BALANCE

    async with session_factory() as session:
        admin_id = await session.scalar(select(User.id).where(User.phone == "+962790000001"))
    alerts = [n for n in await inbox_of(session_factory, admin_id) if n.kind == "deletion_deferred"]
    assert len(alerts) == 1, alerts
    # **ومرّةً لا كلَّ ساعة**: الدورةُ التالية بالسبب نفسِه لا تنبّه ثانية
    assert (await _run(session_factory))["deferred"] == 1
    alerts = [n for n in await inbox_of(session_factory, admin_id) if n.kind == "deletion_deferred"]
    assert len(alerts) == 1, alerts

    queue = (await client.get("/admin/deletions", headers=admin_headers)).json()
    mine = [row for row in queue if row["id"] == str(uid)]
    assert mine and mine[0]["deletion_deferred_reason"] == "rider_balance_changed"
    assert mine[0]["deletion_due_at"] is not None


async def test_a_driver_with_money_is_deferred_not_anonymized(
    client: AsyncClient, session_factory
) -> None:
    """**المهلةُ وقتُ سحبه** — ورصيدٌ لم يُسحب يؤجّل ولا يُجهَّل معه."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    uid = _uid(driver)
    async with session_factory() as session:
        owner = await session.get(User, uid)
        await wallet_service.record(
            session, owner=owner, owner_type=WalletOwnerType.DRIVER,
            tx_type=WalletTransactionType.RIDE_EARNING, amount=Decimal("10.000"),
            idempotency_key=f"t:{uuid.uuid4()}",
        )
        await session.commit()
    assert (await client.post("/account/deletion", json={}, headers=driver["headers"])).status_code == 201
    await _due_now(session_factory, uid)

    assert (await _run(session_factory))["deferred"] == 1
    user = await _user(session_factory, uid)
    assert user.deleted_at is None
    assert user.deletion_deferred_reason == account_deletion.DEFER_DRIVER_BALANCE
