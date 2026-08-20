"""ما تقرؤه الصفحةُ التعريفيةُ العامة — **قراءةٌ محضة، بلا جلسةٍ وبلا كتابة**.

**ولا مسارَ هنا يكتب حرفاً** (شرطُ المالك 2026-08-21): لا تسجيل، ولا جمعَ
بيانات، ولا أثرَ في القاعدة. وهذا الملفُّ كلُّه `GET` واحد.

**ولماذا بابٌ عامٌّ للعرض أصلاً**: الصفحةُ تعِد الكبتنَ بـ«الشهر الأول مجاناً»،
**والوعدُ يُقرأ من العرض القائم لا يُكتب نصّاً** — فعرضٌ أُطفئ أو نفد سقفُه
**يختفي سطرُه من نفسه**. وهي قاعدةُ ورقة الترحيب بعينها: **ورقةٌ تعِد بما نفد
أسوأُ من ورقةٍ صامتة**.

**وما يُنشر هنا عرضٌ عامٌّ لا عرضُ شخص**: `audience` من `all` أو `new_driver`
وحدَهما — أي ما ينطبق على **من لا حسابَ له بعد**. وعرضُ `lapsed` أو `manual`
يخصّ كبتناً بعينه، ونشرُه على صفحةٍ عامة يَعِد من لا يستحقّه (الفرعُ و من
البند ٥٤).

**ولا يُنشر سقفُه ولا ميزانيتُه**: «بقي ٣ مقاعد» رقمٌ يُستعمل ضغطاً، ونحن لا
نعرف إن كان صادقاً لحظةَ القراءة.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import DbSession
from app.models.enums import CountryCode, FeatureKey
from app.models.subscription_offer import (
    AUDIENCE_ALL,
    AUDIENCE_NEW_DRIVER,
    SubscriptionOffer,
)
from app.models.subscription import SubscriptionPlan
from app.schemas.public_site import LandingOfferOut, LandingOut
from app.services import pricing, settings_service

router = APIRouter(prefix="/public", tags=["public"])

#: الجمهورُ الذي يصحّ نشرُه لمن لا حسابَ له.
PUBLIC_AUDIENCES = (AUDIENCE_ALL, AUDIENCE_NEW_DRIVER)


@router.get("/landing", response_model=LandingOut)
async def landing(
    session: DbSession, country_code: CountryCode = CountryCode.JO
) -> LandingOut:
    """أفضلُ عرضٍ عامٍّ قائمٍ الآن — أو لا شيء."""
    if not await settings_service.is_feature_enabled(
        session, country_code, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED
    ):
        return LandingOut(offer=None)

    now = datetime.now(UTC)
    offers = (
        await session.execute(
            select(SubscriptionOffer).where(
                SubscriptionOffer.country_code == country_code,
                SubscriptionOffer.is_active.is_(True),
                SubscriptionOffer.audience.in_(PUBLIC_AUDIENCES),
                (SubscriptionOffer.starts_at.is_(None))
                | (SubscriptionOffer.starts_at <= now),
                (SubscriptionOffer.ends_at.is_(None))
                | (SubscriptionOffer.ends_at > now),
            )
        )
    ).scalars().all()
    if not offers:
        return LandingOut(offer=None)

    plans = (
        await session.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == country_code,
                SubscriptionPlan.is_active.is_(True),
            )
        )
    ).scalars().all()
    if not plans:
        return LandingOut(offer=None)

    # **أكبرُ توفيرٍ لا أوّلُ خطة** — الصفحةُ تُقرأ في ثوانٍ، والرقمُ الذي يجذب
    # هو الأكبر. وهي قاعدةُ `pickWelcomeOffer` نفسُها، مطبَّقةً على من لا
    # حسابَ له
    best: LandingOfferOut | None = None
    best_saving = Decimal("-1")
    for offer in offers:
        for plan in plans:
            if offer.plan_id is not None and offer.plan_id != plan.id:
                continue
            cut = pricing.round_money(plan.price * offer.discount_value / 100)
            if offer.max_discount is not None:
                cut = min(cut, offer.max_discount)
            after = pricing.round_money(max(Decimal("0.000"), plan.price - cut))
            saving = plan.price - after
            if saving > best_saving:
                best_saving = saving
                best = LandingOfferOut(
                    name=offer.name,
                    plan_name=plan.name,
                    price=plan.price,
                    price_after=after,
                    currency=plan.currency,
                    free=after == 0,
                )
    return LandingOut(offer=best if best_saving > 0 else None)
