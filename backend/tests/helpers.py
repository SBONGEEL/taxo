"""أدوات مشتركة لاختبارات الرحلات والتوزيع والتتبع.

منذ المرحلة 4 لم يعد قبولُ رحلةٍ استدعاءً مباشراً: التوزيع يعرضها على كبتن
واحد، فلا يقبلها إلا هو. لذلك صار المسار «كبتن أونلاين بموقع ← طلب ← انتظار
العرض ← قبول» شرطاً لكل اختبار دورة حياة — وهو ما تختصره هذه الأدوات.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.enums import DriverStatus
from app.services import dispatch
from app.services.directions import Route

# نقطتان في عمّان — القيم الحقيقية لا تهم لأن Mapbox مُستبدَل في الاختبار
PICKUP = {"lat": 31.9539, "lng": 35.9106}
DROPOFF = {"lat": 31.9800, "lng": 35.8900}
# ~0.7 كم من نقطة الانطلاق: داخل دائرة الثلاثة كيلومترات
NEAR_PICKUP = {"lat": 31.9600, "lng": 35.9106}
# ~5.1 كم: خارج الدائرة الأولى وداخل الموسّعة (7 كم)
FAR_PICKUP = {"lat": 32.0000, "lng": 35.9106}

MAPBOX_SECRET = "sk.test-token"

RIDER = {
    "phone": "0791111111",
    "name": "راكب الرحلات",
    "password": "SuperSecret123",
    "country_code": "JO",
    "role": "rider",
}
DRIVER = {
    "phone": "0792222222",
    "name": "كبتن الرحلات",
    "password": "SuperSecret123",
    "country_code": "JO",
    "role": "driver",
}
OTHER_RIDER = RIDER | {"phone": "0793333333", "name": "راكب آخر"}
SECOND_DRIVER = DRIVER | {"phone": "0794444444", "name": "كبتن ثانٍ"}
THIRD_DRIVER = DRIVER | {"phone": "0795555555", "name": "كبتن ثالث"}

# 1.000 + (10 × 0.500) + (20 × 0.100) = 8.000
STUB_ROUTE = Route(distance_km=Decimal("10.000"), duration_min=Decimal("20.00"))
EXPECTED_FARE = "8.000"
CANCELLATION_FEE = "0.750"

# حدود محفظة الأردن في الاختبارات (fixture: jordan_wallet)
TRANSFER_DAILY_LIMIT = "50.000"
TRANSFER_MONTHLY_LIMIT = "200.000"
MIN_WITHDRAWAL = "10.000"


# ------------------------------------------------------------------ الحسابات


async def register(client: AsyncClient, payload: dict) -> dict:
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def auth(body: dict) -> dict:
    return {"Authorization": f"Bearer {body['tokens']['access_token']}"}


def token_of(body: dict) -> str:
    return body["tokens"]["access_token"]


async def rider_session(client: AsyncClient, payload: dict = RIDER) -> dict:
    """يُرجع الترويسات وتوكن المقبس معاً."""
    body = await register(client, payload)
    return {"headers": auth(body), "token": token_of(body)}


SUBSCRIPTION_PLAN_NAME = "خطة الاختبار الشهرية"
SUBSCRIPTION_PLAN_PRICE = "30.000"


async def ensure_plan(
    session_factory: Any,
    *,
    country: str = "JO",
    name: str = SUBSCRIPTION_PLAN_NAME,
    price: str = SUBSCRIPTION_PLAN_PRICE,
    duration: str = "monthly",
    is_active: bool = True,
) -> uuid.UUID:
    """خطة اشتراك للدولة — تُنشأ مرة وتُعاد بعدها (فريدٌ على الدولة والاسم)."""
    from app.core.currency import currency_for_country
    from app.models.enums import CountryCode, SubscriptionDurationType
    from app.models.subscription import SubscriptionPlan

    country_code = CountryCode(country)
    async with session_factory() as session:
        plan = await session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == country_code,
                SubscriptionPlan.name == name,
            )
        )
        if plan is None:
            plan = SubscriptionPlan(
                country_code=country_code,
                name=name,
                duration_type=SubscriptionDurationType(duration),
                price=Decimal(price),
                currency=currency_for_country(country_code),
                is_active=is_active,
            )
            session.add(plan)
            await session.commit()
        return plan.id


async def subscribe_driver(
    session_factory: Any, driver_id: uuid.UUID, *, days: int = 30
) -> None:
    """اشتراكٌ ساري يُكتب مباشرة — كما تُكتب الموافقة مباشرة.

    منذ المرحلة 7 لا يصل الكبتنَ عرضٌ بلا اشتراك ساري (SPEC القسم 5.3)، فصار
    هذا شرطاً في كل اختبار توزيعٍ أو رحلة. مسارُ الشراء نفسه تختبره
    `test_subscriptions.py` عبر الـ API لا من هنا.
    """
    from app.models.driver import Driver
    from app.models.enums import PaymentMethod, SubscriptionStatus
    from app.models.subscription import DriverSubscription
    from app.models.user import User

    async with session_factory() as session:
        country = await session.scalar(
            select(User.country_code)
            .join(Driver, Driver.user_id == User.id)
            .where(Driver.id == driver_id)
        )

    plan_id = await ensure_plan(session_factory, country=country.value)
    now = datetime.now(UTC)
    async with session_factory() as session:
        session.add(
            DriverSubscription(
                driver_id=driver_id,
                plan_id=plan_id,
                starts_at=now - timedelta(minutes=1),
                expires_at=now + timedelta(days=days),
                amount_paid=Decimal(SUBSCRIPTION_PLAN_PRICE),
                payment_method=PaymentMethod.CASH,
                status=SubscriptionStatus.ACTIVE,
            )
        )
        await session.commit()


async def approved_driver(
    client: AsyncClient,
    session_factory: Any,
    payload: dict = DRIVER,
    *,
    plate_number: str = "AMM-4242",
    category: str = "economy",
    subscribed: bool = True,
) -> dict:
    """كبتن معتمد بمركبة واشتراكٍ ساري — كلاهما يُكتب مباشرة.

    `subscribed=False` للاختبارات التي تريد كبتناً بلا اشتراك: لا رحلات له
    (SPEC القسم 8)، وهو ما تتحقق منه `test_subscriptions.py`.
    """
    body = await register(client, payload)
    headers = auth(body)

    created = await client.post(
        "/drivers/me/vehicles",
        json={
            "make": "Toyota",
            "model": "Camry",
            "year": 2021,
            "color": "أبيض",
            "plate_number": plate_number,
            "category": category,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text

    async with session_factory() as session:
        driver = await session.scalar(
            select(Driver).where(Driver.user_id == uuid.UUID(body["user"]["id"]))
        )
        driver.status = DriverStatus.APPROVED
        await session.commit()
        driver_id = driver.id

    if subscribed:
        await subscribe_driver(session_factory, driver_id)

    return {
        "headers": headers,
        "token": token_of(body),
        "driver_id": driver_id,
        # محفظة الكبتن مفتاحها `users.id` لا `drivers.id`
        "user_id": body["user"]["id"],
    }


async def topup_wallet(
    client: AsyncClient,
    admin_headers: dict,
    user_id: str,
    amount: str,
    *,
    method: str = "cash",
) -> dict:
    """يضع رصيداً في محفظة عبر المسار الحقيقي — لا كتابة مباشرة في الدفتر."""
    response = await client.post(
        f"/admin/wallets/{user_id}/topups",
        json={"method": method, "amount": amount, "reference": "شحن اختبار"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def wallet_of(client: AsyncClient, headers: dict) -> dict:
    response = await client.get("/wallet/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def bring_online(
    client: AsyncClient, driver: dict, location: dict = NEAR_PICKUP
) -> None:
    """أونلاين + أول بث موقع — بهما معاً يدخل الكبتن دائرة التوزيع."""
    online = await client.post("/drivers/me/online", headers=driver["headers"])
    assert online.status_code == 200, online.text
    located = await client.post(
        "/drivers/me/location",
        json={**location, "heading": 90},
        headers=driver["headers"],
    )
    assert located.status_code == 204, located.text


# -------------------------------------------------------------------- الانتظار


async def wait_until(
    predicate: Callable[[], Awaitable[Any]],
    *,
    timeout: float = 10.0,
    interval: float = 0.05,
    message: str = "لم يتحقق الشرط",
) -> Any:
    """ينتظر أثر مهمة تعمل في الخلفية — التوزيع لا يستجيب لحظياً."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = await predicate()
        if result:
            return result
        await asyncio.sleep(interval)
    raise AssertionError(message)


async def wait_for_offer(ride_id: str, driver_id: uuid.UUID | None = None) -> uuid.UUID:
    """ينتظر أن يعرض التوزيع الرحلة (على كبتن بعينه إن طُلب)."""
    redis = get_redis_client()

    async def _offered() -> uuid.UUID | None:
        offered = await dispatch.current_offer(redis, uuid.UUID(ride_id))
        if offered is None or (driver_id is not None and offered != driver_id):
            return None
        return offered

    return await wait_until(_offered, message="لم يصل عرض الرحلة لأي كبتن")


async def wait_for_status(
    client: AsyncClient, headers: dict, ride_id: str, expected: str
) -> dict:
    async def _reached() -> dict | None:
        response = await client.get(f"/rides/{ride_id}", headers=headers)
        body = response.json()
        return body if body.get("status") == expected else None

    return await wait_until(
        _reached, message=f"لم تصل الرحلة إلى الحالة «{expected}»"
    )


# ---------------------------------------------------------------------- الرحلة


async def request_ride(
    client: AsyncClient, headers: dict, *, category: str = "economy"
) -> dict:
    response = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": category},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def accepted_ride(
    client: AsyncClient, rider_headers: dict, driver: dict
) -> dict:
    """المسار الكامل حتى القبول — أساس كل اختبار لما بعد الإسناد."""
    ride = await request_ride(client, rider_headers)
    await wait_for_offer(ride["id"], driver["driver_id"])

    accepted = await client.post(
        f"/rides/{ride['id']}/accept", headers=driver["headers"]
    )
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


async def started_ride(client: AsyncClient, rider_headers: dict, driver: dict) -> dict:
    """رحلة في `in_progress` — من هنا يبدأ تسجيل المسار (SPEC القسم 5.7)."""
    ride = await accepted_ride(client, rider_headers, driver)
    for step in ("arrive", "start"):
        response = await client.post(
            f"/rides/{ride['id']}/{step}", headers=driver["headers"]
        )
        assert response.status_code == 200, response.text
    return response.json()


async def completed_ride(
    client: AsyncClient, rider_headers: dict, driver: dict
) -> dict:
    """رحلة منتهية — أساس كل اختبار دفعٍ أو تقييم."""
    ride = await started_ride(client, rider_headers, driver)
    response = await client.post(
        f"/rides/{ride['id']}/complete", headers=driver["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


async def broadcast_location(
    client: AsyncClient, driver: dict, lat: float, lng: float
) -> None:
    response = await client.post(
        "/drivers/me/location",
        json={"lat": lat, "lng": lng, "heading": 90},
        headers=driver["headers"],
    )
    assert response.status_code == 204, response.text


# ---------------------------------------------------------------------- الدفع


async def pay_ride(
    client: AsyncClient,
    rider_headers: dict,
    ride_id: str,
    method: str,
    *,
    key: str = "pay-key-0001",
) -> Any:
    return await client.post(
        f"/rides/{ride_id}/payments",
        json={"method": method, "idempotency_key": key},
        headers=rider_headers,
    )


async def enable_features(session_factory: Any, *keys: str) -> None:
    """يرفع مفاتيح الأردن — غياب الصف يعني معطّلاً، فلا اختبار يفترض التفعيل."""
    from app.models.enums import CountryCode
    from app.models.feature_flag import FeatureFlag

    async with session_factory() as session:
        for key in keys:
            session.add(
                FeatureFlag(
                    country_code=CountryCode.JO, feature_key=key, enabled=True
                )
            )
        await session.commit()


async def set_commission(
    session_factory: Any, percent: str, applies_to: str = "all_rides"
) -> None:
    """يفعّل عمولة الأردن **قبل** إنشاء الرحلة — النسبة تُجمَّد لحظة الإنشاء."""
    from app.models.commission import CommissionSetting
    from app.models.enums import CommissionAppliesTo, CountryCode

    async with session_factory() as session:
        session.add(
            CommissionSetting(
                country_code=CountryCode.JO,
                commission_enabled=True,
                commission_percent=Decimal(percent),
                applies_to=CommissionAppliesTo(applies_to),
            )
        )
        await session.commit()


async def set_cliq_alias(
    session_factory: Any, driver_id: uuid.UUID, alias: str = "0791234567"
) -> None:
    async with session_factory() as session:
        driver = await session.get(Driver, driver_id)
        driver.cliq_alias = alias
        await session.commit()


async def add_route_points(
    session_factory: Any, ride_id: str, coordinates: list[tuple[float, float]]
) -> None:
    """يكتب مساراً معلوم الشكل مباشرةً.

    مسار الالتقاط من بثّ الكبتن تختبره `test_route.py` بنفسه؛ اختبارات السعر
    تحتاج مسافةً معلومة لا سباقاً مع نافذة أخذ العيّنة.

    `created_at` صريحٌ متصاعد: هو ما يرتّب الخط في `ST_MakeLine`، و`now()`
    الافتراضية تعطي الصفوف كلها نفس اللحظة فيصير الترتيب عشوائياً بالمُعرّف
    وتخرج مسافةٌ غير التي رسمها الاختبار.
    """
    from app.models.ride import RideRoutePoint, make_point

    base = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    async with session_factory() as session:
        for index, (lat, lng) in enumerate(coordinates):
            session.add(
                RideRoutePoint(
                    ride_id=uuid.UUID(ride_id),
                    point=make_point(lat, lng),
                    created_at=base + timedelta(seconds=20 * index),
                )
            )
        await session.commit()


async def payments_of(client: AsyncClient, headers: dict, ride_id: str) -> dict:
    response = await client.get(f"/rides/{ride_id}/payments", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ البطاقة


TELR_STORE_ID = "test-store-42"
TELR_AUTH_KEY = "test-auth-key"


async def enable_card_provider(
    session_factory: Any, *, use_mock: bool = True, country: str = "JO"
) -> None:
    """يُدخل عقد Telr للأردن ويفعّله — فيُرفع `card_enabled` تلقائياً.

    عبر `credentials_service.upsert` لا بكتابةٍ مباشرة: مزامنةُ مفتاح الميزة مع
    العقد جزءٌ من السلوك المُختبَر (SPEC القسم 4)، ولا يُقلَّد بيدٍ في اختبار.
    """
    from app.models.enums import CountryCode, ProviderKey
    from app.services.providers import credentials as credentials_service

    async with session_factory() as session:
        await credentials_service.upsert(
            session,
            provider_key=ProviderKey.TELR,
            country_code=CountryCode(country),
            values={
                "store_id": TELR_STORE_ID,
                "auth_key": TELR_AUTH_KEY,
                "test_mode": True,
                "use_mock": use_mock,
            },
            is_active=True,
        )
        await session.commit()


async def card_order_of(client: AsyncClient, headers: dict, cart_id: str) -> dict:
    response = await client.get(f"/payments/card/orders/{cart_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def simulate_card(
    client: AsyncClient, headers: dict, cart_id: str, outcome: str = "paid"
) -> Any:
    """يحاكي ضغطة الدافع على صفحة المزود الوهمي."""
    return await client.post(
        f"/payments/card/mock/{cart_id}",
        json={"outcome": outcome},
        headers=headers,
    )


# ------------------------------------------- مزودو المرحلة 8 (وهميون)


COMPANY_CLIQ_ALIAS = "TAXO.JO"


async def _enable_provider(
    session_factory: Any,
    provider_key: str,
    values: dict,
    *,
    country: str | None = None,
) -> None:
    """يُدخل عقد مزودٍ ويفعّله عبر الخدمة نفسها لا بكتابةٍ مباشرة.

    مزامنةُ مفتاح الميزة مع العقد جزءٌ من السلوك المُختبَر (SPEC القسم 4).
    """
    from app.models.enums import CountryCode, ProviderKey
    from app.services.providers import credentials as credentials_service

    async with session_factory() as session:
        await credentials_service.upsert(
            session,
            provider_key=ProviderKey(provider_key),
            country_code=CountryCode(country) if country else None,
            values=values,
            is_active=True,
        )
        await session.commit()


async def enable_sms_provider(session_factory: Any, **overrides: Any) -> None:
    """عقد رسائل وهمي — يحوّل الدخول كله إلى OTP (SPEC القسم 15/أ)."""
    await _enable_provider(
        session_factory,
        "sms",
        {
            "provider_name": "mock",
            "api_key": "sms-secret",
            "sender_id": "TAXO",
            "use_mock": True,
        }
        | overrides,
    )


async def enable_push_provider(session_factory: Any, **overrides: Any) -> None:
    await _enable_provider(
        session_factory,
        "fcm",
        {"project_id": "taxo-test", "use_mock": True} | overrides,
    )


async def enable_cliq_provider(
    session_factory: Any, *, country: str = "JO", **overrides: Any
) -> None:
    await _enable_provider(
        session_factory,
        "cliq_acquirer",
        {
            "merchant_id": "merchant-42",
            "api_key": "cliq-secret",
            "company_alias": COMPANY_CLIQ_ALIAS,
            "use_mock": True,
        }
        | overrides,
        country=country,
    )


async def enable_payout_provider(
    session_factory: Any, *, country: str = "JO", **overrides: Any
) -> None:
    await _enable_provider(
        session_factory,
        "payout",
        {"api_key": "payout-secret", "use_mock": True} | overrides,
        country=country,
    )


async def read_otp(phone: str) -> str:
    """يقرأ الرمز من رسالة المزود الوهمي — كما يقرؤه صاحب الهاتف."""
    import re

    from app.services.sms import last_message

    body = await last_message(get_redis_client(), phone)
    assert body is not None, f"لم تصل رسالة إلى {phone}"
    match = re.search(r"\d{6}", body)
    assert match is not None, f"لا رمز في الرسالة: {body}"
    return match.group()


async def fast_forward_otp_cooldown(phone: str) -> None:
    """«مرّت دقيقة» بلا انتظار دقيقة.

    مهلةُ إعادة الإرسال تُختبر مرةً واحدة في `test_resend_has_a_cooldown`؛
    وبقيةُ الاختبارات تحتاج رمزاً ثانياً لا أن تعيد اختبار الحارس.
    """
    from app.services import otp

    await get_redis_client().delete(otp.COOLDOWN_KEY.format(phone=phone))


async def register_device(
    client: AsyncClient,
    headers: dict,
    *,
    device_id: str = "device-1",
    token: str = "fcm-token-1",
    platform: str = "android",
) -> dict:
    response = await client.put(
        "/me/devices",
        json={"device_id": device_id, "token": token, "platform": platform},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def pushes_to(token: str) -> list[dict]:
    """ما «وصل» جهازاً بعينه من المزود الوهمي."""
    from app.services.push import sent_messages

    return await sent_messages(get_redis_client(), token)


def mock_webhook_payload(cart_id: str, *, store_id: str = TELR_STORE_ID) -> dict:
    """حمولة إشعارٍ موقّعةً بتوقيع المزود الوهمي.

    بلا مبلغ ولا حالة عمداً: الخلفية لا تقرأ منهما شيئاً أصلاً، وحمولةٌ تحملهما
    في اختبارٍ توهم أنها تُقرأ.
    """
    return {
        "tran_store": store_id,
        "tran_cartid": cart_id,
        "tran_ref": f"mock-{cart_id}",
        "tran_check": f"mock-check-{cart_id}",
    }
