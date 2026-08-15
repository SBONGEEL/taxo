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
    CliqReferenceRequest,
    PaymentCreate,
    PaymentDisputeRequest,
    PaymentOut,
    RidePaymentsOut,
)
from app.services import settlement
from app.services import (
    card_payments as card_service,
    notifications,
    payments as payments_service,
    rides as rides_service,
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
    return PaymentOut.model_validate(payment)


@router.post("/payments/{payment_id}/dispute", response_model=PaymentOut)
async def dispute_payment(
    payment_id: uuid.UUID,
    payload: PaymentDisputeRequest,
    driver: CurrentDriver,
    session: DbSession,
) -> PaymentOut:
    """«لم يصلني» على دفعة كليك → تنتقل للوحة الإدارة (SPEC القسم 6.2)."""
    payment = await payments_service.get_payment(session, payment_id, for_update=True)
    payment = await payments_service.dispute_by_driver(
        session, payment=payment, driver=driver, reason=payload.reason
    )
    await session.commit()
    return PaymentOut.model_validate(payment)
