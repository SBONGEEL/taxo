"""الحسابات في اللوحة: القائمة والفلترة واعتماد الكباتن (SPEC القسم 13.2/13.3).

شريحةٌ صغيرة من صفحتي «الكباتن» و«الركاب» تسبق واجهتَهما في المرحلة 11،
لأن قاعدتين من المرحلة 8-ب لا مكان لهما بغيرها:

- **الحسابات غير المحققة تُعلَّم وتُفلتر**: الرقم غير المُثبَت حالةٌ استثنائية
  لا تقع إلا بإطفاء مفتاح الطوارئ، ولا تُعالَج إن لم تُرَ.
- **لا يُعتمد كبتنٌ غير محقق الرقم مهما كان المفتاح**: رقمُ الكبتن هو ما
  يستلم عليه حوالات كليك (SPEC القسم 6/9)، فاعتمادُ من لا نعرف أنه يملكه
  إرسالُ مالٍ إلى رقمٍ مجهول.

وأضافت **المرحلة 9-ب** مراجعةَ المستندات إلى نفس الملف (SPEC القسم 13/2):
معاينةُ كل مستند وقبولُه أو رفضُه بسبب. القراءة لـ staff والقرار لـ admin
وحده — مراجعةٌ تفتح باب العمل على المنصة ليست إجراء دعمٍ فني (القسم 13/8).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core.deps import AdminUser, DbSession, RedisDep, StaffUser
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, UserRole
from app.models.user import User
from app.routers.drivers import document_response
from app.schemas.auth import UserOut
from app.schemas.driver import (
    DocumentReviewIn,
    DriverDocumentOut,
    DriverDocumentsOut,
    DriverOut,
)
from app.services import (
    documents as documents_service,
    drivers as drivers_service,
    notifications,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _staff: StaffUser,
    session: DbSession,
    role: UserRole | None = None,
    country_code: CountryCode | None = None,
    phone_verified: bool | None = Query(
        default=None,
        description="فلترة الحسابات غير المحققة — تُعالَج أولاً بعد إعادة تفعيل المفتاح",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[UserOut]:
    """قائمة الحسابات بوسم التحقق — و`UserOut.phone_verified` هو الوسم."""
    stmt = select(User).order_by(User.created_at.desc())
    if role is not None:
        stmt = stmt.where(User.role == role)
    if country_code is not None:
        stmt = stmt.where(User.country_code == country_code)
    if phone_verified is True:
        stmt = stmt.where(User.phone_verified_at.is_not(None))
    elif phone_verified is False:
        stmt = stmt.where(User.phone_verified_at.is_(None))

    rows = (await session.scalars(stmt.limit(limit).offset(offset))).all()
    return [UserOut.model_validate(row) for row in rows]


@router.get("/drivers/{driver_id}/documents", response_model=DriverDocumentsOut)
async def list_driver_documents(
    driver_id: uuid.UUID, _staff: StaffUser, session: DbSession
) -> DriverDocumentsOut:
    """مستندات كبتنٍ للمراجعة، ومعها ما ينقصه للاعتماد (SPEC القسم 13/2)."""
    await _driver(session, driver_id)
    return DriverDocumentsOut(
        documents=[
            DriverDocumentOut.model_validate(document)
            for document in await documents_service.list_for_driver(session, driver_id)
        ],
        missing_required=await documents_service.missing_required(session, driver_id),
    )


@router.get("/drivers/{driver_id}/documents/{document_id}/file")
async def download_driver_document(
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    _staff: StaffUser,
    session: DbSession,
) -> FileResponse:
    """معاينة المستند في اللوحة — بنفس ترويسات مسار الكبتن."""
    document = await documents_service.get_for_review(
        session, driver_id=driver_id, document_id=document_id
    )
    return document_response(document)


@router.post(
    "/drivers/{driver_id}/documents/{document_id}/review",
    response_model=DriverDocumentOut,
)
async def review_driver_document(
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentReviewIn,
    admin: AdminUser,
    session: DbSession,
    redis: RedisDep,
) -> DriverDocumentOut:
    """قبول مستند أو رفضه — **admin حصراً** (SPEC القسم 13/8).

    المراجعة قرارٌ يفتح باب العمل على المنصة، لا إجراءَ دعمٍ فني. وقفلُ
    الصفِّ داخل `documents.review` لا هنا: بغيره تمر ضغطتان متزامنتان فيصل
    الكبتنَ إشعاران متناقضان عن وثيقةٍ واحدة.
    """
    driver = await _driver(session, driver_id)
    document = await documents_service.review(
        session,
        driver_id=driver_id,
        document_id=document_id,
        actor=admin,
        approved=payload.approved,
        note=payload.note,
    )
    await session.commit()
    await session.refresh(document)

    # بعد الـ commit كما تفرض قاعدة البثّ: حالةٌ تُعلن ثم تُلغى أسوأ من
    # حالةٍ تتأخر لحظة
    await notifications.publish_document_review(
        session, redis, driver_user_id=driver.user_id, document=document
    )
    return DriverDocumentOut.model_validate(document)


@router.post("/drivers/{driver_id}/approve", response_model=DriverOut)
async def approve_driver(
    driver_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> DriverOut:
    """اعتماد الكبتن — بحارسَي `services/drivers.approve`.

    رقمٌ مُثبت (8-ب) **ومستنداتٌ مطلوبةٌ مقبولةٌ كلها** (9-ب). فالزرُّ لم يعد
    يعمل والمستنداتُ فارغة، وهو ما كان يقع قبل هذه المرحلة.
    """
    driver = await _driver(session, driver_id)
    driver = await drivers_service.approve(session, driver=driver, actor=admin)
    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)


@router.post("/drivers/{driver_id}/reject", response_model=DriverOut)
async def reject_driver(
    driver_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> DriverOut:
    driver = await _driver(session, driver_id)
    driver = await drivers_service.set_status(
        session, driver=driver, status=DriverStatus.REJECTED, actor=admin
    )
    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)


async def _driver(session, driver_id: uuid.UUID) -> Driver:
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFound("الكبتن غير موجود")
    return driver
