"""مشاركةُ الرحلة بين ركاب — المرحلة 12-ي (SPEC القسم 5.12).

**الشكلُ (ب): رحلتان في مجموعةٍ واحدة** (قرارُ المالك الأول): كلُّ صفِّ رحلةٍ
يبقى لراكبه بملكيته ودفعته وتقييمه ونزاعه، ويجمعهما `rides.share_group_id`.
فلا قاعدةَ مالٍ تُعاد كتابتُها، ويبقى «من يملك هذه الرحلة» سؤالاً بجوابٍ واحد.

**والخصمُ تتحمّله الشركة** (قرارُ المالك الثالث): صفُّ دفعةٍ بقناة `share`
تُنشئها المنصةُ وتؤكّدها لحظةَ الإنهاء — بآلية 12-ز نفسِها بحرفها. والسببُ ليس
التبسيط: `ride_earning` و`commission` كلاهما يُحسب من `payment.amount` في
`payments.settle`، فخصمٌ يُنقص `final_fare` كان سيُنقص **ما يقبضه الكبتن** من
خصمٍ لم يقرّره — وحينها يرفض المشاركةَ وهو محقّ.

**وقناةُ `share` مستقلةٌ عن `promo`** لأن `promo.spent()` يقيس مصروفَ الكوبون
بجمع دفعات `promo`؛ فخصمُ مشاركةٍ على رحلةٍ تحمل كوبوناً كان سيُستهلك من
**ميزانية الكوبون**.

**والوعدُ يُحترم ولو لم يوجد شريك** (قرارُ المالك الثالث، جواباً على السؤال
الثالث): الرحلةُ تُنفَّذ بالسعر المخصوم وتتحمّل الشركةُ الفرقَ كاملاً. فطالبُ
المشاركة لا يُفاجأ برفعِ سعرٍ وافق عليه، وهو ما يجعل المقعدَ الثاني **زيادةً
محتملة** لا شرطاً للخصم.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.enums import (
    CountryCode,
    FeatureKey,
    GenderPreference,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentStatus,
)
from app.models.payment import Payment
from app.models.ride import SHARE_SEAT_LEAD, Ride
from app.models.sharing import RideSharingSetting
from app.models.user import User
from app.services import pricing
from app.services import settings_service


class SharingUnavailable(AppError):
    """المشاركةُ غيرُ متاحةٍ في هذا السوق — مفتاحٌ مطفأٌ أو نسبةٌ لم تُقرَّر."""

    status_code = 422
    code = "ride_sharing_unavailable"
    message = "مشاركة الرحلة غير متاحة في بلدك الآن"


class SharingNotAllowedForGendered(AppError):
    """طلبٌ بتفضيلٍ نسائيٍّ لا يُشارَك إلا باختيارٍ صريحٍ من صاحبته."""

    status_code = 422
    code = "ride_sharing_gender_choice_required"
    message = "طلبك يحدّد جنس الكبتن — المشاركة فيه اختيارٌ منفصل تختارينه بنفسك"


async def settings_for(
    session: AsyncSession, country: CountryCode
) -> RideSharingSetting | None:
    return await session.scalar(
        select(RideSharingSetting).where(RideSharingSetting.country_code == country)
    )


async def enabled_in(session: AsyncSession, country: CountryCode) -> bool:
    """**شرطان لا شرطٌ واحد**: المفتاحُ مشتعلٌ **ونسبةُ الخصم أكبرُ من صفر**.

    صفرُ النسبة يُقرأ «لم تُقرَّر بعد» كما يُقرأ صفرُ مبلغ البقشيش وصفرُ مكافأة
    الإحالة (12-و و12-ح). ومشاركةٌ بخصمٍ مقدارُه صفرٌ تَعِد الراكبَ بتوفيرٍ ثم
    تعطيه رحلةً منفردةً بسعرها كاملاً ومعها راكبٌ لم يختره — وهو أسوأُ من غياب
    الميزة، لا نصفُها.
    """
    if not await settings_service.is_feature_enabled(
        session, country, FeatureKey.RIDE_SHARING_ENABLED
    ):
        return False
    row = await settings_for(session, country)
    return row is not None and row.discount_percent > 0


async def require_available(session: AsyncSession, country: CountryCode) -> None:
    if not await enabled_in(session, country):
        raise SharingUnavailable()


def guard_gender_choice(
    preference: GenderPreference, *, share_confirmed: bool
) -> None:
    """**القبولُ الصامتُ لا يكفي في مسألة أمان** (قرارُ المالك الرابع).

    شدَّد المالكُ ما اقترحته المواصفة: الاقتراحُ كان «تُشارَك مع راكبةٍ أعلنت
    جنسها»، والقرارُ أضيق — **طلبٌ بتفضيلٍ نسائيٍّ غيرُ قابلٍ للمشاركة افتراضياً،
    حتى مع راكبةٍ أخرى، ولا يصير قابلاً إلا بخيارٍ صريحٍ تختاره الراكبةُ نفسُها**.
    فـ«كانت ستوافق لو سُئلت» ليست موافقة، والافتراضُ في السلامة على الأضيق.

    و**تُرفض ولا تُتجاهَل**: طلبٌ يصل بمشاركةٍ على تفضيلٍ مجنَّسٍ بلا الخيار
    الصريح خطأُ عميلٍ يجب أن يُرى، لا شيءٌ يُصحَّح بصمت — نفسُ قاعدةِ `gender`
    على مسار الكبتن (12-ح).
    """
    if preference is not GenderPreference.ANY and not share_confirmed:
        raise SharingNotAllowedForGendered()


def discount_on(fare: Decimal, percent: Decimal) -> Decimal:
    """قيمةُ الخصم من أجرةٍ ونسبة — **حسابٌ في الخلفية وحدها** (القسم 14)."""
    return pricing.round_money(fare * percent / Decimal("100"))


async def preview(
    session: AsyncSession, *, fare: Decimal, country: CountryCode
) -> tuple[Decimal, Decimal] | None:
    """(الخصم، الأجرة بعده) لعرضه قبل الطلب — أو `None` حيث لا مشاركة.

    **عرضٌ لا التزام**: الأجرةُ النهائيةُ تُحسب على المسافة الفعلية عند الإنهاء،
    والخصمُ يُحسب عليها هي بالنسبة المجمَّدة على الرحلة.
    """
    if not await enabled_in(session, country):
        return None
    row = await settings_for(session, country)
    assert row is not None  # `enabled_in` تحقّق منه
    discount = discount_on(fare, row.discount_percent)
    return discount, pricing.round_money(fare - discount)


async def settle_discount(
    session: AsyncSession, ride: Ride, *, rider: User
) -> Payment | None:
    """يُنشئ دفعةَ `share` ويؤكّدها لحظةَ الإنهاء — أو `None` بلا مشاركة.

    **وتمرّ من `payments.settle` نفسِه** لا من كتابةٍ مستقلة في الدفتر: بابٌ
    واحدٌ لتسوية كل القنوات (قاعدةُ 12-ز).

    **والنسبةُ المجمَّدة هي الحكم** لا ما في الإعدادات الآن: مشرفٌ يعدّل النسبة
    ورحلةٌ سائرةٌ الآن لا يجوز أن يتغيّر خصمُها تحت عين راكبها — نفسُ قاعدةِ
    `commission_percent_at_ride` ورسومِ الانتظار المجمَّدة (12-ب).
    """
    if ride.share_discount_percent_at_ride <= 0 or ride.final_fare is None:
        return None

    discount = discount_on(ride.final_fare, ride.share_discount_percent_at_ride)
    if discount <= 0:  # pragma: no cover - نسبةٌ مجمَّدةٌ تعطي صفراً
        return None

    from app.services import payments as payments_service

    payment = Payment(
        ride_id=ride.id,
        method=PaymentMethod.SHARE,
        amount=discount,
        currency=ride.currency,
        status=PaymentStatus.PENDING,
        # مفتاحٌ مشتقٌّ من الرحلة: إنهاءٌ يُعاد لا يخلق خصمين
        idempotency_key=f"share:{ride.id}",
    )
    session.add(payment)
    await session.flush()

    await payments_service.settle(
        session,
        payment=payment,
        ride=ride,
        rider=rider,
        confirmed_by=PaymentConfirmedBy.SYSTEM,
        actor_id=None,
    )
    return payment


async def group_members(
    session: AsyncSession, group_id: uuid.UUID
) -> list[Ride]:
    """صفوفُ المجموعة بترتيب مقاعدها — والمنفردةُ مجموعةٌ من واحد."""
    rows = await session.scalars(
        select(Ride)
        .where(Ride.share_group_id == group_id)
        .order_by(Ride.share_seat)
    )
    return list(rows)


def is_lead(ride: Ride) -> bool:
    return ride.share_seat == SHARE_SEAT_LEAD
