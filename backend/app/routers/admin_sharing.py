"""إعداداتُ مشاركة الرحلة في اللوحة — `admin` حصراً (المرحلة 12-ي، §5.12).

**ولا `StaffUser`**: نسبةُ الخصم مالٌ تتحمّله الشركة، كمبلغ حافز الإحالة وسقفِ
الكوبون بالضبط (القسم 13/8). وأرقامُ المطابقة الثلاثةُ معها في الشاشة نفسِها
لأنها **معايرةُ الميزة الواحدة**، وفصلُها في شاشتين يجعل من يضبط النسبةَ لا يرى
ما يجعلها تقع أصلاً.

**ولا جدولَ مجموعاتٍ هنا ولا شاشةَ «فُكَّ هذه المجموعة»**: المجموعةُ توزيعٌ لا
كيانٌ يُدار (قرارُ المالك الأول)، وكلُّ صفِّ رحلةٍ يُقرأ في سجلِّ الرحلات بمفرده
كما يُحاسَب بمفرده. وزرٌّ يفكّها من اللوحة بابٌ ثالثٌ لتغيير حالة رحلتين معاً —
وهو ما رفضته `Rides.tsx` أصلاً بحجّةٍ لا تخصّ المشاركة.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import SettingsWriter, DbSession, StaffUser
from app.models.enums import AuditAction, CountryCode
from app.schemas.sharing import RideSharingSettingsIn, RideSharingSettingsOut
from app.services import audit, sharing as sharing_service

router = APIRouter(prefix="/admin/sharing", tags=["admin"])


def _out(country: CountryCode, row) -> RideSharingSettingsOut:
    return RideSharingSettingsOut(
        country_code=country,
        discount_percent=row.discount_percent,
        corridor_km=row.corridor_km,
        max_detour_minutes=row.max_detour_minutes,
        partner_wait_seconds=row.partner_wait_seconds,
    )


@router.get("/settings", response_model=RideSharingSettingsOut)
async def get_settings(
    _staff: StaffUser, session: DbSession, country_code: CountryCode
) -> RideSharingSettingsOut:
    """القراءةُ لكل موظف — والكتابةُ للمشرف وحدَه."""
    row = await sharing_service.ensure_settings(session, country_code)
    await session.commit()
    return _out(country_code, row)


@router.put("/settings", response_model=RideSharingSettingsOut)
async def update_settings(
    payload: RideSharingSettingsIn,
    admin: SettingsWriter,
    session: DbSession,
    country_code: CountryCode,
) -> RideSharingSettingsOut:
    """الأربعة. **ومعايرةُ النسبة مقيَّدةٌ بشرطٍ مكتوب في المواصفة**: ما يقبضه
    الكبتن من رحلتين أعلى بوضوحٍ مما يقبضه من منفردة — وإلا رفض المشاركةَ وهو
    محقّ. والشرطُ لا يُفرض هنا لأنه يقارن أرقاماً في جدولٍ آخر (التسعيرة
    والعمولة) ويتغيّر بتغيّرهما؛ فيبقى قراراً يُقاس لا حدّاً يُرفض.
    """
    row = await sharing_service.update_settings(
        session,
        country=country_code,
        discount_percent=payload.discount_percent,
        corridor_km=payload.corridor_km,
        max_detour_minutes=payload.max_detour_minutes,
        partner_wait_seconds=payload.partner_wait_seconds,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="ride_sharing_settings",
        entity_id=row.id,
        # أسماءُ ما تغيّر لا قيمُه (`services/audit.py`)
        details={
            "country": country_code.value,
            "fields": [
                name
                for name, value in (
                    ("discount_percent", payload.discount_percent),
                    ("corridor_km", payload.corridor_km),
                    ("max_detour_minutes", payload.max_detour_minutes),
                    ("partner_wait_seconds", payload.partner_wait_seconds),
                )
                if value is not None
            ],
        },
    )
    await session.commit()
    return _out(country_code, row)
