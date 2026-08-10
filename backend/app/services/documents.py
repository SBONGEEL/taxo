"""مستندات الكبتن: الرفع والاستبدال والمراجعة (SPEC القسم 12/1 و13/2 — المرحلة 9-ب).

الجدول `driver_documents` قائمٌ منذ المرحلة 1 ولم يكن له مسارٌ يكتبه: كان
المشروع يعتمد كباتن بلا مستندٍ واحد. هذه الطبقة هي ما كان ناقصاً.

**القواعد التي تحملها:**

- **صفٌّ واحد لكل نوع، والرفعُ يستبدل.** يفرضه الفريد
  `(driver_id, doc_type)`؛ والاستبدال يعيد الحالة `pending` ويمحو أثر
  المراجعة السابقة — وثيقةٌ جديدة مراجعةٌ جديدة.
- **الملف يُحفظ قبل الصف، ويُحذف بعد الـ commit.** ملفٌّ يتيمٌ بلا صفّ
  نفايةٌ تُنظَّف؛ وصفٌّ يشير إلى ملفٍ محذوف عطلٌ يراه المستخدم. ولذلك يعيد
  `upload` مسار الملف المُستبدَل ولا يحذفه بنفسه: من يملك الـ commit هو من
  يملك الحذف.
- **المراجعة انتقالُ حالة، فتقع تحت قفل الصف** (`for_update`). بغيره تقرأ
  مراجعتان متزامنتان `pending` نفسها فتمرّان معاً: قيدا تدقيقٍ وإشعاران
  متناقضان لوثيقةٍ واحدة. ولذلك «الحكم نفسه مرتين» يُرفض بـ409 بينما تبديل
  الحكم مسموح — فمشرفٌ ضغط «رفض» خطأً يصحّحه، ولا تمر ضغطتان متزامنتان.
- **لا يُعتمد الكبتن قبل قبول مستنداته المطلوبة** (`missing_required`) —
  حارسٌ ثانٍ بجانب `phone_verified_at` في `services/drivers.approve`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.exceptions import Conflict, NotFound
from app.models.driver import REQUIRED_DOCUMENT_TYPES, Driver, DriverDocument
from app.models.enums import AuditAction, DocumentReviewStatus, DocumentType
from app.models.user import User
from app.services import audit

# الاسم المعروض لكل نوع — يقرؤه الإشعار ورسالةُ «مستندات لم تُعتمد بعد».
# هنا لا في `notifications.py`: النوع مفهومُ هذه الطبقة، ومن يسمّيه في مكانين
# يجعلهما يفترقان
DOCUMENT_TYPE_LABEL: dict[DocumentType, str] = {
    DocumentType.DRIVING_LICENSE: "رخصة القيادة",
    DocumentType.NATIONAL_ID: "الهوية الشخصية",
    DocumentType.VEHICLE_REGISTRATION: "رخصة المركبة والتأمين",
    DocumentType.VEHICLE_PHOTO: "صور المركبة",
}


def label_for(doc_type: DocumentType) -> str:
    return DOCUMENT_TYPE_LABEL.get(doc_type, doc_type.value)


# ------------------------------------------------------------------ القراءة


async def list_for_driver(
    session: AsyncSession, driver_id: uuid.UUID
) -> Sequence[DriverDocument]:
    return (
        await session.scalars(
            select(DriverDocument)
            .where(DriverDocument.driver_id == driver_id)
            .order_by(DriverDocument.doc_type)
        )
    ).all()


async def get_for_driver(
    session: AsyncSession, *, driver_id: uuid.UUID, document_id: uuid.UUID
) -> DriverDocument:
    """مستندٌ **بشرط ملكيته** — لا IDOR (SPEC القسم 14).

    الشرطان في نفس الاستعلام لا في فحصٍ بعده: مستند كبتنٍ آخر يردّ 404 لا
    403، فلا يُستدل من الجواب على وجود صفٍّ لا يخص السائل.
    """
    document = await session.scalar(
        select(DriverDocument).where(
            DriverDocument.id == document_id, DriverDocument.driver_id == driver_id
        )
    )
    if document is None:
        raise NotFound("المستند غير موجود")
    return document


async def get_for_review(
    session: AsyncSession,
    *,
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    for_update: bool = False,
) -> DriverDocument:
    """نفس القراءة للوحة — و`for_update` إلزامي في كل مسارٍ يراجع."""
    stmt = select(DriverDocument).where(
        DriverDocument.id == document_id, DriverDocument.driver_id == driver_id
    )
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    document = await session.scalar(stmt)
    if document is None:
        raise NotFound("المستند غير موجود")
    return document


async def missing_required(
    session: AsyncSession, driver_id: uuid.UUID
) -> list[DocumentType]:
    """أنواعُ المستندات المطلوبة التي لا مستندَ مقبولاً لها بعد."""
    approved = set(
        await session.scalars(
            select(DriverDocument.doc_type).where(
                DriverDocument.driver_id == driver_id,
                DriverDocument.review_status == DocumentReviewStatus.APPROVED,
            )
        )
    )
    return [doc_type for doc_type in REQUIRED_DOCUMENT_TYPES if doc_type not in approved]


# ------------------------------------------------------------------- الرفع


async def upload(
    session: AsyncSession,
    *,
    driver: Driver,
    doc_type: DocumentType,
    reader: storage.AsyncReader,
) -> tuple[DriverDocument, str | None]:
    """يحفظ الملف ويكتب صفَّه، ويعيد (المستند، مسارَ المُستبدَل إن وُجد).

    الـ commit **وحذفُ المُستبدَل** مسؤولية المستدعي؛ وإن فشل شيءٌ بعد الحفظ
    يُحذف الملف الجديد هنا فلا يبقى أثرٌ لرفعٍ لم يكتمل.
    """
    stored = await storage.save(reader, folder=str(driver.id))

    try:
        # القفل يسلسل استبدالين متزامنين لنفس النوع: بغيره يقرأ الاثنان
        # «لا صفّ» فيُدخلان صفّين ويصطدمان بالفريد
        existing = await session.scalar(
            select(DriverDocument)
            .where(
                DriverDocument.driver_id == driver.id,
                DriverDocument.doc_type == doc_type,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        superseded: str | None = None
        if existing is not None:
            superseded = existing.file_path
            existing.file_path = stored.relative_path
            existing.content_type = stored.content_type
            existing.size_bytes = stored.size_bytes
            # مراجعةٌ سابقة لملفٍ لم يعد موجوداً حكمٌ على غائب
            existing.review_status = DocumentReviewStatus.PENDING
            existing.review_note = None
            existing.reviewed_by = None
            existing.reviewed_at = None
            document = existing
        else:
            document = DriverDocument(
                driver_id=driver.id,
                doc_type=doc_type,
                file_path=stored.relative_path,
                content_type=stored.content_type,
                size_bytes=stored.size_bytes,
                review_status=DocumentReviewStatus.PENDING,
            )
            session.add(document)

        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise Conflict("رفعٌ آخر لنفس المستند يجري الآن — أعد المحاولة") from exc

        return document, superseded
    except BaseException:
        await storage.delete(stored.relative_path)
        raise


# ---------------------------------------------------------------- المراجعة


async def review(
    session: AsyncSession,
    *,
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    actor: User,
    approved: bool,
    note: str | None = None,
) -> DriverDocument:
    """يعتمد مستنداً أو يرفضه — **يقرأ الصفَّ بقفلٍ ثم يفحص ثم يكتب**.

    القفل داخل الدالة لا في مستدعيها عمداً: حارسٌ يعتمد على أن يتذكّره كلُّ
    راوترٍ جديد حارسٌ سيُنسى، ولا يستطيع اختبارٌ أن يملكه — يكفي أن ينسى
    الاختبارُ نفسُه تمريرَه فيمر بلا قفلٍ ولا يُلاحظ أحد.

    الـ commit مسؤولية الراوتر، وكذلك إشعار صاحبه — والإشعار بعد الـ commit
    كما تفرض قاعدة البثّ.
    """
    document = await get_for_review(
        session, driver_id=driver_id, document_id=document_id, for_update=True
    )

    target = (
        DocumentReviewStatus.APPROVED if approved else DocumentReviewStatus.REJECTED
    )
    if document.review_status is target:
        raise Conflict(
            "اعتُمد هذا المستند بالفعل"
            if approved
            else "رُفض هذا المستند بالفعل"
        )

    document.review_status = target
    document.review_note = (note or "").strip() or None
    document.reviewed_by = actor.id
    document.reviewed_at = datetime.now(UTC)

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="driver_document",
        entity_id=document.id,
        # أسماء الحقول وحالتُها لا نصُّ الملاحظة: `details` لا تحمل قيماً
        # (القاعدة المعمارية في CLAUDE.md)، وملاحظةُ الرفض نصٌّ يكتبه بشر
        details={"review_status": target.value, "doc_type": document.doc_type.value},
    )
    await session.flush()
    return document
