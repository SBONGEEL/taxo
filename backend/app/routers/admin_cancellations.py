"""رسومُ الإلغاء في اللوحة (`design/CANCELLATION-FEE.md` §3 و§10).

**بابان لا ثالث لهما، وكلاهما يُغلق صفّاً بلا أن يحرّك مالاً:**

* **الإعفاء** (§3) — وهو **بابُ الاعتراض بعد الحدث**: القياسُ آليٌّ لحظةَ
  الإلغاء كي لا يُحبس من يريد الإلغاءَ الآن خلف طابورٍ بشريّ، وهذا هو البابُ
  الذي وُعد به بعدها. من قال «كنتُ قريباً» أو «لم يتحرك أحد» يُراجَع هنا.
* **الشطب** (§10) — حين لا يعود الراكبُ أبداً وكان مآلُ الدولة «تشطبه الإدارة».

**ولا زرَّ «حصّله»**: التحصيلُ يقع في محفظة صاحبه — خصماً مع رحلةٍ أو لحظةَ
شحن. وزرٌّ هنا يعني كتابةَ مالٍ من بابٍ ثانٍ، وهو ما لا تفعله أيُّ شاشةٍ في
هذه اللوحة (قاعدةُ جدول السلف نفسُها).

**ولا زرَّ «تتحمّلها الشركة» أيضاً**: ذلك **إعدادُ دولةٍ تطبّقه الدورة**، لا
قرارٌ يُتخذ صفّاً صفّاً — وزرٌّ به يجعل الخسارةَ تقع بمزاجِ من يفتح الشاشة
بينما وُضع الإعدادُ ليقرّرها مرةً واحدةً بقاعدةٍ مكتوبة.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.core.deps import AdminUser, DbSession, StaffUser
from app.core.exceptions import NotFound
from app.models.cancellation import RideCancellationCharge
from app.models.driver import Driver
from app.models.enums import CancellationChargeStatus, CountryCode
from app.models.ride import Ride
from app.models.user import User
from app.schemas.cancellation import CancellationChargeRow, ChargeReasonRequest
from app.services import cancellation

router = APIRouter(prefix="/admin/cancellation-charges", tags=["admin"])


def _row(record) -> CancellationChargeRow:
    charge, country, payer_name, payer_phone, beneficiary_name, carrier_name = record
    return CancellationChargeRow(
        id=charge.id,
        ride_id=charge.ride_id,
        country_code=country,
        amount=charge.amount,
        currency=charge.currency,
        status=charge.status,
        payer_name=payer_name,
        payer_phone=payer_phone,
        beneficiary_driver_id=charge.beneficiary_driver_id,
        beneficiary_name=beneficiary_name,
        carrier_driver_id=charge.carrier_driver_id,
        carrier_name=carrier_name,
        carrier_due_at=charge.carrier_due_at,
        collected_from_ride_id=charge.collected_from_ride_id,
        settled_at=charge.settled_at,
        waive_reason=charge.waive_reason,
        writeoff_reason=charge.writeoff_reason,
        created_at=charge.created_at,
    )


def _select():
    """استعلامُ الصف بأسمائه — **بابٌ واحدٌ للقائمة ولإعادة صفٍّ بعد إجراء**.

    والدولةُ تُقرأ من الرحلة لا عمودٌ مكرَّرٌ على الصف: الرسمُ يتبع رحلتَه كما
    تتبع الدفعةُ رحلتَها (`payments.list_all`)، فالضمُّ هنا لا عمودٌ هناك.
    """
    beneficiary_driver = aliased(Driver)
    beneficiary_user = aliased(User)
    carrier_driver = aliased(Driver)
    carrier_user = aliased(User)
    payer = aliased(User)

    stmt = (
        select(
            RideCancellationCharge,
            Ride.country_code,
            payer.name,
            payer.phone,
            beneficiary_user.name,
            carrier_user.name,
        )
        .join(Ride, Ride.id == RideCancellationCharge.ride_id)
        .outerjoin(payer, payer.id == RideCancellationCharge.payer_user_id)
        .outerjoin(
            beneficiary_driver,
            beneficiary_driver.id == RideCancellationCharge.beneficiary_driver_id,
        )
        .outerjoin(beneficiary_user, beneficiary_user.id == beneficiary_driver.user_id)
        .outerjoin(
            carrier_driver,
            carrier_driver.id == RideCancellationCharge.carrier_driver_id,
        )
        .outerjoin(carrier_user, carrier_user.id == carrier_driver.user_id)
        .order_by(RideCancellationCharge.created_at.desc())
    )
    return stmt


@router.get("", response_model=list[CancellationChargeRow])
async def list_charges(
    _staff: StaffUser,
    session: DbSession,
    country_code: CountryCode | None = None,
    status: CancellationChargeStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CancellationChargeRow]:
    stmt = _select()
    if country_code is not None:
        stmt = stmt.where(Ride.country_code == country_code)
    if status is not None:
        stmt = stmt.where(RideCancellationCharge.status == status)

    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    return [_row(record) for record in rows]


@router.post("/{charge_id}/waive", response_model=CancellationChargeRow)
async def waive_charge(
    charge_id: uuid.UUID,
    payload: ChargeReasonRequest,
    admin: AdminUser,
    session: DbSession,
) -> CancellationChargeRow:
    """يُعفي راكباً من رسمٍ لم يُحصَّل بعد — **بسببٍ مكتوبٍ يدخل التدقيق**."""
    await cancellation.waive(
        session, charge_id=charge_id, admin=admin, reason=payload.reason
    )
    await session.commit()
    return await _reload(session, charge_id)


@router.post("/{charge_id}/write-off", response_model=CancellationChargeRow)
async def write_off_charge(
    charge_id: uuid.UUID,
    payload: ChargeReasonRequest,
    admin: AdminUser,
    session: DbSession,
) -> CancellationChargeRow:
    """يشطب رسماً لم يعد صاحبُه (§10) — اعترافٌ بالخسارة باسم من قرّرها.

    **ولا قيدَ يُكتب في الدفتر**: لم يتحرك مالٌ في محفظة أحد، وقيدُ «تسوية»
    وهميٌّ يجعل الكشفَ يقول إن الراكب سدَّد — وهو لم يفعل.
    """
    await cancellation.write_off(
        session, charge_id=charge_id, admin=admin, reason=payload.reason
    )
    await session.commit()
    return await _reload(session, charge_id)


async def _reload(session, charge_id: uuid.UUID) -> CancellationChargeRow:
    """قراءةٌ ثانيةٌ بعد الالتزام: الصفُّ يُعاد بأسمائه كما يُعاد في القائمة."""
    record = (
        await session.execute(
            _select().where(RideCancellationCharge.id == charge_id)
        )
    ).first()
    if record is None:  # pragma: no cover - يمنعه القفلُ في الخدمة
        raise NotFound("رسمُ الإلغاء غير موجود")
    return _row(record)
