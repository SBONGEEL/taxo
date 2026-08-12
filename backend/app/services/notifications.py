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

**و`data` تحمل القيم خاماً، و`title`/`body` لدرج النظام وحده.**

كلُّ إشعارٍ هنا يضع في `data` ما تحتاجه الواجهةُ لتصوغ جملتَها بنفسها: مبلغاً
ومعرّفَ رحلةٍ وعملةً وموعداً — لا جملةً مصوغة. والسبب أن الخلفية تكتب
`f"{amount} {currency}"` فيخرج «4.100 JOD» بخاناتٍ لاتينية ورمزٍ إنجليزي في
تطبيقٍ كلُّ أرقامه عربيةٌ-هندية وكلُّ نصّه عربي. والبديلُ الآخر — تعريبُ
الخانات في الخلفية — يضع قرارَ عرضٍ في طبقةٍ لا تعرف من يقرأ ولا بأيّ لغة،
ويمرّ بالمال في مكانٍ لا يجوز أن يمسّه إلا حسابياً.

فتبقى `title`/`body` مكتوبتين هنا لأن **درج نظام التشغيل يرسمهما والتطبيق
مغلق** ولا واجهةَ تصوغ شيئاً حينها؛ وتقرأ الشاشاتُ `data` وتصوغ نصَّها حين
تكون هي من يرسم (صندوق الوارد، والأوراق السفلية). وصفُّ صندوق الوارد يخزّن
الاثنين، فما لا تعرف الواجهةُ صياغته يبقى له نصُّ الخلفية احتياطاً.

**والحملات التسويقية استثناء**: نصُّها هو المحتوى نفسه كما كتبه المشرف، فلا
تصوغه الواجهة (`services/campaigns.py`).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import DriverDocument
from app.models.enums import DocumentReviewStatus
from app.models.payment import Payment
from app.models.ride import Ride, RideStop
from app.services import devices, documents, inbox, presence
from app.services.push import PushMessage, PushResult, get_push_provider_or_none
from app.ws import events
from app.ws.events import DocumentEvent, RideEvent, SubscriptionEvent

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
    # المحطات الوسيطة (المرحلة 12-ب). و`stop_wait_exceeded` **ليس هنا**: نصُّه
    # يختلف بين الطرفين — الراكبُ يُقال له إن العدّاد صار يُحتسب، والكبتنُ إن
    # له مخرجاً — فبابُه `publish_stop_wait_exceeded` كما لانقضاء مهلة كليك
    RideEvent.STOP_REACHED: ("وصل الكبتن إلى المحطة", "بانتظارك عند المحطة"),
    RideEvent.STOP_RESUMED: ("استُؤنفت الرحلة", "في الطريق إلى الوجهة التالية"),
}

# أحداثٌ تُرسل ولا تُحفظ في صندوق الوارد (المرحلة 9-ب).
#
# بطاقة الطلب وحدها: عمرُها عشرون ثانية بحكم `dispatch.OFFER_TIMEOUT_SECONDS`،
# وبعدها إمّا قُبلت — فحدثُ `driver_assigned` هو الأثر الصحيح — أو انتقلت
# لكبتنٍ آخر. وصفٌّ باقٍ يقول «طلب رحلة جديد» لطلبٍ مضى يفتح عند الضغط
# لا شيء، ويملأ الصندوق بما لا يُقرأ حتى يصير الجرس بلا معنى.
EPHEMERAL_KINDS: frozenset[str] = frozenset({RideEvent.RIDE_OFFER.value})

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
    """صندوقُ الوارد ثم Push — ولا يُسقط أيُّهما ما استدعاه.

    **الترتيب مقصود**: صفُّ الصندوق أثرُ الحدث لا أثرُ المزوّد، فيُكتب ولو
    لم يكن ثمة عقد FCM أصلاً، ولو كان الجهاز مفتوحاً فلا Push له. وهو ما
    يجعل الجرس في التطبيقين يعرض ما جرى لا ما نجح إرسالُه.

    ومحاولتان منفصلتان لا واحدة: فشلُ الكتابة لا يمنع الإرسال، وفشلُ
    الإرسال لا يمحو الأثر. وما في `EPHEMERAL_KINDS` يُرسل ولا يُحفظ.
    """
    # `kind` هو `data["type"]` نفسه، فلا يفترق ما يفتحه الضغط على الإشعار
    # عمّا يفتحه الضغط على صفّه في الصندوق
    kind = message.data.get("type", "")
    if kind not in EPHEMERAL_KINDS:
        try:
            await inbox.record(
                session,
                user_id=user_id,
                kind=kind,
                title=message.title,
                body=message.body,
                data=dict(message.data),
            )
            # الـ commit هنا كما في `notify_user`: البثّ دائماً بعد commit
            # المستدعي، فلا معاملةَ تُقطع ولا يبقى صفٌّ معلّقاً
            await session.commit()
        except Exception:  # pragma: no cover - يعتمد على عطل قاعدة
            logger.exception("تعذّر تسجيل إشعار في صندوق %s", user_id)
            await session.rollback()

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
        data={
            "type": event.value,
            "ride_id": str(ride.id),
            # القيمُ خامٌ لتصوغها الواجهة بلغتها وخاناتها (انظر ترويسة الملف)
            "amount": str(ride.final_fare or ride.estimated_fare),
            "currency": ride.currency.value,
            "status": ride.status.value,
        },
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
                "amount": str(ride.estimated_fare),
                "currency": ride.currency.value,
                "distance_to_pickup_km": str(distance_to_pickup_km),
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
        expires_at=(
            payment.cliq_confirmation_expires_at.isoformat()
            if payment.cliq_confirmation_expires_at
            else None
        ),
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
                "amount": str(payment.amount),
                "currency": payment.currency.value,
                "transfer_reference": payment.cliq_transfer_reference or "",
                "expires_at": (
                    payment.cliq_confirmation_expires_at.isoformat()
                    if payment.cliq_confirmation_expires_at
                    else ""
                ),
            },
        ),
    )


async def publish_cliq_confirmation_expired(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    rider_user_id: uuid.UUID,
    ride_id: uuid.UUID,
    payment: Payment,
) -> None:
    """انقضت المهلة فصارت الدفعة نزاعاً — **يُخطر الطرفان** (القسم 6.2/6).

    الكبتنُ ليعرف أن دفعته خرجت من يده إلى الإدارة، والراكبُ ليعرف أن تحويله
    لم يُؤكَّد وأن هناك من يفصل. وصمتُ النظام هنا يصنع تذكرتَي دعمٍ لا واحدة:
    كلٌّ منهما يسأل «أين مالي» ولا أحد أخبره أن شيئاً وقع أصلاً.

    ونصّان مختلفان لا نصٌّ واحد: ما يطمئن أحدَهما ليس ما يطمئن الآخر.
    """
    await events.publish_cliq_expired(
        redis,
        driver_user_id=driver_user_id,
        rider_user_id=rider_user_id,
        ride_id=ride_id,
        payment_id=payment.id,
    )

    data = {
        "type": events.PaymentEvent.CLIQ_CONFIRMATION_EXPIRED.value,
        "ride_id": str(ride_id),
        "payment_id": str(payment.id),
        "amount": str(payment.amount),
        "currency": payment.currency.value,
    }

    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title="انقضت مهلة تأكيد الحوالة",
            body=(
                f"{payment.amount} {payment.currency.value} — "
                "صارت الدفعة نزاعاً وتفصل فيها الإدارة."
            ),
            data=data,
        ),
    )

    await _safe_notify(
        session,
        redis,
        user_id=rider_user_id,
        message=PushMessage(
            title="لم يؤكّد الكبتن حوالتك",
            body=(
                f"{payment.amount} {payment.currency.value} — "
                "انتقلت الدفعة إلى الإدارة للفصل فيها."
            ),
            data=data,
        ),
    )


async def publish_stop_wait_exceeded(
    session: AsyncSession,
    redis: Redis,
    *,
    ride: Ride,
    stop: RideStop,
) -> None:
    """تجاوز الانتظارُ عند محطةٍ سقفَه — **يُخطر الطرفان** (القسم 5.10).

    ونصّان مختلفان لأن ما يعنيه الحدثُ لكلٍّ منهما مختلف: الراكبُ يُقال له إن
    العدّاد تجاوز المجاني — فيعرف أن ما يقرؤه صار يُحتسب، وهو ما يمنع مفاجأةَ
    شاشة الدفع؛ والكبتنُ يُقال له إن له **مخرجاً** — فبغيره يقف ينتظر ظانّاً
    أن لا خيار له إلا الانتظار.

    **ولا إنهاءَ في هذه الدالة ولا في مستدعيها**: الإنهاءُ فعلُ الكبتن.
    """
    driver_user_id = ride.driver.user_id if ride.driver is not None else None

    # البثُّ بنفس بابِ بقية أحداث الرحلة، فتصل الواجهةَ `RideOut` واحدة
    await events.publish_ride_event(redis, ride, RideEvent.STOP_WAIT_EXCEEDED)

    # قيمٌ خام لا جملةٌ مصوغة ولا رقمٌ منسّق (القسم 10)
    data = {
        "type": RideEvent.STOP_WAIT_EXCEEDED.value,
        "ride_id": str(ride.id),
        "stop_id": str(stop.id),
        "sequence": str(stop.sequence),
        "max_wait_minutes": str(ride.stop_max_wait_minutes_at_ride),
    }

    await _safe_notify(
        session,
        redis,
        user_id=ride.rider_id,
        message=PushMessage(
            title="تجاوز الانتظار عند المحطة",
            body="العدّاد تجاوز الدقائق المجانية — وما بعدها يُحتسب على الرحلة.",
            data=data,
        ),
    )

    if driver_user_id is not None:
        await _safe_notify(
            session,
            redis,
            user_id=driver_user_id,
            message=PushMessage(
                title="طال الانتظار عند المحطة",
                body="تجاوز الراكب سقف الانتظار — يمكنك إنهاء الرحلة عند هذه المحطة.",
                data=data,
            ),
        )


# ------------------------------------------------- مراجعة المستندات


async def publish_document_review(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    document: DriverDocument,
) -> None:
    """نتيجة مراجعة مستند إلى صاحبه (SPEC القسم 12/1 — المرحلة 9-ب).

    **سبب الرفض جزءٌ من الإشعار** لا تفصيلٌ يُطلب بعده: كبتنٌ يعرف أن رخصته
    رُفضت ولا يعرف لماذا يعيد رفع الصورة نفسها، ويبقى «قيد المراجعة» إلى
    الأبد. وأولويةٌ عادية: المراجعة تستغرق ساعات فلا معنى لإيقاظ الجهاز.
    """
    approved = document.review_status is DocumentReviewStatus.APPROVED
    event = (
        DocumentEvent.DOCUMENT_APPROVED if approved else DocumentEvent.DOCUMENT_REJECTED
    )
    label = documents.label_for(document.doc_type)

    await events.publish_document_event(
        redis,
        driver_user_id=driver_user_id,
        event=event,
        document_id=document.id,
        doc_type=document.doc_type.value,
        review_note=document.review_note,
    )

    if approved:
        title, body = "اعتُمد مستندك", f"{label}: مقبولة"
    else:
        title = "رُفض مستندك"
        body = f"{label}: {document.review_note or 'أعد رفعها بصورة أوضح'}"

    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title=title,
            body=body,
            data={
                "type": event.value,
                "document_id": str(document.id),
                "doc_type": document.doc_type.value,
                "review_status": document.review_status.value,
                "review_note": document.review_note or "",
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
            data={
                "type": event.value,
                "expires_at": expires_at.isoformat(),
            },
        ),
    )
