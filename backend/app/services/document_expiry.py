"""انتهاءُ صلاحية مستندات الكبتن — تنبيهٌ قبله، وتعليقٌ عنده (البند ج).

**العتباتُ ثلاثٌ ثم التعليق** (قرارُ المالك 2026-08-25): ٣٠ يوماً · ٧ · ١ ·
ثمّ **يومَ الانتهاء يُعلَّق الحساب**.

═══════════════════════════════════════════════════════════════════════════
**ما يُعلَّق به وما لا يُعلَّق** — يُقرأ قبل أن يُصدَّق:

١) **المطلوبُ وحدَه يُعلِّق.** رخصةٌ منتهيةٌ تمنع القيادة؛ ووثيقةٌ اختياريةٌ
   منتهيةٌ لا تمنع شيئاً. **والمطلوبُ لهذا الكبتن بعينه** لا جدولٌ ثابت —
   `documents.required_for` هي التي تجيب (البند ٥٢).

٢) **والفارغُ لا يُعلِّق أبداً.** `expires_on = NULL` يعني «لا تاريخَ لهذا
   النوع» لا «تاريخٌ نُسي» — **فحسابٌ لم يُملأ له حقلٌ لا يتوقّف**. وهذا
   الشرطُ هو ما يمنع أن يصير حقلٌ أُضيف اليومَ سبباً في تعليق كلِّ كبتنٍ
   قائم.

٣) **والمعتمَدُ وحدَه يُعلَّق.** من هو `pending` أصلاً لا يعمل، وتعليقُه
   يخرجه من طابور المراجعة إلى حالٍ لا يعرف كيف يخرج منها.

٤) **ولا يُرفع التعليقُ من هنا.** رفعُه بابُه رفعُ مستندٍ جديدٍ ومراجعتُه —
   وهو المسارُ المبنيُّ أصلاً (`documents.upload` يعيده `pending`، ثمّ
   `drivers.approve`). **ودورةٌ ترفع ما علّقته تُخفي أن التعليقَ وقع**، ومن
   جدّد رخصتَه يريد مراجعةً لا عودةً صامتة.
═══════════════════════════════════════════════════════════════════════════

**والتنبيهُ حدثٌ لا سجلّ**: تُميَّز المرّةُ بمفتاحٍ في Redis لا بعمودٍ على
الصفّ — كتنبيه الاشتراك والسلفة. ومفتاحُه يحمل **العتبة** لا اليومَ وحدَه،
وإلا ابتلع تنبيهُ الثلاثين تنبيهَ السبعة.

**واليومُ يومُ البلد لا يومُ الخادم**: خادمٌ على UTC يقرأ منتصفَ ليل عمّان
بعد ثلاث ساعات، فيُعلَّق كبتنٌ يوماً قبل أوانه أو بعده. والمنطقةُ من
`notification_settings` كما في `services/stats.py`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver, DriverDocument
from app.models.enums import CountryCode, DocumentType, DriverStatus
from app.models.user import User
from app.services import documents as documents_service
from app.services import drivers as drivers_service

# **العتباتُ بأيّامها** — والترتيبُ من الأبعد إلى الأقرب، فيُختار أقربُ عتبةٍ
# بلغها المستندُ اليومَ ولا تُرسل ثلاثةُ إشعاراتٍ دفعةً واحدةً لمن رفع وثيقةً
# تنتهي بعد يوم.
NOTICE_DAYS: tuple[int, ...] = (30, 7, 1)


@dataclass(frozen=True)
class ExpiringDocument:
    """مستندٌ بلغ عتبةً — ومعه ما يلزم للإشعار بلا استعلامٍ ثانٍ."""

    document_id: uuid.UUID
    driver_id: uuid.UUID
    driver_user_id: uuid.UUID
    doc_type: DocumentType
    expires_on: date
    days_left: int


@dataclass(frozen=True)
class ExpiredDocument:
    """مستندٌ **مطلوبٌ** انتهى — وصاحبُه معتمَدٌ يُعلَّق."""

    document_id: uuid.UUID
    driver_id: uuid.UUID
    driver_user_id: uuid.UUID
    doc_type: DocumentType
    expires_on: date


def _base_query():
    """الصفوفُ التي لها تاريخٌ أصلاً — **والفارغُ خارجَ كلِّ شيء**."""
    return (
        select(DriverDocument, Driver, User)
        .join(Driver, Driver.id == DriverDocument.driver_id)
        .join(User, User.id == Driver.user_id)
        .where(DriverDocument.expires_on.is_not(None))
    )


async def expiring_on(
    session: AsyncSession, *, today: date, country: CountryCode
) -> list[ExpiringDocument]:
    """ما بلغ عتبةً **بالضبط** اليوم — لا ما هو دونها.

    **بالضبط لا «أقلّ من»**: «أقلُّ من ثلاثين» يشمل السابع والأول، فيُرسل
    تنبيهُ الثلاثين كلَّ يومٍ لثلاثين يوماً. والعتبةُ لحظةٌ تُعبر مرّةً.
    """
    targets = {today + timedelta(days=d): d for d in NOTICE_DAYS}
    rows = (
        await session.execute(
            _base_query()
            .where(User.country_code == country)
            .where(DriverDocument.expires_on.in_(list(targets)))
        )
    ).all()

    found: list[ExpiringDocument] = []
    for document, driver, user in rows:
        # **المطلوبُ وحدَه يُنبَّه عليه**: تنبيهٌ عن وثيقةٍ اختياريةٍ يعلّم
        # قارئَه أن تنبيهاتِنا لا تعني توقّفاً، فيتجاهل الذي يعني.
        required = await documents_service.required_for(session, driver.id)
        if document.doc_type not in required:
            continue
        found.append(
            ExpiringDocument(
                document_id=document.id,
                driver_id=driver.id,
                driver_user_id=user.id,
                doc_type=document.doc_type,
                expires_on=document.expires_on,
                days_left=targets[document.expires_on],
            )
        )
    return found


async def expired_requiring_suspension(
    session: AsyncSession, *, today: date, country: CountryCode
) -> list[ExpiredDocument]:
    """ما انتهى **وصاحبُه معتمَدٌ ومستندُه مطلوب**.

    `expires_on <= today` لا `< today`: «تنتهي في ١٥ آذار» تعني أنها **لا
    تصلح في ١٥ آذار** — وهو ما يقرؤه من يمسك الورقة.
    """
    rows = (
        await session.execute(
            _base_query()
            .where(User.country_code == country)
            .where(DriverDocument.expires_on <= today)
            .where(Driver.status == DriverStatus.APPROVED)
        )
    ).all()

    found: list[ExpiredDocument] = []
    for document, driver, user in rows:
        required = await documents_service.required_for(session, driver.id)
        if document.doc_type not in required:
            continue
        found.append(
            ExpiredDocument(
                document_id=document.id,
                driver_id=driver.id,
                driver_user_id=user.id,
                doc_type=document.doc_type,
                expires_on=document.expires_on,
            )
        )
    return found


async def suspend_for_expiry(
    session: AsyncSession, *, item: ExpiredDocument
) -> Driver | None:
    """يعلّق الحسابَ **بقفل الصفِّ قبل قراءة الحال** — كبقية تحوّلات الحال.

    **والقفلُ ليس زينة**: مشرفٌ يعتمد الكبتنَ في اللحظة نفسِها يقرأ هذه الدورةُ
    فيها `approved` قديمةً، فتكتب `suspended` فوق اعتمادٍ وقع بعدها — أو
    العكس. وهو عينُ ما يحرسه قفلُ `drivers` في مسار الوثائق.

    ويعيد `None` إن لم يعد التعليقُ واقعاً — **فالدورةُ لا تفترض ما قرأته**.
    """
    driver = await session.get(Driver, item.driver_id)
    if driver is None:
        return None
    # **يُقفل ثمّ تُقرأ الحال** — لا العكس
    await drivers_service.lock(session, driver)
    if driver.status is not DriverStatus.APPROVED:
        return None

    label = documents_service.label_for(item.doc_type)
    await drivers_service.set_status(
        session,
        driver=driver,
        status=DriverStatus.SUSPENDED,
        # **بلا فاعل**: لم يقرّره مشرف — وصفٌّ يسمّي من لم يفعل أسوأُ من صفٍّ
        # يسمّي لا أحد (قاعدةُ `totp_reset` نفسُها).
        actor=None,
        reason=f"انتهت صلاحية {label} في {item.expires_on.isoformat()}",
    )
    return driver
