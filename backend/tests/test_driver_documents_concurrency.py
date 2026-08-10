"""تزامنُ مراجعة المستندات (المرحلة 9-ب).

المراجعة انتقالُ حالة، وقاعدة المشروع صريحة: «أيُّ مسارٍ يغيّر حالة صفٍّ
يقفله بـ`for_update` **قبل** أن يفحص الانتقال». والقفل يعيش داخل
`documents.review` نفسها، فهذا الملف يستدعي الخدمة لا الراوتر — كما يفعل
`test_stage8_concurrency.py` بالضبط، ولنفس السبب: اختبارٌ يمرر القفل بيده
لا يملك القفل.

**ما يملكه القفل هنا**: أن يقع القرارُ مرةً واحدة. بحذف `for_update=True`
من `documents.review` تقرأ المراجعتان `pending` نفسها فتمرّان معاً — قيدا
تدقيقٍ لوثيقةٍ واحدة، وكبتنٌ يقرأ في جرسه حكمين على رفعةٍ واحدة.

والتداخل **مُرتَّبٌ عمداً لا متروكٌ للحظ**: الأولى تكتب ولا تُثبّت، والثانية
تبدأ وهي مفتوحة. اختبارٌ يطلق طلبين على HTTP ويأمل أن يتداخلا ينجح بلا قفلٍ
كلما جدولةُ الحلقة رتّبتهما — وذاك اختبارٌ يمنح ثقةً لا يملكها.
"""

from __future__ import annotations

import asyncio
import uuid

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.exceptions import Conflict
from app.models.audit import AdminAuditLog
from app.models.driver import Driver, DriverDocument
from app.models.enums import DocumentReviewStatus
from app.models.user import User
from tests.helpers import DRIVER, PNG_BYTES, auth, register, upload_document

DEADLOCK_TIMEOUT = 20


async def _driver_row(session_factory, phone: str) -> Driver:
    async with session_factory() as session:
        return await session.scalar(
            select(Driver).join(User, Driver.user_id == User.id).where(
                User.phone == phone
            )
        )


async def _admin_user(session_factory) -> User:
    async with session_factory() as session:
        return await session.scalar(
            select(User).where(User.phone == "+962790000001")
        )


async def test_two_reviews_at_once_decide_once(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    from app.services import documents

    body = await register(client, DRIVER)
    driver = await _driver_row(session_factory, "+962792222222")
    document = await upload_document(client, auth(body))
    document_id = uuid.UUID(document["id"])
    admin = await _admin_user(session_factory)

    outcomes: list[str] = []

    async def _approve_holding_the_transaction() -> None:
        async with session_factory() as session:
            await documents.review(
                session,
                driver_id=driver.id,
                document_id=document_id,
                actor=admin,
                approved=True,
            )
            await asyncio.sleep(0.3)
            await session.commit()
            outcomes.append("first")

    async def _approve_meanwhile() -> None:
        await asyncio.sleep(0.05)
        async with session_factory() as session:
            try:
                await documents.review(
                    session,
                    driver_id=driver.id,
                    document_id=document_id,
                    actor=admin,
                    approved=True,
                )
                await session.commit()
                outcomes.append("second")
            except Conflict:
                outcomes.append("refused")

    # `wait_for` لأن الجمود يتعلّق ولا يرفع استثناءً: التوقيتُ وحده يكشفه
    await asyncio.wait_for(
        asyncio.gather(
            _approve_holding_the_transaction(), _approve_meanwhile()
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert sorted(outcomes) == ["first", "refused"]

    async with session_factory() as session:
        stored = await session.get(DriverDocument, document_id)
        assert stored.review_status is DocumentReviewStatus.APPROVED
        # الثابت الذي يملكه القفل: قرارٌ واحد ⇔ قيدُ تدقيقٍ واحد
        audits = await session.scalar(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "driver_document")
        )
        assert audits == 1


async def test_opposite_reviews_at_once_leave_a_coherent_row(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """حكمان متضادان في آنٍ واحد — والصفُّ يوافق ملاحظتَه أياً كان الفائز.

    تبديلُ الحكم مسموح (مشرفٌ يصحّح ضغطةً خاطئة)، فلا يُرفض الثاني هنا؛ ما
    يحرسه القفل أن يقع الحكمان **بالتتابع** فينتهي الصفُّ بحالةٍ وملاحظةٍ من
    مصدرٍ واحد — لا `approved` تحمل سببَ رفض.
    """
    from app.services import documents

    body = await register(client, DRIVER)
    driver = await _driver_row(session_factory, "+962792222222")
    document = await upload_document(client, auth(body))
    document_id = uuid.UUID(document["id"])
    admin = await _admin_user(session_factory)

    async def _approve_holding_the_transaction() -> None:
        async with session_factory() as session:
            await documents.review(
                session,
                driver_id=driver.id,
                document_id=document_id,
                actor=admin,
                approved=True,
            )
            await asyncio.sleep(0.3)
            await session.commit()

    async def _reject_meanwhile() -> None:
        await asyncio.sleep(0.05)
        async with session_factory() as session:
            await documents.review(
                session,
                driver_id=driver.id,
                document_id=document_id,
                actor=admin,
                approved=False,
                note="الصورة غير واضحة",
            )
            await session.commit()

    await asyncio.wait_for(
        asyncio.gather(_approve_holding_the_transaction(), _reject_meanwhile()),
        timeout=DEADLOCK_TIMEOUT,
    )

    async with session_factory() as session:
        stored = await session.get(DriverDocument, document_id)
        if stored.review_status is DocumentReviewStatus.REJECTED:
            assert stored.review_note == "الصورة غير واضحة"
        else:
            assert stored.review_status is DocumentReviewStatus.APPROVED
            assert stored.review_note is None


async def test_two_uploads_of_one_type_at_once_leave_one_row(
    client: AsyncClient, session_factory
) -> None:
    """الاستبدال تحت قفلٍ أيضاً: النوع الواحد صفٌّ واحد مهما تزامن الرفع.

    الفريد `(driver_id, doc_type)` يمنع الصفَّ الثاني على كل حال؛ ما يمنعه
    القفلُ هو أن يصير المنعُ خطأً غامضاً للرافع — فالخاسر يقرأ 409 مفهومة.
    """
    body = await register(client, DRIVER)
    headers = auth(body)

    responses = await asyncio.wait_for(
        asyncio.gather(
            client.put(
                "/drivers/me/documents/driving_license",
                files={"file": ("a.png", PNG_BYTES, "image/png")},
                headers=headers,
            ),
            client.put(
                "/drivers/me/documents/driving_license",
                files={"file": ("b.png", PNG_BYTES, "image/png")},
                headers=headers,
            ),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )
    assert {r.status_code for r in responses} <= {200, 409}
    assert 200 in {r.status_code for r in responses}

    async with session_factory() as session:
        rows = await session.scalar(
            select(func.count()).select_from(DriverDocument)
        )
        assert rows == 1
