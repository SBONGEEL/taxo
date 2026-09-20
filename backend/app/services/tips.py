"""البقشيش — هديةُ الراكب للكبتن (SPEC القسم 6.5، المرحلة 12-و).

**قرارُ المالك**: الراكبُ يموّله، والكبتنُ يقبضه **كاملاً بلا عمولة**. فهذا
الملف يكتب قيدين متقابلين ولا يكتب ثالثاً: `tip_payment` خصماً على الراكب
و`tip` إضافةً للكبتن، **ولا `commission`** — ولا يدخل البقشيشُ نطاق
`commission_settings.applies_to` بحال.

**والقناةُ المحفظةُ وحدها** (قرارُ المالك بعد أن رأى الرقم): رسمُ بوابةِ
البطاقات على نصف دينارٍ يتجاوز البقشيشَ نفسه، فتدفع الشركةُ لتوصيل هديةٍ من
الراكب إلى الكبتن. وبقشيشُ اليد لا يُسجَّل بحكم التعريف — الكاشُ لا تراه
المنصة، وهو منطق `DIRECTLY_COLLECTED_METHODS` نفسُه.

**وترتيبُ الأقفال كما هو في المشروع**: صفُّ الرحلة أولاً (فيصير فحصُ
`completed` والملكية ذرّياً)، ثم قفلا المحفظتين بترتيب UUID المرتَّب
(`wallet.lock_wallets`) — راكبٌ وكبتنٌ في عمليةٍ واحدة، وبغير الترتيب يتقابل
بقشيشان متعاكسان في جمود.

**ومفتاحُ التكرار لا يقوم مقام القفل**: `UNIQUE (ride_id)` يفشل الثانيةَ بجوابٍ
مفهوم، والقفلُ يحرس أن لا يُقرأ رصيدٌ واحدٌ مرتين. وكلاهما مُختبَرٌ بحذفه.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import Conflict, FeatureDisabled, InvalidInput, NotFound
from app.models.enums import (
    CountryCode,
    FeatureKey,
    RideStatus,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.payment_setting import PaymentSetting
from app.models.ride import Ride
from app.models.tip import Tip
from app.models.user import User
from app.services import pricing, settings_service, wallet

# **نافذةٌ ثابتةٌ في الخدمة لا إعدادٌ**: البقشيشُ قريبٌ من الرحلة أو لا يكون —
# وخصمٌ من محفظةٍ بعد ثلاثة أسابيع يفاجئ صاحبَها ولا يذكّره بشيء. ورقمٌ كهذا
# يُغيَّر بمراجعةِ كودٍ لا بضغطةٍ في اللوحة (نفس ثوابت `services/dispatch.py`)
TIP_WINDOW_HOURS = 72


class TipsUnavailable(FeatureDisabled):
    code = "tips_unavailable"
    message = "البقشيش غير مفعّل في بلدك"


class TipNotAllowed(Conflict):
    code = "tip_not_allowed"
    message = "لا يمكن إضافة بقشيش لهذه الرحلة"


class TipAlreadyGiven(Conflict):
    code = "tip_already_given"
    message = "سبق أن أضفت بقشيشاً لهذه الرحلة"


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------ الإعدادات


async def settings_for(
    session: AsyncSession, country: CountryCode
) -> PaymentSetting | None:
    return await session.scalar(
        select(PaymentSetting).where(PaymentSetting.country_code == country)
    )


async def offered_in(session: AsyncSession, country: CountryCode) -> bool:
    """هل تُعرض الميزةُ في هذه الدولة؟ **ثلاثة شروطٍ لا شرط**.

    المفتاحُ مشتعل، **و**المحفظةُ مفعّلة (القناةُ الوحيدة اليوم)، **و**المبالغُ
    مضبوطة. وصفرُ السقف يعني «لم يُضبط» فتُخفى الأزرار — لا زرَّ بقشيشٍ مقداره
    صفر، ولا زرَّ معطَّلاً يرفع توقّعَ الكبتن ثم يخيّبه.
    """
    if not await settings_service.is_feature_enabled(
        session, country, FeatureKey.TIPS_ENABLED
    ):
        return False
    if not await settings_service.is_feature_enabled(
        session, country, FeatureKey.WALLET_ENABLED
    ):
        return False
    row = await settings_for(session, country)
    return bool(row and row.tips_configured)


async def for_ride(session: AsyncSession, ride_id: uuid.UUID) -> Tip | None:
    return await session.scalar(select(Tip).where(Tip.ride_id == ride_id))


# ------------------------------------------------------------ الكتابة


async def create(
    session: AsyncSession,
    *,
    ride: Ride,
    rider: User,
    amount: Decimal,
) -> Tip:
    """يكتب البقشيشَ وقيديه — أو يرفع خطأً مفهوماً. الـcommit للراوتر.

    الترتيب مقصود: تُفحص الشروطُ كلُّها **قبل** أي قفل، ثم يُقفل صفُّ الرحلة
    فيصير فحصُ حالتها ذرّياً، ثم المحفظتان. وبغير قفل الرحلة يمكن أن يُقرأ
    `completed` وقد صار غيرَه — واليومَ لا مسارَ يفعل ذلك، والقفلُ للترتيب
    الذي يحرس ما سيُضاف غداً لا لحالةٍ قائمة اليوم.
    """
    if ride.rider_id != rider.id:
        raise NotFound("الرحلة غير موجودة")

    country = ride.country_code
    if not await offered_in(session, country):
        raise TipsUnavailable()

    # **محفظةٌ مجمَّدة لا تُخرج مالاً**: التجميدُ إجراءُ اللوحة على محفظةٍ مشبوهة
    # (القسم 7/13.3)، وبقشيشٌ يخرج منها يجعل التجميدَ نصفَ تجميد. والحارسُ
    # موجودٌ في `wallet` فيُستدعى صريحاً كما يفعل التحويل — لا يُعاد كتابتُه
    wallet.require_not_frozen(rider, WalletOwnerType.RIDER)

    row = await settings_for(session, country)
    assert row is not None  # `offered_in` تضمنه

    amount = pricing.round_money(amount)
    if amount <= 0:
        raise InvalidInput("مبلغ البقشيش يجب أن يكون أكبر من صفر")
    if amount > row.tip_max:
        raise InvalidInput(
            f"أقصى بقشيش {pricing.round_money(row.tip_max)} "
            f"{currency_for_country(country).value}"
        )

    # الرحلةُ مكتملةٌ وحديثة. **والنافذةُ من `completed_at`** لا من `created_at`:
    # رحلةٌ طويلةٌ بدأت أمس وانتهت الآن يستحق كبتنُها بقشيشاً
    await session.refresh(ride, with_for_update=True)
    if ride.status is not RideStatus.COMPLETED or ride.completed_at is None:
        raise TipNotAllowed("البقشيش بعد اكتمال الرحلة")
    if ride.driver_id is None:
        raise TipNotAllowed()
    if _now() - ride.completed_at > timedelta(hours=TIP_WINDOW_HOURS):
        raise TipNotAllowed("مضى وقتٌ طويل على هذه الرحلة")

    # **قيدُ الدفتر يملكه `users.id` لا `drivers.id`** (قاعدةٌ كلّفت المشروع
    # مرةً: `wallet_transactions.owner_id` يشير إلى `users` للطرفين، وتمريرُ
    # `driver.id` يعيد صفراً صامتاً لأنه لا يطابق صفاً)
    from app.models.driver import Driver

    driver_user_id = await session.scalar(
        select(Driver.user_id).where(Driver.id == ride.driver_id)
    )
    if driver_user_id is None:  # pragma: no cover - صفٌّ محذوف
        raise TipNotAllowed()

    tip = Tip(
        ride_id=ride.id,
        rider_id=rider.id,
        driver_id=driver_user_id,
        amount=amount,
        currency=currency_for_country(country).value,
    )
    session.add(tip)
    try:
        await session.flush()
    except IntegrityError as exc:
        # القيدُ الفريد على الرحلة — ضغطتان متزامنتان لا تنتجان بقشيشين،
        # والحارسُ في القاعدة لا في فحصٍ سابقٍ يمكن أن يُسبَق (كما في `ratings`)
        await session.rollback()
        raise TipAlreadyGiven() from exc

    # قفلا المحفظتين بترتيبٍ ثابت — ثم قيدان بمفتاحٍ واحدٍ مشتقٍّ من الصف.
    #
    # **وما يملكه هذا القفلُ المسبق هو الترتيبُ لا القراءةُ المزدوجة**:
    # `wallet.record` يقفل محفظةَ صاحبه بنفسه قبل أن يجمع رصيدَه، فالقراءةُ
    # المزدوجة محروسةٌ هناك. والمسبقُ يضمن أن **محفظتَي عمليةٍ واحدة تُقفلان
    # مرتَّبتين** فلا يتقابل مع عمليةٍ أخرى تمسّهما في جمود — نفس ما يفعله
    # `transfer`. وهو زائدٌ لو نُظر إلى ثابتٍ واحد، ولازمٌ للترتيب الذي يحرس
    # كلَّ ما يُضاف بعده (`CLAUDE.md`: «إضافةُ قفلٍ جديد تعني إدخالَه في هذا
    # الترتيب لا اختراعَ ترتيبٍ ثانٍ»)
    driver_user = await session.get(User, driver_user_id)
    await wallet.lock_wallets(session, rider.id, driver_user_id)

    key = f"tip:{tip.id}"
    await wallet.record(
        session,
        owner=rider,
        # **الإكراميةُ تخرج من محفظة الراكب** كما تخرج منها الأجرة
        owner_type=WalletOwnerType.RIDER,
        tx_type=WalletTransactionType.TIP_PAYMENT,
        amount=-amount,
        ride_id=ride.id,
        idempotency_key=key,
    )
    await wallet.record(
        session,
        owner=driver_user,
        # **وتدخل محفظةَ الكبتن** كما يدخلها الأجر
        owner_type=WalletOwnerType.DRIVER,
        tx_type=WalletTransactionType.TIP,
        amount=amount,
        ride_id=ride.id,
        idempotency_key=key,
    )
    return tip
