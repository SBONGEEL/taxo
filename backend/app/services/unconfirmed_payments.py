"""المدفوعاتُ غيرُ المؤكَّدة — `design/PAYMENTS-UNCONFIRMED.md` بخطواته ١–٥ (§١٠)، SPEC §٦٤-ج، `design/APPROVALS-62.md` §٣.

## ما يفعله هذا الملف

١. **صفُّ الدفع يولد مع نهاية الرحلة** للكاش وكليك (`open_on_completion`) — بالطريقة التي أُرسلت مع الطلب، **بلا قيد**.
   ومعه إقرارُ الراكب بالتسليم (`declare_cash`) وتبديلُ الطريقة (`change_method`).
٢. **التذكيراتُ** (`remind_one`) بمواعيد §٣ ونصوصه، **مختومةً على الصفّ** فلا يتكرّر تذكير. والقائمتان اللتان تُعرضان عند
   فتح التطبيق (`rider_items` · `captain_items`).
٣. **الحدود** — حجبُ الكبتن مشتقٌّ في استعلام التوزيع (`unconfirmed_rules.driver_blocked_clause`)، ومنعُ الراكب عند الطلب
   (`require_rider_not_blocked`)، وإطفاءُ الكاش لمن حُكم عليه مرّتين (`require_cash_allowed`).
٤. **طابورُ الإدارة** (`queue`) وأفعالُه الأربعة، كلٌّ بسببٍ مكتوبٍ يدخل التدقيق.
٥. **الإتمامُ الآليُّ للكاش** (`auto_confirm_one`) بمفتاحه المستقلّ، **والاعتراضُ عليه** (`object_auto_confirm`).

## ما لا يفعله — بقصد

- **لا قيدَ في الدفتر إلا عبر `payments.settle`** — البابُ نفسُه الذي يدخله «استلمت» من الكبتن. فالإتمامُ الآليُّ وحكمُ المشرف
  «مدفوع» يكتبان **ما يكتبه التأكيدُ حرفاً** (§٨)، و«غيرُ مدفوع» لا يكتب شيئاً، **ولا يُحذف صفٌّ أبداً**.
- **لا ماسحَ لرمز كليك** (§٤-٢/٢ — ينتظر توثيقَ ترتيب حقول Jo-QR من JoPACC)، **ولا إنهاءَ آليَّ للرحلة** (§٢-٢ — شروطُه
  تحتاج قراءةَ الموقع والمسار) — **لم يُبنيا عمداً**.

**ومطفأً** (`unconfirmed_payments_enabled`) **لا يفعل شيئاً مما سبق**: كلُّ دالّةٍ هنا تسأل المفتاحَ أوّلاً، والمساراتُ القائمةُ
كما هي حرفاً.

## ترتيبُ الأقفال

**صفُّ الدفعة يُقفل قبل فحص أيِّ انتقال** (قاعدةُ `CLAUDE.md`) — في كلِّ بابٍ هنا: الإقرار، والتبديل، والاعتراض، وأفعال
المشرف (في موجّهاتها، كـ`confirm_payment`)، والتذكير، والإتمام الآليّ (هنا). **ولا قفلَ جديدٌ في الترتيب**: الدفعةُ موضعُها
القائم (الرحلة ← الدفعة ← … ← المحفظة)، والإتمامُ الآليُّ يدخل `settle` من الدفعة كما يدخلها تأكيدُ الكبتن تماماً.
**والتبديلُ وحدَه يقفل الرحلةَ قبلها** (`change_method`): يُلغي ويدفع في معاملةٍ واحدة، والدفعُ (`payments.pay_ride`) بابُه
الرحلة — فالرحلةُ ثمّ الدفعة، **ولا بابَ يقفل الدفعةَ ثمّ الرحلة** (`settle` لا يقفل رحلة).

## حدُّ الإطلاق

**ما يُذكَّر به ويُحجب به ويُتمّ آلياً هو ما في التدفّق وحدَه** (`unconfirmed_rules.in_flow` — رحلةٌ طُلبت والمفتاحُ مشتعلٌ من
تطبيقٍ أرسل طريقتَه). **والمعلَّقُ القديمُ للطابور وحدَه**: لحظةُ الإشعال لا تمنع راكباً ولا تحجب كبتناً بصفوف `pay_ride`
القديمة. **وأيُّ الحدّين يُعتمد قرارُ المالك** — مكتوبٌ في التقرير.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import (
    CashChannelOff,
    Conflict,
    FeatureDisabled,
    InvalidInput,
    InvalidPaymentTransition,
    NotFound,
    ObjectionCounterEntryPending,
    ObjectionWindowClosed,
    PayerMethodMismatch,
    PermissionDenied,
    RideNotPayable,
    UnconfirmedPaymentBlocked,
)
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    CountryCode,
    Currency,
    DisputeResolution,
    DriverStatus,
    FeatureKey,
    Gender,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentStatus,
    RidePayer,
    RideStatus,
)
from app.models.feature_flag import FeatureFlag
from app.models.notification import UserNotification
from app.models.payment import Payment
from app.models.payment_setting import (
    DEFAULT_CASH_AUTO_CONFIRM_HOURS,
    DEFAULT_CASH_AUTO_CONFIRM_MAX,
    DEFAULT_CLIQ_REFERENCE_MINUTES,
    DEFAULT_DISPUTE_WINDOW_HOURS,
    DEFAULT_DRIVER_UNCONFIRMED_BLOCK_COUNT,
    DEFAULT_DRIVER_UNCONFIRMED_BLOCK_HOURS,
    DEFAULT_PAYMENT_REMINDER_MINUTES,
    DEFAULT_RIDER_UNCONFIRMED_BLOCK_MINUTES,
    DEFAULT_RIDER_UNPAID_RULINGS_CASH_OFF,
    DEFAULT_RIDER_UNPAID_RULINGS_WINDOW_DAYS,
)
from app.models.ride import Ride
from app.models.user import User
from app.services import audit, settings_service
from app.services import payments as payments_service
from app.services.unconfirmed_rules import (
    AWAITED_METHODS,
    awaits_captain,
    awaits_rider,
    driver_blocked_clause,
    in_flow,
    payment_due,
    pending_awaited,
    unconfirmed,
)

logger = logging.getLogger(__name__)

#: **نوعُ الإشعار** — `data["type"]` وعمودُ `kind` في صندوق الوارد معاً
REMINDER_KIND = "payment_reminder"
DISPUTED_KIND = "payment_disputed"
AUTO_CONFIRMED_KIND = "payment_auto_confirmed"

#: **«طابورُ الإدارة بعد ٢٤ س»** و«أحمرُ فوق ٢٤ س» (§٢-٣/§٥) — **رقمُ التصميم نفسِه، ولا عمودَ له في جدول §٩**، فيبقى ثابتاً
#: هنا معلَّلاً لا رقماً يُخترع في اللوحة. ومنه يُحسب «بعد ساعةٍ تُحال رحلتُك» في التذكير الرابع
ESCALATION_HOURS = 24

#: **أقلُّ طول سببٍ يكتبه المشرف** (§٥): «٨ أحرف على الأقل» — سببٌ أقصرُ لا يُقرأ بعد شهر. **ومصدرُه بابُ الحكم الواحد**
#: (`payments.resolve_dispute`) فلا رقمان لسببٍ واحد
MIN_REASON_LENGTH = payments_service.MIN_RULING_REASON_LENGTH

#: **علامةُ العملة في نصِّ الدرج وحدَه** — النظامُ يرسمه والتطبيقُ مغلق فلا واجهةَ تصوغه (`notifications.py`). و`data` يحمل المعرّفات
_TRAY_CURRENCY: dict[Currency, str] = {Currency.JOD: "د.أ", Currency.LYD: "د.ل"}

#: **توقيتُ السوق حين لا صفَّ `notification_settings` له** — موعدُ «اعترض قبل» يُقرأ بساعة كبتنه لا بساعة الخادم
_MARKET_TIMEZONE: dict[CountryCode, str] = {
    CountryCode.JO: "Asia/Amman",
    CountryCode.LY: "Africa/Tripoli",
}


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ الإعدادات


@dataclass(frozen=True, slots=True)
class Thresholds:
    """عتباتُ §٩ لسوقٍ واحد — **مقروءةً مرّةً لكلِّ قرار**، وافتراضُ التصميم حين لا صفّ (مسارُ قراءةٍ لا يكتب صفَّ إعدادات)."""

    reminder_minutes: tuple[int, ...] = DEFAULT_PAYMENT_REMINDER_MINUTES
    cash_auto_confirm_hours: int = DEFAULT_CASH_AUTO_CONFIRM_HOURS
    cash_auto_confirm_max: Decimal = DEFAULT_CASH_AUTO_CONFIRM_MAX
    cliq_reference_minutes: int = DEFAULT_CLIQ_REFERENCE_MINUTES
    driver_block_count: int = DEFAULT_DRIVER_UNCONFIRMED_BLOCK_COUNT
    driver_block_hours: int = DEFAULT_DRIVER_UNCONFIRMED_BLOCK_HOURS
    rider_block_minutes: int = DEFAULT_RIDER_UNCONFIRMED_BLOCK_MINUTES
    cash_off_rulings: int = DEFAULT_RIDER_UNPAID_RULINGS_CASH_OFF
    cash_off_window_days: int = DEFAULT_RIDER_UNPAID_RULINGS_WINDOW_DAYS
    dispute_window_hours: int = DEFAULT_DISPUTE_WINDOW_HOURS


async def thresholds_for(session: AsyncSession, country: CountryCode) -> Thresholds:
    row = await settings_service.get_payment_settings(session, country)
    if row is None:
        return Thresholds()
    return Thresholds(
        reminder_minutes=tuple(int(value) for value in row.payment_reminder_minutes),
        cash_auto_confirm_hours=row.cash_auto_confirm_hours,
        cash_auto_confirm_max=row.cash_auto_confirm_max_amount,
        cliq_reference_minutes=row.cliq_reference_minutes,
        driver_block_count=row.driver_unconfirmed_block_count,
        driver_block_hours=row.driver_unconfirmed_block_hours,
        rider_block_minutes=row.rider_unconfirmed_block_minutes,
        cash_off_rulings=row.rider_unpaid_rulings_cash_off,
        cash_off_window_days=row.rider_unpaid_rulings_window_days,
        dispute_window_hours=row.dispute_window_hours,
    )


async def enabled(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(
        session, country, FeatureKey.UNCONFIRMED_PAYMENTS_ENABLED
    )


async def auto_confirm_enabled(session: AsyncSession, country: CountryCode) -> bool:
    """**المفتاحان معاً**: الإتمامُ الآليُّ جزءٌ من التدفّق لا ميزةٌ قائمةٌ وحدَها (§١٠/٥)."""
    return await enabled(session, country) and await settings_service.is_feature_enabled(
        session, country, FeatureKey.CASH_AUTO_CONFIRM_ENABLED
    )


async def _require_enabled(session: AsyncSession, country: CountryCode) -> None:
    if not await enabled(session, country):
        raise FeatureDisabled("تأكيدُ المدفوعات المعلَّقة غيرُ مفعّلٍ في بلدك")


async def _enabled_markets(session: AsyncSession, *keys: FeatureKey) -> list[CountryCode]:
    """الأسواقُ التي اشتعلت فيها المفاتيحُ كلُّها — **صفٌّ مكتوبٌ لا افتراض** (ميزاتٌ تُفتح لا حرّاس)."""
    markets: set[CountryCode] | None = None
    for key in keys:
        found = set(
            (
                await session.scalars(
                    select(FeatureFlag.country_code).where(
                        FeatureFlag.feature_key == key.value,
                        FeatureFlag.enabled.is_(True),
                    )
                )
            ).all()
        )
        markets = found if markets is None else markets & found
    return sorted(markets or set())


# ------------------------------------------------------------------ النصوص


def _money(amount: Decimal, currency: Currency) -> str:
    return f"{amount} {_TRAY_CURRENCY.get(currency, currency.value)}"


def _first_name(name: str | None) -> str:
    parts = (name or "").split()
    return parts[0] if parts else "الراكب"


def _hours_phrase(hours: int) -> str:
    """«ساعة · ساعتين · 3 ساعات · 24 ساعة» — **بخاناتٍ لاتينية** (قرارُ المالك 2026-08-19)."""
    if hours == 1:
        return "ساعة"
    if hours == 2:
        return "ساعتين"
    if 3 <= hours <= 10:
        return f"{hours} ساعات"
    return f"{hours} ساعة"


def _minutes_phrase(minutes: int) -> str:
    if minutes % 60 == 0:
        return _hours_phrase(minutes // 60)
    if minutes == 1:
        return "دقيقة"
    if minutes == 2:
        return "دقيقتين"
    if 3 <= minutes <= 10:
        return f"{minutes} دقائق"
    return f"{minutes} دقيقة"


def _after(minutes: int) -> str:
    """«بعد ساعةٍ» كما في نصِّ التصميم — **والفارقُ من الإعداد لا ثابتٌ في الجملة**: من ضبط المواعيدَ غيرَ ذلك قيل له ما يقع."""
    if minutes <= 0:
        return "الآن"
    if minutes == 60:
        return "بعد ساعةٍ"
    return f"بعد {_minutes_phrase(minutes)}"


@dataclass(frozen=True, slots=True)
class Notice:
    """إشعارٌ يُرسل **بعد الـcommit** — يُبنى تحت القفل ويُرسل خارجه، كقاعدة البثّ في المشروع."""

    user_id: uuid.UUID
    kind: str
    title: str
    body: str
    payment_id: uuid.UUID
    ride_id: uuid.UUID


async def send(session: AsyncSession, redis: Redis, notices: Sequence[Notice]) -> None:
    from app.services import notifications

    for notice in notices:
        await notifications.publish_payment_notice(
            session,
            redis,
            user_id=notice.user_id,
            kind=notice.kind,
            title=notice.title,
            body=notice.body,
            payment_id=notice.payment_id,
            ride_id=notice.ride_id,
        )


# ------------------------------------------------------- ١) الصفُّ يولد مع النهاية


async def open_on_completion(session: AsyncSession, ride: Ride) -> Payment | None:
    """**صفُّ الدفع يولد مع نهاية الرحلة** بالطريقة المختارة وبالمتبقّي — **لا قيدَ معه** (§٢-١/§٨).

    يُنادى من `rides.complete_ride` **وصفُّ الرحلة مقفول** — فالترتيبُ رحلةٌ ثمّ دفعة كما في `CLAUDE.md`. **ونمطُ
    `payments.open_payer_cash` بعينه**: المفتاحُ على الرحلة (`hint:{ride_id}`) فإنهاءٌ يُعاد لا يفتح صفّين، **والمتبقّي بعد
    الخصمين** (الكوبون والمشاركة والمشوار) فلا يُفتح ما غُطّي. **ولا يلتقي بـ`open_payer_cash`**: ذاك لرحلةٍ يدفعها غيرُ طالبها،
    وهذا لطالبها وحدَه.

    - **الكاش**: معلَّقٌ ينتظر «استلمت».
    - **كليك**: معلَّقٌ بالاسم المستعار مجمَّداً **إن كان للكبتن اسمٌ مستعار** — وإلا لا شيء، كما اليوم: لا وجهةَ لحوالةٍ بلا
      اسم (`payments._require_cliq_alias`). **ولا يُفتح كليك في سوقٍ أطفأه** (`cliq_enabled`).
    - **المحفظةُ والبطاقة كما اليوم**: الراكبُ يدفعهما من شاشة الدفع، ولا صفَّ يُفتح هنا.
    """
    method = ride.payment_method_hint
    if method not in AWAITED_METHODS:
        return None
    if ride.payer != RidePayer.REQUESTER.value:
        return None
    if not await enabled(session, ride.country_code):
        return None

    key = f"hint:{ride.id}"
    existing = await payments_service._find_by_idempotency_key(session, key)
    if existing is not None:
        return existing

    outstanding = await payments_service.outstanding_amount(session, ride)
    if outstanding <= 0:
        return None

    alias: str | None = None
    if method == PaymentMethod.CLIQ:
        if not await settings_service.is_feature_enabled(
            session, ride.country_code, FeatureKey.CLIQ_ENABLED
        ):
            return None
        alias = (
            await session.scalar(
                select(Driver.cliq_alias).where(Driver.id == ride.driver_id)
            )
            or ""
        ).strip() or None
        if alias is None:
            return None

    payment = payments_service._new_payment(
        ride,
        method=method,
        amount=outstanding,
        idempotency_key=key,
        cliq_alias=alias,
    )
    session.add(payment)
    await session.flush()
    return payment


async def validate_hint(
    session: AsyncSession,
    *,
    rider: User,
    method: PaymentMethod | None,
    for_other: bool,
    payer: RidePayer,
) -> PaymentMethod | None:
    """**الطريقةُ التي تُحفظ على الرحلة** — أو `None` إن كان المفتاحُ مطفأً أو لم تُرسل (§٢-١).

    **مطفأً لا تُحفظ ولا تُفحص**: الرحلةُ كما كانت حرفاً، وتطبيقٌ قديمٌ لا يرسلها لا يتغيّر له شيء.
    """
    if method is None or not await enabled(session, rider.country_code):
        return None
    if method not in (
        PaymentMethod.CASH,
        PaymentMethod.CLIQ,
        PaymentMethod.WALLET,
        PaymentMethod.CARD,
    ):
        raise InvalidInput("طريقةُ الدفع هذه لا يختارها الراكب", field="payment_method")

    # **«يدفعها راكبُها/مستلمُها نقداً»** (§٦٣-ج/١ و٤): صفُّها يفتحه `open_payer_cash` — فلا طريقةَ يختارها الطالبُ غيرُ النقد
    if payer in (RidePayer.PASSENGER_CASH, RidePayer.RECIPIENT_CASH):
        if method != PaymentMethod.CASH:
            raise PayerMethodMismatch("يدفع هذه الرحلةَ غيرُك نقداً للكبتن")
        return None
    # **«يدفعها الطالب» لغيره بالمحفظة أو البطاقة وحدهما** — قاعدةُ `payments._require_payer_method` بعينها
    if for_other and method not in (PaymentMethod.WALLET, PaymentMethod.CARD):
        raise PayerMethodMismatch("اخترتَ أن تدفع أنت — بالمحفظة أو البطاقة")

    feature = payments_service.METHOD_FEATURE.get(method)
    if feature is not None and not await settings_service.is_feature_enabled(
        session, rider.country_code, feature
    ):
        raise FeatureDisabled(f"قناة الدفع «{method.value}» غير مفعّلة في بلدك")
    if method == PaymentMethod.CASH:
        await require_cash_allowed(session, rider)
    return method


# ------------------------------------------------------- أفعالُ الراكب والكبتن


async def declare_cash(session: AsyncSession, *, payment: Payment, rider: User) -> Payment:
    """**«سلّمتُ المبلغ»** — إقرارُ الراكب (§٢-٣). **لا يكتب شيئاً في الدفتر**: المستلمُ هو الحَكَم في النقد.

    **يُنادى وصفُّ الدفعة مقفول** (`get_payment(for_update=True)` في الموجّه): بغيره يُقرأ `pending` بينما يؤكّد الكبتنُ في
    المعاملة المجاورة، **فيُختم إقرارٌ على دفعةٍ أُكّدت** وتقول الشاشةُ «بانتظار الكبتن» عن مالٍ حُسم.

    **ويُعاد بلا خطأ إن سبق** — من ضغط ثانيةً لم يخطئ. **ويُقبل على النزاع** (§٦: «سلّمتُه — أضف ما يثبت ذلك»): إقرارُه بعد
    «لم يدفع» روايتُه للمشرف، ولا يغيّر الحالَ.

    **ويبدأ للكبتن ساعةً جديدة** (§٢-٥/٢: «لم يعترض خلال ٢٤ ساعة **من الإقرار** رغم أربعة تذكيرات وصلته»): مواعيدُه تُعدّ من
    الإقرار (`_captain_start`)، **وعدّادُ ما وصله يُصفَّر** فلا يُحتسب للإتمام تذكيرٌ سبق الإقرار. والأثرُ الكاملُ باقٍ في صندوق
    الوارد (`queue` → `reminder_trail`).
    """
    ride = await payments_service.ride_of(session, payment)
    if ride.rider_id != rider.id:
        raise NotFound("الدفعة غير موجودة")
    await _require_enabled(session, ride.country_code)
    if payment.method != PaymentMethod.CASH:
        raise InvalidPaymentTransition(
            "الإقرارُ بالتسليم للدفع نقداً وحدَه — وكليك يُقَرّ بمرجع الحوالة"
        )
    if ride.payer != RidePayer.REQUESTER.value:
        raise PayerMethodMismatch("يدفع هذه الرحلةَ غيرُك نقداً — والإقرارُ لمن سلّم")
    if payment.declared_at is not None:
        return payment
    if payment.status not in (PaymentStatus.PENDING, PaymentStatus.DISPUTED):
        raise InvalidPaymentTransition("هذه الدفعة لم تعد بانتظار التسليم")
    payment.declared_at = _now()
    payment.driver_reminders = 0
    return payment


async def _lock_ride_for_change(session: AsyncSession, ride_id: uuid.UUID) -> Ride:
    """**صفُّ الرحلة بـ`FOR NO KEY UPDATE` لا `FOR UPDATE`** — أوّلُ أقفال «غيّر طريقة الدفع»، وشروطُ `payments._payable_ride` نفسُها.

    **ولمَ الأضعف** (قِيس ٢٠٢٦-١٠-٠٧): البابان اللذان يسابقان التبديلَ على صفِّ الدفعة — «استلمت» وحكمُ المشرف — يقفلان
    الدفعةَ **ثمّ يأخذان على الرحلة `FOR KEY SHARE` من غير أن يطلباه**: Postgres يفحص المفتاحَ الأجنبيَّ إلى `rides` عند إدراج
    دَين العمولة (`driver_debts.ride_id`)، **وعند تحديثٍ ثانٍ لصفِّ الدفعة نفسِه في المعاملة نفسِها** (حكمُ «مدفوع» يُفرغ الختمَ
    ثمّ التسوية — تحديثان؛ والثاني يرى صفّاً كتبته معاملتُه فيفحص المفتاحَ ولو لم يتغيّر). و`FOR UPDATE` يتعارض مع
    `FOR KEY SHARE`: **فالتبديلُ ممسكٌ بالرحلة ينتظر الدفعة، والتأكيدُ ممسكٌ بالدفعة ينتظر الرحلة — جمود** يُسقط أحدَهما.
    و`FOR NO KEY UPDATE` لا يتعارض مع `FOR KEY SHARE`، **ويتعارض مع نفسِه ومع `FOR UPDATE`** — فتبديلان، أو تبديلٌ و`pay_ride`،
    يتسلسلان على الرحلة كما كانا. ثمّ يرفعه `pay_ride` إلى `FOR UPDATE` وصفُّ الدفعة بيده — فلا أحدَ ينتظره عليها.
    """
    ride = await session.scalar(
        select(Ride)
        .where(Ride.id == ride_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    if ride is None:
        raise NotFound("الرحلة غير موجودة")
    if ride.status != RideStatus.COMPLETED or ride.final_fare is None:
        raise RideNotPayable()
    return ride


async def change_method(
    session: AsyncSession,
    *,
    payment_id: uuid.UUID,
    rider: User,
    method: PaymentMethod,
    idempotency_key: str,
    save_card: bool = False,
    saved_card_id: uuid.UUID | None = None,
) -> Sequence[Payment]:
    """**«غيّر طريقة الدفع»** — **يُلغى المعلَّقُ ويُنشأ غيرُه في خطوةٍ واحدة** (§٢-١)، ويعيد دفعاتِ الرحلة كلَّها.

    **خطوةٌ واحدةٌ لا خطوتان** (مراجعةُ ٢٠٢٦-١٠-٠٧): كان يُلغي ولا يُنشئ، ويترك الراكبَ «يدفع من جديد» بـ`pay_ride` — **فراكبٌ
    ممنوعٌ يرفع منعَه بضغطةٍ ولا يدفع**: صفٌّ `voided` يخرج من كلِّ شرطٍ يقرأ `pending`، فتختفي الرحلةُ من قائمته وقائمة الكبتن
    والطابور، **ويسقط «لم يدفع» من يد الكبتن** (لا صفَّ معلَّقاً يُنازَع). فالإلغاءُ والدفعُ الجديدُ في معاملةٍ واحدة: **سقط
    الثاني** (رصيدٌ لا يكفي، قناةٌ مطفأة، كبتنٌ بلا اسمٍ مستعار، كاشٌ موقوفٌ له) **فلا إلغاءَ** — والصفُّ القديمُ على حاله.

    **ومنطقُ الدفع الجديد هو `payments.pay_ride` بعينه** لا نسخةٌ منه: المحفظةُ تُسوّى، والبطاقةُ تفتح طلبَها، والكاشُ وكليك
    صفٌّ معلَّقٌ جديد — **وبفحوصه كلِّها** (المفتاح، الدافع، إطفاء الكاش، مفتاحُ عدم التكرار).

    **ترتيبُ الأقفال: الرحلةُ ثمّ الدفعة** (`CLAUDE.md`) — الرحلةُ أوّلاً (`_lock_ride_for_change`، `FOR NO KEY UPDATE` بعلّته)
    ثمّ صفُّ الدفعة، **وفحصُ الانتقال بعد قفله**:
    بغيره يُلغى صفٌّ أكّده الكبتنُ في اللحظة نفسِها فيدفع الراكبُ مرّتين. و`pay_ride` يقفل الرحلةَ ثانيةً في المعاملة نفسِها
    (لا شيء في Postgres).

    **ما دام لم يُقِرّ ولم يؤكّد الكبتن**: إقرارٌ أو مرجعُ حوالةٍ يعني أن المالَ قيل إنه تحرّك — وتبديلُ الطريقة بعدها دفعٌ ثانٍ
    لمالٍ واحد. **إلا «سأدفع الآن» على نزاع كاش** (§٢-٣/§٦): الكبتنُ قال «لم يدفع» والراكبُ يدفع الآن بدل أن ينتظر المشرف —
    فيُلغى المتنازَعُ عليه ويُفتح ما يدفع به، **ولو كاشاً ثانيةً** (يسلّمه الآن). **والطريقةُ نفسُها على معلَّقٍ** لا تُبدِّل شيئاً
    فتُردّ.

    **ومفتاحُ عدم التكرار يُفحص قبل الصفّ**: الضغطةُ الثانيةُ بالمفتاح نفسِه تجد الصفَّ القديمَ `voided` — فتعيد حالَ الرحلة لا
    خطأً (نمطُ `pay_ride`).
    """
    ride_id = await session.scalar(select(Payment.ride_id).where(Payment.id == payment_id))
    if ride_id is None:
        raise NotFound("الدفعة غير موجودة")
    ride = await _lock_ride_for_change(session, ride_id)  # قفلُ الرحلة أوّلاً
    if ride.rider_id != rider.id:
        raise NotFound("الدفعة غير موجودة")
    await _require_enabled(session, ride.country_code)
    if await payments_service._find_by_idempotency_key(session, idempotency_key) is not None:
        return await payments_service.list_for_ride(session, ride.id)

    payment = await payments_service.get_payment(session, payment_id, for_update=True)  # قفلُ التبديل — بعد الرحلة
    if payment.method not in AWAITED_METHODS:
        raise InvalidPaymentTransition(
            "تُبدَّل طريقةُ الكاش وكليك وحدَهما — المحفظةُ والبطاقةُ تُحسمان لحظتَهما"
        )
    if ride.payer != RidePayer.REQUESTER.value:
        raise PayerMethodMismatch("يدفع هذه الرحلةَ غيرُك نقداً للكبتن")
    payments_service.require_transition(payment, PaymentStatus.VOIDED)
    if payment.status == PaymentStatus.DISPUTED:
        # **«سأدفع الآن» للكاش وحدَه** — نزاعُ كليك حوالةٌ قيل إنها خرجت، ولا يُدفع فوقها قبل حكم
        if payment.method != PaymentMethod.CASH:
            raise InvalidPaymentTransition("نزاعُ الحوالة يفصل فيه فريقُ TAXO — لا يُدفع فوقه")
    else:
        if payment.declared_at is not None:
            raise InvalidPaymentTransition("أقررتَ بتسليم المبلغ — لا تُبدَّل الطريقةُ بعد الإقرار")
        if payment.cliq_transfer_reference is not None:
            raise InvalidPaymentTransition("أدخلتَ مرجعَ الحوالة — لا تُبدَّل الطريقةُ بعده")
        if method == payment.method:
            raise InvalidInput("هذه طريقتُك الآن — اختر غيرَها", field="method")
    payment.status = PaymentStatus.VOIDED
    payment.voided_at = _now()
    await session.flush()

    return await payments_service.pay_ride(
        session,
        ride_id=ride.id,
        rider=rider,
        method=method,
        idempotency_key=idempotency_key,
        save_card=save_card,
        saved_card_id=saved_card_id,
    )


def objection_deadline(payment: Payment) -> datetime | None:
    """**آخرُ لحظةٍ للاعتراض** — من نافذةٍ **مجمَّدةٍ على الصفّ** لحظةَ الإتمام، لا من إعدادٍ تغيّر بعده."""
    if payment.confirmed_by != PaymentConfirmedBy.AUTO_RULE or payment.confirmed_at is None:
        return None
    hours = int((payment.auto_confirm_criteria or {}).get("objection_window_hours", 0))
    return payment.confirmed_at + timedelta(hours=hours)


async def object_auto_confirm(
    session: AsyncSession, *, payment: Payment, driver: Driver, reason: str
) -> Payment:
    """**«لم أستلم هذا المبلغ»** — اعتراضُ الكبتن على إتمامٍ آليٍّ خلال نافذته (§٢-٥).

    **نزاعٌ بعد التأكيد لا عكسٌ له**: «لا يُعكس قيدٌ قبل حكم المشرف» — الصفُّ يبقى `confirmed` ويُختم الاعتراضُ عليه، فيظهر في
    طابور الإدارة «مُتمٌّ آلياً ومعترَضٌ عليه». **ولا يحتاج المفتاحَ مشتعلاً**: حقُّه في الاعتراض لا يسقط بإطفاء الميزة بعد
    أن أُتمّ مالُه آلياً. **ويُنادى وصفُّ الدفعة مقفول**: اعتراضان معاً لا يكتبان سببين.
    """
    ride = await payments_service.ride_of(session, payment)
    if ride.driver_id != driver.id:
        raise PermissionDenied("هذه الدفعة ليست على رحلة مُسندة إليك")
    if (
        payment.status != PaymentStatus.CONFIRMED
        or payment.confirmed_by != PaymentConfirmedBy.AUTO_RULE
    ):
        raise InvalidPaymentTransition("الاعتراضُ على مبلغٍ أُتمّ آلياً وحدَه")
    if payment.objected_at is not None:
        raise Conflict("اعترضتَ على هذا المبلغ سلفاً — وهو بيد فريق TAXO")
    deadline = objection_deadline(payment)
    if deadline is None or _now() > deadline:
        raise ObjectionWindowClosed()
    cleaned = reason.strip()
    if not cleaned:
        raise InvalidInput("سببُ الاعتراض مطلوب", field="reason")
    payment.objected_at = _now()
    payment.objection_reason = cleaned[:255]
    return payment


# ------------------------------------------------------------------ ٣) الحدود


@dataclass(frozen=True, slots=True)
class RiderBlock:
    """**ما يمنع الراكبَ من الطلب** — رحلتُه، ودفعتُها إن كان لها صفٌّ ينتظره (`None`: الأجرةُ مستحقّةٌ بلا صفّ — يدفعها)."""

    ride_id: uuid.UUID
    payment_id: uuid.UUID | None


async def rider_blocking_payment(
    session: AsyncSession, rider: User, *, now: datetime | None = None
) -> RiderBlock | None:
    """**أقدمُ ما يمنع الراكبَ من الطلب**، بعد مهلته من نهاية الرحلة (§٧) — أو `None`. وجهان:

    - **صفٌّ ينتظره** (`awaits_rider`): لم يُقِرّ / بلا مرجع — يرفعه الإقرارُ أو المرجعُ أو تبديلُ الطريقة.
    - **أجرةٌ مستحقّةٌ بلا صفٍّ حيّ** (`payment_due`): حكمُ «غيرُ مدفوع» (§٧: «لا طلبَ جديدَ حتى يُسدَّد»)، أو بطاقةٌ سقطت،
      أو رحلةٌ لم يُفتح لها صفّ — **يرفعه الدفعُ وحدَه**، أي صفٌّ جديدٌ من `POST /rides/{id}/payments`.

    **والنزاعُ المفتوحُ لا يمنع** (§٧: «في يد الإدارة لا في يدهما»)، **ولا ما ينتظر الكبتن**: من أقرّ «لا يلزمه شيء» (§٦).
    """
    if not await enabled(session, rider.country_code):
        return None
    limits = await thresholds_for(session, rider.country_code)
    cutoff = (now or _now()) - timedelta(minutes=limits.rider_block_minutes)
    waiting = (
        await session.execute(
            select(Payment.id, Payment.ride_id, Ride.completed_at)
            .join(Ride, Ride.id == Payment.ride_id)
            .where(Ride.rider_id == rider.id, awaits_rider(), Ride.completed_at <= cutoff)
            .order_by(Ride.completed_at, Payment.created_at)
            .limit(1)
        )
    ).first()
    due = (
        await session.execute(
            select(Ride.id, Ride.completed_at)
            .where(Ride.rider_id == rider.id, payment_due(), Ride.completed_at <= cutoff)
            .order_by(Ride.completed_at)
            .limit(1)
        )
    ).first()
    if waiting is not None and (due is None or waiting.completed_at <= due.completed_at):
        return RiderBlock(ride_id=waiting.ride_id, payment_id=waiting.id)
    if due is not None:
        return RiderBlock(ride_id=due.id, payment_id=None)
    return None


async def require_rider_not_blocked(session: AsyncSession, rider: User) -> None:
    """يُنادى من `rides.request_ride` — **البابُ الذي ينشئ منه الحجزُ المجدولُ رحلاتِه أيضاً**، فلا يُنسى في بابٍ ثانٍ.

    و`payment_id` فارغٌ حين لا صفَّ ينتظره: الشاشةُ تفتح دفعَ الرحلة (`ride_id`) لا بطاقةَ دفعة.
    """
    blocking = await rider_blocking_payment(session, rider)
    if blocking is not None:
        raise UnconfirmedPaymentBlocked(
            payment_id=str(blocking.payment_id) if blocking.payment_id else None,
            ride_id=str(blocking.ride_id),
        )


async def unpaid_rulings(
    session: AsyncSession, rider_id: uuid.UUID, *, window_days: int, now: datetime | None = None
) -> int:
    """**أحكامُ «لم يدفع» على رحلات هذا الراكب** في نافذتها — من صفوف الدفع نفسِها (`resolution = unpaid`) لا عدّادٍ ثانٍ."""
    since = (now or _now()) - timedelta(days=window_days)
    return int(
        await session.scalar(
            select(func.count(Payment.id))
            .join(Ride, Ride.id == Payment.ride_id)
            .where(
                Ride.rider_id == rider_id,
                Payment.resolution == DisputeResolution.UNPAID,
                Payment.resolved_at >= since,
            )
        )
        or 0
    )


async def cash_allowed(session: AsyncSession, rider: User) -> bool:
    """**أمفتوحةٌ قناةُ الكاش لهذا الراكب؟** — مغلقةٌ لمن حُكم عليه مرّتين بـ«لم يدفع» في نافذتها (§٧). **القناةُ وحدَها لا الحساب**.

    **ويُرفع بمضيّ النافذة** على أقدم الحكمين. **و«بقرار مشرف» قبلها لم يُبنَ** — لا بابَ يرفعه يدوياً اليوم، وهو مكتوبٌ في
    التقرير لا مسكوتٌ عنه. **ويُسأل في كلِّ بابٍ يفتح كاشاً للراكب**: الطريقةُ مع الطلب (`validate_hint`)، والدفعُ بعد الرحلة
    وباقي المحفظة (`payments.pay_ride`) — ومنه «غيّر طريقة الدفع» — والمحجوزُ بالساعة نقداً (`rides.request_ride`).
    """
    if not await enabled(session, rider.country_code):
        return True
    limits = await thresholds_for(session, rider.country_code)
    return (
        await unpaid_rulings(session, rider.id, window_days=limits.cash_off_window_days)
        < limits.cash_off_rulings
    )


async def require_cash_allowed(session: AsyncSession, rider: User) -> None:
    if not await cash_allowed(session, rider):
        raise CashChannelOff()


async def driver_is_blocked(session: AsyncSession, driver: Driver) -> bool:
    """**الشرطُ نفسُه الذي يقرؤه التوزيع** — لا حسابٌ ثانٍ في بايثون يفترق عنه أوّلَ تعديل."""
    return (
        await session.scalar(
            select(Driver.id)
            .join(User, Driver.user_id == User.id)
            .where(Driver.id == driver.id, driver_blocked_clause())
        )
    ) is not None


# ------------------------------------------------- ٢) القائمتان عند فتح التطبيق


@dataclass(slots=True)
class RiderItem:
    #: `None` لـ`payment_due` — الأجرةُ مستحقّةٌ ولا صفَّ حيٌّ عليها
    payment: Payment | None
    ride: Ride
    captain_name: str | None
    state: str
    blocks_at: datetime
    blocks_requests: bool
    #: **ما يُعرض مبلغاً**: مبلغُ الصفّ، أو المستحقُّ على الرحلة حين لا صفّ — محسوباً هنا لا في الشاشة (§14)
    amount: Decimal
    method: PaymentMethod


async def rider_items(
    session: AsyncSession, rider: User, *, now: datetime | None = None
) -> tuple[bool, list[RiderItem]]:
    """**ما ينتظر الراكبَ أو ينتظره هو** — الأقدمُ أوّلاً (§٦، R31). و`blocked` هو حكمُ الطلب نفسُه (`rider_blocking_payment`).

    أربعُ حالات: `awaiting_you` (لم يُقِرّ / بلا مرجع)، و`awaiting_captain` (أقرّ أو أدخل المرجع — «لا يلزمك شيء»)،
    و`disputed`، **و`payment_due`** (الأجرةُ مستحقّةٌ ولا صفَّ عليها — حكمُ «غيرُ مدفوع» أو دفعٌ سقط: زرُّه «ادفع الآن» على
    `POST /rides/{id}/payments`). **ولرحلاتٍ يدفعها هو وحدَها** (`payer = requester`) **وفي التدفّق** (`in_flow`).

    **و`payment_due` هنا لأن المنعَ بلا بطاقةٍ بابٌ بلا زرّ**: راكبٌ يُقال له «لا يمكن طلبُ رحلةٍ جديدة» وقائمتُه فارغة لا
    يعرف ما يفعل.
    """
    moment = now or _now()
    if not await enabled(session, rider.country_code):
        return False, []
    limits = await thresholds_for(session, rider.country_code)
    captain = aliased(User)
    rows = (
        await session.execute(
            select(Payment, Ride, captain.name)
            .join(Ride, Ride.id == Payment.ride_id)
            .outerjoin(Driver, Driver.id == Ride.driver_id)
            .outerjoin(captain, captain.id == Driver.user_id)
            .where(
                Ride.rider_id == rider.id,
                Ride.payer == RidePayer.REQUESTER.value,
                Ride.completed_at.is_not(None),
                or_(
                    unconfirmed(),
                    (Payment.status == PaymentStatus.DISPUTED) & in_flow(),
                ),
            )
        )
    ).all()
    due_rows = (
        await session.execute(
            select(Ride, captain.name)
            .outerjoin(Driver, Driver.id == Ride.driver_id)
            .outerjoin(captain, captain.id == Driver.user_id)
            .where(Ride.rider_id == rider.id, payment_due())
        )
    ).all()

    items: list[RiderItem] = []
    for payment, ride, captain_name in rows:
        state = _rider_state(payment)
        blocks_at = ride.completed_at + timedelta(minutes=limits.rider_block_minutes)
        items.append(
            RiderItem(
                payment=payment,
                ride=ride,
                captain_name=captain_name,
                state=state,
                blocks_at=blocks_at,
                blocks_requests=state == "awaiting_you" and moment >= blocks_at,
                amount=payment.amount,
                method=payment.method,
            )
        )
    for ride, captain_name in due_rows:
        blocks_at = ride.completed_at + timedelta(minutes=limits.rider_block_minutes)
        items.append(
            RiderItem(
                payment=None,
                ride=ride,
                captain_name=captain_name,
                state="payment_due",
                blocks_at=blocks_at,
                blocks_requests=moment >= blocks_at,
                amount=await payments_service.outstanding_amount(session, ride),
                # **الطريقةُ التي اختارها مع الطلب** — `in_flow` يضمن أنها مكتوبة
                method=ride.payment_method_hint,
            )
        )
    items.sort(
        key=lambda item: (
            item.ride.completed_at,
            item.payment.created_at if item.payment is not None else item.ride.completed_at,
        )
    )
    return any(item.blocks_requests for item in items), items


def _rider_state(payment: Payment) -> str:
    if payment.status == PaymentStatus.DISPUTED:
        return "disputed"
    if payment.method == PaymentMethod.CASH:
        return "awaiting_captain" if payment.declared_at is not None else "awaiting_you"
    return "awaiting_captain" if payment.cliq_reference_at is not None else "awaiting_you"


@dataclass(slots=True)
class CaptainItem:
    payment: Payment
    ride: Ride
    rider_name: str | None
    state: str
    objection_deadline: datetime | None = None


async def captain_items(
    session: AsyncSession, driver: Driver, *, now: datetime | None = None
) -> tuple[bool, Thresholds, list[CaptainItem]]:
    """**ما ينتظر تأكيدَ الكبتن** — الأقدمُ أوّلاً (§٦، C33) — **ومعه ما أُتمّ آلياً ونافذةُ اعتراضه مفتوحة**.

    `awaiting_you`: كاشٌ أو كليك بمرجع. `auto_confirmed`: «عُدّ مبلغُ رحلة ليلى مستلَماً … فاعترض قبل {الوقت}». **وكليك بلا
    مرجعٍ ليس هنا**: لا شيءَ يؤكّده بعد. و`blocked` من شرط التوزيع نفسِه (`driver_is_blocked`).
    """
    moment = now or _now()
    country = await session.scalar(select(User.country_code).where(User.id == driver.user_id))
    if country is None or not await enabled(session, country):
        return False, Thresholds(), []
    limits = await thresholds_for(session, country)
    rider = aliased(User)
    rows = (
        await session.execute(
            select(Payment, Ride, rider.name)
            .join(Ride, Ride.id == Payment.ride_id)
            .join(rider, rider.id == Ride.rider_id)
            .where(
                Ride.driver_id == driver.id,
                or_(
                    awaits_captain(),
                    (Payment.status == PaymentStatus.CONFIRMED)
                    & (Payment.confirmed_by == PaymentConfirmedBy.AUTO_RULE)
                    & Payment.objected_at.is_(None),
                ),
            )
            .order_by(Ride.completed_at, Payment.created_at)
        )
    ).all()

    items: list[CaptainItem] = []
    for payment, ride, rider_name in rows:
        if payment.status == PaymentStatus.CONFIRMED:
            deadline = objection_deadline(payment)
            if deadline is None or moment > deadline:
                continue
            items.append(
                CaptainItem(payment, ride, rider_name, "auto_confirmed", deadline)
            )
        else:
            items.append(CaptainItem(payment, ride, rider_name, "awaiting_you"))
    return await driver_is_blocked(session, driver), limits, items


# ------------------------------------------------------------------ ٢) التذكيرات


def _reached_slot(minutes: Sequence[int], start: datetime, moment: datetime | None) -> int:
    """**آخرُ موعدٍ بلغته الساعةُ عند `moment`** — فهرسُه، أو `-1` إن لم تبلغ أوّلَها (أو لم تبدأ بعد)."""
    if moment is None or moment < start:
        return -1
    elapsed = (moment - start).total_seconds() / 60
    reached = [index for index, value in enumerate(minutes) if elapsed >= value]
    return reached[-1] if reached else -1


def _due_slot(
    minutes: Sequence[int], start: datetime, now: datetime, *, reminded_at: datetime | None
) -> int | None:
    """**الموعدُ المستحقُّ الذي لم يُرسَل على هذه الساعة** — أو `None`.

    **الأحدثُ وحدَه لا كلُّ ما فات**: كنسٌ توقّف ساعتين يجد مواعيدَ فاتت — **وثلاثةُ تذكيراتٍ في دقيقةٍ واحدة إزعاجٌ لا تذكير**.
    فيُرسل آخرُها.

    **وما أُرسل يُقرأ من وقت آخر تذكيرٍ لا من عدّاد** (مراجعةُ ٢٠٢٦-١٠-٠٧): كان العدّادُ مؤشّرَ موعدٍ يقفز إلى «٤» بتذكيرٍ واحدٍ
    متأخّر، **فيُقرأ «أربعةُ تذكيراتٍ وصلته» شرطاً للإتمام الآليّ وما وصله إلا واحد**. والآن العدّادُ عددُ ما أُرسل حقاً
    (`+1` لكلِّ تذكير)، **والموعدُ الذي بلغه آخرُ تذكيرٍ** يُشتقّ من وقته على الساعة نفسِها — **فساعةٌ بدأت بعده** (إقرارُ
    الراكب، §٢-٥) **تبدأ مواعيدُها من أوّلها** بلا عمودٍ ثانٍ يُصفَّر.
    """
    latest = _reached_slot(minutes, start, now)
    if latest < 0:
        return None
    return latest if latest > _reached_slot(minutes, start, reminded_at) else None


def _rider_minutes(payment: Payment, limits: Thresholds) -> tuple[int, ...]:
    """**كليك يُمهل مرجعَه قبل أن يُذكَّر** (§٢-٤: «خلال ٣٠ دقيقة») — فلا موعدَ للراكب قبل مهلة المرجع."""
    if payment.method == PaymentMethod.CLIQ:
        return tuple(max(value, limits.cliq_reference_minutes) for value in limits.reminder_minutes)
    return limits.reminder_minutes


def _captain_start(payment: Payment, ride: Ride) -> datetime | None:
    """**متى تبدأ مواعيدُ تذكير الكبتن**: لحظةُ المرجع لكليك (§٢-٤)، **ولحظةُ الإقرار للكاش المُقَرّ به** وإلا نهايةُ الرحلة.

    **ساعةُ الإقرار لا ساعةُ الرحلة** (§٢-٥/٢: «خلال ٢٤ ساعة **من الإقرار** رغم أربعة تذكيرات»؛ §٣: «بعد ساعةٍ يُعدّ المبلغُ
    مستلَماً» لا تصدق إلا على ساعةٍ تبدأ بالإقرار): راكبٌ أقرّ بعد موعد الـ٢٣ ساعة **كان يُتمّ آلياً بلا تذكيرٍ واحدٍ بعد
    إقراره** ولا إنذار. **وحجبُ التوزيع يبقى على نهاية الرحلة** (`unconfirmed_rules.captain_clock`) — هذه مواعيدُ لا حدود.
    """
    if payment.method == PaymentMethod.CLIQ:
        return payment.cliq_reference_at
    return payment.declared_at or ride.completed_at


def warning_lead_minutes(limits: Thresholds) -> int:
    """**كم بين الإنذار الأخير والإتمام الآليّ** — «بعد ساعةٍ يُعدّ المبلغُ مستلَماً» (§٣): مهلةُ الإتمام ناقصَ موعد التذكير الرابع.

    **ومنه يُصاغ نصُّ الإنذار ويُؤجَّل الإتمامُ معاً**: إنذارٌ تأخّر كنسُه لا يُقصِّر ما وعد به — الإتمامُ بعده بهذه الدقائق لا
    قبلها. فما يقوله النصُّ هو ما يقع.
    """
    return max(limits.cash_auto_confirm_hours * 60 - limits.reminder_minutes[-1], 0)


def _awaits_captain(payment: Payment) -> bool:
    return payment.method == PaymentMethod.CASH or payment.cliq_reference_at is not None


def _awaits_rider(payment: Payment, ride: Ride) -> bool:
    if ride.payer != RidePayer.REQUESTER.value:
        return False
    if payment.method == PaymentMethod.CASH:
        return payment.declared_at is None
    return payment.cliq_reference_at is None


async def _auto_confirm_possible(
    session: AsyncSession, payment: Payment, ride: Ride, limits: Thresholds
) -> bool:
    """**أيُمكن أن يُتمّ هذا الصفُّ آلياً إن بقي الكبتنُ صامتاً؟** — ومنه نصُّ التذكير الرابع: إنذارٌ بإتمامٍ لا يقع كذب."""
    return (
        payment.method == PaymentMethod.CASH
        and payment.declared_at is not None
        and payment.amount <= limits.cash_auto_confirm_max
        and await auto_confirm_enabled(session, ride.country_code)
    )


async def _captain_text(
    session: AsyncSession,
    payment: Payment,
    ride: Ride,
    slot: int,
    limits: Thresholds,
    rider_name: str | None,
) -> tuple[str, str]:
    """**نصوصُ §٣ للكبتن** — الموعدان الأوّلان نصٌّ واحد، والثالثُ «منذ»، والرابعُ «بعد ساعةٍ…».

    **والرابعُ بحسب ما سيقع فعلاً** (انحرافٌ مقصودٌ عن جملةٍ واحدة): «يُعدّ المبلغُ مستلَماً كما أقرّ الراكب» **صادقةٌ
    للكاش المُقَرِّ به والإتمامُ مشتعل وحدَه** — ولكليك ولكاشٍ لم يُقَرّ به **كذبٌ** (لا إتمامَ آليَّ لهما، §٢-٤/§٢-٥).
    فلهما ما يقع: نزاعٌ آليٌّ لكليك، وإحالةٌ إلى الفريق للكاش.
    """
    money = _money(payment.amount, payment.currency)
    if slot <= 1 or slot >= len(limits.reminder_minutes):
        return f"رحلةُ {_first_name(rider_name)} بانتظار تأكيدك", f"استلمتَ {money}؟"
    if slot == 2:
        return (
            f"تأكيدٌ ينتظرك منذ {_minutes_phrase(limits.reminder_minutes[2])}",
            f"تُوقَف الطلباتُ الجديدةُ عند {_hours_phrase(limits.driver_block_hours)}",
        )

    start = _captain_start(payment, ride)
    sent_at = (start or _now()) + timedelta(minutes=limits.reminder_minutes[3])
    if await _auto_confirm_possible(session, payment, ride, limits):
        # **المهلةُ من الإعداد لا من موعدٍ نظريّ**: الإتمامُ يُؤجَّل حتى تمضي بعد إرسال الإنذار فعلاً (`_auto_criteria`)
        after = _after(warning_lead_minutes(limits))
        return (
            f"{after} يُعدّ المبلغُ مستلَماً كما أقرّ الراكب",
            "إن لم تستلمه فاضغط «لم يدفع» الآن",
        )
    if payment.method == PaymentMethod.CLIQ:
        expires = payment.cliq_confirmation_expires_at or sent_at
        after = _after(round((expires - sent_at).total_seconds() / 60))
        return (
            f"{after} تصير الحوالةُ نزاعاً لدى فريق TAXO",
            "إن وصلتك فاضغط «وصلتني»، وإلا فـ«لم تصلني» الآن",
        )
    escalation = (start or _now()) + timedelta(hours=ESCALATION_HOURS)
    after = _after(round((escalation - sent_at).total_seconds() / 60))
    return (
        f"{after} تُحال الدفعةُ إلى فريق TAXO",
        "أكّد الاستلام أو اضغط «لم يدفع» الآن",
    )


def _rider_text(payment: Payment, ride: Ride, slot: int, limits: Thresholds) -> tuple[str, str]:
    """**نصوصُ §٣ للراكب** — «سلّمتَ…؟» للكاش، **و«حوّلتَ…؟» لكليك بلا مرجع** (الجملةُ في التصميم نقدية، فتُكيَّف لكليك)."""
    money = _money(payment.amount, payment.currency)
    cash = payment.method == PaymentMethod.CASH
    if slot <= 1 or slot >= len(limits.reminder_minutes):
        if cash:
            return f"سلّمتَ الكبتن {money}؟", "أكّد ذلك كي تُغلق الرحلة"
        return f"حوّلتَ للكبتن {money}؟", "أدخل مرجع الحوالة كي تُغلق الرحلة"
    if slot == 2:
        return "دفعُ رحلتك غيرُ مؤكَّد", "لا يمكن طلبُ رحلةٍ جديدةٍ حتى يُحسم"
    minutes = _rider_minutes(payment, limits)
    after = _after(ESCALATION_HOURS * 60 - minutes[3])
    return (
        f"{after} تُحال رحلتُك إلى فريق TAXO",
        "أكّد تسليم المبلغ أو غيّر طريقة الدفع"
        if cash
        else "أدخل مرجع الحوالة أو غيّر طريقة الدفع",
    )


async def reminder_candidate_ids(session: AsyncSession) -> list[uuid.UUID]:
    """**قراءةٌ بلا قفل** — ثمّ قفلٌ لكلِّ صفٍّ على حدة في `remind_one` (نمطُ `payments.expired_cliq_payment_ids`)."""
    markets = await _enabled_markets(session, FeatureKey.UNCONFIRMED_PAYMENTS_ENABLED)
    if not markets:
        return []
    return list(
        (
            await session.scalars(
                select(Payment.id)
                .join(Ride, Ride.id == Payment.ride_id)
                .where(unconfirmed(), Ride.country_code.in_(markets))
                .order_by(Payment.created_at)
            )
        ).all()
    )


async def remind_one(
    session: AsyncSession, payment_id: uuid.UUID, *, now: datetime | None = None
) -> list[Notice]:
    """يختم الموعدَ المستحقَّ لكلِّ طرفٍ ويعيد إشعاراته — **ولا يرسل**: الإرسالُ بعد الـcommit.

    **القفلُ قبل قراءة العدد** (قاعدةُ `CLAUDE.md`): كنسان معاً — عاملان، أو دورةٌ طالت حتى بدأت التالية — يقرآن العددَ
    صفراً معاً بغيره، **فيصل الطرفَ التذكيرُ نفسُه مرّتين**. بالقفل ينتظر الثاني ثمّ يجد العددَ مختوماً فلا يرسل شيئاً.
    """
    moment = now or _now()
    payment = await payments_service.get_payment(session, payment_id, for_update=True)  # قفلُ التذكير
    if payment.status != PaymentStatus.PENDING or payment.method not in AWAITED_METHODS:
        return []
    ride = await session.get(Ride, payment.ride_id)
    if (
        ride is None
        or ride.completed_at is None
        # **في التدفّق وحدَه** (`unconfirmed_rules.in_flow`) — صفٌّ قديمٌ للطابور لا للتذكير
        or ride.payment_method_hint is None
        or not await enabled(session, ride.country_code)
    ):
        return []
    limits = await thresholds_for(session, ride.country_code)
    notices: list[Notice] = []

    if _awaits_captain(payment) and ride.driver_id is not None:
        start = _captain_start(payment, ride)
        slot = (
            _due_slot(
                limits.reminder_minutes, start, moment, reminded_at=payment.driver_reminded_at
            )
            if start is not None
            else None
        )
        if slot is not None:
            # **عددُ ما وصله حقاً** على ساعته الحالية — لا مؤشّرُ موعد (شرطُ الإتمام الآليّ يقرؤه)
            payment.driver_reminders += 1
            payment.driver_reminded_at = moment
            notices.append(await _captain_notice(session, payment, ride, slot, limits))

    if _awaits_rider(payment, ride):
        slot = _due_slot(
            _rider_minutes(payment, limits),
            ride.completed_at,
            moment,
            reminded_at=payment.rider_reminded_at,
        )
        if slot is not None:
            payment.rider_reminders += 1
            payment.rider_reminded_at = moment
            notices.append(_rider_notice(payment, ride, slot, limits))
    return notices


async def _captain_notice(
    session: AsyncSession, payment: Payment, ride: Ride, slot: int, limits: Thresholds
) -> Notice:
    driver_user_id = await session.scalar(select(Driver.user_id).where(Driver.id == ride.driver_id))
    rider_name = await session.scalar(select(User.name).where(User.id == ride.rider_id))
    title, body = await _captain_text(session, payment, ride, slot, limits, rider_name)
    return Notice(driver_user_id, REMINDER_KIND, title, body, payment.id, ride.id)


def _rider_notice(payment: Payment, ride: Ride, slot: int, limits: Thresholds) -> Notice:
    title, body = _rider_text(payment, ride, slot, limits)
    return Notice(ride.rider_id, REMINDER_KIND, title, body, payment.id, ride.id)


# ------------------------------------------------------- ٥) الإتمامُ الآليُّ للكاش


async def auto_confirm_candidate_ids(session: AsyncSession) -> list[uuid.UUID]:
    """كاشٌ معلَّقٌ أقرّ به الراكبُ في سوقٍ اشتعل فيه المفتاحان — **والشروطُ كلُّها تُفحص تحت القفل** في `auto_confirm_one`."""
    markets = await _enabled_markets(
        session,
        FeatureKey.UNCONFIRMED_PAYMENTS_ENABLED,
        FeatureKey.CASH_AUTO_CONFIRM_ENABLED,
    )
    if not markets:
        return []
    return list(
        (
            await session.scalars(
                select(Payment.id)
                .join(Ride, Ride.id == Payment.ride_id)
                .where(
                    unconfirmed(),
                    Payment.method == PaymentMethod.CASH,
                    Payment.declared_at.is_not(None),
                    Ride.country_code.in_(markets),
                )
                .order_by(Payment.declared_at)
            )
        ).all()
    )


async def _auto_criteria(
    session: AsyncSession, payment: Payment, ride: Ride, now: datetime
) -> dict[str, Any] | None:
    """**الشروطُ الخمسةُ مجتمعةً** (§٢-٥) — ومعاييرُها كما ستُجمَّد على الصفّ، أو `None` إن سقط واحد.

    **وما يُمنع دائماً**: كليك (القناةُ هنا كاشٌ وحدَه)، و«رحلةٌ أُنهيت آلياً ولم يُقِرّ الراكبُ بالوصول» (**الإنهاءُ الآليُّ لم
    يُبنَ** — فكلُّ رحلةٍ هنا أنهاها كبتنُها)، و«دفعةٌ جزئيّةٌ يختلف فيها المتبقّي عمّا أقرّه» (**الإقرارُ على صفٍّ مبلغُه مجمَّد**،
    فما أقرّه هو مبلغُ الصفِّ حرفاً ولا يفترقان).
    """
    if (
        payment.status != PaymentStatus.PENDING
        or payment.method != PaymentMethod.CASH
        or payment.declared_at is None
        or ride.payer != RidePayer.REQUESTER.value
        # **في التدفّق وحدَه** (`unconfirmed_rules.in_flow`): صفٌّ قديمٌ لا يُتمّ آلياً أبداً — للطابور
        or ride.payment_method_hint is None
        or not await auto_confirm_enabled(session, ride.country_code)
    ):
        return None
    limits = await thresholds_for(session, ride.country_code)
    # ١) إقرارٌ صريح — مفحوصٌ أعلاه. ٢) صمتُ الكبتن مهلتَه **رغم أربعة تذكيراتٍ وصلته بعد الإقرار، آخرُها الإنذار**:
    #    - العدّادُ عددُ ما أُرسل حقاً على ساعة الإقرار (يُصفَّر عند الإقرار، `+1` لكلِّ تذكير) — **لا مؤشّرُ موعدٍ يقفز**؛
    #    - **والإنذارُ** («بعد ساعةٍ يُعدّ المبلغُ مستلَماً») **أُرسل بعد الإقرار** في موعده الأخير على ساعته؛
    #    - **ومضت بعده المهلةُ التي وعد بها** — كنسٌ تأخّر لا يُقصِّرها.
    #    وما لم يجتمع يُؤجَّل لا يُرفض: الدفعةُ في الطابور والمشرفُ يراها (§٢-٣).
    warning_due = payment.declared_at + timedelta(minutes=limits.reminder_minutes[-1])
    lead = warning_lead_minutes(limits)
    if now < payment.declared_at + timedelta(hours=limits.cash_auto_confirm_hours):
        return None
    if payment.driver_reminders < len(limits.reminder_minutes):
        return None
    if payment.driver_reminded_at is None or payment.driver_reminded_at < warning_due:
        return None
    if now < payment.driver_reminded_at + timedelta(minutes=lead):
        return None
    # ٣) السقف
    if payment.amount > limits.cash_auto_confirm_max:
        return None
    # ٤) لا حكمَ «لم يدفع» على الراكب في النافذة، والكبتنُ غيرُ موقوف
    rulings = await unpaid_rulings(
        session, ride.rider_id, window_days=limits.cash_off_window_days, now=now
    )
    if rulings > 0:
        return None
    driver = await session.get(Driver, ride.driver_id) if ride.driver_id else None
    if driver is None or driver.status == DriverStatus.SUSPENDED:
        return None
    # ٥) لا نزاعَ مفتوحاً على الرحلة نفسِها
    if await session.scalar(
        select(Payment.id).where(
            Payment.ride_id == ride.id, Payment.status == PaymentStatus.DISPUTED
        )
    ):
        return None

    return {
        "rule": "cash_auto_confirm",
        "declared_at": payment.declared_at.isoformat(),
        "hours": limits.cash_auto_confirm_hours,
        "max_amount": str(limits.cash_auto_confirm_max),
        "amount": str(payment.amount),
        "reminders_required": len(limits.reminder_minutes),
        #: **ما وصله حقاً بعد الإقرار** — عددٌ لا مؤشّر
        "reminders_sent": payment.driver_reminders,
        "reminder_minutes": list(limits.reminder_minutes),
        #: **الإنذارُ الأخير** ووقتُه والمهلةُ التي وعد بها — آخرُ تذكيرٍ مختومٍ هو هو
        "warning_sent_at": payment.driver_reminded_at.isoformat(),
        "warning_lead_minutes": lead,
        "rider_unpaid_rulings": rulings,
        "rulings_window_days": limits.cash_off_window_days,
        "driver_status": driver.status.value,
        "objection_window_hours": limits.dispute_window_hours,
        "evaluated_at": now.isoformat(),
    }


async def auto_confirm_one(
    session: AsyncSession, payment_id: uuid.UUID, *, now: datetime | None = None
) -> Payment | None:
    """**يُتمّ دفعةً واحدةً آلياً إن اجتمعت شروطُها** — ويكتب **ما يكتبه تأكيدُ الكبتن حرفاً** (`payments.settle`) بـ`auto_rule`.

    **القفلُ قبل الفحص**: بغيره يُقرأ `pending` بينما يضغط الكبتنُ «استلمت» في المعاملة المجاورة، **فيُكتب «أتمّته القاعدة»
    فوق تأكيدِ إنسان** وتُفتح عليه نافذةُ اعتراضٍ على مالٍ أكّده هو. و`None` ليست فشلاً: الكبتنُ تكلّم قبل القاعدة.

    **والمعاييرُ تُكتب قبل `settle`**: قيدُ `payment_auto_rule_criteria` يُفحص عند كلِّ `flush`، و`settle` يُفرغ في منتصفه.
    """
    moment = now or _now()
    payment = await payments_service.get_payment(session, payment_id, for_update=True)  # قفلُ الإتمام الآليّ
    ride = await session.get(Ride, payment.ride_id)
    if ride is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
        return None
    criteria = await _auto_criteria(session, payment, ride, moment)
    if criteria is None:
        return None
    rider = await session.get(User, ride.rider_id)
    payment.auto_confirm_criteria = criteria
    await payments_service.settle(
        session,
        payment=payment,
        ride=ride,
        rider=rider,
        confirmed_by=PaymentConfirmedBy.AUTO_RULE,
        actor_id=None,
    )
    return payment


async def auto_confirmed_notice(session: AsyncSession, payment: Payment) -> Notice | None:
    """«عُدّ مبلغُ رحلة ليلى مستلَماً لأنها أقرّت بتسليمه ولم تعترض — إن لم تستلمه فاعترض قبل {الوقت}» (§٦)."""
    ride = await session.get(Ride, payment.ride_id)
    if ride is None or ride.driver_id is None:
        return None
    driver_user_id = await session.scalar(select(Driver.user_id).where(Driver.id == ride.driver_id))
    rider = await session.get(User, ride.rider_id)
    deadline = objection_deadline(payment)
    female = rider is not None and rider.gender == Gender.FEMALE
    told = "أقرّت بتسليمه ولم تعترض" if female else "أقرّ بتسليمه ولم يعترض"
    return Notice(
        driver_user_id,
        AUTO_CONFIRMED_KIND,
        f"عُدّ مبلغُ رحلة {_first_name(rider.name if rider else None)} مستلَماً",
        f"لأن الراكب{'ة' if female else ''} {told} — إن لم تستلمه فاعترض قبل "
        f"{await _local(session, ride.country_code, deadline)}",
        payment.id,
        ride.id,
    )


async def _local(session: AsyncSession, country: CountryCode, moment: datetime | None) -> str:
    """وقتٌ بتوقيت السوق — **«قبل 21:58» بلا توقيتٍ كذبةٌ بثلاث ساعات** (قاعدةُ «يومُ السوق» في `stats.py`)."""
    if moment is None:
        return ""
    from app.services import campaigns

    setting = await campaigns.get_settings(session, country)
    zone_name = (
        setting.timezone
        if setting is not None
        else _MARKET_TIMEZONE.get(CountryCode(country), _MARKET_TIMEZONE[CountryCode.JO])
    )
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError):  # pragma: no cover - إعدادٌ خاطئ
        zone = ZoneInfo(_MARKET_TIMEZONE[CountryCode.JO])
    return moment.astimezone(zone).strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ ٤) الطابور


@dataclass(slots=True)
class QueueParty:
    user_id: uuid.UUID
    name: str
    phone: str | None
    pending_count: int
    #: **شارةُ «حساب تجربة»** في صفِّ الطابور (SPEC §٦٥-ج) — بلا افتراض: بانٍ ينساه يسقط
    is_test: bool
    driver_id: uuid.UUID | None = None


@dataclass(slots=True)
class QueueRow:
    payment: Payment
    ride: Ride
    state: str
    age_minutes: int
    rider: QueueParty
    driver: QueueParty | None
    trail: list[tuple[str, datetime]] = field(default_factory=list)
    #: **في التدفّق** (`unconfirmed_rules.in_flow`) — وخارجَه صفٌّ سبق المفتاحَ أو جاء من تطبيقٍ قديم: **لا تذكيرَ ولا حجبَ
    #: ولا إتمامَ آليَّ عليه**، والطابورُ وحدَه يحسمه
    in_flow: bool = True


def queue_state(payment: Payment, ride: Ride) -> str:
    """**الحالُ في الطابور** (§٥) — خمسٌ من ستّ: **«رحلةٌ لم تُنهَ» لا تُنتَج** لأن الإنهاءَ الآليَّ وقراءتَه (§٢-٢) لم يُبنيا.

    و«بانتظار الراكب» كاشٌ لم يُقَرّ به **ولرحلةٍ يدفعها طالبُها** — فما يدفعه راكبٌ فعليٌّ نقداً ينتظر الكبتنَ وحدَه.
    """
    if payment.status == PaymentStatus.DISPUTED:
        return "disputed"
    if payment.status == PaymentStatus.CONFIRMED:
        return "auto_confirmed_objected"
    if payment.method == PaymentMethod.CLIQ:
        return "awaiting_captain" if payment.cliq_reference_at is not None else "cliq_no_reference"
    if payment.declared_at is None and ride.payer == RidePayer.REQUESTER.value:
        return "awaiting_rider"
    return "awaiting_captain"


def _objection_open():
    """**إتمامٌ آليٌّ اعترض عليه الكبتنُ ولم يُحكم فيه** — يبقى في الطابور **أيّاً كان المفتاح** (`_queue_scope`)."""
    return (
        (Payment.status == PaymentStatus.CONFIRMED)
        & (Payment.confirmed_by == PaymentConfirmedBy.AUTO_RULE)
        & Payment.objected_at.is_not(None)
        & Payment.resolution.is_(None)
    )


def is_objection_open(payment: Payment) -> bool:
    return (
        payment.status == PaymentStatus.CONFIRMED
        and payment.confirmed_by == PaymentConfirmedBy.AUTO_RULE
        and payment.objected_at is not None
        and payment.resolution is None
    )


def _queue_scope(markets: Sequence[CountryCode]):
    """**ما يدخل الطابور**: المعلَّقُ كلُّه — **قديماً كان أو في التدفّق** (`pending_awaited`) — والنزاعات، في أسواقٍ اشتعل فيها
    المفتاح؛ **والاعتراضُ المفتوحُ في كلِّ سوق**.

    **الاعتراضُ لا يُشترط له المفتاح** (مراجعةُ ٢٠٢٦-١٠-٠٧): بابُه (`object_auto_confirm`) يعمل مطفأً — حقُّ الكبتن لا يسقط
    بإطفاء الميزة بعد أن أُتمّ مالُه آلياً — **فطابورٌ يحجبه مطفأً يُضيّع اعتراضاً لا يحكم فيه أحد**، والدفعةُ مؤكَّدةٌ عليه.
    """
    in_market = or_(pending_awaited(), Payment.status == PaymentStatus.DISPUTED) & Ride.country_code.in_(
        list(markets)
    )
    return or_(in_market, _objection_open())


async def queue(
    session: AsyncSession,
    *,
    country: CountryCode | None,
    limit: int,
    offset: int,
    now: datetime | None = None,
) -> list[QueueRow]:
    """**«المدفوعاتُ غيرُ المؤكَّدة» — الأقدمُ أوّلاً** (§٥، A10/AM05)، **لأسواقٍ اشتعل فيها المفتاحُ** — والاعتراضُ المفتوحُ في كلِّها.

    **والمعلَّقُ القديمُ هنا وحدَه** (`unconfirmed_rules.in_flow`): صفٌّ سبق المفتاحَ يحسمه المشرف، ولا تذكيرَ ولا حجبَ عليه —
    و`in_flow` على الصفِّ يقول أيَّهما هو.

    **ومجاميعُ الطرفين والأثرُ تُقرأ لصفحةٍ كاملةٍ بثلاثة استعلامات** لا استعلامٍ لكلِّ صف — صفحةُ خمسين لا تصير مئةً وخمسين.
    والأثرُ من صندوق الوارد (`kind = payment_reminder`): **ما أُرسل فعلاً بوقته** — والختمُ على الصفِّ عددٌ وآخرُ وقت.
    """
    moment = now or _now()
    markets = await _enabled_markets(session, FeatureKey.UNCONFIRMED_PAYMENTS_ENABLED)
    scope = _queue_scope(markets)
    if country is not None:
        scope = scope & (Ride.country_code == country)

    rows = (
        await session.execute(
            select(Payment, Ride)
            .join(Ride, Ride.id == Payment.ride_id)
            .where(scope)
            .order_by(Ride.completed_at.asc().nulls_last(), Payment.created_at)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    if not rows:
        return []

    rider_ids = {ride.rider_id for _payment, ride in rows}
    driver_ids = {ride.driver_id for _payment, ride in rows if ride.driver_id is not None}
    riders = {
        user.id: user
        for user in (await session.scalars(select(User).where(User.id.in_(rider_ids)))).all()
    }
    drivers = {
        driver.id: (driver, user)
        for driver, user in (
            await session.execute(
                select(Driver, User)
                .join(User, User.id == Driver.user_id)
                .where(Driver.id.in_(driver_ids))
            )
        ).all()
    }
    rider_counts = dict(
        (
            await session.execute(
                select(Ride.rider_id, func.count(Payment.id))
                .join(Ride, Ride.id == Payment.ride_id)
                .where(pending_awaited(), Ride.rider_id.in_(rider_ids))
                .group_by(Ride.rider_id)
            )
        ).all()
    )
    driver_counts = (
        dict(
            (
                await session.execute(
                    select(Ride.driver_id, func.count(Payment.id))
                    .join(Ride, Ride.id == Payment.ride_id)
                    .where(pending_awaited(), Ride.driver_id.in_(driver_ids))
                    .group_by(Ride.driver_id)
                )
            ).all()
        )
        if driver_ids
        else {}
    )
    payment_ids = [str(payment.id) for payment, _ride in rows]
    trail_rows = (
        await session.execute(
            select(
                UserNotification.data["payment_id"].astext,
                UserNotification.user_id,
                UserNotification.created_at,
            )
            .where(
                UserNotification.kind == REMINDER_KIND,
                UserNotification.data["payment_id"].astext.in_(payment_ids),
            )
            .order_by(UserNotification.created_at)
        )
    ).all()
    trails: dict[str, list[tuple[uuid.UUID, datetime]]] = {}
    for payment_id, user_id, created_at in trail_rows:
        trails.setdefault(payment_id, []).append((user_id, created_at))

    result: list[QueueRow] = []
    for payment, ride in rows:
        rider = riders[ride.rider_id]
        driver_party = None
        driver_user_id = None
        if ride.driver_id is not None and ride.driver_id in drivers:
            driver, driver_user = drivers[ride.driver_id]
            driver_user_id = driver_user.id
            driver_party = QueueParty(
                user_id=driver_user.id,
                name=driver_user.name,
                phone=driver_user.phone,
                pending_count=int(driver_counts.get(driver.id, 0)),
                is_test=driver_user.is_test,
                driver_id=driver.id,
            )
        started = ride.completed_at or payment.created_at
        result.append(
            QueueRow(
                payment=payment,
                ride=ride,
                state=queue_state(payment, ride),
                age_minutes=max(int((moment - started).total_seconds() // 60), 0),
                rider=QueueParty(
                    user_id=rider.id,
                    name=rider.name,
                    phone=rider.phone,
                    pending_count=int(rider_counts.get(rider.id, 0)),
                    is_test=rider.is_test,
                ),
                driver=driver_party,
                trail=[
                    ("captain" if user_id == driver_user_id else "rider", created_at)
                    for user_id, created_at in trails.get(str(payment.id), [])
                ],
                in_flow=ride.payment_method_hint is not None,
            )
        )
    return result


def _reason(reason: str) -> str:
    cleaned = (reason or "").strip()
    if len(cleaned) < MIN_REASON_LENGTH:
        raise InvalidInput(
            f"اكتب سبباً من {MIN_REASON_LENGTH} أحرف على الأقل", field="reason"
        )
    return cleaned[:255]


async def _queue_ride(session: AsyncSession, payment: Payment) -> Ride:
    """رحلةُ صفِّ الطابور — **والمفتاحُ شرطُ كلِّ فعلٍ إلا الحكمَ في اعتراضٍ مفتوح** (`_queue_scope`: يبقى أيّاً كان المفتاح)."""
    ride = await payments_service.ride_of(session, payment)
    if not is_objection_open(payment):
        await _require_enabled(session, ride.country_code)
    return ride


def _stamp_ruling(
    payment: Payment, *, outcome: DisputeResolution, actor: User, note: str
) -> None:
    payment.resolution = outcome
    payment.resolution_note = note
    payment.resolved_by = actor.id
    payment.resolved_at = _now()


def _require_unconfirmed(payment: Payment, ride: Ride) -> None:
    if (
        payment.status != PaymentStatus.PENDING
        or payment.method not in AWAITED_METHODS
        or ride.completed_at is None
    ):
        raise InvalidPaymentTransition("هذه الدفعة ليست معلَّقةً تنتظر أحداً")


async def admin_remind(
    session: AsyncSession, *, payment: Payment, actor: User, reason: str
) -> list[Notice]:
    """**«أرسل تذكيراً الآن»** للطرف المنتظَر (§٥) — **ولا يمسّ مواعيدَ الجدول**: التذكيراتُ الأربعُ شرطُ الإتمام الآليّ، وتذكيرٌ
    يدويٌّ يُعدّ منها يُقرِّب الإتمامَ بضغطة مشرف."""
    cleaned = _reason(reason)
    ride = await _queue_ride(session, payment)
    _require_unconfirmed(payment, ride)
    limits = await thresholds_for(session, ride.country_code)
    notices: list[Notice] = []
    if _awaits_captain(payment) and ride.driver_id is not None:
        notices.append(await _captain_notice(session, payment, ride, 0, limits))
    if _awaits_rider(payment, ride):
        notices.append(_rider_notice(payment, ride, 0, limits))
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="payment",
        entity_id=payment.id,
        details={
            "via": "unconfirmed_queue",
            "action": "remind",
            "reason": cleaned,
            "sent_to": reminded_sides(notices, ride),
        },
    )
    return notices


def reminded_sides(notices: Sequence[Notice], ride: Ride) -> list[str]:
    return ["rider" if notice.user_id == ride.rider_id else "captain" for notice in notices]


async def admin_resolve(
    session: AsyncSession,
    *,
    payment: Payment,
    actor: User,
    outcome: DisputeResolution,
    reason: str,
) -> Payment:
    """**«احسم: مدفوع» / «احسم: غيرُ مدفوع»** (§٥/§٨) — بسببٍ مكتوبٍ يدخل التدقيق.

    - **معلَّقةٌ أو في نزاع**: «مدفوع» ← **ما يكتبه التأكيدُ حرفاً** (`settle`، `confirmed_by = admin`)؛ «غيرُ مدفوع» ← `failed`
      **ولا قيد**، فيعود المبلغُ مستحقّاً على الرحلة (القائم).
    - **مُتمٌّ آلياً ومعترَضٌ عليه**: «مدفوع» ← يُقفل الاعتراضُ **ولا يُكتب شيء** (القيودُ كُتبت يومَ الإتمام). «غيرُ مدفوع» ←
      **يُردّ** (`ObjectionCounterEntryPending`).

    **ويُنادى وصفُّ الدفعة مقفول** (الموجّه): بغيره يحسم المشرفُ «مدفوع» على صفٍّ أكّده الكبتنُ في اللحظة نفسِها، فيُكتب
    حكمان لواقعةٍ واحدة.

    **والمعلَّقُ والنزاعُ يُحكمان من `payments.resolve_dispute` نفسِه** — بابُ الحكم الواحد لبابَي اللوحة (مراجعةُ ٢٠٢٦-١٠-٠٧):
    نسخةٌ هنا كانت تفترق عنه في السبب والتدقيق، فيُحكم النزاعُ نفسُه بقاعدتين بحسب الباب.
    """
    cleaned = _reason(reason)
    ride = await _queue_ride(session, payment)

    if is_objection_open(payment):
        if outcome == DisputeResolution.UNPAID:
            # TODO(§٨ «اعتراضٌ بعد إتمامٍ تلقائيّ» — القيدُ المقابل): حكمُ «غيرُ مدفوع» هنا يجب أن **يكتب قيداً مقابلاً لكلِّ
            # ما كتبه الإتمامُ الآليّ** ولا يحذف شيئاً — عكسُ دَين العمولة (`driver_debts`: شطبٌ إن كان قائماً، أو قيدُ
            # `adjustment` موجبٌ لكبتنٍ حُصِّلت منه بـ`commission`)، **وعكسُ حمل رسم الإلغاء** (`cancellation.collect_with_ride`)،
            # وإعادةُ المستحقّ على الرحلة دَيناً على الراكب. **وهو أكبرُ مما يبدو** — فلم يُبنَ، ويُردّ الحكمُ صراحةً حتى يُبنى.
            raise ObjectionCounterEntryPending()
        _stamp_ruling(payment, outcome=DisputeResolution.PAID, actor=actor, note=cleaned)
        await audit.record(
            session,
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type="payment",
            entity_id=payment.id,
            details={
                "via": "unconfirmed_queue",
                "action": "resolve",
                "status": payment.status.value,
                "resolution": DisputeResolution.PAID.value,
                "reason": cleaned,
            },
        )
        return payment

    if payment.status == PaymentStatus.PENDING:
        _require_unconfirmed(payment, ride)
    elif payment.status != PaymentStatus.DISPUTED:
        raise InvalidPaymentTransition("هذه الدفعة ليست في طابور المعلَّقات")
    return await payments_service.resolve_dispute(
        session,
        payment=payment,
        actor=actor,
        resolution=outcome,
        note=cleaned,
        allow_pending=True,
        details={"via": "unconfirmed_queue", "action": "resolve", "reason": cleaned},
    )


async def admin_dispute(
    session: AsyncSession, *, payment: Payment, actor: User, reason: str
) -> list[Notice]:
    """**«حوّل إلى نزاع»** (§٥) ← `disputed` **ويُسأل الطرفان بنصّهما** بعد الـcommit. لا قيد."""
    cleaned = _reason(reason)
    ride = await _queue_ride(session, payment)
    _require_unconfirmed(payment, ride)
    payments_service.require_transition(payment, PaymentStatus.DISPUTED)
    payment.status = PaymentStatus.DISPUTED
    payment.dispute_reason = cleaned
    payment.disputed_at = _now()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="payment",
        entity_id=payment.id,
        details={"via": "unconfirmed_queue", "action": "dispute", "reason": cleaned},
    )
    money = _money(payment.amount, payment.currency)
    # **«يُسأل الطرفان بنصّهما»** (§٥) — **ونصُّ كليك حوالةٌ لا تسليم** (كما في `_rider_text`): من حوّل من بنكه يُسأل «حوّلتَ؟»
    # ومرجعُه إن لم يُدخله، والكبتنُ «وصلتك؟» لا «استلمتَ؟»
    if payment.method == PaymentMethod.CLIQ:
        rider_body = (
            f"هل حوّلتَ {money}؟ افتح التطبيق لتردّ"
            if payment.cliq_transfer_reference is not None
            else f"هل حوّلتَ {money}؟ أدخل مرجع الحوالة أو افتح التطبيق لتردّ"
        )
        captain_body = f"هل وصلتك حوالةُ {money}؟ افتح التطبيق لتردّ"
    else:
        rider_body = f"هل سلّمتَ {money}؟ افتح التطبيق لتردّ"
        captain_body = f"هل استلمتَ {money}؟ افتح التطبيق لتردّ"
    notices: list[Notice] = []
    if ride.payer == RidePayer.REQUESTER.value:
        notices.append(
            Notice(
                ride.rider_id,
                DISPUTED_KIND,
                "أحال فريقُ TAXO دفعَ رحلتك إلى نزاع",
                rider_body,
                payment.id,
                ride.id,
            )
        )
    if ride.driver_id is not None:
        driver_user_id = await session.scalar(
            select(Driver.user_id).where(Driver.id == ride.driver_id)
        )
        notices.append(
            Notice(
                driver_user_id,
                DISPUTED_KIND,
                "أحال فريقُ TAXO الدفعةَ إلى نزاع",
                captain_body,
                payment.id,
                ride.id,
            )
        )
    return notices


async def captain_dispute_notice(session: AsyncSession, payment: Payment) -> Notice | None:
    """**«يقول الكبتن إنه لم يستلم — هل سلّمتَ المبلغ؟»** (§٢-٣) — يُسأل الراكبُ فوراً بعد «لم يدفع» على الكاش."""
    if payment.method != PaymentMethod.CASH or payment.status != PaymentStatus.DISPUTED:
        return None
    ride = await session.get(Ride, payment.ride_id)
    if ride is None or ride.payer != RidePayer.REQUESTER.value:
        return None
    return Notice(
        ride.rider_id,
        DISPUTED_KIND,
        "الكبتنُ يقول إنه لم يستلم المبلغ",
        f"هل سلّمتَ {_money(payment.amount, payment.currency)}؟ افتح التطبيق لتردّ",
        payment.id,
        ride.id,
    )
