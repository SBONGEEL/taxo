"""حوافزُ الإحالة — الرمزُ والإسنادُ والاستحقاقُ والدفع (SPEC §9.1، 12-ح ثم تعميمُها).

**قرارُ المالك (2026-08-12)**: تُبنى الآليةُ والتتبّع، والمبالغُ صفرٌ حتى
يحدّدها. فيشحن الملفُّ عاملاً وخامداً معاً: الرمزُ يُولَّد، والإسنادُ يُكتب،
والعدُّ يُقرأ — ولا قيدٌ يُكتب حتى يُحدَّد مبلغ.

**وتعميمُ 2026-08-16**: ثلاثةُ برامجَ خلف بابٍ واحد، **والبرنامجُ يُختار من دور
المُحال** لا من دور المُحيل (قرارُ المالك الثالث): الغرضُ اكتسابُ حسابات، ومن
جاء بكبتنٍ جاء بكبتن أياً كان دورُه هو. **والنسائيُّ علاوةٌ لا برنامجٌ ثالث**
(القرار الثاني) — وتفصيلُ سببه في `models/referral.py`.

**والاستحقاقُ مقارنةٌ حيّةٌ هنا لا عمودٌ في القاعدة**: تغييرُ الحدِّ من اللوحة
يعيد تقييمَ الجميع، بدل أن يترك صفوفاً وسمها حدٌّ قديم — نفسُ قاعدةِ «flagged»
في تقارير عدم تطابق الجنس. **والمدفوعُ وحده يُجمَّد**، لأن المالَ لا يُعاد
تقييمه.

**والرمزُ يُستهلك في التسجيل وحده**: لا مسارَ في هذا الملف يُسند إحالةً لحسابٍ
قائم. إسنادٌ رجعيٌّ («سجّلتُ الأسبوع الماضي، أضف رمز صديقي») هو بابُ التلاعب
الوحيد الذي لا يُغلق بعد فتحه — من يملك حسابين يُحيل نفسه متى شاء.

**وترتيبُ الأقفال**: صفُّ الإحالة، ثم **قفلُ محفظة المُحيل صراحةً قبل عدِّ
السقف**، ثم `wallet.record` (وهو معاود الدخول داخل المعاملة). والسببُ أن قفلَ
صفِّ الإحالة يحمي الصفَّ من دفعتين **ولا يحمي مُحيلاً من صفَّين مختلفَين
يُدفعان معاً فيتجاوزان سقفَه** — والقفلُ الصحيح موجودٌ أصلاً على صاحب المحفظة.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    DriverStatus,
    FeatureKey,
    Gender,
    RideStatus,
    UserRole,
    WalletTransactionType,
)
from app.models.referral import (
    DEFAULT_REQUIRED_RIDES,
    DEFAULT_REWARD_AMOUNT,
    DEFAULT_RIDER_REQUIRED_RIDES,
    REFERRAL_TYPE_DRIVER,
    REFERRAL_TYPE_RIDER,
    Referral,
    ReferralSetting,
)
from app.models.ride import Ride
from app.models.subscription import DriverSubscription
from app.models.user import User
from app.services import settings_service, wallet

# أبجديةٌ بلا `0/O/1/I/L`: الرمزُ يُقرأ من شاشةٍ ويُنطق في مكالمةٍ ويُكتب في
# أخرى، وحرفان متشابهان يجعلان رمزاً صحيحاً يُرفض.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8

# مفتاحُ كلِّ برنامج — والنوعُ يقرّر أيَّهما يُقرأ
TYPE_FLAG: dict[str, FeatureKey] = {
    REFERRAL_TYPE_DRIVER: FeatureKey.DRIVER_REFERRALS_ENABLED,
    REFERRAL_TYPE_RIDER: FeatureKey.RIDER_REFERRALS_ENABLED,
}

DEFAULT_REQUIRED_BY_TYPE: dict[str, int] = {
    REFERRAL_TYPE_DRIVER: DEFAULT_REQUIRED_RIDES,
    REFERRAL_TYPE_RIDER: DEFAULT_RIDER_REQUIRED_RIDES,
}


class ReferralCodeUnknown(NotFound):
    code = "referral_code_unknown"
    message = "رمز الإحالة غير صحيح"


class ReferralNotAllowed(Conflict):
    code = "referral_not_allowed"
    message = "لا يمكن استخدام رمز الإحالة"


def _now() -> datetime:
    return datetime.now(UTC)


def generate_code() -> str:
    """رمزٌ عشوائيٌّ لأي حساب. والفرادةُ يحرسها الفهرس، وهذا يقلّل الاصطدام."""
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def normalize(code: str) -> str:
    """الرمزُ يُطبَّع كما يُطبَّع رمزُ الكوبون: يُقرأ من ملصقٍ ويُكتب بأي حالة."""
    return code.strip().upper()


def type_for_role(role: UserRole) -> str:
    """**البرنامجُ من دور المُحال** — مشتقٌّ لا مخزَّن.

    `users.role` ثابتٌ مدى عمر الحساب (لا مسارَ في المشروع يبدّله)، فعمودُ نوعٍ
    على صفِّ الإحالة بيتٌ ثانٍ لحقيقةٍ قائمة. **وحيث يُكتب النوعُ فعلاً هو
    الإعدادات**، لأن الصفَّ هناك هو **البرنامج** لا وصفٌ لحدثٍ وقع.
    """
    return REFERRAL_TYPE_DRIVER if role is UserRole.DRIVER else REFERRAL_TYPE_RIDER


# ------------------------------------------------------------ الإعدادات


async def settings_for(
    session: AsyncSession, country: CountryCode, referral_type: str
) -> ReferralSetting | None:
    return await session.scalar(
        select(ReferralSetting).where(
            ReferralSetting.country_code == country,
            ReferralSetting.referral_type == referral_type,
        )
    )


@dataclass(frozen=True)
class Policy:
    """سياسةُ برنامجٍ كما تُقرأ لحظةَ السؤال — لا تُجمَّد إلا على مكافأةٍ دُفعت."""

    referral_type: str
    enabled: bool
    reward_amount: Decimal
    required_rides: int
    female_bonus_amount: Decimal
    monthly_cap: int | None
    referred_promo_code_id: uuid.UUID | None

    @property
    def pays(self) -> bool:
        """هل تُدفع مكافأةٌ فعلاً؟ **صفرٌ يعني «لم يُحدَّد»** لا «صفراً»."""
        return self.enabled and self.reward_amount > 0

    def amount_for(self, *, female_verified: bool) -> Decimal:
        """المبلغُ المستحقّ — **الأساسُ والعلاوةُ قيدٌ واحد**.

        والعلاوةُ على برنامج السائقين وحدَه: راكبةٌ موثَّقةُ الجنس لا علاوةَ
        عليها، فغرضُ العلاوة بناءُ عرضِ السائقات لا مكافأةُ جنسٍ في ذاته.
        """
        if self.referral_type != REFERRAL_TYPE_DRIVER or not female_verified:
            return self.reward_amount
        return self.reward_amount + self.female_bonus_amount


async def policy_for(
    session: AsyncSession, country: CountryCode, referral_type: str
) -> Policy:
    row = await settings_for(session, country, referral_type)
    return Policy(
        referral_type=referral_type,
        enabled=await settings_service.is_feature_enabled(
            session, country, TYPE_FLAG[referral_type]
        ),
        reward_amount=row.reward_amount if row else DEFAULT_REWARD_AMOUNT,
        required_rides=(
            row.required_rides
            if row
            else DEFAULT_REQUIRED_BY_TYPE.get(referral_type, DEFAULT_REQUIRED_RIDES)
        ),
        female_bonus_amount=(
            row.female_bonus_amount if row else DEFAULT_REWARD_AMOUNT
        ),
        monthly_cap=row.monthly_cap if row else None,
        referred_promo_code_id=row.referred_promo_code_id if row else None,
    )


# ------------------------------------------------------------ الإسناد


async def by_code(session: AsyncSession, code: str) -> User | None:
    """صاحبُ الرمز — **حسابٌ لا كبتن**: الإحالةُ علاقةٌ بين حسابين."""
    return await session.scalar(
        select(User).where(User.referral_code == normalize(code))
    )


async def attach(session: AsyncSession, *, referred: User, code: str) -> Referral:
    """يُسند إحالةً للحساب المُسجَّل الآن. تُستدعى من مسار التسجيل وحده.

    **ولا تُفحص شروطُ الاستحقاق هنا**: الإسنادُ سجلٌّ لما وقع (سجّلت برمز
    فلان)، والاستحقاقُ سؤالٌ يُطرح لاحقاً وقد يتغيّر جوابُه. وربطُهما يعني أن
    رمزاً في سوقٍ مطفأٍ اليوم يُهمل صامتاً — فإن أُشعل المفتاحُ غداً لم يبق
    أثرٌ لمن أحال من.

    **ولا يُفحص السقفُ هنا أيضاً** (قرارُ المالك الرابع): المنعُ عند التسجيل
    يعاقب **القادمَ الجديد** على سقف غيره. فتُسجَّل الإحالةُ وتُنسب، ويُقال
    للمُحيل في شاشته إنها فوق سقف الشهر ولن تُدفع — **لا صمتَ ولا رقمٌ يختفي**.
    """
    referrer = await by_code(session, code)
    if referrer is None:
        raise ReferralCodeUnknown()
    if referrer.id == referred.id:
        raise ReferralNotAllowed("لا يمكن إحالة نفسك")

    referral = Referral(
        referrer_user_id=referrer.id,
        referred_user_id=referred.id,
        code_used=normalize(code),
    )
    session.add(referral)
    try:
        await session.flush()
    except IntegrityError as exc:
        # الفريدُ على المُحال — حسابٌ واحدٌ يُحال مرةً واحدة، والحارسُ في
        # القاعدة لا في فحصٍ سابقٍ يمكن أن يُسبَق
        await session.rollback()
        raise ReferralNotAllowed("هذا الحساب مُحالٌ بالفعل") from exc
    return referral


# ------------------------------------------------------------ الاستحقاق


async def _completed_rides(
    session: AsyncSession, user_id: uuid.UUID, referral_type: str
) -> int:
    """رحلاتٌ مكتملة — **ككبتنٍ أو كراكب بحسب البرنامج**. تُعدّ في القاعدة."""
    if referral_type == REFERRAL_TYPE_DRIVER:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(Ride)
                .join(Driver, Driver.id == Ride.driver_id)
                .where(Driver.user_id == user_id, Ride.status == RideStatus.COMPLETED)
            )
            or 0
        )
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Ride)
            .where(Ride.rider_id == user_id, Ride.status == RideStatus.COMPLETED)
        )
        or 0
    )


@dataclass(frozen=True)
class Progress:
    """أين وصلت إحالةٌ واحدة — للشاشتين ولجدول اللوحة.

    **جملةُ الحالة تُبنى في الواجهة من هذه الحقائق**، لا نصٌّ يأتي من الخلفية:
    نفسُ سببِ بناء نصِّ الإشعار من `data` (`services/notifications.py`).
    """

    referral: Referral
    referral_type: str
    driver_approved: bool
    has_subscription: bool
    female_verified: bool
    rides_done: int
    rides_required: int
    over_monthly_cap: bool = False

    @property
    def rewarded(self) -> bool:
        return self.referral.rewarded_at is not None

    @property
    def qualifies(self) -> bool:
        """شروطُ كلِّ برنامجٍ — **ولا مكافأةَ على تسجيلٍ مجرَّد في الحالتين**.

        وهو الحارسُ الوحيد الذي يقف في وجه الحسابات الوهمية فعلاً.
        """
        if self.rides_done < self.rides_required:
            return False
        if self.referral_type == REFERRAL_TYPE_DRIVER:
            return self.driver_approved and self.has_subscription
        return True


async def progress_of(
    session: AsyncSession, referral: Referral, *, policy: Policy
) -> Progress:
    referred = await session.get(User, referral.referred_user_id)
    assert referred is not None  # مفتاحٌ أجنبيٌّ بـ CASCADE

    driver = await session.scalar(
        select(Driver).where(Driver.user_id == referred.id)
    )
    return Progress(
        referral=referral,
        referral_type=policy.referral_type,
        driver_approved=driver is not None and driver.status is DriverStatus.APPROVED,
        has_subscription=(
            driver is not None and await _bought_once(session, driver.id)
        ),
        # **الوسمُ لا الإقرار**: بلا `gender_verified_at` كلمةُ «سائقة» كلمةٌ
        # يكتبها أحدٌ عن نفسه — نفسُ قراءةِ التوفيق في 10-ج. ومالٌ يُدفع على
        # إقرارٍ غيرِ موثَّق مالٌ يُدفع على كلمة
        female_verified=(
            referred.gender is Gender.FEMALE
            and referred.gender_verified_at is not None
        ),
        rides_done=await _completed_rides(
            session, referred.id, policy.referral_type
        ),
        rides_required=policy.required_rides,
    )


async def _bought_once(session: AsyncSession, driver_id: uuid.UUID) -> bool:
    """**اشترى اشتراكاً مرةً على الأقل** — لا «نشطٌ لحظةَ الدفع».

    قرارُ المالك (2026-08-16) وسببُه بنصِّه: **حقٌّ اكتُسب لا يُمحى بمرور
    الزمن**، وقراءةُ «نشطٌ لحظة الدفع» تجعل الاستحقاقَ يرقص مع تقويم الكبتن —
    تُدفع إن صادفت الدورةُ يومَ سريانه وتضيع إن صادفت يومَ انقطاعه. **والعملُ
    هو الحكمُ لا التوقيت**.

    وصفُّ `driver_subscriptions` **لا يوجد إلا وقد وصل مالُه** (لا حالةَ
    `pending` فيه)، فوجودُ الصفِّ هو الشراء. ثم إن إكمالَ الرحلات يستلزم
    اشتراكاً سارياً أصلاً (`dispatch.eligible_driver_ids`) فالشرطان لا يتناقضان.
    """
    return (
        await session.scalar(
            select(DriverSubscription.id)
            .where(DriverSubscription.driver_id == driver_id)
            .limit(1)
        )
    ) is not None


async def progress_many(
    session: AsyncSession,
    referrals: list[Referral],
    *,
    policies: dict[str, Policy],
) -> dict[uuid.UUID, Progress]:
    """حالُ صفحةٍ كاملةٍ بعددٍ ثابتٍ من الاستعلامات — لا أربعةٍ لكل صف.

    نفسُ شكلِ `ride_log.payment_summaries`: صفحةُ خمسين صفاً كانت ستُصدر مئتَي
    ذهابٍ وعودة، وهو ثمنٌ يُدفع على كل فتحةٍ لشاشةٍ تُقرأ ولا تُكتب.
    """
    if not referrals:
        return {}

    referred_ids = [row.referred_user_id for row in referrals]

    # (١) الحسابُ المُحال: دورُه وجنسُه ووسمُه — ومعه صفُّ الكبتن إن وُجد
    people = {
        user_id: (role, gender, verified, driver_id, status)
        for user_id, role, gender, verified, driver_id, status in (
            await session.execute(
                select(
                    User.id,
                    User.role,
                    User.gender,
                    User.gender_verified_at,
                    Driver.id,
                    Driver.status,
                )
                .outerjoin(Driver, Driver.user_id == User.id)
                .where(User.id.in_(referred_ids))
            )
        ).all()
    }
    driver_ids = [row[3] for row in people.values() if row[3] is not None]

    # (٢) من اشترى اشتراكاً مرةً — مجموعةٌ لا استعلامٌ لكلٍّ
    subscribed = set(
        (
            await session.scalars(
                select(DriverSubscription.driver_id).where(
                    DriverSubscription.driver_id.in_(driver_ids)
                )
            )
        ).all()
    ) if driver_ids else set()

    # (٣) رحلاتٌ مكتملة — عدّان في القاعدة (القسم 14): ككبتنٍ وكراكب
    as_driver = {
        driver_id: int(total)
        for driver_id, total in (
            await session.execute(
                select(Ride.driver_id, func.count())
                .where(
                    Ride.driver_id.in_(driver_ids),
                    Ride.status == RideStatus.COMPLETED,
                )
                .group_by(Ride.driver_id)
            )
        ).all()
    } if driver_ids else {}
    as_rider = {
        rider_id: int(total)
        for rider_id, total in (
            await session.execute(
                select(Ride.rider_id, func.count())
                .where(
                    Ride.rider_id.in_(referred_ids),
                    Ride.status == RideStatus.COMPLETED,
                )
                .group_by(Ride.rider_id)
            )
        ).all()
    }

    out: dict[uuid.UUID, Progress] = {}
    for row in referrals:
        role, gender, verified, driver_id, status = people.get(
            row.referred_user_id, (UserRole.RIDER, None, None, None, None)
        )
        referral_type = type_for_role(role)
        policy = policies[referral_type]
        out[row.id] = Progress(
            referral=row,
            referral_type=referral_type,
            driver_approved=status is DriverStatus.APPROVED,
            has_subscription=driver_id is not None and driver_id in subscribed,
            female_verified=gender is Gender.FEMALE and verified is not None,
            rides_done=(
                as_driver.get(driver_id, 0)
                if referral_type == REFERRAL_TYPE_DRIVER
                else as_rider.get(row.referred_user_id, 0)
            ),
            rides_required=policy.required_rides,
        )
    return out


async def policies_for(
    session: AsyncSession, country: CountryCode
) -> dict[str, Policy]:
    """سياسةُ البرنامجين لسوقٍ واحد — تُقرأ مرةً لصفحةٍ كاملة."""
    return {
        referral_type: await policy_for(session, country, referral_type)
        for referral_type in (REFERRAL_TYPE_RIDER, REFERRAL_TYPE_DRIVER)
    }


async def list_for_referrer(
    session: AsyncSession, *, user: User
) -> tuple[dict[str, Policy], list[Progress], int]:
    """إحالاتُ حسابٍ بحالتها — لشاشته. ومعها سياسةُ كلِّ برنامجٍ وما بقي من سقفه.

    **والسقفُ يُعلن قبل أن يدعو** (شرطُ المالك): الشاشةُ تقول السقفَ الشهريَّ
    وكم بقي منه هذا الشهر — لا أن يُفاجأ برفض دفعٍ بعد أن دعا.
    """
    rows = list(
        (
            await session.scalars(
                select(Referral)
                .where(Referral.referrer_user_id == user.id)
                .order_by(Referral.created_at.desc())
            )
        ).all()
    )
    policies = await policies_for(session, user.country_code)
    progresses = await progress_many(session, rows, policies=policies)
    return (
        policies,
        [progresses[row.id] for row in rows],
        await _paid_this_month(session, user.id),
    )


async def rewarded_total(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """مجموعُ ما قبضه حسابٌ من مكافآت — **يُجمع في القاعدة** (القسم 14)."""
    return Decimal(
        await session.scalar(
            select(func.coalesce(func.sum(Referral.reward_amount), 0)).where(
                Referral.referrer_user_id == user_id,
                Referral.rewarded_at.is_not(None),
            )
        )
        or 0
    )


def _month_start(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _paid_this_month(session: AsyncSession, user_id: uuid.UUID) -> int:
    """كم إحالةً **أُنشئت** هذا الشهر ودُفعت — والسقفُ يُقاس بشهر الإنشاء.

    قرارُ المالك الرابع: **شهرُ الإنشاء** لا شهرُ الدفع. ولو حُسب بشهر الدفع
    لصار السقفُ **جدولَ صرفٍ لا سقفاً**: من أحال عشرةً في كانون يقبض ثلاثةً فيه
    وثلاثةً في شباط — وهو عكسُ ما يُراد من السقف.
    """
    since = _month_start(_now())
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Referral)
            .where(
                Referral.referrer_user_id == user_id,
                Referral.created_at >= since,
                Referral.rewarded_at.is_not(None),
            )
        )
        or 0
    )


# ------------------------------------------------------------ الدفع


async def _locked(session: AsyncSession, referral_id: uuid.UUID) -> Referral:
    """يقرأ صفَّ الإحالة **مقفولاً** قبل فحص «هل دُفعت».

    وبغير القفل تمرّ دورتان متزامنتان من المهمة الدورية على صفٍّ واحد، فتقرآن
    `rewarded_at IS NULL` كلتاهما وتكتبان مكافأتين — ومفتاحُ تكرارِ الدفتر يمنع
    القيدَ الثاني لكنه **لا يمنع** الصفَّ من أن يُكتب مرتين بمبلغين.
    """
    row = await session.scalar(
        select(Referral)
        .where(Referral.id == referral_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:  # pragma: no cover - صفٌّ محذوف
        raise NotFound("الإحالة غير موجودة")
    return row


async def pay(session: AsyncSession, referral_id: uuid.UUID) -> Referral | None:
    """يدفع مكافأةَ إحالةٍ إن استحقّت. الـcommit للمستدعي.

    يعيد `None` إن لم تستحقّ أو كانت مدفوعة أو تجاوزت سقفَ شهرها — فالمهمةُ
    الدورية تمرّ على صفوفٍ كثيرةٍ وأكثرُها ليس جاهزاً، وذلك حالةٌ عادية لا خطأ.
    """
    referral = await _locked(session, referral_id)
    if referral.rewarded_at is not None:
        return None

    referrer = await session.get(User, referral.referrer_user_id)
    referred = await session.get(User, referral.referred_user_id)
    if referrer is None or referred is None:  # pragma: no cover
        return None

    # **دولةُ المُحيل هي الحاكمة**: المالُ يدخل محفظتَه، وعملتُه عملةُ بلده.
    # ولو حُكمت بدولة المُحال لدُفع بعملةٍ لا تُنفق في محفظةٍ أخرى
    country = referrer.country_code
    policy = await policy_for(session, country, type_for_role(referred.role))
    if not policy.pays:
        return None

    progress = await progress_of(session, referral, policy=policy)
    if not progress.qualifies:
        return None

    # **قفلُ محفظة المُحيل صراحةً قبل عدِّ السقف** (القسم ٩ من المواصفة):
    # قفلُ صفِّ الإحالة يحمي الصفَّ من دفعتين، ولا يحمي **مُحيلاً** من صفَّين
    # مختلفَين يُدفعان معاً فيتجاوزان سقفَه. والقفلُ الاستشاري معاود الدخول،
    # فـ`wallet.record` يعيد أخذَه بلا ثمن — ولا قفلَ جديدٌ في الترتيب العام
    await wallet.lock_wallet(session, referrer.id)

    if policy.monthly_cap is not None:
        if await _paid_this_month(session, referrer.id) >= policy.monthly_cap:
            return None

    amount = policy.amount_for(female_verified=progress.female_verified)
    if amount <= 0:  # pragma: no cover - يمنعه `pays`
        return None

    # محفظةٌ مجمَّدة لا تُستقبل فيها مكافأة؟ **بل تُستقبل**: التجميدُ يمنع
    # الإخراج، ومنعُ الإدخال يجعل الحقَّ يضيع لا يُؤجَّل
    entry = await wallet.record(
        session,
        owner=referrer,
        tx_type=WalletTransactionType.REFERRAL_BONUS,
        amount=amount,
        reference=f"مكافأة إحالة: {referral.code_used}",
        idempotency_key=f"referral:{referral.id}",
    )

    referral.rewarded_at = _now()
    referral.reward_amount = amount
    referral.reward_currency = currency_for_country(country).value
    referral.transaction_id = entry.id
    await session.flush()
    return referral


async def due_ids(session: AsyncSession, *, limit: int = 200) -> list[uuid.UUID]:
    """معرّفاتُ الإحالات غير المكافأة — مدخلُ المهمة الدورية.

    **تُقرأ بلا قفلٍ وتُدفع كلٌّ بقفلها**، والأقدمُ أولاً كي لا تُزاحَم إحالةٌ
    قديمةٌ بجديدة — وهو ما يجعل السقفَ يخدم من انتظر أطول.
    """
    rows = await session.scalars(
        select(Referral.id)
        .where(Referral.rewarded_at.is_(None))
        .order_by(Referral.created_at)
        .limit(limit)
    )
    return list(rows)


async def pay_due(session: AsyncSession) -> list[uuid.UUID]:
    """يدفع ما استحقّ ويعيد معرّفاتِ ما دُفع — لتُشعَر أصحابُها بعد الالتزام."""
    paid: list[uuid.UUID] = []
    for referral_id in await due_ids(session):
        if await pay(session, referral_id) is not None:
            await session.commit()
            paid.append(referral_id)
        else:
            # **تُنهى المعاملةُ حتى في حالة «لم يستحقّ»**: القفلُ الذي أخذه
            # `_locked` يبقى إلى نهاية المعاملة
            await session.rollback()
    return paid


async def ensure_settings(
    session: AsyncSession, country: CountryCode, referral_type: str
) -> ReferralSetting:
    """صفُّ برنامجٍ إن لم يكن — بقيمِ الافتراض (صفرٌ وحدُّ رحلاتِ نوعه)."""
    row = await settings_for(session, country, referral_type)
    if row is not None:
        return row
    row = ReferralSetting(
        country_code=country,
        referral_type=referral_type,
        required_rides=DEFAULT_REQUIRED_BY_TYPE.get(
            referral_type, DEFAULT_REQUIRED_RIDES
        ),
    )
    session.add(row)
    await session.flush()
    return row


async def update_settings(
    session: AsyncSession,
    *,
    country: CountryCode,
    referral_type: str,
    reward_amount: Decimal | None = None,
    required_rides: int | None = None,
    female_bonus_amount: Decimal | None = None,
    monthly_cap: int | None = None,
    clear_monthly_cap: bool = False,
    referred_promo_code_id: uuid.UUID | None = None,
) -> ReferralSetting:
    row = await ensure_settings(session, country, referral_type)
    if reward_amount is not None:
        if reward_amount < 0:
            raise InvalidInput("مبلغ المكافأة لا يكون سالباً")
        row.reward_amount = reward_amount
    if required_rides is not None:
        if required_rides < 0:
            raise InvalidInput("عدد الرحلات لا يكون سالباً")
        row.required_rides = required_rides
    if female_bonus_amount is not None:
        # **حارسُ المالك (2026-08-16)**: لا تُحفظ سالبةً — وهي تُضاف إلى الأساس
        # لا تحلّ محلَّه، فسالبُها كان سيخصم من مكافأةٍ استُحقّت
        if female_bonus_amount < 0:
            raise InvalidInput("علاوة الإحالة النسائية لا تكون سالبة")
        row.female_bonus_amount = female_bonus_amount
    # **و`NULL` تعني «بلا سقف» فتحتاج بابَها الصريح**: قيمةٌ غائبةٌ في الطلب
    # تعني «لا تلمسه»، وهما حالتان لا يحملهما حقلٌ واحد
    if clear_monthly_cap:
        row.monthly_cap = None
    elif monthly_cap is not None:
        if monthly_cap <= 0:
            raise InvalidInput("السقف الشهري يكون أكبر من صفر، أو بلا سقف")
        row.monthly_cap = monthly_cap
    if referred_promo_code_id is not None:
        row.referred_promo_code_id = referred_promo_code_id
    await session.flush()
    return row
