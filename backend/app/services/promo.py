"""الكوبونات والخصومات (SPEC القسم 6.6، المرحلة 12-ز).

**قرارُ المالك**: تُبنى، بشرطَي أن تسمّي اللوحةُ من يتحمّل الخصم (الشركةُ دائماً
في هذه المرحلة) وأن يكون لكل رمزٍ سقفُ ميزانية.

**والقرارُ المحوريّ أن الخصمَ صفُّ دفعةٍ بقناة `promo` لا نقصٌ في `final_fare`**،
وسببُه في الكود لا في الرأي: `ride_earning` و`commission` كلاهما يُحسب من
`payment.amount` (`services/payments.settle`)، فخصمٌ ينقص ما يدفعه الراكب ينقص ما
يقبضه الكبتن — والمالكُ قرر أن **الشركة** تتحمّله. وبالصفِّ الثاني تتولّى آليةُ
«الدفع المختلط» (القائمة منذ 6-أ) الحسابَ كلَّه:

- `outstanding = final_fare − Σ(الدفعات)` فيصير ما على الراكب الأجرةَ ناقصَ
  الخصم **بلا لمس** `outstanding_amount` ولا `_payable_ride`.
- وأرباحُ الكبتن وعمولتُه تُجمعان من الصفَّين، فصافيه **لا يتغيّر** بوجود
  الكوبون ولا بغيابه. وهذا هو المعنى العمليُّ لـ«الشركة تتحمّله».
- و«الرحلة مجاناً» تعمل بلا حالةٍ خاصة: خصمٌ يغطي الأجرةَ يجعل `outstanding = 0`
  فيرفض `create_payment` من نفسه — بلا بابٍ ثانٍ يكتب المال عند الإنهاء، وذاك
  ما يمنعه القسم 6 («المال يتحرك عند `confirmed` وحدها»).

**والسقفُ يحدّ التطبيقَ الجديد لا رحلةً تحمل رمزاً**: المبلغُ لا يُعرف قبل
الإنهاء، ورفضٌ عنده يحاسب راكباً بسعرٍ غير الذي أظهرته له الشاشة. فالتجاوزُ
ممكنٌ ومحدود (الباقي + أقصى خصمٍ × الرحلات الجارية) ويُعرض في اللوحة كما هو.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, FeatureDisabled
from app.models.enums import (
    CountryCode,
    FeatureKey,
    PaymentMethod,
    PaymentStatus,
    PromoDiscountType,
    RideStatus,
)
from app.models.payment import Payment
from app.models.promo import PromoCode
from app.models.ride import ACTIVE_RIDER_STATUSES, Ride
from app.models.user import User
from app.services import pricing, settings_service

# الرحلاتُ التي تُعدّ استعمالاً للرمز: الجاريةُ والمكتملة. **والجاريةُ منها
# لازمة**: من عدَّ المكتملةَ وحدها فتح البابَ لمن يطلب ثلاث رحلاتٍ في اللحظة
# نفسها بنفس الرمز. والملغاةُ لا تُعدّ — رمزٌ حُجز لرحلةٍ لم تقع يعود لصاحبه
COUNTED_STATUSES: tuple[RideStatus, ...] = (
    *ACTIVE_RIDER_STATUSES,
    RideStatus.COMPLETED,
)


class PromoUnavailable(FeatureDisabled):
    code = "promo_unavailable"
    message = "الكوبونات غير مفعّلة في بلدك"


class PromoInvalid(AppError):
    """رمزٌ لا وجود له أو خارجَ مدّته أو معطَّل.

    **ونصٌّ واحدٌ لكل هذه الحالات**: تفصيلُ «موجودٌ لكنه انتهى» يخبر من يجرّب
    الرموزَ أيُّها كان صحيحاً يوماً، وتلك خريطةٌ لحملاتنا يبنيها بالتجريب.
    """

    status_code = 404
    code = "promo_invalid"
    message = "رمز الخصم غير صالح"


class PromoExhausted(AppError):
    """نفدت ميزانيةُ الحملة أو حدُّ استعمالها.

    404 لا 409 عمداً — ومن نفس السبب: «نفدت» تخبر المُجرِّب أن الرمزَ حقيقي.
    ونصُّها يختلف عن السابق لأن صاحبَ الرمز الحقيقي يستحق أن يعرف أنه فاته لا
    أنه أخطأ الكتابة.
    """

    status_code = 404
    code = "promo_exhausted"
    message = "انتهت صلاحية هذا العرض"


class PromoAlreadyUsed(AppError):
    status_code = 409
    code = "promo_already_used"
    message = "استعملتَ هذا العرض سابقاً"


def _now() -> datetime:
    return datetime.now(UTC)


def normalize(code: str) -> str:
    """بالحروف الكبيرة بلا فراغات — الرمزُ يُقرأ من ملصقٍ ويُكتب بحالاتٍ مختلفة."""
    return (code or "").strip().upper()


# ------------------------------------------------------------- الحساب


def discount_for(
    *,
    discount_type: PromoDiscountType,
    value: Decimal,
    cap: Decimal | None,
    fare: Decimal,
) -> Decimal:
    """مبلغُ الخصم على أجرةٍ معلومة — **دالةٌ خالصةٌ تُختبر وحدها**.

    ولا يزيد الخصمُ على الأجرة أبداً: خصمٌ أكبرُ منها يجعل المدفوعَ سالباً، أي
    ديناً على المنصة لراكبٍ لم يدفع شيئاً.
    """
    if fare <= 0:
        return Decimal("0.000")

    if discount_type is PromoDiscountType.PERCENT:
        amount = fare * value / Decimal("100")
        if cap is not None:
            amount = min(amount, cap)
    else:
        amount = value

    return pricing.round_money(min(amount, fare))


def discount_on_ride(ride: Ride, fare: Decimal) -> Decimal:
    """الخصمُ من **القاعدة المجمَّدة على الرحلة** لا من صفِّ الرمز الحاليّ.

    فتعديلُ الرمز في اللوحة لا يمسّ رحلةً رأى صاحبُها خصمَها — نفسُ منطق
    `commission_percent_at_ride`.
    """
    if ride.promo_code_id is None or ride.promo_type_at_ride is None:
        return Decimal("0.000")
    return discount_for(
        discount_type=ride.promo_type_at_ride,
        value=ride.promo_value_at_ride or Decimal("0"),
        cap=ride.promo_cap_at_ride,
        fare=fare,
    )


# ------------------------------------------------------------- القراءة


async def enabled_in(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(
        session, country, FeatureKey.PROMO_CODES_ENABLED
    )


async def find(
    session: AsyncSession,
    code: str,
    country: CountryCode,
    *,
    for_update: bool = False,
) -> PromoCode | None:
    """رمزٌ صالحُ المدّة ومفعَّل — أو `None`."""
    now = _now()
    stmt = select(PromoCode).where(
        PromoCode.country_code == country,
        PromoCode.code == normalize(code),
        PromoCode.is_active.is_(True),
        or_(PromoCode.valid_from.is_(None), PromoCode.valid_from <= now),
        or_(PromoCode.valid_until.is_(None), PromoCode.valid_until >= now),
    )
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(stmt)


async def spent(session: AsyncSession, promo_id: uuid.UUID) -> Decimal:
    """المصروفُ = مجموعُ دفعات `promo` على رحلات هذا الرمز.

    **ولا عمودَ يراكمه**: قاعدةُ «لا عمود رصيد» نفسُها (القسم 4) — رقمٌ محسوبٌ
    ومراكمٌ في عمودٍ يفترقان يوماً، والفرقُ في المال لا يُكتشف إلا بمطابقة.
    والملغاةُ خارجةٌ تلقائياً: لا دفعةَ `promo` عليها.
    """
    total = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .select_from(Payment)
        .join(Ride, Payment.ride_id == Ride.id)
        .where(
            Ride.promo_code_id == promo_id,
            Payment.method == PaymentMethod.PROMO,
            Payment.status == PaymentStatus.CONFIRMED,
        )
    )
    return pricing.round_money(Decimal(total or 0))


async def usage_count(
    session: AsyncSession, promo_id: uuid.UUID, *, rider_id: uuid.UUID | None = None
) -> int:
    """كم رحلةً حملت هذا الرمز — **الجاريةُ والمكتملة**.

    الجاريةُ محسوبةٌ عمداً: بغيرها يطلب راكبٌ ثلاث رحلاتٍ معاً بنفس الرمز فتمرّ
    كلُّها لأن أياً منها لم تكتمل بعد.
    """
    stmt = (
        select(func.count())
        .select_from(Ride)
        .where(Ride.promo_code_id == promo_id, Ride.status.in_(COUNTED_STATUSES))
    )
    if rider_id is not None:
        stmt = stmt.where(Ride.rider_id == rider_id)
    return int(await session.scalar(stmt) or 0)


async def preview(
    session: AsyncSession,
    *,
    code: str,
    country: CountryCode,
    rider: User,
    fare: Decimal,
) -> tuple[PromoCode, Decimal]:
    """تحقّقٌ **لا يستهلك شيئاً** — لزرِّ «تطبيق» في ورقة التأكيد.

    ويرفع نفسَ أخطاء التطبيق الحقيقي: زرٌّ يقول «مقبول» ثم يرتدّ عند الطلب
    يُعلّم الراكبَ ألّا يثق بالشاشة.
    """
    if not await enabled_in(session, country):
        raise PromoUnavailable()

    promo = await find(session, code, country)
    if promo is None:
        raise PromoInvalid()

    await _check_limits(session, promo, rider, fare=fare)
    return promo, discount_for(
        discount_type=promo.discount_type,
        value=promo.discount_value,
        cap=promo.max_discount,
        fare=fare,
    )


# ------------------------------------------------------------- الحدود


async def committed(session: AsyncSession, promo: PromoCode) -> Decimal:
    """**الالتزامُ** لا المصروفُ وحده: ما دُفع + ما وُعد به ولم يُدفع بعد.

    وهذا هو الفرقُ الذي كشفه اختبارُ التزامن ولم تره المواصفة: `spent` يجمع
    دفعاتِ `promo` **المؤكَّدة**، وهي لا تُنشأ إلا عند الإنهاء. فلو كان السقفُ
    يُقاس بالمصروف وحده لمرّت مئةُ رحلةٍ في ثانيةٍ قبل أن تُنشأ أولُ دفعة —
    وتجاوزت الحملةُ ميزانيتَها مئةَ ضعف، وصار السقفُ الذي شرطه المالك رقماً في
    شاشة لا حارساً.

    فالالتزامُ = دفعاتٌ مؤكَّدة + **خصمُ كل رحلةٍ جاريةٍ تحمل الرمز مقيساً على
    تقديرها**. والتقديرُ لا الأجرةُ النهائية لأنها لا تُعرف قبل الإنهاء؛ وهو
    تقريبٌ في الاتجاه الصحيح: يحجز أكثرَ قليلاً لا أقل.
    """
    total = await spent(session, promo.id)

    rows = await session.execute(
        select(
            Ride.estimated_fare,
            Ride.promo_type_at_ride,
            Ride.promo_value_at_ride,
            Ride.promo_cap_at_ride,
        ).where(
            Ride.promo_code_id == promo.id,
            Ride.status.in_(ACTIVE_RIDER_STATUSES),
        )
    )
    for fare, kind, value, cap in rows:
        if kind is None or fare is None:  # pragma: no cover - صفٌّ نصفُ مكتوب
            continue
        total += discount_for(
            discount_type=kind, value=value or Decimal("0"), cap=cap, fare=fare
        )

    return pricing.round_money(total)


async def _check_limits(
    session: AsyncSession,
    promo: PromoCode,
    rider: User,
    *,
    fare: Decimal | None = None,
) -> None:
    """الحدودُ الثلاثة: ميزانيةٌ، وحدٌّ إجمالي، وحدٌّ لكل مستخدم.

    و`fare` تقديرُ الرحلة التي **ستحمل** الرمز: تدخل الحسابَ قبل أن تُثبَّت،
    فالرحلةُ الأخيرة التي تُخرج الحملةَ عن ميزانيتها تُرفض قبل أن تبدأ لا بعدها.
    """
    exposure = await committed(session, promo)
    if fare is not None:
        exposure += discount_for(
            discount_type=promo.discount_type,
            value=promo.discount_value,
            cap=promo.max_discount,
            fare=fare,
        )
    if exposure > promo.budget_total:
        raise PromoExhausted()

    if promo.total_usage_limit is not None:
        if await usage_count(session, promo.id) >= promo.total_usage_limit:
            raise PromoExhausted()

    mine = await usage_count(session, promo.id, rider_id=rider.id)
    if mine >= promo.per_user_limit:
        raise PromoAlreadyUsed()


# ------------------------------------------------------------- الكتابة


async def apply_to_ride(
    session: AsyncSession, *, ride: Ride, rider: User, code: str
) -> PromoCode:
    """يُجمّد قاعدةَ الرمز على الرحلة — **تحت قفل صفِّ الرمز**.

    والقفلُ هو ما يمنع طلبين متزامنين من تجاوز حدِّ المستخدم أو الميزانية: كلٌّ
    منهما يقرأ العدَّ نفسه ويمرّ. وموضعُه في ترتيب الأقفال **بعد صفِّ الرحلة
    وقبل صفِّ الدفعة** — ولا ترتيبَ ثانٍ يُخترع (`CLAUDE.md`).

    ولا يُكتب مبلغٌ هنا: الأجرةُ النهائية لا تُعرف قبل الإنهاء.
    """
    country = ride.country_code
    if not await enabled_in(session, country):
        raise PromoUnavailable()

    promo = await find(session, code, country, for_update=True)
    if promo is None:
        raise PromoInvalid()

    await _check_limits(session, promo, rider, fare=ride.estimated_fare)

    ride.promo_code_id = promo.id
    ride.promo_type_at_ride = promo.discount_type
    ride.promo_value_at_ride = promo.discount_value
    ride.promo_cap_at_ride = promo.max_discount
    return promo


async def settle_discount(
    session: AsyncSession, ride: Ride, *, rider: User
) -> Payment | None:
    """يُنشئ دفعةَ `promo` ويؤكّدها لحظةَ الإنهاء — أو `None` بلا كوبون.

    **وتمرّ من `payments.settle` نفسِه** لا من كتابةٍ مستقلة في الدفتر: بابٌ
    واحدٌ لتسوية كل القنوات، وقيدٌ يُكتب من مكانٍ ثانٍ هو حالةٌ ثانيةٌ يمكن أن
    تخالف الأولى.

    والقفلُ على صفِّ الرمز يُؤخذ هنا أيضاً — لا لفحصِ سقفٍ (السقفُ فُحص عند
    التطبيق، ورحلةٌ تحمل الرمز تُنهى بخصمها كاملاً) بل ليكون **جمعُ المصروف
    وتسجيلُ الدفعة متسلسلين**: بغيره تقرأ إنهاءاتٌ متزامنة مصروفاً واحداً،
    فيُعرض في اللوحة رقمٌ أقلُّ من الحقيقة بلا أن يخطئ أحد.
    """
    if ride.promo_code_id is None or ride.final_fare is None:
        return None

    discount = discount_on_ride(ride, ride.final_fare)
    if discount <= 0:  # pragma: no cover - قاعدةٌ مجمَّدةٌ بقيمةٍ صفرية
        return None

    # القفلُ على الرمز قبل إنشاء الدفعة — بعد صفِّ الرحلة الذي أقفله `complete`
    await session.execute(
        select(PromoCode.id)
        .where(PromoCode.id == ride.promo_code_id)
        .with_for_update()
    )

    from app.services import payments as payments_service

    payment = Payment(
        ride_id=ride.id,
        method=PaymentMethod.PROMO,
        amount=discount,
        currency=ride.currency,
        status=PaymentStatus.PENDING,
        # مفتاحٌ مشتقٌّ من الرحلة: إنهاءٌ يُعاد لا يخلق خصمين
        idempotency_key=f"promo:{ride.id}",
    )
    session.add(payment)
    await session.flush()

    from app.models.enums import PaymentConfirmedBy

    await payments_service.settle(
        session,
        payment=payment,
        ride=ride,
        rider=rider,
        confirmed_by=PaymentConfirmedBy.SYSTEM,
        actor_id=None,
    )
    return payment
