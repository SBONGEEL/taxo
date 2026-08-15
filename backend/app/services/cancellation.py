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
from datetime import datetime, timezone
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cancellation import (
    DEFAULT_BLOCK_AFTER_UNPAID,
    DEFAULT_EXEMPT_WITHIN_METERS,
    DEFAULT_UNPAID_AFTER_DAYS,
    CancellationSetting,
    RideCancellationCharge,
)
from app.models.driver import Driver
from app.models.enums import (
    CancellationChargeStatus,
    CountryCode,
    UnpaidCancellationOutcome,
    WalletTransactionType,
)
from app.models.ride import Ride
from app.models.user import User
from app.services import geo, wallet
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


async def try_collect(
    session: AsyncSession, charge: RideCancellationCharge
) -> bool:
    """يخصم من الراكب ويقيّد للكبتن **في معاملةٍ واحدة**، أو يترك الصفَّ معلّقاً.

    ولا يرمي على رصيدٍ لا يكفي: `wallet.record` يرمي `InsufficientBalance` وهو
    هنا **حالٌ متوقَّعةٌ لا خطأ** — الدَّينُ هو الجواب، لا رفضُ العملية.
    """
    if charge.status is not CancellationChargeStatus.PENDING:
        return False

    payer = await session.get(User, charge.payer_user_id)
    driver = await session.get(Driver, charge.beneficiary_driver_id)
    if payer is None or driver is None:  # pragma: no cover - حذفُ حسابٍ نادر
        return False
    beneficiary = await session.get(User, driver.user_id)
    if beneficiary is None:  # pragma: no cover
        return False

    # **القفلُ قبل قراءة الرصيد، لا بعدها**: قراءةٌ ثم قرارٌ ثم كتابةٌ ليست
    # ذرّيةً وحدَها — وخصمان متزامنان على رصيدٍ يكفي أحدَهما يقرآن الرقمَ
    # نفسَه فيمرّان معاً، ثم يرمي `wallet.record` عند الثاني `InsufficientBalance`
    # **داخل مسار الإلغاء** فيرتدّ الإلغاءُ كلُّه. وهذا الترتيبُ هو ما يجعل
    # الثاني يرى الرصيدَ بعد الأول فيعود `False` ويبقى ديناً — وهو الجواب.
    #
    # وترتيبُ القفلين بالـUUID المرتَّب: قاعدةُ `wallet._lock_wallets` نفسُها،
    # وبدونها يتقابل خصمان متزامنان على محفظتين في اتجاهين متعاكسين
    await wallet.lock_wallets(session, payer.id, beneficiary.id)

    if await wallet.balance_of(session, payer) < charge.amount:
        return False

    key = f"cancellation:{charge.id}"
    await wallet.record(
        session,
        owner=payer,
        tx_type=WalletTransactionType.CANCELLATION_FEE,
        amount=-charge.amount,
        ride_id=charge.ride_id,
        idempotency_key=key,
    )
    await wallet.record(
        session,
        owner=beneficiary,
        tx_type=WalletTransactionType.CANCELLATION_COMPENSATION,
        amount=charge.amount,
        ride_id=charge.ride_id,
        idempotency_key=key,
    )

    charge.status = CancellationChargeStatus.SETTLED
    charge.settled_at = _now()
    await session.flush()
    return True


# ------------------------------------------------------------------ القراءة


async def debt_of(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    """ما على راكبٍ من رسومِ إلغاءٍ لم تُحصَّل — **مجموعٌ يُقرأ لا عمودٌ يُخزَّن**.

    قاعدةُ «لا عمودَ رصيد» نفسُها: عمودٌ يخزّن مجموعاً يفترق عن مجموعه أوَّلَ
    صفٍّ يُكتب بلا تحديثه.
    """
    total = await session.scalar(
        select(func.coalesce(func.sum(RideCancellationCharge.amount), 0)).where(
            RideCancellationCharge.payer_user_id == user_id,
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
        select(func.count()).where(
            RideCancellationCharge.payer_user_id == user_id,
            RideCancellationCharge.status == CancellationChargeStatus.PENDING,
        )
    )
    return int(total or 0)


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
