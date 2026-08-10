"""شاشة الدفع وتحصيل الأجرة (SPEC القسم 6/11.5/12.4).

الراوتر يقرّر **من** يحق له الطلب فقط؛ كل ما عداه في `services/payments.py`.
لا مبلغ يصل من العميل في أي مسار هنا: المبلغ هو المتبقي من `final_fare`
والحساب في الخلفية حصراً (القسم 14).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentDriver, CurrentUser, DbSession, RiderUser
from app.models.enums import PaymentMethod
from app.models.ride import Ride
from app.schemas.payment import (
    CardOrderOut,
    PaymentCreate,
    PaymentDisputeRequest,
    PaymentOut,
    RidePaymentsOut,
)
from app.services import (
    card_payments as card_service,
    payments as payments_service,
    rides as rides_service,
)

router = APIRouter(tags=["payments"])


async def _ride_payments_out(session: AsyncSession, ride: Ride) -> RidePaymentsOut:
    """حال الدفع على الرحلة — نفس التمثيل لكل مسارات هذا الملف."""
    entries = await payments_service.list_for_ride(session, ride.id)
    # alias الكبتن لا يظهر إلا حيث يُحتاج فعلاً: مع دفعة كليك قائمة
    needs_alias = any(entry.method == PaymentMethod.CLIQ for entry in entries)
    # وطلبُ البطاقة لا يظهر إلا وهو معلّق: منه يبني العميل «متابعة الدفع»
    open_order = await card_service.open_order_for_ride(session, ride.id)

    return RidePaymentsOut(
        ride_id=ride.id,
        currency=ride.currency,
        final_fare=ride.final_fare,
        outstanding=await payments_service.outstanding_amount(session, ride),
        payments=[PaymentOut.model_validate(entry) for entry in entries],
        cliq_alias=(
            ride.driver.cliq_alias if needs_alias and ride.driver is not None else None
        ),
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


@router.post("/payments/{payment_id}/confirm", response_model=PaymentOut)
async def confirm_payment(
    payment_id: uuid.UUID, driver: CurrentDriver, session: DbSession
) -> PaymentOut:
    """«استلمت المبلغ» في تطبيق الكبتن (SPEC القسم 6.1/12.4)."""
    payment = await payments_service.get_payment(session, payment_id, for_update=True)
    payment = await payments_service.confirm_by_driver(
        session, payment=payment, driver=driver
    )
    await session.commit()
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
