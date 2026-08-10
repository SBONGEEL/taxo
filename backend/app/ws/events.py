"""أحداث الزمن الحقيقي وقنواتها على Redis pub/sub (SPEC القسم 10).

الناشر لا يعرف من يستمع: الراوترات وخدمة التوزيع تنشر في قناة صاحب الشأن،
وكل اتصال WebSocket يشترك في قنواته وحده. هكذا يعمل النظام بأكثر من عامل
uvicorn بلا حالة مشتركة في الذاكرة، ولا يحتاج الناشر أن يكون في نفس العملية
التي يجلس فيها الاتصال.

**البث يأتي دائماً بعد الـ commit**: قبله قد نُعلن حالةً تُلغى بعد لحظة.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from redis.asyncio import Redis

from app.models.ride import Ride
from app.schemas.ride import RideOut


class RideEvent(StrEnum):
    """أحداث الرحلة المبثوثة.

    الخمسة الأولى نصّ عليها SPEC القسم 10 وتُبث للطرفين. البقية لازمة لتشغيل
    ما وصفه SPEC نفسه: `ride_offer` و`offer_expired` هما بطاقة الطلب الواردة
    وعدّاد العشرين ثانية في تطبيق الكبتن (القسم 12.3)، و`no_driver_found`
    مخرج التوزيع حين تنفد المحاولات (القسم 5.3) — لا يعرفه الراكب بغير بث،
    و`driver_connection_lost`/`driver_reconnected` هما «تنبيه الطرفين» عند
    انقطاع الكبتن أثناء الرحلة (القسم 5).
    """

    DRIVER_ASSIGNED = "driver_assigned"
    DRIVER_ARRIVED = "driver_arrived"
    RIDE_STARTED = "ride_started"
    RIDE_COMPLETED = "ride_completed"
    RIDE_CANCELLED = "ride_cancelled"
    NO_DRIVER_FOUND = "no_driver_found"
    RIDE_OFFER = "ride_offer"
    OFFER_EXPIRED = "offer_expired"
    DRIVER_CONNECTION_LOST = "driver_connection_lost"
    DRIVER_RECONNECTED = "driver_reconnected"


class PaymentEvent(StrEnum):
    """أحداث شاشة الدفع (SPEC القسم 6.2).

    نوعٌ مستقل عن `RideEvent` لأنه لا يصف انتقالاً في حالة الرحلة بل خطوةً في
    تحصيل أجرتها، ولا يُبث للطرفين بل لطرفٍ واحد. `cliq_transfer_submitted` هو
    «إشعارٌ فوري للكبتن» في القسم 6.2: الراكب أدخل مرجع حوالته، فتظهر عند
    الكبتن بطاقةُ «وصلني / لم يصلني» — وهي شاشةُ المرحلة 10.
    """

    CLIQ_TRANSFER_SUBMITTED = "cliq_transfer_submitted"


class SubscriptionEvent(StrEnum):
    """أحداث اشتراك الكبتن (SPEC القسم 8).

    نوعٌ مستقل عن `RideEvent` لأنه لا يخص رحلةً ولا يُبث إلا لصاحبه: «إشعار قبل
    الانتهاء بـ 24 ساعة» و«انتهى اشتراكك» في القسم 8. القناة نفسها
    (`ws:user:{id}`) لأن الوجهة واحدة — تطبيق الكبتن وهو مفتوح؛ وإشعارات Push
    (FCM) تأتي في **المرحلة 8** فتصل الكبتنَ والتطبيقُ مغلق (القسم 15/أ).
    """

    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    SUBSCRIPTION_EXPIRED = "subscription_expired"


def user_channel(user_id: uuid.UUID | str) -> str:
    """قناة المستخدم — أحداث رحلاته وعروض الطلبات إن كان كبتناً."""
    return f"ws:user:{user_id}"


def driver_location_channel(driver_id: uuid.UUID | str) -> str:
    """بث موقع كبتن بعينه — يشترك فيه راكبه المُسنَد وحده."""
    return f"ws:driver_location:{driver_id}"


async def publish(redis: Redis, channel: str, payload: dict[str, Any]) -> None:
    await redis.publish(channel, json.dumps(payload, ensure_ascii=False))


async def publish_ride_event(redis: Redis, ride: Ride, event: RideEvent) -> None:
    """يبث حدث الرحلة لطرفيها معاً (SPEC القسم 10).

    يتطلب رحلةً محمّلة العلاقات (`driver.user` و`driver.vehicles`) لأن الحمولة
    هي `RideOut` نفسها التي يعيدها REST — فيصل للواجهة تمثيل واحد لا تمثيلان.
    """
    payload = {
        "type": event.value,
        "ride": RideOut.from_ride(ride).model_dump(mode="json"),
    }

    await publish(redis, user_channel(ride.rider_id), payload)
    if ride.driver is not None:
        await publish(redis, user_channel(ride.driver.user_id), payload)


async def publish_ride_offer(
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    ride: Ride,
    distance_to_pickup_km: float,
    expires_in_seconds: int,
) -> None:
    """بطاقة الطلب الواردة للكبتن المعروض عليه وحده (SPEC القسم 12.3).

    لا تحمل هوية الراكب: نقطة الانطلاق والمسافة إليها والسعر والمهلة فقط.
    """
    await publish(
        redis,
        user_channel(driver_user_id),
        {
            "type": RideEvent.RIDE_OFFER.value,
            "ride": RideOut.from_ride(ride).model_dump(mode="json"),
            "distance_to_pickup_km": distance_to_pickup_km,
            "expires_in_seconds": expires_in_seconds,
        },
    )


async def publish_offer_expired(
    redis: Redis, *, driver_user_id: uuid.UUID, ride_id: uuid.UUID
) -> None:
    """انتهت المهلة أو رفض الكبتن — تُطوى البطاقة من شاشته."""
    await publish(
        redis,
        user_channel(driver_user_id),
        {"type": RideEvent.OFFER_EXPIRED.value, "ride_id": str(ride_id)},
    )


async def publish_cliq_transfer(
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    ride_id: uuid.UUID,
    payment_id: uuid.UUID,
    amount: str,
    currency: str,
    transfer_reference: str,
) -> None:
    """أدخل الراكب مرجع حوالته — تصل البطاقة الكبتنَ وحده (SPEC القسم 6.2).

    الحمولة هي ما تحتاجه بطاقة التأكيد لا الدفعةَ كاملة: كم، وبأي مرجع، وعلى
    أي رحلة. لا هوية راكبٍ فيها كما لا هوية في بطاقة الطلب.
    """
    await publish(
        redis,
        user_channel(driver_user_id),
        {
            "type": PaymentEvent.CLIQ_TRANSFER_SUBMITTED.value,
            "ride_id": str(ride_id),
            "payment_id": str(payment_id),
            "amount": amount,
            "currency": currency,
            "transfer_reference": transfer_reference,
        },
    )


async def publish_subscription_event(
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    event: SubscriptionEvent,
    expires_at: datetime,
) -> None:
    """تنبيه اشتراكٍ للكبتن وحده — لا شأن لأحد غيره به."""
    await publish(
        redis,
        user_channel(driver_user_id),
        {"type": event.value, "expires_at": expires_at.isoformat()},
    )


async def publish_driver_location(
    redis: Redis,
    *,
    driver_id: uuid.UUID,
    lat: float,
    lng: float,
    heading: float | None,
) -> None:
    """موقع الكبتن كل ثلاث ثوانٍ — يصل راكبه المُسنَد إن كان متصلاً."""
    await publish(
        redis,
        driver_location_channel(driver_id),
        {
            "type": "driver_location",
            "driver_id": str(driver_id),
            "lat": lat,
            "lng": lng,
            "heading": heading,
        },
    )
