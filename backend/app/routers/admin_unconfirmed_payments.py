"""طابورُ «المدفوعات غير المؤكَّدة» في اللوحة (`design/PAYMENTS-UNCONFIRMED.md` §٥، SPEC §٦٤-ج، A10 · AM05).

**موجّهٌ واحدٌ في ملفِّه** (قاعدةُ `check:contract`: موجّهٌ ثانٍ في ملفٍّ يُخفي أبوابه). **والقراءةُ لـ`support` والأفعالُ لمن
يملك `payments.resolve`** — قسمةُ `admin_payments.py` بحرفها: فصلُ النزاع حكمٌ بين طرفين، وهذه أحكامٌ من جنسه.

**وكلُّ فعلٍ بسببٍ مكتوبٍ (٨ أحرف على الأقل) يدخل التدقيق باسم صاحبه** في معاملة الفعل نفسِها. **ولا «حذف» ولا «تعديل
مبلغ»** — الدفترُ لا يُعدَّل (القاعدةُ الثانية في `CLAUDE.md`). **ولا «أنهِ الرحلة»**: الإنهاءُ الآليُّ وطابورُه (§٢-٢) لم
يُبنيا عمداً.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.deps import DbSession, DisputeResolver, RedisDep, StaffUser
from app.core.phone import mask_phone
from app.models.enums import CountryCode
from app.schemas.payment import PaymentOut
from app.schemas.unconfirmed_payment import (
    AdminReasonRequest,
    AdminRemindOut,
    AdminUnconfirmedResolveRequest,
    AdminUnconfirmedRow,
    QueuePartyOut,
    ReminderStampOut,
)
from app.services import cancellation, notifications
from app.services import payments as payments_service
from app.services import unconfirmed_payments as unconfirmed_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _party(party: unconfirmed_service.QueueParty) -> QueuePartyOut:
    return QueuePartyOut(
        user_id=party.user_id,
        driver_id=party.driver_id,
        name=party.name,
        # **مقنَّعاً** (§٥: «اسمٌ ورقمٌ مقنَّع») — البادئةُ وآخرُ ثلاث، والملفُّ يُفتح بالمعرّف
        phone_masked=mask_phone(party.phone),
        pending_count=party.pending_count,
        is_test=party.is_test,
    )


def _row(item: unconfirmed_service.QueueRow) -> AdminUnconfirmedRow:
    """**بانٍ واحدٌ للصفّ** — بابٌ واحدٌ ينشره، فلا حقلَ يُملأ هنا ويُنسى هناك."""
    payment = item.payment
    return AdminUnconfirmedRow(
        payment_id=payment.id,
        ride_id=item.ride.id,
        state=item.state,
        completed_at=item.ride.completed_at,
        age_minutes=item.age_minutes,
        amount=payment.amount,
        currency=payment.currency,
        method=payment.method,
        status=payment.status,
        confirmed_by=payment.confirmed_by,
        confirmed_at=payment.confirmed_at,
        declared_at=payment.declared_at,
        cliq_transfer_reference=payment.cliq_transfer_reference,
        cliq_reference_at=payment.cliq_reference_at,
        dispute_reason=payment.dispute_reason,
        disputed_at=payment.disputed_at,
        objected_at=payment.objected_at,
        objection_reason=payment.objection_reason,
        auto_confirm_criteria=payment.auto_confirm_criteria,
        rider=_party(item.rider),
        driver=_party(item.driver) if item.driver is not None else None,
        driver_reminders=payment.driver_reminders,
        driver_reminded_at=payment.driver_reminded_at,
        rider_reminders=payment.rider_reminders,
        rider_reminded_at=payment.rider_reminded_at,
        reminder_trail=[ReminderStampOut(to=to, at=at) for to, at in item.trail],
        in_flow=item.in_flow,
    )


@router.get("/payments/unconfirmed", response_model=list[AdminUnconfirmedRow])
async def list_unconfirmed(
    _staff: StaffUser,
    session: DbSession,
    country_code: CountryCode | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminUnconfirmedRow]:
    """**الأقدمُ أوّلاً** — ما ينتظر أحداً، والنزاعات، وما أُتمّ آلياً واعتُرض عليه. **ولأسواقٍ اشتعل فيها المفتاحُ وحدَها**."""
    rows = await unconfirmed_service.queue(
        session, country=country_code, limit=limit, offset=offset
    )
    return [_row(row) for row in rows]


@router.post(
    "/payments/unconfirmed/{payment_id}/remind", response_model=AdminRemindOut
)
async def remind_now(
    payment_id: uuid.UUID,
    payload: AdminReasonRequest,
    staff: DisputeResolver,
    session: DbSession,
    redis: RedisDep,
) -> AdminRemindOut:
    """**«أرسل تذكيراً الآن»** للطرف المنتظَر — **ولا يمسّ مواعيدَ الجدول** (شرطُ الإتمام الآليّ). والإرسالُ بعد الـcommit."""
    payment = await payments_service.get_payment(session, payment_id, for_update=True)  # قفلُ التذكير اليدويّ
    notices = await unconfirmed_service.admin_remind(
        session, payment=payment, actor=staff, reason=payload.reason
    )
    ride = await payments_service.ride_of(session, payment)
    sides = unconfirmed_service.reminded_sides(notices, ride)
    await session.commit()
    await unconfirmed_service.send(session, redis, notices)
    return AdminRemindOut(sent_to=sides)


@router.post(
    "/payments/unconfirmed/{payment_id}/resolve", response_model=PaymentOut
)
async def resolve_unconfirmed(
    payment_id: uuid.UUID,
    payload: AdminUnconfirmedResolveRequest,
    staff: DisputeResolver,
    session: DbSession,
    redis: RedisDep,
) -> PaymentOut:
    """**«احسم: مدفوع»** (ما يكتبه التأكيدُ حرفاً، `confirmed_by = admin`) **أو «غيرُ مدفوع»** (`failed`، لا قيد).

    **قفلُ صفِّ الدفعة قبل الفحص**: بغيره يحسم المشرفُ «مدفوع» على صفٍّ أكّده الكبتنُ في اللحظة نفسِها — حكمان لواقعةٍ واحدة.
    """
    payment = await payments_service.get_payment(session, payment_id, for_update=True)  # قفلُ الحسم
    payment = await unconfirmed_service.admin_resolve(
        session,
        payment=payment,
        actor=staff,
        outcome=payload.outcome,
        reason=payload.reason,
    )
    ride = await payments_service.ride_of(session, payment)
    ride_id, rider_id = ride.id, ride.rider_id
    settled = payment.confirmed_by is not None and payment.objected_at is None
    await session.commit()
    # **ويُقال للطرفين ما يُقال بعد «استلمت»** — البابان نفساهما بعد الـcommit (`routers/payments.confirm_payment`): التسويةُ
    # قد تحمل رسمَ إلغاءٍ سابقاً (`settle` → `cancellation.collect_with_ride`)، **فإعلانُه يتبعها أيّاً كان من أكّد**
    if settled:
        await notifications.publish_payment_confirmed(
            session, redis, rider_id=rider_id, payment=payment
        )
        await cancellation.announce_ride_collection(session, redis, ride_id=ride_id)
    return PaymentOut.model_validate(payment)


@router.post(
    "/payments/unconfirmed/{payment_id}/dispute", response_model=PaymentOut
)
async def dispute_unconfirmed(
    payment_id: uuid.UUID,
    payload: AdminReasonRequest,
    staff: DisputeResolver,
    session: DbSession,
    redis: RedisDep,
) -> PaymentOut:
    """**«حوّل إلى نزاع»** — `disputed` **ويُسأل الطرفان بنصّهما** (بعد الـcommit). لا قيد."""
    payment = await payments_service.get_payment(session, payment_id, for_update=True)  # قفلُ النزاع
    notices = await unconfirmed_service.admin_dispute(
        session, payment=payment, actor=staff, reason=payload.reason
    )
    await session.commit()
    await unconfirmed_service.send(session, redis, notices)
    return PaymentOut.model_validate(payment)
