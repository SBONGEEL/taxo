"""مسارات اشتراك الكبتن (SPEC القسم 8/12.5).

شاشة «اشتراكي» في تطبيق الكبتن: الحالة وعدّاد الأيام والخطط الثلاث والتجديد
بضغطة. القنوات الفورية وحدها هنا — المحفظة والبطاقة؛ الكاش وكليك تسجّلهما
اللوحة بعد قبض المال (`admin_subscriptions`)، فلا يفتح الكبتن لنفسه اشتراكاً
بمالٍ لم يصل.

مساران للشراء لا مسار واحد: الأول يعيد صفَّ اشتراكٍ نافذاً، والثاني يعيد رابط
صفحة الدفع (أو حالاً نهائية على بطاقة محفوظة). ردّان مختلفان لعمليتين مختلفتين
— نفس تفريق `/wallet/me/topups` عن `/wallet/me/topups/card`.

الراوتر يقرّر **من** يحق له الطلب فقط؛ كل ما عداه في `services/subscriptions.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.core import rate_limit
from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep
from app.core.exceptions import RateLimited
from app.schemas.payment import CardOrderOut
from app.schemas.settings import SubscriptionPlanOut
from app.schemas.subscription import (
    MySubscriptionOut,
    SubscriptionCardPurchase,
    SubscriptionOut,
    SubscriptionPurchase,
)
from app.services import card_payments, subscriptions

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# كل نداء يفتح عملية عند مزود خارجي — سقفٌ يكفي المحاولات المعقولة (القسم 14)
CARD_PURCHASE_LIMIT = 10
CARD_PURCHASE_WINDOW_SECONDS = 300


@router.get("/plans", response_model=list[SubscriptionPlanOut])
async def list_plans(
    _driver: CurrentDriver, user: CurrentUser, session: DbSession
) -> list[SubscriptionPlanOut]:
    """الخطط المعروضة على الكبتن — المفعّلة في بلده وحدها (SPEC القسم 12.5)."""
    plans = await subscriptions.available_plans(session, user.country_code)
    return [SubscriptionPlanOut.model_validate(plan) for plan in plans]


@router.get("/me", response_model=MySubscriptionOut)
async def get_my_subscription(
    driver: CurrentDriver, user: CurrentUser, session: DbSession
) -> MySubscriptionOut:
    """حالة الاشتراك وعدّاد الأيام المتبقية (SPEC القسم 12.5).

    الخطط في نفس الردّ: شاشةٌ تقول «انتهى اشتراكك» ولا تعرض بمَ يُجدَّد شاشةٌ
    ناقصة، وطلبٌ ثانٍ لأجلها طلبٌ زائد على تطبيقٍ يفتحه الكبتن كل صباح.
    """
    current = await subscriptions.current_subscription(session, driver.id)
    until = await subscriptions.coverage_until(session, driver.id)
    plans = await subscriptions.available_plans(session, user.country_code)

    return MySubscriptionOut(
        is_active=current is not None,
        coverage_until=until,
        days_remaining=subscriptions.days_remaining(until),
        current=(
            SubscriptionOut.from_subscription(current) if current is not None else None
        ),
        plans=[SubscriptionPlanOut.model_validate(plan) for plan in plans],
    )


@router.get("/me/history", response_model=list[SubscriptionOut])
async def list_my_subscriptions(
    driver: CurrentDriver,
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[SubscriptionOut]:
    """سجل الاشتراكات — التجديد صفٌّ جديد فالتاريخ كله محفوظ (SPEC القسم 4)."""
    rows = await subscriptions.history(session, driver.id, limit=limit, offset=offset)
    return [SubscriptionOut.from_subscription(row) for row in rows]


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def purchase_subscription(
    payload: SubscriptionPurchase,
    driver: CurrentDriver,
    user: CurrentUser,
    session: DbSession,
) -> SubscriptionOut:
    """شراء أو تجديد من رصيد المحفظة — خصمٌ واشتراكٌ في معاملة واحدة."""
    subscription = await subscriptions.purchase_with_wallet(
        session,
        driver=driver,
        user=user,
        plan_id=payload.plan_id,
        idempotency_key=payload.idempotency_key,
    )
    await session.commit()
    return SubscriptionOut.from_subscription(subscription)


@router.post(
    "/card", response_model=CardOrderOut, status_code=status.HTTP_201_CREATED
)
async def purchase_subscription_with_card(
    payload: SubscriptionCardPurchase,
    driver: CurrentDriver,
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
) -> CardOrderOut:
    """شراء بالبطاقة — يفتح عملية عند المزود ولا يُنشئ اشتراكاً قبل جوابه."""
    limit = await rate_limit.hit(
        redis,
        f"subscription:card:{user.id}",
        limit=CARD_PURCHASE_LIMIT,
        window_seconds=CARD_PURCHASE_WINDOW_SECONDS,
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    plan = await subscriptions.get_plan(session, payload.plan_id, user.country_code)
    order = await card_payments.start_subscription(
        session,
        driver=driver,
        owner=user,
        plan=plan,
        save_card=payload.save_card,
        saved_card_id=payload.saved_card_id,
    )
    await session.commit()
    return CardOrderOut.model_validate(order)
