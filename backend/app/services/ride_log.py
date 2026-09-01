"""قراءةُ سجل الرحلات للوحة (SPEC القسم 13/4).

**قراءةٌ فقط: لا دالةَ هنا تغيّر حالة رحلة.** كل انتقالٍ يمر بـ`services/
rides.py` وحده كما تقول `CLAUDE.md`، وشاشةُ السجل تعرض ولا تقرر — ولا يوجد
في القسم 13/4 إجراءٌ إداريٌّ على الرحلة نفسها: النزاعُ يُفصل على **الدفعة**
(`admin_payments.resolve_dispute`) لا على الرحلة، وإسنادُ سائقٍ يدوياً مؤجَّلٌ
في `FUTURE-FEATURES` لأن العرض يقع على كبتنٍ واحدٍ في كل لحظة (القسم 5).

وقاعدتان تحكمان شكل الاستعلامين:

1. **الجمعُ في الاستعلام لا في اللوحة.** حالُ الدفع على رحلةٍ ليست عموداً:
   الدفعُ المختلط صفّان (القسم 6)، فـ«هل سُدِّدت؟» مجموعُ الدفعات المؤكدة
   مقابل الأجرة. جمعُه في الواجهة يعطي رقماً يختلف حين تُقصّ الصفحة — وهو
   بالضبط ما يمنعه القسم 14 في المال ويمنعه `services/stats.py` في العدّ.
2. **صفّان لكل رحلة على الأكثر في القائمة**: الرحلات في استعلام، وملخّصُ
   دفعاتها في استعلامٍ ثانٍ على نفس المجموعة — لا نداءَ لكل صف. وجمعُ
   الدفعات في نفس الاستعلام الأول كان سيضاعف صفوف الرحلة بعدد دفعاتها.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.driver import Driver
from app.models.enums import CountryCode, PaymentMethod, PaymentStatus, RideStatus
from app.models.payment import Payment
from app.models.rating import Rating
from app.models.ride import Ride, RideRoutePoint
from app.models.payment import OWING_PAYMENT_STATUSES
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services import admin_search, settlement
from app.services.settlement import SettlementState

# سقفُ نقاط المسار في شاشة التفاصيل. رحلةٌ بنقطةٍ كل عشرين ثانية تكتب مئةً
# وثمانين نقطةً في الساعة، فألفٌ تغطي أطول رحلةٍ معقولة؛ وما تجاوزها يُقصّ
# **ويُقال إنه قُصّ** — مسارٌ ناقصٌ يُقرأ كاملاً دليلٌ يكذب في نزاع
ROUTE_POINT_CAP = 1000

# الدفعاتُ التي «تشغل» الأجرة — نفس مجموعة `payments.OWING_PAYMENT_STATUSES`
# لكن المعروضَ هنا هو ما **تأكّد** وحده: الرقم يُقرأ «كم وصل فعلاً»
SETTLED_STATUS = PaymentStatus.CONFIRMED


@dataclass(frozen=True, slots=True)
class PaymentSummary:
    """ملخّصُ دفعات رحلةٍ واحدة — محسوبٌ في القاعدة."""

    methods: list[PaymentMethod]
    paid_amount: Decimal
    has_open_dispute: bool
    # ما تشغله الصفوفُ القائمة — **غيرُ ما تأكّد**: دفعةٌ `pending` تمنع فتحَ
    # صفٍّ جديد ولا تُقرأ «وصلت»، والفرقُ بينهما هو الفرقُ بين «بانتظار
    # التأكيد» و«اكتمل الدفع» على الشاشة (`services/settlement.py`)
    held_amount: Decimal = Decimal("0.000")


EMPTY_SUMMARY = PaymentSummary(
    methods=[], paid_amount=Decimal("0.000"), has_open_dispute=False
)


def settlement_of(ride: Ride, summary: PaymentSummary) -> SettlementState:
    """حالُ سدادِ صفٍّ في السجل — **من المصدر الواحد، لا بحسابٍ في الشاشة**."""
    return settlement.state_from_totals(
        chargeable=settlement.chargeable_of(ride),
        held=summary.held_amount,
        paid=summary.paid_amount,
        contested=summary.has_open_dispute,
    )


def _base_query():
    """الرحلة ومعها طرفاها — `selectinload` لا `join` كي لا تتكرر الصفوف."""
    return select(Ride).options(
        selectinload(Ride.rider),
        selectinload(Ride.driver).selectinload(Driver.user),
        selectinload(Ride.driver).selectinload(Driver.vehicles),
    )


async def list_rides(
    session: AsyncSession,
    *,
    country: CountryCode | None = None,
    status: RideStatus | None = None,
    driver_id: uuid.UUID | None = None,
    rider_id: uuid.UUID | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Ride]:
    """صفحةٌ من السجل بفلاترها (القسم 13/4).

    والبحثُ `q` على **اسم الطرفين ورقميهما ومعرّف الرحلة** — وهو ما يكتبه
    المشرف في حقل الرأس. ومعرّفُ الرحلة يُطابَق كاملاً حين يكون UUID صالحاً:
    مطابقةُ بادئته نصّياً تجعل بحثاً بحرفٍ واحد يمسح الجدول كلَّه.
    """
    stmt = _base_query().order_by(Ride.created_at.desc())

    if country is not None:
        stmt = stmt.where(Ride.country_code == country)
    if status is not None:
        stmt = stmt.where(Ride.status == status)
    if driver_id is not None:
        stmt = stmt.where(Ride.driver_id == driver_id)
    if rider_id is not None:
        stmt = stmt.where(Ride.rider_id == rider_id)
    if from_at is not None:
        stmt = stmt.where(Ride.created_at >= from_at)
    if to_at is not None:
        stmt = stmt.where(Ride.created_at <= to_at)

    text = (query or "").strip()
    if text:
        conditions = []
        try:
            conditions.append(Ride.id == uuid.UUID(text))
        except ValueError:
            pass

        # **حروفُ `LIKE` تُهرَّب** (عطبٌ قِيس 2026-09-02، والبيتُ الواحد
        # `services/admin_search.py`): كان النمطُ عارياً — **فمن كتب `%` رأى
        # السجلَّ كلَّه وظنّه نتيجةَ بحثه**
        pattern = admin_search.like(text)
        rider = select(User.id).where(
            or_(User.name.ilike(pattern), User.phone.ilike(pattern))
        )
        conditions.append(Ride.rider_id.in_(rider))
        conditions.append(
            Ride.driver_id.in_(
                select(Driver.id).join(User, Driver.user_id == User.id).where(
                    or_(User.name.ilike(pattern), User.phone.ilike(pattern))
                )
            )
        )
        stmt = stmt.where(or_(*conditions))

    return list((await session.scalars(stmt.limit(limit).offset(offset))).all())


async def payment_summaries(
    session: AsyncSession, ride_ids: list[uuid.UUID]
) -> dict[uuid.UUID, PaymentSummary]:
    """ملخّصُ الدفعات لمجموعةِ رحلاتٍ **في استعلامٍ واحد**.

    استعلامٌ ثانٍ لا ضمُّه إلى الأول: رحلةٌ بدفعتين تصير صفّين في الضمّ،
    فتُعدّ الرحلةُ مرتين في صفحةٍ مسقوفة بخمسين.
    """
    if not ride_ids:
        return {}

    rows = await session.execute(
        select(
            Payment.ride_id,
            func.array_agg(func.distinct(Payment.method)),
            func.coalesce(
                func.sum(Payment.amount).filter(Payment.status == SETTLED_STATUS), 0
            ),
            func.count().filter(Payment.status == PaymentStatus.DISPUTED) > 0,
            func.coalesce(
                func.sum(Payment.amount).filter(
                    Payment.status.in_(OWING_PAYMENT_STATUSES)
                ),
                0,
            ),
        )
        .where(Payment.ride_id.in_(ride_ids))
        .group_by(Payment.ride_id)
    )

    return {
        ride_id: PaymentSummary(
            methods=[PaymentMethod(value) for value in sorted(methods or [])],
            # ثلاثُ منازل كبقية المال: `Decimal(0)` يخرج «0» فيقرأ الصفَّ
            # مختلفاً عن جاره في نفس العمود
            paid_amount=Decimal(paid).quantize(Decimal("0.001")),
            has_open_dispute=bool(disputed),
            held_amount=Decimal(held).quantize(Decimal("0.001")),
        )
        for ride_id, methods, paid, disputed, held in rows.all()
    }


async def get_ride(session: AsyncSession, ride_id: uuid.UUID) -> Ride | None:
    return await session.scalar(_base_query().where(Ride.id == ride_id))


async def payments_of(session: AsyncSession, ride_id: uuid.UUID) -> list[Payment]:
    return list(
        (
            await session.scalars(
                select(Payment)
                .where(Payment.ride_id == ride_id)
                .order_by(Payment.created_at)
            )
        ).all()
    )


async def ratings_of(session: AsyncSession, ride_id: uuid.UUID) -> list[Rating]:
    return list(
        (
            await session.scalars(
                select(Rating)
                .where(Rating.ride_id == ride_id)
                .order_by(Rating.created_at)
            )
        ).all()
    )


async def route_of(
    session: AsyncSession, ride_id: uuid.UUID
) -> tuple[list[RideRoutePoint], bool]:
    """نقاط المسار مرتّبةً زمنياً، ومعها هل قُصّ الذيل.

    القراءةُ `CAP + 1` صفاً: القصُّ يُعرف بوجود الصفّ الزائد لا باستعلام عدٍّ
    ثانٍ على نفس الجدول.
    """
    rows = list(
        (
            await session.scalars(
                select(RideRoutePoint)
                .where(RideRoutePoint.ride_id == ride_id)
                .order_by(RideRoutePoint.created_at)
                .limit(ROUTE_POINT_CAP + 1)
            )
        ).all()
    )
    return rows[:ROUTE_POINT_CAP], len(rows) > ROUTE_POINT_CAP


def plate_of(ride: Ride) -> str | None:
    """لوحةُ المركبة إن كان للكبتن مركبةٌ مسجّلة — يحتاج `vehicles` محمّلة."""
    if ride.driver is None or not ride.driver.vehicles:
        return None
    vehicle: Vehicle = ride.driver.vehicles[0]
    return vehicle.plate_number
