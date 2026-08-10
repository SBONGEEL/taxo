"""الإشعارات المعاملاتية: نفس الحدث على قناتين (SPEC القسم 10 — المرحلة 8).

`ws/events.py` يبث إلى Redis pub/sub فيصل التطبيقَ **وهو مفتوح**. هذا الملف
يضيف القناة الثانية — Push — فيصل الحدثُ صاحبَه والشاشة مغلقة. ولذلك صار كل
مسارٍ يبث حدثاً يستدعي دالةً من هنا بدل `events` مباشرة: **قناةٌ واحدةٌ
تنسى حدثاً** هي بالضبط ما يمنعه أن يكون للبثّ بابٌ واحد.

ثلاث قواعد:

- **لا Push لجهازٍ سوكته نشط** (القسم 10). ومن ضمن ما يحلّه هذا مجاناً:
  الفاعلُ نفسه لا يصله إشعارٌ بفعله — من ضغط «وصلت» تطبيقُه مفتوحٌ بالتعريف.
- **طلب الرحلة بأولوية عالية**: مهلة القبول عشرون ثانية، وDoze mode يؤجّل
  الإشعار العادي دقائق — فتصل البطاقة بعد أن انتقل الطلب لغيره.
- **الفشل يُبتلع ويُسجَّل.** إشعارٌ لم يُرسل خسارةٌ أهون من رحلةٍ لم تبدأ لأن
  خدمةً بعيدة تأخرت — نفس منطق التقاط نقاط المسار في `services/route.py`.

وهذه الفئة **غير قابلة للإطفاء من المستخدم**: جزءٌ من الخدمة لا إعلان.
`users.marketing_push_enabled` لا يُقرأ هنا إطلاقاً — بيتُه
`services/campaigns.py`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.ride import Ride
from app.services import devices, presence
from app.services.push import PushMessage, PushResult, get_push_provider_or_none
from app.ws import events
from app.ws.events import RideEvent, SubscriptionEvent

logger = logging.getLogger(__name__)

# نصوص الأحداث الخمسة التي ينص عليها القسم 10، ومعها `no_driver_found` لأنه
# مخرجُ التوزيع الذي لا يعرفه الراكب بغير بثّ. ما ليس هنا يبقى على WebSocket
# وحده: `ride_offer` له دالته (أولوية عالية)، وأحداثُ انقطاع الكبتن تخص
# شاشةً مفتوحة أثناء رحلة جارية.
RIDE_EVENT_TEXT: dict[RideEvent, tuple[str, str]] = {
    RideEvent.DRIVER_ASSIGNED: ("تم قبول رحلتك", "الكبتن في طريقه إلى نقطة الانطلاق"),
    RideEvent.DRIVER_ARRIVED: ("وصل الكبتن", "الكبتن بانتظارك في نقطة الانطلاق"),
    RideEvent.RIDE_STARTED: ("بدأت الرحلة", "رحلة موفقة"),
    RideEvent.RIDE_COMPLETED: ("انتهت الرحلة", "شاشة الدفع بانتظارك"),
    RideEvent.RIDE_CANCELLED: ("أُلغيت الرحلة", "تم إلغاء الرحلة"),
    RideEvent.NO_DRIVER_FOUND: (
        "لم نجد كبتناً متاحاً",
        "لم يقبل أي كبتن الطلب — حاول مرة أخرى",
    ),
}

SUBSCRIPTION_EVENT_TEXT: dict[SubscriptionEvent, tuple[str, str]] = {
    SubscriptionEvent.SUBSCRIPTION_EXPIRING: (
        "اشتراكك يقارب الانتهاء",
        "يتبقى أقل من 24 ساعة — جدّد لتبقى ضمن التوزيع",
    ),
    SubscriptionEvent.SUBSCRIPTION_EXPIRED: (
        "انتهى اشتراكك",
        "لن تصلك طلبات جديدة حتى التجديد",
    ),
}


# ------------------------------------------------------------------ الإرسال


async def notify_user(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: uuid.UUID,
    message: PushMessage,
) -> PushResult:
    """يرسل إشعاراً إلى أجهزة مستخدمٍ **غير المفتوحة الآن**.

    الـ commit هنا مقصود ومحدود: تعطيلُ رمزٍ ميت أثرٌ يخص هذا الملف وحده،
    ويقع بعد أن أنهى المستدعي معاملته (البثّ دائماً بعد الـ commit) — فلا
    معاملةَ تُقطع، ولا يبقى تعطيلٌ معلّقاً حتى يمر عليه commit غريب.
    """
    provider = await get_push_provider_or_none(session)
    if provider is None:
        return PushResult()  # لا عقد FCM — الحدث وصل على WebSocket

    open_devices = await presence.active_devices(redis, user_id)
    tokens = await devices.active_tokens_for(
        session, user_id, exclude_device_ids=open_devices
    )
    if not tokens:
        return PushResult()

    result = await provider.send(tokens, message)
    if result.invalid_tokens:
        await devices.deactivate_tokens(session, result.invalid_tokens)
        await session.commit()
    return result


async def _safe_notify(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: uuid.UUID,
    message: PushMessage,
) -> None:
    """إشعارٌ لا يُسقط ما استدعاه مهما كان جواب المزود."""
    try:
        await notify_user(session, redis, user_id=user_id, message=message)
    except Exception:  # pragma: no cover - يعتمد على عطل خارجي
        logger.exception("تعذّر إرسال إشعار إلى %s", user_id)


# ------------------------------------------------------- أحداث الرحلة


async def publish_ride_event(
    session: AsyncSession, redis: Redis, ride: Ride, event: RideEvent
) -> None:
    """بثُّ الحدث على WebSocket ثم Push لمن كان تطبيقه مغلقاً.

    يحل محل `events.publish_ride_event` في كل مسار: بابٌ واحد للقناتين، فلا
    تُضاف قناةٌ لحدثٍ وتُنسى لآخر.
    """
    await events.publish_ride_event(redis, ride, event)

    text = RIDE_EVENT_TEXT.get(event)
    if text is None:
        return

    message = PushMessage(
        title=text[0],
        body=text[1],
        data={"type": event.value, "ride_id": str(ride.id)},
    )
    await _safe_notify(session, redis, user_id=ride.rider_id, message=message)
    if ride.driver is not None:
        await _safe_notify(
            session, redis, user_id=ride.driver.user_id, message=message
        )


async def publish_ride_offer(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    ride: Ride,
    distance_to_pickup_km: float,
    expires_in_seconds: int,
) -> None:
    """بطاقة الطلب الواردة — **بأولوية عالية** (SPEC القسم 10/12.3)."""
    await events.publish_ride_offer(
        redis,
        driver_user_id=driver_user_id,
        ride=ride,
        distance_to_pickup_km=distance_to_pickup_km,
        expires_in_seconds=expires_in_seconds,
    )

    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title="طلب رحلة جديد",
            body=(
                f"نقطة الانطلاق على بُعد {distance_to_pickup_km} كم — "
                f"{ride.estimated_fare} {ride.currency.value}"
            ),
            data={
                "type": RideEvent.RIDE_OFFER.value,
                "ride_id": str(ride.id),
                "expires_in_seconds": str(expires_in_seconds),
            },
            high_priority=True,
        ),
    )


# ----------------------------------------------------- أحداث شاشة الدفع


async def publish_cliq_transfer(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    ride_id: uuid.UUID,
    payment: Payment,
) -> None:
    """«إشعار فوري للكبتن» بعد أن يُدخل الراكب مرجع حوالته (SPEC القسم 6.2).

    أولويةٌ عادية لا عالية: بطاقة التأكيد ليس لها عدّاد عشرين ثانية كبطاقة
    الطلب، والمال في حساب الكبتن أصلاً — التأخر دقيقةً لا يُضيّع شيئاً.
    """
    await events.publish_cliq_transfer(
        redis,
        driver_user_id=driver_user_id,
        ride_id=ride_id,
        payment_id=payment.id,
        amount=str(payment.amount),
        currency=payment.currency.value,
        transfer_reference=payment.cliq_transfer_reference or "",
    )

    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title="حوالة كليك بانتظار تأكيدك",
            body=(
                f"{payment.amount} {payment.currency.value} — "
                f"مرجع الحوالة {payment.cliq_transfer_reference}"
            ),
            data={
                "type": events.PaymentEvent.CLIQ_TRANSFER_SUBMITTED.value,
                "ride_id": str(ride_id),
                "payment_id": str(payment.id),
            },
        ),
    )


# --------------------------------------------------- أحداث الاشتراك


async def publish_subscription_event(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    event: SubscriptionEvent,
    expires_at: datetime,
) -> None:
    """تنبيه الاشتراك — هذا ما كانت المرحلة 7 تنتظره من المرحلة 8."""
    await events.publish_subscription_event(
        redis,
        driver_user_id=driver_user_id,
        event=event,
        expires_at=expires_at,
    )

    title, body = SUBSCRIPTION_EVENT_TEXT[event]
    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title=title,
            body=body,
            data={"type": event.value, "expires_at": expires_at.isoformat()},
        ),
    )
