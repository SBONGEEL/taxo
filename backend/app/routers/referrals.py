"""قسمُ الإحالة — **لكل حساب** (SPEC §9.1، 12-ح ثم تعميمُها).

راوترٌ رقيق: يحلّ من له الحق ويستدعي `services/referrals.py`، والقواعدُ هناك.

**والمسارُ انتقل من `/drivers/me/referrals` إلى `/me/referrals`**: صار الرمزُ
لكل حساب، ومسارٌ تحت `/drivers` يجعل تطبيقَ الراكب يقرأ من بابٍ اسمُه ليس له —
وهو بابٌ يحرسه `CurrentDriver` أصلاً فلا يفتح له.

**ولا مسارَ كتابةٍ فيه**: الرمزُ يُولَّد عند إنشاء الحساب، والإسنادُ يقع في
التسجيل، والدفعُ مهمةٌ دورية. فما يملك صاحبُ الحساب فعلَه هنا **قراءةٌ فقط** —
ولو كان ثمّ زرٌّ يقول «اطلب مكافأتي» لصار للمال بابان.
"""

from __future__ import annotations

from app.core.deps import CurrentUser, DbSession
from app.models.referral import REFERRAL_TYPE_DRIVER, REFERRAL_TYPE_RIDER
from app.schemas.referral import (
    MyReferralsOut,
    ReferralProgramOut,
    ReferralStageOut,
)
from app.services import referrals as referrals_service

from fastapi import APIRouter

router = APIRouter(prefix="/me/referrals", tags=["referrals"])


def _stage(progress: referrals_service.Progress, *, over_cap: bool) -> ReferralStageOut:
    row = progress.referral
    return ReferralStageOut(
        id=row.id,
        created_at=row.created_at,
        referral_type=progress.referral_type,
        driver_approved=progress.driver_approved,
        has_subscription=progress.has_subscription,
        female_verified=progress.female_verified,
        rides_done=progress.rides_done,
        rides_required=progress.rides_required,
        qualifies=progress.qualifies,
        rewarded=progress.rewarded,
        # **تُقال صراحةً**: إحالةٌ استحقّت ولن تُدفع لأنها فوق سقف الشهر تُعرض
        # بذلك — والصمتُ عنها يجعل الرقمَ يختفي بلا سبب يُقرأ (شرطُ المالك)
        over_monthly_cap=over_cap and progress.qualifies and not progress.rewarded,
        reward_amount=row.reward_amount,
        reward_currency=row.reward_currency,
        rewarded_at=row.rewarded_at,
    )


def _program(policy: referrals_service.Policy) -> ReferralProgramOut:
    return ReferralProgramOut(
        referral_type=policy.referral_type,
        enabled=policy.enabled,
        reward_amount=policy.reward_amount,
        required_rides=policy.required_rides,
        female_bonus_amount=policy.female_bonus_amount,
        monthly_cap=policy.monthly_cap,
    )


@router.get("", response_model=MyReferralsOut)
async def my_referrals(user: CurrentUser, session: DbSession) -> MyReferralsOut:
    """رمزُه ومن سجّل به وأين وصل كلٌّ منهم.

    **والرمزُ يُعرض حتى حيث المفتاح مطفأ أو المبلغُ صفر**: الإحالةُ تُسجَّل على
    كلِّ حال (`referrals.attach` لا تسأل عن المفتاح)، فمن أحال اليومَ يُحفظ
    أثرُه ليُكافأ يومَ يُحدَّد المبلغ. وما يُخفى هو **المبلغُ** لا الرمز.

    **والبرنامجان يُعرضان معاً** (شرطُ المالك الثاني): النصُّ في الشاشة يشرح أن
    الرمزَ يعمل مع الاثنين وأن المكافأة تختلف بحسب من يسجّل به — فمن يدعو
    سائقاً لا يُفاجأ بمبلغٍ غير الذي توقّعه.
    """
    policies, progresses, paid_this_month = (
        await referrals_service.list_for_referrer(session, user=user)
    )

    # **السقفُ يُقاس ببرنامجِ كلِّ صف**: مُحيلٌ قد يجمع النوعين، وسقفُ أحدهما
    # لا يحجب الآخر — ولو قيس بسقفٍ واحد لصار وسمُ «فوق السقف» يكذب على نصفهم
    caps = {
        referral_type: (
            policy.monthly_cap is not None and paid_this_month >= policy.monthly_cap
        )
        for referral_type, policy in policies.items()
    }

    return MyReferralsOut(
        code=user.referral_code or "",
        programs=[
            _program(policies[REFERRAL_TYPE_RIDER]),
            _program(policies[REFERRAL_TYPE_DRIVER]),
        ],
        paid_this_month=paid_this_month,
        total_rewarded=await referrals_service.rewarded_total(session, user.id),
        referrals=[
            _stage(item, over_cap=caps.get(item.referral_type, False))
            for item in progresses
        ],
    )
