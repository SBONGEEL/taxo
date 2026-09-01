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

from app.core.deps import AdminUser, DbSession, StaffUser
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import CountryCode, SubscriptionStatus
from app.models.user import User
from app.schemas.subscription import AdminSubscriptionCreate, SubscriptionOut
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
    payload: AdminSubscriptionCreate, admin: AdminUser, session: DbSession
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
