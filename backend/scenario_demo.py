"""يبني سيناريو فحصٍ بصريٍّ في قاعدة التطوير — حساباتٌ جديدة لا يمسّ القائمة.

**يمر بالمسارات الحقيقية حيث توجد** (رحلة، دفع، اشتراك، سحب، مستندات)، ولا
يكتب مباشرةً إلا حيث لا مسار: كلمةُ المرور وختمُ الرقم واعتمادُ الكبتن — وهي
نفسها ما تكتبه `tests/helpers.py` مباشرةً للسبب نفسه.

يُشغَّل داخل حاوية الخلفية:
    docker compose exec -T backend python /scratch/scenario.py
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.phone import normalize_phone
from app.core.security import hash_password
from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    DriverStatus,
    Gender,
    GenderPreference,
    PaymentMethod,
    SubscriptionStatus,
    UserRole,
)
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.user import User

API = "http://localhost:8000/api/v1"
PASSWORD = "TaxoDemo123"

RIDER = ("0799000001", "سارة العمري", Gender.FEMALE)
RIDER2 = ("0799000002", "خالد النعيمي", Gender.MALE)
DRIVER_M = ("0799000010", "أحمد الزعبي", Gender.MALE)
DRIVER_F = ("0799000011", "ليلى الحوراني", Gender.FEMALE)
SUPPORT = ("0799000099", "موظف الدعم", None)


async def _upsert_user(session, phone_raw, name, gender, *, role, verified=True):
    phone = normalize_phone(phone_raw, "JO")
    user = await session.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, name=name, role=role, country_code=CountryCode.JO)
        session.add(user)
    user.name = name
    user.role = role
    user.password_hash = hash_password(PASSWORD)
    user.phone_verified_at = datetime.now(UTC) if verified else None
    if gender is not None:
        user.gender = gender
        # جنسُ الراكبة تعلنه هي (بلا ختم)، وجنسُ الكبتن يختمه المشرف
        if role is UserRole.DRIVER:
            user.gender_verified_at = datetime.now(UTC)
    await session.flush()
    return user


async def _driver_row(session, user: User) -> Driver:
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        driver = Driver(user_id=user.id, cliq_alias=user.phone)
        session.add(driver)
        await session.flush()
    return driver


async def _plan(session) -> SubscriptionPlan:
    plan = await session.scalar(
        select(SubscriptionPlan).where(SubscriptionPlan.country_code == CountryCode.JO)
    )
    return plan


async def seed_accounts() -> dict:
    out: dict = {}
    async with SessionLocal() as session:
        rider = await _upsert_user(session, *RIDER, role=UserRole.RIDER)
        rider.ride_gender_preference = GenderPreference.FEMALE
        rider2 = await _upsert_user(session, *RIDER2, role=UserRole.RIDER)
        await _upsert_user(session, *SUPPORT, role=UserRole.SUPPORT)

        dm_user = await _upsert_user(session, *DRIVER_M, role=UserRole.DRIVER)
        df_user = await _upsert_user(session, *DRIVER_F, role=UserRole.DRIVER)
        dm = await _driver_row(session, dm_user)
        df = await _driver_row(session, df_user)
        dm.status = DriverStatus.APPROVED
        # كبتنةٌ قصرت عملها على النساء — وهو ما يرسمه شريطُ التفضيل
        df.status = DriverStatus.APPROVED
        df.gender_preference = GenderPreference.FEMALE

        plan = await _plan(session)
        now = datetime.now(UTC)
        for driver in (dm, df):
            existing = await session.scalar(
                select(DriverSubscription).where(
                    DriverSubscription.driver_id == driver.id,
                    DriverSubscription.expires_at > now,
                )
            )
            if existing is None and plan is not None:
                session.add(
                    DriverSubscription(
                        driver_id=driver.id,
                        plan_id=plan.id,
                        starts_at=now - timedelta(days=2),
                        expires_at=now + timedelta(days=28),
                        amount_paid=plan.price,
                        payment_method=PaymentMethod.CASH,
                        status=SubscriptionStatus.ACTIVE,
                    )
                )

        await session.commit()
        out = {
            "rider": str(rider.id),
            "rider2": str(rider2.id),
            "driver_m": str(dm.id),
            "driver_f": str(df.id),
            "driver_m_user": str(dm_user.id),
            "driver_f_user": str(df_user.id),
        }
    return out


async def clear_login_limits(quiet: bool = False) -> None:
    """يمحو عدّادات حدِّ محاولات الدخول قبل البدء.

    السكربتُ يسجّل دخولَ خمسةِ حساباتٍ من نفس الـIP خلال ثوانٍ، وهو بالضبط ما
    وُضع الحدُّ لأجله (القسم 14) — فالمسحُ هنا **لبيئة التطوير وحدها** ولا
    يمسّ الحارس نفسه.
    """
    from app.core.redis_client import get_redis_client

    redis = get_redis_client()
    keys = [key async for key in redis.scan_iter(match="ratelimit:login:*")]
    if keys:
        await redis.delete(*keys)
        if not quiet:
            print(f"مُسح {len(keys)} عدّاد محاولات دخول")


async def login(
    client: httpx.AsyncClient, phone: str, password: str = PASSWORD
) -> dict:
    # الحدُّ يُمحى **قبل كل دخول** لا مرةً واحدة: السكربت يسجّل خمسةَ حسابات
    # من نفس الـIP في ثوانٍ، وهو بالضبط ما وُضع الحدُّ لأجله
    await clear_login_limits(quiet=True)
    response = await client.post(
        f"{API}/auth/login",
        json={"phone": phone, "password": password, "country_code": "JO"},
    )
    response.raise_for_status()
    body = response.json()
    return {"Authorization": f"Bearer {body['tokens']['access_token']}"}


async def ensure_vehicle(client, headers, plate: str) -> None:
    existing = await client.get(f"{API}/drivers/me/vehicles", headers=headers)
    if existing.status_code == 200 and existing.json():
        return
    await client.post(
        f"{API}/drivers/me/vehicles",
        headers=headers,
        json={
            "make": "Toyota",
            "model": "Corolla",
            "year": 2022,
            "color": "أبيض",
            "plate_number": plate,
            "category": "economy",
        },
    )


PICKUP = {"lat": 31.9539, "lng": 35.9106}
DROPOFF = {"lat": 31.9800, "lng": 35.8900}


async def go_online(client, headers) -> None:
    await client.post(f"{API}/drivers/me/online", headers=headers)
    await client.post(
        f"{API}/drivers/me/location",
        headers=headers,
        json={"lat": 31.9560, "lng": 35.9100, "heading": 45},
    )


async def make_ride(client, rider_headers, driver_headers, *, preference="any") -> dict:
    created = await client.post(
        f"{API}/rides",
        headers=rider_headers,
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "pickup_address": "دوار الداخلية، عمّان",
            "dropoff_address": "شارع الرينبو، جبل عمّان",
            "vehicle_category": "economy",
            "gender_preference": preference,
        },
    )
    created.raise_for_status()
    ride = created.json()

    # ينتظر أن يصل العرضُ إلى الكبتن ثم يقبل
    for _ in range(40):
        await asyncio.sleep(0.25)
        accepted = await client.post(
            f"{API}/rides/{ride['id']}/accept", headers=driver_headers
        )
        if accepted.status_code == 200:
            return accepted.json()
    raise RuntimeError(f"لم يصل العرض: {ride['id']}")


async def main() -> None:
    await clear_login_limits()
    ids = await seed_accounts()
    print("الحسابات جاهزة:", ids)

    async with httpx.AsyncClient(timeout=30) as client:
        rider = await login(client, RIDER[0])
        rider2 = await login(client, RIDER2[0])
        dm = await login(client, DRIVER_M[0])
        df = await login(client, DRIVER_F[0])
        # المشرفُ حسابٌ قائمٌ بكلمته من `.env.local` — لا يمسّه هذا السكربت
        admin = await login(client, "0790000000", "AdminLocal123")

        await ensure_vehicle(client, dm, "AMM-1010")
        await ensure_vehicle(client, df, "AMM-2020")
        await go_online(client, dm)
        await go_online(client, df)

        # --- رحلتان مكتملتان مدفوعتان (سجل الرحلات والتقارير) ---
        for index in range(2):
            ride = await make_ride(client, rider2, dm)
            await client.post(f"{API}/rides/{ride['id']}/arrive", headers=dm)
            await client.post(f"{API}/rides/{ride['id']}/start", headers=dm)
            await client.post(
                f"{API}/drivers/me/location",
                headers=dm,
                json={"lat": 31.9700, "lng": 35.9000, "heading": 90},
            )
            await client.post(f"{API}/rides/{ride['id']}/complete", headers=dm)
            paid = await client.post(
                f"{API}/rides/{ride['id']}/payments",
                headers=rider2,
                json={"method": "cash", "idempotency_key": f"demo-cash-{index}-{uuid.uuid4().hex[:8]}"},
            )
            if paid.status_code == 201:
                payment = paid.json()["payments"][0]
                await client.post(f"{API}/payments/{payment['id']}/confirm", headers=dm)
            print(f"رحلة مكتملة #{index + 1}: {ride['id']}")

        # --- رحلةٌ ملغاة بعد القبول (معدّل الإلغاء) ---
        cancelled = await make_ride(client, rider2, dm)
        await client.post(
            f"{API}/rides/{cancelled['id']}/cancel",
            headers=dm,
            json={"reason": "تعطّلت المركبة"},
        )
        print("رحلة ملغاة:", cancelled["id"])

        # --- رحلةٌ نسائيةٌ جارية (شارة الرحلة النسائية + شريط الكبتن) ---
        active = await make_ride(client, rider, df, preference="female")
        await client.post(f"{API}/rides/{active['id']}/arrive", headers=df)
        await client.post(f"{API}/rides/{active['id']}/start", headers=df)
        print("رحلة نسائية جارية:", active["id"])

        # --- طلبُ سحبٍ معلّق (المالية) ---
        await client.post(
            f"{API}/admin/wallets/{ids['driver_m_user']}/topups",
            headers=admin,
            json={"method": "cash", "amount": "40.000", "reference": "شحن تجريبي"},
        )
        await client.post(
            f"{API}/wallet/me/withdrawals",
            headers=dm,
            json={"amount": "15.000", "method": "cliq"},
        )
        print("طلب سحب معلّق أُنشئ")

    print("\nكلمة المرور للجميع:", PASSWORD)


if __name__ == "__main__":
    asyncio.run(main())
