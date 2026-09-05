"""شاشةُ «الموقع» في اللوحة — **البند ٤٩ (§52)**.

**و`settings.write`**: ما يُعرض على `taxo.tajora.ly` **إعدادُ منصّةٍ لا إدارةُ
أسطول** — وهو نفسُ سببِ وضع الإصدارات والسياسات هناك.

**وبابُ كتابةٍ واحدٌ لكلِّ الحقول** (`PATCH`): حقولُ الصفحة تُقرأ معاً وتُكتب
معاً، **وبابٌ لكلِّ مجموعةٍ يجعل «ما الذي تغيّر؟» سؤالاً يُجمع جوابُه من ثلاثة
سجلّات**. والتدقيقُ يحمل **القيمةَ قبل وبعد** لكلِّ حقلٍ تغيّر فعلاً.

**ولا يُذكر ما لم يتغيّر**: `apply_changes` يقارن قبل أن يكتب — وحقلٌ أُرسل
بقيمته نفسِها ليس تعديلاً، **وذكرُه يجعل السجلَّ يقول إن شيئاً وقع ولم يقع**.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.enums import AuditAction
from app.schemas.site import SiteAdminOut, SiteUpdateIn
from app.services import audit, site as site_service

router = APIRouter(prefix="/admin/site", tags=["admin"])


@router.get("", response_model=SiteAdminOut)
async def read_site(_staff: StaffUser, session: DbSession) -> SiteAdminOut:
    """كلُّ حقول الصفحة كما هي الآن — **ومعها ما يُقرأ من مصدره**.

    **ويُنشئ الصفَّ إن لم يوجد**: هذا بابُ الشاشة التي تُحرّره، **وشاشةُ تحريرٍ
    بلا صفٍّ تعرض فراغاً ثمّ يسقط أوّلُ حفظ**. والبابُ العامُّ لا يُنشئ شيئاً —
    وهما بابان بشرطين مختلفين بقصد.
    """
    row = await site_service.get_or_create(session)
    await session.commit()
    await session.refresh(row)
    public = await site_service.public_payload(session)
    return SiteAdminOut(
        **{field: getattr(row, field) for field in site_service.PUBLIC_FIELDS},
        commission_percent=public["commission_percent"],
        updated_at=row.updated_at,
    )


@router.patch("", response_model=SiteAdminOut)
async def update_site(
    payload: SiteUpdateIn, actor: SettingsWriter, session: DbSession
) -> SiteAdminOut:
    """يحفظ ما أُرسل — **وما لم يُرسَل لا يُمسّ**.

    `exclude_unset` يفرّق **«لم يُرسَل»** عن **«أُرسل فارغاً»**: الثاني قصدٌ
    (إفراغُ رابطٍ يُطفئ أيقونتَه)، والأولُ سكوت. **ونموذجٌ يخلطهما يمحو حقلاً
    لم يقصده أحد** كلَّما حفظت الشاشةُ قسماً واحداً.
    """
    row = await site_service.get_or_create(session)
    changes = audit.apply_changes(row, payload.model_dump(exclude_unset=True))
    if changes:
        await audit.record(
            session,
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type="site_settings",
            entity_id=row.id,
            changes=changes,
        )
    await session.commit()
    await session.refresh(row)
    public = await site_service.public_payload(session)
    return SiteAdminOut(
        **{field: getattr(row, field) for field in site_service.PUBLIC_FIELDS},
        commission_percent=public["commission_percent"],
        updated_at=row.updated_at,
    )
