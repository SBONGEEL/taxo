"""الدفع بالبطاقة عبر مزود خارجي (SPEC القسم 6.4/7/8).

ثلاثة مسارات تنتهي كلها إلى بابٍ واحد:

- **صفحة دفع مستضافة** لأجرة رحلة أو شحن محفظة أو اشتراك كبتن (المرحلة 7) →
  يعود الدافع → تُسوّى.
- **الدفع بضغطة** على بطاقة محفوظة → يُحسم في نداء واحد → تُسوّى.
- **إشعار المزود (webhook)** يصل موقّعاً، ربما قبل عودة المتصفح أو مرتين.

والباب الواحد هو `apply_state`: **لا يتحرك الدفتر إلا فيه**، ولا يقرأ حالته إلا
من جواب المزود للخلفية مباشرة (`check_order`) — لا من حمولة الإشعار ولا من
العميل. فحمولةٌ موقَّعة تقول «انظر في هذا الطلب»، لا «قيِّد هذا المبلغ».

**عدم التكرار** (SPEC القسم 14) بثلاث طبقات لا تتّكل إحداها على الأخرى:
`payments.idempotency_key` الفريد يمنع دفعتين لنفس الضغطة، وقفلُ صف الطلب
يسلسل الإشعارات المتزامنة، وحالةُ الطلب (`created` وحدها تُسوّى) تجعل الإشعار
المُعاد لا حدثاً. وفوقها مفاتيح قيود الدفتر المشتقة من مُعرّف الطلب.

**ترتيب الأقفال: صف الرحلة ← صف الدفعة ← صف الطلب ← صف الكبتن ← القفل الاستشاري
للمحفظة.** `_locked_order` يأخذ قفل الدفعة قبل قفل الطلب لأن الاسترداد الإداري
يبدأ من الدفعة، وصفُّ الكبتن يأتي بعد صف الطلب في مسار الاشتراك لأن الإشعار
يبدأ من الطلب — فلو عكس أحدُ المسارين الترتيب تقابلا في جمود. ونداءُ المزود يقع
**خارج** قفل الطلب حيث أمكن (`reconcile`)، فلا يُحتجز صفٌّ طولَ رحلةٍ عبر
الشبكة.

الـ commit مسؤولية الراوتر: دفعةٌ وقيدُها لا يُثبَّت نصفهما.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import (
    FeatureDisabled,
    InvalidInput,
    NotFound,
    PermissionDenied,
)
from app.models.enums import (
    CountryCode,
    Currency,
    FeatureKey,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    ProviderOrderPurpose,
    ProviderOrderStatus,
    WalletTransactionType,
)
from app.models.driver import Driver
from app.models.payment import Payment, SavedCard
from app.models.provider_order import OPEN_ORDER_STATUSES, ProviderOrder
from app.models.ride import Ride
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.services import (
    cancellation,
    offers,
    payments as payments_service,
    settings_service,
    subscriptions as subscriptions_service,
    wallet,
)
from app.services.card_gateway import (
    CardDetails,
    OrderRequest,
    OrderState,
    get_gateway,
    resolve_webhook,
    return_url_for,
)

logger = logging.getLogger(__name__)

# سقف Telr على `ivp_cart` قصير، فالمُعرّف قصيرٌ عمداً: بادئة الغرض + 18 خانة
# ست عشرية (72 بت). لا تصادم عملياً، والقيد الفريد في القاعدة هو الحكم الأخير.
_CART_RANDOM_BYTES = 9


def _now() -> datetime:
    return datetime.now(UTC)


def _new_cart_id(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(_CART_RANDOM_BYTES)}"


# --------------------------------------------------------------- بوابة القناة


async def require_card_enabled(
    session: AsyncSession, country_code: CountryCode
) -> None:
    """`card_enabled` يُرفع تلقائياً بتفعيل عقد Telr (SPEC القسم 4).

    غياب الصف = معطّل. لا يفترض الكود تفعيلاً لقناةٍ مالية أبداً.
    """
    if not await settings_service.is_feature_enabled(
        session, country_code, FeatureKey.CARD_ENABLED
    ):
        raise FeatureDisabled("الدفع بالبطاقة غير مفعّل في بلدك")


# ------------------------------------------------------------------ القراءة


async def get_order(
    session: AsyncSession, cart_id: str, *, for_update: bool = False
) -> ProviderOrder:
    stmt = select(ProviderOrder).where(ProviderOrder.cart_id == cart_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    order = await session.scalar(stmt)
    if order is None:
        raise NotFound("طلب الدفع غير موجود")
    return order


async def order_for_user(
    session: AsyncSession, cart_id: str, user: User
) -> ProviderOrder:
    """ملكية الطلب قبل قراءته — لا IDOR (SPEC القسم 14)."""
    order = await get_order(session, cart_id)
    if order.user_id != user.id and not payments_service.is_staff(user):
        # 404 لا 403: وجود طلبٍ ماليٍّ ليس معلومة يستحقها غير صاحبه
        raise NotFound("طلب الدفع غير موجود")
    return order


async def open_order_for_ride(
    session: AsyncSession, ride_id: uuid.UUID
) -> ProviderOrder | None:
    """الطلب المعلّق على الرحلة — منه يبني العميل زرّ «متابعة الدفع»."""
    return await session.scalar(
        select(ProviderOrder)
        .where(
            ProviderOrder.ride_id == ride_id,
            ProviderOrder.status.in_(OPEN_ORDER_STATUSES),
        )
        .order_by(ProviderOrder.created_at.desc())
        .limit(1)
    )


async def _locked_order(session: AsyncSession, cart_id: str) -> ProviderOrder:
    """يقفل صف الدفعة (إن وُجدت) ثم صف الطلب — بهذا الترتيب لا غيره.

    القراءة الأولى بلا قفل ليست ثغرة: غرضها معرفةُ **أي** دفعة تُقفل، والحكم
    كله يُبنى بعدها على الصف المقفول المُعاد تحميله.
    """
    peek = await get_order(session, cart_id)
    if peek.payment_id is not None:
        await payments_service.get_payment(session, peek.payment_id, for_update=True)
    return await get_order(session, cart_id, for_update=True)


# ------------------------------------------------------------------ الإنشاء


def _order_request(
    *,
    cart_id: str,
    payer: User,
    amount: Decimal,
    currency: Currency,
    description: str,
    save_card: bool,
) -> OrderRequest:
    return OrderRequest(
        cart_id=cart_id,
        amount=amount,
        currency=currency,
        # وصفٌ بحروف لاتينية: يعبر نماذج HTTP لدى المزودين بلا لبس ترميز
        description=description,
        return_url=return_url_for(cart_id, payer_role=payer.role),
        customer_name=payer.name,
        customer_phone=payer.phone,
        # مُعرّفٌ ثابت للدافع لدى المزود — به تُربط بطاقاته المحفوظة
        customer_ref=str(payer.id),
        save_card=save_card,
    )


async def _start(
    session: AsyncSession,
    *,
    order: ProviderOrder,
    payer: User,
    description: str,
    saved_card_id: uuid.UUID | None,
) -> ProviderOrder:
    """يفتح العملية عند المزود: صفحةً مستضافة أو خصماً بضغطة.

    نداء الشبكة يقع تحت قفل صف الرحلة في مسار أجرة الرحلة. هذا مقصود ومحدود:
    القفل يخص رحلةً واحدة، ولا يحجز إلا محاولاتِ دفعٍ أخرى على **نفس** الرحلة
    — وهي بالضبط ما نريد تسلسله. والمهلة مسقوفة في `card_gateway.base`.
    """
    gateway = await get_gateway(session, order.country_code)
    request = _order_request(
        cart_id=order.cart_id,
        payer=payer,
        amount=order.amount,
        currency=order.currency,
        description=description,
        save_card=order.save_card,
    )

    if saved_card_id is not None:
        card = await _owned_card(session, saved_card_id, payer)
        state = await gateway.charge_saved_card(request, card.provider_token)
        order.provider_order_ref = state.provider_order_ref
        await session.flush()
        # الخصم بضغطة يعود بحالٍ نهائية، فتُسوّى الآن لا بإشعارٍ لاحق
        return await apply_state(session, cart_id=order.cart_id, state=state)

    page = await gateway.create_hosted_page(request)
    order.provider_order_ref = page.provider_order_ref
    order.redirect_url = page.redirect_url
    await session.flush()
    return order


async def start_ride_payment(
    session: AsyncSession,
    *,
    ride: Ride,
    rider: User,
    amount: Decimal,
    idempotency_key: str,
    save_card: bool = False,
    saved_card_id: uuid.UUID | None = None,
) -> Payment:
    """يفتح دفعة بطاقة على رحلة مكتملة ويعيدها.

    تُستدعى من `payments.pay_ride` **تحت قفل صف الرحلة** وبعد حساب المتبقي،
    فالمبلغ هنا لا يأتي من عميل أبداً (SPEC القسم 14).
    """
    await require_card_enabled(session, ride.country_code)

    payment = Payment(
        ride_id=ride.id,
        method=PaymentMethod.CARD,
        provider=PaymentProvider.TELR,
        amount=amount,
        currency=currency_for_country(ride.country_code),
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
    )
    session.add(payment)
    await session.flush()

    order = ProviderOrder(
        provider=PaymentProvider.TELR,
        purpose=ProviderOrderPurpose.RIDE_PAYMENT,
        status=ProviderOrderStatus.CREATED,
        cart_id=_new_cart_id("r"),
        user_id=rider.id,
        country_code=ride.country_code,
        amount=amount,
        currency=payment.currency,
        ride_id=ride.id,
        payment_id=payment.id,
        save_card=save_card,
    )
    session.add(order)
    await session.flush()

    await _start(
        session,
        order=order,
        payer=rider,
        description=f"TAXO ride {str(ride.id)[:8]}",
        saved_card_id=saved_card_id,
    )
    return payment


async def start_wallet_topup(
    session: AsyncSession,
    *,
    owner: User,
    amount: Decimal,
    save_card: bool = False,
    saved_card_id: uuid.UUID | None = None,
) -> ProviderOrder:
    """شحن محفظة بالبطاقة — فوريٌّ آلي بلا طلبٍ ينتظر إنساناً (SPEC القسم 7).

    كليك والكاش يمران بـ `wallet_topup_requests` لأن لا API يشهد عليهما؛ هذه
    يشهد عليها المزود، فأثرها الوحيد قيدُ `topup` عند تأكيده.
    """
    await wallet.require_wallet_enabled(session, owner.country_code)
    await require_card_enabled(session, owner.country_code)
    wallet.require_not_frozen(owner)
    # يفحص أن للحساب محفظة أصلاً (راكب أو كبتن لا مشرف)
    wallet.owner_type_for(owner)

    order = ProviderOrder(
        provider=PaymentProvider.TELR,
        purpose=ProviderOrderPurpose.WALLET_TOPUP,
        status=ProviderOrderStatus.CREATED,
        cart_id=_new_cart_id("w"),
        user_id=owner.id,
        country_code=owner.country_code,
        amount=amount,
        currency=currency_for_country(owner.country_code),
        save_card=save_card,
    )
    session.add(order)
    await session.flush()

    return await _start(
        session,
        order=order,
        payer=owner,
        description="TAXO wallet topup",
        saved_card_id=saved_card_id,
    )


async def start_subscription(
    session: AsyncSession,
    *,
    driver: Driver,
    owner: User,
    plan: SubscriptionPlan,
    save_card: bool = False,
    saved_card_id: uuid.UUID | None = None,
) -> ProviderOrder:
    """اشتراك كبتنٍ بالبطاقة — فوريٌّ آلي كشحن المحفظة (SPEC القسم 8).

    **لا صفَّ اشتراكٍ يُنشأ هنا**: الطلب يحمل الخطة، والصف يولد في
    `_activate_subscription` بعد أن يقول المزود «دُفع». اشتراكٌ مكتوبٌ قبل
    الدفع يعطي رحلاتٍ بمالٍ لم يصل.

    والمبلغ سعرُ الخطة من القاعدة لا من العميل: كل حساب مالي في الخلفية
    (القسم 14).
    """
    await require_card_enabled(session, owner.country_code)
    subscriptions_service.require_purchasable(driver)

    # **الخصمُ يقع على مبلغ الطلب لا على صفّ الاشتراك** (البند ٥٤): الطلبُ هو
    # ما يُدفع، فمبلغٌ كاملٌ يُفتح به ثم صفٌّ مخفَّضٌ يُكتب بعده يحصّل من الكبتن
    # ما لم يُخصم. ولا `for_update` هنا: لا صفَّ يُكتب بعدُ فلا ميزانيةَ تُستهلك،
    # والحجزُ يقع لحظةَ التفعيل.
    offer = await offers.resolve(session, driver=driver, plan=plan)
    payable = plan.price - (offer.amount if offer is not None else Decimal("0"))

    order = ProviderOrder(
        provider=PaymentProvider.TELR,
        purpose=ProviderOrderPurpose.SUBSCRIPTION,
        status=ProviderOrderStatus.CREATED,
        cart_id=_new_cart_id("s"),
        user_id=owner.id,
        country_code=owner.country_code,
        amount=payable,
        currency=plan.currency,
        plan_id=plan.id,
        save_card=save_card,
    )
    session.add(order)
    await session.flush()

    return await _start(
        session,
        order=order,
        payer=owner,
        description="TAXO driver subscription",
        saved_card_id=saved_card_id,
    )


# ------------------------------------------------------------------ التسوية


async def apply_state(
    session: AsyncSession,
    *,
    cart_id: str,
    state: OrderState,
) -> ProviderOrder:
    """البابُ الوحيد الذي يتحرك فيه المال في هذه القناة.

    يُستدعى من الإشعار ومن استعلام العميل ومن الخصم بضغطة معاً، فيُقفل الصفَّ
    ويرفض ما ليس `created`: إشعارٌ مُعاد أو استعلامٌ متأخر لا يقيّد شيئاً ثانياً.
    """
    order = await _locked_order(session, cart_id)

    if order.provider_order_ref is None:
        order.provider_order_ref = state.provider_order_ref

    if order.status not in OPEN_ORDER_STATUSES:
        return order
    if not state.settled:
        # لم يحسم المزود بعد: الراكب على الصفحة أو البنك يصادق. لا تخمين
        return order

    payment = (
        await payments_service.get_payment(session, order.payment_id)
        if order.payment_id is not None
        else None
    )
    if payment is not None and state.transaction_ref:
        payment.provider_payment_id = state.transaction_ref

    if not state.paid:
        return await _mark_failed(session, order, payment, state.status_text)

    # المزود قد يعيد مبلغه؛ إن اختلف عن مبلغنا فالحساب لا يُقفل بتخمين: تُفتح
    # واقعةُ نزاعٍ تفصلها الإدارة (القسم 13.4) ولا يتحرك الدفتر
    if state.amount is not None and state.amount != order.amount:
        return await _mark_amount_mismatch(session, order, payment, state.amount)

    order.status = ProviderOrderStatus.PAID
    if order.purpose == ProviderOrderPurpose.RIDE_PAYMENT:
        await _settle_ride_payment(session, order, payment)
    elif order.purpose == ProviderOrderPurpose.SUBSCRIPTION:
        await _activate_subscription(session, order)
    else:
        await _credit_wallet_topup(session, order)

    if order.save_card and state.card is not None:
        await _store_card(session, order, state.card)

    await session.flush()
    return order


async def _mark_failed(
    session: AsyncSession,
    order: ProviderOrder,
    payment: Payment | None,
    reason: str,
) -> ProviderOrder:
    """سقوط العملية يُسقط دفعتها، فيعود مبلغها ديناً على الرحلة.

    بغير ذلك تبقى الدفعة `pending` تحجز المبلغ فلا يستطيع الراكب اختيار قناة
    أخرى لرحلةٍ لم تُدفع — نفس منطق `resolution=unpaid` في نزاع كليك.
    """
    order.status = ProviderOrderStatus.FAILED
    order.failure_reason = reason[:255] or None

    if payment is not None:
        payments_service.require_transition(payment, PaymentStatus.FAILED)
        payment.status = PaymentStatus.FAILED
    await session.flush()
    return order


async def _mark_amount_mismatch(
    session: AsyncSession,
    order: ProviderOrder,
    payment: Payment | None,
    provider_amount: Decimal,
) -> ProviderOrder:
    reason = (
        f"مبلغ المزود ({provider_amount}) لا يطابق مبلغ الطلب ({order.amount})"
    )
    logger.error("تعارض مبلغ في طلب الدفع %s: %s", order.cart_id, reason)
    order.status = ProviderOrderStatus.FAILED
    order.failure_reason = reason[:255]

    if payment is not None:
        # `disputed` لا `failed`: مالُ الراكب قد خرج فعلاً، ومبلغُ الرحلة يبقى
        # محجوزاً حتى تفصل الإدارة — لا يُفتح للدفع مرتين ولا يُقيَّد بلا يقين
        payments_service.require_transition(payment, PaymentStatus.DISPUTED)
        payment.status = PaymentStatus.DISPUTED
        payment.dispute_reason = reason[:255]
        payment.disputed_at = _now()
    await session.flush()
    return order


async def _settle_ride_payment(
    session: AsyncSession, order: ProviderOrder, payment: Payment | None
) -> None:
    if payment is None:  # pragma: no cover - يمنعه قيد القاعدة
        raise NotFound("دفعة هذا الطلب غير موجودة")

    ride = await session.get(Ride, order.ride_id)
    rider = await session.get(User, ride.rider_id)
    await payments_service.settle(
        session,
        payment=payment,
        ride=ride,
        rider=rider,
        confirmed_by=PaymentConfirmedBy.SYSTEM,
        # المزود هو من أكّد، لا مستخدمٌ ضغط زراً
        actor_id=None,
    )


async def _activate_subscription(
    session: AsyncSession, order: ProviderOrder
) -> None:
    """يفتح اشتراك الكبتن بعد أن دفع المزود (SPEC القسم 8).

    **لا قيد في الدفتر**: مال الكبتن خرج من بطاقته لا من محفظته — نفس عدم
    التماثل الذي تسير عليه دفعةُ الرحلة بالبطاقة مع الراكب. وأثرُ الطلب هنا
    صفُّ الاشتراك نفسه، فلا `transaction_id` له.

    والقفل: صفُّ الطلب مأخوذٌ سلفاً في `_locked_order`، ويأتي صفُّ الكبتن بعده
    داخل الخدمة — بهذا الترتيب لا عكسه.
    """
    owner = await session.get(User, order.user_id)
    await subscriptions_service.activate_paid_order(
        session,
        driver_user=owner,
        plan_id=order.plan_id,
        amount=order.amount,
        reference=order.provider_order_ref,
        # الطلب نفسه مفتاح عدم التكرار: إشعاران لا يفتحان اشتراكين
        idempotency_key=f"card-subscription:{order.id}",
    )


async def _credit_wallet_topup(
    session: AsyncSession, order: ProviderOrder
) -> None:
    owner = await session.get(User, order.user_id)
    # تجميدُ محفظةٍ بعد بدء الشحن لا يجوز أن يحرق مالاً دخل فعلاً: القيد يُكتب
    # ويبقى المنعُ على الإنفاق منه (`require_not_frozen` في مسارات الدفع)
    entry = await wallet.record(
        session,
        owner=owner,
        tx_type=WalletTransactionType.TOPUP,
        amount=order.amount,
        reference=order.provider_order_ref,
        created_by=None,
        # الطلب نفسه مفتاح عدم التكرار: إشعاران لا يشحنان مرتين
        idempotency_key=f"card-topup:{order.id}",
    )
    order.transaction_id = entry.id
    # دَينُ إلغاءٍ يُسدَّد لحظةَ اكتمال الشحن (`CANCELLATION-FEE.md` §7).
    # **وهذا هو مخرجُ قناة البطاقة**: الشحنةُ لا تحمل الدَّينَ في مسار الأجرة
    # (تفسيرُه في `cancellation.collect_with_ride`)، فمن يشحن محفظته يسدّد هنا
    await cancellation.on_wallet_funded(session, user=owner)


# ---------------------------------------------------------------- الاستعلام


async def drop_unopened(
    session: AsyncSession, order: ProviderOrder
) -> ProviderOrder:
    """يُسقط طلباً **لم يصل المزودَ أصلاً** (لا مرجع له) ويُحرّر دفعتَه.

    يستدعيه كنسُ الصيانة وحده (`services/order_maintenance.py`)، وشرطُه هناك:
    لا `provider_order_ref` ومضى عليه ما يكفي. والبابُ هنا لا هناك لأن تحريرَ
    صفِّ الدفعة شأنُ هذه القناة — وبغيره تبقى `pending` تحجز مبلغَ رحلةٍ لم
    تُدفع، وهو ما يمنع صاحبَها من اختيار قناةٍ أخرى.
    """
    order = await _locked_order(session, order.cart_id)
    if order.status not in OPEN_ORDER_STATUSES:
        return order
    # **ومرجعٌ ظهر بين القراءتين يمنع الإسقاط**: نداءُ فتحٍ متأخرٌ كتبه، فالطلبُ
    # موجودٌ لدى المزود بعد كل شيء — والحكمُ يعود إليه لا إلينا
    if order.provider_order_ref is not None:
        return order

    payment = (
        await payments_service.get_payment(session, order.payment_id, for_update=True)
        if order.payment_id is not None
        else None
    )
    return await _mark_failed(session, order, payment, "لم يُفتح لدى المزود")


async def reconcile(session: AsyncSession, order: ProviderOrder) -> ProviderOrder:
    """يسأل المزود عن الطلب ثم يسوّيه — مسار عودة العميل من صفحة الدفع.

    ليس مسار احتياطٍ للـ webhook بل شريكُه: أيُّهما وصل أولاً سوّى، والآخر يجد
    الطلب محسوماً فلا يفعل شيئاً. والسؤال يقع **قبل** أخذ القفل، فطلبان
    متزامنان لا يحتجز أولهما الصفَّ طولَ نداءٍ عبر الشبكة.
    """
    if order.status not in OPEN_ORDER_STATUSES or not order.provider_order_ref:
        return order

    gateway = await get_gateway(session, order.country_code)
    state = await gateway.check_order(order.provider_order_ref)
    return await apply_state(session, cart_id=order.cart_id, state=state)


async def handle_webhook(
    session: AsyncSession, payload: dict[str, str]
) -> ProviderOrder:
    """إشعار المزود: يُتحقق من توقيعه، ثم **لا يُقرأ منه مبلغ ولا حالة**.

    الحمولة تحدد أيَّ طلبٍ ننظر فيه فقط؛ الحالة والمبلغ يأتيان من `check_order`
    (نداءٌ من الخلفية إلى المزود). فتوقيعٌ صحيح لحمولةٍ عُدّل مبلغها لا يقيّد
    ديناراً زائداً — وهذا هو المقصود من «تحقق توقيع Webhooks» في القسم 14:
    أن يكون التوقيع شرطاً لا سنداً.
    """
    gateway, notice = await resolve_webhook(session, payload)

    order = await get_order(session, notice.cart_id)
    if order.status not in OPEN_ORDER_STATUSES:
        return order

    state = await gateway.check_order(
        order.provider_order_ref or notice.provider_order_ref
    )
    return await apply_state(session, cart_id=order.cart_id, state=state)


# ---------------------------------------------------------------- الاسترداد


async def refund_via_provider(
    session: AsyncSession, *, payment: Payment, reason: str
) -> str:
    """يردّ دفعة بطاقة إلى بطاقتها عبر المزود ويعيد مرجع الردّ.

    يُستدعى من `payments.refund` وهو يحمل قفل صف الدفعة، فقفلُ الطلب يأتي بعده
    — نفس الترتيب في كل مسار.
    """
    order = await session.scalar(
        select(ProviderOrder)
        .where(ProviderOrder.payment_id == payment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None or order.provider_order_ref is None:
        raise InvalidInput("لا طلب دفعٍ لدى المزود يمكن الردّ عليه")
    if order.status != ProviderOrderStatus.PAID:
        raise InvalidInput("لم يُدفع هذا الطلب لدى المزود فلا شيء يُردّ")
    if order.refund_ref is not None:
        # ردٌّ سابق قائم — لا يُطلب من المزود ردّان لدفعةٍ واحدة
        return order.refund_ref

    gateway = await get_gateway(session, order.country_code)
    order.refund_ref = await gateway.refund_order(
        order.provider_order_ref, payment.amount, payment.currency, reason
    )
    await session.flush()
    return order.refund_ref


# ------------------------------------------------------- البطاقات المحفوظة


async def _owned_card(
    session: AsyncSession, card_id: uuid.UUID, user: User
) -> SavedCard:
    card = await session.get(SavedCard, card_id)
    if card is None or card.user_id != user.id:
        raise NotFound("البطاقة المحفوظة غير موجودة")
    return card


async def list_cards(session: AsyncSession, user: User) -> Sequence[SavedCard]:
    return (
        await session.scalars(
            select(SavedCard)
            .where(SavedCard.user_id == user.id)
            .order_by(SavedCard.is_default.desc(), SavedCard.created_at.desc())
        )
    ).all()


async def _store_card(
    session: AsyncSession, order: ProviderOrder, card: CardDetails
) -> None:
    """يحفظ رمز البطاقة بعد نجاح الدفع (SPEC القسم 6.4).

    ما ينقص منه رمزٌ أو آخرُ أربعةٍ أو تاريخٌ لا يُحفظ: بطاقةٌ لا تُعرض لصاحبها
    ولا يُدفع بها صفٌّ بلا فائدة. **ولا PAN ولا CVV هنا بحال** — لا يصل
    أصلاً، وهذا هو غرض الـ tokenization.
    """
    if not card.is_storable:
        return

    existing = await session.scalar(
        select(SavedCard).where(
            SavedCard.user_id == order.user_id,
            SavedCard.provider == order.provider,
            SavedCard.provider_token == card.token,
        )
    )
    if existing is not None:
        existing.brand = card.brand
        existing.last4 = card.last4
        existing.expiry_month = card.expiry_month
        existing.expiry_year = card.expiry_year
        return

    count = await session.scalar(
        select(func.count(SavedCard.id)).where(SavedCard.user_id == order.user_id)
    )
    session.add(
        SavedCard(
            user_id=order.user_id,
            provider=order.provider,
            provider_token=card.token,
            brand=card.brand,
            last4=card.last4,
            expiry_month=card.expiry_month,
            expiry_year=card.expiry_year,
            # أولى البطاقات هي الافتراضية بلا اختيار — ولا ثانية لها تنازعها
            is_default=not count,
        )
    )


async def set_default_card(
    session: AsyncSession, card_id: uuid.UUID, user: User
) -> SavedCard:
    card = await _owned_card(session, card_id, user)
    for other in await list_cards(session, user):
        other.is_default = other.id == card.id
    await session.flush()
    return card


async def delete_card(
    session: AsyncSession, card_id: uuid.UUID, user: User
) -> None:
    """حذف بطاقة محفوظة — حقٌّ لصاحبها وحده.

    الصفُّ يُمحى فعلاً بخلاف الجداول المالية: رمزٌ محفوظ بيانُ راحةٍ لا سجلٌّ
    محاسبي (SPEC القسم 4). والدفعاتُ التي مرّت به تبقى بمراجعها في `payments`.
    """
    card = await _owned_card(session, card_id, user)
    was_default = card.is_default
    await session.delete(card)
    await session.flush()

    if was_default:
        remaining = await list_cards(session, user)
        if remaining:
            remaining[0].is_default = True
            await session.flush()


def require_owner(order: ProviderOrder, user: User) -> None:
    if order.user_id != user.id:
        raise PermissionDenied("هذا الطلب ليس لك")
