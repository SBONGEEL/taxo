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

from app.core.deps import FinanceManager, DbSession, OwnerUser, RedisDep, StaffUser
from app.core.exceptions import NotFound, PermissionDenied
from app.models.driver import Driver
from app.models.enums import CountryCode, SubscriptionStatus, UserRole
from app.models.subscription import DriverSubscription
from app.models.user import User
from app.schemas.subscription import (
    AdminSubscriptionCreate,
    AdminSubscriptionPreviewIn,
    AdminSubscriptionPreviewOut,
    AmbassadorRevokeOut,
    CancellationLineOut,
    GiftRowOut,
    CancellationPlanOut,
    SubscriptionCancelIn,
    SubscriptionOut,
)
from app.services import notifications, subscriptions

router = APIRouter(prefix="/admin/subscriptions", tags=["admin"])


@router.get("", response_model=list[SubscriptionOut])
async def list_subscriptions(
    _staff: StaffUser,
    session: DbSession,
    subscription_status: SubscriptionStatus | None = None,
    driver_id: uuid.UUID | None = None,
    country_code: CountryCode | None = None,
    q: str | None = Query(default=None, max_length=120, description="اسمُ الكابتن أو رقمُه"),
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


async def _driver_and_user(session, driver_id: uuid.UUID) -> tuple[Driver, User]:
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFound("ملف الكابتن غير موجود")
    user = await session.scalar(select(User).where(User.id == driver.user_id))
    return driver, user


def _require_owner_for_permanent(permanent: bool, admin: User) -> None:
    """**منحُ «سفير TAXO» ونزعُه للمالك وحدَه** (SPEC §١١١-د/٤)."""
    if permanent and not admin.has_role(UserRole.OWNER):
        raise PermissionDenied("منحُ الاشتراك الدائم ونزعُه للمالك وحدَه")


@router.post("/preview", response_model=AdminSubscriptionPreviewOut)
async def preview_subscription(
    payload: AdminSubscriptionPreviewIn, admin: FinanceManager, session: DbSession
) -> AdminSubscriptionPreviewOut:
    """**ورقةُ التأكيد قبل «تسجيل اشتراك»** — من متى إلى متى، والمقترَحُ تلميحاً. قراءةٌ بلا أثر (SPEC §١١١-د/٤)."""
    _require_owner_for_permanent(payload.permanent, admin)
    driver, user = await _driver_and_user(session, payload.driver_id)
    preview = await subscriptions.preview_manual(
        session,
        driver=driver,
        user=user,
        plan_id=payload.plan_id,
        days=payload.days,
        permanent=payload.permanent,
    )
    return AdminSubscriptionPreviewOut(
        starts_at=preview.starts_at,
        expires_at=preview.expires_at,
        suggested_amount=preview.suggested_amount,
        currency=preview.currency,
        permanent_exists=preview.permanent_exists,
    )


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def record_subscription(
    payload: AdminSubscriptionCreate, admin: FinanceManager, session: DbSession, redis: RedisDep
) -> SubscriptionOut:
    """يسجّل اشتراكاً قبضته الإدارة كاشاً أو كليكاً — بعد وصول المال لا قبله.

    **ومعه «عدد أيام» و«سفير TAXO»** (SPEC §١١١-د/٤): الدائمُ للمالك وحدَه، والكبتنُ يُشعَر بعد الـ commit.
    """
    _require_owner_for_permanent(payload.permanent, admin)
    driver, user = await _driver_and_user(session, payload.driver_id)

    subscription = await subscriptions.record_manual(
        session,
        driver=driver,
        user=user,
        plan_id=payload.plan_id,
        method=payload.method,
        amount_paid=payload.amount_paid,
        reference=payload.reference,
        actor=admin,
        days=payload.days,
        permanent=payload.permanent,
    )
    await session.commit()
    if payload.permanent or payload.days is not None:
        await notifications.publish_subscription_gift(
            session,
            redis,
            driver_user_id=user.id,
            kind="permanent" if payload.permanent else "days",
            days=payload.days,
        )
    return SubscriptionOut.from_subscription(subscription)


# ═══════════════════════════ «السفراء والمميّزون» (SPEC §١١١-د/٤)


@router.get("/gifts", response_model=list[GiftRowOut])
async def list_gift_subscriptions(
    _admin: FinanceManager,
    session: DbSession,
    country_code: CountryCode | None = None,
    q: str | None = Query(default=None, max_length=120, description="اسمُ الكابتن أو رقمُه"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[GiftRowOut]:
    """صفحةُ «السفراء والمميّزون»: كلُّ دائمٍ ساري وكلُّ «عدد أيام» لم ينقضِ، ببحثٍ بالاسم والهاتف."""
    rows = await subscriptions.list_gifts(
        session, country_code=country_code, q=q, limit=limit, offset=offset
    )
    return [
        GiftRowOut(
            subscription_id=row.subscription.id,
            driver_id=row.subscription.driver_id,
            name=row.name,
            phone=row.phone,
            country_code=row.country_code,
            is_permanent=bool(row.subscription.is_permanent),
            custom_days=row.subscription.custom_days,
            plan_name=row.subscription.plan.name,
            starts_at=row.subscription.starts_at,
            expires_at=row.subscription.expires_at,
            amount_paid=row.subscription.amount_paid,
            currency=row.subscription.plan.currency,
            payment_method=row.subscription.payment_method,
            reference=row.subscription.reference,
            created_at=row.subscription.created_at,
            revoke_refund=row.revoke_refund,
        )
        for row in rows
    ]


@router.post("/ambassadors/{driver_id}/revoke", response_model=AmbassadorRevokeOut)
async def revoke_ambassador(
    driver_id: uuid.UUID,
    payload: SubscriptionCancelIn,
    owner: OwnerUser,
    session: DbSession,
    redis: RedisDep,
) -> AmbassadorRevokeOut:
    """**نزعُ «سفير TAXO»** — بسببٍ إلزاميٍّ وتأكيد، للمالك وحدَه، ويُلغى الصفُّ الدائمُ وحدَه بمسار الإلغاء (لا حذفَ ولا تعديلَ تاريخ)."""
    row, refund = await subscriptions.revoke_permanent(
        session, driver_id=driver_id, admin=owner, reason=payload.reason.strip()
    )
    currency = row.plan.currency.value if row.plan else ""
    user_id = (await session.get(Driver, driver_id)).user_id
    await session.commit()
    await notifications.publish_subscription_gift(
        session, redis, driver_user_id=user_id, kind="revoked"
    )
    return AmbassadorRevokeOut(subscription_id=row.id, refund=refund, currency=currency)


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
