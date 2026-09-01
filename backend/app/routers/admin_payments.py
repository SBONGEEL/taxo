"""النزاعات والاستردادات من اللوحة (SPEC القسم 13.4/13.8).

القسمة بين الدورين هي نفسها في `admin_wallets.py` بحرفها: **`support` يقرأ
ويفصل في النزاعات** — وهذا نصُّ القسم 13.8 لا توسيعٌ له — **و`admin` وحده
يحرّك مالاً**، فالاسترداد له وحده. وكل إجراء يدخل سجل التدقيق في نفس معاملته.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.deps import AdminUser, DbSession, StaffUser
from app.models.enums import CountryCode, PaymentStatus
from app.schemas.payment import (
    PaymentOut,
    PaymentRefundRequest,
    PaymentResolveRequest,
)
from app.services import payments as payments_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/payments", response_model=list[PaymentOut])
async def list_payments(
    _staff: StaffUser,
    session: DbSession,
    status_filter: PaymentStatus | None = Query(default=None, alias="status"),
    country_code: CountryCode | None = None,
    q: str | None = Query(default=None, max_length=120, description="اسمُ طرفٍ أو رقمُه"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PaymentOut]:
    """قائمة الدفعات؛ الفلترة على `disputed` هي شاشة النزاعات.

    **والدولة تُفلتر من الرحلة لا من الدفعة**: لا عمودَ دولةٍ على `payments`،
    وهو صحيح — الدفعة تتبع رحلتها. واللوحة تمرّرها لأن مبدّل الدولة في رأسها
    وعدٌ لكل شاشة، وشاشةٌ تتجاهله تعرض على مشرف السوق الليبي نزاعاتٍ أردنية.
    """
    entries = await payments_service.list_all(
        session,
        status=status_filter,
        country_code=country_code,
        limit=limit,
        offset=offset,
        q=q,
    )
    return [PaymentOut.model_validate(entry) for entry in entries]


@router.post("/payments/{payment_id}/resolve", response_model=PaymentOut)
async def resolve_dispute(
    payment_id: uuid.UUID,
    payload: PaymentResolveRequest,
    staff: StaffUser,
    session: DbSession,
) -> PaymentOut:
    """الفصل في نزاع كليك: وصل المال أو لم يصل (SPEC القسم 6.2)."""
    payment = await payments_service.get_payment(session, payment_id, for_update=True)
    payment = await payments_service.resolve_dispute(
        session,
        payment=payment,
        actor=staff,
        resolution=payload.resolution,
        note=payload.note,
    )
    await session.commit()
    return PaymentOut.model_validate(payment)


@router.post("/payments/{payment_id}/refund", response_model=PaymentOut)
async def refund_payment(
    payment_id: uuid.UUID,
    payload: PaymentRefundRequest,
    admin: AdminUser,
    session: DbSession,
) -> PaymentOut:
    """ردّ دفعةٍ مرّ مالها بالمنصة إلى محفظة الراكب — بقيدين متقابلين."""
    payment = await payments_service.get_payment(session, payment_id, for_update=True)
    payment = await payments_service.refund(
        session, payment=payment, actor=admin, reason=payload.reason
    )
    await session.commit()
    return PaymentOut.model_validate(payment)
