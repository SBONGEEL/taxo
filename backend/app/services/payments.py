"""تحصيل أجرة الرحلة (SPEC القسم 6/9).

أربع قنوات وثلاثة سلوكات:

- **يقبضها الكبتن بيده** (كاش، كليك): لا يمر المال بنا، فلا قيد `ride_earning`
  له في الدفتر (القسم 9). الدفعة `pending` حتى يضغط الكبتن «استلمت»، وفي كليك
  وحدها له أن يضغط «لم يصلني» فتصير `disputed` وتنتقل للوحة الإدارة.
- **يمر المال بالمنصة من محفظة الراكب** (المحفظة): يُخصم منه ويُقيَّد للكبتن في
  نفس المعاملة.
- **يمر المال بالمنصة من غير محفظة الراكب** (البطاقة، المرحلة 6-ب): يُقيَّد
  للكبتن ولا يُخصم من محفظة الراكب — مالُه خرج من بطاقته لا من رصيده، فقيدُ
  خصمٍ عليه خصمٌ ثانٍ. تسويةُ هذه القناة كلها في `services/card_payments.py`،
  وهي تنتهي إلى `settle` هنا كما تنتهي إليه بقية القنوات.

**الدفع المختلط** (القسم 6) ليس قناةً خامسة بل نتيجةُ رصيدٍ جزئي: يدفع الراكب
ما في محفظته ويبقى الباقي كاشاً — صفّان على رحلة واحدة، أولهما `confirmed`
فوراً والثاني ينتظر الكبتن.

**ترتيب الأقفال: صف الرحلة ← صف الدفعة ← صف طلب المزود ← القفل الاستشاري
للمحفظة.** إنشاء الدفعات يقفل الرحلة (فلا ينشئ طلبان متزامنان دفعتين لنفس
المبلغ)، وكل تغيير حالةٍ يقفل صف الدفعة **قبل** فحص الانتقال (فلا يمر تأكيدان
معاً على `pending` واحدة)، وطلبُ المزود يُقفل بعد دفعته، والقيود المالية تأخذ
قفل المحفظة أخيراً. لا مسار يعكس هذا الترتيب، فلا جمود.

الـ commit مسؤولية الراوتر: دفعةٌ وقيدُها لا يُثبَّت نصفهما.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import (
    FeatureDisabled,
    InsufficientBalance,
    InvalidInput,
    InvalidPaymentTransition,
    NotFound,
    PermissionDenied,
    RideAlreadyPaid,
    RideNotPayable,
)
from app.models.commission import CommissionSetting
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    CommissionAppliesTo,
    DisputeResolution,
    FeatureKey,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentStatus,
    RideStatus,
    UserRole,
    WalletTransactionType,
)
from app.models.payment import (
    DIRECTLY_COLLECTED_METHODS,
    OWING_PAYMENT_STATUSES,
    WALLET_FUNDED_METHODS,
    Payment,
)
from app.models.ride import Ride
from app.models.user import User
from app.services import audit, settings_service, wallet
from app.services.pricing import round_money

# آلة حالات الدفعة — ما ليس هنا ممنوع (SPEC القسم 4)
ALLOWED_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset(
        {PaymentStatus.CONFIRMED, PaymentStatus.FAILED, PaymentStatus.DISPUTED}
    ),
    # مخرجا النزاع حكمان لا ثالث لهما: وصل المال أو لم يصل
    PaymentStatus.DISPUTED: frozenset({PaymentStatus.CONFIRMED, PaymentStatus.FAILED}),
    PaymentStatus.CONFIRMED: frozenset({PaymentStatus.REFUNDED}),
    PaymentStatus.FAILED: frozenset(),
    PaymentStatus.REFUNDED: frozenset(),
}

# القناة والمفتاح الذي يحكمها. الكاش ليس هنا: لا مفتاح له لأنه القناة الوحيدة
# التي تعمل بلا أي إعداد — وإعدادُ ليبيا الافتراضي «كاش فقط» (SPEC القسم 4).
METHOD_FEATURE: dict[PaymentMethod, FeatureKey] = {
    PaymentMethod.CLIQ: FeatureKey.CLIQ_ENABLED,
    PaymentMethod.CARD: FeatureKey.CARD_ENABLED,
    PaymentMethod.WALLET: FeatureKey.WALLET_ENABLED,
}

# قنوات يمكن استردادها: ما دخل المنصةَ وحده يخرج منها. الكاش وكليك قبضهما
# الكبتن بيده فلا نملك ما نردّه (SPEC القسم 9).
REFUNDABLE_METHODS: tuple[PaymentMethod, ...] = (
    PaymentMethod.WALLET,
    PaymentMethod.CARD,
)


STAFF_ROLES: tuple[UserRole, ...] = (UserRole.ADMIN, UserRole.SUPPORT)


def _now() -> datetime:
    return datetime.now(UTC)


def is_staff(user: User) -> bool:
    """من يقرأ سجلات غيره بحكم دوره (SPEC القسم 13.8)."""
    return user.role in STAFF_ROLES


# ------------------------------------------------------------------ القراءة


async def get_payment(
    session: AsyncSession, payment_id: uuid.UUID, *, for_update: bool = False
) -> Payment:
    """`for_update` إلزامي لكل مسار يغيّر الحالة.

    بدونه تقرأ ضغطتان متزامنتان على «استلمت المبلغ» الحالةَ `pending` معاً قبل
    أن يُثبّت أيّهما تغييره، فتمر كلتاهما من `require_transition` ولا يمنع
    القيدَ المزدوج إلا مفتاح عدم التكرار — والحارس لا يُترك حارساً وحيداً.
    نفس نهج `topups.get_request` و`withdrawals.get_request`.
    """
    stmt = select(Payment).where(Payment.id == payment_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)

    payment = await session.scalar(stmt)
    if payment is None:
        raise NotFound("الدفعة غير موجودة")
    return payment


async def list_for_ride(
    session: AsyncSession, ride_id: uuid.UUID
) -> Sequence[Payment]:
    return (
        await session.scalars(
            select(Payment)
            .where(Payment.ride_id == ride_id)
            .order_by(Payment.created_at, Payment.id)
        )
    ).all()


async def list_all(
    session: AsyncSession,
    *,
    status: PaymentStatus | None,
    limit: int,
    offset: int,
) -> Sequence[Payment]:
    """قائمة اللوحة — الفلترة على `disputed` هي شاشة النزاعات (القسم 13.4)."""
    stmt = select(Payment).order_by(Payment.created_at.desc())
    if status is not None:
        stmt = stmt.where(Payment.status == status)
    return (await session.scalars(stmt.limit(limit).offset(offset))).all()


async def outstanding_amount(session: AsyncSession, ride: Ride) -> Decimal:
    """ما تبقّى من أجرة الرحلة بعد الدفعات القائمة.

    `failed` و`refunded` لا تُحسب: مبلغُ دفعةٍ سقطت مبلغٌ ما زال مطلوباً.
    """
    covered = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.ride_id == ride.id,
            Payment.status.in_(OWING_PAYMENT_STATUSES),
        )
    )
    due = ride.final_fare or Decimal("0.000")
    return round_money(due - Decimal(covered))


# ------------------------------------------------------------------ الإنشاء


def require_transition(payment: Payment, target: PaymentStatus) -> None:
    """يُفحص **بعد** قفل صف الدفعة لا قبله — انظر `get_payment`."""
    if target not in ALLOWED_TRANSITIONS[payment.status]:
        raise InvalidPaymentTransition(
            f"لا يمكن الانتقال من «{payment.status.value}» إلى «{target.value}»"
        )


async def _require_method_enabled(
    session: AsyncSession, ride: Ride, method: PaymentMethod
) -> None:
    feature = METHOD_FEATURE.get(method)
    if feature is None:
        return
    if not await settings_service.is_feature_enabled(
        session, ride.country_code, feature
    ):
        raise FeatureDisabled(f"قناة الدفع «{method.value}» غير مفعّلة في بلدك")


async def _payable_ride(session: AsyncSession, ride_id: uuid.UUID) -> Ride:
    """الرحلة مقفولاً صفُّها — بغيره ينشئ طلبان متزامنان دفعتين لنفس المبلغ."""
    ride = await session.scalar(
        select(Ride)
        .where(Ride.id == ride_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if ride is None:
        raise NotFound("الرحلة غير موجودة")
    # شاشة الدفع تلي الإنهاء في تدفق القسم 5؛ رسوم إلغاءٍ ليست أجرة رحلة
    if ride.status != RideStatus.COMPLETED or ride.final_fare is None:
        raise RideNotPayable()
    return ride


def _new_payment(
    ride: Ride,
    *,
    method: PaymentMethod,
    amount: Decimal,
    idempotency_key: str | None,
) -> Payment:
    return Payment(
        ride_id=ride.id,
        method=method,
        amount=amount,
        # العملة من دولة الرحلة لا من العميل (SPEC القسم 4)
        currency=currency_for_country(ride.country_code),
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
    )


async def pay_ride(
    session: AsyncSession,
    *,
    ride_id: uuid.UUID,
    rider: User,
    method: PaymentMethod,
    idempotency_key: str,
    save_card: bool = False,
    saved_card_id: uuid.UUID | None = None,
) -> Sequence[Payment]:
    """يفتح دفعات الرحلة بالقناة المختارة ويعيدها كلها.

    قد ترجع صفّين: رصيدٌ جزئي في المحفظة يعني دفعاً مختلطاً (القسم 6).
    `save_card` و`saved_card_id` للبطاقة وحدها (القسم 6.4)، وتتجاهلهما بقية
    القنوات: خيارُ حفظ بطاقةٍ في دفعةٍ نقدية لا معنى له فلا يُعطى معنى.
    """
    ride = await _payable_ride(session, ride_id)
    if ride.rider_id != rider.id:
        # 404 لا 403: وجود الرحلة ليس معلومة يستحقها غير أطرافها
        raise NotFound("الرحلة غير موجودة")

    # الفحص بعد قفل الرحلة لا قبله: ضغطتان بنفس المفتاح تتسلسلان هنا فتجد
    # الثانيةُ دفعةَ الأولى بدل أن تصطدم بالقيد الفريد
    if await _find_by_idempotency_key(session, idempotency_key) is not None:
        return await list_for_ride(session, ride.id)

    outstanding = await outstanding_amount(session, ride)
    if outstanding <= 0:
        raise RideAlreadyPaid()

    await _require_method_enabled(session, ride, method)

    if method == PaymentMethod.CARD:
        # استيرادٌ داخل الدالة عمداً: `card_payments` يستورد هذا الملف ليصل إلى
        # `settle` — وهو الاتجاه الصحيح، فالبطاقة تبني على التسوية لا العكس.
        # استيرادُها هنا يكسر الحلقة في نقطةٍ واحدة معلومة بدل أن يوزّع
        # الاعتماد على الطبقتين.
        from app.services import card_payments

        await card_payments.start_ride_payment(
            session,
            ride=ride,
            rider=rider,
            amount=outstanding,
            idempotency_key=idempotency_key,
            save_card=save_card,
            saved_card_id=saved_card_id,
        )
        return await list_for_ride(session, ride.id)

    if method == PaymentMethod.WALLET:
        payments = await _pay_from_wallet(
            session,
            ride=ride,
            rider=rider,
            outstanding=outstanding,
            idempotency_key=idempotency_key,
        )
    else:
        if method == PaymentMethod.CLIQ:
            await _require_cliq_alias(session, ride)
        payments = [
            _new_payment(
                ride,
                method=method,
                amount=outstanding,
                idempotency_key=idempotency_key,
            )
        ]
        session.add(payments[0])

    try:
        await session.flush()
    except IntegrityError as exc:
        # القيد الفريد على المفتاح — سباقٌ عبر عمليتين لا تتقاسمان قفل الصف
        await session.rollback()
        raise RideAlreadyPaid("هذه العملية نُفّذت بالفعل") from exc

    return await list_for_ride(session, ride.id)


async def _find_by_idempotency_key(
    session: AsyncSession, key: str
) -> Payment | None:
    return await session.scalar(
        select(Payment).where(Payment.idempotency_key == key)
    )


async def _require_cliq_alias(session: AsyncSession, ride: Ride) -> None:
    """كليك تحويلٌ على alias الكبتن (القسم 6.2) — فبلا alias لا وجهة للمال."""
    alias = await session.scalar(
        select(Driver.cliq_alias).where(Driver.id == ride.driver_id)
    )
    if not (alias or "").strip():
        raise InvalidInput("لم يضف الكبتن alias كليك — اختر قناة أخرى")


async def _pay_from_wallet(
    session: AsyncSession,
    *,
    ride: Ride,
    rider: User,
    outstanding: Decimal,
    idempotency_key: str,
) -> list[Payment]:
    """خصمٌ فوري من رصيد الراكب، وما عجز عنه الرصيد يبقى كاشاً (القسم 6).

    المفتاح على صف المحفظة وحده حين ينقسم الدفع: البحث بالمفتاح يعيد دفعات
    الرحلة كلها، فالصف الثاني لا يحتاج مفتاحاً خاصاً به.
    """
    wallet.require_not_frozen(rider)

    # القفل قبل قراءة الرصيد: رصيدٌ يُقرأ ثم يُخصم منه لاحقاً رصيدٌ قديم
    await wallet.lock_wallet(session, rider.id)
    balance = await wallet.balance_of(session, rider)
    if balance <= 0:
        raise InsufficientBalance("لا رصيد في محفظتك — اختر قناة أخرى")

    wallet_amount = min(balance, outstanding)
    payments = [
        _new_payment(
            ride,
            method=PaymentMethod.WALLET,
            amount=wallet_amount,
            idempotency_key=idempotency_key,
        )
    ]
    remainder = round_money(outstanding - wallet_amount)
    if remainder > 0:
        payments.append(
            _new_payment(
                ride,
                method=PaymentMethod.CASH,
                amount=remainder,
                idempotency_key=None,
            )
        )

    session.add_all(payments)
    # المفتاح يلزم قبل الاستقرار: مفاتيح عدم التكرار مشتقة من مُعرّف الدفعة
    await session.flush()

    # الخصم فوري: المحفظة قناةٌ لا تنتظر تأكيد أحد
    await settle(
        session,
        payment=payments[0],
        ride=ride,
        rider=rider,
        confirmed_by=PaymentConfirmedBy.SYSTEM,
        actor_id=rider.id,
    )
    return payments


# ------------------------------------------------------------ تحريك المال


async def _driver_user(session: AsyncSession, ride: Ride) -> User | None:
    """صاحب محفظة الكبتن: `users.id` لا `drivers.id` (SPEC القسم 4)."""
    if ride.driver_id is None:
        return None
    user_id = await session.scalar(
        select(Driver.user_id).where(Driver.id == ride.driver_id)
    )
    return await session.get(User, user_id) if user_id else None


async def _commission_for(
    session: AsyncSession, ride: Ride, method: PaymentMethod
) -> Decimal:
    """عمولة المنصة على هذه الدفعة.

    **النسبة مجمّدة على الرحلة** (`commission_percent_at_ride`) ولا تُقرأ من
    الإعدادات: القسم 4 يمنع إعادة حسابها بأثر رجعي، فرفعُ النسبة اليوم لا يمس
    رحلةَ أمس. أما **النطاق** (`applies_to`) فيُقرأ الآن لأنه لا يمكن تجميده
    أصلاً: يتعلق بقناة الدفع، وهي لا تُعرف قبل شاشة الدفع.
    """
    percent = ride.commission_percent_at_ride
    if percent <= 0:
        return Decimal("0.000")

    applies_to = await session.scalar(
        select(CommissionSetting.applies_to).where(
            CommissionSetting.country_code == ride.country_code
        )
    )
    # الغياب كالغياب في feature_flags: لا يُفترض تفعيل ولا نطاق أوسع
    if applies_to is None:
        return Decimal("0.000")
    if (
        applies_to == CommissionAppliesTo.CASHLESS_RIDES
        and method in DIRECTLY_COLLECTED_METHODS
    ):
        return Decimal("0.000")
    return percent


async def settle(
    session: AsyncSession,
    *,
    payment: Payment,
    ride: Ride,
    rider: User,
    confirmed_by: PaymentConfirmedBy,
    actor_id: uuid.UUID | None,
) -> None:
    """يثبّت الدفعة `confirmed` ويكتب قيودها في الدفتر.

    بابُ التسوية لكل القنوات: يدخله الكبتن بضغطة «استلمت»، وتدخله المحفظة
    فوراً، وتدخله البطاقة من `card_payments.apply_state` بعد جواب المزود. حالةٌ
    واحدة تُكتب في مكان واحد.

    ثلاثة قيود ممكنة لكل دفعة، كلها بمفاتيح مشتقة من مُعرّفها فلا تتكرر:

    - `ride_payment` خصماً من الراكب — **للمحفظة وحدها** (`WALLET_FUNDED_METHODS`).
      البطاقة تمر بالمنصة ولا تمر بالمحفظة: مالُها خرج من بطاقة الراكب إلى
      المزود، فقيدُ خصمٍ على رصيده يخصم منه مرتين.
    - `ride_earning` إضافةً للكبتن **بكامل المبلغ**، ثم `commission` خصماً
      بنسبتها. القسم 6.3 يصف نصيب الكبتن صافياً، والقسم 9 يكتب الرصيد
      «أرباح − عمولات»: القيدان المنفصلان يعطيان نفس الصافي ويُبقيان العمولة
      سطراً ظاهراً في الكشف — وبقيدٍ واحد صافٍ لا تظهر عمولة الرحلات النقدية
      وحدها فيصير الكشفان مختلفين لنفس النسبة.
    - في الكاش وكليك لا `ride_earning`: الكبتن قبض المال بيده (القسم 9)،
      لكن العمولة تبقى مستحقة إن كان نطاقها `all_rides` — فتُخصم من محفظته.
      محفظةٌ فارغة تعني رفضَ التأكيد برسالة صريحة: المحفظة مسبقة الدفع لا
      تُسحب على المكشوف (القسم 4).
    """
    require_transition(payment, PaymentStatus.CONFIRMED)
    payment.status = PaymentStatus.CONFIRMED
    payment.confirmed_by = confirmed_by
    payment.confirmed_at = _now()

    if payment.method in WALLET_FUNDED_METHODS:
        entry = await wallet.record(
            session,
            owner=rider,
            tx_type=WalletTransactionType.RIDE_PAYMENT,
            amount=-payment.amount,
            ride_id=ride.id,
            created_by=actor_id,
            idempotency_key=f"payment:{payment.id}",
        )
        payment.transaction_id = entry.id

    driver_user = await _driver_user(session, ride)
    if driver_user is None:  # pragma: no cover - رحلة مكتملة لها كبتن دائماً
        return

    if payment.method not in DIRECTLY_COLLECTED_METHODS:
        await wallet.record(
            session,
            owner=driver_user,
            tx_type=WalletTransactionType.RIDE_EARNING,
            amount=payment.amount,
            ride_id=ride.id,
            created_by=actor_id,
            idempotency_key=f"earning:{payment.id}",
        )

    percent = await _commission_for(session, ride, payment.method)
    if percent <= 0:
        return

    commission = round_money(payment.amount * percent / 100)
    if commission <= 0:
        return

    try:
        await wallet.record(
            session,
            owner=driver_user,
            tx_type=WalletTransactionType.COMMISSION,
            amount=-commission,
            ride_id=ride.id,
            created_by=actor_id,
            idempotency_key=f"commission:{payment.id}",
        )
    except InsufficientBalance as exc:
        raise InsufficientBalance(
            "رصيد محفظتك لا يغطي عمولة هذه الرحلة — اشحن المحفظة ثم أكّد"
        ) from exc


# ------------------------------------------------------------ إجراءات الكبتن


async def confirm_by_driver(
    session: AsyncSession, *, payment: Payment, driver: Driver
) -> Payment:
    """«استلمت المبلغ» — الكاش وكليك وحدهما (SPEC القسم 6.1/6.3)."""
    ride = await _ride_of(session, payment)
    if ride.driver_id != driver.id:
        raise PermissionDenied("هذه الدفعة ليست على رحلة مُسندة إليك")
    if payment.method not in DIRECTLY_COLLECTED_METHODS:
        raise InvalidPaymentTransition("هذه الدفعة تُحصَّل آلياً ولا تحتاج تأكيدك")

    require_transition(payment, PaymentStatus.CONFIRMED)
    rider = await session.get(User, ride.rider_id)
    await settle(
        session,
        payment=payment,
        ride=ride,
        rider=rider,
        confirmed_by=PaymentConfirmedBy.DRIVER,
        actor_id=driver.user_id,
    )
    return payment


async def dispute_by_driver(
    session: AsyncSession, *, payment: Payment, driver: Driver, reason: str
) -> Payment:
    """«لم يصلني» على دفعة كليك (SPEC القسم 6.2).

    كليك وحدها: التحويل يقع خارج التطبيق ولا API يشهد عليه، فبين قول الراكب
    «حوّلت» وقول الكبتن «لم يصلني» فراغٌ يملؤه إنسان. الكاش يقع يداً بيد فلا
    فراغ فيه، والمحفظة يشهد عليها الدفتر.
    """
    ride = await _ride_of(session, payment)
    if ride.driver_id != driver.id:
        raise PermissionDenied("هذه الدفعة ليست على رحلة مُسندة إليك")
    if payment.method != PaymentMethod.CLIQ:
        raise InvalidPaymentTransition("النزاع متاح على دفعات كليك وحدها")
    if not reason.strip():
        raise InvalidInput("سبب النزاع مطلوب")

    require_transition(payment, PaymentStatus.DISPUTED)
    payment.status = PaymentStatus.DISPUTED
    payment.dispute_reason = reason.strip()
    payment.disputed_at = _now()
    return payment


async def _ride_of(session: AsyncSession, payment: Payment) -> Ride:
    ride = await session.get(Ride, payment.ride_id)
    if ride is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
        raise NotFound("الرحلة غير موجودة")
    return ride


# ------------------------------------------------------------ إجراءات الإدارة


async def resolve_dispute(
    session: AsyncSession,
    *,
    payment: Payment,
    actor: User,
    resolution: DisputeResolution,
    note: str | None,
) -> Payment:
    """فصل الإدارة في نزاع (SPEC القسم 6.2/13.4).

    `paid` تعني أن المال وصل الكبتن فعلاً فتُثبَّت الدفعة وتُحسب عمولتها،
    و`unpaid` تعني أنه لم يصل فتسقط الدفعة ويعود مبلغها ديناً على الرحلة —
    يفتح الراكب دفعةً جديدة بقناة أخرى.
    """
    if payment.status != PaymentStatus.DISPUTED:
        raise InvalidPaymentTransition("لا نزاع قائم على هذه الدفعة")

    target = (
        PaymentStatus.CONFIRMED
        if resolution == DisputeResolution.PAID
        else PaymentStatus.FAILED
    )
    require_transition(payment, target)

    payment.resolution = resolution
    payment.resolution_note = (note or "").strip() or None
    payment.resolved_by = actor.id
    payment.resolved_at = _now()

    if target == PaymentStatus.CONFIRMED:
        ride = await _ride_of(session, payment)
        rider = await session.get(User, ride.rider_id)
        await settle(
            session,
            payment=payment,
            ride=ride,
            rider=rider,
            confirmed_by=PaymentConfirmedBy.ADMIN,
            actor_id=actor.id,
        )
    else:
        payment.status = PaymentStatus.FAILED

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="payment",
        entity_id=payment.id,
        # أسماء الحقول وحالاتها لا مبالغها (SPEC القسم 14)
        details={"status": payment.status.value, "resolution": resolution.value},
    )
    return payment


async def refund(
    session: AsyncSession, *, payment: Payment, actor: User, reason: str
) -> Payment:
    """يعيد دفعةً مرّ مالها بالمنصة إلى حيث خرج (SPEC القسم 6/6.4).

    **الردُّ يعود من حيث جاء المال، لا إلى المحفظة دائماً:**

    - المحفظة: قيد `refund` بكامل المبلغ في محفظة الراكب.
    - البطاقة: ردٌّ **عند المزود** إلى نفس البطاقة (`card_payments`)، فلا قيد
      للراكب في الدفتر — مالُه لم يدخل رصيده أصلاً، فردُّه إليه رصيداً يمنحه
      مرتين. هذا ما تعنيه «الاسترداد عبر المزود» في المرحلة 6-ب.

    وفي الحالتين `adjustment` مضاد على الكبتن بصافي ما قُيّد له (المبلغ −
    العمولة): الدفتر لا يُعدَّل ولا يُحذف منه، فالردُّ قيدٌ جديد (القسم 4).

    الكاش وكليك خارج هذا الباب: مالهما لم يدخل المنصة أصلاً فلا تملك ردّه.
    """
    if payment.method not in REFUNDABLE_METHODS:
        raise InvalidPaymentTransition(
            "الكاش وكليك يقبضهما الكبتن مباشرة — لا استرداد لهما من المنصة"
        )
    require_transition(payment, PaymentStatus.REFUNDED)
    if not reason.strip():
        raise InvalidInput("سبب الاسترداد مطلوب")

    ride = await _ride_of(session, payment)
    rider = await session.get(User, ride.rider_id)

    if payment.method in WALLET_FUNDED_METHODS:
        await wallet.record(
            session,
            owner=rider,
            tx_type=WalletTransactionType.REFUND,
            amount=payment.amount,
            ride_id=ride.id,
            reference=reason.strip(),
            created_by=actor.id,
            idempotency_key=f"refund:{payment.id}",
        )
    else:
        # ردُّ المزود أولاً: لو رفضه ارتدّ الطلب كله ولم تُوسم الدفعة مردودةً
        # ولم يُخصم من الكبتن — صفٌّ يقول «مردود» ومالٌ لم يُردّ أسوأ من فشلٍ
        from app.services import card_payments

        await card_payments.refund_via_provider(
            session, payment=payment, reason=reason.strip()
        )

    driver_user = await _driver_user(session, ride)
    if driver_user is not None:
        percent = await _commission_for(session, ride, payment.method)
        net = round_money(payment.amount - payment.amount * percent / 100)
        if net > 0:
            await wallet.record(
                session,
                owner=driver_user,
                tx_type=WalletTransactionType.ADJUSTMENT,
                amount=-net,
                ride_id=ride.id,
                reference=f"استرداد دفعة: {reason.strip()}",
                created_by=actor.id,
                idempotency_key=f"refund-earning:{payment.id}",
            )

    payment.status = PaymentStatus.REFUNDED
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="payment",
        entity_id=payment.id,
        details={"status": payment.status.value},
    )
    return payment
