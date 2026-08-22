"""صورةُ الراكب — **اختياريةٌ، بلا مراجعة، وتُحجب ببلاغ** (قرارُ المالك 2026-08-22).

**ولمَ بلا مراجعة**: الكبتنُ يبحث عن راكبه في مكانٍ مزدحم — **والانتظارُ
يُفرغ الميزةَ من غرضها**. وهي **ليست وثيقةَ هوية**: لا تفتح باباً ولا تثبت
شيئاً، **فلا تُقاس بمقياس رخصةِ قيادة**.

**والثمنُ مقبولٌ وعلاجُه مبنيّ**: قد تُنشر صورةٌ مسيئة — **فبلاغُ الكبتن
يحجبها في الحال** ويعرضها على المشرف. **والحجبُ قبل القرار**: الضررُ يقع في
الدقائق لا في الأيام، ومن رأى صورةً مسيئةً لا يُطلب منه أن ينتظر.

**ومن يراها**: كبتنُ الرحلة **بعد قبوله رحلةَ صاحبها** — **بالبابِ نفسِه
الذي يرى به الراكبُ كبتنَه**: مفتاحُه الرحلةُ لا المستخدم، فلا يستعرض أحدٌ
وجوهَ الركاب بعدّ المعرّفات.

**وشكلُ الردِّ واحدٌ كصورة الكبتن**: ٢٠٠ دائماً، `image/jpeg`، **بطولٍ ثابت**
— فلا يُستدلّ من الحالة ولا من الطول على من رفع ومن لم يرفع ومن حُجبت
صورتُه. **وهو الدرسُ نفسُه** الذي أُصلح به عطبُ الإعفاء في اليوم نفسِه.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.exceptions import Conflict, NotFound
from app.models.photo_report import UserPhotoReport
from app.models.user import User

async def set_photo(session: AsyncSession, *, user: User, reader) -> User:
    """يرفع صورةً أو يستبدلها — **بالبابِ نفسِه الذي تمرّ به المستندات**.

    **و`core/storage` وحدَه يلمس القرص**: الاسمُ يُولَّد، والنوعُ يُقرأ من
    البايتات لا من ترويسة العميل، والحجمُ يُحسب بالقراءة لا من `Content-Length`.

    **والملفُّ يُكتب قبل الصفّ، والقديمُ يُحذف بعد الـflush**: ملفٌّ يتيمٌ
    نفاية، وصفٌّ يشير إلى ملفٍ محذوفٍ عطلٌ يراه المستخدم.
    """
    previous = user.photo_path
    stored = await storage.save(reader, folder=str(user.id))
    user.photo_path = stored.relative_path
    # **ورفعُ صورةٍ جديدةٍ يرفع الحجب**: الحجبُ وقع على صورةٍ بعينها، وإبقاؤه
    # على غيرها عقوبةٌ على الشخص لا على الصورة — **والقرارُ في البلاغ يبقى**
    user.photo_hidden_at = None
    await session.flush()
    if previous:
        await storage.delete(previous)
    return user


async def clear_photo(session: AsyncSession, *, user: User) -> User:
    """يحذفها بطلب صاحبها — **ملفّاً وصفّاً**."""
    previous = user.photo_path
    user.photo_path = None
    user.photo_hidden_at = None
    await session.flush()
    if previous:
        await storage.delete(previous)
    return user


def visible_path(user: User) -> str | None:
    """ما يُعرض فعلاً — **والمحجوبةُ كالمعدومة**."""
    if user.photo_path is None or user.photo_hidden_at is not None:
        return None
    return user.photo_path


async def report(
    session: AsyncSession,
    *,
    subject: User,
    reporter_id: uuid.UUID,
    ride_id: uuid.UUID,
) -> UserPhotoReport:
    """بلاغُ كبتنٍ — **يحجب في الحال**، والقرارُ للمشرف لاحقاً.

    **ولا يُبلَّغ عمّا لا يُرى**: صورةٌ غيرُ موجودةٍ أو محجوبةٌ سلفاً ليست
    محلَّ بلاغ — و`409` أصدقُ من قبولٍ لا أثرَ له.
    """
    if subject.photo_path is None:
        raise NotFound("لا صورةَ لهذا الراكب")
    if subject.photo_hidden_at is not None:
        raise Conflict("الصورةُ محجوبةٌ سلفاً وتنتظر المشرف")

    subject.photo_hidden_at = datetime.now(UTC)
    row = UserPhotoReport(
        subject_id=subject.id, reported_by=reporter_id, ride_id=ride_id
    )
    session.add(row)
    await session.flush()
    return row


async def resolve(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    admin_id: uuid.UUID,
    remove: bool,
) -> UserPhotoReport:
    """قرارُ المشرف: حذفٌ أو إعادة — **والصفُّ يبقى بعده**.

    مُبلِّغٌ يبلّغ كذباً مراراً يُقرأ من صفوفه، ومن حُذفت صورتُه ثم رفع مثلَها
    كذلك. **فالحذفُ يمسح الملفَّ لا الأثر.**
    """
    row = await session.get(UserPhotoReport, report_id)
    if row is None:
        raise NotFound("البلاغ غير موجود")
    if row.resolved_at is not None:
        raise Conflict("البلاغ محسومٌ سلفاً")

    subject = await session.get(User, row.subject_id)
    if subject is not None:
        if remove:
            await clear_photo(session, user=subject)
        else:
            subject.photo_hidden_at = None

    row.resolution = "removed" if remove else "restored"
    row.resolved_at = datetime.now(UTC)
    row.resolved_by = admin_id
    await session.flush()
    return row


async def open_reports(session: AsyncSession) -> list[UserPhotoReport]:
    return list(
        (
            await session.scalars(
                select(UserPhotoReport)
                .where(UserPhotoReport.resolved_at.is_(None))
                .order_by(UserPhotoReport.created_at)
            )
        ).all()
    )
