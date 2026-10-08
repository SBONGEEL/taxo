"""قواعدُ «من ينتظر من» في المدفوعات غير المؤكَّدة — **شروطُ SQL وحدَها، بيتٌ واحدٌ لكلِّ قارئ**.

(`design/PAYMENTS-UNCONFIRMED.md` §٢/§٧، SPEC §٦٤-ج)

**ولمَ ملفٌّ مستقلٌّ خفيف**: يقرؤها التوزيعُ (`dispatch._eligible_levels` — حجبُ العروض عن الكبتن) والطلبُ (منعُ الراكب)
والتذكيراتُ وطابورُ الإدارة وقائمتا التطبيقين. **وشرطٌ يُكتب في كلِّ واحدٍ منها يفترق أوّلَ تعديل** — فكبتنٌ تقول له شاشتُه
«لا يلزمك شيء» والتوزيعُ يحجبه. **ولا يستورد إلا النماذج**، فلا يجرّ التوزيعَ إلى خدمات الدفع.

**ولا عمودَ محضَّرٌ للحجب** (خلافَ `advance_blocked`/`debt_blocked`): التصميمُ يقول «**يُرفع فور الحسم**» (§٧)، وعمودٌ تكتبه
دورةٌ يُرفع بعد الدورة لا فوراً. **فالحكمُ يُشتقّ في استعلام الأهلية نفسِه** — شرطٌ واحدٌ مرتبطٌ بصفِّ الكبتن، بلا استعلامٍ ثانٍ.
"""

from __future__ import annotations

from sqlalchemy import and_, case, exists, false, func, literal_column, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.models.driver import Driver
from app.models.enums import FeatureKey, PaymentMethod, PaymentStatus, RidePayer, RideStatus
from app.models.feature_flag import FeatureFlag
from app.models.payment import OWING_PAYMENT_STATUSES, Payment
from app.models.payment_setting import (
    DEFAULT_DRIVER_UNCONFIRMED_BLOCK_COUNT,
    DEFAULT_DRIVER_UNCONFIRMED_BLOCK_HOURS,
    PaymentSetting,
)
from app.models.ride import Ride
from app.models.user import User

#: **القناتان اللتان تنتظران إنساناً** — المالُ يقع خارج المنصّة فلا يشهد عليه دفترٌ ولا مزوّد (القسم 9)
AWAITED_METHODS: tuple[PaymentMethod, ...] = (PaymentMethod.CASH, PaymentMethod.CLIQ)

#: **صفٌّ حيٌّ على الرحلة** — ينتظر أحداً أو بيد الإدارة. ما عداهما (`confirmed`·`failed`·`refunded`·`voided`) حُسم أو سقط
LIVE_STATUSES: tuple[PaymentStatus, ...] = (PaymentStatus.PENDING, PaymentStatus.DISPUTED)

#: **افتراضا الحجب حين لا صفَّ إعداداتٍ للسوق** — نصُّ §٩، ومصدرُهما النموذجُ نفسُه لا رقمٌ ثانٍ هنا
_DEFAULT_BLOCK_COUNT = DEFAULT_DRIVER_UNCONFIRMED_BLOCK_COUNT
_DEFAULT_BLOCK_HOURS = DEFAULT_DRIVER_UNCONFIRMED_BLOCK_HOURS


def in_flow() -> ColumnElement[bool]:
    """**رحلةٌ دخلت التدفّق** — طُلبت والمفتاحُ مشتعلٌ من تطبيقٍ أرسل طريقتَه (`rides.payment_method_hint`).

    **حدُّ الإطلاق، لا زينة** (مراجعةُ ٢٠٢٦-١٠-٠٧): بغيره يقرأ كلُّ شرطٍ هنا **كلَّ معلَّقٍ في تاريخ السوق** — صفوفَ `pay_ride`
    القديمةَ التي يسمّيها التصميمُ «معلَّقاً إلى الأبد» (§٠/٢). فلحظةَ يشتعل المفتاحُ: كلُّ راكبٍ عليه صفٌّ قديمٌ يُمنع، وكلُّ
    كبتنٍ عليه ثلاثةٌ يخرج من التوزيع، وكلُّ صفٍّ قديمٍ يصله التذكيرُ الأخيرُ دفعةً واحدة — **ثمّ يُتمّ آلياً بعد أسبوع**.
    **وتطبيقٌ قديمٌ لا يملك زرَّ «سلّمتُ المبلغ»**، فمنعُه بما لا يملك بابٌ بلا زرّ.

    **فالقديمُ للطابور وحدَه** (`pending_awaited`): يراه المشرفُ ويحسمه، **ولا تذكيرَ ولا حجبَ ولا إتمامَ آليَّ عليه**.
    **وأيُّ الحدّين يُعتمد قرارُ المالك** — مكتوبٌ في التقرير: هذا الأضيقُ أثراً، ويُوسَّع بسطرٍ واحد.
    """
    return Ride.payment_method_hint.is_not(None)


def pending_awaited() -> ColumnElement[bool]:
    """**معلَّقةٌ تنتظر أحداً**: كاشٌ أو كليك، `pending`، **على رحلةٍ انتهت** — **قديمةً كانت أو في التدفّق** (يحتاج `Ride` مضموماً).

    **والانتهاءُ شرطٌ لا زينة**: محجوزُ «بالساعة» النقديّ يولد `pending` عند **البدء** (`hourly.prepay_on_start`)، ورحلتُه
    جارية — فلا يُذكَّر به أحدٌ ولا يُحجب به كبتنٌ في منتصف رحلته. **وهذا ما يقرؤه طابورُ الإدارة وحدَه**.
    """
    return and_(
        Payment.status == PaymentStatus.PENDING,
        Payment.method.in_(AWAITED_METHODS),
        Ride.completed_at.is_not(None),
    )


def unconfirmed() -> ColumnElement[bool]:
    """**معلَّقةٌ تنتظر أحداً في التدفّق** — ما يُذكَّر به ويُحجب به ويُتمّ آلياً (`in_flow`)."""
    return and_(pending_awaited(), in_flow())


def payment_due() -> ColumnElement[bool]:
    """**رحلةٌ أجرتُها مستحقّةٌ ولا صفَّ حيٌّ عليها** — على `Ride` وحدَه (§٧، المبدأ ٣ في §١).

    منتهيةٌ، يدفعها طالبُها، في التدفّق، **ولا صفَّ معلَّقاً ولا في نزاعٍ عليها**، والمستحقُّ (`final_fare` ناقصَ ما يشغله صفٌّ)
    فوق الصفر. **وهي ما يبقى حين يسقط كلُّ صفّ**: حكمُ «غيرُ مدفوع» (§٧: «لا طلبَ جديدَ حتى يُسدَّد» — كان يرفع المنعَ لأن
    الصفَّ صار `failed` فخرج من `awaits_rider`)، وبطاقةٌ رُفضت، ورحلةٌ لم يفتح لها أحدٌ صفّاً. **بغيره يمحو الراكبُ منعَه بإسقاط
    صفِّه** — والمستحقُّ قائمٌ لا يراه أحد.

    **والصفُّ المعلَّقُ بأيِّ قناةٍ يخرجها منه**: بطاقةٌ صفحتُها مفتوحة، أو كاشٌ ينتظر إقراره (وذاك يمنع بـ`awaits_rider`).
    **والمبلغُ من `OWING_PAYMENT_STATUSES` نفسِها** التي يقرؤها `payments.outstanding_amount` — فلا حسابان يفترقان.
    """
    live = aliased(Payment)
    owing = aliased(Payment)
    covered = (
        select(func.coalesce(func.sum(owing.amount), 0))
        .where(owing.ride_id == Ride.id, owing.status.in_(OWING_PAYMENT_STATUSES))
        .scalar_subquery()
    )
    return and_(
        Ride.status == RideStatus.COMPLETED,
        Ride.completed_at.is_not(None),
        Ride.payer == RidePayer.REQUESTER.value,
        in_flow(),
        Ride.final_fare.is_not(None),
        ~exists(select(live.id).where(live.ride_id == Ride.id, live.status.in_(LIVE_STATUSES))),
        Ride.final_fare > covered,
    )


def awaits_captain() -> ColumnElement[bool]:
    """**ما ينتظر تأكيدَ الكبتن** (§٢-٣/§٢-٤): الكاشُ كلُّه، **وكليك بعد أن يُدخل الراكبُ مرجعَه** — فقبله لا شيءَ يؤكّده."""
    return and_(
        unconfirmed(),
        or_(
            Payment.method == PaymentMethod.CASH,
            Payment.cliq_reference_at.is_not(None),
        ),
    )


def awaits_rider() -> ColumnElement[bool]:
    """**ما ينتظر الراكب**: كاشٌ لم يُقِرّ بتسليمه، أو كليك بلا مرجع (§٢-٣/§٢-٤).

    **ولرحلةٍ يدفعها طالبُها وحدَها**: «يدفعها راكبُها/مستلمُها نقداً» (§٦٣-ج/١ و٤) صاحبُ مالها لا يحمل التطبيق، **فطالبُها لا
    يُذكَّر بما لا يملك ولا يُمنع به**.
    """
    return and_(
        unconfirmed(),
        Ride.payer == RidePayer.REQUESTER.value,
        or_(
            and_(Payment.method == PaymentMethod.CASH, Payment.declared_at.is_(None)),
            and_(Payment.method == PaymentMethod.CLIQ, Payment.cliq_reference_at.is_(None)),
        ),
    )


def captain_clock():
    """**متى بدأ انتظارُ الكبتن**: نهايةُ الرحلة للكاش، **ولحظةُ المرجع لكليك** — «ومن هنا تبدأ ساعةُ الكبتن» (§٢-٤)."""
    return case(
        (Payment.method == PaymentMethod.CLIQ, Payment.cliq_reference_at),
        else_=Ride.completed_at,
    )


def flag_on(country_column, key: FeatureKey) -> ColumnElement[bool]:
    """**مفتاحُ السوق مقروءاً داخل الاستعلام** — وغيابُ صفِّه إطفاءٌ كبقية الميزات (`settings_service.default_for`)."""
    return exists(
        select(FeatureFlag.id).where(
            FeatureFlag.country_code == country_column,
            FeatureFlag.feature_key == key.value,
            FeatureFlag.enabled.is_(True),
        )
    )


def _market_setting(column, default) -> ColumnElement:
    """عتبةُ سوق الكبتن — **وافتراضُ §٩ حين لا صفّ**، فلا يصير `NULL` حكماً صامتاً على أحد."""
    return func.coalesce(
        select(column)
        .where(PaymentSetting.country_code == User.country_code)
        .scalar_subquery(),
        default,
    )


def driver_blocked_clause() -> ColumnElement[bool]:
    """**كبتنٌ محجوبٌ عن العروض الجديدة** (§٧): ما ينتظر تأكيدَه ≥ العدد، أو أقدمُه أقدمُ من الساعات — **وسوقُه مشتعل**.

    **يُربط بصفِّ الكبتن الخارجيّ** (`Driver` مضموماً إليه `User` — شكلُ `dispatch._eligible_levels`)، ويُقرأ في الاستعلام
    نفسِه. **والرحلةُ الجاريةُ تكتمل**: الحجبُ للعروض لا للجاري. **والنزاعُ المفتوحُ لا يحجب أحداً** — ليس `pending`.

    **و`COALESCE(…, false)` على الأقدم ليس احتياطاً**: كبتنٌ لا شيءَ ينتظره أقدمُه `NULL`، و`NULL < x` مجهول — **و`NOT`
    المجهولِ مجهولٌ يُسقط الكبتنَ من التوزيع كلِّه بلا سبب**. وهو أسوأُ ما يقع هنا: حجبٌ صامتٌ لكلِّ كبتنٍ نظيف.
    """
    waiting = (
        select(Payment.id)
        .join(Ride, Ride.id == Payment.ride_id)
        .where(Ride.driver_id == Driver.id, awaits_captain())
    )
    count = (
        select(func.count(Payment.id))
        .join(Ride, Ride.id == Payment.ride_id)
        .where(Ride.driver_id == Driver.id, awaits_captain())
        .scalar_subquery()
    )
    oldest = (
        select(func.min(captain_clock()))
        .join(Ride, Ride.id == Payment.ride_id)
        .where(Ride.driver_id == Driver.id, awaits_captain())
        .scalar_subquery()
    )
    hours = _market_setting(PaymentSetting.driver_unconfirmed_block_hours, _DEFAULT_BLOCK_HOURS)
    cutoff = func.now() - literal_column("interval '1 hour'") * hours
    return and_(
        flag_on(User.country_code, FeatureKey.UNCONFIRMED_PAYMENTS_ENABLED),
        # **ولا يُعدّ شيءٌ لكبتنٍ لا ينتظره شيء** — الشرطُ الأرخصُ أوّلاً
        exists(waiting),
        or_(
            count >= _market_setting(
                PaymentSetting.driver_unconfirmed_block_count, _DEFAULT_BLOCK_COUNT
            ),
            func.coalesce(oldest < cutoff, false()),
        ),
    )
