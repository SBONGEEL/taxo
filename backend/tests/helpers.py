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


async def approved_driver(
    client: AsyncClient,
    session_factory: Any,
    payload: dict = DRIVER,
    *,
    plate_number: str = "AMM-4242",
    category: str = "economy",
) -> dict:
    """كبتن معتمد بمركبة — الموافقة تتم من اللوحة (المرحلة 11) فنكتبها مباشرة."""
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
