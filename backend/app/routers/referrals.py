"""قسمُ الإحالة في تطبيق الكبتن (SPEC القسم 9.1، المرحلة 12-ح).

راوترٌ رقيق: يحلّ من له الحق ويستدعي `services/referrals.py`، والقواعدُ هناك.

**ولا مسارَ كتابةٍ فيه**: الرمزُ يُولَّد عند إنشاء الحساب، والإسنادُ يقع في
التسجيل، والدفعُ مهمةٌ دورية. فما يملك الكبتنُ فعلَه هنا **قراءةٌ فقط** — ولو
كان ثمّ زرٌّ يقول «اطلب مكافأتي» لصار للمال بابان.
"""

from __future__ import annotations

from app.core.deps import CurrentDriver, DbSession
from app.models.user import User
from app.schemas.referral import MyReferralsOut, ReferralStageOut
from app.services import referrals as referrals_service

from fastapi import APIRouter

router = APIRouter(prefix="/drivers/me/referrals", tags=["referrals"])


def _stage(progress: referrals_service.Progress) -> ReferralStageOut:
    row = progress.referral
    return ReferralStageOut(
        id=row.id,
        created_at=row.created_at,
        driver_approved=progress.driver_approved,
        gender_ready=progress.gender_ready,
        rides_done=progress.rides_done,
        rides_required=progress.rides_required,
        qualifies=progress.qualifies,
        rewarded=progress.rewarded,
        reward_amount=row.reward_amount,
        reward_currency=row.reward_currency,
        rewarded_at=row.rewarded_at,
    )


@router.get("", response_model=MyReferralsOut)
async def my_referrals(driver: CurrentDriver, session: DbSession) -> MyReferralsOut:
    """رمزُه ومن سجّل به وأين وصل كلٌّ منهم.

    **والرمزُ يُعرض حتى حيث المفتاح مطفأ أو المبلغُ صفر**: الإحالةُ تُسجَّل على
    كلِّ حال (`referrals.attach` لا تسأل عن المفتاح)، فمن أحال اليومَ يُحفظ
    أثرُه ليُكافأ يومَ يُحدَّد المبلغ. وما يُخفى هو **المبلغُ** لا الرمز:
    الواجهةُ تقرأ `reward_amount == 0` فلا ترسم وعداً.
    """
    # **دولةُ حسابه هي الحاكمة**: المكافأةُ تدخل محفظتَه بعملةِ بلده، والسياسةُ
    # per-country — فقراءةُ سياسةِ دولةٍ أخرى تعرض حدَّ رحلاتٍ لا يُقاس به
    user = await session.get(User, driver.user_id)
    assert user is not None  # كبتنٌ بلا حسابٍ لا يمرّ من `CurrentDriver`

    policy, progresses = await referrals_service.list_for_referrer(
        session, driver=driver, country=user.country_code
    )
    return MyReferralsOut(
        code=driver.referral_code or "",
        enabled=policy.enabled,
        reward_amount=policy.reward_amount,
        required_rides=policy.required_rides,
        total_rewarded=await referrals_service.rewarded_total(session, driver.id),
        referrals=[_stage(item) for item in progresses],
    )
