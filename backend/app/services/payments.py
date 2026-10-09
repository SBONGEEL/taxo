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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.currency import currency_for_country
from app.core.exceptions import (
    Conflict,
    FeatureDisabled,
    InsufficientBalance,
    InvalidInput,
    InvalidPaymentTransition,
    NotFound,
    PayerMethodMismatch,
    PermissionDenied,
    RideAlreadyPaid,
    RideNotPayable,
)
from app.models.commission import CommissionSetting
from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    CommissionAppliesTo,
    CountryCode,
    DisputeResolution,
    DriverDebtSource,
    FeatureKey,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentStatus,
    RidePayer,
    RideStatus,
    UserRole,
    WalletOwnerType,
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
from app.models.wallet import WalletTransaction
from app.services import (
    admin_search,
    advances,
    audit,
    cancellation,
    cliq_qr,
    debts,
    settings_service,
    wallet,
)
from app.services import rounding as rounding_service
from app.services.pricing import round_money

# آلة حالات الدفعة — ما ليس هنا ممنوع (SPEC القسم 4)
ALLOWED_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset(
        {
            PaymentStatus.CONFIRMED,
            PaymentStatus.FAILED,
            PaymentStatus.DISPUTED,
            # **«غيّر طريقة الدفع»** (`design/PAYMENTS-UNCONFIRMED.md` §٢-١، SPEC §٦٤-ج):
            # من المعلَّقة وحدَها — ما أقرّ به الراكبُ أو أكّده الكبتنُ لا يُبدَّل
            PaymentStatus.VOIDED,
        }
    ),
    # مخرجا النزاع حكمان: وصل المال أو لم يصل — **وثالثٌ للراكب وحدَه**: «سأدفع الآن» على نزاع كاش
    # (`design/PAYMENTS-UNCONFIRMED.md` §٢-٣/§٦، SPEC §٦٤-ج) يُلغي المتنازَعَ عليه ويفتح ما يدفع به في معاملةٍ واحدة
    # (`unconfirmed_payments.change_method`) — **لا حكمٌ يُكتب ولا قيد**، فالنزاعُ يسقط لأن المالَ يُدفع لا لأن أحداً حكم
    PaymentStatus.DISPUTED: frozenset(
        {PaymentStatus.CONFIRMED, PaymentStatus.FAILED, PaymentStatus.VOIDED}
    ),
    PaymentStatus.CONFIRMED: frozenset({PaymentStatus.REFUNDED}),
    PaymentStatus.FAILED: frozenset(),
    PaymentStatus.REFUNDED: frozenset(),
    # **نهائيّةٌ كـ`failed`**: الدفعةُ التي تحلّ محلَّها صفٌّ جديدٌ من `pay_ride`
    PaymentStatus.VOIDED: frozenset(),
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

#: **أقلُّ طول سببٍ لحكم المشرف** (`design/PAYMENTS-UNCONFIRMED.md` §٥: «٨ أحرف على الأقل») — **يُفرض حين يشتعل §٦٤-ج
#: في السوق** على بابَي الحكم كليهما (`resolve_dispute`)، ومطفأً يبقى البابُ القديمُ كما كان (`note` اختياريّ)
MIN_RULING_REASON_LENGTH = 8


def _now() -> datetime:
    return datetime.now(UTC)


def is_staff(user: User) -> bool:
    """من يقرأ سجلات غيره بحكم دوره (SPEC القسم 13.8)."""
    return user.has_role(*STAFF_ROLES)


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
    country_code: CountryCode | None = None,
    limit: int,
    offset: int,
    q: str | None = None,
) -> Sequence[Payment]:
    """قائمة اللوحة — الفلترة على `disputed` هي شاشة النزاعات (القسم 13.4).

    والدولةُ تُقرأ من الرحلة: لا عمودَ دولةٍ على `payments` لأن الدفعة تتبع
    رحلتها، فالضمُّ هنا لا عمودٌ مكرَّر هناك.

    **وطرفا الرحلة يُحمَّلان معها** (§٤٧٫١٩، 2026-09-04): صفُّ اللوحة صار
    يحمل الراكبَ والكبتنَ ليُفتح ملفُّهما، **وقراءةٌ كسولةٌ بعد خروج الجلسة
    تقع خارج السياق** — `MissingGreenlet` بعينه، وهو فخُّ هذا المشروع
    المعروف. **و`selectinload` لا `join`** كي لا تتكرّر الصفوف فتصير صفحةُ
    الخمسين أقلَّ من خمسين — وهو قرارُ `ride_log` نفسُه.
    """
    stmt = (
        select(Payment)
        .options(
            selectinload(Payment.ride).selectinload(Ride.rider),
            selectinload(Payment.ride)
            .selectinload(Ride.driver)
            .selectinload(Driver.user),
        )
        .order_by(Payment.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(Payment.status == status)
    if country_code is not None:
        stmt = stmt.join(Ride, Payment.ride_id == Ride.id).where(
            Ride.country_code == country_code
        )
    # **مرشِّحٌ فقط** (`services/admin_search.py`): من دفع — راكبُ الرحلة أو
    # كبتنُها. **وبـ`EXISTS` لا بضمّ** كي لا يتغيّر ما تحويه الصفحةُ الواحدة.
    #
    # **و`ride_parties_clause` لا `any_user_clause`** (عطبٌ قِيس 2026-09-02):
    # `rides.driver_id` عمودُ `drivers.id` لا `users.id`، **فالشرطُ الأولُ كان
    # لا يطابق كبتناً أبداً** — من بحث عن دفعاتِ كبتنٍ باسمه قرأ «لا نتائج»
    # وهو «لا يبحث»
    term = admin_search.normalize(q)
    if term is not None:
        stmt = stmt.where(
            select(Ride.id)
            .where(
                Ride.id == Payment.ride_id,
                admin_search.ride_parties_clause(
                    term, Ride.rider_id, Ride.driver_id
                ),
            )
            .exists()
        )
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
    cliq_alias: str | None = None,
) -> Payment:
    return Payment(
        ride_id=ride.id,
        method=method,
        amount=amount,
        # العملة من دولة الرحلة لا من العميل (SPEC القسم 4)
        currency=currency_for_country(ride.country_code),
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
        cliq_alias=cliq_alias,
        # المرجع الداخلي يولَد مع الدفعة لا عند عرض الشاشة: هو ما يُطبع في
        # الرمز وما يكتبه الراكب في حوالته، فلو تولّد عند كل عرضٍ لحمل الرمزُ
        # مرجعاً والحوالةُ آخر (SPEC القسم 6). عشوائيته تجعل التصادم على القيد
        # الفريد أبعد من أن يُبرمَج له مسار
        cliq_reference=cliq_qr.new_reference() if method == PaymentMethod.CLIQ else None,
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
    _require_payer_method(ride, method)

    # **قناةُ الكاش المطفأةُ لهذا الراكب تُطفأ هنا لا في الطلب وحدَه** (`design/PAYMENTS-UNCONFIRMED.md` §٧، SPEC §٦٤-ج):
    # «حكمان بـ"لم يدفع" في ٩٠ يوماً ⇒ محفظة/بطاقة/كليك فقط». **وهذا البابُ هو ما يفتح الكاش فعلاً** — فحصُ الطريقة المرسلة
    # مع الطلب وحدَه يتركها مفتوحةً لمن لم يرسل طريقةً (تطبيقٌ قديم) أو أرسل غيرَها ثمّ دفع نقداً. **وباقي المحفظة كاشٌ
    # كذلك** (`_pay_from_wallet`)، فلا يُفتح باقٍ نقديٌّ لمن أُطفئ له. ومطفأً المفتاحُ لا يُسأل شيء (`cash_allowed`)
    from app.services import unconfirmed_payments

    if method == PaymentMethod.CASH:
        await unconfirmed_payments.require_cash_allowed(session, rider)

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
            # **رحلةٌ لغيره يدفعها هو لا يبقى منها نقد** (§٦٣-ج/١): الطالبُ ليس عند السيارة ليدفع الباقي.
            # **ولا لمن أُطفئ له الكاش** (§٧ أعلاه): رصيدٌ لا يغطّي يُردّ بـ«اشحن أو ادفع بالبطاقة» لا بباقٍ نقديّ
            cash_remainder=not ride.for_other
            and await unconfirmed_payments.cash_allowed(session, rider),
        )
    else:
        alias = (
            await _require_cliq_alias(session, ride)
            if method == PaymentMethod.CLIQ
            else None
        )
        payments = [
            _new_payment(
                ride,
                method=method,
                amount=outstanding,
                idempotency_key=idempotency_key,
                cliq_alias=alias,
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


def _require_payer_method(ride: Ride, method: PaymentMethod) -> None:
    """قناةُ الدفع تتبع من اختار الطالبُ أن يدفع (§٦٣-ج/١) — **ورحلةٌ يركبها صاحبُها لا يمسّها شيء**.

    `passenger_cash`: الراكبُ الفعليُّ يدفع نقداً، **ودفعتُه تُفتح عند الإنهاء** (`open_payer_cash`) — فلا قناةَ يختارها
    الطالب، وما بعد سقوطها (رفضُ الدفع) سؤالٌ للمالك (§٦٣-د/٥) **لا يُنشأ قيدُه قبل جوابه**. و`requester`: الطالبُ يدفع
    بالمحفظة أو البطاقة — **لا نقدَ ولا كليك**: ليس عند السيارة ولا يحوّل إلى الكبتن من بعيد.
    """
    # **والطرد** (§٦٣-ج/٤): المستلمُ نقداً ⇒ دفعتُه يفتحها الإنهاء؛ والمرسلُ عند الالتقاط ⇒ أيُّ قناة
    if ride.payer == RidePayer.RECIPIENT_CASH:
        raise PayerMethodMismatch("يدفع هذا الطردَ مستلمُه نقداً للكبتن")
    if not ride.for_other:
        return
    if ride.payer == RidePayer.PASSENGER_CASH:
        raise PayerMethodMismatch("يدفع هذه الرحلةَ راكبُها نقداً للكبتن")
    if method not in (PaymentMethod.WALLET, PaymentMethod.CARD):
        raise PayerMethodMismatch("اخترتَ أن تدفع أنت — بالمحفظة أو البطاقة")


async def open_payer_cash(session: AsyncSession, ride: Ride) -> Payment | None:
    """دفعةُ نقد الراكب الفعليّ — **يفتحها الإنهاءُ لا الراكب** (§٦٣-ج/١).

    اختار الطالبُ أن يدفع الراكبُ نقداً، وصاحبُ الدفعة لا يحمل التطبيق ليفتحها — فتُفتح **بما بقي بعد الخصمين** كما لو
    اختارها هو في شاشة الدفع، **ويؤكّدها الكبتنُ بمساره القائم** (`confirm_by_driver`) فتقع العمولةُ ديناً كسائر النقد.
    **وليست قيداً من تخمين**: قناةٌ اختارها الطالبُ صراحةً، ومبلغٌ هو الباقي حرفاً.

    يُنادى من `rides.complete_ride` وصفُّ الرحلة مقفول — فالترتيبُ رحلةٌ ثمّ دفعة كما في `CLAUDE.md`، **والمفتاحُ
    على الرحلة** فإنهاءٌ يُعاد لا يفتح دفعتين.
    """
    outstanding = await outstanding_amount(session, ride)
    if outstanding <= 0:
        return None
    payment = _new_payment(
        ride,
        method=PaymentMethod.CASH,
        amount=outstanding,
        idempotency_key=f"payer-cash:{ride.id}",
    )
    session.add(payment)
    await session.flush()
    return payment


async def _find_by_idempotency_key(
    session: AsyncSession, key: str
) -> Payment | None:
    return await session.scalar(
        select(Payment).where(Payment.idempotency_key == key)
    )


async def _require_cliq_alias(session: AsyncSession, ride: Ride) -> str:
    """كليك تحويلٌ على alias الكبتن (القسم 6.2) — فبلا alias لا وجهة للمال.

    يعيد الـ alias ليُجمَّد على الدفعة: تغييرُ الكبتن aliasه غداً لا يجوز أن
    يغيّر ما تقوله دفعةُ اليوم عن وجهة الحوالة (المرحلة 9).
    """
    alias = await session.scalar(
        select(Driver.cliq_alias).where(Driver.id == ride.driver_id)
    )
    cleaned = (alias or "").strip()
    if not cleaned:
        raise InvalidInput("لم يضف الكبتن alias كليك — اختر قناة أخرى")
    return cleaned


async def _pay_from_wallet(
    session: AsyncSession,
    *,
    ride: Ride,
    rider: User,
    outstanding: Decimal,
    idempotency_key: str,
    cash_remainder: bool = True,
) -> list[Payment]:
    """خصمٌ فوري من رصيد الراكب، وما عجز عنه الرصيد يبقى كاشاً (القسم 6).

    المفتاح على صف المحفظة وحده حين ينقسم الدفع: البحث بالمفتاح يعيد دفعات
    الرحلة كلها، فالصف الثاني لا يحتاج مفتاحاً خاصاً به.
    """
    wallet.require_not_frozen(rider, WalletOwnerType.RIDER)

    # القفل قبل قراءة الرصيد: رصيدٌ يُقرأ ثم يُخصم منه لاحقاً رصيدٌ قديم
    await wallet.lock_wallet(session, rider.id)
    # **تُعلَن كما يعلنها القيدُ الذي يليها** (`confirm`: `owner_type=RIDER`) —
    # كانت بلا إعلان فأصابت ذا الدور الواحد بالصدفة، وردّت حاملَ الدورين ٤٠٩
    # `wallet_owner_undecided` والسياقُ يعرف الجواب: أجرةُ رحلته يدفعها راكباً
    # (عطبُ رحلاتٍ قائمٌ منذ `7bea224`، `SPEC-DELIVERY.md` §D6)
    balance = await wallet.balance_of(session, rider, declared=WalletOwnerType.RIDER)
    if balance <= 0:
        raise InsufficientBalance("لا رصيد في محفظتك — اختر قناة أخرى")

    if not cash_remainder and balance < outstanding:
        raise InsufficientBalance("رصيدُك لا يغطّي الأجرة — اشحن محفظتك أو ادفع بالبطاقة")

    # **رصيدٌ لا يغطّي الأجرةَ يدفع أكبرَ مضاعفٍ للوحدة لا يتجاوزه** (SPEC §٧٠-ج/٤) — **فالباقي نقداً مضاعفٌ أيضاً**، والكسرُ
    # القديمُ يبقى في المحفظة لصاحبه كما هو. ومطفأً `floor_to_unit` هويّةٌ: `min(الرصيد، الأجرة)` حرفاً كما كان
    if balance >= outstanding:
        wallet_amount = outstanding
    else:
        wallet_amount = rounding_service.floor_to_unit(
            balance, await rounding_service.policy_for(session, ride.country_code)
        )
    if wallet_amount <= 0:
        raise InsufficientBalance("رصيدُك أقلُّ من أصغر مبلغٍ يُدفع في بلدك — اختر قناة أخرى")
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


async def _driver_row(session: AsyncSession, ride: Ride) -> Driver:
    """صفُّ الكبتن نفسُه — يحتاجه اقتطاعُ السلفة ليطفئ إيقافَه لحظةَ السداد."""
    driver = await session.get(Driver, ride.driver_id)
    assert driver is not None  # لا تُسوّى رحلةٌ بلا كبتن
    return driver


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


#: **قناتا الخصم** — ما تتحمّله المنصّةُ عن الراكب (القسيمةُ والمشاركة). **لا `PLATFORM_WRITTEN_METHODS` كلُّها**: المشوارُ الثابت
#: فيها لأن المنصّةَ تكتبه، **لكنه مالُ الراكب نفسِه مدفوعاً مقدّماً** — فوعاءُ عمولته وعاءُ ما يدفعه الراكب لا وعاءُ خصم
DISCOUNT_METHODS: tuple[PaymentMethod, ...] = (PaymentMethod.PROMO, PaymentMethod.SHARE)


@dataclass(frozen=True, slots=True)
class _PricedShares:
    """**ما يحتاجه وعاءُ العمولة من الرحلة كلِّها** حين يقع فيها تقريب (SPEC §٧٠-ج/٤ و/٧، مراجعةُ المال البند ٣).

    - `difference`: **فرقُ التقريب داخل `final_fare`** (`D`) — فرقُ الرحلة من السجلّ، **أو فرقُ سعر المشوار الثابت للرحلة
      الواحدة** (سعرُها المقرَّب ناقصَ الدقيق، من صفِّ الشهر في السجلّ). فالأجرةُ المسعَّرة `F = final − D`.
    - `discounts`: **صفّا الخصم القائمان** (`P` — القسيمةُ والمشاركة)، على الأجرة الدقيقة.
    """

    difference: Decimal
    discounts: Decimal


async def _priced_shares(session: AsyncSession, ride: Ride) -> _PricedShares:
    from app.services import commute

    if ride.commute_id is not None:
        difference = await commute.ride_price_difference(session, ride)
    else:
        difference = await rounding_service.ride_difference(session, ride.id)
    discounts = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.ride_id == ride.id,
            Payment.status.in_(OWING_PAYMENT_STATUSES),
            Payment.method.in_(DISCOUNT_METHODS),
        )
    )
    return _PricedShares(difference=difference, discounts=round_money(Decimal(discounts or 0)))


def _commission_amount(
    ride: Ride, payment: Payment, percent: Decimal, shares: _PricedShares
) -> Decimal:
    """عمولةُ دفعةٍ **على حصّتها من الأجرة المسعَّرة دون رسوم الكبتن** (§٦٣-ب: «للكبتن» = كاملاً بلا عمولة؛ §٧٠-ج/٤: «العمولةُ
    على الأجرة المسعَّرة بلا سطر التقريب — بدقّتها كما اليوم»).

    **بلا فرقٍ في الرحلة — الفرعُ الذي كان حرفاً**: الرسمُ داخل `final_fare` فيُحصَّل بقناة الأجرة نفسِها، **وكلُّ دفعةٍ تحمل منه
    حصّتَها** — الوعاءُ `الدفعة × (الأجرة − الرسم) / الأجرة`، **وبلا رسمٍ `الدفعة` حرفاً**. وقبل الأجرة (مقدَّمُ الساعة عند البدء
    والتقريبُ مطفأٌ عليها) الدفعةُ كلُّها.

    **ومع فرق** (`F = final − D` المسعَّرة، `P` الخصمان):

    - **صفُّ الخصم وعاؤه كاليوم**: `الدفعة × (F − الرسم) / F` — مبلغُه على الدقيقة أصلاً، **فعمولتُه لا تتغيّر بتقريبٍ وقع بعده**
      (كان التوزيعُ الموحَّد يحمّله من الفرق: `0.095` بدل `0.097` في المثال (ب)، **وعمولةُ رحلةٍ عمولتُها على غير النقد ودفعها
      الراكبُ نقداً هبطت من `0.097` إلى `0.095`** على قسيمةٍ لم يتغيّر مبلغُها).
    - **وما يدفعه الراكبُ يحمل الفرقَ كلَّه خارج وعائه**: `الدفعة × (F − الرسم) / F × (F − P) / (final − P)` — حصّتُه من الدقيقة
      الباقية على الراكب بنسبة ما دفع، **فمجموعُ أوعية صفوفه = ما على الراكب بدقّته**. المثال (ب): `4.000 × 3.896 / 4.000 = 3.896`
      ⇐ `0.390`، والقسيمةُ `0.097` — **`0.487` = عمولةُ `4.870` حرفاً، وصفّاً صفّاً كاليوم**. **ومقدَّمُ الساعة صفُّ راكبٍ كغيره**:
      عمولتُه تُؤجَّل إلى الإنهاء حين يُقرَّب (`settle_deferred_commission`)، فتُحسب بهذه الصيغة نفسِها.
    - **والمشوارُ الثابتُ صفُّ راكب** (مالُه مدفوعاً مقدّماً): `7.000 × 7.200 / 7.000 = 7.200` — العمولةُ على السعر المسعَّر.
    """
    amount = payment.amount
    if ride.final_fare is None or shares.difference == 0 or ride.final_fare - shares.difference <= 0:
        if ride.captain_fees_at_ride > 0 and ride.final_fare:
            base = amount * (ride.final_fare - ride.captain_fees_at_ride) / ride.final_fare
        else:
            base = amount
    else:
        priced = ride.final_fare - shares.difference
        fee_share = (priced - ride.captain_fees_at_ride) / priced
        if payment.method in DISCOUNT_METHODS:
            base = amount * fee_share
        else:
            paid = ride.final_fare - shares.discounts
            precise = priced - shares.discounts
            base = amount * fee_share * precise / paid if paid > 0 else amount * fee_share
    return round_money(base * percent / 100)


def _commission_waits_for_fare(ride: Ride, payment: Payment) -> bool:
    """**عمولةُ مقدَّم الساعة تنتظر الأجرةَ حين يُقرَّب** (مراجعةُ المال البند ١) — يُسوّى المقدَّمُ عند البدء ولا أجرةَ بعد، **فعمولتُه
    لو حُسبت الآن حُسبت على المقرَّب المدفوع** (`8.000` لا `7.875`)، **ولا يُعرف بعدُ ما سيُقرَّب منه الباقي** (زيادةٌ تُقرَّب إلى صفرٍ
    تبقى بلا صفٍّ يحمل عمولتَها). فتُكتب عند الإنهاء بالصيغة نفسِها التي تُكتب بها كلُّ دفعة (`settle_deferred_commission`).

    **ومطفأً لا تنتظر** — تُكتب عند البدء على المبلغ كلِّه كما كانت حرفاً. والسياسةُ هي المجمَّدةُ عند البدء (`hourly.prepay_on_start`).
    """
    from app.services import hourly

    return (
        ride.final_fare is None
        and payment.idempotency_key == hourly.prepay_key(ride.id)
        and rounding_service.frozen_policy(ride).enabled
    )


async def _written_commission(session: AsyncSession, payment: Payment) -> Decimal:
    """**العمولةُ التي كُتبت فعلاً لهذه الدفعة عند تسويتها** — قيدُها في الدفتر (`commission:{id}`)، أو دَينُها حين لم يغطّها
    الرصيد (`driver_debts`)، أو صفرٌ حين لم تُكتب عمولة.

    **يقرؤها الاستردادُ ولا يعيد حسابَها** (مراجعةُ المال البند ١): ما يتغيّر بين التسوية والردّ — أجرةٌ نهائيّةٌ لم تكن عند تسوية
    مقدَّم الساعة، وفرقُ تقريبٍ كُتب بعده، ودفعةٌ رُدّت قبلها فخرجت من الصفوف القائمة، ونطاقُ عمولةٍ بدّله المشرف — **يجعل الحسابَ
    الثاني غيرَ الأول**، والفرقُ فلسٌ يبقى على الكبتن أو له بلا سطرٍ يقوله.
    """
    entry = await session.scalar(
        select(WalletTransaction.amount).where(
            WalletTransaction.idempotency_key == f"commission:{payment.id}",
            WalletTransaction.type == WalletTransactionType.COMMISSION,
        )
    )
    if entry is not None:
        return -entry
    debt = await session.scalar(
        select(DriverDebt.amount).where(
            DriverDebt.payment_id == payment.id,
            DriverDebt.source == DriverDebtSource.RIDE_COMMISSION,
        )
    )
    return debt if debt is not None else Decimal("0.000")


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
            # **الراكبُ يدفع أجرةَ رحلته من محفظته هو** — ومحفظةُ الكبتن
            # تحمل أرباحاً تخضع للسلَف والعمولة، فالخلطُ يخصم أجرةً من أرباح
            owner_type=WalletOwnerType.RIDER,
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

    await _distribute(
        session,
        payment=payment,
        ride=ride,
        driver_user=driver_user,
        actor_id=actor_id,
    )

    # **وآخرَ ما يقع: دَينُ إلغاءٍ سابق** (`CANCELLATION-FEE.md` §5 و§6-و).
    # موضعُه **بعد** الأجرة والعمولة كلِّها هو نصُّ الفرع (و): «العمولةُ أولاً —
    # حقُّ المنصّة على رحلةٍ وقعت، والدَّينُ يبقى مطلوباً»، وبالقياس نفسِه أجرةُ
    # كبتنِ اليوم قبل دَينِ الأمس. **ولا يُفشل التسويةَ أبداً**: رصيدٌ لا يكفي
    # يعني ديناً يبقى في جدوله، لا دفعةً تُرفض (قاعدةُ اقتطاع السلفة نفسُها)
    await cancellation.collect_with_ride(
        session, ride=ride, rider=rider, method=payment.method
    )


async def _distribute(
    session: AsyncSession,
    *,
    payment: Payment,
    ride: Ride,
    driver_user: User,
    actor_id: uuid.UUID | None,
) -> None:
    """نصيبُ الكبتن وعمولتُه — نصفُ `settle` الذي يخصّ **أجرة هذه الرحلة**.

    وفُصل عنها كي يبقى ما بعده (دَينُ إلغاءٍ سابق) واقعاً على كل حال: كان
    الخروجُ المبكّر عند «لا عمولة» يتخطّى ما يليه، وهو الشكلُ الذي يجعل قاعدةً
    تعمل في نصف الحالات بلا أن يفشل شيء.
    """
    if payment.method not in DIRECTLY_COLLECTED_METHODS:
        await wallet.record(
            session,
            owner=driver_user,
            # **أجرُ الرحلة يدخل محفظةَ الكبتن** — وهي التي يُسحب منها
            owner_type=WalletOwnerType.DRIVER,
            tx_type=WalletTransactionType.RIDE_EARNING,
            amount=payment.amount,
            ride_id=ride.id,
            created_by=actor_id,
            idempotency_key=f"earning:{payment.id}",
        )

        # **الدَّينُ أوّلاً ثم السلفة** (قرارُ المالك 2026-08-30): «رصيدٌ يكبر
        # ودَينٌ قائمٌ يريه مالاً لا يملكه». **والترتيبُ ليس ذوقاً**: السلفةُ
        # مالٌ أعطيناه، والدَّينُ مالٌ **يحمله عنّا** — فمن يقبض أجرةً نقداً
        # فيها عمولتُنا قابضٌ لا مَدين، وحقُّنا أسبقُ من قسط قرضٍ منحناه.
        await debts.collect_from_balance(
            session, driver=await _driver_row(session, ride), user=driver_user
        )

        # **اقتطاعُ السلفة** (البند ١٥): خصمٌ من أرباحٍ **داخلة** — وموضعُه هنا
        # داخل الشرط لا خارجه، لأن الكاشَ وكليكاً لا يكتبان `ride_earning`
        # أصلاً (القسم 9): المالُ في يده لا في محفظته، فلا شيءَ يُقتطع منه.
        # ولا يُفشل هذا التسويةَ أبداً — الدَّينُ يبقى في جدوله
        await advances.deduct_from_earning(
            session,
            driver=await _driver_row(session, ride),
            user=driver_user,
            country=ride.country_code,
            earning=payment.amount,
            ride_id=ride.id,
            payment_id=payment.id,
        )

    percent = await _commission_for(session, ride, payment.method)
    if percent <= 0:
        return
    # **مقدَّمُ الساعة والتقريبُ مشتعلٌ عليها: عمولتُه عند الإنهاء** (`_commission_waits_for_fare`) — والأجرُ قُيِّد أعلاه كما كان
    if _commission_waits_for_fare(ride, payment):
        return

    commission = _commission_amount(ride, payment, percent, await _priced_shares(session, ride))
    await _charge_commission(
        session, ride=ride, payment=payment, driver_user=driver_user, actor_id=actor_id, commission=commission
    )


async def _charge_commission(
    session: AsyncSession,
    *,
    ride: Ride,
    payment: Payment,
    driver_user: User,
    actor_id: uuid.UUID | None,
    commission: Decimal,
) -> None:
    """**يكتب عمولةَ دفعةٍ واحدة** — قيداً من محفظة الكبتن، أو دَيناً حين قبض بيده أو لم يغطّها رصيدُه. بابُ `_distribute` وبابُ
    العمولة المؤجَّلة (`settle_deferred_commission`) معاً، فلا يفترق ما يُكتب بينهما."""
    if commission <= 0:
        return

    driver_row = await _driver_row(session, ride)

    # ## **العمولةُ التي لا يغطّيها رصيدٌ تصير دَيناً، ولا تُسقط الرحلة**
    #
    # **العطبُ الذي أغلق هذا الباب** (قِيس 2026-08-30): كان هنا `raise
    # InsufficientBalance("… اشحن المحفظة ثم أكّد")` — **وبابُ شحن محفظة
    # الكبتن أُلغي** (قرارُ المالك 2026-08-29)، فصارت الجملةُ تدلّ على ما ليس
    # هناك، **وكبتنٌ رصيدُه دون العمولة لا يُنهي رحلةَ كاشٍ أصلاً**.
    #
    # **والحارسُ لم يُرخَ**: `balance_after < 0` يبقى مرفوضاً في `wallet`.
    # المستحقُّ يخرج من الدفتر إلى **جدولِه** — كالسلفةِ ورسمِ الإلغاء قبله.
    #
    # **وقناةُ اليدِ دَينٌ بطبعها لا استثناءً**: كاشٌ وكليك لا يكتبان
    # `ride_earning` أصلاً، **فالأجرةُ كلُّها في جيبه ومنها عمولتُنا** — فهو
    # يحملها عنّا من اللحظة الأولى، والقيدُ السالبُ كان يصفها وصفاً خاطئاً.
    if payment.method in DIRECTLY_COLLECTED_METHODS:
        await debts.record_from_ride(
            session, driver=driver_row, ride=ride, payment=payment, amount=commission
        )
    else:
        try:
            await wallet.record(
                session,
                owner=driver_user,
                # **العمولةُ تُخصم من محفظة الكبتن** — من حيث دخل الأجر
                owner_type=WalletOwnerType.DRIVER,
                tx_type=WalletTransactionType.COMMISSION,
                amount=-commission,
                ride_id=ride.id,
                created_by=actor_id,
                idempotency_key=f"commission:{payment.id}",
            )
        except InsufficientBalance:
            # **وحتى القناةُ التي تمرّ بنا لا تُسقط رحلة**: اقتطاعُ السلفة
            # يسبق العمولةَ في هذا المسار، فقد لا يُبقي ما يغطّيها — **وقاعدةٌ
            # تعمل في نصف الحالات هي الشكلُ الذي نتجنّبه**.
            await debts.record_from_ride(
                session,
                driver=driver_row,
                ride=ride,
                payment=payment,
                amount=commission,
            )

    # **ويُحصَّل فوراً إن كان الرصيدُ يغطّيه** — فمن كان رصيدُه كافياً يُخصم
    # منه في هذه المعاملة نفسِها كما كان يُخصم قبل اليوم، **ولا يرى فرقاً**.
    # والدَّينُ يبقى لمن لا رصيدَ له، وهو وحدَه من كان يُمنع من إنهاء رحلته.
    await debts.collect_from_balance(session, driver=driver_row, user=driver_user)


async def settle_deferred_commission(session: AsyncSession, ride: Ride) -> None:
    """**عمولةُ مقدَّم الساعة المؤجَّلة تُكتب عند الإنهاء** (مراجعةُ المال البند ١) — بعد أن صارت الأجرةُ وفرقُ تقريبها معلومَين.

    يُنادى من `rides.complete_ride` **وصفُّ الرحلة مقفول**، بعد التقريب وتسوية الخصمين. **ومن يسابقه، وما يحرس كلّاً** (مقيسٌ لا
    مفترض، `test_rounding_paths_concurrency`):

    - **تأكيدُ الكبتن لمقدَّمٍ نقديٍّ معلَّق** — يقرأ `final_fare` بلا قفل الرحلة، فلو قرأه فارغاً (الإنهاءُ لم يُثبَّت) أجّل العمولة،
      **ولو قرأ الإنهاءُ الصفَّ معلَّقاً تخطّاه — فلا تُكتب عمولةٌ أبداً**. **فالصفُّ المعلَّقُ يُقفل هنا** (الرحلةُ ثمّ الدفعة —
      الترتيبُ العامّ) وتُعاد قراءةُ حاله: تأكيدٌ ثُبِّت قبلنا نكتب عمولتَه، وتأكيدٌ ينتظر قفلَنا يجد الأجرةَ بعد التثبيت فيكتبها بنفسه.
      **وبحذف هذا القفل تضيع العمولةُ** (قِيس ٢٠٢٦-١٠-٠٩).
    - **ردُّ مقدَّم المحفظة من اللوحة** — **ولا يُقفل له الصفّ**: قيدُ الردّ يحمل `ride_id`، ففحصُ مفتاحه يطلب `FOR KEY SHARE` على صفِّ
      الرحلة المقفول هنا — فإمّا ينتظر الردُّ تثبيتَنا ثمّ يقرأ العمولةَ المكتوبة ويعكسها، وإمّا ننتظر نحن تثبيتَه فنقرأ الصفَّ مردوداً.
      **وقفلُ الصفِّ له كان يصنع جموداً**: الردُّ يمسك الدفعةَ وينتظر الرحلة، ونحن نمسك الرحلةَ وننتظر الدفعة.

    **وحدُّه مكتوب**: تأكيدُ مقدَّمٍ نقديٍّ في اللحظة نفسِها **وعلى الراكب دَينُ إلغاءٍ يُحصَّل معه** (`collect_with_ride` يكتب قيداً
    بـ`ride_id` وهو ممسكٌ بالدفعة) — جمودٌ يكسره PostgreSQL بإسقاط أحدهما فيُعاد؛ لا مالَ يضيع فيه.

    **وعمولتُه بالصيغة نفسِها التي تُكتب بها كلُّ دفعةٍ بعد الأجرة** (`_commission_amount`): المقدَّمُ صفُّ راكبٍ يحمل حصّتَه من
    الأجرة المسعَّرة — `7.875` لا `8.000`، **وزيادةٌ قُرِّبت إلى صفرٍ تبقى عمولتُها عليه** فلا تضيع. ومطفأً لا شيءَ مؤجَّلٌ أصلاً.
    """
    from app.services import hourly

    if ride.ride_type != "hourly" or not rounding_service.frozen_policy(ride).enabled:
        return
    payment = await session.scalar(select(Payment).where(Payment.idempotency_key == hourly.prepay_key(ride.id)))
    if payment is not None and payment.status is PaymentStatus.PENDING:
        payment = await session.scalar(
            select(Payment)
            .where(Payment.id == payment.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    if payment is None or payment.status is not PaymentStatus.CONFIRMED:
        return
    if await _written_commission(session, payment) > 0:  # pragma: no cover - لا يُكتب مرّتين
        return
    driver_user = await _driver_user(session, ride)
    if driver_user is None:  # pragma: no cover - رحلةٌ مكتملةٌ لها كبتنٌ دائماً
        return
    percent = await _commission_for(session, ride, payment.method)
    if percent <= 0:
        return
    commission = _commission_amount(ride, payment, percent, await _priced_shares(session, ride))
    await _charge_commission(
        session, ride=ride, payment=payment, driver_user=driver_user, actor_id=None, commission=commission
    )


# --------------------------------------------------------- قناة كليك اليدوية


def cliq_charge(payment: Payment) -> cliq_qr.CliqRideCharge | None:
    """ما تعرضه شاشة دفع كليك لهذه الدفعة (SPEC القسم 6.2 — المرحلة 9).

    الرمز يُبنى عند القراءة ولا يُخزَّن: مشتقٌّ بالكامل من المُجمَّد على الصف
    (alias والمبلغ والعملة والمرجع)، وعمودٌ يخزّن مشتقاً عمودٌ يفترق عن أصله
    يوم تُصحَّح صيغة الرمز.
    """
    if payment.method != PaymentMethod.CLIQ or not payment.cliq_reference:
        return None
    return cliq_qr.build_charge(
        alias=payment.cliq_alias or "",
        amount=payment.amount,
        currency=payment.currency,
        reference=payment.cliq_reference,
    )


async def submit_cliq_reference(
    session: AsyncSession, *, payment: Payment, rider: User, reference: str
) -> Payment:
    """«حوّلتُ، وهذا مرجع الحوالة» (SPEC القسم 6.3 — المرحلة 9).

    **يُكتب مرةً واحدة ولا يُعدَّل**: السجل هو كل ما يملكه فاصلُ النزاع في
    قناةٍ لا API يشهد عليها، ومرجعٌ يتبدّل بعد أن رآه الكبتن سجلٌّ لا يُحتج به.
    من أخطأ في الرقم يقول الكبتنُ «لم يصلني» وتفصل الإدارة (القسم 13.4).

    يُستدعى وصفُّ الدفعة مقفول (`get_payment(for_update=True)`): بغير القفل
    تقرأ ضغطتان متزامنتان `cliq_transfer_reference` فارغاً معاً فتمرّان، ويكتب
    آخرُهما فوق مرجعٍ أُعلن للكبتن بالفعل — وهو بالضبط ما يمنعه «يُكتب مرة».
    """
    ride = await _ride_of(session, payment)
    if ride.rider_id != rider.id:
        # 404 لا 403: وجود الدفعة ليس معلومة يستحقها غير صاحبها
        raise NotFound("الدفعة غير موجودة")
    if payment.method != PaymentMethod.CLIQ:
        raise InvalidPaymentTransition("مرجع الحوالة يخص دفعات كليك وحدها")
    if payment.status != PaymentStatus.PENDING:
        raise InvalidPaymentTransition("هذه الدفعة لم تعد بانتظار حوالة")
    if payment.cliq_transfer_reference is not None:
        raise Conflict("مرجع الحوالة مسجَّل على هذه الدفعة ولا يُعدَّل")

    cleaned = reference.strip()
    if not cleaned:
        raise InvalidInput("مرجع الحوالة مطلوب")

    payment.cliq_transfer_reference = cleaned
    payment.cliq_reference_at = _now()
    # المهلةُ تُجمَّد الآن من إعداد الدولة (القسم 6.2/6): بعدها تصير الدفعة
    # نزاعاً بكنسٍ دوري، فيعرف الطرفان أن السكوت لا يُبقي المال معلّقاً أبداً
    settings_row = await settings_service.get_or_create_payment_settings(
        session, ride.country_code
    )
    payment.cliq_confirmation_expires_at = payment.cliq_reference_at + timedelta(
        hours=settings_row.cliq_confirmation_hours
    )
    return payment


# ------------------------------------------------------------ إجراءات الكبتن


async def confirm_by_driver(
    session: AsyncSession, *, payment: Payment, driver: Driver
) -> Payment:
    """«استلمت المبلغ» — الكاش وكليك وحدهما (SPEC القسم 6.1/6.3).

    **ولا يُقال على دفعةٍ صارت نزاعاً.** `ALLOWED_TRANSITIONS` يسمح
    `disputed → confirmed` لأن **فصلَ الإدارة** يمر منه (القسم 13.4)، وليس
    ليعود الكبتن فيسحب نزاعاً بضغطة: تأكيدُه حينها يُقيّد المال ويترك
    `disputed_at` مكتوباً بلا `resolution` ولا `resolved_at` ولا من فصل —
    فيختفي الصفُّ من طابور الإدارة بلا أن يفصل فيه أحد. ومن انقضت مهلته ثم
    وصله المال يفصل له المشرفُ `paid`، فيبقى للقرار أثرٌ يُقرأ.
    """
    ride = await _ride_of(session, payment)
    if ride.driver_id != driver.id:
        raise PermissionDenied("هذه الدفعة ليست على رحلة مُسندة إليك")
    if payment.status is PaymentStatus.DISPUTED:
        raise InvalidPaymentTransition(
            "هذه الدفعة في نزاع — تفصل فيها الإدارة ولا تُؤكَّد من التطبيق"
        )
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


# سببُ النزاع الآلي — نصٌّ ثابتٌ يميّزه فاصلُ النزاع عن نزاعٍ كتبه كبتن
AUTO_DISPUTE_REASON = "انقضت مهلة تأكيد الحوالة دون ردّ الكبتن"


async def expired_cliq_payment_ids(session: AsyncSession) -> list[uuid.UUID]:
    """معرّفاتُ دفعات كليك التي انقضت مهلتها (SPEC القسم 6.2/6).

    قراءةٌ بلا قفل ثم قفلٌ لكل صفٍّ على حدة في `expire_cliq_confirmation`:
    قفلُ الدفعات كلِّها في استعلامٍ واحد يحبس معاملةً طويلةً على صفوفٍ يضغط
    عليها كباتنُها في اللحظة نفسها — والقفلُ يقع حيث يقع التغيير.
    """
    rows = await session.scalars(
        select(Payment.id).where(
            Payment.method == PaymentMethod.CLIQ,
            Payment.status == PaymentStatus.PENDING,
            Payment.cliq_confirmation_expires_at.is_not(None),
            Payment.cliq_confirmation_expires_at <= _now(),
        )
    )
    return list(rows)


async def expire_cliq_confirmation(
    session: AsyncSession, payment_id: uuid.UUID
) -> Payment | None:
    """يحوّل دفعةً انقضت مهلتها إلى `disputed` — أو لا شيء إن سبقه الكبتن.

    **القفلُ قبل الفحص** كما في كل مسارٍ يغيّر حالة: بغيره يقرأ الكنسُ
    `pending` بينما يؤكّد الكبتنُ في المعاملة المجاورة، فتُنازَع دفعةٌ وصل
    مالُها فعلاً. وإعادةُ `None` هنا ليست فشلاً بل الحالُ الصحيحة: الكبتن
    تكلّم قبل المهلة بثانية، وهو ما وُجدت المهلة لتشجيعه عليه.
    """
    payment = await get_payment(session, payment_id, for_update=True)
    if payment.status is not PaymentStatus.PENDING:
        return None
    if payment.method is not PaymentMethod.CLIQ:  # pragma: no cover - يمنعه الاستعلام
        return None
    deadline = payment.cliq_confirmation_expires_at
    if deadline is None or deadline > _now():
        return None

    require_transition(payment, PaymentStatus.DISPUTED)
    payment.status = PaymentStatus.DISPUTED
    payment.dispute_reason = AUTO_DISPUTE_REASON
    payment.disputed_at = _now()
    return payment


async def dispute_by_driver(
    session: AsyncSession, *, payment: Payment, driver: Driver, reason: str
) -> Payment:
    """«لم يصلني» على دفعة كليك (SPEC القسم 6.2) — **و«لم يدفع» على الكاش حين يشتعل §٦٤-ج**.

    كليك: التحويل يقع خارج التطبيق ولا API يشهد عليه، فبين قول الراكب «حوّلت»
    وقول الكبتن «لم يصلني» فراغٌ يملؤه إنسان. والمحفظة يشهد عليها الدفتر.

    **والكاش صار له الفراغُ نفسُه** (`design/PAYMENTS-UNCONFIRMED.md` §٢-٣): كان «يداً بيد فلا فراغ»، **وصفُّ الدفع صار
    يولد مع نهاية الرحلة** قبل أن تلتقي اليدان — فراكبٌ نزل بلا أن يدفع لا مخرجَ لكبتنه إلا «استلمت» أو صمتٌ إلى الأبد
    (§٠/٢). **فـ«لم يدفع» نزاعٌ كنزاع كليك** يذهب إلى الإدارة ولا يكتب شيئاً. **وبمفتاح السوق وحدَه**: مطفأً يبقى الكاشُ كما
    كان بلا نزاع.
    """
    ride = await _ride_of(session, payment)
    if ride.driver_id != driver.id:
        raise PermissionDenied("هذه الدفعة ليست على رحلة مُسندة إليك")
    cash_disputable = (
        payment.method == PaymentMethod.CASH
        and await settings_service.is_feature_enabled(
            session, ride.country_code, FeatureKey.UNCONFIRMED_PAYMENTS_ENABLED
        )
    )
    if payment.method != PaymentMethod.CLIQ and not cash_disputable:
        raise InvalidPaymentTransition("النزاع متاح على دفعات كليك وحدها")
    if not reason.strip():
        raise InvalidInput("سبب النزاع مطلوب")

    require_transition(payment, PaymentStatus.DISPUTED)
    payment.status = PaymentStatus.DISPUTED
    payment.dispute_reason = reason.strip()
    payment.disputed_at = _now()
    return payment


async def ride_of(session: AsyncSession, payment: Payment) -> Ride:
    """رحلةُ الدفعة — يحتاجها الراوترُ ليبثّ للراكب بعد التأكيد."""
    return await _ride_of(session, payment)


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
    allow_pending: bool = False,
    details: dict[str, object] | None = None,
) -> Payment:
    """فصل الإدارة في نزاع (SPEC القسم 6.2/13.4) — **بابُ الحكم الواحد** لبابَي اللوحة كليهما.

    `paid` تعني أن المال وصل الكبتن فعلاً فتُثبَّت الدفعة وتُحسب عمولتها،
    و`unpaid` تعني أنه لم يصل فتسقط الدفعة ويعود مبلغها ديناً على الرحلة —
    يفتح الراكب دفعةً جديدة بقناة أخرى.

    **وطابورُ المعلَّقات يحكم من هنا لا من نسخة** (`design/PAYMENTS-UNCONFIRMED.md` §٥، SPEC §٦٤-ج، مراجعةُ ٢٠٢٦-١٠-٠٧):
    كان له منطقٌ منسوخٌ بقواعدَ أخرى — **فنزاعُ كاشٍ في الطابور يُحكم من البابِ القديم بلا سبب**، وهو شكلُ «بابان ينشران
    الشيءَ نفسَه ويفترقان» (`PATTERNS.md`). فـ`allow_pending` للطابور وحدَه (معلَّقٌ لم يصر نزاعاً — §٥ «احسم»)، و`details`
    ما يضيفه إلى التدقيق (`via`·`action`·`reason`). **والسببُ ≥ ٨ أحرف على البابين حين يشتعل §٦٤-ج في السوق**؛ ومطفأً يبقى
    البابُ القديمُ كما كان حرفاً.
    """
    open_statuses = (
        (PaymentStatus.DISPUTED, PaymentStatus.PENDING)
        if allow_pending
        else (PaymentStatus.DISPUTED,)
    )
    if payment.status not in open_statuses:
        raise InvalidPaymentTransition("لا نزاع قائم على هذه الدفعة")

    ride = await _ride_of(session, payment)
    cleaned = (note or "").strip()
    if len(cleaned) < MIN_RULING_REASON_LENGTH and await settings_service.is_feature_enabled(
        session, ride.country_code, FeatureKey.UNCONFIRMED_PAYMENTS_ENABLED
    ):
        raise InvalidInput(
            f"اكتب سبباً من {MIN_RULING_REASON_LENGTH} أحرف على الأقل", field="note"
        )

    target = (
        PaymentStatus.CONFIRMED
        if resolution == DisputeResolution.PAID
        else PaymentStatus.FAILED
    )
    require_transition(payment, target)

    # **الحكمُ يُختم كاملاً قبل `settle`**: قيدُ `payment_resolution_complete` يُفحص عند كلِّ `flush`، و`settle` يُفرغ في منتصفه
    payment.resolution = resolution
    payment.resolution_note = cleaned[:255] or None
    payment.resolved_by = actor.id
    payment.resolved_at = _now()

    if target == PaymentStatus.CONFIRMED:
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
        details={"status": payment.status.value, "resolution": resolution.value}
        | (details or {}),
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
            # **الردُّ يعود إلى المحفظة التي دُفع منها** — محفظةُ الراكب
            owner_type=WalletOwnerType.RIDER,
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
        # **العمولةُ التي كُتبت عند التسوية تُقرأ ولا يُعاد حسابُها** (مراجعةُ المال البند ١) — فيُعكس ما قُيِّد له حرفاً
        net = round_money(payment.amount - await _written_commission(session, payment))
        if net > 0:
            await wallet.record(
                session,
                owner=driver_user,
                # **عكسُ الأجر يُخصم من حيث قُيّد** — محفظةُ الكبتن
                owner_type=WalletOwnerType.DRIVER,
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
