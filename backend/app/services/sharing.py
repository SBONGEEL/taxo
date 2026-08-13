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

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from dataclasses import dataclass

from geoalchemy2 import Geography, Geometry
from redis.asyncio import Redis
from sqlalchemy import cast, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, RoutingFailed, RoutingUnavailable
from app.models.enums import (
    CountryCode,
    FeatureKey,
    Gender,
    GenderPreference,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentStatus,
    RideStatus,
)
from app.models.driver import Driver
from app.models.payment import Payment
from app.models.ride import (
    SHARE_SEAT_LEAD,
    SHARE_SEAT_PARTNER,
    SRID,
    Ride,
    make_point,
)
from app.models.sharing import RideSharingSetting
from app.models.user import User
from app.services import directions
from app.services import pricing
from app.services import settings_service
from app.ws.events import RideEvent

logger = logging.getLogger(__name__)


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


# **قبل الانطلاق**: هنا وحدَه يُرفع السعرُ إلى المنفرد (قرارُ المالك الخامس)
BEFORE_DEPARTURE = (
    RideStatus.REQUESTED,
    RideStatus.SEARCHING,
    RideStatus.ACCEPTED,
    RideStatus.ARRIVED,
)
# **وبعده لا يُرفع** (القرار السادس) — لا لأن المبلغ كبير بل لأن الإخبارَ حينئذٍ
# بلا بديل: من يُخبَر وهو في السيارة لا يملك قبولاً ولا رفضاً
AFTER_DEPARTURE = (RideStatus.IN_PROGRESS, RideStatus.AT_STOP)


@dataclass(frozen=True, slots=True)
class Aftermath:
    """من بقي بعد إلغاء شريكه، وهل بقي سعرُه كما وافق عليه."""

    ride_id: uuid.UUID
    rider_id: uuid.UUID
    price_kept: bool


async def on_member_cancelled(
    session: AsyncSession, cancelled: Ride
) -> Aftermath | None:
    """يطبّق قرارَي المالك الخامس والسادس على **من بقي**.

    ولا يفعل شيئاً لمن ألغى: قرارُ المالك الخامس نصُّه أن **الرسمَ العاديَّ عليه
    وحدَه** — وذلك ما يفعله `rides.cancel_ride` أصلاً بلا حرفٍ جديد. وهو ما
    اشتُري بالشكل (ب): كلُّ صفِّ رحلةٍ يُحاسَب بمفرده.

    **وجملةُ `UPDATE` واحدةٌ لا قفلُ صفٍّ ثانٍ**، وهذا مقصود: قفلُ صفِّ الشريك
    بعد صفِّ الملغي يفتح جموداً حقيقياً — راكبان يلغيان معاً (وهي حالٌ واقعية
    حين يتأخر الكبتن) فيقفل كلٌّ صفَّه ثم ينتظر صفَّ الآخر. والجملةُ الواحدة
    تأخذ قفلَها وتُفلته في نفسها، وشرطُها على الحالة يجعلها **جامدةَ التكرار**:
    الثانيةُ لا تجد صفّاً مطابقاً لأن الأولى أخرجته من الحالات النشطة.

    **وتصفيرُ النسبة المجمَّدة هو رفعُ السعر نفسُه**: `settle_discount` تقرؤها
    عند الإنهاء، فصفرُها يعني ألّا صفَّ خصمٍ يُكتب — ولا مكانَ ثانٍ يقرّر.
    """
    if cancelled.share_group_id is None:
        return None

    raised = (
        await session.execute(
            update(Ride)
            .where(
                Ride.share_group_id == cancelled.share_group_id,
                Ride.id != cancelled.id,
                Ride.status.in_(BEFORE_DEPARTURE),
            )
            .values(share_discount_percent_at_ride=Decimal("0.00"))
            .returning(Ride.id, Ride.rider_id)
        )
    ).first()
    if raised is not None:
        return Aftermath(ride_id=raised.id, rider_id=raised.rider_id, price_kept=False)

    # وإلا: إمّا لا شريكَ نشط، وإمّا شريكٌ انطلقت رحلتُه فيبقى سعرُه كما هو
    departed = (
        await session.execute(
            select(Ride.id, Ride.rider_id).where(
                Ride.share_group_id == cancelled.share_group_id,
                Ride.id != cancelled.id,
                Ride.status.in_(AFTER_DEPARTURE),
            )
        )
    ).first()
    if departed is None:
        return None
    return Aftermath(ride_id=departed.id, rider_id=departed.rider_id, price_kept=True)


class ShareGroupFull(AppError):
    """المقعدُ الثاني محجوزٌ — أو الرحلةُ الأولى لم تعد قابلةً للمشاركة."""

    status_code = 409
    code = "share_group_unavailable"
    message = "لم تعد هذه الرحلة قابلة للمشاركة"


async def join_group(session: AsyncSession, *, ride: Ride, lead: Ride) -> Ride:
    """يُلحق `ride` بمجموعة `lead` على كبتنها — **المقعدُ الثاني**.

    **وترتيبُ القفلين: الرحلةُ الأولى ثم اللاحقة، دائماً.** كلُّ ملتحقٍ يقفل
    نفسَ الصفِّ الأول ثم صفَّه هو، فلا تنشأ حلقةُ انتظار — وعكسُه (كلٌّ يقفل
    نفسَه ثم الأول) هو الجمودُ بعينه حين يلتحق اثنان معاً.

    **وما تملكه هذه الدالةُ لا الفهرس**: أن تكون مجموعةُ الشريك هي **مجموعةَ
    الكبتن نفسِها**. لا فهرسَ فريدٌ يقارن صفّين (`SPEC` §5.12، القرار الثاني)،
    فالتحقّقُ هنا تحت قفل الصفِّ الأول — وهو ما يجعل «كبتنٌ لمجموعةٍ واحدة»
    صحيحاً لا مجرّدَ نيّة.

    **والمقعدُ نفسُه ليس ملكَ هذا القفل، وقد قِيس**: إسقاطُ `with_for_update` عن
    الرحلة الأولى يُبقي «ملتحقان معاً ⇐ واحد» أخضر، لأن فهرسَ
    `(driver_id, share_seat)` هو من يلتقط الثاني. **والذي يملكه القفلُ وحدَه
    حالةُ الأولى بين الفحص والكتابة**: انطلاقٌ يقع في تلك الفجوة يجعل الملتحقَ
    يجتاز فحصاً على قراءةٍ قديمة، فيُلحَق راكبٌ بسيارةٍ غادرت مكانَه — بلا
    استثناءٍ ولا سطرٍ في سجل. `test_a_join_racing_the_departure_loses` يسقط بحذفه.
    """
    if lead.share_group_id is None and lead.share_seat != SHARE_SEAT_LEAD:
        raise ShareGroupFull()

    locked_lead = await session.scalar(
        select(Ride)
        .where(Ride.id == lead.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_lead is None:
        raise ShareGroupFull()

    # الأولى ما زالت قابلةً للمشاركة؟ — كبتنٌ مُسنَد، وحالةٌ نشطةٌ قبل الانطلاق،
    # ونسبةُ خصمٍ مجمَّدةٌ عليها (فهي وحدَها من طلب المشاركة)
    if (
        locked_lead.driver_id is None
        or locked_lead.status not in BEFORE_DEPARTURE
        or locked_lead.share_discount_percent_at_ride <= 0
    ):
        raise ShareGroupFull()

    # المجموعةُ تُولد عند أول التحاقٍ لا عند الطلب: رحلةٌ لم يشاركها أحدٌ تبقى
    # `NULL` — و«مجموعةٌ من واحد» صفٌّ يقول ما لم يقع
    if locked_lead.share_group_id is None:
        locked_lead.share_group_id = uuid.uuid4()

    joiner = await session.scalar(
        select(Ride)
        .where(Ride.id == ride.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    # **الانتقالُ يُقرأ من جدول `rides` نفسِه لا من قائمةٍ هنا**: «القبولُ لا
    # يُبلَغ من `requested`» قاعدةٌ في تلك الآلة (التوزيعُ يمرّ بـ`searching`
    # أولاً)، ونسخُها هنا يجعلها قاعدتين تفترقان أوّلَ تعديل. وهذا البابُ ليس
    # قبولاً بلا عرض: **الكبتنُ اختير بعرضِ الرحلة الأولى** وقَبِلها معلَّمةً
    # بالمشاركة، والملتحقُ يدخل على قبولٍ وقع.
    from app.services.rides import ALLOWED_TRANSITIONS

    if (
        joiner is None
        or RideStatus.ACCEPTED not in ALLOWED_TRANSITIONS[joiner.status]
    ):
        raise ShareGroupFull()

    joiner.driver_id = locked_lead.driver_id
    joiner.share_group_id = locked_lead.share_group_id
    joiner.share_seat = SHARE_SEAT_PARTNER
    joiner.status = RideStatus.ACCEPTED
    joiner.accepted_at = datetime.now(UTC)

    try:
        await session.flush()
    except IntegrityError as exc:
        # الفهرسان الجزئيان: مقعدٌ ثانٍ محجوزٌ على الكبتن أو في المجموعة
        await session.rollback()
        raise ShareGroupFull() from exc

    return joiner


# ----------------------------------------------------------------- المطابقة

# **سقفُ المرشَّحين — وهو سقفُ نداءات Mapbox في مسارٍ يقف عليه راكبٌ ينتظر.**
# ثلاثةٌ لا خمسة: كلُّ مرشَّحٍ نداءُ شبكةٍ خارجيٌّ في طريق `POST /rides`،
# والمقايضةُ ليست بين دقّةٍ وسرعةٍ بل بين مطابقةٍ أفضلَ قليلاً وشاشةٍ تنتظر.
MAX_CANDIDATES = 3


@dataclass(frozen=True, slots=True)
class Match:
    """رحلةٌ أولى تقبل شريكاً، والالتفافُ الذي تكلّفه صاحبَها بالدقائق."""

    lead: Ride
    detour_minutes: Decimal


def _as_geography(point):
    """المقارنةُ بالمتر لا بالدرجة — وقد قِيس أثرُ غيابها.

    `ST_DWithin` بين **geometry**ين يقيس بدرجات الإحداثيات، ورقمُ الإعداد
    كيلومترات. وحذفُ التحويلين معاً يجعل رحلةً إلى المفرق (سبعون كيلومتراً)
    داخلَ ممرِّ الكيلومترين، وممرّاً بعرض **متر** يسع المدينةَ كلَّها — قِيس،
    ويسقط به اختباران.

    **ولا يخطئ شيءٌ ظاهرياً حين يقع**: الاستعلامُ يمرّ ويعيد مرشَّحين، وسقفُ
    الالتفاف وحدَه يردّهم — فتُنفق نداءاتُ Mapbox على رحلاتٍ في مدينةٍ أخرى،
    ويصير الممرُّ حقلاً في اللوحة لا يفعل شيئاً.

    **وواحدٌ من التحويلين يكفي** (قِيس أيضاً): PostGIS يحوّل الطرفَ الآخر ضمناً
    إلى geography. وهما مكتوبان معاً لأن الاعتمادَ على تحويلٍ ضمنيٍّ يعرفه من
    كتبه وحدَه هو ما يجعل «تبسيطاً» لاحقاً يحذف الاثنين ظنّاً أنهما زينة.
    """
    return cast(point, Geography(geometry_type="POINT", srid=SRID))


def _corridor(ride: type[Ride]):
    """ممرٌّ حول **الخطِّ المستقيم** بين نقطتي الرحلة الأولى — تصفيةٌ لا حكم.

    المسارُ الحقيقيُّ منحنٍ وهذا الخطُّ وترُه، فالممرُّ حوله **أضيقُ في الأطراف
    وأوسعُ في الوسط** من ممرِّ المسار. وهو مقبولٌ هنا لأنه ليس القرار: ما يقرّر
    هو سقفُ الالتفاف المقيسُ بـMapbox بعده. وفائدتُه أنه يمنع نداءً خارجياً لكل
    رحلةٍ قائمةٍ في البلد — وهذا ما لا يجوز أن يُشترى بدقّةٍ في تصفية.
    """
    line = func.ST_MakeLine(
        cast(ride.pickup_point, Geometry(geometry_type="POINT", srid=SRID)),
        cast(ride.dropoff_point, Geometry(geometry_type="POINT", srid=SRID)),
    )
    return cast(line, Geography(geometry_type="LINESTRING", srid=SRID))


def _gender_compatible(
    *, lead_ride: Ride, lead_rider: User, joiner_ride: Ride, joiner_rider: User
) -> bool:
    """**رحلةٌ بتفضيلٍ نسائيٍّ لا يجلس فيها إلا نساءٌ** (SPEC §5.12، ثالثاً).

    `ride_gender_preference` تفضيلٌ في **جنس الكبتن** لا في جنس من يجلس بجانبها،
    فالمشاركةُ تفتح ما لم يفتحه شيءٌ قبلها: **راكبٌ ثانٍ لم تختره ولم تُسأل عنه**.
    وامرأةٌ طلبت كبتنةً لأمانها ثم وجدت رجلاً غريباً في المقعد الآخر تكون الخدمةُ
    قد نقضت غرضَها بيدها.

    **والشرطُ متناظرٌ عمداً**: يكفي أن يكون أحدُ الطلبين مجنَّساً ليُشترط في
    **كليهما** إعلانُ الأنوثة. فمن اشترطت كبتنةً لا تُعطى راكباً، ومن لم تشترط
    لا تُقحَم في مقعدٍ اشترطته غيرُها.

    **وإعلانٌ لا ختمُ مشرف**: جنسُ الراكب مُعلَنٌ عن نفسه في كل هذا النظام
    (`gender_verified_at` للكبتنة وحدَها، لأن إعلانَها يقيّد أمانَ غيرها). ورفعُ
    الشرط هنا إلى ختمٍ يُغلق البابَ على كل راكبةٍ في السوق — ولا أحدَ يختم الركّاب.
    """
    gendered = (
        lead_ride.gender_preference is not GenderPreference.ANY
        or joiner_ride.gender_preference is not GenderPreference.ANY
    )
    if not gendered:
        return True
    return lead_rider.gender is Gender.FEMALE and joiner_rider.gender is Gender.FEMALE


async def find_lead(session: AsyncSession, ride: Ride, rider: User) -> Match | None:
    """يبحث عن رحلةٍ أولى يلتحق بها `ride` — أو `None` فيمضي منفرداً.

    **ولا يرفع استثناءً حين لا يجد**: غيابُ الشريك هو الحالُ الغالبة، وقرارُ
    المالك الثالث يجعله بلا أثرٍ على الراكب أصلاً — الوعدُ يُحترم والشركةُ تتحمّل
    الفرق. فالمطابقةُ **زيادةٌ محتملة** لا شرطٌ في الطلب.

    ثلاثةُ أرقامٍ per-country تحكمها (SPEC §5.12): عرضُ الممرِّ، وسقفُ الالتفاف،
    ونافذةُ الانتظار — **وكلُّها إعداداتٌ لا ثوابتُ كود**، لأن مدينةً بشوارعَ
    ضيّقةٍ ليست مدينةً بطريقٍ دائري.

    **والترتيبُ الأقدمُ أولاً، وأولُ من يتّسع له السقفُ يفوز** — لا الأقلُّ
    التفافاً بعد قياس الجميع. فقياسُ الجميع نداءان زائدان في طريقٍ يقف عليه راكبٌ
    ينتظر، والأقدمُ أولاً عدلٌ يُفهَم: من انتظر أطولَ يُخدَم أولاً.
    """
    row = await settings_for(session, ride.country_code)
    if row is None or row.discount_percent <= 0:
        return None

    corridor_metres = float(row.corridor_km) * 1000
    window_opened = datetime.now(UTC) - timedelta(seconds=row.partner_wait_seconds)
    joiner_pickup = _as_geography(make_point(ride.pickup_lat, ride.pickup_lng))
    joiner_dropoff = _as_geography(make_point(ride.dropoff_lat, ride.dropoff_lng))

    candidates = (
        await session.execute(
            select(Ride, User)
            .join(User, User.id == Ride.rider_id)
            .where(
                Ride.id != ride.id,
                Ride.country_code == ride.country_code,
                Ride.vehicle_category == ride.vehicle_category,
                Ride.status.in_(BEFORE_DEPARTURE),
                Ride.driver_id.is_not(None),
                # **مقعدٌ أولٌ بلا مجموعة = لم يلتحق بها أحدٌ قط.** وصفٌّ له
                # مجموعةٌ وقد ألغى شريكُه يبقى خارجَ البحث بقرار المالك الثامن:
                # لا شريكَ ثالث، ونافذةُ انتظارٍ ثانيةٌ تُطيل رحلةَ من بقي لأجل
                # خصمٍ لم يعد يُطبَّق عليه
                Ride.share_seat == SHARE_SEAT_LEAD,
                Ride.share_group_id.is_(None),
                Ride.share_discount_percent_at_ride > 0,
                Ride.created_at >= window_opened,
                func.ST_DWithin(_corridor(Ride), joiner_pickup, corridor_metres),
                func.ST_DWithin(_corridor(Ride), joiner_dropoff, corridor_metres),
            )
            .order_by(Ride.created_at)
            .limit(MAX_CANDIDATES)
        )
    ).all()

    for lead, lead_rider in candidates:
        if not _gender_compatible(
            lead_ride=lead,
            lead_rider=lead_rider,
            joiner_ride=ride,
            joiner_rider=rider,
        ):
            continue
        detour = await _detour_minutes(session, lead=lead, joiner=ride)
        if detour is None or detour > row.max_detour_minutes:
            continue
        return Match(lead=lead, detour_minutes=detour)
    return None


async def _detour_minutes(
    session: AsyncSession, *, lead: Ride, joiner: Ride
) -> Decimal | None:
    """كم تطول رحلةُ **الأول** بالتقاط الثاني — أو `None` إن تعذّر القياس.

    **والترتيبُ المقيسُ هو الأسوأُ للأول عمداً**: يُلتقط الشريكُ ثم يُنزل قبله
    (`الأول ← الثاني ← وجهةُ الثاني ← وجهةُ الأول`). فأيُّ ترتيبٍ آخرَ يسوقه
    الكبتنُ فعلاً أقصرُ من هذا أو مساوٍ له — أي أن السقفَ يبقى صحيحاً مهما ساق،
    بدل أن يكون صحيحاً في ترتيبٍ واحدٍ ويُخلَف في غيره. **ونداءٌ واحدٌ لا نداءان**
    (SPEC §5.12: «نداءٌ لكل مرشَّح»): مقارنةُ ترتيبين تضاعف الانتظارَ لتحسّنَ
    مطابقةً، والسقفُ الأسوأُ يغني عنها.

    **وفشلُ التوجيه يُبتلع هنا ولا يُسقط الطلب**: الرحلةُ المنفردةُ سُعِّرت قبل
    هذا النداء، فانقطاعُ Mapbox لحظتَها يمنع **زيادةً** لا يمنع رحلة. والابتلاعُ
    ضيّقٌ باسمه — لا `except Exception` تخفي خطأً برمجياً كالذي شحن في 12-ط.
    """
    try:
        route = await directions.route_between(
            session,
            directions.Coordinates(lat=lead.pickup_lat, lng=lead.pickup_lng),
            directions.Coordinates(lat=lead.dropoff_lat, lng=lead.dropoff_lng),
            country_code=lead.country_code,
            stops=(
                directions.Coordinates(lat=joiner.pickup_lat, lng=joiner.pickup_lng),
                directions.Coordinates(lat=joiner.dropoff_lat, lng=joiner.dropoff_lng),
            ),
        )
    except (RoutingFailed, RoutingUnavailable):
        logger.warning("تعذّر قياس التفاف المشاركة للرحلة %s", lead.id)
        return None
    return route.duration_min - lead.duration_min


async def try_join(
    session: AsyncSession, redis: Redis, *, ride: Ride, rider: User
) -> Ride | None:
    """مطابقةٌ ثم التحاقٌ ثم إبلاغُ من يعنيه — أو `None` فيمضي التوزيعُ عادياً.

    **وترتيبُ الخطوات ليس تنظيماً**: البحثُ يسبق كلَّ قفل، لأن فيه نداءَ Mapbox —
    وقاعدةُ المشروع أن **لا يُمسَك قفلُ صفٍّ عبر نداءٍ خارجيٍّ يمكن أن يسبقه**
    (`card_payments.reconcile`). ثم يُقفل ويُكتب، ثم يُثبَّت، ثم يُبلَّغ **بعد
    الـcommit** كما تفعل الحجوزات: إشعارٌ يسبق تثبيتَه قد يصف ما لم يقع.

    **و`ShareGroupFull` هنا ليست خطأً يُرفع للراكب**: معناها أن ملتحقاً آخرَ سبقنا
    إلى المقعد في تلك اللحظة (وهو ما يحرسه اختبارُ التزامن). وطالبُ المشاركة لا
    شأن له بذلك — رحلتُه تمضي بالخصم إلى التوزيع، والشركةُ تتحمّل الفرق.
    """
    match = await find_lead(session, ride, rider)
    if match is None:
        return None

    try:
        joined = await join_group(session, ride=ride, lead=match.lead)
    except ShareGroupFull:
        logger.info("سُبقنا إلى المقعد الثاني في المجموعة — تمضي منفردة")
        return None

    lead_rider_id = match.lead.rider_id
    driver_user_id = await session.scalar(
        select(Driver.user_id).where(Driver.id == joined.driver_id)
    )
    await session.commit()

    from app.services import notifications

    try:
        # الملتحقُ يعرف بحدثه المعتاد: كبتنٌ أُسند إليه
        await notifications.publish_ride_event(
            session, redis, joined, RideEvent.DRIVER_ASSIGNED
        )
        if driver_user_id is not None:
            await notifications.publish_share_partner_joined(
                session,
                redis,
                driver_user_id=driver_user_id,
                lead_rider_id=lead_rider_id,
                ride_id=joined.id,
                detour_minutes=str(match.detour_minutes),
            )
        await session.commit()
    except Exception:  # noqa: BLE001 - إشعارٌ متعثّر لا يفكّ مجموعةً تكوّنت
        logger.warning("تعذّر إبلاغ أطراف المشاركة", exc_info=True)

    return joined
