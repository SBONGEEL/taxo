"""اشتراكات الكباتن من اللوحة (SPEC القسم 8/13.5).

بابان: تسجيل اشتراكٍ قُبض كاشاً أو كليكاً — و`admin` وحده يفعله لأنه إثباتُ
مالٍ وصل — وتقارير الاشتراكات التي يقرأها `support` كذلك.

القناتان الفوريتان (المحفظة والبطاقة) ليستا هنا: يفتحهما الكبتن من تطبيقه
ويشهد عليهما الدفترُ أو المزود، فلا شيء ينتظر إنساناً فيهما.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.core.deps import FinanceManager, DbSession, StaffUser
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import CountryCode, SubscriptionStatus
from app.models.subscription import DriverSubscription
from app.models.user import User
from app.schemas.subscription import (
    AdminSubscriptionCreate,
    CancellationLineOut,
    CancellationPlanOut,
    SubscriptionCancelIn,
    SubscriptionOut,
)
from app.services import subscriptions

router = APIRouter(prefix="/admin/subscriptions", tags=["admin"])


@router.get("", response_model=list[SubscriptionOut])
async def list_subscriptions(
    _staff: StaffUser,
    session: DbSession,
    subscription_status: SubscriptionStatus | None = None,
    driver_id: uuid.UUID | None = None,
    country_code: CountryCode | None = None,
    q: str | None = Query(default=None, max_length=120, description="اسمُ الكبتن أو رقمُه"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SubscriptionOut]:
    """تقارير الاشتراكات (SPEC القسم 13.5)."""
    rows = await subscriptions.list_all(
        session,
        status=subscription_status,
        driver_id=driver_id,
        country_code=country_code,
        limit=limit,
        offset=offset,
        q=q,
    )
    return [SubscriptionOut.from_subscription(row) for row in rows]


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def record_subscription(
    payload: AdminSubscriptionCreate, admin: FinanceManager, session: DbSession
) -> SubscriptionOut:
    """يسجّل اشتراكاً قبضته الإدارة كاشاً أو كليكاً — بعد وصول المال لا قبله."""
    driver = await session.get(Driver, payload.driver_id)
    if driver is None:
        raise NotFound("ملف الكبتن غير موجود")
    user = await session.scalar(select(User).where(User.id == driver.user_id))

    subscription = await subscriptions.record_manual(
        session,
        driver=driver,
        user=user,
        plan_id=payload.plan_id,
        method=payload.method,
        amount_paid=payload.amount_paid,
        reference=payload.reference,
        actor=admin,
    )
    await session.commit()
    return SubscriptionOut.from_subscription(subscription)


def _plan_out(plan: subscriptions.CancellationPlan) -> CancellationPlanOut:
    """بانٍ واحدٌ للمعاينة والفعل — **فلا يفترق ما يُعرض عمّا يقع**."""
    return CancellationPlanOut(
        cancelled_count=len(plan.lines),
        total_refund=plan.total_refund,
        currency=plan.currency,
        lines=[
            CancellationLineOut(
                subscription_id=line.subscription_id,
                plan_name=line.plan_name,
                starts_at=line.starts_at,
                expires_at=line.expires_at,
                amount_paid=line.amount_paid,
                refund=line.refund,
                started=line.started,
            )
            for line in plan.lines
        ],
    )


@router.get(
    "/{subscription_id}/cancellation-preview", response_model=CancellationPlanOut
)
async def preview_cancellation(
    subscription_id: uuid.UUID, _admin: FinanceManager, session: DbSession
) -> CancellationPlanOut:
    """**ما سيقع قبل أن يقع** — زرُّه ورقةُ التأكيد في اللوحة (شرطُ المالك).

    «اعرض عدد الاشتراكات التي ستُلغى وقيمة الردّ الكلّية **قبل** الضغط لا بعده».

    **و`admin` لا `staff`**: الرقمُ المعروضُ هنا يقود إلى قرارٍ ماليّ، ومن لا
    يملك الفعلَ لا يحتاج معاينتَه.

    **ولا أثرَ له**: قراءةٌ محضة — لا قفلَ ولا كتابة.
    """
    row = await session.get(DriverSubscription, subscription_id)
    if row is None:
        raise NotFound("الاشتراك غير موجود")
    return _plan_out(await subscriptions.plan_cancellation(session, row.driver_id))


@router.post("/{subscription_id}/cancel", response_model=CancellationPlanOut)
async def cancel_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionCancelIn,
    admin: FinanceManager,
    session: DbSession,
) -> CancellationPlanOut:
    """يُلغي تغطيةَ صاحب هذا الاشتراك كلَّها ويردّ ما لم يُستعمل (§38).

    **ويُلغى كلُّ ما لم ينقضِ لا الصفُّ المضغوط وحدَه** (قرارُ المالك): التجديدُ
    المبكر يكدّس صفّاً يبدأ بعد الحالي، **وزرٌّ يُبقي اشتراكاً قادماً بعد
    الإلغاء يكذب**.

    **و`admin` وحدَه**: مالٌ يخرج من حساب المنصة إلى محفظة كبتن — وهو من صنف
    «قرارٌ ماليّ لا إجراءُ دعم» (القسم 13/8).
    """
    row = await session.get(DriverSubscription, subscription_id)
    if row is None:
        raise NotFound("الاشتراك غير موجود")
    plan = await subscriptions.cancel_for_driver(
        session, driver_id=row.driver_id, admin=admin, reason=payload.reason.strip()
    )
    await session.commit()
    return _plan_out(plan)
