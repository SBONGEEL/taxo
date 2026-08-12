"""تزامنُ تعديل المركبة (`FUTURE-FEATURES` بند 43).

تعديلُ حقلِ هويةٍ **انتقالُ حالة**: يكتب `drivers.status = pending` عن
`approved` قرأها. وقاعدةُ المشروع صريحة — يُقفل الصفُّ قبل أن تُقرأ الحالةُ
ليُقرَّر عليها — والقفلُ يعيش داخل `vehicles.update` نفسِها، فهذا الملف يستدعي
الخدمة لا الراوتر: اختبارٌ يمرّر القفل بيده لا يملك القفل.

**وما يملكه القفل هنا ليس منعَ التكرار بل منعَ الإلغاء.** الخسارةُ من غيره
ليست صفّاً مكرَّراً — هي **إيقافٌ إداريٌّ يُمحى**: مشرفٌ يوقف كبتناً
(`suspended`) في اللحظة التي يغيّر فيها هو لوحته، فيكتب مسارُ المركبة
`pending` فوق `suspended` ويعود الموقوفُ إلى طابور المراجعة — أي إلى بابٍ
يُخرجه منه اعتمادٌ واحد. ولذلك يقيس الاختبارُ **الحالةَ النهائية** لا عدد
النجاحات: الطلبان ينجحان كلاهما، والثابتُ أن الإيقاف يبقى.

والتداخل **مرتَّبٌ عمداً لا متروكٌ للحظ**: الأول يقفل ويمسك معاملته مفتوحة،
والثاني يبدأ وهي مفتوحة — كـ`test_driver_documents_concurrency.py` تماماً.
بحذف `drivers_service.lock` من `vehicles.update` يمرّ الثاني بلا انتظار
ويقرأ `approved` قديمة، فينتهي الكبتن `pending` والاختبارُ يفشل.
"""

from __future__ import annotations

import asyncio
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.models.driver import Driver
from app.models.enums import DriverStatus
from app.models.vehicle import Vehicle
from tests.helpers import approved_driver

DEADLOCK_TIMEOUT = 20

# مهلةُ إمساك المعاملة الأولى مفتوحة: أطولُ من تأخير الثاني بفارقٍ واضح
HOLD_SECONDS = 0.4


async def _vehicle_id(session_factory, driver_id: uuid.UUID) -> uuid.UUID:
    async with session_factory() as session:
        return await session.scalar(
            select(Vehicle.id).where(Vehicle.driver_id == driver_id)
        )


async def _status(session_factory, driver_id: uuid.UUID) -> DriverStatus:
    async with session_factory() as session:
        return await session.scalar(
            select(Driver.status).where(Driver.id == driver_id)
        )


async def test_a_suspension_landing_mid_edit_is_not_undone(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """إيقافٌ إداريٌّ يقع أثناء تعديل اللوحة — والكبتن يبقى موقوفاً."""
    from app.services import vehicles

    driver = await approved_driver(client, session_factory)
    driver_id = driver["driver_id"]
    vehicle_id = await _vehicle_id(session_factory, driver_id)

    async def _suspend_holding_the_transaction() -> None:
        async with session_factory() as session:
            row = await session.scalar(
                select(Driver)
                .where(Driver.id == driver_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            row.status = DriverStatus.SUSPENDED
            await session.flush()
            await asyncio.sleep(HOLD_SECONDS)
            await session.commit()

    async def _change_the_plate_meanwhile() -> None:
        await asyncio.sleep(0.05)
        async with session_factory() as session:
            row = await session.get(Driver, driver_id)
            await vehicles.update(
                session,
                driver=row,
                vehicle_id=vehicle_id,
                changes={"plate_number": "AMM-9999"},
            )
            await session.commit()

    # `wait_for` لأن الجمود يتعلّق ولا يرفع استثناءً
    await asyncio.wait_for(
        asyncio.gather(
            _suspend_holding_the_transaction(), _change_the_plate_meanwhile()
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    # الثابت: التعديلُ وقع، **والإيقاف لم يُلغَ**. بحذف القفل تصير `pending`
    assert await _status(session_factory, driver_id) is DriverStatus.SUSPENDED

    async with session_factory() as session:
        stored = await session.get(Vehicle, vehicle_id)
        assert stored.plate_number == "AMM-9999"


async def test_two_identity_edits_at_once_leave_one_coherent_row(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """تعديلان متزامنان — واللوحةُ والحالة من مصدرٍ واحد.

    كلاهما مسموح (الكبتن يصحّح ما كتبه)، فلا يُرفض الثاني؛ ما يحرسه القفل أن
    يقعا **بالتتابع** فينتهي الصفّان متوافقين: كبتنٌ `pending` بلوحةٍ واحدة، لا
    لوحةُ أحدهما مع اعتمادِ ما قبل الآخر.
    """
    from app.services import vehicles

    driver = await approved_driver(client, session_factory)
    driver_id = driver["driver_id"]
    vehicle_id = await _vehicle_id(session_factory, driver_id)

    async def _edit(plate: str, hold: float, delay: float) -> None:
        await asyncio.sleep(delay)
        async with session_factory() as session:
            row = await session.get(Driver, driver_id)
            await vehicles.update(
                session,
                driver=row,
                vehicle_id=vehicle_id,
                changes={"plate_number": plate},
            )
            await asyncio.sleep(hold)
            await session.commit()

    await asyncio.wait_for(
        asyncio.gather(
            _edit("AMM-1111", HOLD_SECONDS, 0.0),
            _edit("AMM-2222", 0.0, 0.05),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert await _status(session_factory, driver_id) is DriverStatus.PENDING
    async with session_factory() as session:
        stored = await session.get(Vehicle, vehicle_id)
        assert stored.plate_number in {"AMM-1111", "AMM-2222"}
