"""دفعُ اشتراك الكبتن بكليك — **تحصيلٌ يدويٌّ على قضيبٍ آليّ** (قرارُ المالك
2026-08-29).

## البيتُ قائمٌ ولم يُبنَ ثالث

**`provider_orders` هو «بيتٌ واحدٌ بغرضٍ معلَن»** الذي أراده المالك: غرضُه
مُصرَّحٌ (`purpose`)، **والتسويةُ تُوجَّه به** في `card_payments.apply_state` —
شحنُ محفظةٍ يقيّد في الدفتر، **واشتراكٌ يكتب صفَّه ولا يمسّ الدفتر أصلاً**.
وبنصِّ `_activate_subscription`: «لا قيد في الدفتر: مال الكبتن خرج من بطاقته
لا من محفظته».

**ولذلك لم يمرّ هذا المسارُ بالمحفظة**: مالُ الاشتراك لو مرّ بها لَحمل رصيدُه
لحظةً مالاً ليس أجراً **فصار قابلاً للسحب** — خلطٌ في الحساب لا في الشاشة.

## و`provider` يبقى `cliq_acquirer` والمصدرُ يفرق

**القضيبُ قضيبُ كليك، والمختلفُ مَن يحصّل.** فيومَ يصل العقدُ **يتبدّل
`source` من `manual` إلى `acquirer` ولا يُعاد بناء**: نفسُ الصفّ، ونفسُ
الغرض، ونفسُ خطوة «تأكيد الدفع» التي يقرأها الاشتراك.

**ولم يُبنَ للقابض شيءٌ هنا**: أسماءُ حقوله وصيغةُ إشعاره تأتي من عقده لا من
ظنّنا.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, InvalidStatusTransition, NotFound
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    PaymentMethod,
    PaymentProvider,
    ProviderOrderPurpose,
    ProviderOrderSource,
    ProviderOrderStatus,
    UserRole,
)
from app.models.provider_order import ProviderOrder
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.services import audit, offers, settings_service
from app.services import subscriptions as subscriptions_service
from app.services.card_payments import _new_cart_id, _paying_side


async def require_cliq_manual_enabled(session: AsyncSession, country) -> str:
    """**لا قناةَ بلا حسابٍ يستقبل** — والسوقُ بلا alias تُخفى عنه القناة."""
    from app.services.topups import require_cliq_alias

    return await require_cliq_alias(session, country)


async def start_subscription(
    session: AsyncSession,
    *,
    driver: Driver,
    owner: User,
    plan: SubscriptionPlan,
) -> ProviderOrder:
    """يفتح مطالبةً يدويّةً بسعر العرض — **ولا اشتراكَ قبل تأكيد الدفع**.

    **والمبلغُ يُشتقّ من الخطة بعد العرض** (§14): لا يكتبه الكبتنُ ولا
    يُخمَّن — **نفسُ حساب مسار البطاقة حرفاً**، فلا موضعان يحسبان ثمناً واحداً.
    """
    await require_cliq_manual_enabled(session, owner.country_code)
    subscriptions_service.require_purchasable(driver)

    offer = await offers.resolve(session, driver=driver, plan=plan)
    payable = plan.price - (offer.amount if offer is not None else Decimal("0"))

    order = ProviderOrder(
        # **القضيبُ كليك والمصدرُ يدويّ** — ويومَ يصل العقدُ يتبدّل المصدرُ وحدَه
        provider=PaymentProvider.CLIQ_ACQUIRER,
        source=ProviderOrderSource.MANUAL,
        purpose=ProviderOrderPurpose.SUBSCRIPTION,
        status=ProviderOrderStatus.CREATED,
        cart_id=_new_cart_id("m"),
        user_id=owner.id,
        country_code=owner.country_code,
        amount=payable,
        currency=plan.currency,
        plan_id=plan.id,
        opened_from_app=_paying_side(owner, UserRole.DRIVER.value),
    )
    session.add(order)
    await session.flush()
    return order


async def list_mine(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int = 20
) -> list[ProviderOrder]:
    """مطالباتُ هذا الكبتن اليدوية — ليقرأ حالَها بنفسه."""
    rows = await session.scalars(
        select(ProviderOrder)
        .where(
            ProviderOrder.user_id == user_id,
            ProviderOrder.source == ProviderOrderSource.MANUAL,
            ProviderOrder.purpose == ProviderOrderPurpose.SUBSCRIPTION,
        )
        .order_by(ProviderOrder.created_at.desc())
        .limit(limit)
    )
    return list(rows)


async def _locked(session: AsyncSession, order_id: uuid.UUID) -> ProviderOrder:
    order = await session.scalar(
        select(ProviderOrder)
        .where(ProviderOrder.id == order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise NotFound("المطالبة غير موجودة")
    return order


async def confirm_payment(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    actor: User,
    credited: Decimal,
) -> tuple[ProviderOrder, bool]:
    """**تأكيدُ الدفع** — الخطوةُ الواحدةُ التي يقرأها الاشتراك.

    يملؤها المشرفُ اليوم بيده، ويملؤها القابضُ غداً بإشعاره — **وما بعدها لا
    يعرف مَن ملأها**.

    ## ولمَ شرطُ المبلغ هنا ولم يلزم قبله

    **المزوّدُ كان يحكم بالمبلغ**: مسارُ البطاقة يفتح الطلبَ بالمبلغ المخصوم،
    **وما يعود من تِلر هو ما خُصم فعلاً** — فلا فجوةَ بين ما فُتح وما دُفع،
    ولذلك `activate_paid_order` **لا يقارن بالسعر أصلاً** (قِيس 2026-08-29).

    **فلمّا صار المصدرُ بشرياً لزم شرطٌ لم يلزم قبله**: المشرفُ يكتب رقماً
    بيده، **ورقمٌ ناقصٌ يفعّل اشتراكاً بأقلَّ من ثمنه**.

    **فالقاعدة**: `credited < سعر العرض` ⇒ **لا تفعيل**، والمطالبةُ تبقى
    معلّقةً بملاحظةٍ تقول الفرق — **والمشرفُ يرفض أو ينتظر التكملة**. ومساوٍ أو
    أكثر ⇒ يُفعَّل.

    **ويُعاد الزوج**: الصفُّ، وهل فُعِّل — فالشاشةُ تقول ما جرى ولا تخمّنه.
    """
    order = await _locked(session, order_id)
    if order.source is not ProviderOrderSource.MANUAL:
        raise InvalidInput("هذه المطالبةُ ليست يدويّةً — تأكيدُها من مزوّدها")
    if order.status is not ProviderOrderStatus.CREATED:
        raise InvalidStatusTransition()

    short = credited < order.amount
    if short:
        # **لا تفعيلَ بأقلَّ من الثمن** — والصفُّ يبقى معلّقاً بفرقه مكتوباً،
        # فمن يقرأه بعد ساعةٍ يعرف كم ينقص ولا يعيد الحساب
        # **`failure_reason` هو حقلُ «لماذا لم يمضِ» في هذا الجدول** — ولا
        # يُضاف عمودٌ جديدٌ لما له بيت
        order.failure_reason = (
            f"وصل {credited} من {order.amount} — ينقص "
            f"{order.amount - credited} {order.currency.value}"
        )
    else:
        order.status = ProviderOrderStatus.PAID
        owner = await session.get(User, order.user_id)
        await subscriptions_service.activate_paid_order(
            session,
            driver_user=owner,
            plan_id=order.plan_id,
            # **المقيَّدُ سعرُ العرض لا ما زاد**: من حوّل أكثرَ لا يُكتب له
            # اشتراكٌ بأغلى، والفرقُ يُردّ من مسار التسوية لا من هنا
            amount=order.amount,
            reference=order.cart_id,
            idempotency_key=f"cliq-manual-subscription:{order.id}",
            method=PaymentMethod.CLIQ,
        )

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="provider_order",
        entity_id=order.id,
        details={
            "action": "confirm_payment",
            "source": ProviderOrderSource.MANUAL.value,
            "credited": str(credited),
            "due": str(order.amount),
            "activated": not short,
            "purpose": order.purpose.value,
        },
    )
    return order, not short


async def review_window(session: AsyncSession, country) -> tuple[int, int]:
    """**العددان من اللوحة لا من الشيفرة** — والجملةُ تُبنى بهما."""
    setting = await settings_service.get_payment_settings(session, country)
    if setting is None:
        return 3, 5
    return setting.cliq_review_min_minutes, setting.cliq_review_max_minutes


async def list_pending(session: AsyncSession, *, country=None) -> list[ProviderOrder]:
    """المعلّقةُ من المطالبات اليدوية — **ما ينتظر عينَ مشرف**."""
    query = select(ProviderOrder).where(
        ProviderOrder.source == ProviderOrderSource.MANUAL,
        ProviderOrder.status == ProviderOrderStatus.CREATED,
    )
    if country is not None:
        query = query.where(ProviderOrder.country_code == country)
    rows = await session.scalars(query.order_by(ProviderOrder.created_at.desc()))
    return list(rows)
