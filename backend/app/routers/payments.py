"""شاشة الدفع وتحصيل الأجرة (SPEC القسم 6/11.5/12.4).

الراوتر يقرّر **من** يحق له الطلب فقط؛ كل ما عداه في `services/payments.py`.
لا مبلغ يصل من العميل في أي مسار هنا: المبلغ هو المتبقي من `final_fare`
والحساب في الخلفية حصراً (القسم 14).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep, RiderUser
from app.models.enums import PaymentMethod, PaymentStatus
from app.models.payment import Payment
from app.models.ride import Ride
from app.schemas.payment import (
    CardOrderOut,
    CliqChargeOut,
    CliqDeclareOut,
    CliqReferenceRequest,
    PaymentCreate,
    PaymentDisputeRequest,
    PaymentOut,
    RidePaymentsOut,
)
from app.schemas.unconfirmed_payment import (
    CaptainUnconfirmedItem,
    CaptainUnconfirmedOut,
    PaymentObjectionRequest,
    RiderUnconfirmedItem,
    RiderUnconfirmedOut,
)
from app.services import cliq_claims
from app.services.push.base import PushMessage
from app.services import settlement
from app.services import (
    cancellation,
    card_payments as card_service,
    notifications,
    payments as payments_service,
    rides as rides_service,
    unconfirmed_payments as unconfirmed_service,
)

router = APIRouter(tags=["payments"])


def _cliq_charge_out(payments: Sequence[Payment]) -> CliqChargeOut | None:
    """رمز كليك ورابطه لدفعةٍ ما زالت تنتظر الحوالة (SPEC القسم 6.2).

    `pending` وحدها: بعد تأكيد الكبتن أو نزاعه لم يعد للرمز ما يفعله، وعرضُه
    يدعو راكباً إلى تحويلٍ ثانٍ.
    """
    pending = next(
        (
            entry
            for entry in payments
            if entry.method == PaymentMethod.CLIQ
            and entry.status == PaymentStatus.PENDING
        ),
        None,
    )
    if pending is None:
        return None

    charge = payments_service.cliq_charge(pending)
    if charge is None:  # pragma: no cover - دفعةٌ سبقت المرحلة 9 بلا مرجع
        return None

    return CliqChargeOut(
        payment_id=pending.id,
        alias=charge.alias,
        reference=charge.reference,
        amount=charge.amount,
        currency=charge.currency,
        qr_payload=charge.qr_payload,
        deep_link=charge.deep_link,
        transfer_reference=pending.cliq_transfer_reference,
        transfer_reference_at=pending.cliq_reference_at,
    )


async def _ride_payments_out(session: AsyncSession, ride: Ride) -> RidePaymentsOut:
    """حال الدفع على الرحلة — نفس التمثيل لكل مسارات هذا الملف."""
    entries = await payments_service.list_for_ride(session, ride.id)
    # وطلبُ البطاقة لا يظهر إلا وهو معلّق: منه يبني العميل «متابعة الدفع»
    open_order = await card_service.open_order_for_ride(session, ride.id)

    return RidePaymentsOut(
        ride_id=ride.id,
        currency=ride.currency,
        final_fare=ride.final_fare,
        outstanding=await payments_service.outstanding_amount(session, ride),
        payments=[PaymentOut.model_validate(entry) for entry in entries],
        # الحكمُ يأتي محسوباً من مصدرٍ واحد، ولا تستنتجه الشاشةُ من
        # `outstanding`: تلك تجيب «أأفتح صفّاً جديداً؟» لا «أعليَّ شيءٌ بيدي؟»
        settlement=settlement.state_for(
            chargeable=settlement.chargeable_of(ride), payments=entries
        ),
        cancellation_debt=await cancellation.debt_of(session, ride.rider_id),
        cliq_charge=_cliq_charge_out(entries),
        card_order=(
            CardOrderOut.model_validate(open_order) if open_order is not None else None
        ),
    )


@router.get("/rides/{ride_id}/payments", response_model=RidePaymentsOut)
async def list_ride_payments(
    ride_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> RidePaymentsOut:
    """يقرؤها طرفا الرحلة والإدارة — لا أحد سواهم (SPEC القسم 14)."""
    ride = await rides_service.get_ride_for_user(session, ride_id, user)
    return await _ride_payments_out(session, ride)


@router.post(
    "/rides/{ride_id}/payments",
    response_model=RidePaymentsOut,
    status_code=status.HTTP_201_CREATED,
)
async def pay_ride(
    ride_id: uuid.UUID,
    payload: PaymentCreate,
    rider: RiderUser,
    session: DbSession,
    redis: RedisDep,
) -> RidePaymentsOut:
    """يختار الراكب قناة الدفع بعد اكتمال الرحلة.

    المحفظة تُخصم فوراً وقد تنقسم إلى دفعٍ مختلط (القسم 6)، والكاش وكليك
    ينتظران تأكيد الكبتن، والبطاقة تعيد `card_order` برابط صفحة الدفع — أو
    تُحسم فوراً إن كانت على بطاقة محفوظة (القسم 6.4). لذلك يعيد المسار **حال
    الرحلة كلها** لا دفعةً واحدة.
    """
    await payments_service.pay_ride(
        session,
        ride_id=ride_id,
        rider=rider,
        method=payload.method,
        idempotency_key=payload.idempotency_key,
        save_card=payload.save_card,
        saved_card_id=payload.saved_card_id,
    )
    await session.commit()

    # رسمُ إلغاءٍ سابقٌ قد يكون حُصِّل مع هذه الدفعة (`CANCELLATION-FEE.md` §5)
    # — ويُعلَن **بعد الـcommit** كبقية البثّ
    await cancellation.announce_ride_collection(session, redis, ride_id=ride_id)

    # قراءة جديدة: بطاقة الكبتن (ومنها alias كليك) تحتاج علاقاتٍ محمّلة
    ride = await rides_service.get_ride(session, ride_id)
    return await _ride_payments_out(session, ride)


@router.post("/payments/{payment_id}/cliq-reference", response_model=RidePaymentsOut)
async def submit_cliq_reference(
    payment_id: uuid.UUID,
    payload: CliqReferenceRequest,
    rider: RiderUser,
    session: DbSession,
    redis: RedisDep,
) -> RidePaymentsOut:
    """«حوّلت — وهذا مرجع الحوالة» (SPEC القسم 6.3 — المرحلة 9).

    قفلُ صف الدفعة **قبل** فحص «هل سبق تسجيل مرجع»: بغيره تقرأ ضغطتان
    متزامنتان الحقلَ فارغاً معاً فتكتبان، ويصل الكبتنَ إشعاران بمرجعين
    لحوالةٍ واحدة.

    ثم يصل الكبتنَ إشعارٌ فوري ببطاقة «وصلني / لم يصلني» — **بعد الـ commit**
    كبقية البثّ. البطاقة نفسها شاشةُ المرحلة 10.
    """
    payment = await payments_service.get_payment(session, payment_id, for_update=True)
    payment = await payments_service.submit_cliq_reference(
        session,
        payment=payment,
        rider=rider,
        reference=payload.transfer_reference,
    )
    await session.commit()

    ride = await rides_service.get_ride(session, payment.ride_id)
    if ride.driver is not None:
        await notifications.publish_cliq_transfer(
            session,
            redis,
            driver_user_id=ride.driver.user_id,
            ride_id=ride.id,
            payment=payment,
        )
    return await _ride_payments_out(session, ride)


@router.post("/payments/{payment_id}/confirm", response_model=PaymentOut)
async def confirm_payment(
    payment_id: uuid.UUID,
    driver: CurrentDriver,
    session: DbSession,
    redis: RedisDep,
) -> PaymentOut:
    """«استلمت المبلغ» في تطبيق الكبتن (SPEC القسم 6.1/12.4)."""
    payment = await payments_service.get_payment(session, payment_id, for_update=True)
    payment = await payments_service.confirm_by_driver(
        session, payment=payment, driver=driver
    )
    ride = await payments_service.ride_of(session, payment)
    await session.commit()
    # **بعد الـcommit** كبقية البثّ: حالٌ يُعلَن قبل تثبيته قد يتراجع
    await notifications.publish_payment_confirmed(
        session, redis, rider_id=ride.rider_id, payment=payment
    )
    # وإن حمل معها رسمَ إلغاءٍ سابقاً لكبتنٍ آخر (§6-أ) قيل لكلٍّ ما يخصّه
    await cancellation.announce_ride_collection(session, redis, ride_id=ride.id)
    return PaymentOut.model_validate(payment)


@router.post("/payments/{payment_id}/dispute", response_model=PaymentOut)
async def dispute_payment(
    payment_id: uuid.UUID,
    payload: PaymentDisputeRequest,
    driver: CurrentDriver,
    session: DbSession,
    redis: RedisDep,
) -> PaymentOut:
    """«لم يصلني» على دفعة كليك → تنتقل للوحة الإدارة (SPEC القسم 6.2) — **و«لم يدفع» على الكاش حين يشتعل §٦٤-ج**."""
    payment = await payments_service.get_payment(session, payment_id, for_update=True)
    payment = await payments_service.dispute_by_driver(
        session, payment=payment, driver=driver, reason=payload.reason
    )
    await session.commit()
    # **«يُسأل الراكبُ فوراً»** (`design/PAYMENTS-UNCONFIRMED.md` §٢-٣) — للكاش وحدَه، وهو لا يقع إلا والمفتاحُ مشتعل؛
    # **فكليك كما كان حرفاً**. وبعد الـcommit كبقية البثّ
    notice = await unconfirmed_service.captain_dispute_notice(session, payment)
    if notice is not None:
        await unconfirmed_service.send(session, redis, [notice])
    return PaymentOut.model_validate(payment)


# ------------------------------------- المدفوعاتُ غيرُ المؤكَّدة (SPEC §٦٤-ج)
# `design/PAYMENTS-UNCONFIRMED.md` — **كلُّ بابٍ هنا يقفل صفَّ الدفعة قبل أيِّ فحص** (قاعدةُ `CLAUDE.md`)، ولا قيدَ يُكتب
# إلا من `payments.settle`. ومطفأً (`unconfirmed_payments_enabled`) تُردّ أفعالُها بـ`feature_disabled` وتعود قوائمُها فارغة.


@router.get("/payments/me/unconfirmed", response_model=RiderUnconfirmedOut)
async def rider_unconfirmed(rider: RiderUser, session: DbSession) -> RiderUnconfirmedOut:
    """**«رحلةٌ لم يكتمل دفعها»** — ما يُعرض بعد الترحيب وقبل الرئيسية عند كلِّ فتح (§٦، R31)، الأقدمُ أوّلاً."""
    blocked, items = await unconfirmed_service.rider_items(session, rider)
    return RiderUnconfirmedOut(
        blocked=blocked,
        items=[_rider_unconfirmed_item(item) for item in items],
    )


def _rider_unconfirmed_item(item: unconfirmed_service.RiderItem) -> RiderUnconfirmedItem:
    """**بانٍ واحدٌ للبطاقة** — وصفُّ الدفعة غائبٌ في `payment_due` (الأجرةُ مستحقّةٌ بلا صفّ)، فحقولُه فارغةٌ لا مخترعة."""
    payment = item.payment
    return RiderUnconfirmedItem(
        payment_id=payment.id if payment else None,
        ride_id=item.ride.id,
        completed_at=item.ride.completed_at,
        pickup_address=item.ride.pickup_address,
        dropoff_address=item.ride.dropoff_address,
        captain_name=item.captain_name,
        amount=item.amount,
        currency=payment.currency if payment else item.ride.currency,
        method=item.method,
        state=item.state,
        status=payment.status if payment else None,
        declared_at=payment.declared_at if payment else None,
        cliq_alias=payment.cliq_alias if payment else None,
        cliq_reference=payment.cliq_reference if payment else None,
        cliq_transfer_reference=payment.cliq_transfer_reference if payment else None,
        cliq_reference_at=payment.cliq_reference_at if payment else None,
        dispute_reason=payment.dispute_reason if payment else None,
        blocks_at=item.blocks_at,
        blocks_requests=item.blocks_requests,
    )


@router.post("/payments/{payment_id}/declare", response_model=RidePaymentsOut)
async def declare_cash_handover(
    payment_id: uuid.UUID, rider: RiderUser, session: DbSession
) -> RidePaymentsOut:
    """**«سلّمتُ المبلغ»** (§٢-٣) — إقرارُ الراكب على دفعة كاش، **بلا قيد**. والضغطةُ الثانيةُ تعيد الحالَ نفسَها.

    **قفلُ صفِّ الدفعة قبل الفحص**: بغيره يُختم إقرارٌ على دفعةٍ أكّدها الكبتنُ في اللحظة نفسِها.
    """
    payment = await payments_service.get_payment(session, payment_id, for_update=True)  # قفلُ الإقرار
    payment = await unconfirmed_service.declare_cash(session, payment=payment, rider=rider)
    await session.commit()
    ride = await rides_service.get_ride(session, payment.ride_id)
    return await _ride_payments_out(session, ride)


@router.post("/payments/{payment_id}/change-method", response_model=RidePaymentsOut)
async def change_payment_method(
    payment_id: uuid.UUID,
    payload: PaymentCreate,
    rider: RiderUser,
    session: DbSession,
    redis: RedisDep,
) -> RidePaymentsOut:
    """**«غيّر طريقة الدفع»** (§٢-١) — **يُلغى المعلَّقُ ويُنشأ غيرُه في معاملةٍ واحدة**، وحملُه حملُ `POST /rides/{id}/payments`
    حرفاً (`method` · `idempotency_key` · `save_card` · `saved_card_id`). **وعلى نزاع كاشٍ هو «سأدفع الآن»** (§٦).

    **والردُّ حالُ الرحلة كلِّها** كردِّ الدفع: الملغاةُ باقيةٌ `voided`، والجديدةُ بحالها (معلَّقةٌ للكاش وكليك، مُسوّاةٌ للمحفظة،
    و`card_order` برابط صفحة البطاقة). **وسقوطُ الدفع الجديد** (رصيدٌ لا يكفي، قناةٌ مطفأة، كاشٌ موقوف) **يُبقي القديمَ كما كان**.

    **الأقفالُ في الخدمة بترتيبها**: الرحلةُ ثمّ صفُّ الدفعة — ثمّ الفحص (`unconfirmed_payments.change_method`).
    """
    entries = await unconfirmed_service.change_method(
        session,
        payment_id=payment_id,
        rider=rider,
        method=payload.method,
        idempotency_key=payload.idempotency_key,
        save_card=payload.save_card,
        saved_card_id=payload.saved_card_id,
    )
    # **قبل الـcommit**: بعده تنتهي صلاحيةُ الصفوف المحمَّلة. ودفعاتُ الرحلة لا تخلو — الملغاةُ منها
    ride_id = entries[0].ride_id
    await session.commit()
    # **ما يُعلَن بعد الدفع يُعلَن هنا**: المحفظةُ قد تحمل رسمَ إلغاءٍ سابقاً (`CANCELLATION-FEE.md` §5)
    await cancellation.announce_ride_collection(session, redis, ride_id=ride_id)
    ride = await rides_service.get_ride(session, ride_id)
    return await _ride_payments_out(session, ride)


@router.get("/drivers/me/payments/unconfirmed", response_model=CaptainUnconfirmedOut)
async def captain_unconfirmed(
    driver: CurrentDriver, session: DbSession
) -> CaptainUnconfirmedOut:
    """**«ركّابٌ ينتظرون تأكيدك»** (§٦، C33) — الأقدمُ أوّلاً، ومعه ما أُتمّ آلياً ونافذتُه مفتوحة. و`blocked` شرطُ التوزيع نفسُه."""
    blocked, limits, items = await unconfirmed_service.captain_items(session, driver)
    return CaptainUnconfirmedOut(
        blocked=blocked,
        block_count=limits.driver_block_count,
        block_hours=limits.driver_block_hours,
        items=[
            CaptainUnconfirmedItem(
                payment_id=item.payment.id,
                ride_id=item.ride.id,
                completed_at=item.ride.completed_at,
                pickup_address=item.ride.pickup_address,
                dropoff_address=item.ride.dropoff_address,
                rider_first_name=(item.rider_name or "").split()[0]
                if (item.rider_name or "").split()
                else None,
                amount=item.payment.amount,
                currency=item.payment.currency,
                method=item.payment.method,
                state=item.state,
                status=item.payment.status,
                declared_at=item.payment.declared_at,
                cliq_transfer_reference=item.payment.cliq_transfer_reference,
                cliq_reference_at=item.payment.cliq_reference_at,
                cliq_confirmation_expires_at=item.payment.cliq_confirmation_expires_at,
                objection_deadline=item.objection_deadline,
            )
            for item in items
        ],
    )


@router.post("/payments/{payment_id}/object", response_model=PaymentOut)
async def object_auto_confirmation(
    payment_id: uuid.UUID,
    payload: PaymentObjectionRequest,
    driver: CurrentDriver,
    session: DbSession,
) -> PaymentOut:
    """**«لم أستلم هذا المبلغ»** — اعتراضُ الكبتن على إتمامٍ آليٍّ خلال نافذته (§٢-٥). **لا يُعكس قيد**: يذهب إلى طابور الإدارة.

    **قفلُ صفِّ الدفعة قبل الفحص**: اعتراضان معاً لا يكتبان سببين ولا يتجاوزان النافذة.
    """
    payment = await payments_service.get_payment(session, payment_id, for_update=True)  # قفلُ الاعتراض
    payment = await unconfirmed_service.object_auto_confirm(
        session, payment=payment, driver=driver, reason=payload.reason
    )
    await session.commit()
    return PaymentOut.model_validate(payment)


@router.post("/payments/cliq/{cart_id}/declare", response_model=CliqDeclareOut)
async def declare_cliq_paid(
    cart_id: str, user: CurrentUser, session: DbSession, redis: RedisDep
) -> CliqDeclareOut:
    """**«حوّلتُ»** — بابٌ واحدٌ للمطالبات اليدويّة كلِّها (قرارُ المالك 2026-09-01).

    **ولمَ بابٌ واحدٌ لا بابٌ لكلِّ غرض**: الأغراضُ اليومَ اثنان — اشتراكٌ
    ودَين — وقد تصير ثلاثة. **وثلاثةُ أبوابٍ تفترق أوّلَ تعديل**، ومفتاحُها
    كلِّها واحدٌ هو `cart_id`.

    **والضغطةُ الثانيةُ تُعيد الصفَّ نفسَه ولا تصيح**: من ضغط ثانيةً لم يخطئ —
    الشبكةُ بطيئةٌ أو الشاشةُ لم تتحدّث. **وخطأٌ هنا يعلّم صاحبَه أنه أفسد
    شيئاً وهو لم يفعل.**
    """
    order = await cliq_claims.declare_paid(session, cart_id=cart_id, user=user)
    await session.commit()

    # **والإشعارُ بعد الإيداع** — قاعدةُ المشروع: حالٌ تُعلن ثم تتراجع
    # معاملتُها **تصل صاحبَها ولا تقع**.
    #
    # **ويصل المشرفَ لحظةَ الضغط** (قرارُ المالك 2026-09-01): صاحبُ المال
    # ينتظر، **وقائمةٌ لا يعلم بها أحدٌ حتى يفتحها تجعل الانتظارَ بطول عادةِ
    # من يفتح**.
    #
    # **وصفُّ صندوق الوارد يُكتب ولو لم يكن ثمة عقدُ FCM ولا جهازٌ مسجَّل**
    # (`_safe_notify`) — فالإشعارُ **قائمٌ اليوم**، والدفعُ إلى الهاتف يصل
    # يومَ يسجّل غلافُ المشرف جهازَه. **ولا يُنتظر الغلافُ ليُبنى الإرسال.**
    for admin in await cliq_claims.admins_of(session, order.country_code):
        await notifications._safe_notify(
            session,
            redis,
            user_id=admin.id,
            message=PushMessage(
                title="حوالةُ كليك بانتظار تأكيدك",
                body=(
                    f"{user.name} يقول إنه حوّل {order.amount} "
                    f"{order.currency.value} — المرجع {order.cart_id}"
                ),
                data=cliq_claims.declared_notice(order),
            ),
        )

    return CliqDeclareOut(
        cart_id=order.cart_id,
        declared_paid_at=order.declared_paid_at,
        status=order.status,
    )
