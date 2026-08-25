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
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver, DriverDocument
from app.models.enums import Currency, DocumentReviewStatus, DocumentType
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

# **ونصُّ الكبتن غيرُ نصِّ الراكب** — وجدته المرحلةُ ١٣ في صندوق الوارد على
# الجهاز: كانت الرسالةُ الواحدة تُرسل للطرفين، فيقرأ الكبتنُ في هاتفه «تم قبول
# رحلتك — الكبتن في طريقه إلى نقطة الانطلاق» **عن نفسه**. وهي القاعدةُ نفسُها
# التي دفعت `stop_wait_exceeded` خارج هذه الخريطة منذ 12-ب: طرفان لا يُقال لهما
# الشيءُ نفسُه.
#
# **و`None` تعني «ليس من شأنه»**: ما فعله بيده (قَبِل، وصل، بدأ) لا يُخبَر به،
# وصفٌّ في صندوقه يقول له ما فعله للتوّ يملأ الصندوق بما لا يُقرأ — نفسُ حجّة
# `EPHEMERAL_KINDS`. وما يقع **عليه** (إلغاءُ الراكب، انتهاءُ الرحلة، انقضاءُ
# البحث) يصله بنصٍّ يخصّه.
DRIVER_RIDE_EVENT_TEXT: dict[RideEvent, tuple[str, str] | None] = {
    RideEvent.DRIVER_ASSIGNED: None,
    RideEvent.DRIVER_ARRIVED: None,
    RideEvent.RIDE_STARTED: None,
    RideEvent.STOP_REACHED: None,
    RideEvent.STOP_RESUMED: None,
    RideEvent.RIDE_COMPLETED: ("انتهت الرحلة", "بانتظار اختيار الراكب طريقةَ الدفع"),
    RideEvent.RIDE_CANCELLED: ("أُلغيت الرحلة", "أُلغيت الرحلة — أنت متاحٌ لطلبٍ جديد"),
    RideEvent.NO_DRIVER_FOUND: None,
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
        "جدّد لتبقى ضمن التوزيع",
    ),
    SubscriptionEvent.SUBSCRIPTION_EXPIRED: (
        "انتهى اشتراكك",
        "لن تصلك طلبات جديدة حتى التجديد",
    ),
    SubscriptionEvent.SUBSCRIPTION_RENEWED: (
        "جُدِّد اشتراكك تلقائياً",
        "خُصم من محفظتك — وأنت ضمن التوزيع",
    ),
    # **الفشلُ يُقال صراحةً** (قرارُ المالك): من رفع مفتاحَ التجديد يظنّ نفسَه
    # مجدَّداً، فيستيقظ خارج التوزيع ولا يعرف لماذا. والصمتُ هنا أسوأُ من عدم
    # وجود الميزة أصلاً
    SubscriptionEvent.SUBSCRIPTION_RENEWAL_FAILED: (
        "تعذّر التجديد التلقائي",
        "لم يكفِ رصيدُ محفظتك — جدّد يدوياً لتبقى ضمن التوزيع",
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

    if ride.driver is None:
        return
    driver_text = DRIVER_RIDE_EVENT_TEXT.get(event, text)
    if driver_text is None:
        return
    await _safe_notify(
        session,
        redis,
        user_id=ride.driver.user_id,
        # **الحمولةُ نفسُها والجملةُ غيرُها**: `data` خامٌ لا لغةَ فيه، والعنوانُ
        # والنصُّ لدرج النظام — وهما ما يختلف بين طرفين
        message=PushMessage(title=driver_text[0], body=driver_text[1], data=message.data),
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


async def publish_document_expiring(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_type: DocumentType,
    expires_on,
    days_left: int,
) -> None:
    """تنبيهٌ قبل الانتهاء — **ويقول إن الحساب ما زال يعمل** (البند ج).

    **وجملتُه تذكر الأثر لا التاريخَ وحدَه**: «تنتهي بعد ٧ أيام» تُقرأ خبراً،
    و«ويُعلَّق حسابُك يومَها» تُقرأ أمراً. ومن قرأ الأولى وحدَها يؤجّل.

    **و`data` خامٌ بلا جملة** كبقية الإشعارات: الرقمُ رقمٌ والتاريخُ تاريخ،
    والشاشةُ تؤلّف — فإرسالُ «٧ أيام» مؤلَّفةً يضع لغةً في طبقةٍ لا تعرف
    قارئَها، ويمرّ المالُ والأرقامُ على مُنسِّقٍ لأسبابِ عرض.
    """
    label = documents.label_for(doc_type)
    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title="مستندك يقترب من الانتهاء",
            body=f"{label}: تنتهي بعد {days_left} يوماً — ويُعلَّق حسابك يومها",
            data={
                "type": DocumentEvent.DOCUMENT_EXPIRING.value,
                "document_id": str(document_id),
                "doc_type": doc_type.value,
                "expires_on": expires_on.isoformat(),
                "days_left": str(days_left),
            },
        ),
    )


async def publish_document_expired(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_type: DocumentType,
    expires_on,
) -> None:
    """التعليقُ وقع — **ومعه طريقُ الخروج في الجملة نفسِها** (البند ج).

    من قرأ «عُلِّق حسابك» بلا ما يفعله يتّصل بالدعم؛ ومن قرأ «ارفع الجديدة»
    يفعلها. **وطريقُ الرجوع جزءٌ من الخبر لا صفحةُ مساعدةٍ بعده** — وهي قاعدةُ
    «رفضٌ بلا مخرجٍ ليس رفضاً» بعينها.
    """
    label = documents.label_for(doc_type)
    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title="عُلِّق حسابك",
            body=f"انتهت صلاحية {label} — ارفع الوثيقة الجديدة لتعود للمراجعة",
            data={
                "type": DocumentEvent.DOCUMENT_EXPIRED.value,
                "document_id": str(document_id),
                "doc_type": doc_type.value,
                "expires_on": expires_on.isoformat(),
            },
        ),
    )


async def publish_payment_confirmed(
    session: AsyncSession,
    redis: Redis,
    *,
    rider_id: uuid.UUID,
    payment,
) -> None:
    """«وصلني المبلغ» يصل الراكبَ — وجدته تجربةُ المرحلة ١٣ على الهاتفين.

    **كان التأكيدُ لا يخرج من مكانه**: يضغط الكبتنُ «استلمت»، فيتغيّر الصفُّ في
    القاعدة ولا يُبثّ شيء — فتبقى شاشةُ الراكب المفتوحة تقول «سلّم المبلغ» بلا
    نهاية، ولا يصل صندوقَه أثرٌ يقول إن دفعتَه أُغلقت. ومن أغلق تطبيقَه لا يعرف
    أبداً أن الرحلةَ سُدِّدت إلا بفتح شاشتها من جديد.

    **وهو للراكب وحدَه**: الكبتنُ هو من ضغط، ومن فعل شيئاً لا يُخبَر به — قاعدةُ
    `DRIVER_RIDE_EVENT_TEXT` نفسُها.

    **والحمولةُ خام**: مبلغٌ وقناةٌ وعملة، والجملةُ تُبنى في التطبيق.
    """
    await _safe_notify(
        session,
        redis,
        user_id=rider_id,
        message=PushMessage(
            title="اكتمل دفع رحلتك",
            body="أكّد الكبتنُ استلام المبلغ — شكراً لك.",
            data={
                "type": "payment_confirmed",
                "ride_id": str(payment.ride_id),
                "payment_id": str(payment.id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "method": payment.method.value,
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
    hours_left: int | None = None,
) -> None:
    """تنبيه الاشتراك — هذا ما كانت المرحلة 7 تنتظره من المرحلة 8.

    و`hours_left` نافذةُ التنبيه (البند ١٢): **رقمٌ خام في `data`** تبني منه
    الواجهةُ جملتَها، ونصُّ الصينية يذكره لأن نظامَ التشغيل يرسمه والتطبيقُ
    مغلق. وبغيره يقول التنبيهان الجملةَ نفسَها، فيُقرأ الثاني تكراراً لا إلحاحاً.
    """
    await events.publish_subscription_event(
        redis,
        driver_user_id=driver_user_id,
        event=event,
        expires_at=expires_at,
    )

    title, body = SUBSCRIPTION_EVENT_TEXT[event]
    if hours_left is not None:
        remaining = (
            f"يتبقى أقل من {hours_left // 24} أيام"
            if hours_left >= 48
            else f"يتبقى أقل من {hours_left} ساعة"
        )
        body = f"{remaining} — {body}"
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
                **({"hours_left": hours_left} if hours_left is not None else {}),
            },
        ),
    )


# ------------------------------------------- أحداث الأمان (المرحلة 12-د)


async def publish_security_event(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> None:
    """حدثُ أمانٍ على حساب صاحبه — استهلاكُ رمز استرداد أو إطفاءُ العامل.

    **ولا بثَّ مقبس هنا** بخلاف بقية النواشر: اللوحة بلا WebSocket أصلاً (SPEC
    القسم 13)، فقناةٌ لا يسمعها أحدٌ عملٌ بلا قارئ. والصفُّ في الصندوق هو كلُّ
    المقصود — وهذان الحدثان بالذات ما يفعله من استولى على حساب، وصاحبُه أوّلُ
    من يجب أن يعرف.

    ويمرّ من هذا الباب لا من `inbox.record` مباشرةً: بابٌ واحدٌ للقناتين هو ما
    يمنع أن تُضاف قناةٌ لحدثٍ وتُنسى لآخر (المرحلة 8).
    """
    await _safe_notify(
        session,
        redis,
        user_id=user_id,
        message=PushMessage(
            title=title,
            body=body,
            data={"type": kind, **(data or {})},
        ),
    )


async def publish_tip_received(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    tip,
) -> None:
    """بقشيشٌ وصل الكبتن (المرحلة 12-و).

    **والحمولةُ قيمٌ خام**: مبلغٌ وعملةٌ ومُعرّفُ رحلة، لا جملةٌ مصوغة ولا رقمٌ
    منسَّق — الخلفيةُ لا تعرف بأي أرقامٍ يقرأ صاحبُ الجهاز (القسم 10). و
    و`title`/`body` للدرج وحده حين يكون التطبيق مغلقاً.

    وأولويةٌ عادية: البقشيشُ خبرٌ سارّ لا مهلةَ فيه — والإيقاظُ لبطاقة الطلب
    وحدها.
    """
    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title="بقشيش من راكب",
            body="شكرك راكبٌ ببقشيش — أُضيف إلى محفظتك.",
            data={
                "type": "tip_received",
                "ride_id": str(tip.ride_id),
                "amount": str(tip.amount),
                "currency": tip.currency,
            },
        ),
    )


async def publish_booking_missed(
    session: AsyncSession,
    redis: Redis,
    *,
    rider_id: uuid.UUID,
    booking_id: uuid.UUID,
) -> None:
    """حجزٌ حلَّ موعدُه وصاحبُه في رحلةٍ جارية (المرحلة 12-ط).

    **ولا يُترك بصمت**: من حجز موعداً ورتّب عليه يومَه يقف على الرصيف ينتظر
    سيارةً لم تُطلب. والصمتُ هنا ليس حياداً بل خبرٌ خاطئ.
    """
    await _safe_notify(
        session,
        redis,
        user_id=rider_id,
        message=PushMessage(
            title="لم يُنفَّذ حجزك",
            body="حلَّ موعدُ حجزك وأنت في رحلةٍ جارية، فلم نطلب سيارةً أخرى.",
            data={"type": "booking_missed", "booking_id": str(booking_id)},
        ),
    )


async def publish_booking_no_driver(
    session: AsyncSession,
    redis: Redis,
    *,
    rider_id: uuid.UUID,
    booking_id: uuid.UUID,
    ride_id: uuid.UUID,
) -> None:
    """حجزٌ سُلّم للتوزيع فلم يجد كبتناً (المرحلة 12-ط).

    **وهو غيرُ إشعار `no_driver_found` على رحلةٍ فورية** وإن تشابها: ذاك يراه
    صاحبُه على الشاشة وهو ينتظر، وهذا يوقظ من حجز موعدَ مطارٍ ونام. فالنصُّ
    يقول «حجزك»، والحمولةُ تحمل `booking_id` كي يفتح الضغطُ الحجزَ لا الرحلة.
    """
    await _safe_notify(
        session,
        redis,
        user_id=rider_id,
        message=PushMessage(
            title="لم نجد كبتناً لحجزك",
            body="لم يقبل أيُّ كبتنٍ رحلتَك المجدولة. جرّب الطلبَ الآن.",
            data={
                "type": "booking_no_driver",
                "booking_id": str(booking_id),
                "ride_id": str(ride_id),
            },
        ),
    )


async def publish_booking_preference_dropped(
    session: AsyncSession,
    redis: Redis,
    *,
    rider_id: uuid.UUID,
    booking_id: uuid.UUID,
    ride_id: uuid.UUID,
) -> None:
    """حجزٌ نُفِّذ بلا تفضيل الجنس لأن الخدمةَ أُطفئت بعده (المرحلة 12-ط).

    **ثلاثةُ مسالكَ ورابعُها هذا**: رفضُ الرحلة يتركها بلا سيارةٍ في موعدٍ رتّبت
    حياتَها عليه؛ وإسقاطُ التفضيل بصمتٍ يجعلها تركب مع من لم تقبله؛ وإبقاؤه يعني
    رحلةً لا تجد كبتناً أبداً (لا مطابقةَ حيث الخدمةُ مطفأة). فالمخرجُ الوحيد
    الذي لا يكذب ولا يهجر: تُطلب الرحلةُ **ويُقال لها**.
    """
    await _safe_notify(
        session,
        redis,
        user_id=rider_id,
        message=PushMessage(
            title="طُلبت رحلتك بلا تفضيل",
            body="خدمةُ الكبتنات غير مفعّلة الآن، فطُلبت رحلتُك من أي كبتنٍ متاح.",
            data={
                "type": "booking_preference_dropped",
                "booking_id": str(booking_id),
                "ride_id": str(ride_id),
            },
        ),
    )


async def publish_women_mode_revoked(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: uuid.UUID,
) -> None:
    """أُلغي الوضعُ النسائيُّ عن حسابٍ لمخالفة الوثائق ما أُقرّ (2026-08-13).

    **ولماذا إشعارٌ أصلاً؟** لأن ما يقع بلا إشعارٍ هو **اختفاءُ لونٍ وميزةٍ بلا
    تفسير** — والسِمةُ الوردية ظاهرةٌ في كل شاشةٍ في تطبيقها، فزوالُها مرئيٌّ
    فوراً وسؤالُ «ماذا حدث لتطبيقي؟» تذكرةُ دعمٍ في نفس الدقيقة. والصمتُ هنا لا
    يحفظ خصوصيةً: هي تعرف ما أقرّت وتعرف أن وثائقها رُوجعت.

    **والنصُّ يقول السببَ العامَّ ولا يزيد** (قرارُ المالك): «مخالفةُ الوثائق لما
    أُقرّ» — ولا يُنقل فيه ما كتبه المشرف. ذاك سببٌ للتدقيق يُقرأ بعد شهرٍ عند
    مراجعةٍ أو نزاع، ونقلُه إلى إشعارٍ يجعل حكمَ موظفٍ خطاباً للحساب.
    """
    await _safe_notify(
        session,
        redis,
        user_id=user_id,
        message=PushMessage(
            title="أُلغي الوضع النسائي",
            body=(
                "لم تطابق وثائقُك ما أُقرّ في الحساب، فأُلغي الوضعُ النسائي. "
                "للتصحيح راسل الدعم."
            ),
            data={"type": "women_mode_revoked"},
        ),
    )


async def publish_share_partner_cancelled(
    session: AsyncSession,
    redis: Redis,
    *,
    rider_id: uuid.UUID,
    ride_id: uuid.UUID,
    price_kept: bool,
) -> None:
    """ألغى شريكُ الرحلة، وبقيت رحلةُ الآخر (المرحلة 12-ي، قرارُ المالك الخامس).

    **والإشعارُ هو ما يفصل هذا عن الخيار الذي رفضته المواصفةُ نصّاً**: المرفوضُ
    أن يُقال له **في نهاية الرحلة** إن السعرَ صار غيرَ ما وافق عليه. فيُقال له
    حين يقع، وهو قادرٌ على التصرّف.

    **ونصّان لا واحد**، لأن ما وقع مختلف:

    - `price_kept=False` — لم تنطلق رحلتُه بعد: **يصير سعرُها منفرداً كاملاً**،
      لأن الخصمَ كان ثمنَ مشاركةٍ لم تقع. ويُقال له الرقمُ الجديد قبل أن يمضي.
    - `price_kept=True` — رحلتُه سائرةٌ فعلاً: **لا يُرفع عليه سعر** وتتحمّل
      الشركةُ الفرق (القرار السادس). ورفعُه هنا هو الخيارُ المرفوضُ بحرفه — لا
      لأن المبلغ كبير بل لأنه بلا بديل: من يُخبَر وهو في السيارة لا يملك قبولاً
      ولا رفضاً. ويُقال له كذلك، فسكوتٌ عن حدثٍ يخصّه يجعله يكتشفه في الإيصال.
    """
    body = (
        "ألغى الراكب الآخر مشاركته. رحلتك مستمرة بسعرها كما وافقت عليه."
        if price_kept
        else "ألغى الراكب الآخر مشاركته، فصارت رحلتك منفردة بسعرها الكامل."
    )
    await _safe_notify(
        session,
        redis,
        user_id=rider_id,
        message=PushMessage(
            title="تغيّرت مشاركة رحلتك",
            body=body,
            data={
                "type": "share_partner_cancelled",
                "ride_id": str(ride_id),
                "price_kept": price_kept,
            },
        ),
    )


async def publish_cancellation_compensation(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_id: uuid.UUID,
    ride_id: uuid.UUID,
    amount: Decimal,
    currency: Currency,
    settled: bool,
) -> None:
    """أُلغيت رحلةٌ بعد قبولها، فاستحقّ الكبتنُ تعويضاً (`CANCELLATION-FEE.md` §8).

    **وحالُه في النصّ لا في شاشةٍ يفتحها لاحقاً**: «وصلك الآن» غيرُ «معلّقٌ حتى
    يسدّد الراكب». من يقرأ الأول ولا يجد المالَ في رصيده يظن العطبَ في المنصّة،
    ومن يقرأ الثاني يعرف أنه ينتظر إنساناً — وكلاهما مالُه، لكن أحدَهما وصل.

    **ومعرّفُ الكبتن لا معرّفُ مستخدمه**: الصفُّ يعرف `drivers.id`، ووجهةُ
    الإشعار `users.id` — وخلطُهما يرسل إشعاراً إلى معرّفٍ لا مستخدمَ له، وهو
    الفخُّ الذي يحرسه `wallet_transactions.owner_id` في كل مسارٍ مالي.
    """
    driver = await session.get(Driver, driver_id)
    if driver is None:  # pragma: no cover
        return
    body = (
        "أُلغيت الرحلة بعد قبولك، وأُضيف تعويضُها إلى محفظتك."
        if settled
        else "أُلغيت الرحلة بعد قبولك. تعويضُك مسجَّلٌ ويصلك حين يسدّده الراكب."
    )
    await _safe_notify(
        session,
        redis,
        user_id=driver.user_id,
        message=PushMessage(
            title="تعويضُ إلغاء",
            body=body,
            data={
                "type": "cancellation_compensation",
                "ride_id": str(ride_id),
                "amount": str(amount),
                "currency": currency.value,
                "settled": settled,
            },
        ),
    )


async def publish_cancellation_collected(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_id: uuid.UUID,
    ride_id: uuid.UUID,
    amount: Decimal,
    currency: Currency,
) -> None:
    """وصل التعويضُ المعلَّقُ محفظةَ المتضرر (`CANCELLATION-FEE.md` §8).

    **وهو الخبرُ الثاني لا تكرارُ الأول**: الأولُ قال «مسجَّلٌ ويصلك حين يسدّد
    الراكب»، وهذا يقول إنه وصل — ومن لا يُخبَر بالثاني يبقى يراقب رقماً في
    قسمِ «المعلّق» لا يعرف متى ينتقل.
    """
    driver = await session.get(Driver, driver_id)
    if driver is None:  # pragma: no cover
        return
    await _safe_notify(
        session,
        redis,
        user_id=driver.user_id,
        message=PushMessage(
            title="وصلك تعويضُ الإلغاء",
            body="أُضيف تعويضُ الرحلة الملغاة إلى رصيدك المتاح.",
            data={
                "type": "cancellation_collected",
                "ride_id": str(ride_id),
                "amount": str(amount),
                "currency": currency.value,
            },
        ),
    )


async def publish_cancellation_carried(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    ride_id: uuid.UUID,
    amount: Decimal,
    currency: Currency,
    transferred: bool,
    due_at: datetime | None,
) -> None:
    """قبض كبتنٌ نقداً مبلغاً مستوفىً لكبتنٍ آخر (§6-أ) — **وحالُه في النصّ**.

    «حُوِّل من محفظتك» غيرُ «بانتظار شحنِ محفظتك»: الأولُ واقعةٌ انتهت، والثاني
    مطلوبٌ منه فعلٌ له مهلة. ومن يقرأ الأول ورصيدُه لم ينقص يظن عطباً، ومن
    يقرأ الثاني ولا يعرف أن عليه شيئاً يُوقَف حسابُه وهو لا يدري لماذا.
    """
    # **والشكرُ صريحٌ في النصّ، لا مكافأةٌ في مكانٍ آخر** (قرارُ المالك
    # 2026-08-16، `CANCELLATION-FEE.md` §6-أ): أُسقطت مكافأةُ الحامل لأن ثمنَها
    # أعلى من العبء الذي تليّنه — والحاملُ لا يخسر شيئاً أصلاً، صافيه صفر.
    # فالذي يقع عليه أساسُه شكرٌ لا ثمن، **ويُقال في اللحظة نفسِها** لا في
    # كشفٍ يفتحه بعد أسبوع. وموضعُه أوّلُ الجملة لا آخرَها: من يقرأ «خُصم من
    # محفظتك» أوّلاً يتوقف عندها
    body = (
        "شكراً لك — نقلتَ لزميلك مالَه. استلمتَ مع الأجرة مبلغاً مستوفىً "
        "لكبتنٍ آخر، وحُوِّل من محفظتك إليه."
        if transferred
        else (
            "شكراً لك — بيدك مالُ زميلك. استلمتَ مع الأجرة مبلغاً مستوفىً "
            "لكبتنٍ آخر ولم يكفِ رصيدُك لتحويله، فاشحن محفظتك ليصله."
        )
    )
    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title="مبلغٌ مستوفى لكبتنٍ آخر",
            body=body,
            data={
                "type": "cancellation_carried",
                "ride_id": str(ride_id),
                "amount": str(amount),
                "currency": currency.value,
                "transferred": transferred,
                "due_at": due_at.isoformat() if due_at else None,
            },
        ),
    )


async def publish_whatsapp_session(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: uuid.UUID,
    state: str,
    needs_human: bool,
    detail: str | None,
) -> None:
    """تبدّلت حالُ جلسة واتساب الذاتية — **إلى المشرفين وحدهم**.

    **وهذا الإشعارُ يخصّ المنصّة لا مستخدماً**، وهو الوحيد كذلك: ما عداه يقول
    لصاحبه شيئاً عن رحلته أو ماله. وسببُ وجوده أن جلسةً تسقط صامتةً **توقف
    تسجيلَ المستخدمين الجدد كلَّهم** بلا أن يعلم أحد — يُكتشف بعد ساعاتٍ من
    أرقامٍ تنقص، لا برسالةٍ تصل.

    **والنصُّ يقول ما يُفعل لا ما وقع**: «امسح رمزَ الربط» فعلٌ، و«الجلسة
    awaiting_qr» حالةٌ لا يعرف قارئُها ماذا يصنع بها.
    """
    if state == "linked":
        title = "عادت جلسةُ واتساب"
        body = "عاد إرسالُ رموز التحقق عبر واتساب."
    elif state == "awaiting_qr":
        title = "جلسةُ واتساب تنتظر ربطاً"
        body = (
            "توقّف إرسالُ رموز التحقق عبر واتساب. افتح صفحةَ العقود وامسح "
            "رمزَ الربط من هاتف الرقم المخصّص."
        )
    elif state == "unreachable":
        title = "بوابةُ واتساب لا تُجيب"
        body = "تعذّر الوصول إلى خدمة البوابة — راجع الخادم."
    else:
        title = "انقطعت جلسةُ واتساب"
        body = "انقطع الاتصالُ وتجري إعادةُ المحاولة. إن طال فبدّل القناة."

    await _safe_notify(
        session,
        redis,
        user_id=user_id,
        message=PushMessage(
            title=title,
            body=body,
            data={
                "type": "whatsapp_session",
                "state": state,
                "needs_human": needs_human,
                "detail": detail,
            },
        ),
    )


async def publish_share_partner_joined(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    lead_rider_id: uuid.UUID,
    ride_id: uuid.UUID,
    detour_minutes: str,
) -> None:
    """التحق شريكٌ بمجموعة الرحلة (المرحلة 12-ي) — للكبتن ولصاحب المقعد الأول.

    **ولا يُخطر به الملتحقُ من هنا**: رحلتُه انتقلت إلى `accepted` بكبتنٍ معيَّن،
    فحدثُه هو `driver_assigned` نفسُه الذي يصل كلَّ راكبٍ أُسند إليه كبتن — بابٌ
    واحدٌ لحالةٍ واحدة، لا رسالةٌ ثانيةٌ تقول نصفَ ما تقوله الأولى.

    **والكبتنُ يُخطَر ولا يُستأذَن**، وهذا ما يجعله مقبولاً: الرحلةُ عُرضت عليه
    معلَّمةً بالمشاركة وقَبِلها بها — فالمقعدُ الثاني احتمالٌ وافق عليه، لا أمرٌ
    وقع عليه. ونصُّه يحمل **دقائقَ الالتفاف** لأن ما يعنيه عملياً طولُ طريقه.

    **وصاحبُ المقعد الأول يُخطَر كذلك**: راكبٌ ثانٍ سيصعد سيارتَه، وهو من طلب
    المشاركة أصلاً — فاكتشافُه بالمفاجأة على الرصيف هو ما يُفسد ميزةً وافق عليها.
    """
    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title="انضم راكب ثانٍ",
            body="أُضيف راكبٌ ثانٍ إلى رحلتك المشتركة — راجع المسار في التطبيق.",
            data={
                "type": "share_partner_joined",
                "ride_id": str(ride_id),
                "detour_minutes": detour_minutes,
            },
        ),
    )
    await _safe_notify(
        session,
        redis,
        user_id=lead_rider_id,
        message=PushMessage(
            title="وجدنا شريكاً لرحلتك",
            body="سيشاركك الرحلة راكبٌ آخر كما طلبت، وسعرك المخصوم كما هو.",
            data={
                "type": "share_partner_joined",
                "ride_id": str(ride_id),
                "detour_minutes": detour_minutes,
            },
        ),
    )


# ------------------------------------------------------- السلف (البند ١٥)

# **أربعةُ أحداثٍ لا حدثٌ واحد** (§٨ من المواصفة): صرفٌ، واقترابُ مهلة، وإيقافٌ،
# وسداد. **والإيقافُ خصوصاً لا يجوز أن يصل صامتاً**: كبتنٌ يستيقظ خارج التوزيع
# بلا سببٍ مكتوبٍ يظنّ العطبَ في التطبيق فيتّصل بالدعم، وقد كان يكفيه سطرٌ
# يقول ما عليه وكيف يخرج منه
ADVANCE_EVENT_TEXT: dict[str, tuple[str, str]] = {
    "advance_disbursed": ("وصلتك السلفة", "أُضيفت إلى محفظتك، وتُقتطع من أرباح رحلاتك"),
    "advance_due_soon": ("مهلةُ السلفة تقترب", "سدّد ما تبقّى قبل انقضائها"),
    "advance_overdue": (
        "أُوقفت الطلبات — سلفةٌ تجاوزت مهلتها",
        "سدّد ما تبقّى ليعود حسابُك إلى التوزيع",
    ),
    "advance_repaid": ("سُدِّدت السلفة", "شكراً — حسابُك يعمل كالمعتاد"),
}


async def publish_advance_event(
    session: AsyncSession,
    redis: Redis,
    *,
    driver_user_id: uuid.UUID,
    kind: str,
    amount: Decimal,
    currency: str,
    due_at: datetime | None = None,
) -> None:
    """حدثُ سلفةٍ يصل صاحبَه (البند ١٥).

    **والحمولةُ قيمٌ خام**: مبلغٌ وعملةٌ ومهلة، والجملةُ تُبنى في التطبيق —
    فالخلفيةُ لا تعرف بأي أرقامٍ يقرأ صاحبُ الجهاز. و`title`/`body` للدرج وحده.
    """
    title, body = ADVANCE_EVENT_TEXT[kind]
    await _safe_notify(
        session,
        redis,
        user_id=driver_user_id,
        message=PushMessage(
            title=title,
            body=body,
            data={
                "type": kind,
                "amount": str(amount),
                "currency": currency,
                **({"due_at": due_at.isoformat()} if due_at else {}),
            },
        ),
    )


async def publish_referral_rewarded(
    session: AsyncSession,
    redis: Redis,
    *,
    referrer_id: uuid.UUID,
    referral,
) -> None:
    """«وصلتك مكافأةُ إحالة» — للمُحيل وحدَه.

    **والمهمةُ الدورية هي ما يدفع**، فلا أحدَ ينظر إلى شاشةٍ لحظةَ الدفع: بلا
    إشعارٍ يرى المُحيلُ رصيدَه ارتفع بلا سبب مكتوب، فيقرؤه خطأً أو يسأل الدعم.
    وهو عكسُ قاعدةِ «من فعل شيئاً لا يُخبَر به» تماماً — إذ لم يفعل هو شيئاً
    الآن، بل وقع له.

    **والحمولةُ خام**: مبلغٌ وعملةٌ ورمز، والجملةُ تُبنى في التطبيق.
    """
    await _safe_notify(
        session,
        redis,
        user_id=referrer_id,
        message=PushMessage(
            title="وصلتك مكافأة إحالة",
            body="أُضيفت مكافأةُ إحالتك إلى محفظتك.",
            data={
                "type": "referral_rewarded",
                "referral_id": str(referral.id),
                "amount": str(referral.reward_amount),
                "currency": referral.reward_currency,
                "code_used": referral.code_used,
            },
        ),
    )


async def publish_ride_paused(
    session: AsyncSession,
    redis: Redis,
    *,
    ride,
    paused: bool,
) -> None:
    """«العدّادُ يعمل ولماذا» — **للراكب وحدَه** (§5.10-ب).

    **وسطرٌ صريحٌ لا رقمٌ يظهر في الفاتورة آخرَ الرحلة**: مبلغٌ لم يُعلَن حين
    نشأ يُقرأ خطأً في الحساب — والراكبُ الذي يرى الرسمَ أولَ مرةٍ في شاشة الدفع
    يفتح نزاعاً على مالٍ استحقّه الكبتن.

    **وللراكب وحدَه**: الكبتنُ هو من ضغط، ومن فعل شيئاً بيده لا يُخبَر به
    (قاعدةُ `DRIVER_RIDE_EVENT_TEXT`).

    **والحمولةُ خام**: قيمةُ الدقيقة والمهلةُ والنوع، والجملةُ تُبنى في التطبيق.
    """
    await _safe_notify(
        session,
        redis,
        user_id=ride.rider_id,
        message=PushMessage(
            title="توقّف مؤقّت" if paused else "استؤنفت الرحلة",
            body=(
                "بدأ احتساب وقت الانتظار."
                if paused
                else "توقّف احتساب وقت الانتظار."
            ),
            data={
                "type": "ride_paused" if paused else "ride_resumed",
                "ride_id": str(ride.id),
                "price_per_min": str(ride.pause_price_per_min_at_ride),
                "currency": ride.currency,
            },
        ),
    )
