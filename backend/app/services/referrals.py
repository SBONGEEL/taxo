"""إحالةُ السائقات — الرمزُ والإسنادُ والاستحقاقُ والدفع (SPEC القسم 9.1، 12-ح).

**قرارُ المالك (2026-08-12)**: تُبنى الآليةُ والتتبّع، ومبلغُ الحافز حقلٌ في
الإعدادات قيمتُه صفرٌ حتى يحدّده، وشرطُ الاستحقاق ثلاثُ رحلاتٍ مكتملة. فيشحن
الملفُّ عاملاً وخامداً معاً: الرمزُ يُولَّد، والإسنادُ يُكتب، والعدُّ يُقرأ — ولا
قيدٌ يُكتب حتى يُحدَّد مبلغ.

**والاستحقاقُ مقارنةٌ حيّةٌ هنا لا عمودٌ في القاعدة**: تغييرُ الحدِّ من اللوحة
يعيد تقييمَ الجميع، بدل أن يترك صفوفاً وسمها حدٌّ قديم — نفسُ قاعدةِ «flagged»
في تقارير عدم تطابق الجنس. **والمدفوعُ وحده يُجمَّد**، لأن المالَ لا يُعاد
تقييمه.

**والرمزُ يُستهلك في التسجيل وحده**: لا مسارَ في هذا الملف يُسند إحالةً لحسابٍ
قائم. إسنادٌ رجعيٌّ («سجّلتُ الأسبوع الماضي، أضف رمز صديقتي») هو بابُ التلاعب
الوحيد الذي لا يُغلق بعد فتحه — من يملك حسابين يُحيل نفسه متى شاء.

**وترتيبُ الأقفال**: صفُّ الإحالة، ثم قفلُ المحفظة الاستشاري داخل
`wallet.record`. ولا صفَّ رحلةٍ ولا دفعةٍ في هذا المسار، فموضعُه في الترتيب
العامّ بين «صفِّ الطلب» و«قفلِ المحفظة» (`CLAUDE.md`).
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
    WalletTransactionType,
)
from app.models.referral import (
    DEFAULT_REQUIRED_RIDES,
    DEFAULT_REWARD_AMOUNT,
    DriverReferral,
    ReferralSetting,
)
from app.models.ride import Ride
from app.models.user import User
from app.services import settings_service, wallet

# أبجديةٌ بلا `0/O/1/I/L`: الرمزُ يُقرأ من شاشةٍ ويُنطق في مكالمةٍ ويُكتب في
# أخرى، وحرفان متشابهان يجعلان رمزاً صحيحاً يُرفض. **ونفسُها في الترحيلة**
# التي تولّد رموزَ القائمين — فرقٌ بينهما يعني أبجديتين لرمزٍ واحد
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


class ReferralCodeUnknown(NotFound):
    code = "referral_code_unknown"
    message = "رمز الإحالة غير صحيح"


class ReferralNotAllowed(Conflict):
    code = "referral_not_allowed"
    message = "لا يمكن استخدام رمز الإحالة"


def _now() -> datetime:
    return datetime.now(UTC)


def generate_code() -> str:
    """رمزٌ عشوائيٌّ للكبتن. والفرادةُ يحرسها الفهرس، وهذا يقلّل الاصطدام."""
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def normalize(code: str) -> str:
    """الرمزُ يُطبَّع كما يُطبَّع رمزُ الكوبون: يُقرأ من ملصقٍ ويُكتب بأي حالة."""
    return code.strip().upper()


# ------------------------------------------------------------ الإعدادات


async def settings_for(
    session: AsyncSession, country: CountryCode
) -> ReferralSetting | None:
    return await session.scalar(
        select(ReferralSetting).where(ReferralSetting.country_code == country)
    )


@dataclass(frozen=True)
class Policy:
    """سياسةُ دولةٍ كما تُقرأ لحظةَ السؤال — لا تُجمَّد إلا على مكافأةٍ دُفعت."""

    enabled: bool
    reward_amount: Decimal
    required_rides: int

    @property
    def pays(self) -> bool:
        """هل تُدفع مكافأةٌ فعلاً؟ **صفرٌ يعني «لم يُحدَّد»** لا «صفراً»."""
        return self.enabled and self.reward_amount > 0


async def policy_for(session: AsyncSession, country: CountryCode) -> Policy:
    row = await settings_for(session, country)
    return Policy(
        enabled=await settings_service.is_feature_enabled(
            session, country, FeatureKey.DRIVER_REFERRALS_ENABLED
        ),
        reward_amount=row.reward_amount if row else DEFAULT_REWARD_AMOUNT,
        required_rides=row.required_rides if row else DEFAULT_REQUIRED_RIDES,
    )


# ------------------------------------------------------------ الإسناد


async def by_code(session: AsyncSession, code: str) -> Driver | None:
    return await session.scalar(
        select(Driver).where(Driver.referral_code == normalize(code))
    )


async def attach(
    session: AsyncSession, *, referred: Driver, code: str
) -> DriverReferral:
    """يُسند إحالةً للكبتن المُسجَّل الآن. تُستدعى من مسار التسجيل وحده.

    **ولا تُفحص شروطُ الاستحقاق هنا**: الإسنادُ سجلٌّ لما وقع (سجّلت برمز
    فلانة)، والاستحقاقُ سؤالٌ يُطرح لاحقاً وقد يتغيّر جوابُه. وربطُهما يعني أن
    رمزاً في سوقٍ مطفأٍ اليوم يُهمل صامتاً — فإن أُشعل المفتاحُ غداً لم يبق
    أثرٌ لمن أحال من.
    """
    referrer = await by_code(session, code)
    if referrer is None:
        raise ReferralCodeUnknown()
    if referrer.id == referred.id:
        raise ReferralNotAllowed("لا يمكن إحالة نفسك")

    referral = DriverReferral(
        referrer_driver_id=referrer.id,
        referred_driver_id=referred.id,
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


async def completed_rides(session: AsyncSession, driver_id: uuid.UUID) -> int:
    """كم رحلةً أكملها هذا الكبتن. **يُعدّ في القاعدة** (القسم 14)."""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Ride)
            .where(Ride.driver_id == driver_id, Ride.status == RideStatus.COMPLETED)
        )
        or 0
    )


@dataclass(frozen=True)
class Progress:
    """أين وصلت إحالةٌ واحدة — لشاشة الكبتن ولجدول اللوحة.

    **جملةُ الحالة تُبنى في الواجهة من هذه الحقائق**، لا نصٌّ يأتي من الخلفية:
    نفسُ سببِ بناء نصِّ الإشعار من `data` (`services/notifications.py`).
    """

    referral: DriverReferral
    driver_approved: bool
    gender_ready: bool
    rides_done: int
    rides_required: int

    @property
    def rewarded(self) -> bool:
        return self.referral.rewarded_at is not None

    @property
    def qualifies(self) -> bool:
        return (
            self.driver_approved
            and self.gender_ready
            and self.rides_done >= self.rides_required
        )


async def progress_of(
    session: AsyncSession, referral: DriverReferral, *, required_rides: int
) -> Progress:
    referred = await session.get(Driver, referral.referred_driver_id)
    assert referred is not None  # مفتاحٌ أجنبيٌّ بـ CASCADE
    # **الجنسُ ووسمُه على `users` لا على `drivers`**: الأخيرُ يحمل تفضيلَ من
    # يحمل (`gender_preference`)، والجنسُ صفةُ الحساب — فحسابُ كبتنٍ امتدادٌ
    # لحساب مستخدم لا كيانٌ موازٍ له
    referred_user = await session.get(User, referred.user_id)
    assert referred_user is not None
    return Progress(
        referral=referral,
        driver_approved=referred.status is DriverStatus.APPROVED,
        # **الوسمُ لا الإقرار**: بلا `gender_verified_at` كلمةُ «سائقة» كلمةٌ
        # يكتبها أحدٌ عن نفسه — نفسُ قراءةِ التوفيق في المرحلة 10-ج. ومكافأةٌ
        # تُدفع على إقرارٍ غيرِ موثَّق مكافأةٌ على كلمة
        gender_ready=referred_user.gender is Gender.FEMALE
        and referred_user.gender_verified_at is not None,
        rides_done=await completed_rides(session, referred.id),
        rides_required=required_rides,
    )


async def progress_many(
    session: AsyncSession,
    referrals: list[DriverReferral],
    *,
    required_rides: int,
) -> dict[uuid.UUID, Progress]:
    """حالُ صفحةٍ كاملةٍ **باستعلامين لا باستعلامٍ لكل صف**.

    نفسُ شكلِ `ride_log.payment_summaries`: صفحةُ خمسين صفاً كانت تُصدر مئةً
    وخمسين رحلةَ ذهابٍ وعودة (كبتنٌ، ومستخدمٌ، وعدُّ رحلاتٍ لكلٍّ)، وهو ثمنٌ
    يُدفع على كل فتحةٍ لشاشةٍ تُقرأ ولا تُكتب.
    """
    if not referrals:
        return {}

    referred_ids = [row.referred_driver_id for row in referrals]

    # (١) حالُ الكبتنة وجنسُها ووسمُه — ضمٌّ واحد
    facts = {
        driver_id: (status, gender, verified)
        for driver_id, status, gender, verified in (
            await session.execute(
                select(
                    Driver.id, Driver.status, User.gender, User.gender_verified_at
                )
                .join(User, User.id == Driver.user_id)
                .where(Driver.id.in_(referred_ids))
            )
        ).all()
    }

    # (٢) عددُ الرحلات المكتملة لكلٍّ — تجميعٌ في القاعدة (القسم 14)
    counts = {
        driver_id: int(total)
        for driver_id, total in (
            await session.execute(
                select(Ride.driver_id, func.count())
                .where(
                    Ride.driver_id.in_(referred_ids),
                    Ride.status == RideStatus.COMPLETED,
                )
                .group_by(Ride.driver_id)
            )
        ).all()
    }

    out: dict[uuid.UUID, Progress] = {}
    for row in referrals:
        status, gender, verified = facts.get(
            row.referred_driver_id, (None, None, None)
        )
        out[row.id] = Progress(
            referral=row,
            driver_approved=status is DriverStatus.APPROVED,
            gender_ready=gender is Gender.FEMALE and verified is not None,
            rides_done=counts.get(row.referred_driver_id, 0),
            rides_required=required_rides,
        )
    return out


async def list_for_referrer(
    session: AsyncSession, *, driver: Driver, country: CountryCode
) -> tuple[Policy, list[Progress]]:
    """إحالاتُ كبتنٍ بحالتها — لشاشة حسابه."""
    policy = await policy_for(session, country)
    rows = (
        await session.scalars(
            select(DriverReferral)
            .where(DriverReferral.referrer_driver_id == driver.id)
            .order_by(DriverReferral.created_at.desc())
        )
    ).all()
    progresses = await progress_many(
        session, list(rows), required_rides=policy.required_rides
    )
    return policy, [progresses[row.id] for row in rows]


async def rewarded_total(session: AsyncSession, driver_id: uuid.UUID) -> Decimal:
    """مجموعُ ما قبضه كبتنٌ من مكافآت — **يُجمع في القاعدة** (القسم 14)."""
    return Decimal(
        await session.scalar(
            select(func.coalesce(func.sum(DriverReferral.reward_amount), 0)).where(
                DriverReferral.referrer_driver_id == driver_id,
                DriverReferral.rewarded_at.is_not(None),
            )
        )
        or 0
    )


# ------------------------------------------------------------ الدفع


async def _locked(session: AsyncSession, referral_id: uuid.UUID) -> DriverReferral:
    """يقرأ صفَّ الإحالة **مقفولاً** قبل فحص «هل دُفعت».

    وبغير القفل تمرّ دورتان متزامنتان من المهمة الدورية على صفٍّ واحد، فتقرآن
    `rewarded_at IS NULL` كلتاهما وتكتبان مكافأتين — ومفتاحُ تكرارِ الدفتر يمنع
    القيدَ الثاني لكنه **لا يمنع** الصفَّ من أن يُكتب مرتين بمبلغين، ولا يمنع
    استثناءً يُفشل الدورة كلَّها. والاختبارُ يفشل بحذف `with_for_update`.
    """
    row = await session.scalar(
        select(DriverReferral)
        .where(DriverReferral.id == referral_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:  # pragma: no cover - صفٌّ محذوف
        raise NotFound("الإحالة غير موجودة")
    return row


async def pay(session: AsyncSession, referral_id: uuid.UUID) -> DriverReferral | None:
    """يدفع مكافأةَ إحالةٍ إن استحقّت. الـcommit للمستدعي.

    يعيد `None` إن لم تستحقّ أو كانت مدفوعة — فالمهمةُ الدورية تمرّ على صفوفٍ
    كثيرةٍ وأكثرُها ليس جاهزاً، وذلك حالةٌ عادية لا خطأ.
    """
    referral = await _locked(session, referral_id)
    if referral.rewarded_at is not None:
        return None

    referrer = await session.get(Driver, referral.referrer_driver_id)
    assert referrer is not None
    referrer_user = await session.get(User, referrer.user_id)
    assert referrer_user is not None

    # **دولةُ المُحيلة هي الحاكمة**: المالُ يدخل محفظتَها، وعملتُه عملةُ بلدها.
    # ولو حُكمت بدولة المُحالة لدُفع بعملةٍ لا تُنفق في محفظةٍ أخرى
    country = referrer_user.country_code
    policy = await policy_for(session, country)
    if not policy.pays:
        return None

    progress = await progress_of(
        session, referral, required_rides=policy.required_rides
    )
    if not progress.qualifies:
        return None

    # محفظةٌ مجمَّدة لا تُستقبل فيها مكافأة؟ **بل تُستقبل**: التجميدُ يمنع
    # الإخراج (`wallet.require_not_frozen` على مسارات الخروج)، ومنعُ الإدخال
    # يجعل الحقَّ يضيع لا يُؤجَّل. والمالُ يبقى محجوزاً حتى يُرفع التجميد
    entry = await wallet.record(
        session,
        owner=referrer_user,
        tx_type=WalletTransactionType.REFERRAL_BONUS,
        amount=policy.reward_amount,
        reference=f"مكافأة إحالة: {referral.code_used}",
        idempotency_key=f"referral:{referral.id}",
    )

    referral.rewarded_at = _now()
    referral.reward_amount = policy.reward_amount
    referral.reward_currency = currency_for_country(country).value
    referral.transaction_id = entry.id
    await session.flush()
    return referral


async def due_ids(session: AsyncSession, *, limit: int = 200) -> list[uuid.UUID]:
    """معرّفاتُ الإحالات غير المكافأة — مدخلُ المهمة الدورية.

    **تُقرأ بلا قفلٍ وتُدفع كلٌّ بقفلها**: قفلُ مئتي صفٍّ في معاملةٍ واحدة يجعل
    دورةً واحدةً تعطّل غيرَها، والدفعُ نفسُه هو ما يجب أن يكون ذرّياً — لا
    قائمةُ المرشَّحين. وترتيبُ الأقدمِ أولاً كي لا تتأخّر إحالةٌ خلف زحمةٍ جديدة.
    """
    rows = await session.scalars(
        select(DriverReferral.id)
        .where(DriverReferral.rewarded_at.is_(None))
        .order_by(DriverReferral.created_at)
        .limit(limit)
    )
    return list(rows)


async def pay_due(session: AsyncSession) -> int:
    """يدفع ما استحقّ ويعيد عددَ المدفوع. تُستدعى من `tasks/referrals.py`."""
    paid = 0
    for referral_id in await due_ids(session):
        if await pay(session, referral_id) is not None:
            await session.commit()
            paid += 1
        else:
            # **تُنهى المعاملةُ حتى في حالة «لم يستحقّ»**: القفلُ الذي أخذه
            # `_locked` يبقى إلى نهاية المعاملة، وحملُه على مئتي صفٍّ إلى آخر
            # الدورة يمنع كلَّ ما يمسّها
            await session.rollback()
    return paid


async def ensure_settings(
    session: AsyncSession, country: CountryCode
) -> ReferralSetting:
    """صفُّ إعداداتٍ لدولةٍ إن لم يكن — بقيمِ الافتراض (صفرٌ وثلاث رحلات)."""
    row = await settings_for(session, country)
    if row is not None:
        return row
    row = ReferralSetting(country_code=country)
    session.add(row)
    await session.flush()
    return row


async def update_settings(
    session: AsyncSession,
    *,
    country: CountryCode,
    reward_amount: Decimal | None = None,
    required_rides: int | None = None,
) -> ReferralSetting:
    row = await ensure_settings(session, country)
    if reward_amount is not None:
        if reward_amount < 0:
            raise InvalidInput("مبلغ المكافأة لا يكون سالباً")
        row.reward_amount = reward_amount
    if required_rides is not None:
        if required_rides < 0:
            raise InvalidInput("عدد الرحلات لا يكون سالباً")
        row.required_rides = required_rides
    await session.flush()
    return row
