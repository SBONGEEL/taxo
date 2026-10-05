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
from app.services import (
    dispatch,
    drivers as drivers_service,
    presence as socket_presence,
    rides as rides_service,
)
from app.services import token_service
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
    """يقبل الاتصال ثم يتحقق — القبول أولاً ليصل سبب الرفض للعميل برمز واضح.

    **والجلسةُ تُسأل مع التوكن** (SPEC §60): مقبسٌ لجلسةٍ أُبطلت لا يُفتح. ومُعرِّفُها
    يُحفظ على المقبس ليعرف `_pump` أيَّ أمرِ إغلاقٍ يخصّه.
    """
    sid = None
    try:
        user, sid = await token_service.authenticate_access(session, token)
    except AppError:
        user = None

    if user is None or user.is_blocked:
        await websocket.close(code=WS_UNAUTHORIZED, reason="جلسة غير صالحة")
        return None
    if not user.has_role(role):
        await websocket.close(code=WS_FORBIDDEN, reason="لا تملك صلاحية هذه القناة")
        return None
    websocket.state.sid = sid
    return user


#: رسالةُ التطبيق حين يغيب عن صاحبه أو يعود (`{"type": "visibility", "visible": bool}`)
VISIBILITY = "visibility"


@dataclass(slots=True)
class _Presence:
    """أثرُ جهاز هذا المقبس — **وحالُه: أمامَ صاحبه أم في الخلفية** (SPEC §٦١-ل/٣).

    **وما لم يبلّغ يُحسب أمامَه** (`background=False`): حكمُ اليوم حرفاً، فشيفرةٌ
    أقدمُ لا تبلّغ لا يتغيّر عليها شيء.
    """

    redis: Redis
    user_id: uuid.UUID
    device_id: str | None
    background: bool = False

    async def report(self, message: dict[str, Any]) -> None:
        """يقرأ رسالةَ الظهور ويكتبها **فوراً** — لا ينتظر ضربةَ الإنعاش التالية.

        **والتالفةُ تُبلَع**: رسالةٌ بلا `visible` منطقيٍّ لا تُسقط مقبساً ولا تُخمَّن.
        """
        visible = message.get("visible")
        if not isinstance(visible, bool) or self.device_id is None:
            return
        background = not visible
        if background == self.background:
            return
        self.background = background
        await socket_presence.heartbeat(
            self.redis, self.user_id, self.device_id, background=background
        )


async def _mark_present(presence: _Presence, device_id: str) -> None:
    """يُبقي أثر هذا الجهاز حياً ما دام المقبس مفتوحاً (SPEC القسم 10).

    الأثر هو ما يمنع إشعار Push المكرر: الحدث يصل هذه الشاشة عبر المقبس، فلا
    يُرسل إليها إشعارٌ ثانٍ. وينعش دورياً لا مرةً واحدة، فمقبسٌ مات فجأةً
    (شبكةٌ قُطعت بلا إغلاق) لا يحرم صاحبَه من الإشعارات إلا لدقيقة ونصف.
    **وحالُه يُجدَّد معه** (`_Presence`) — فعلامةُ الخلفية تعيش ما عاش أثرُه.
    """
    while True:
        await socket_presence.heartbeat(
            presence.redis,
            presence.user_id,
            device_id,
            background=presence.background,
        )
        await asyncio.sleep(socket_presence.REFRESH_SECONDS)


def _revocation(websocket: WebSocket, payload: dict[str, Any]) -> bool | None:
    """**أمرُ إغلاق الجلسة** (SPEC §60-ب/١) — يقرؤه كلُّ مقبسٍ يمرّر قناةَ صاحبه.

    `None`: ليس أمراً، فيُمرَّر كما هو. `True`: يخصّ جلسةَ هذا المقبس فيُغلق.
    `False`: لجلسةٍ أخرى من الحساب نفسِه، فيُبلَع — **ولا يصل التطبيقَ أبداً**.

    **ومقبسُ جلسةٍ أُبطلت لا يتلقّى بعدها شيئاً**: هاتفٌ ضاع وأُنهيت جلساتُه لا يبقى
    مقبسُه المفتوحُ يستقبل الطلباتِ والأحداث. والأمرُ للحساب كلِّه (`sid` فارغ) أو
    لجلسةٍ بعينها، وأمرُ الحساب كلِّه قد يستثني جلسةً (`keep`) — جلسةَ من غيّر
    كلمتَه بنفسه. **وفي بيتٍ واحد** لأن للمقابس حلقتين (`_pump` و`_rider_loop`)،
    **وكانت الثانيةُ تمرّره كأيِّ حدثٍ وتبقى مفتوحة** — أمسكه
    `test_auth_sessions.py` قبل أن يُودَع.
    """
    if payload.get("type") != events.SESSION_REVOKED:
        return None
    sid = getattr(websocket.state, "sid", None)
    mine = str(sid) if sid is not None else None
    target, keep = payload.get("sid"), payload.get("keep")
    if target is None:
        return keep is None or keep != mine
    return target == mine


async def _pump(websocket: WebSocket, subscription: Subscription) -> None:
    """يمرر ما يصل من Redis إلى المقبس كما هو — **إلا أمرَ إغلاق الجلسة** (`_revocation`)."""
    while True:
        payload = await subscription.poll(POLL_TIMEOUT_SECONDS)
        if payload is None:
            continue
        revoked = _revocation(websocket, payload)
        if revoked:
            await websocket.close(code=WS_UNAUTHORIZED, reason="انتهت الجلسة")
            return
        if revoked is None:
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
    presence: _Presence,
) -> None:
    while True:
        message = await websocket.receive_json()
        if isinstance(message, dict) and message.get("type") == VISIBILITY:
            await presence.report(message)
            continue
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
async def driver_socket(
    websocket: WebSocket,
    token: str = Query(...),
    device_id: str | None = Query(default=None),
) -> None:
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
        # **والعرضُ المعلَّق يُستعاد كما تُستعاد الرحلة** (2026-08-21):
        # `dispatch:driver_offer:{id}` قائمٌ في Redis بمهلته، **وكان المقبسُ
        # يصمت عنه** — فكبتنٌ نقر إشعارَ الطلب يفتح شاشةً فارغةً بينما عرضُه
        # حيٌّ بضع ثوانٍ، ثم يقرأ ذلك عطباً في التطبيق.
        #
        # **ومصدرُه Redis لا القاعدة**: هناك يعيش العرضُ وهناك ينتهي، فلا
        # بيتَ ثانٍ يمكن أن يقول غيرَ ما يقوله الموزِّع.
        pending = await dispatch.pending_offer_frame(session, redis, driver=driver)

    presence = _Presence(redis, user.id, device_id)
    try:
        async with Subscription(redis) as subscription:
            await subscription.subscribe(events.user_channel(user.id))
            # آخر حالة معروفة مع أول رسالة — عليها يعتمد الاسترجاع بعد انقطاع
            await websocket.send_json({"type": "connected", "active_ride": snapshot})
            if pending is not None:
                await websocket.send_json(pending)
            await _serve(
                websocket,
                _pump(websocket, subscription),
                _driver_reader(websocket, redis, context, presence),
                *_presence_tasks(presence),
            )
    except WebSocketDisconnect:
        pass
    finally:
        await _clear_presence(redis, user.id, device_id)
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


async def _rider_reader(
    websocket: WebSocket, state: _RiderState, presence: _Presence
) -> None:
    """يستقبل مركز الخريطة الحالي — حوله تُرسم السيارات القريبة. **ومعه ظهورُ التطبيق** (§٦١-ل/٣)."""
    while True:
        message = await websocket.receive_json()
        if isinstance(message, dict) and message.get("type") == VISIBILITY:
            await presence.report(message)
            continue
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
            redis,
            session,
            country_code=user.country_code,
            lat=state.lat,
            lng=state.lng,
            # نفس تصفية الخريطة في المقبس: لولاها لاختلفت أول رسمةٍ عن التي
            # تليها، وهو فرقٌ يظهر للراكبة كسيارةٍ تظهر ثم تختفي
            rider=user,
        )

    await websocket.send_json(
        {
            "type": "nearby_drivers",
            "drivers": [
                NearbyDriverOut.of(
                    presence,
                    ref=drivers_service.anonymous_ref(presence.driver_id, state.salt),
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
            # **أمرُ إغلاق الجلسة قبل أيِّ حدث** (SPEC §60) — ولا يُمرَّر إلى التطبيق
            revoked = _revocation(websocket, payload)
            if revoked:
                await websocket.close(code=WS_UNAUTHORIZED, reason="انتهت الجلسة")
                return
            if revoked is None:
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
async def rider_socket(
    websocket: WebSocket,
    token: str = Query(...),
    device_id: str | None = Query(default=None),
) -> None:
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

    presence = _Presence(redis, user.id, device_id)
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
                _rider_reader(websocket, state, presence),
                *_presence_tasks(presence),
            )
    except WebSocketDisconnect:
        pass
    finally:
        await _clear_presence(redis, user.id, device_id)


def _presence_tasks(presence: _Presence):
    """مهمةُ الإنعاش إن عرّف العميل جهازه، وإلا لا شيء.

    **مقبسٌ بلا `device_id` لا يمنع Push**: لا سبيل لمعرفة أيَّ جهازٍ هو،
    وحرمانُ كل أجهزة الحساب لأن أحدها مفتوح يعني هاتفاً في الجيب لا يرنّ
    لأن لوحاً على الطاولة مفتوح.
    """
    device_id = presence.device_id
    return () if not device_id else (_mark_present(presence, device_id),)


async def _clear_presence(
    redis: Redis, user_id: uuid.UUID, device_id: str | None
) -> None:
    """إغلاقُ المقبس يعيد Push إلى هذا الجهاز فوراً — بلا انتظار انتهاء الأثر."""
    if device_id:
        await socket_presence.leave(redis, user_id, device_id)


__all__ = ["ws_router"]
