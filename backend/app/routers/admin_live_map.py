"""الخريطة الحيّة (SPEC القسم 13/1).

**`AdminUser` لا `StaffUser`** — وهو الفرق الوحيد عن بقية شاشات القراءة في
اللوحة. «نظرة عامة» أرقامٌ مجمّعة يقرأها الدعم لأنه يعالج ما تشير إليه؛ وهذه
أسماءُ أشخاصٍ وأرقامُ هواتفهم ومواقعُهم الآنية، ومعالجةُ نزاعٍ لا تحتاج شيئاً
منها. ولو فُتحت للدعم لصارت أوسعَ صلاحيةٍ في النظام يملكها أقلُّ دورٍ فيه.

وقيدُ التدقيق يُكتب هنا **قبل** القراءة لا بعدها، ومخنوقاً بنافذةٍ في
`live_map.record_access` كي لا تبتلع جلسةُ مراقبةٍ واحدة سجلَّ القرارات.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import AdminUser, DbSession, RedisDep
from app.models.enums import CountryCode
from app.schemas.live_map import LiveDriverOut, LiveMapOut, PendingRideOut
from app.services import live_map as live_map_service

router = APIRouter(prefix="/admin/live", tags=["admin"])


@router.get("/map", response_model=LiveMapOut)
async def live_map(
    admin: AdminUser,
    session: DbSession,
    redis: RedisDep,
    country_code: CountryCode,
) -> LiveMapOut:
    """السائقون الحاضرون بهويّاتهم، والطلبات التي لم يقبلها أحد بعد."""
    await live_map_service.record_access(
        session, redis, admin=admin, country=country_code
    )
    drivers = await live_map_service.drivers_now(redis, session, country=country_code)
    pending = await live_map_service.pending_rides(session, country=country_code)
    return LiveMapOut(
        drivers=[LiveDriverOut.model_validate(row) for row in drivers],
        pending_rides=[PendingRideOut.model_validate(row) for row in pending],
    )
