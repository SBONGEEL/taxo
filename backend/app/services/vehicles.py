"""تعديلُ بيانات المركبة من التطبيق (`FUTURE-FEATURES` بند 43/18).

**والبندُ يقول إنه يحتاج قرارَ سياسة، والسياسةُ مقرَّرةٌ أصلاً في مكانٍ آخر**:
المرحلة 9-ب قضت أن **استبدال مستندٍ مطلوب يُسقط اعتماد الكبتن إلى `pending`**
حتى يُراجَع الجديد (SPEC القسم 4/`driver_documents`)، لأن «الاعتماد شهادةٌ على
مستنداتٍ بعينها رآها مشرف». و**رخصةُ المركبة أحدُ تلك المستندات الثلاثة** —
فتغييرُ لوحةِ المركبة أو طرازها بعد الاعتماد هو نفسُ الفعل بحرفه: اعتمادٌ صدر
لمركبةٍ يُشغَّل به غيرُها. فلا سياسةَ جديدة هنا، بل **امتدادُ سياسةٍ قائمة إلى
البابِ الثاني الذي يصل إلى نفس النتيجة**.

ومن ذلك تنبع ثلاث قواعد:

1. **حقولُ الهوية تُسقط الاعتماد** (`plate_number`, `make`, `model`, `year`,
   `category`): كلُّها مكتوبةٌ في رخصة المركبة، وتغييرُها يجعل ما رآه المشرف
   غيرَ ما يسير في الشارع. والفئةُ معها لأنها تحدّد التسعيرة.
2. **واللونُ لا يُسقطه**: لونٌ خاطئ يجعل الراكب لا يعرف السيارة — إزعاجٌ لا
   خطر، وإسقاطُ اعتمادٍ لتصحيح خطأٍ إملائي في «أبيض» يُخرج كبتناً من العمل
   يوماً لأجل لا شيء. **وهذا هو الحدُّ**: ما تشهد عليه الورقةُ هويةً يُراجَع،
   وما يصف المظهر يُصحَّح.
3. **ويُرفض التعديل أثناء رحلةٍ جارية** (409) — حرفياً كاستبدال المستند: إسقاطُ
   الاعتماد وسطها يُخرج الكبتن من `presence_context` فيتجمّد موقعُه على خريطة
   راكبه ثم يُطلق تنبيهَ «انقطع اتصال الكبتن» (القسم 5) على من لم ينقطع.

**والجوابُ يقول ما وقع صراحةً** (`approval_reverted`)، كجواب رفع المستند:
بغيره يكتشف الكبتن أنه خرج من التوزيع حين لا تصله طلبات، لا حين فعلَ ما أخرجه.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.models.driver import Driver
from app.models.enums import DriverStatus
from app.models.ride import ACTIVE_DRIVER_STATUSES, Ride
from app.models.vehicle import Vehicle
from app.services import drivers as drivers_service

# ما تشهد عليه رخصةُ المركبة هويةً — تغييرُه يعيد الكبتن إلى المراجعة
IDENTITY_FIELDS: frozenset[str] = frozenset(
    {"plate_number", "make", "model", "year", "category"}
)


@dataclass(frozen=True, slots=True)
class VehicleUpdateResult:
    vehicle: Vehicle
    approval_reverted: bool
    driver_status: DriverStatus


async def _has_active_ride(session: AsyncSession, driver_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(Ride.id)
            .where(Ride.driver_id == driver_id, Ride.status.in_(ACTIVE_DRIVER_STATUSES))
            .limit(1)
        )
    )


async def update(
    session: AsyncSession,
    *,
    driver: Driver,
    vehicle_id: uuid.UUID,
    changes: dict[str, object],
) -> VehicleUpdateResult:
    """يعدّل مركبةَ الكبتن — ويُسقط اعتمادَه إن مسّ التعديلُ هويتَها."""
    vehicle = await session.scalar(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.driver_id == driver.id)
    )
    if vehicle is None:
        raise NotFound("المركبة غير موجودة")

    # ما تغيّر **فعلاً**: إرسالُ نفس اللوحة ليس تغييراً، ولا يجوز أن يُسقط
    # اعتماداً — والتطبيقُ يرسل الحقول كلَّها من نموذجٍ ممتلئ
    changed = {
        field: value
        for field, value in changes.items()
        if getattr(vehicle, field) != value
    }
    if not changed:
        return VehicleUpdateResult(
            vehicle=vehicle, approval_reverted=False, driver_status=driver.status
        )

    touches_identity = bool(IDENTITY_FIELDS & changed.keys())
    # **الحالةُ تُقرأ تحت قفل الصف** لا قبله: بغيره يكتب هذا المسارُ `pending`
    # عن `approved` قرأها قبل إيقافٍ إداريٍّ وقع بينهما، فيُلغي الإيقاف
    if touches_identity:
        await drivers_service.lock(session, driver)
    reverts = touches_identity and driver.status is DriverStatus.APPROVED

    if reverts and await _has_active_ride(session, driver.id):
        raise Conflict(
            "لا يمكن تعديل بيانات المركبة أثناء رحلة جارية — أنهِ الرحلة ثم عدّلها"
        )

    for field, value in changed.items():
        setattr(vehicle, field, value)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("رقم اللوحة مسجَّل لمركبةٍ أخرى") from exc

    if reverts:
        await drivers_service.set_status(
            session,
            driver=driver,
            status=DriverStatus.PENDING,
            # لا مشرفَ وراء هذا: فعلُ الكبتن نفسه هو ما أسقط الاعتماد
            actor=None,
            reason="vehicle_identity_changed",
        )

    return VehicleUpdateResult(
        vehicle=vehicle, approval_reverted=reverts, driver_status=driver.status
    )
