"""شحن المحفظة بكليك آلياً عبر حساب التاجر (SPEC القسم 7/15-أ — المرحلة 8).

قبل عقد الـ acquirer: الراكب يحوّل على alias الشركة ويُدخل المرجع، ويؤكد
موظفٌ (`services/topups.py`). بعده: رمزُ استجابةٍ سريعة بالمبلغ والمرجع،
والشهادةُ من حساب التاجر لا من موظف — **والمسار اليدوي يبقى قائماً** لأن
مزوداً متوقفاً لا يجوز أن يقطع قناة شحنٍ كاملة.

**لماذا `provider_orders` لا `wallet_topup_requests`؟** لنفس سبب شحن
البطاقة في المرحلة 6-ب حرفاً بحرف: جدولُ الطلبات بيتُ ما ينتظر **إنساناً**،
وهذا ينتظر جواب مزود. والصفُّ هنا يعرف «طلبٌ فُتح ولم يُحسم» ويحمل مُعرّفاً
نرسله ويعود به — وهو ما لا يعرفه ذاك الجدول.

**الأقفال:** لا رحلة ولا دفعة في هذا المسار، فالترتيب: صفُّ الطلب ثم القفل
الاستشاري للمحفظة — نفس الترتيب العام بحلقتيه الوسطى والأخيرة. ونداءُ المزود
في `reconcile` يقع **قبل** أي قفل، كما في `card_payments.reconcile`.
"""

from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import FeatureDisabled, InvalidInput, NotFound
from app.models.enums import (
    FeatureKey,
    PaymentProvider,
    ProviderOrderPurpose,
    ProviderOrderStatus,
    WalletTransactionType,
)
from app.models.provider_order import OPEN_ORDER_STATUSES, ProviderOrder
from app.models.user import User
from app.services import settings_service, wallet
from app.services.cliq import (
    CliqChargeRequest,
    CliqChargeState,
    get_cliq_provider,
)
from app.services.pricing import round_money

logger = logging.getLogger(__name__)

_CART_RANDOM_BYTES = 9


def _new_cart_id() -> str:
    return f"q{secrets.token_hex(_CART_RANDOM_BYTES)}"


async def get_order(
    session: AsyncSession, cart_id: str, *, for_update: bool = False
) -> ProviderOrder:
    stmt = select(ProviderOrder).where(
        ProviderOrder.cart_id == cart_id,
        ProviderOrder.provider == PaymentProvider.CLIQ_ACQUIRER,
    )
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    order = await session.scalar(stmt)
    if order is None:
        raise NotFound("طلب الشحن غير موجود")
    return order


async def order_for_user(
    session: AsyncSession, cart_id: str, user: User
) -> ProviderOrder:
    """الملكية قبل القراءة — لا IDOR (SPEC القسم 14)."""
    order = await get_order(session, cart_id)
    if order.user_id != user.id:
        # 404 لا 403: وجود طلبٍ مالي ليس معلومة يستحقها غير صاحبه
        raise NotFound("طلب الشحن غير موجود")
    return order


async def start_topup(
    session: AsyncSession, *, owner: User, amount: Decimal
) -> ProviderOrder:
    """يفتح تحصيلاً عند الـ acquirer ويعيد الطلب بحاملِ رمزه.

    كما في البطاقة: لا رصيد يتغيّر هنا بحال — الأثر الوحيد قيدُ `topup` عند
    تأكيد المزود في `apply_state`.
    """
    await wallet.require_wallet_enabled(session, owner.country_code)
    if not await settings_service.is_feature_enabled(
        session, owner.country_code, FeatureKey.CLIQ_ENABLED
    ):
        raise FeatureDisabled("كليك غير مفعّل في بلدك")
    wallet.require_not_frozen(owner)
    # يفحص أن للحساب محفظة أصلاً (راكب أو كبتن لا مشرف)
    wallet.owner_type_for(owner)

    amount = round_money(amount)
    if amount <= 0:
        raise InvalidInput("مبلغ الشحن يجب أن يكون أكبر من صفر")

    provider = await get_cliq_provider(session, owner.country_code)
    order = ProviderOrder(
        provider=PaymentProvider.CLIQ_ACQUIRER,
        purpose=ProviderOrderPurpose.WALLET_TOPUP,
        status=ProviderOrderStatus.CREATED,
        cart_id=_new_cart_id(),
        user_id=owner.id,
        country_code=owner.country_code,
        amount=amount,
        currency=currency_for_country(owner.country_code),
    )
    session.add(order)
    await session.flush()

    charge = await provider.create_charge(
        CliqChargeRequest(
            reference=order.cart_id,
            amount=order.amount,
            currency=order.currency,
            description="TAXO wallet topup",
            customer_name=owner.name,
            customer_phone=owner.phone,
        )
    )
    order.provider_order_ref = charge.provider_ref
    order.qr_payload = charge.qr_payload
    order.redirect_url = charge.deep_link
    await session.flush()
    return order


async def apply_state(
    session: AsyncSession, *, cart_id: str, state: CliqChargeState
) -> ProviderOrder:
    """البابُ الوحيد الذي يتحرك فيه المال في هذه القناة.

    يُقفل الصفَّ ويرفض ما ليس `created`: استعلامان متزامنان لا يشحنان مرتين،
    وفوقهما مفتاحُ عدم التكرار في الدفتر.
    """
    order = await get_order(session, cart_id, for_update=True)

    if order.status not in OPEN_ORDER_STATUSES:
        return order
    if not state.settled:
        return order  # الحوالة لم تصل بعد — لا تخمين

    if not state.paid:
        order.status = ProviderOrderStatus.FAILED
        order.failure_reason = state.status_text[:255] or None
        await session.flush()
        return order

    # مبلغٌ مختلف عمّا فُتح به الطلب لا يُقيَّد بتخمين: لا صفَّ دفعةٍ هنا
    # تُفتح عليه واقعةُ نزاع، والشحنُ بما لم يُطلب يجعل الدفتر يقول غير ما
    # جرى. يسقط الطلب برسالته، وللإدارة أن تشحن المبلغ الواصل يدوياً (القسم 7)
    if state.amount is not None and state.amount != order.amount:
        reason = f"مبلغ المزود ({state.amount}) لا يطابق مبلغ الطلب ({order.amount})"
        logger.error("تعارض مبلغ في شحن كليك %s: %s", order.cart_id, reason)
        order.status = ProviderOrderStatus.FAILED
        order.failure_reason = reason[:255]
        await session.flush()
        return order

    owner = await session.get(User, order.user_id)
    entry = await wallet.record(
        session,
        owner=owner,
        tx_type=WalletTransactionType.TOPUP,
        amount=order.amount,
        reference=order.provider_order_ref,
        created_by=None,
        # الطلب نفسه مفتاح عدم التكرار: استعلامان لا يشحنان مرتين
        idempotency_key=f"cliq-topup:{order.id}",
    )
    order.transaction_id = entry.id
    order.status = ProviderOrderStatus.PAID
    await session.flush()
    return order


async def reconcile(session: AsyncSession, order: ProviderOrder) -> ProviderOrder:
    """يسأل المزود ثم يسوّي — يستدعيه العميل وهو ينتظر وصول حوالته.

    السؤال **قبل** القفل: طلبان متزامنان لا يحتجز أولهما الصفَّ طوال نداءٍ
    عبر الشبكة (نفس قاعدة `card_payments.reconcile`).
    """
    if order.status not in OPEN_ORDER_STATUSES or not order.provider_order_ref:
        return order

    provider = await get_cliq_provider(session, order.country_code)
    state = await provider.check_charge(order.provider_order_ref)
    return await apply_state(session, cart_id=order.cart_id, state=state)
