"""تحصيلُ رسم الإلغاء — **نقلُ مالٍ بين مستخدمَين، لا دخلٌ للمنصّة**.

المواصفةُ كاملةً في `design/CANCELLATION-FEE.md` وقراراتُ المالك في قسمها ١١.
وما يلي هو ما يجعلها قابلةً للمراجعة في مكانٍ واحد:

* **من يقبض: الكبتن** — هو من تحرّك وأنفق وقتاً ووقوداً، والشركةُ لم تخسر
  شيئاً. ورسمٌ يذهب لمن لم يتضرر **غرامةٌ لا تعويض**، ومن هذا الفرق تأتي كلُّ
  قاعدةِ إعفاءٍ هنا.
* **والإعفاءُ بالقرب لا بالسببِ المكتوب**: كبتنٌ لم يبرح مكانَه لم يُتعِب
  أحداً، ويُقاس القربُ **من آخر موقعٍ مبثوث** لا من موقعه لحظةَ القبول — من
  قَبِل بعيداً ثم قطع نصفَ الطريق تحرّك فعلاً.
* **وبلا موقعٍ مبثوثٍ يُعفى الراكب** (قرارُ المالك، الفرع أ): لا دليلَ على
  تحرّك، والشكُّ لمن سيُخصم منه، ومن تحرّك يعترض في اللوحة.
* **ولا يُرفض الإلغاء لفراغ المحفظة أبداً**: راكبٌ لا يستطيع الإلغاءَ لخلوّ
  رصيده يبقى في سيارةٍ لا يريدها أو يترك كبتناً ينتظر بلا قرار — وكلاهما أسوأُ
  من دَينٍ مكتوب. فالتحصيلُ **يُحاوَل** عند الإلغاء، وما تعذّر بقي `pending`.
* **والقيدان اثنان لا واحدٌ صافٍ**: `cancellation_fee` على الراكب و
  `cancellation_compensation` للكبتن. وقيدٌ صافٍ يعطي الرقمَ نفسَه ويُخفي أن
  للمال طرفَين — وهي قاعدةُ فصلِ `ride_earning` عن `commission` منذ 6-أ.

**والفشلُ لا يُسقط الإلغاء**: من ضغط «ألغِ» أُلغيت رحلتُه. تعذُّرُ كتابة الرسم
يترك الصفَّ `pending` — أما استثناءٌ يرتدّ من `cancel_ride` فيترك راكباً في
رحلةٍ ظنّ أنه خرج منها.
"""

from __future__ import annotations

import logging
import math
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.cancellation import (
    DEFAULT_BLOCK_AFTER_UNPAID,
    DEFAULT_CARRIER_GRACE_HOURS,
    DEFAULT_EXEMPT_WITHIN_METERS,
    DEFAULT_UNPAID_AFTER_DAYS,
    CancellationSetting,
    RideCancellationCharge,
)
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    CancellationChargeStatus,
    CountryCode,
    PaymentMethod,
    UnpaidCancellationOutcome,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.payment import DIRECTLY_COLLECTED_METHODS, WALLET_FUNDED_METHODS
from app.models.ride import Ride
from app.models.user import User
from app.services import audit, geo, wallet
from app.services.pricing import round_money

logger = logging.getLogger(__name__)

ZERO = Decimal("0.000")
EARTH_RADIUS_M = 6_371_000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _metres_between(a: geo.Position, b_lat: float, b_lng: float) -> float:
    """مسافةٌ بالأمتار — حسابُ **مسافةٍ لا مال**، فمكانُه هنا لا في القاعدة.

    والقسم 14 يمنع حسابَ المال في غير الخلفية؛ وهذا حسابٌ هندسيٌّ يقرّر شرطاً
    ثم يُنسى، ولا يظهر رقمُه في شاشةٍ ولا في قيد.
    """
    lat1, lat2 = math.radians(a.lat), math.radians(b_lat)
    d_lat = lat2 - lat1
    d_lng = math.radians(b_lng - a.lng)
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


# ------------------------------------------------------------------ الإعدادات


async def settings_for(
    session: AsyncSession, country: CountryCode
) -> CancellationSetting:
    """سياسةُ الدولة — **وصفٌّ غائبٌ يُقرأ بالافتراضات لا بالمنع**.

    غيابُ الصف حالُ تركيبٍ جديدٍ قبل البذر، وقراءتُه «لا إعفاءَ بالقرب» تجعل
    أولَ إلغاءٍ في سوقٍ جديد يُحصَّل بلا شرطٍ راجعه أحد.
    """
    row = await session.get(CancellationSetting, country)
    if row is not None:
        return row
    return CancellationSetting(
        country_code=country,
        exempt_within_meters=DEFAULT_EXEMPT_WITHIN_METERS,
        exempt_when_location_unknown=True,
        block_after_unpaid=DEFAULT_BLOCK_AFTER_UNPAID,
        carrier_grace_hours=DEFAULT_CARRIER_GRACE_HOURS,
        unpaid_after_days=DEFAULT_UNPAID_AFTER_DAYS,
        unpaid_outcome=UnpaidCancellationOutcome.KEEP_PENDING,
    )


# ------------------------------------------------------------------ الاستحقاق


async def is_exempt_by_proximity(
    redis: Redis, *, ride: Ride, driver_id: uuid.UUID, policy: CancellationSetting
) -> bool:
    """هل بقي الكبتنُ قريباً فلم يُتعِب أحداً — أم لا موقعَ يُقاس عليه.

    **الحالتان تنتهيان إلى الإعفاء ولا تُخلطان في الشرح**: «لم يتحرك» واقعةٌ
    مقيسة، و«لا نعرف» جهلٌ يُفسَّر لصالح من سيُخصم منه (قرارُ المالك).
    """
    position = await geo.last_position(
        redis, driver_id=driver_id, country_code=ride.country_code
    )
    if position is None:
        return policy.exempt_when_location_unknown
    metres = _metres_between(position, ride.pickup_lat, ride.pickup_lng)
    return metres <= policy.exempt_within_meters


async def charge_for(
    session: AsyncSession,
    redis: Redis,
    *,
    ride: Ride,
    fee: Decimal,
) -> RideCancellationCharge | None:
    """يكتب صفَّ الرسم إن استُحقّ — ثم **يحاول** تحصيله فوراً.

    يُنادى من `rides.cancel_ride` **بعد** تجميد `cancellation_fee` على الرحلة
    وقبل الالتزام، فيقع كلُّ شيءٍ في معاملة الإلغاء نفسِها: إلغاءٌ يقع ورسمٌ
    لا يُكتب هو العطبُ الذي وُجد هذا الملفُّ لإصلاحه، ولا يجوز أن يعود من باب
    الالتزام المنفصل.
    """
    if fee <= ZERO or ride.driver_id is None:
        return None

    policy = await settings_for(session, ride.country_code)
    if await is_exempt_by_proximity(
        redis, ride=ride, driver_id=ride.driver_id, policy=policy
    ):
        # **ويُصفَّر على الرحلة أيضاً**: رقمٌ مجمَّدٌ بلا صفِّ تحصيلٍ هو بعينه
        # العطبُ القديم — «مدينٌ بلا باب» يقرؤه الراكبُ في شاشة التفاصيل.
        #
        # **والقراءةُ بعده لا تُترك**: `pickup_lat`/`dropoff_lat` تعبيراتُ
        # `column_property` تحسبها القاعدة، وأيُّ UPDATE على الصف يُبطلها —
        # فيحاول المُسلسِلُ تحميلَها كسولاً خارج سياق async ويرمي
        # `MissingGreenlet`. وهذا هو الفخُّ الذي وُجدت له `_flush_and_reload`،
        # ووقع هنا فعلاً: أولُ تشغيلٍ للاختبار أعاد 500 على إلغاءٍ **معفيّ**
        ride.cancellation_fee = ZERO
        await session.flush()
        await session.refresh(ride)
        return None

    charge = RideCancellationCharge(
        ride_id=ride.id,
        payer_user_id=ride.rider_id,
        beneficiary_driver_id=ride.driver_id,
        amount=round_money(fee),
        currency=ride.currency,
        status=CancellationChargeStatus.PENDING,
    )
    session.add(charge)
    await session.flush()

    await try_collect(session, charge)
    return charge


# ------------------------------------------------------------------ التحصيل


async def _beneficiary_user(
    session: AsyncSession, charge: RideCancellationCharge
) -> User | None:
    """صاحبُ محفظة المتضرر: `users.id` لا `drivers.id` (SPEC القسم 4)."""
    driver = await session.get(Driver, charge.beneficiary_driver_id)
    if driver is None:  # pragma: no cover - حذفُ حسابٍ نادر
        return None
    return await session.get(User, driver.user_id)


async def _move(
    session: AsyncSession,
    charge: RideCancellationCharge,
    *,
    payer: User,
    beneficiary: User,
    collected_from_ride_id: uuid.UUID | None,
) -> bool:
    """قيدان بين محفظتَين، أو لا شيءَ ويبقى الصفُّ معلّقاً.

    **والقفلُ قبل قراءة الرصيد، لا بعدها**: قراءةٌ ثم قرارٌ ثم كتابةٌ ليست
    ذرّيةً وحدَها — وخصمان متزامنان على رصيدٍ يكفي أحدَهما يقرآن الرقمَ نفسَه
    فيمرّان معاً، ثم يرمي `wallet.record` عند الثاني `InsufficientBalance`
    **داخل مسار الإلغاء أو مسار الدفع** فيرتدّ ما لا علاقةَ له بالرسم. وهذا
    الترتيبُ هو ما يجعل الثاني يرى الرصيدَ بعد الأول فيعود `False` ويبقى
    ديناً — وهو الجواب لا الخطأ.

    وترتيبُ القفلين بالـUUID المرتَّب: قاعدةُ `wallet._lock_wallets` نفسُها،
    وبدونها يتقابل خصمان متزامنان على محفظتين في اتجاهين متعاكسين.
    """
    await wallet.lock_wallets(session, payer.id, beneficiary.id)

    # **والمحفظةُ الواحدة حالٌ واقعة**: كبتنٌ قبض نقداً رسمَ إلغاءٍ مستحقٍّ
    # **له هو** (راكبٌ ألغى عليه ثم ركب معه). القيدان يُكتبان كما يُكتبان
    # لغيره — صافيهما صفر، لكنّ حذفَ أحدهما يجعل الدفترَ يقول إنه قبض بلا أن
    # يُسلِّم أو سلّم بلا أن يقبض. **والترتيبُ يُعكس وحدَه**: الدائنُ أولاً كي
    # لا يرفض `balance_after >= 0` خصماً يغطّيه الدائنُ الذي لم يُكتب بعد
    same_wallet = payer.id == beneficiary.id
    # **المحفظةُ التي يُقرأ رصيدُها هي التي يُكتب عليها القيد** (`debit` أدناه) —
    # كانت القراءةُ بلا إعلان، فمدينٌ بدورين أسقط الإلغاءَ كلَّه ٤٠٩ (عطبُ رحلاتٍ
    # قائمٌ منذ `7bea224`، `SPEC-DELIVERY.md` §D6). ومتغيّرٌ واحدٌ للقراءة والكتابة
    payer_wallet = (
        WalletOwnerType.DRIVER
        if charge.carrier_driver_id is not None
        else WalletOwnerType.RIDER
    )
    if (
        not same_wallet
        and await wallet.balance_of(session, payer, declared=payer_wallet)
        < charge.amount
    ):
        return False

    key = f"cancellation:{charge.id}"

    async def credit() -> None:
        await wallet.record(
            session,
            owner=beneficiary,
            # **المتضرِّرُ كبتنٌ بالبناء**: `beneficiary_driver_id` عمودُ كبتن
            # يُملأ من `ride.driver_id` ويُقرأ عبر `Driver` — فالتعويضُ يدخل
            # محفظةَ الكبتن، وهي التي يُسحب منها
            owner_type=WalletOwnerType.DRIVER,
            tx_type=WalletTransactionType.CANCELLATION_COMPENSATION,
            amount=charge.amount,
            ride_id=charge.ride_id,
            idempotency_key=key,
        )

    async def debit() -> None:
        await wallet.record(
            session,
            owner=payer,
            # **المدينُ يتبدّل، والصفُّ يختمه لا الدور**: بعد تسليمٍ نقديٍّ
            # يصير المطلوبُ من **الحامل** (كبتن)، وقبله من الراكب — وهو ما
            # يقرأه `_debtor_user` من `carrier_driver_id`. فالمحفظةُ تُشتقّ من
            # الختم نفسِه، **فلا تفترق قراءتان لصفٍّ واحد** — ولا القراءةُ
            # والكتابة: المتغيّرُ نفسُه الذي قرأ الرصيدَ أعلاه
            owner_type=payer_wallet,
            tx_type=WalletTransactionType.CANCELLATION_FEE,
            amount=-charge.amount,
            ride_id=charge.ride_id,
            idempotency_key=f"{key}:paid",
        )

    if same_wallet:
        await credit()
        await debit()
    else:
        await debit()
        await credit()

    charge.status = CancellationChargeStatus.SETTLED
    charge.settled_at = _now()
    if collected_from_ride_id is not None:
        charge.collected_from_ride_id = collected_from_ride_id
    await session.flush()
    return True


async def try_collect(
    session: AsyncSession,
    charge: RideCancellationCharge,
    *,
    collected_from_ride_id: uuid.UUID | None = None,
) -> bool:
    """يخصم **ممّن عليه الآن** ويقيّد للمتضرر، أو يترك الصفَّ معلّقاً.

    و«من عليه الآن» ليس دائماً الراكب: بعد أن يُسنَد الصفُّ إلى **حاملٍ**
    (القسم ٦-أ) يكون الراكبُ قد سلّم المبلغَ نقداً وصار المطلوبُ تحويلَه من
    يد الحامل — فالقراءةُ من `carrier_driver_id` لا من `payer_user_id` وحده.
    """
    if charge.status is not CancellationChargeStatus.PENDING:
        return False

    payer = await _debtor_user(session, charge)
    beneficiary = await _beneficiary_user(session, charge)
    if payer is None or beneficiary is None:  # pragma: no cover - حذفُ حسابٍ نادر
        return False

    return await _move(
        session,
        charge,
        payer=payer,
        beneficiary=beneficiary,
        collected_from_ride_id=collected_from_ride_id,
    )


async def _debtor_user(
    session: AsyncSession, charge: RideCancellationCharge
) -> User | None:
    """من يُخصم منه هذا الصفُّ الآن — الحاملُ إن وُجد، وإلا الراكب."""
    if charge.carrier_driver_id is not None:
        carrier = await session.get(Driver, charge.carrier_driver_id)
        if carrier is None:  # pragma: no cover
            return None
        return await session.get(User, carrier.user_id)
    return await session.get(User, charge.payer_user_id)


# ------------------------------------------------------------------ القراءة


def _rider_debt_predicate(user_id: uuid.UUID):
    """ما زال **على الراكب**: معلّقٌ ولم يُسلَّم إلى حاملٍ بعد.

    **وشرطُ `carrier_driver_id IS NULL` ليس تجميلاً**: من سلّم المبلغَ نقداً مع
    أجرة رحلته سدَّد فعلاً، والصفُّ بقي معلّقاً لأن **الحاملَ** لم يحوّله بعد.
    فعدُّه على الراكب يمنعه من الطلب بدَينٍ دفعه بيده — وهو أسوأُ ما يمكن أن
    يفعله حدُّ الإيقاف.
    """
    return (
        RideCancellationCharge.payer_user_id == user_id,
        RideCancellationCharge.status == CancellationChargeStatus.PENDING,
        RideCancellationCharge.carrier_driver_id.is_(None),
    )


async def debt_of(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """ما على راكبٍ من رسومِ إلغاءٍ لم تُحصَّل — **مجموعٌ يُقرأ لا عمودٌ يُخزَّن**.

    قاعدةُ «لا عمودَ رصيد» نفسُها: عمودٌ يخزّن مجموعاً يفترق عن مجموعه أوَّلَ
    صفٍّ يُكتب بلا تحديثه.
    """
    total = await session.scalar(
        select(func.coalesce(func.sum(RideCancellationCharge.amount), 0)).where(
            *_rider_debt_predicate(user_id)
        )
    )
    return round_money(Decimal(total or 0))


async def carrier_dues_of(session: AsyncSession, driver_id: uuid.UUID) -> Decimal:
    """ما في يد كبتنٍ من مالِ كبتنٍ آخر (§6-أ) — **لا أجرةٌ ولا خصمٌ عليه**.

    ويُطرح من **المتاح للسحب** كما يُطرح المحتجَز: مالٌ قبضه ولم يحوّله ليس
    مالَه، وسحبُه يجعل المنصّةَ تدفع لكبتنٍ ما تعرف أنه عند غيره.
    """
    total = await session.scalar(
        select(func.coalesce(func.sum(RideCancellationCharge.amount), 0)).where(
            RideCancellationCharge.carrier_driver_id == driver_id,
            RideCancellationCharge.status == CancellationChargeStatus.PENDING,
        )
    )
    return round_money(Decimal(total or 0))


async def pending_for_driver(
    session: AsyncSession, driver_id: uuid.UUID
) -> Decimal:
    """مستحقاتٌ **معلّقة** لكبتن: تُعرض ولا تدخل الرصيدَ المتاح.

    رصيدٌ يشمل مالاً لم يصل يكذب على صاحبه — وهي قاعدةُ الرصيد المحتجَز في
    البند ١٣ نفسُها، ولذلك لا يُكتب لها قيدٌ في الدفتر: القيدُ يعني مالاً وصل.
    """
    total = await session.scalar(
        select(func.coalesce(func.sum(RideCancellationCharge.amount), 0)).where(
            RideCancellationCharge.beneficiary_driver_id == driver_id,
            RideCancellationCharge.status == CancellationChargeStatus.PENDING,
        )
    )
    return round_money(Decimal(total or 0))


async def unpaid_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    """عددُ الرسوم القائمة — عليه يقوم إيقافُ الطلب عند التكرار (القسم ٤)."""
    total = await session.scalar(
        select(func.count()).where(*_rider_debt_predicate(user_id))
    )
    return int(total or 0)


async def pending_charges_of_payer(
    session: AsyncSession, user_id: uuid.UUID, *, for_update: bool = False
) -> Sequence[RideCancellationCharge]:
    """رسومُ راكبٍ القائمة، **أقدمُها أولاً** — من انتظر أطولَ يُنصف أولاً.

    وتُقرأ مقفولةً في مسار التحصيل: بغير القفل يقرأ نداءان متزامنان الصفَّ
    نفسَه معلّقاً فيحاولان تحصيلَه معاً.
    """
    query = (
        select(RideCancellationCharge)
        .where(*_rider_debt_predicate(user_id))
        .order_by(RideCancellationCharge.created_at, RideCancellationCharge.id)
    )
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await session.scalars(query)).all()


async def collect_with_ride(
    session: AsyncSession,
    *,
    ride: Ride,
    rider: User,
    method: PaymentMethod,
) -> list[RideCancellationCharge]:
    """السدادُ مع رحلةٍ لاحقة (§5) — **والقاعدةُ تنقسم بحسب من يقبض (§6)**.

    يُنادى من `payments.settle` **بعد** قيود الأجرة كلِّها، وموضعُه ذاك هو
    الفرعُ (و) بعينه: «العمولةُ أولاً — حقُّ المنصّة على رحلةٍ وقعت، والدَّينُ
    يبقى مطلوباً». وبالقياس نفسِه أجرةُ الكبتن الحاليِّ قبل دَينِ الأمس.

    **ولا قيدَ واحدٌ صافٍ ولا ضمٌّ للأجرة** (§5، بنصِّ المالك): ضمُّ المبلغ إلى
    الأجرة يجعل أرقامَ الكبتن تكذب عليه، **ويحسب عمولةً على مالٍ لا يخصّه**،
    **ويُخفي أن صاحبَ الدَّين كبتنٌ آخر**. ولذلك لا يزيد `payment.amount` ولا
    يُكتب صفُّ دفعةٍ ثانٍ: قيدان في الدفتر، وطرفاهما مسمَّيان في `charge`.

    وثلاثةُ مساراتٍ بحسب القناة:

    * **كاشٌ وكليك** (`DIRECTLY_COLLECTED_METHODS`): الراكبُ سلّم الأجرةَ
      **والدَّينَ معها** بيده، فالمالُ عند الكبتن الحالي — يصير **حاملاً**،
      وتُخصم القيمةُ من محفظته وتُقيَّد للمتضرر (آليةُ عمولة رحلة الكاش نفسُها).
    * **المحفظة**: مالُ الراكب في المنصّة، فالخصمُ منه مباشرةً — ولا يقع إلا
      إن بقي في رصيده بعد الأجرة ما يغطّيه، وإلا بقي ديناً.
    * **البطاقة**: القناةُ الوحيدةُ التي **لا تحمل الدَّين في هذا الإصدار**، ولا
      يقع فيها شيء. وسببُه مكتوبٌ لئلا يُقرأ سهواً: مبلغُ الشحنة عند المزوّد
      هو `payment.amount` نفسُه، ورفعُه بقيمة الدَّين يجعل `ride_earning` و
      `commission` — وكلاهما يُحسب من `payment.amount` — يقعان على مالٍ ليس
      أجرةً؛ وصفُّ دفعةٍ ثانٍ يُقيَّد `ride_earning` **للكبتن الحالي** لا
      للمتضرر. وكلاهما ما يمنعه §5 حرفاً. فيبقى الدَّينُ حتى أوّل رصيدٍ يدخل
      محفظتَه (شحنٌ أو رحلةٌ تُدفع منها)، وحدُّ الإيقاف هو ما يحرس المُصِرّ.
    """
    # **القناةُ تُفحص قبل الاستعلام لا بعده**: القراءةُ تحت `FOR UPDATE`، فقفلُ
    # صفوفِ راكبٍ ثم إعادةُ لا شيء يحبسها إلى آخر المعاملة بلا سبب. وقنواتُ
    # المنصّة (`promo` و`share`) تدخل هذا الباب في كل رحلةٍ فيها كوبونٌ أو
    # مشاركة، فهي أكثرُ الداخلين لا أندرُهم
    if method not in DIRECTLY_COLLECTED_METHODS and method not in WALLET_FUNDED_METHODS:
        return []

    charges = await pending_charges_of_payer(session, rider.id, for_update=True)
    if not charges:
        return []

    if method in DIRECTLY_COLLECTED_METHODS:
        if ride.driver_id is None:  # pragma: no cover - رحلةٌ مكتملةٌ لها كبتن
            return []
        policy = await settings_for(session, ride.country_code)
        collected = []
        for charge in charges:
            await _hand_to_carrier(session, charge, ride=ride, policy=policy)
            collected.append(charge)
        return collected

    if method in WALLET_FUNDED_METHODS:
        return [
            charge
            for charge in charges
            if await try_collect(session, charge, collected_from_ride_id=ride.id)
        ]

    return []


async def _hand_to_carrier(
    session: AsyncSession,
    charge: RideCancellationCharge,
    *,
    ride: Ride,
    policy: CancellationSetting,
) -> bool:
    """الكبتنُ الحاليُّ قبض بيده ما ليس كلُّه له (§6-أ) — فصار حاملاً.

    **والإسنادُ يقع سواءٌ تمّ التحويلُ أم لا**، وهذا هو مربطُ الفرس: الراكبُ
    سلّم المبلغَ نقداً، فذمّتُه بَرِئت في اللحظة نفسِها ولو كان رصيدُ الحامل
    صفراً — وبقاءُ الصفِّ «على الراكب» بعدها يمنعه من الطلب بدَينٍ دفعه بيده.

    **والمهلةُ تُجمَّد الآن** من سياسة الدولة، كـ`cliq_confirmation_expires_at`:
    تقصيرُها في اللوحة غداً لا يُقصّر مهلةً ينظر إليها كبتنٌ في شاشته اليوم.
    وصفرُ الساعات «لا مهلةَ ولا منع» — فلا يُكتب تاريخٌ أصلاً.
    """
    charge.carrier_driver_id = ride.driver_id
    charge.carrier_assigned_at = _now()
    charge.collected_from_ride_id = ride.id
    charge.carrier_due_at = (
        _now() + timedelta(hours=policy.carrier_grace_hours)
        if policy.carrier_grace_hours > 0
        else None
    )
    await session.flush()
    return await try_collect(session, charge)


async def collect_from_carrier(
    session: AsyncSession, *, driver: Driver
) -> list[RideCancellationCharge]:
    """يحوّل ما في يد الحامل **لحظةَ أن يصير رصيدُه كافياً** (§7).

    «فوريٌّ كلما دخل المالُ المنصّة»: يُنادى بعد كل شحنٍ اكتمل، فلا مراجعةَ
    إداريةٌ ولا دورةٌ مجدولةٌ تؤخّر مالاً وصل فعلاً.

    **ويرفع المنعَ في المسار نفسِه** لا بالدورة التالية: من شحن وبقي ممنوعاً
    عشر دقائق يقرأ الشحنَ بلا أثر — قاعدةُ `advances._settle_if_clear` نفسُها.
    """
    rows = (
        await session.scalars(
            select(RideCancellationCharge)
            .where(
                RideCancellationCharge.carrier_driver_id == driver.id,
                RideCancellationCharge.status == CancellationChargeStatus.PENDING,
            )
            .order_by(RideCancellationCharge.carrier_assigned_at)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()

    settled = [charge for charge in rows if await try_collect(session, charge)]
    if driver.cancellation_carry_blocked and len(settled) == len(rows):
        driver.cancellation_carry_blocked = False
        await session.flush()
    return settled


async def collect_own_debt(
    session: AsyncSession, *, rider: User
) -> list[RideCancellationCharge]:
    """يحصّل ما على راكبٍ لحظةَ أن يدخل محفظتَه مال (§7).

    وهو ما يجعل القناةَ التي لا تحمل الدَّين (البطاقة) بلا بابٍ مسدود: من شحن
    محفظته سدَّد، ومن دفع منها سدَّد — ولا يبقى الدَّينُ إلا لمن لا يفعل أيّاً
    من الاثنين، وهو من وُضع له حدُّ الإيقاف.
    """
    charges = await pending_charges_of_payer(session, rider.id, for_update=True)
    return [charge for charge in charges if await try_collect(session, charge)]


async def on_wallet_funded(
    session: AsyncSession, *, user: User
) -> list[RideCancellationCharge]:
    """**بابٌ واحدٌ لكل شحنٍ اكتمل** (§7) — «فوريٌّ كلما دخل المالُ المنصّة».

    يُنادى من مساراتِ الشحن الثلاثة (اليدويُّ من اللوحة، وكليك الآلي،
    والبطاقة)، ويقرّر بحسب صاحب المحفظة: راكبٌ يسدّد ما عليه، وكبتنٌ يحوّل ما
    في يده. **وثلاثةُ نداءاتٍ في ثلاثة مساراتٍ بابٌ واحد** لأن القرارَ هنا لا
    هناك — ولو تكرّر لصار قاعدةً يذكرها مسارٌ وينساها مسار.

    ولا يُفشل الشحنَ أبداً: من شحن محفظته شُحنت، وما تعذّر تحصيلُه يبقى ديناً.
    """
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is not None:
        return await collect_from_carrier(session, driver=driver)
    return await collect_own_debt(session, rider=user)


async def blocks_new_ride(
    session: AsyncSession, *, user_id: uuid.UUID, country: CountryCode
) -> bool:
    """هل بلغ الراكبُ حدَّ الإيقاف — **مقارنةٌ حيّةٌ لا عمودٌ موسوم**.

    فخفضُ الحدِّ في اللوحة أو رفعُه يُعيد تقييمَ الجميع بلا لمس صف، وسدادُ
    الدَّين يرفع المنعَ من نفسه — قاعدةُ «flagged» في تقارير عدم التطابق
    واستحقاقِ الإحالة نفسُها.
    """
    policy = await settings_for(session, country)
    if policy.block_after_unpaid <= 0:
        return False
    return await unpaid_count(session, user_id) >= policy.block_after_unpaid


# ------------------------------------------------------------------ الإشعار

# مفتاحُ «قيل مرة» — **إشعارٌ حدثٌ لا سجلّ**، فلا عمودَ له كتنبيه الاشتراك
# قبل ٢٤ ساعة. وعمرُه يوم: ما بعده لا يعود أحدٌ يستدعي المسارَ نفسَه
ANNOUNCED_TTL_SECONDS = 86_400


async def _say_once(redis: Redis, key: str) -> bool:
    """يمنع تكرارَ خبرٍ واحد — ويعود `False` إن سبق أن قيل."""
    return bool(
        await redis.set(
            f"cancellation:said:{key}", "1", nx=True, ex=ANNOUNCED_TTL_SECONDS
        )
    )


async def announce_ride_collection(
    session: AsyncSession, redis: Redis, *, ride_id: uuid.UUID
) -> None:
    """يخبر أطرافَ ما وقع على هذه الرحلة من رسومٍ سابقة — **بعد الالتزام**.

    وموضعُه في الراوتر بعد `commit` لا داخلَ `payments.settle`: حالٌ تُعلَن قبل
    التزامها قد ترتدّ، فيقرأ كبتنٌ أن مالاً وصله ولم يصل. وهي قاعدةُ
    `publish_ride_event` نفسُها منذ المرحلة 4.

    ويُقرأ الأثرُ من الصفوف لا يُمرَّر من الخدمة: قائمةٌ تُحمل عبر طبقتين تصير
    مُعامِلاً في كل نداءٍ لـ`settle`، وأحدُ نداءاته لا يعرف عن هذا شيئاً
    (البطاقة تدخل من `card_payments`).
    """
    from app.services import notifications

    charges = (
        await session.scalars(
            select(RideCancellationCharge).where(
                RideCancellationCharge.collected_from_ride_id == ride_id
            )
        )
    ).all()

    for charge in charges:
        settled = charge.status is CancellationChargeStatus.SETTLED
        if charge.carrier_driver_id is not None:
            carrier_user = await _debtor_user(session, charge)
            if carrier_user is not None and await _say_once(
                redis, f"carried:{charge.id}:{int(settled)}"
            ):
                await notifications.publish_cancellation_carried(
                    session,
                    redis,
                    driver_user_id=carrier_user.id,
                    ride_id=charge.ride_id,
                    amount=charge.amount,
                    currency=charge.currency,
                    transferred=settled,
                    due_at=charge.carrier_due_at,
                )
        if settled:
            await announce_arrival(session, redis, [charge])


# نافذةُ «سُدِّد للتوّ» — الشحنُ يُحصّل داخل معاملته، والإشعارُ يقع بعد
# الالتزام مباشرةً. والنافذةُ تمنع أن يوقظ أوّلُ نداءٍ بعد النشر تاريخاً كاملاً
JUST_SETTLED_WINDOW_SECONDS = 300


async def announce_settled_for_debtor(
    session: AsyncSession, redis: Redis, *, user: User
) -> None:
    """يخبر المتضررين بمالٍ وصلهم من سدادِ هذا المستخدم — **بعد الالتزام**.

    وبابُه الشحن: من شحن محفظته سدَّد ما عليه أو حوّل ما في يده (§7)، ومن
    استفاد لا يعرف بذلك إلا بخبر. والقراءةُ من الصفوف بعد الالتزام هي القاعدةُ
    نفسُها التي تمنع إعلانَ حالٍ قد ترتدّ.
    """
    driver_id = await session.scalar(
        select(Driver.id).where(Driver.user_id == user.id)
    )
    since = _now() - timedelta(seconds=JUST_SETTLED_WINDOW_SECONDS)
    condition = (
        RideCancellationCharge.carrier_driver_id == driver_id
        if driver_id is not None
        else (
            (RideCancellationCharge.payer_user_id == user.id)
            & RideCancellationCharge.carrier_driver_id.is_(None)
        )
    )
    charges = (
        await session.scalars(
            select(RideCancellationCharge).where(
                condition,
                RideCancellationCharge.status == CancellationChargeStatus.SETTLED,
                RideCancellationCharge.settled_at >= since,
            )
        )
    ).all()
    await announce_arrival(session, redis, charges)


async def announce_arrival(
    session: AsyncSession,
    redis: Redis,
    charges: Sequence[RideCancellationCharge],
) -> None:
    """يخبر كلَّ متضررٍ بوصول ماله — **مرةً واحدة** مهما تكرّر النداء."""
    from app.services import notifications

    for charge in charges:
        if await _say_once(redis, f"collected:{charge.id}"):
            await notifications.publish_cancellation_collected(
                session,
                redis,
                driver_id=charge.beneficiary_driver_id,
                ride_id=charge.ride_id,
                amount=charge.amount,
                currency=charge.currency,
            )


# ------------------------------------------------------------ إجراءات الإدارة


class ChargeNotOpen(Conflict):
    code = "cancellation_charge_not_open"
    message = "هذا الرسم لم يعد معلّقاً"


async def _locked_charge(
    session: AsyncSession, charge_id: uuid.UUID
) -> RideCancellationCharge:
    """الصفُّ مقفولاً **قبل** فحص حالته — قاعدةُ كل مسارٍ يغيّر حالة.

    بغيره يقرأ إعفاءان متزامنان `pending` معاً فيمرّان، فيُكتب إعفاءٌ فوق
    تحصيلٍ وقع — أي صفٌّ يقول «أُعفي» ومالٌ خرج من محفظة راكب.
    """
    charge = await session.get(
        RideCancellationCharge,
        charge_id,
        with_for_update=True,
        populate_existing=True,
    )
    if charge is None:
        raise NotFound("رسمُ الإلغاء غير موجود")
    if charge.status is not CancellationChargeStatus.PENDING:
        raise ChargeNotOpen()
    return charge


async def waive(
    session: AsyncSession, *, charge_id: uuid.UUID, admin: User, reason: str
) -> RideCancellationCharge:
    """إعفاءُ الإدارة (§3) — **وهو بابُ الاعتراض بعد الحدث لا شرطٌ قبله**.

    القياسُ آليٌّ لحظةَ الإلغاء كي لا يُحبس من يريد الإلغاءَ الآن خلف طابورٍ
    بشريّ؛ وهذا هو البابُ الذي وُعد به بعدها. **ولا قيدَ في الدفتر**: لم يتحرك
    مالٌ في محفظة أحد، وقيدٌ يقول «سُدِّد» يجعل الكشفَ يكذب على الطرفين —
    قاعدةُ شطبِ السلفة نفسُها.

    **والسببُ المكتوبُ إلزاميّ** ويدخل قيدَ التدقيق بنصّه: هو محتوى القرار
    نفسُه لا قيمةُ حقلٍ تُخفى (استثناءُ «أسماءُ الحقول لا قيمُها»).
    """
    cleaned = reason.strip()
    if not cleaned:
        raise InvalidInput("سبب الإعفاء مطلوب")

    charge = await _locked_charge(session, charge_id)
    charge.status = CancellationChargeStatus.WAIVED
    charge.waived_by_user_id = admin.id
    charge.waive_reason = cleaned
    # قيدُ CHECK «كلٌّ أو لا شيء» يطلب وقتاً مع الفاعل والسبب
    charge.settled_at = _now()

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="ride_cancellation_charge",
        entity_id=charge.id,
        details={"status": charge.status.value, "reason": cleaned},
    )
    await session.flush()
    return charge


async def write_off(
    session: AsyncSession,
    *,
    charge_id: uuid.UUID,
    admin: User | None,
    reason: str,
) -> RideCancellationCharge:
    """شطبُ رسمٍ لم يعد صاحبُه (§10) — بقرارٍ إداريٍّ أو بإعدادِ الدولة.

    **والفاعلُ يجوز أن يكون فارغاً**: حين تُطبّقه الدورةُ بإعدادٍ ضبطته الإدارة
    لا إنسانَ ضغط زرّاً — وصفٌّ يسمّي من لم يفعل أسوأُ من صفٍّ لا يسمّي أحداً
    (قاعدةُ `scripts/totp_reset.py`). والسببُ يقول أيَّ إعدادٍ قرّر.
    """
    cleaned = reason.strip()
    if not cleaned:  # pragma: no cover - كلُّ مُستدعٍ يكتب سبباً
        raise InvalidInput("سبب الشطب مطلوب")

    charge = await _locked_charge(session, charge_id)
    charge.status = CancellationChargeStatus.WRITTEN_OFF
    charge.written_off_at = _now()
    charge.written_off_by_user_id = admin.id if admin else None
    charge.writeoff_reason = cleaned

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="ride_cancellation_charge",
        entity_id=charge.id,
        details={"status": charge.status.value, "reason": cleaned},
    )
    await session.flush()
    return charge


async def bear_by_company(
    session: AsyncSession, *, charge_id: uuid.UUID, reason: str
) -> RideCancellationCharge | None:
    """تتحمّلها الشركةُ فيصل المتضررَ مالُه (§10) — **دائنٌ بلا مدينٍ مقابل**.

    وهو شكلُ `referral_bonus` و«خصم الكوبون» نفسُه: وعاءُ الشركة ليس محفظةً في
    هذا النظام، فالخسارةُ المعترَفُ بها تُكتب دائناً واحداً واسمُ من قرّرها في
    التدقيق. **ولا يُخصم من الراكب**: لو خُصم منه لما كانت الشركةُ تحمّلت شيئاً.
    """
    charge = await _locked_charge(session, charge_id)
    beneficiary = await _beneficiary_user(session, charge)
    if beneficiary is None:  # pragma: no cover - حذفُ حسابٍ نادر
        return None

    await wallet.lock_wallet(session, beneficiary.id)
    await wallet.record(
        session,
        owner=beneficiary,
        # **دائنٌ بلا مدين** تتحمّله الشركة — والمتضرِّرُ كبتنٌ كما في `_move`
        owner_type=WalletOwnerType.DRIVER,
        tx_type=WalletTransactionType.CANCELLATION_COMPENSATION,
        amount=charge.amount,
        ride_id=charge.ride_id,
        reference=reason,
        idempotency_key=f"cancellation:{charge.id}",
    )
    charge.status = CancellationChargeStatus.SETTLED
    charge.settled_at = _now()

    await audit.record(
        session,
        actor=None,
        action=AuditAction.UPDATE,
        entity_type="ride_cancellation_charge",
        entity_id=charge.id,
        details={"status": charge.status.value, "reason": reason},
    )
    await session.flush()
    return charge


# ------------------------------------------------------------ المهام الدورية


async def stale_charge_ids(session: AsyncSession) -> list[uuid.UUID]:
    """رسومٌ مضت مدّتُها ولم يعد صاحبُها (§10) — **بمهلة كل دولةٍ على حدة**.

    والمهلةُ تُقرأ **حيّةً من الإعداد** لا مجمَّدةً على الصف: هي سؤالٌ عن
    سياسةٍ تُراجَع («متى نعتبره ضائعاً»)، لا وعدٌ قيل لأحدٍ فلا يجوز نقضُه —
    بخلاف مهلة الحامل التي رآها في شاشته. وخفضُها في اللوحة يُعيد تقييمَ
    الجميع، كحدِّ الإيقاف تماماً.

    **والمُسنَدُ إليه حاملٌ ليس منها**: ذاك مالٌ عند كبتنٍ نعرفه، ومهلتُه
    مهلتُه هو — لا «راكبٌ لم يعد».
    """
    rows = await session.execute(
        select(RideCancellationCharge.id)
        .join(Ride, Ride.id == RideCancellationCharge.ride_id)
        .join(
            CancellationSetting,
            CancellationSetting.country_code == Ride.country_code,
        )
        .where(
            RideCancellationCharge.status == CancellationChargeStatus.PENDING,
            RideCancellationCharge.carrier_driver_id.is_(None),
            CancellationSetting.unpaid_after_days > 0,
            CancellationSetting.unpaid_outcome
            != UnpaidCancellationOutcome.KEEP_PENDING,
            RideCancellationCharge.created_at
            + func.make_interval(0, 0, 0, CancellationSetting.unpaid_after_days)
            <= _now(),
        )
        .order_by(RideCancellationCharge.created_at)
    )
    return [row[0] for row in rows.all()]


async def outcome_for_charge(
    session: AsyncSession, charge: RideCancellationCharge
) -> UnpaidCancellationOutcome:
    """مآلُ هذا الصفِّ بحسب دولة رحلته — تُقرأ لحظةَ التطبيق لا قبله."""
    ride = await session.get(Ride, charge.ride_id)
    if ride is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
        return UnpaidCancellationOutcome.KEEP_PENDING
    policy = await settings_for(session, ride.country_code)
    return policy.unpaid_outcome


async def overdue_carrier_ids(session: AsyncSession) -> list[uuid.UUID]:
    """حاملون انقضت مهلتُهم ولم يُمنعوا بعد (§6-أ).

    والمنعُ **من التوزيع** كإيقاف السلفة: `eligible_driver_ids` تقرأ عموداً
    محضَّراً، ولا شيءَ هنا يقطع رحلةً جارية — قطعُها يترك راكباً على الرصيف.
    """
    rows = await session.scalars(
        select(RideCancellationCharge.carrier_driver_id)
        .join(Driver, Driver.id == RideCancellationCharge.carrier_driver_id)
        .where(
            RideCancellationCharge.status == CancellationChargeStatus.PENDING,
            RideCancellationCharge.carrier_due_at.is_not(None),
            RideCancellationCharge.carrier_due_at <= _now(),
            Driver.cancellation_carry_blocked.is_(False),
        )
        .distinct()
    )
    return list(rows)


async def block_carrier(
    session: AsyncSession, driver_id: uuid.UUID
) -> Driver | None:
    """يوقف حاملاً تجاوز مهلته — ويعود `None` إن سبقه سدادٌ أو دورةٌ أخرى."""
    driver = await session.get(
        Driver, driver_id, with_for_update=True, populate_existing=True
    )
    if driver is None or driver.cancellation_carry_blocked:  # pragma: no cover
        return None
    if await carrier_dues_of(session, driver.id) <= ZERO:  # pragma: no cover
        return None
    driver.cancellation_carry_blocked = True
    await session.flush()
    return driver
