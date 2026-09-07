"""بابُ الحساب — **إغلاقُه، لصاحبه أيّاً كان دورُه** (٢٠٢٦-٠٩-٠٧).

## ولمَ انتقل من `‎/drivers/me/deactivation` ولم يُضَف بجانبه

**أوجب المتجرُ مسارَ حذفٍ لكلِّ حسابٍ يُنشأ في التطبيق** — «If your app allows
users to create an account, you must also provide an option to request account
deletion» — **ولم يكن للراكب مسار**.

**وبابان يفعلان الشيءَ نفسَه هو الشكلُ الثامنُ في هذا المشروع**: كلٌّ صادقٌ
منفرداً، **ويفترقان أوّلَ تعديل** — فيُصلَح مانعٌ في أحدهما ويُنسى في أخيه،
**ويخرج راكبٌ من بابٍ لا يسأل ما يسأله بابُ الكبتن**.

**فالبابُ واحدٌ والموضوعُ الحساب**: `deactivation_requests.user_id` بدل
`driver_id` (الترحيلة `0075`)، **والموانعُ هي التي تعرف الدور** — ومن يحمل
الدورين تُجمع موانعُه كلُّها، **فحسابٌ واحدٌ يُغلق مرّةً واحدة**.

**والقرارُ لمشرفٍ لا لمفتاح**: يمسّ مالاً محجوزاً ومسؤوليةً قائمة. **وهذا
ليس التفافاً على شرط المتجر**: الشرطُ «option to **request** account deletion»
— **طلبٌ يُقدَّم**، وهو ما يفعله هذا الباب.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.currency import currency_for_country
from app.core.deps import CurrentUser, DbSession
from app.schemas.driver import (
    DeactivationRequestIn,
    DeactivationRequestOut,
    DeactivationStateOut,
)
from app.services import deactivation, settings_service

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/deactivation", response_model=DeactivationStateOut)
async def my_deactivation_state(
    user: CurrentUser, session: DbSession
) -> DeactivationStateOut:
    """حالُ طلبه وموانعُه والمحتجَزُ برقمه — سؤالٌ واحدٌ بجوابٍ واحد.

    **والمحتجَزُ يُرسل للجميع وإن كان شرطاً على الكبتن**: الحقلُ رقمٌ
    والشاشةُ تقرّر عرضَه، **وحقلٌ يظهر ويختفي بالدور يجعل مرآةً واحدةً
    شكلين** — و`check:config` يقيس المرآةَ لا من يقرؤها.
    """
    limits = await settings_service.get_or_create_wallet_settings(
        session, user.country_code
    )
    pending = await deactivation.pending_for(session, user.id)
    return DeactivationStateOut(
        request=(DeactivationRequestOut.model_validate(pending) if pending else None),
        blockers=await deactivation.blockers(session, user),
        reserve_amount=limits.withdrawal_reserve_amount,
        currency=currency_for_country(user.country_code).value,
    )


@router.post(
    "/deactivation",
    response_model=DeactivationRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def request_deactivation(
    payload: DeactivationRequestIn, user: CurrentUser, session: DbSession
) -> DeactivationRequestOut:
    """يفتح طلبَ إغلاق — يُرفض إن كان عليه ما لا يُترك خلفه (SPEC القسم 7)."""
    row = await deactivation.request(session, user=user, reason=payload.reason)
    await session.commit()
    await session.refresh(row)
    return DeactivationRequestOut.model_validate(row)


@router.delete("/deactivation", response_model=DeactivationRequestOut)
async def cancel_deactivation(
    user: CurrentUser, session: DbSession
) -> DeactivationRequestOut:
    """يعدل عن طلبه ما دام معلّقاً — والقفلُ يمنع سباقَه مع قرار المشرف."""
    row = await deactivation.cancel(session, user=user)
    await session.commit()
    await session.refresh(row)
    return DeactivationRequestOut.model_validate(row)
