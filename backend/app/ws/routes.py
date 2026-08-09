"""مقابس التتبع اللحظي (SPEC القسم 10).

مقبسان لا أكثر:

- `WS /ws/driver` — يبث الكبتن موقعه كل ثلاث ثوانٍ، ويستقبل بطاقات الطلبات
  الواردة وأحداث رحلته.
- `WS /ws/rider` — يستقبل الراكب سيارات الكباتن القريبين كل خمس ثوانٍ **قبل**
  الطلب (مجهّلة)، وموقع كبتنه هو وحده أثناء الرحلة، وأحداث الرحلة في الحالين.

**المصادقة عبر `?token=` لا ترويسة**: متصفحات الويب لا تسمح بترويسات مخصصة
عند فتح WebSocket. التوكن نفسه توكن الدخول قصير العمر.

الحالة كلها في Redis: القاعدة تُسأل عند الاتصال وعند بث الجيران فقط، لا مع
كل رسالة موقع.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.exceptions import AppError
from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.driver import DriverLocationIn, NearbyDriverOut
from app.schemas.ride import RideOut
from app.services import drivers as drivers_service, rides as rides_service
from app.services.token_service import access_token_subject
from app.ws import events
from app.ws.hub import Subscription

ws_router = APIRouter(prefix="/ws", tags=["realtime"])

# رموز إغلاق خاصة بالتطبيق (المجال 4000+ محجوز للتطبيقات في معيار WebSocket)
WS_UNAUTHORIZED = 4401
WS_FORBIDDEN = 4403

# كل خمس ثوانٍ تتحرك سيارات الخريطة عند الراكب (SPEC القسم 10)
NEARBY_BROADCAST_SECONDS = 5.0
# مهلة انتظار رسالة pub/sub قبل العودة لالتزامات الحلقة الدورية
POLL_TIMEOUT_SECONDS = 0.5


# ------------------------------------------------------------------ المصادقة


async def _authenticate(
    session: AsyncSession, websocket: WebSocket, token: str, role: UserRole
) -> User | None:
    """يقبل الاتصال ثم يتحقق — القبول أولاً ليصل سبب الرفض للعميل برمز واضح."""
    try:
        user = await session.get(User, access_token_subject(token))
    except AppError:
        user = None

    if user is None or user.is_blocked:
        await websocket.close(code=WS_UNAUTHORIZED, reason="جلسة غير صالحة")
        return None
    if user.role != role:
        await websocket.close(code=WS_FORBIDDEN, reason="لا تملك صلاحية هذه القناة")
        return None
    return user


async def _pump(websocket: WebSocket, subscription: Subscription) -> None:
    """يمرر ما يصل من Redis إلى المقبس كما هو."""
    while True:
        payload = await subscription.poll(POLL_TIMEOUT_SECONDS)
        if payload is not None:
            await websocket.send_json(payload)


async def _serve(websocket: WebSocket, *coros) -> None:
    """يشغّل مهام المقبس حتى تنتهي أولاها (قطع الاتصال عادةً)."""
    tasks = [asyncio.create_task(coro) for coro in coros]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                await task


# ------------------------------------------------------------- مقبس الكبتن


async def _driver_reader(
    websocket: WebSocket,
    redis: Redis,
    context: drivers_service.PresenceContext,
) -> None:
    while True:
        message = await websocket.receive_json()
        if not isinstance(message, dict) or message.get("type") != "location":
            continue
        try:
            location = DriverLocationIn.model_validate(message)
        except ValidationError:
            # رسالة تالفة لا تُسقط اتصالاً؛ الكبتن على الطريق
            await websocket.send_json({"type": "error", "detail": "إحداثيات غير صالحة"})
            continue
        await drivers_service.report_location(
            redis,
            context,
            lat=location.lat,
            lng=location.lng,
            heading=location.heading,
        )


@ws_router.websocket("/driver")
async def driver_socket(websocket: WebSocket, token: str = Query(...)) -> None:
    """قناة الكبتن: بثّ الموقع صعوداً، والطلبات والأحداث نزولاً.

    فتح المقبس هو نفسه رفع مفتاح Online؛ إغلاقه ينزله ويسقط الكبتن من الفهرس
    الجغرافي فوراً — فلا يُعرض طلب على تطبيق مغلق.
    """
    await websocket.accept()
    redis = get_redis_client()

    async with SessionLocal() as session:
        user = await _authenticate(session, websocket, token, UserRole.DRIVER)
        if user is None:
            return

        driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
        if driver is None:
            await websocket.close(code=WS_FORBIDDEN, reason="ملف الكبتن غير موجود")
            return

        try:
            context = await drivers_service.go_online(session, driver)
        except AppError as exc:  # غير معتمد أو بلا مركبة مسجّلة
            await websocket.close(code=WS_FORBIDDEN, reason=exc.message)
            return
        await session.commit()

        active = await rides_service.active_ride_for_user(session, user)
        snapshot = RideOut.from_ride(active).model_dump(mode="json") if active else None

    try:
        async with Subscription(redis) as subscription:
            await subscription.subscribe(events.user_channel(user.id))
            # آخر حالة معروفة مع أول رسالة — عليها يعتمد الاسترجاع بعد انقطاع
            await websocket.send_json({"type": "connected", "active_ride": snapshot})
            await _serve(
                websocket,
                _pump(websocket, subscription),
                _driver_reader(websocket, redis, context),
            )
    except WebSocketDisconnect:
        pass
    finally:
        async with SessionLocal() as session:
            offline = await session.get(Driver, driver.id)
            if offline is not None:
                await drivers_service.go_offline(session, redis, offline)
                await session.commit()


# ------------------------------------------------------------- مقبس الراكب


@dataclass(slots=True)
class _RiderState:
    """ما يتبدل أثناء جلسة الراكب الواحدة."""

    # مِلح تجهيل ثابت للاتصال الواحد: يسمح بتنعيم الحركة ولا يعرّف كبتناً
    salt: str = field(default_factory=lambda: secrets.token_hex(16))
    driver_id: uuid.UUID | None = None
    lat: float | None = None
    lng: float | None = None


async def _rider_reader(websocket: WebSocket, state: _RiderState) -> None:
    """يستقبل مركز الخريطة الحالي — حوله تُرسم السيارات القريبة."""
    while True:
        message = await websocket.receive_json()
        if not isinstance(message, dict) or message.get("type") != "viewport":
            continue
        try:
            viewport = DriverLocationIn.model_validate(message)
        except ValidationError:
            await websocket.send_json({"type": "error", "detail": "إحداثيات غير صالحة"})
            continue
        state.lat, state.lng = viewport.lat, viewport.lng


async def _send_nearby(
    websocket: WebSocket, redis: Redis, user: User, state: _RiderState
) -> None:
    async with SessionLocal() as session:
        presences = await drivers_service.nearby_available(
            redis, session, country_code=user.country_code, lat=state.lat, lng=state.lng
        )

    await websocket.send_json(
        {
            "type": "nearby_drivers",
            "drivers": [
                NearbyDriverOut(
                    ref=drivers_service.anonymous_ref(presence.driver_id, state.salt),
                    lat=presence.lat,
                    lng=presence.lng,
                    heading=presence.heading,
                    vehicle_category=presence.vehicle_category,
                ).model_dump(mode="json")
                for presence in presences
            ],
        }
    )


async def _rider_loop(
    websocket: WebSocket,
    redis: Redis,
    user: User,
    state: _RiderState,
    subscription: Subscription,
) -> None:
    """حدثان في حلقة واحدة: ما يصل من Redis، وبثّ الجيران كل خمس ثوانٍ.

    اشتراك قناة الكبتن يتبدل من هنا وحده، فلا يتزاحم عليه منفذان.
    """
    next_nearby = 0.0

    while True:
        payload = await subscription.poll(POLL_TIMEOUT_SECONDS)
        if payload is not None:
            await _apply_event(payload, state, subscription)
            await websocket.send_json(payload)

        # أثناء الرحلة يرى الراكب كبتنه وحده — لا سيارات أخرى (SPEC القسم 10)
        if state.driver_id is None and state.lat is not None:
            now = time.monotonic()
            if now >= next_nearby:
                next_nearby = now + NEARBY_BROADCAST_SECONDS
                await _send_nearby(websocket, redis, user, state)


async def _apply_event(
    payload: dict[str, Any], state: _RiderState, subscription: Subscription
) -> None:
    """يفتح ويغلق اشتراك بثّ موقع الكبتن حسب مسار الرحلة."""
    event = payload.get("type")

    if event == events.RideEvent.DRIVER_ASSIGNED.value:
        driver = (payload.get("ride") or {}).get("driver") or {}
        driver_id = driver.get("id")
        if driver_id:
            state.driver_id = uuid.UUID(driver_id)
            await subscription.subscribe(events.driver_location_channel(driver_id))
        return

    if event in {
        events.RideEvent.RIDE_COMPLETED.value,
        events.RideEvent.RIDE_CANCELLED.value,
        events.RideEvent.NO_DRIVER_FOUND.value,
    } and state.driver_id is not None:
        await subscription.unsubscribe(
            events.driver_location_channel(state.driver_id)
        )
        state.driver_id = None


@ws_router.websocket("/rider")
async def rider_socket(websocket: WebSocket, token: str = Query(...)) -> None:
    """قناة الراكب: الخريطة قبل الطلب، وكبتنه أثناء الرحلة، وأحداثها دائماً."""
    await websocket.accept()
    redis = get_redis_client()
    state = _RiderState()

    async with SessionLocal() as session:
        user = await _authenticate(session, websocket, token, UserRole.RIDER)
        if user is None:
            return

        active = await rides_service.active_ride_for_user(session, user)
        snapshot = RideOut.from_ride(active).model_dump(mode="json") if active else None
        if active is not None and active.driver_id is not None:
            state.driver_id = active.driver_id

    try:
        async with Subscription(redis) as subscription:
            await subscription.subscribe(events.user_channel(user.id))
            if state.driver_id is not None:
                await subscription.subscribe(
                    events.driver_location_channel(state.driver_id)
                )
            await websocket.send_json({"type": "connected", "active_ride": snapshot})
            await _serve(
                websocket,
                _rider_loop(websocket, redis, user, state, subscription),
                _rider_reader(websocket, state),
            )
    except WebSocketDisconnect:
        pass


__all__ = ["ws_router"]
