"""مهامُّ الكبتن ومستواه وشاراتُه — قراءةٌ فقط (البند ٥٣، §٦).

**ولا مسارَ كتابةٍ فيه**: المهمّةَ تكتبها الإدارة، والمستوى مهمّةٌ دورية،
والشارةَ المشرفُ بيده. فما يملك الكبتنُ فعلَه هنا قراءةٌ — ولو كان ثمّ زرٌّ يقول
«حدّث مستواي» لصار للعمود كاتبٌ ثانٍ، وهو ما يُفسده.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentDriver, DbSession
from app.models.enums import FeatureKey
from app.models.mission import MAX_LEVEL, normalize_metric
from app.models.user import User
from app.schemas.mission import (
    BadgeOut,
    GrantedBadgeOut,
    MissionOut,
    MissionProgressOut,
    MyProgressOut,
)
from app.services import badges as badges_service
from app.services import missions as missions_service
from app.services import settings_service

router = APIRouter(prefix="/drivers/me", tags=["missions"])


@router.get("/progress", response_model=MyProgressOut)
async def my_progress(driver: CurrentDriver, session: DbSession) -> MyProgressOut:
    """مهامُّ الشهر وتقدّمُه ومستواه وشاراتُه.

    **ومطفأً يُجاب بـ`enabled=false` لا بـ404**: الشاشةُ تُخفى في التطبيق
    (قاعدةُ الخدمة النسائية)، ومنفذٌ يرتدّ خطأً يجعل شاشةً مخفيّةً تبدو معطوبةً
    لمن وصلها برابطٍ قديم.

    **والشاراتُ تُعرض ولو كان المفتاح مطفأً**: هي تقديرٌ مُنح لصاحبه فعلاً، ولا
    علاقةَ لها بالمستوى ولا بالتوزيع — وإخفاؤها بمفتاح غيرها يسحب من كبتنٍ
    اعترافاً نالَه.
    """
    user = await session.get(User, driver.user_id)
    assert user is not None  # كبتنٌ بلا حسابٍ لا يمرّ من `CurrentDriver`

    enabled = await settings_service.is_feature_enabled(
        session, user.country_code, FeatureKey.DRIVER_LEVELS_ENABLED
    )
    progress = await missions_service.progress_for(session, driver=driver) if enabled else []
    discounts = await missions_service.discounts_for(session, user.country_code)

    granted = [
        GrantedBadgeOut(
            badge=BadgeOut.model_validate(badge, from_attributes=True),
            granted_at=row.granted_at,
        )
        for row, badge in await badges_service.for_driver(session, driver.id)
    ]

    return MyProgressOut(
        enabled=enabled,
        level=driver.level,
        max_level=MAX_LEVEL,
        level_computed_at=driver.level_computed_at,
        # **الأثرُ يُنشر بالأمتار ليكون النصُّ مقيساً لا موعوداً**: «يقرّبك ٥٠م»
        # جملةٌ تُقاس، و«أولويةٌ في الطلبات» وعدٌ يعدّه صاحبُه ولا يجده
        level_effect_meters=discounts.get(driver.level, 0),
        missions_done=sum(1 for item in progress if item.done),
        missions_total=len(progress),
        missions=[
            MissionProgressOut(
                mission=MissionOut.model_validate(item.mission, from_attributes=True),
                # **الهدفُ والقيمةُ بمقياسٍ واحد** — وإلا قُرئ «٢ من ٣٫٠٠٠»
                value=normalize_metric(item.mission.metric, item.value),
                target=normalize_metric(item.mission.metric, item.target),
                done=item.done,
            )
            for item in progress
        ],
        badges=granted,
    )
