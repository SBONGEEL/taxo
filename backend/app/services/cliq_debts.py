"""سدادُ دَينِ الكبتن بكليك — **قضيبُ `cliq_subscriptions` نفسُه بغرضٍ رابع**.

## ولمَ لزم بابٌ للسداد أصلاً

**«ونصُّ المحجوب يقول: المبلغَ بالضبط، وسبيلَ السداد، وأن العملَ يعود فور
السداد»** (قرارُ المالك 2026-08-30). **وسبيلُ سدادٍ لا يوجد يجعل النصَّ كذباً**
— وهو بعينه العطبُ الذي أُصلح اليوم: جملةٌ تقول «اشحن المحفظة» وبابُ الشحن
مُلغى.

**وقِيس أنّ للكبتن مدخلاً واحداً للمال**: `ride_earning` من رحلةٍ تمرّ بالمنصّة.
**فمن يعمل كاشاً وحدَه لا يدخل محفظتَه شيءٌ أبداً** — ولو مُنع فوق السقف لَما
وجد ما يسدّد به، **ولَصار المنعُ حبساً لا حافزاً**.

## وثلاثةُ فروقٍ عن مطالبة الاشتراك، كلُّها بعللها

1. **الناقصُ يُقبل ويُنقص** — «السدادُ الجزئيُّ يُقبل» (قرارُ المالك).
   والاشتراكُ عكسُه: أقلُّ من الثمن **لا يفعّل**، لأن ثمنَه شيءٌ واحدٌ
   لا يتجزّأ. **والدَّينُ عددٌ ينقص.**
2. **ولا `plan_id`** — فقيدُ `provider_order_plan_matches_purpose` يمرّ.
3. **والمبلغُ يكتبه الكبتن** (لا تحسبه الخلفية) لأنه **يختار كم يسدّد** —
   ويُحدُّ بالقائم عليه: **لا سدادَ فوق دَينه**، فلا يُنشئ رصيداً في بيتٍ
   لا يحمل أرصدة.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import InvalidInput, InvalidStatusTransition, NotFound
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    PaymentProvider,
    ProviderOrderPurpose,
    ProviderOrderSource,
    ProviderOrderStatus,
    UserRole,
)
from app.models.provider_order import ProviderOrder
from app.models.user import User
from app.services import audit, debts
from app.services.card_payments import _new_cart_id, _paying_side
from app.services.cliq_subscriptions import require_cliq_manual_enabled
from app.services.pricing import round_money


async def start_payment(
    session: AsyncSession,
    *,
    driver: Driver,
    owner: User,
    amount: Decimal,
) -> ProviderOrder:
    """يفتح مطالبةً يدويّةً بمبلغٍ يختاره الكبتن — **لا تتجاوز دَينَه**."""
    await require_cliq_manual_enabled(session, owner.country_code)

    amount = round_money(amount)
    if amount <= 0:
        raise InvalidInput("المبلغ يجب أن يكون أكبر من صفر")

    outstanding = await debts.outstanding_of(session, driver.id)
    if outstanding <= 0:
        raise InvalidInput("لا مستحقّات عليك")
    if amount > outstanding:
        # **ولا يُقصّ صامتاً إلى الدَّين**: من كتب رقماً أكبر أخطأ في القراءة،
        # وتصحيحُه له خيرٌ من قبضِ ما لم يُقصَد
        raise InvalidInput("المبلغ أكبر من المستحقّ عليك")

    order = ProviderOrder(
        provider=PaymentProvider.CLIQ_ACQUIRER,
        source=ProviderOrderSource.MANUAL,
        purpose=ProviderOrderPurpose.DEBT,
        status=ProviderOrderStatus.CREATED,
        cart_id=_new_cart_id("d"),
        user_id=owner.id,
        country_code=owner.country_code,
        amount=amount,
        # **العملةُ من سوقه لا من ظنّ الشاشة** — بيتُها الواحد في `core`
        currency=currency_for_country(owner.country_code),
        opened_from_app=_paying_side(owner, UserRole.DRIVER.value),
    )
    session.add(order)
    await session.flush()
    return order


async def list_mine(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int = 20
) -> list[ProviderOrder]:
    rows = await session.scalars(
        select(ProviderOrder)
        .where(
            ProviderOrder.user_id == user_id,
            ProviderOrder.source == ProviderOrderSource.MANUAL,
            ProviderOrder.purpose == ProviderOrderPurpose.DEBT,
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
) -> tuple[ProviderOrder, Decimal]:
    """**تأكيدُ الوصول** — يملؤها المشرفُ بيده اليوم، والقابضُ بإشعاره غداً.

    **والمقيَّدُ ما وصل فعلاً لا ما فُتحت به المطالبة**: المشرفُ يقرأ كشفَه
    ويكتب الرقمَ الذي رآه. **وأقلُّ يُقبل ويُنقص** — بخلاف الاشتراك.

    **وما زاد عن الدَّين لا يُقيَّد ولا يُبتلع**: يُعاد المطبَّقُ رقماً ليقوله
    المشرفُ لصاحبه — **ولا بيتَ لرصيدٍ في جدول دَين**.
    """
    order = await _locked(session, order_id)
    if order.purpose is not ProviderOrderPurpose.DEBT:
        raise InvalidInput("هذه المطالبةُ ليست سدادَ دَين")
    if order.source is not ProviderOrderSource.MANUAL:
        raise InvalidInput("هذه المطالبةُ ليست يدويّةً — تأكيدُها من مزوّدها")
    if order.status is not ProviderOrderStatus.CREATED:
        raise InvalidStatusTransition()

    credited = round_money(credited)
    if credited <= 0:
        raise InvalidInput("المبلغ الواصل يجب أن يكون أكبر من صفر")

    owner = await session.get(User, order.user_id)
    driver = await session.scalar(select(Driver).where(Driver.user_id == owner.id))
    if driver is None:  # pragma: no cover - مطالبةٌ بلا كبتن
        raise NotFound("لا كبتن لهذه المطالبة")

    applied = await debts.apply_settlement(
        session, driver=driver, country=owner.country_code, amount=credited
    )
    order.status = ProviderOrderStatus.PAID
    if applied < credited:
        # **الفرقُ يُكتب حيث يُقرأ** — `failure_reason` حقلُ «ما لم يمضِ»
        order.failure_reason = (
            f"وصل {credited} وطُبّق {applied} — الزائد {credited - applied} "
            f"لا يقيَّد في جدول الدَّين"
        )

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="provider_order",
        entity_id=order.id,
        details={
            "action": "confirm_debt_payment",
            "source": ProviderOrderSource.MANUAL.value,
            "credited": str(credited),
            "applied": str(applied),
            "purpose": order.purpose.value,
        },
    )
    return order, applied


async def list_pending(session: AsyncSession, *, country=None) -> list[ProviderOrder]:
    """المعلّقةُ — **ما ينتظر عينَ مشرف**."""
    query = select(ProviderOrder).where(
        ProviderOrder.source == ProviderOrderSource.MANUAL,
        ProviderOrder.purpose == ProviderOrderPurpose.DEBT,
        ProviderOrder.status == ProviderOrderStatus.CREATED,
    )
    if country is not None:
        query = query.where(ProviderOrder.country_code == country)
    rows = await session.scalars(query.order_by(ProviderOrder.created_at.desc()))
    return list(rows)
