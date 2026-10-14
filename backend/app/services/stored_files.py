"""**كلُّ عمودٍ يحفظ مسارَ ملفٍّ تحت جذر التخزين — في قائمةٍ واحدة** (قِيس ٢٠٢٦-١٠-١٤).

**العلّةُ مقيسة**: كنسُ اليتامى الأسبوعيُّ (`maintenance.sweep_orphan_documents`) كان يعرف عمودين — الوثائقَ وتسجيلاتِ المكالمات — **وتسعةُ
مستدعين يكتبون تحت الجذر نفسِه**. فكان كلُّ ما عداهما «يتيماً» عنده: صورُ المستخدمين · صورُ أشكال المركبات (٧٣٨ ملفّاً على الإنتاج) ·
لافتاتُ المتجر · رموزُ QR · إيصالاتُ الدفع. **ولم يمحها بعدُ** (قِيس: صفرُ غائبٍ منها على قرص الإنتاج) **لأنها أحدثُ من آخر كنس** —
وكان الكنسُ التالي (الجمعة ٠٤:٢٠) سيمحوها كلَّها ويُبقي صفوفَها تَعِد بملفّات.

**فالقائمةُ هنا، والكنسُ يقرؤها، و`test_stored_files.py` يمسح النماذجَ كلَّها**: عمودٌ اسمُه `…_path` لا يدخلها يُسقط المجموعة —
**فعمودُ الملفّ العاشرُ لا يُنسى كما نُسيت السبعة**.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.driver import DriverDocument
from app.models.feedback import AppFeedback
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.payment_setting import PaymentSetting
from app.models.ride_call import RideCall
from app.models.storefront import PromoBanner
from app.models.user import User
from app.models.vehicle_skin import VehicleSkin

#: **الأعمدةُ التي تكتب فيها `storage.save` (أو `_write_svg`) مساراً نسبيّاً** — وأيُّ عمودٍ جديدٍ يُضاف هنا في الإيداع نفسِه
STORED_FILE_COLUMNS: tuple[InstrumentedAttribute, ...] = (
    DriverDocument.file_path,
    RideCall.recording_path,
    User.photo_path,
    VehicleSkin.store_image_path,
    VehicleSkin.map_image_path,
    PromoBanner.image_path,
    PayMethod.qr_image_path,
    PaymentRequest.receipt_path,
    PaymentSetting.cliq_qr_path,
    AppFeedback.screenshot_path,
)


async def referenced_paths(session: AsyncSession) -> set[str]:
    """كلُّ مسارٍ يشير إليه صفّ — **وما سواه تحت الجذر يتيم**."""
    known: set[str] = set()
    for column in STORED_FILE_COLUMNS:
        known |= {path for path in (await session.scalars(select(column).where(column.is_not(None)))) if path}
    return known
