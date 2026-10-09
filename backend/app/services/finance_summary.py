"""الملخّصاتُ المالية في اللوحة (SPEC §٦٥-د) — **قراءةٌ وحدَها، وكلُّ رقمٍ من الدفتر وجداول المال القائمة**.

## قواعدُ المالك التسع، وأين تقع كلٌّ منها في هذا الملفّ

1. **قراءةٌ وحدَها**: لا دالّةَ هنا تكتب صفّاً — **ولا `get_or_create`**: إعداداتُ المحفظة والسقف تُقرأ بـ`select` فإن غابت قُرئ
   غيابُها (احتجازٌ صفر، لا سقف)، ولا يُنشأ صفُّ إعداداتٍ لأن مشرفاً فتح صفحةً. **والكتابةُ الوحيدةُ سطرُ التدقيق**، يكتبه الموجّه.
2. **كلُّ مجموعٍ تعريفُه بجانبه** (`Metric.definition`) — **والنصُّ نفسُه يُنشر للّوحة** فيقرأ المشرفُ من أين جاء الرقم، **فلا
   يفترق تعريفٌ في تعليقٍ عن تعريفٍ في شاشة**.
3. **السوقُ واحدٌ في كلِّ مرّة** (`CountryCode` إلزاميّ) **ولا مجموعَ يعبر سوقين**: دينارٌ أردنيٌّ لا يُجمع إلى ليبيّ، فلا «كلّ
   الأسواق» هنا أصلاً. **والفترةُ بيوم السوق** — المِنطقةُ نفسُها التي يقرؤها `stats.py`.
4. **من أيِّ مجموعٍ تُفتح صفوفُه**: كلُّ مجموعٍ **صفوفٌ** (`rows`) بأعمدةٍ واحدة، **ومنها وحدَها** يُحسب الرقمُ (`_aggregate`)
   والمستخدمون (`users_page`) والمعاملات (`transactions_page`) — **فلا يفترق رقمُ البطاقة عمّا وراءها**: هما الاستعلامُ نفسُه.
5. **والتصديرُ يقرأ الدوالَّ نفسَها** (`finance_export.py`) — لا استعلامَ ثانياً يفترق.
6. **حساباتُ التجربة مستثناةٌ دائماً** — بشروط `test_accounts` لا بشرطٍ يُكتب هنا بصيغته.
8. **المطابقةُ** (`reconcile`): أرصدةُ المحافظ ومجاميعُ الدفتر بالنوع **تُحسب ثانيةً بـSQL خامٍ لا يمرّ بالصفوف أعلاه**، وتُقارن
   بمجاميع الصفحة. **والمقارنةُ دالّةٌ محضة** (`compare`) يُغذّيها اختبارٌ بقيمةٍ مزوّرةٍ فتصيح.

## المخزونُ والتدفّق — **سؤالان لا سؤالٌ واحد**

«كم يدين TAXO للكباتن» **رصيدٌ الآن** لا حركةُ فترة — فالمجاميعُ المخزونة (`stock=True`) **لا تقرأ الفترة**: تُحسب على الدفتر كلِّه
حتى الآن، **وتقول ذلك في الشاشة**. وما سواها (الشحن، العمولة، الرسوم…) **حركةُ الفترة** بحدود يوم السوق.

## والمرشِّحُ الذي لا ينطبق يُقال ولا يُطبَّق بصمت

**بطاقةٌ لا طريقةَ دفعٍ لها** (العمولةُ المحصَّلة من الدفتر) **لا تُصفَّر حين يختار المشرفُ «كاش»** — صفرٌ هناك يُقرأ «لا عمولةَ
على الكاش» وهو كذب. **فتُعلَّم `applicable=False` بعلّتها**، وترسمها اللوحةُ «لا ينطبق» لا رقماً.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal, get_args
from zoneinfo import ZoneInfo

from sqlalchemy import (
    CompoundSelect,
    Numeric,
    Select,
    String,
    and_,
    case,
    cast,
    false,
    func,
    literal,
    literal_column,
    null,
    or_,
    select,
    text,
    union_all,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.currency import currency_for_country
from app.core.exceptions import InvalidInput, NotFound
from app.core.phone import mask_phone
from app.models.cancellation import RideCancellationCharge
from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import (
    CancellationChargeStatus,
    CountryCode,
    Currency,
    DriverDebtStatus,
    DriverStatus,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    RideStatus,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.payment import Payment
from app.models.payment_setting import PaymentSetting
from app.models.provider_order import ProviderOrder
from app.models.ride import Ride
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.user import User
from app.models.wallet import (
    PENDING_WITHDRAWAL_STATUSES,
    WalletTopupRequest,
    WalletTransaction,
    WithdrawalRequest,
)
from app.models.wallet_freeze import WalletFreeze
from app.models.wallet_setting import WalletSetting
from app.services import stats, test_accounts
from app.services.payments import REFUNDABLE_METHODS

_MONEY = Numeric(12, 3)
_UUID = PgUUID(as_uuid=True)
_STEP = Decimal("0.001")

#: **سقفُ الفترة المخصَّصة** — سنةٌ وزيادةُ يوم: مقارنةُ عامٍ بعامٍ ممكنة، وطلبُ عشر سنواتٍ يمسح الدفترَ كلَّه في نداءٍ واحد
MAX_CUSTOM_DAYS = 366
#: **صفحةُ ما وراء البطاقة** — كسقف الطابور (`admin_unconfirmed_payments.py`): مئتان، وما بعدها صفحةٌ تالية
MAX_PAGE = 200


def money(value: object) -> Decimal:
    """**المالُ بثلاث خاناتٍ دائماً** (الشكلُ السابع): مجموعٌ فارغٌ يعود `0` لا `0.000` — وكلُّ مبلغٍ يخرج من هنا يمرّ به."""
    return Decimal(value or 0).quantize(_STEP)


# ═════════════════════════════════════════════════════════════ المرشِّحات


#: الفترة — **ثلاثُ نوافذَ كـ«التقارير»** (`stats.PERIOD_DAYS`) **ومخصَّصةٌ بتاريخين** بيوم السوق.
#:
#: **حرفيّةٌ لا `StrEnum`** — كبابِ «التقارير» نفسِه (`admin_stats.reports`): **قِيس ٢٠٢٦-١٠-٠٨** أن تعداداً فيه `today` يجعل
#: `check:enums` في التطبيقين يقرأ اتحادَ العرض `NotificationsT2.Group` («اليوم · أمس · أقدم») **مخلوطاً** — فيقف البناءُ على
#: شاشةٍ لا تعرف هذه الصفحة. **والحرفيّةُ تُقبل في الباب وتُنشر كما هي**، ولا تدخل قائمةَ قيم التعدادات.
FinancePeriod = Literal["today", "week", "month", "custom"]
PERIODS: tuple[str, ...] = get_args(FinancePeriod)
CUSTOM: FinancePeriod = "custom"


class FinanceUserType(StrEnum):
    """نوعُ المستخدم — **قيمُ `WalletOwnerType` نفسُها**: «راكب» و«كبتن» هما المحفظتان."""

    RIDER = "rider"
    DRIVER = "driver"


class FinanceMethod(StrEnum):
    """طريقةُ الدفع في المرشِّح — **قيمُ `PaymentMethod` التي يختارها إنسان**؛ وقنواتُ المنصّة (الكوبون والمشاركة) بطاقاتٌ لا مرشِّح."""

    CASH = "cash"
    CLIQ = "cliq"
    CARD = "card"
    WALLET = "wallet"


class FinanceStatus(StrEnum):
    """الحال — **ثلاثٌ كما رسمها طلبُ التصميم**: مؤكَّد · غيرُ مؤكَّد · متنازَعٌ عليه.

    **و«مؤكَّد» يشمل كلَّ قيدٍ في الدفتر**: الدفترُ لا يُكتب فيه إلا مالٌ وقع، فلا قيدَ «غيرُ مؤكَّد» — وبطاقاتُ الدفتر تقبل
    «مؤكَّد» وحدَه وترسم «لا ينطبق» لما سواه.
    """

    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    DISPUTED = "disputed"


class FinanceRowSource(StrEnum):
    """**من أيِّ جدولٍ جاء الصفّ** — فتعرف اللوحةُ كيف تسمّي نوعَه بخرائطها القائمة (`WALLET_TX_LABEL`…) لا بنسخةٍ ثانية."""

    LEDGER = "ledger"
    PAYMENT = "payment"
    DEBT = "debt"
    SUBSCRIPTION = "subscription"
    CHARGE = "charge"
    POSITION = "position"
    RIDE_FEE = "ride_fee"


class FinanceView(StrEnum):
    """ما يُصدَّر — **العروضُ الثلاثةُ نفسُها**: الملخّص، ومستخدمو مجموعٍ، ومعاملاتُه."""

    SUMMARY = "summary"
    USERS = "users"
    TRANSACTIONS = "transactions"


@dataclass(frozen=True, slots=True)
class Scope:
    """كلُّ ما يُقرأ به رقم — **السوقُ ونافذتُه ومرشِّحاتُه** في كائنٍ واحدٍ يمرّ بكلِّ استعلام."""

    country: CountryCode
    currency: Currency
    zone: ZoneInfo
    period: FinancePeriod
    from_at: datetime
    to_at: datetime
    now: datetime
    user_type: FinanceUserType | None = None
    method: FinanceMethod | None = None
    status: FinanceStatus | None = None

    @property
    def filtered(self) -> bool:
        return any(value is not None for value in (self.user_type, self.method, self.status))

    def unfiltered(self) -> Scope:
        """**السوقُ والفترةُ وحدَهما** — ما تقارنه المطابقةُ بالدفتر، فمرشِّحُ «كاش» لا يُقرأ فرقاً عن الدفتر."""
        return replace(self, user_type=None, method=None, status=None)


def window(
    zone: ZoneInfo,
    period: FinancePeriod,
    now: datetime,
    from_date: date | None,
    to_date: date | None,
) -> tuple[datetime, datetime]:
    """**[بداية، نهاية)** بمِنطقة السوق — نصفُ مفتوحة، **ونهايتُها منتصفُ ليلِ اليوم التالي** لا «الآن».

    **ولمَ لا «الآن»**: «اليوم» يومٌ كامل بحدّيه، **وقيدٌ كُتب في الثانية التي تلي نداءً سابقاً لا يسقط بين نافذتين**. والقيودُ
    في المستقبل لا وجودَ لها، فالحدُّ الأعلى لا يُدخل شيئاً لم يقع.

    **والمخصَّصةُ تاريخان شاملان بيوم السوق**: «من ١ إلى ٣٠» تعني منتصفَ ليل عمّان يومَ ١ حتى منتصفِ ليلها بعد يوم ٣٠ —
    **لا أيامَ UTC**، فخادمٌ على UTC يقصّ ثلاثَ ساعاتٍ من أوّلها ويضمّ ثلاثاً من آخرها.
    """
    if period == CUSTOM:
        if from_date is None or to_date is None:
            raise InvalidInput("الفترةُ المخصَّصة تحتاج تاريخَي البداية والنهاية")
        if from_date > to_date:
            raise InvalidInput("تاريخُ البداية بعد تاريخ النهاية")
        if (to_date - from_date).days + 1 > MAX_CUSTOM_DAYS:
            raise InvalidInput(f"الفترةُ المخصَّصة لا تتجاوز {MAX_CUSTOM_DAYS} يوماً")
        first, last = from_date, to_date
    else:
        days = stats.PERIOD_DAYS[period]
        last = now.astimezone(zone).date()
        first = last - timedelta(days=days - 1)
    start = datetime.combine(first, time.min, tzinfo=zone)
    end = datetime.combine(last + timedelta(days=1), time.min, tzinfo=zone)
    return start.astimezone(now.tzinfo or zone), end.astimezone(now.tzinfo or zone)


async def build_scope(
    session: AsyncSession,
    *,
    country: CountryCode,
    period: FinancePeriod,
    now: datetime,
    from_date: date | None = None,
    to_date: date | None = None,
    user_type: FinanceUserType | None = None,
    method: FinanceMethod | None = None,
    status: FinanceStatus | None = None,
) -> Scope:
    """**المِنطقةُ من `stats._zone`** — البيتُ الذي يحكم «اليوم» في نظرة عامة والتقارير وساعات الهدوء، **فلا تقويمان في نظامٍ واحد**."""
    zone = await stats._zone(session, country)
    from_at, to_at = window(zone, period, now, from_date, to_date)
    return Scope(
        country=country,
        currency=currency_for_country(country),
        zone=zone,
        period=period,
        from_at=from_at,
        to_at=to_at,
        now=now,
        user_type=user_type,
        method=method,
        status=status,
    )


# ═════════════════════════════════════════════════════════════ الصفوف


def _text(value: str | None):
    return literal(value, String) if value is not None else cast(null(), String)


def _row(
    *,
    source: FinanceRowSource,
    occurred_at,
    subject_id,
    role,
    kind,
    method,
    amount,
    status,
    ride_id,
    ref_id,
) -> list:
    """**أعمدةُ كلِّ صفٍّ وراء كلِّ مجموع** — واحدةٌ لكلِّ الجداول، فالتجميعُ والصفحتان والتصديرُ تقرأ شكلاً واحداً.

    `amount` **بالإشارة التي يُجمع بها المجموع**: عمولةٌ مدينةٌ في الدفتر (`-1.200`) تصير `1.200` في بطاقة «العمولة المحصَّلة»،
    **والإشارةُ قرارُ المجموع لا قرارُ الشاشة** — فلا تقلب اللوحةُ إشارةً بيدها (§14).
    """
    return [
        literal(source.value, String).label("source"),
        occurred_at.label("occurred_at"),
        cast(subject_id, _UUID).label("subject_id"),
        (literal(role, String) if isinstance(role, str) else cast(role, String)).label("subject_role"),
        (literal(kind, String) if isinstance(kind, str) else cast(kind, String)).label("kind"),
        (method if method is not None else _text(None)).label("method"),
        cast(amount, _MONEY).label("amount"),
        (status if status is not None else _text(None)).label("status"),
        (ride_id if ride_id is not None else cast(null(), _UUID)).label("ride_id"),
        cast(ref_id, _UUID).label("ref_id"),
    ]


def _in_window(column, scope: Scope) -> list:
    return [column >= scope.from_at, column < scope.to_at]


def _ledger(
    scope: Scope,
    *,
    types: tuple[WalletTransactionType, ...] | None = None,
    owner: WalletOwnerType | None = None,
    stock: bool = False,
    sign: int = 1,
    where: tuple = (),
) -> Select:
    """**قيودُ الدفتر** — صاحبُها المستخدم، وسوقُه سوقُ حسابه، **وحسابُ التجربة خارجها** (`real_user`).

    `stock`: **الدفترُ كلُّه حتى الآن** (رصيد) لا نافذةُ الفترة.
    """
    tx = WalletTransaction
    query = (
        select(
            *_row(
                source=FinanceRowSource.LEDGER,
                occurred_at=tx.created_at,
                subject_id=tx.owner_id,
                role=tx.owner_type,
                kind=tx.type,
                method=None,
                amount=tx.amount * sign,
                status=_text(FinanceStatus.CONFIRMED.value),
                ride_id=tx.ride_id,
                ref_id=tx.id,
            )
        )
        .select_from(tx)
        .join(User, User.id == tx.owner_id)
        .where(User.country_code == scope.country, test_accounts.real_user(tx.owner_id), *where)
    )
    if not stock:
        query = query.where(*_in_window(tx.created_at, scope))
    if types is not None:
        query = query.where(tx.type.in_(types))
    if owner is not None:
        query = query.where(tx.owner_type == owner)
    if scope.user_type is not None:
        query = query.where(tx.owner_type == WalletOwnerType(scope.user_type.value))
    return query


# ─────────────────────────────────────────── مستحقّاتُ الكباتن: الرصيدُ مقسوماً


async def _reserve(session: AsyncSession, country: CountryCode) -> Decimal:
    """**المحتجَزُ من إعداد السوق قراءةً** — وغيابُ الصفّ صفر، **ولا يُنشأ صفٌّ** (`get_or_create` يكتب، وهذه صفحةُ قراءة)."""
    value = await session.scalar(
        select(WalletSetting.withdrawal_reserve_amount).where(WalletSetting.country_code == country)
    )
    return money(value)


def _positions(scope: Scope, reserve: Decimal) -> Select:
    """**رصيدُ كلِّ كبتنٍ مقسوماً قسمين** — بقاعدة `withdrawals.available_balance` حرفاً، **محسوبةً في SQL لكلِّ الكباتن معاً**.

    - **يُصرف الآن** = ما طلبه ولم يُصرف بعد (`pending`/`approved`) **ومعه ما يستطيع طلبَه الآن** (المتاحُ للسحب):
      `LEAST(الرصيد, GREATEST(المطلوب, الرصيد − المحتجَز − ما يحمله لغيره))`، ولا ينزل تحت الصفر.
    - **لم يحِن بعد** = الباقي: **المحتجَزُ** (`withdrawal_reserve_amount` — ويسقط عمّن أُلغي تفعيلُه كما يسقط هناك) **وما قبضه
      نقداً لكبتنٍ آخر** (رسومُ إلغاءٍ يحملها، `cancellation.carrier_dues_of`).
    - **والمحفظةُ المجمَّدةُ لا يُصرف منها شيء** (`wallet_freezes` بمحفظة `driver`): بابُ السحب يردّها قبل أن يقرأ رصيدَها
      (`wallet.require_not_frozen`)، **فرصيدُها كلُّه «لم يحِن»** — ومعه ما طلبه قبل التجميد: التجميدُ وُضع ليوقف خروجَ المال.

    **ولا يُقرأ الحدُّ الأدنى للسحب** هنا: رصيدٌ تحته «يُصرف» حين يكتمل لا «محتجَز» — **وهذا حدٌّ مكتوبٌ لا مسكوتٌ عنه**.
    """
    tx = WalletTransaction
    balances = (
        select(tx.owner_id.label("user_id"), func.sum(tx.amount).label("balance"))
        .join(User, User.id == tx.owner_id)
        .where(
            tx.owner_type == WalletOwnerType.DRIVER,
            User.country_code == scope.country,
            test_accounts.real_user(tx.owner_id),
        )
        .group_by(tx.owner_id)
        .subquery("balances")
    )
    requested = (
        select(Driver.user_id.label("user_id"), func.sum(WithdrawalRequest.amount).label("requested"))
        .join(Driver, Driver.id == WithdrawalRequest.driver_id)
        .where(WithdrawalRequest.status.in_(PENDING_WITHDRAWAL_STATUSES))
        .group_by(Driver.user_id)
        .subquery("requested")
    )
    carried = (
        select(Driver.user_id.label("user_id"), func.sum(RideCancellationCharge.amount).label("carried"))
        .join(Driver, Driver.id == RideCancellationCharge.carrier_driver_id)
        .where(RideCancellationCharge.status == CancellationChargeStatus.PENDING)
        .group_by(Driver.user_id)
        .subquery("carried")
    )
    balance = balances.c.balance
    held_by_rule = case(
        (Driver.status == DriverStatus.DEACTIVATED, literal(Decimal("0.000"), _MONEY)),
        else_=literal(reserve, _MONEY),
    ) + func.coalesce(carried.c.carried, 0)
    frozen = select(WalletFreeze.user_id).where(WalletFreeze.owner_type == WalletOwnerType.DRIVER)
    payable = case(
        (balances.c.user_id.in_(frozen), literal(Decimal("0.000"), _MONEY)),
        else_=func.greatest(
            0,
            func.least(balance, func.greatest(func.coalesce(requested.c.requested, 0), balance - held_by_rule)),
        ),
    )
    return (
        select(
            balances.c.user_id.label("user_id"),
            balance.label("balance"),
            payable.label("payable"),
            (func.length(func.trim(func.coalesce(Driver.cliq_alias, ""))) > 0).label("cliq"),
        )
        .select_from(balances)
        .outerjoin(Driver, Driver.user_id == balances.c.user_id)
        .outerjoin(requested, requested.c.user_id == balances.c.user_id)
        .outerjoin(carried, carried.c.user_id == balances.c.user_id)
        .subquery("positions")
    )


def _position_rows(scope: Scope, reserve: Decimal, *, part: str) -> Select:
    positions = _positions(scope, reserve)
    amount = positions.c.payable if part == "payable_now" else positions.c.balance - positions.c.payable
    return (
        select(
            *_row(
                source=FinanceRowSource.POSITION,
                occurred_at=literal(scope.now),
                subject_id=positions.c.user_id,
                role=WalletOwnerType.DRIVER.value,
                kind=part,
                method=None,
                amount=amount,
                status=_text(FinanceStatus.CONFIRMED.value),
                ride_id=None,
                ref_id=positions.c.user_id,
            )
        )
        .select_from(positions)
        .where(amount != 0)
    )


def _captains_by_payout(scope: Scope, *, cliq: bool) -> Select:
    """**طريقةُ الصرف من ملفِّ الكبتن**: له حسابُ كليك (`drivers.cliq_alias`) ⇒ «كليك»، وإلا «غيرُها» (حوالةٌ بنكية)."""
    has_alias = func.length(func.trim(func.coalesce(Driver.cliq_alias, ""))) > 0
    with_alias = select(Driver.user_id).where(has_alias)
    return _ledger(
        scope,
        owner=WalletOwnerType.DRIVER,
        stock=True,
        where=(
            (WalletTransaction.owner_id.in_(with_alias) if cliq else WalletTransaction.owner_id.not_in(with_alias)),
        ),
    )


# ─────────────────────────────────────────────── ديونُ الكباتن لـTAXO


def _debts(scope: Scope, *, outstanding: bool, drivers: Select | None = None) -> Select:
    """**صفوفُ `driver_debts`** — عمولةُ رحلةٍ قبض الكبتنُ مالَها بيده. **والطريقةُ طريقةُ تلك الدفعة** (كاش · كليك)."""
    remaining = DriverDebt.amount - DriverDebt.collected
    query = (
        select(
            *_row(
                source=FinanceRowSource.DEBT,
                occurred_at=DriverDebt.created_at,
                subject_id=Driver.user_id,
                role=WalletOwnerType.DRIVER.value,
                kind=DriverDebt.source,
                method=cast(Payment.method, String),
                amount=remaining if outstanding else DriverDebt.amount,
                status=cast(DriverDebt.status, String),
                ride_id=DriverDebt.ride_id,
                ref_id=DriverDebt.id,
            )
        )
        .select_from(DriverDebt)
        .join(Driver, Driver.id == DriverDebt.driver_id)
        .outerjoin(Payment, Payment.id == DriverDebt.payment_id)
        .where(DriverDebt.country_code == scope.country, test_accounts.real_driver(DriverDebt.driver_id))
    )
    if outstanding:
        query = query.where(DriverDebt.status == DriverDebtStatus.OUTSTANDING)
    else:
        query = query.where(*_in_window(DriverDebt.created_at, scope))
    if drivers is not None:
        query = query.where(DriverDebt.driver_id.in_(drivers))
    if scope.method is not None:
        query = query.where(Payment.method == PaymentMethod(scope.method.value))
    return query


async def _ceiling(session: AsyncSession, country: CountryCode) -> Decimal | None:
    """سقفُ دَين السوق قراءةً — **و`None` لا سقف** (`debts.ceiling_for`)، فلا أحدَ «فوقه»."""
    return await session.scalar(
        select(PaymentSetting.driver_debt_ceiling).where(PaymentSetting.country_code == country)
    )


def _over_ceiling(scope: Scope, ceiling: Decimal | None) -> Select:
    """**من دَينُه القائمُ كلُّه فوق السقف** — `>` لا `>=` كما يحجب `debts.refresh_block`. **ويُقاس على الدَّين كلِّه** قبل مرشِّح
    الطريقة: «فوق السقف» حالُ كبتنٍ لا حالُ دفعة."""
    if ceiling is None:
        return select(Driver.id).where(false())
    return (
        select(DriverDebt.driver_id)
        .where(
            DriverDebt.country_code == scope.country,
            DriverDebt.status == DriverDebtStatus.OUTSTANDING,
        )
        .group_by(DriverDebt.driver_id)
        .having(func.sum(DriverDebt.amount - DriverDebt.collected) > ceiling)
    )


# ─────────────────────────────────────────────────────────────── الشحن


def _topup_channel():
    """**قناةُ الشحن من صفِّ مصدره لا من نصِّ مرجعه**: طلبُ شحنٍ يدويّ (`wallet_topup_requests.method`: كليك أو كاش) أو طلبُ
    مزوّد (`provider_orders.provider`: Telr ⇒ بطاقة، مُقتني كليك ⇒ كليك) — **كلاهما يحمل `transaction_id` القيد**.
    وما لا مصدرَ له يُقرأ «أخرى» ولا يُخمَّن — **والمطابقةُ تصيح** إن لم تجمع القنواتُ الثلاثُ مجموعَ الشحن."""
    return case(
        (WalletTopupRequest.id.is_not(None), cast(WalletTopupRequest.method, String)),
        (ProviderOrder.provider == PaymentProvider.TELR, literal("card", String)),
        (ProviderOrder.provider == PaymentProvider.CLIQ_ACQUIRER, literal("cliq", String)),
        else_=literal("other", String),
    )


def _topups(scope: Scope, channel: str | None) -> Select:
    tx = WalletTransaction
    method = _topup_channel()
    query = (
        select(
            *_row(
                source=FinanceRowSource.LEDGER,
                occurred_at=tx.created_at,
                subject_id=tx.owner_id,
                role=tx.owner_type,
                kind=tx.type,
                method=method,
                amount=tx.amount,
                status=_text(FinanceStatus.CONFIRMED.value),
                ride_id=tx.ride_id,
                ref_id=tx.id,
            )
        )
        .select_from(tx)
        .join(User, User.id == tx.owner_id)
        .outerjoin(WalletTopupRequest, WalletTopupRequest.transaction_id == tx.id)
        .outerjoin(ProviderOrder, ProviderOrder.transaction_id == tx.id)
        .where(
            tx.type == WalletTransactionType.TOPUP,
            User.country_code == scope.country,
            test_accounts.real_user(tx.owner_id),
            *_in_window(tx.created_at, scope),
        )
    )
    if channel is not None:
        query = query.where(method == channel)
    if scope.method is not None:
        query = query.where(method == scope.method.value)
    if scope.user_type is not None:
        query = query.where(tx.owner_type == WalletOwnerType(scope.user_type.value))
    return query


# ─────────────────────────────────────────────────────── الدفعاتُ والرحلات


def _payments(
    scope: Scope,
    side: FinanceUserType,
    *,
    methods: tuple[PaymentMethod, ...],
    statuses: tuple[PaymentStatus, ...],
    at=None,
) -> Select:
    """**صفوفُ `payments`** على رحلات السوق — **وصاحبُ الصفّ بحسب نوع المستخدم**: الكبتنُ الذي قبض (افتراضاً)، أو الراكبُ الذي دفع.

    والفترةُ **بلحظة فتح الدفعة** (`created_at` — عند نهاية الرحلة)، **فالحالاتُ الثلاثُ تقسم مجموعةً واحدة** لا ثلاثَ مجموعاتٍ
    بثلاثة أعمدةِ وقت.
    """
    subject = Ride.rider_id if side is FinanceUserType.RIDER else Driver.user_id
    stamp = Payment.created_at if at is None else at
    query = (
        select(
            *_row(
                source=FinanceRowSource.PAYMENT,
                occurred_at=stamp,
                subject_id=subject,
                role=side.value,
                kind="ride_payment",
                method=cast(Payment.method, String),
                amount=Payment.amount,
                status=cast(Payment.status, String),
                ride_id=Payment.ride_id,
                ref_id=Payment.id,
            )
        )
        .select_from(Payment)
        .join(Ride, Ride.id == Payment.ride_id)
        .outerjoin(Driver, Driver.id == Ride.driver_id)
        .where(
            Ride.country_code == scope.country,
            test_accounts.real_ride(),
            Payment.method.in_(methods),
            Payment.status.in_(statuses),
            *_in_window(stamp, scope),
        )
    )
    if scope.method is not None:
        query = query.where(Payment.method == PaymentMethod(scope.method.value))
    return query


#: **سطرُ رسم المطار في تفصيل الأجرة المجمَّد** (`rides.fare_lines`) — نصٌّ لأن الجدولَ يُقرأ باسمه في الاستعلام الخارجيّ
_AIRPORT_LINE = literal_column(
    "COALESCE((SELECT SUM((line->>'amount')::numeric) FROM jsonb_array_elements(rides.fare_lines) AS line "
    "WHERE line->>'kind' = 'airport_fee'), 0)",
    _MONEY,
)


def _ride_fee(scope: Scope, side: FinanceUserType, *, part: str) -> Select:
    """**رسومُ الكبتن داخل الأجرة** (§٦٣-ج/٢ و٤) — `rides.captain_fees_at_ride` مجمَّدٌ لحظةَ الطلب، **وهو مجموعُ رسمَي المطار والطرد**.

    - **المطار**: كاملُ `captain_fees_at_ride` لرحلةٍ تمسّ مرفقاً (`facility_id`) وليست طرداً؛ **ولطردٍ إلى مطار** سطرُ
      `airport_fee` من تفصيل الأجرة المجمَّد.
    - **الطرد**: `captain_fees_at_ride` لرحلة طرد **ناقصاً سطرَ المطار** إن مسّت مرفقاً.

    **والرحلاتُ المكتملة وحدَها، بلحظة اكتمالها**: الرسمُ يُحصَّل بقناة الأجرة عند النهاية، ورحلةٌ أُلغيت لم يُحصَّل رسمُها.
    """
    is_parcel = Ride.ride_type == "parcel"
    airport_of_ride = case(
        (Ride.facility_id.is_(None), literal(Decimal("0.000"), _MONEY)),
        (~is_parcel, Ride.captain_fees_at_ride),
        else_=_AIRPORT_LINE,
    )
    if part == "airport_fee":
        amount = airport_of_ride
    else:
        amount = case((is_parcel, Ride.captain_fees_at_ride - airport_of_ride), else_=literal(Decimal("0.000"), _MONEY))
    subject = Ride.rider_id if side is FinanceUserType.RIDER else Driver.user_id
    return (
        select(
            *_row(
                source=FinanceRowSource.RIDE_FEE,
                occurred_at=Ride.completed_at,
                subject_id=subject,
                role=side.value,
                kind=part,
                method=None,
                amount=amount,
                status=None,
                ride_id=Ride.id,
                ref_id=Ride.id,
            )
        )
        .select_from(Ride)
        .outerjoin(Driver, Driver.id == Ride.driver_id)
        .where(
            Ride.country_code == scope.country,
            Ride.status == RideStatus.COMPLETED,
            test_accounts.real_ride(),
            *_in_window(Ride.completed_at, scope),
            amount > 0,
        )
    )


_CHARGE_STATUS_FOR = {
    FinanceStatus.CONFIRMED: CancellationChargeStatus.SETTLED,
    FinanceStatus.UNCONFIRMED: CancellationChargeStatus.PENDING,
}


#: **رسمٌ يُطلب أو وصل** — ما يُعدّ في «الإلغاء» كما تُعدّ الرسومُ الأخرى ما وصل منها. **والمُعفى والمشطوبُ لم يُحصَّلا ولن
#: يُحصَّلا**، فجمعُهما إلى الرسوم يقرأ تنازلاً دخلاً — **ولهما سطرُهما** (`fee_cancellation_forgiven`)
_CHARGES_DUE = (CancellationChargeStatus.PENDING, CancellationChargeStatus.SETTLED)
_CHARGES_FORGIVEN = (CancellationChargeStatus.WAIVED, CancellationChargeStatus.WRITTEN_OFF)


def _cancellation_charges(
    scope: Scope, side: FinanceUserType, *, statuses: tuple[CancellationChargeStatus, ...]
) -> Select:
    """**رسومُ الإلغاء المكتوبة في الفترة** (`ride_cancellation_charges`) **بالأحوال المسمّاة** — والحالُ في التفصيل تحت البطاقة.

    **وصاحبُ الصفّ**: الراكبُ الذي ألغى (افتراضاً) أو الكبتنُ المستفيد. **و«مؤكَّد» = سُدِّد، و«غيرُ مؤكَّد» = معلَّق.**
    """
    beneficiary = Driver.user_id
    subject = RideCancellationCharge.payer_user_id if side is FinanceUserType.RIDER else beneficiary
    query = (
        select(
            *_row(
                source=FinanceRowSource.CHARGE,
                occurred_at=RideCancellationCharge.created_at,
                subject_id=subject,
                role=side.value,
                kind="cancellation_fee",
                method=None,
                amount=RideCancellationCharge.amount,
                status=cast(RideCancellationCharge.status, String),
                ride_id=RideCancellationCharge.ride_id,
                ref_id=RideCancellationCharge.id,
            )
        )
        .select_from(RideCancellationCharge)
        .join(Ride, Ride.id == RideCancellationCharge.ride_id)
        .join(Driver, Driver.id == RideCancellationCharge.beneficiary_driver_id)
        .where(
            Ride.country_code == scope.country,
            test_accounts.real_user(RideCancellationCharge.payer_user_id),
            test_accounts.real_driver(RideCancellationCharge.beneficiary_driver_id),
            RideCancellationCharge.status.in_(statuses),
            *_in_window(RideCancellationCharge.created_at, scope),
        )
    )
    if scope.status is not None:
        query = query.where(RideCancellationCharge.status == _CHARGE_STATUS_FOR[scope.status])
    return query


def _subscriptions(scope: Scope, *, discount: bool = False) -> Select:
    """**الاشتراكاتُ المباعة في الفترة** — صفٌّ لا يُكتب إلا بعد وصول ماله (`CLAUDE.md`)، **فكلُّ صفٍّ بيعٌ وقع**، ونوعُه اسمُ خطّته.

    **وسوقُه سوقُ حساب الكبتن** كما في `stats.reports`: لا عمودَ دولةٍ على الاشتراك.

    `discount`: **ما تنازل عنه TAXO في البيع نفسِه** (`discount_amount` = `list_price − amount_paid` مجمَّداً) بدل ما دُفع —
    **بالضمّ والشروط نفسِها**، فلا يفترق «من اشترى» عن «من خُصم له» إلا بالعمود المجموع.
    """
    query = (
        select(
            *_row(
                source=FinanceRowSource.SUBSCRIPTION,
                occurred_at=DriverSubscription.created_at,
                subject_id=Driver.user_id,
                role=WalletOwnerType.DRIVER.value,
                kind=SubscriptionPlan.name,
                method=cast(DriverSubscription.payment_method, String),
                amount=DriverSubscription.discount_amount if discount else DriverSubscription.amount_paid,
                status=_text(FinanceStatus.CONFIRMED.value),
                ride_id=None,
                ref_id=DriverSubscription.id,
            )
        )
        .select_from(DriverSubscription)
        .join(Driver, Driver.id == DriverSubscription.driver_id)
        .join(User, User.id == Driver.user_id)
        .join(SubscriptionPlan, SubscriptionPlan.id == DriverSubscription.plan_id)
        .where(
            User.country_code == scope.country,
            test_accounts.real_driver(DriverSubscription.driver_id),
            *_in_window(DriverSubscription.created_at, scope),
        )
    )
    if discount:
        # **بيعٌ بسعر خطّته لا خصمَ فيه** — صفٌّ بصفرٍ يُعدّ «خصماً» في العدد تحت البطاقة وهو ليس كذلك
        query = query.where(DriverSubscription.discount_amount > 0)
    if scope.method is not None:
        query = query.where(DriverSubscription.payment_method == PaymentMethod(scope.method.value))
    return query


def _commission_returned(scope: Scope) -> Select:
    """**العمولةُ التي ردّها الاستردادُ** — لكلِّ دفعةٍ صارت `refunded` (`payments.refund`): **ما ردّه TAXO للراكب ناقصاً ما
    استعاده من الكبتن** = `payments.amount + عكسُ الأجر` (`adjustment` بمفتاح `refund-earning:{payment.id}`، سالبٌ بصافي ما قُيّد
    له). **وهو العمولةُ نفسُها**: الراكبُ يستعيد المبلغَ كلَّه، والكبتنُ لا يُستعاد منه إلا صافيه — والفرقُ يخرج من TAXO **ولا قيدَ
    في الدفتر يسمّيه** — فتبقى «المحصَّلة» على قيد `commission` كاملةً بعد أن رُدّت.

    **سالبٌ بإشارته** (يُنقص العمولة)، وصاحبُه الكبتنُ الذي كانت عليه، **ولحظتُه لحظةُ الردّ** (`payments.updated_at` — الردُّ
    آخرُ حالٍ للدفعة، كبطاقة «ردودٌ إلى البطاقة»). **والرحلةُ ذاتُ كبتنٍ وحدَها**: بلا كبتنٍ لم تُقيَّد عمولةٌ أصلاً، والمعادلةُ
    هناك تقرأ المبلغَ كلَّه «عمولة».

    **وحدُّه مكتوب**: عمولةُ دفعةٍ صارت دَيناً لأن رصيدَ الكبتن لم يغطّها (`payments._distribute`) لم تدخل «المحصَّلة»، **وتُعدّ
    هنا مردودةً** — فالصافي ينزل عنها بقدرها حتى يُحصَّل الدَّين.
    """
    reversal = aliased(WalletTransaction)
    returned = Payment.amount + func.coalesce(reversal.amount, 0)
    return (
        select(
            *_row(
                source=FinanceRowSource.PAYMENT,
                occurred_at=Payment.updated_at,
                subject_id=Driver.user_id,
                role=WalletOwnerType.DRIVER.value,
                kind="commission_returned",
                method=cast(Payment.method, String),
                amount=-returned,
                status=cast(Payment.status, String),
                ride_id=Payment.ride_id,
                ref_id=Payment.id,
            )
        )
        .select_from(Payment)
        .join(Ride, Ride.id == Payment.ride_id)
        .join(Driver, Driver.id == Ride.driver_id)
        .outerjoin(
            reversal,
            and_(
                reversal.owner_id == Driver.user_id,
                reversal.owner_type == WalletOwnerType.DRIVER,
                reversal.type == WalletTransactionType.ADJUSTMENT,
                reversal.idempotency_key == literal("refund-earning:", String) + cast(Payment.id, String),
            ),
        )
        .where(
            Ride.country_code == scope.country,
            test_accounts.real_ride(),
            Payment.method.in_(REFUNDABLE_METHODS),
            Payment.status == PaymentStatus.REFUNDED,
            *_in_window(Payment.updated_at, scope),
            returned != 0,
        )
    )


def _commission_net(scope: Scope) -> CompoundSelect:
    """**صافي العمولة** — صفوفُ «المحصَّلة» (قيودُ `commission` موجبةً) **وصفوفُ «رُدّت مع الاسترداد»** (سالبةً) معاً، **فيُرسم
    الصافي رقماً من الخلفية** لا طرحاً في الشاشة (§14)، وما وراءه الصفوفُ نفسُها التي وراء البطاقتين."""
    return union_all(
        _ledger(scope, types=(WalletTransactionType.COMMISSION,), sign=-1),
        _commission_returned(scope),
    )


#: مفتاحُ قيد عكس أجر الكبتن عند استرداد دفعة (`payments.refund`) — **الكاتبُ الآليُّ الوحيدُ لـ`adjustment`**، والباقي بابُ اللوحة
_EARNING_REVERSAL_KEY = "refund-earning:%"


# ═════════════════════════════════════════════════════════════ الأسماء


#: **أنواعُ القيود بأسماء اللوحة نفسِها** (`admin-panel/src/lib/labels.ts::WALLET_TX_LABEL`) — **وتُكتب هنا لأن التصديرَ يحتاجها**:
#: ملفُّ Excel لا يقرأ خرائطَ الواجهة. **والشاشةُ والتصديرُ يقرآن هذه وحدَها في هذه الصفحة** فلا يفترقان؛ والنسخةُ في اللوحة
#: لشاشاتها الأخرى. **وعضوٌ يُضاف إلى التعداد بلا اسمٍ هنا يُرسم بمفتاحه** — ويُمسكه `test_finance_summary` الذي يشترط التغطية.
LEDGER_LABEL: dict[str, str] = {
    "topup": "شحن",
    "ride_payment": "دفع رحلة",
    "ride_earning": "أرباح رحلة",
    "commission": "عمولة",
    "transfer_in": "تحويل وارد",
    "transfer_out": "تحويل صادر",
    "withdrawal": "سحب",
    "refund": "استرداد",
    "subscription_payment": "اشتراك",
    "adjustment": "تسوية",
    "tip": "بقشيش مقبوض",
    "tip_payment": "بقشيش مدفوع",
    "cancellation_fee": "رسم إلغاء مستحقّ",
    "cancellation_compensation": "تعويض إلغاء",
    "advance": "سلفة مصروفة",
    "advance_repayment": "سداد سلفة",
    "skin_purchase": "شراء زينة مركبة",
    "referral_bonus": "حافز إحالة",
    "guarantee_hold": "رسم ضمان محفوظ",
    "guarantee_fee": "رسم ضمان للكبتن",
    "guarantee_refund": "ردّ رسم الضمان",
    "guarantee_penalty": "غرامة اعتذار عن حجز مضمون",
    "guarantee_compensation": "تعويض اعتذار الكبتن",
    "commute_prepay": "اشتراك المشوار الثابت",
    "commute_credit": "رصيدُ أيامٍ لم تُستعمل",
    "commute_incentive": "حافزُ المشوار الثابت",
    "intercity_hold": "حجزُ مقعدٍ بين المدن",
    "intercity_refund": "ردُّ حجزٍ بين المدن",
    "intercity_earning": "أجرةُ رحلةٍ بين المدن",
    "cashback": "الاسترداد الأسبوعي",
    # **زائدُ «ادفع كلَّ ما عليك» مقرَّباً، مردوداً إلى المحفظة** (SPEC §٧٠-ج/٦) — بالإشارتين في التعداد، وموجبٌ اليوم وحدَه
    "rounding": "تقريب",
}

METHOD_LABEL: dict[str, str] = {
    "cash": "كاش",
    "cliq": "كليك",
    "card": "بطاقة",
    "wallet": "محفظة",
    "promo": "خصم كوبون",
    "share": "خصم مشاركة",
    "commute": "اشتراك المشوار",
    # **شحنٌ لا مصدرَ له يُعرف** — يُقال ولا يُخمَّن (`_topup_channel`)
    "other": "أخرى",
}

_KIND_LABEL: dict[str, dict[str, str]] = {
    FinanceRowSource.LEDGER.value: LEDGER_LABEL,
    FinanceRowSource.PAYMENT.value: {"ride_payment": "دفعةُ رحلة", "commission_returned": "عمولةٌ رُدّت مع الاسترداد"},
    FinanceRowSource.DEBT.value: {"ride_commission": "عمولةُ رحلة", "intercity_commission": "عمولةُ رحلةٍ بين المدن"},
    FinanceRowSource.CHARGE.value: {"cancellation_fee": "رسمُ إلغاء"},
    FinanceRowSource.POSITION.value: {"payable_now": "يُصرف الآن", "not_due": "لم يحِن بعد"},
    FinanceRowSource.RIDE_FEE.value: {"airport_fee": "رسمُ المطار", "parcel_fee": "رسمُ الطرد"},
}

_STATUS_LABEL: dict[str, dict[str, str]] = {
    FinanceRowSource.LEDGER.value: {"confirmed": "في الدفتر"},
    FinanceRowSource.PAYMENT.value: {
        "pending": "بانتظار التأكيد",
        "confirmed": "مؤكَّدة",
        "failed": "فاشلة",
        "disputed": "متنازَعٌ عليها",
        "refunded": "مردودة",
        "voided": "بُدِّلت طريقتُها",
    },
    FinanceRowSource.DEBT.value: {"outstanding": "قائم", "settled": "سُدِّد", "written_off": "شُطب"},
    FinanceRowSource.CHARGE.value: {
        CancellationChargeStatus.PENDING.value: "لم يُحصَّل",
        CancellationChargeStatus.SETTLED.value: "وصل الكبتن",
        CancellationChargeStatus.WAIVED.value: "أُعفي",
        CancellationChargeStatus.WRITTEN_OFF.value: "شُطب",
    },
    FinanceRowSource.SUBSCRIPTION.value: {"confirmed": "مدفوع"},
    FinanceRowSource.POSITION.value: {"confirmed": "الآن"},
}

ROLE_LABEL = {FinanceUserType.RIDER.value: "راكب", FinanceUserType.DRIVER.value: "كبتن"}


def kind_label(source: str, kind: str) -> str:
    """**اسمُ النوع بجهته** — والخطّةُ اسمُها كما كُتب (`subscription`)، وما لا اسمَ له يُرسم بمفتاحه لا بفراغ."""
    return _KIND_LABEL.get(source, {}).get(kind, kind)


def method_label(method: str | None) -> str | None:
    return METHOD_LABEL.get(method, method) if method is not None else None


def status_label(source: str, status: str | None) -> str | None:
    return _STATUS_LABEL.get(source, {}).get(status, status) if status is not None else None


# ═════════════════════════════════════════════════════════════ الكتالوج


ALL_SIDES = frozenset(FinanceUserType)
RIDERS = frozenset({FinanceUserType.RIDER})
DRIVERS = frozenset({FinanceUserType.DRIVER})
LEDGER_STATUSES = frozenset({FinanceStatus.CONFIRMED})


@dataclass(frozen=True, slots=True)
class Context:
    """ما يُقرأ مرّةً لكلِّ نداءٍ ويحتاجه أكثرُ من مجموع — **إعداداتٌ تُقرأ لا تُنشأ**."""

    reserve: Decimal
    ceiling: Decimal | None


@dataclass(frozen=True, slots=True)
class Metric:
    """مجموعٌ واحد — **صفوفُه وتعريفُه وما ينطبق عليه من المرشِّحات**."""

    key: str
    group: str
    label: str
    #: **ما يجمعه بالضبط** — الجداولُ والشروطُ والإشارة؛ يُنشر للّوحة كما هو
    definition: str
    #: ما يُعدّ في السطر الصغير تحت الرقم — «كبتن» · «دفعة» · «قيد»…
    unit: str
    rows: Callable[[Scope, FinanceUserType, Context], Select | CompoundSelect]
    stock: bool = False
    sides: frozenset[FinanceUserType] = ALL_SIDES
    default_side: FinanceUserType = FinanceUserType.DRIVER
    methods: frozenset[FinanceMethod] = frozenset()
    statuses: frozenset[FinanceStatus] = frozenset()
    #: **تفصيلٌ تحت البطاقة** — عمودٌ من الصفوف يُجمع به: `kind` (الخطّة) · `status` · `sign` (إضافة/خصم)
    breakdown: str | None = None
    #: **شارةُ تحذير** — يُرسم الرقمُ بلون الخطر متى لم يكن صفراً (فوق السقف)
    warn: bool = False


@dataclass(frozen=True, slots=True)
class Group:
    key: str
    title: str
    #: `cards` بطاقاتٌ، و`table` جدولٌ مضغوط (حركةُ الدفتر بالنوع — أربعٌ وثلاثون بطاقةً لا تُقرأ)
    layout: str = "cards"


GROUPS: tuple[Group, ...] = (
    Group("captains_owed", "مستحقّاتُ الكباتن"),
    Group("captains_owing", "ديونُ الكباتن لـTAXO"),
    Group("riders", "أرصدةُ الركّاب"),
    Group("topups", "الشحن"),
    Group("ride_payments", "رحلاتُ الكاش وكليك"),
    Group("subscriptions", "الاشتراكات"),
    Group("commission", "العمولة"),
    Group("fees", "الرسوم"),
    Group("discounts", "الخصوماتُ والاسترداد"),
    Group("refunds", "الردودُ والتصحيحات"),
    Group("ledger", "حركةُ الدفتر في الفترة", layout="table"),
)

_DIRECT = (PaymentMethod.CASH, PaymentMethod.CLIQ)
_DIRECT_METHODS = frozenset({FinanceMethod.CASH, FinanceMethod.CLIQ})


def _side(fn: Callable[[Scope, FinanceUserType], Select]) -> Callable[[Scope, FinanceUserType, Context], Select]:
    return lambda scope, side, _ctx: fn(scope, side)


def _plain(
    fn: Callable[[Scope], Select | CompoundSelect],
) -> Callable[[Scope, FinanceUserType, Context], Select | CompoundSelect]:
    return lambda scope, _side, _ctx: fn(scope)


_CATALOG: list[Metric] = [
    # ── مستحقّاتُ الكباتن — رصيدٌ الآن
    Metric(
        "captain_balances", "captains_owed", "المجموع",
        "مجموعُ أرصدة محافظ الكباتن الآن: كلُّ قيود `wallet_transactions` بمحفظة `driver` (موجبُها وسالبُها) لحسابات السوق، "
        "بلا حسابات التجربة — مالٌ يدين به TAXO لأصحابه.",
        "كبتن", _plain(lambda s: _ledger(s, owner=WalletOwnerType.DRIVER, stock=True)),
        stock=True, sides=DRIVERS, statuses=LEDGER_STATUSES,
    ),
    Metric(
        "captain_balances_cliq", "captains_owed", "صرفٌ بكليك",
        "أرصدةُ الكباتن الذين في ملفّهم حسابُ كليك (`drivers.cliq_alias`) — قيودُ محافظهم كلُّها.",
        "كبتن", _plain(lambda s: _captains_by_payout(s, cliq=True)),
        stock=True, sides=DRIVERS, statuses=LEDGER_STATUSES,
    ),
    Metric(
        "captain_balances_other", "captains_owed", "صرفٌ بغير كليك",
        "أرصدةُ الكباتن بلا حسابِ كليك في ملفّهم — يُصرف لهم بحوالةٍ بنكية.",
        "كبتن", _plain(lambda s: _captains_by_payout(s, cliq=False)),
        stock=True, sides=DRIVERS, statuses=LEDGER_STATUSES,
    ),
    Metric(
        "captain_payable_now", "captains_owed", "يُصرف الآن",
        "لكلِّ كبتن: ما طلب سحبَه ولم يُصرف (`withdrawal_requests` معلَّقاً أو معتمَداً) ومعه ما يستطيع طلبَه الآن — "
        "الرصيدُ ناقصاً المحتجَز (`withdrawal_reserve_amount`) وما يحمله نقداً لكبتنٍ آخر، بقاعدة «المتاح للسحب» نفسِها. "
        "والمحفظةُ المجمَّدة (`wallet_freezes`) لا يُصرف منها شيء. والحدُّ الأدنى للسحب لا يُقرأ هنا.",
        "كبتن", lambda s, _side, ctx: _position_rows(s, ctx.reserve, part="payable_now"),
        stock=True, sides=DRIVERS, statuses=LEDGER_STATUSES,
    ),
    Metric(
        "captain_not_due", "captains_owed", "لم يحِن بعد",
        "باقي الرصيد: المحتجَزُ بإعداد السوق (ويسقط عمّن أُلغي تفعيلُه) ورسومُ إلغاءٍ قبضها نقداً لكبتنٍ آخر ولم يحوّلها، "
        "ورصيدُ المحفظة المجمَّدة كلُّه.",
        "كبتن", lambda s, _side, ctx: _position_rows(s, ctx.reserve, part="not_due"),
        stock=True, sides=DRIVERS, statuses=LEDGER_STATUSES,
    ),
    # ── ديونُ الكباتن — قائمٌ الآن
    Metric(
        "captain_debts", "captains_owing", "المجموع",
        "ما بقي من ديون العمولة القائمة الآن: `driver_debts.amount − collected` بحال `outstanding` في السوق — "
        "عمولةُ رحلاتٍ قبض الكبتنُ مالَها بيده (كاش أو كليك).",
        "كبتن", _plain(lambda s: _debts(s, outstanding=True)),
        stock=True, sides=DRIVERS, methods=_DIRECT_METHODS,
    ),
    Metric(
        "captain_debts_over_ceiling", "captains_owing", "فوق السقف",
        "ديونُ الكباتن الذين قائمُهم كلُّه أكبرُ من سقف السوق (`payment_settings.driver_debt_ceiling`، و`>` كالحجب نفسِه). "
        "وسوقٌ بلا سقفٍ لا أحدَ فيه فوقه.",
        "كبتن", lambda s, _side, ctx: _debts(s, outstanding=True, drivers=_over_ceiling(s, ctx.ceiling)),
        stock=True, sides=DRIVERS, methods=_DIRECT_METHODS, warn=True,
    ),
    # ── أرصدةُ الركّاب
    Metric(
        "rider_balances", "riders", "المجموع",
        "مجموعُ أرصدة محافظ الركّاب الآن: كلُّ قيود `wallet_transactions` بمحفظة `rider` لحسابات السوق، بلا حسابات التجربة.",
        "محفظة", _plain(lambda s: _ledger(s, owner=WalletOwnerType.RIDER, stock=True)),
        stock=True, sides=RIDERS, statuses=LEDGER_STATUSES,
    ),
    # ── الشحن
    Metric(
        "topups", "topups", "المجموع",
        "قيودُ `topup` في الفترة — للراكب والكبتن — بقناتها من صفِّ مصدرها (طلبُ شحنٍ يدويّ أو طلبُ مزوّد).",
        "شحنة", _plain(lambda s: _topups(s, None)),
        methods=frozenset({FinanceMethod.CLIQ, FinanceMethod.CARD, FinanceMethod.CASH}), statuses=LEDGER_STATUSES,
        default_side=FinanceUserType.RIDER,
    ),
    Metric(
        "topups_cliq", "topups", "كليك",
        "قيودُ `topup` من طلب شحنٍ يدويّ بكليك (`wallet_topup_requests.method = cliq`) أو من مُقتني كليك (`provider_orders`).",
        "شحنة", _plain(lambda s: _topups(s, "cliq")),
        methods=frozenset({FinanceMethod.CLIQ}), statuses=LEDGER_STATUSES,
    ),
    Metric(
        "topups_card", "topups", "بطاقة",
        "قيودُ `topup` من طلب بطاقةٍ عند Telr (`provider_orders.provider = telr`).",
        "شحنة", _plain(lambda s: _topups(s, "card")),
        methods=frozenset({FinanceMethod.CARD}), statuses=LEDGER_STATUSES,
    ),
    Metric(
        "topups_cash", "topups", "نقطةُ كاش",
        "قيودُ `topup` من شحنٍ نقديٍّ سجّله مشرف (`wallet_topup_requests.method = cash`).",
        "شحنة", _plain(lambda s: _topups(s, "cash")),
        methods=frozenset({FinanceMethod.CASH}), statuses=LEDGER_STATUSES,
    ),
    # ── رحلاتُ الكاش وكليك
    Metric(
        "ride_payments_confirmed", "ride_payments", "مؤكَّدة",
        "دفعاتُ `payments` بطريقة كاش أو كليك وحال `confirmed`، فُتحت في الفترة على رحلات السوق.",
        "دفعة",
        _side(lambda s, side: _payments(s, side, methods=_DIRECT, statuses=(PaymentStatus.CONFIRMED,))),
        methods=_DIRECT_METHODS, statuses=frozenset({FinanceStatus.CONFIRMED}),
    ),
    Metric(
        "ride_payments_unconfirmed", "ride_payments", "غيرُ مؤكَّدة",
        "دفعاتُ كاش أو كليك بحال `pending` — فُتحت في الفترة ولم يؤكّدها أحدٌ بعد.",
        "دفعة",
        _side(lambda s, side: _payments(s, side, methods=_DIRECT, statuses=(PaymentStatus.PENDING,))),
        methods=_DIRECT_METHODS, statuses=frozenset({FinanceStatus.UNCONFIRMED}),
    ),
    Metric(
        "ride_payments_disputed", "ride_payments", "متنازَعٌ عليها",
        "دفعاتُ كاش أو كليك بحال `disputed` — فُتحت في الفترة وتنتظر فصلاً.",
        "دفعة",
        _side(lambda s, side: _payments(s, side, methods=_DIRECT, statuses=(PaymentStatus.DISPUTED,))),
        methods=_DIRECT_METHODS, statuses=frozenset({FinanceStatus.DISPUTED}),
    ),
    # ── الاشتراكات
    Metric(
        "subscriptions_sold", "subscriptions", "المباعة",
        "صفوفُ `driver_subscriptions` المكتوبة في الفترة بـ`amount_paid` — الصفُّ لا يُكتب إلا بعد وصول ماله، بكلِّ قنواته — "
        "وتفصيلُها بالخطّة.",
        "اشتراك", _plain(_subscriptions),
        sides=DRIVERS,
        methods=frozenset(FinanceMethod), statuses=LEDGER_STATUSES, breakdown="kind",
    ),
    # ── العمولة
    Metric(
        "commission_collected", "commission", "المحصَّلة",
        "قيودُ `commission` في الفترة (مدينةٌ على محفظة الكبتن، وتُعرض موجبة): عمولةُ رحلات المحفظة والبطاقة، "
        "وما حُصِّل من رصيده لدَينٍ قديم. ولا يدخلها ما سدّده الكبتنُ بكليك خارج المحفظة — لا عمودَ يحمل مبلغَه الواصل.",
        "قيد", _plain(lambda s: _ledger(s, types=(WalletTransactionType.COMMISSION,), sign=-1)),
        sides=DRIVERS, statuses=LEDGER_STATUSES,
    ),
    Metric(
        "commission_refunded", "commission", "رُدّت مع الاسترداد",
        "لكلِّ دفعةٍ صارت `refunded` في الفترة (بوقت آخر تعديلٍ لصفّها): `payments.amount` الذي عاد للراكب ناقصاً عكسَ أجر الكبتن "
        "(`adjustment` بمفتاح `refund-earning:`) — العمولةُ التي ردّها TAXO ولا قيدَ يسمّيها. سالبة.",
        "دفعة", _plain(_commission_returned),
        sides=DRIVERS,
    ),
    Metric(
        "commission_net", "commission", "الصافي",
        "صفوفُ «المحصَّلة» و«رُدّت مع الاسترداد» معاً — ما بقي لـTAXO من عمولة الفترة بعد ردودها.",
        "صفّ", _plain(_commission_net),
        sides=DRIVERS, breakdown="kind",
    ),
    Metric(
        "commission_accrued_direct", "commission", "المستحقّة على الكاش وكليك",
        "صفوفُ `driver_debts` المكتوبة في الفترة بمبلغها كاملاً — عمولةُ رحلاتٍ قبض الكبتنُ أجرتَها بيده، "
        "حُصِّلت بعدها أم بقيت.",
        "رحلة", _plain(lambda s: _debts(s, outstanding=False)),
        sides=DRIVERS, methods=_DIRECT_METHODS,
    ),
    # ── الرسوم
    Metric(
        "fee_airport", "fees", "المطار",
        "رسمُ المطار داخل أجور الرحلات المكتملة في الفترة: `rides.captain_fees_at_ride` لرحلةٍ تمسّ مرفقاً وليست طرداً، "
        "وسطرُ `airport_fee` من تفصيل الأجرة لطردٍ إلى مطار. يصل الكبتنَ كاملاً.",
        "رحلة", _side(lambda s, side: _ride_fee(s, side, part="airport_fee")),
    ),
    Metric(
        "fee_guarantee", "fees", "الضمان",
        "قيودُ `guarantee_fee` في الفترة — رسمُ الحجز المضمون حين وصل الكبتنَ بعد رحلته (المحفوظُ المردودُ لا يدخلها).",
        "حجز", _plain(lambda s: _ledger(s, types=(WalletTransactionType.GUARANTEE_FEE,))),
        sides=DRIVERS, statuses=LEDGER_STATUSES,
    ),
    Metric(
        "fee_parcel", "fees", "الطرد",
        "رسمُ الطرد داخل أجور رحلات الطرد المكتملة في الفترة: `rides.captain_fees_at_ride` ناقصاً سطرَ المطار إن مسّت مرفقاً.",
        "طرد", _side(lambda s, side: _ride_fee(s, side, part="parcel_fee")),
    ),
    Metric(
        "fee_cancellation", "fees", "الإلغاء",
        "رسومُ `ride_cancellation_charges` المكتوبة في الفترة بحال `settled` أو `pending` — ما وصل الكبتنَ وما يُطلب بعد؛ "
        "والتفصيلُ بالحال. والمُعفى والمشطوبُ في سطرهما لا هنا: لم يُحصَّلا ولن يُحصَّلا.",
        "رسم", _side(lambda s, side: _cancellation_charges(s, side, statuses=_CHARGES_DUE)),
        default_side=FinanceUserType.RIDER,
        statuses=frozenset({FinanceStatus.CONFIRMED, FinanceStatus.UNCONFIRMED}), breakdown="status",
    ),
    Metric(
        "fee_cancellation_forgiven", "fees", "الإلغاء — أُعفي أو شُطب",
        "رسومُ `ride_cancellation_charges` المكتوبة في الفترة بحال `waived` (أعفته الإدارة) أو `written_off` (شُطب بقرار) — "
        "رسومٌ استُحقّت ولم يُحصَّل منها شيء، ولا قيدَ لها في الدفتر. والتفصيلُ بالحال.",
        "رسم", _side(lambda s, side: _cancellation_charges(s, side, statuses=_CHARGES_FORGIVEN)),
        default_side=FinanceUserType.RIDER, breakdown="status",
    ),
    # ── الخصوماتُ والاسترداد
    Metric(
        "coupons", "discounts", "الكوبونات",
        "دفعاتُ `payments` بقناة `promo` وحال `confirmed` في الفترة — خصمٌ يتحمّله TAXO عن الراكب.",
        "رحلة",
        _side(lambda s, side: _payments(s, side, methods=(PaymentMethod.PROMO,), statuses=(PaymentStatus.CONFIRMED,))),
        default_side=FinanceUserType.RIDER,
    ),
    Metric(
        "share_discounts", "discounts", "خصمُ المشاركة",
        "دفعاتُ `payments` بقناة `share` وحال `confirmed` في الفترة — خصمُ الرحلة المشتركة يتحمّله TAXO.",
        "رحلة",
        _side(lambda s, side: _payments(s, side, methods=(PaymentMethod.SHARE,), statuses=(PaymentStatus.CONFIRMED,))),
        default_side=FinanceUserType.RIDER,
    ),
    Metric(
        "subscription_discounts", "discounts", "خصمُ الاشتراكات",
        "`driver_subscriptions.discount_amount` للاشتراكات المكتوبة في الفترة (`list_price − amount_paid` مجمَّداً لحظةَ البيع): "
        "خصمُ عرض اشتراك، أو مبلغٌ أقلُّ من سعر الخطّة حصّله مشرفٌ نقداً أو بكليك — يتحمّله TAXO. والبيعُ بسعره لا يُعدّ.",
        "اشتراك", _plain(lambda s: _subscriptions(s, discount=True)),
        sides=DRIVERS,
        methods=frozenset(FinanceMethod), statuses=LEDGER_STATUSES,
    ),
    Metric(
        "cashback", "discounts", "الاستردادُ الأسبوعيّ",
        "قيودُ `cashback` في الفترة — دائنٌ للراكب من TAXO.",
        "قيد", _plain(lambda s: _ledger(s, types=(WalletTransactionType.CASHBACK,))),
        sides=RIDERS, default_side=FinanceUserType.RIDER, statuses=LEDGER_STATUSES,
    ),
    Metric(
        "referral_bonuses", "discounts", "مكافآتُ الإحالة",
        "قيودُ `referral_bonus` في الفترة — للراكب والكبتن، يتحمّلها TAXO.",
        "قيد", _plain(lambda s: _ledger(s, types=(WalletTransactionType.REFERRAL_BONUS,))),
        statuses=LEDGER_STATUSES,
    ),
    # ── الردودُ والتصحيحات
    Metric(
        "refunds_riders", "refunds", "ردودٌ للركّاب",
        "قيودُ `refund` في محافظ الركّاب في الفترة — ردُّ دفعةٍ دُفعت من المحفظة.",
        "قيد", _plain(lambda s: _ledger(s, types=(WalletTransactionType.REFUND,), owner=WalletOwnerType.RIDER)),
        sides=RIDERS, default_side=FinanceUserType.RIDER, statuses=LEDGER_STATUSES,
    ),
    Metric(
        "refunds_card", "refunds", "ردودٌ إلى البطاقة",
        "دفعاتُ بطاقةٍ صارت `refunded` في الفترة (بوقت آخر تعديلٍ للصفّ — الردُّ آخرُ حالٍ لها) — رُدّت عند المزوّد، فلا قيدَ لها "
        "في محفظة الراكب.",
        "دفعة",
        _side(
            lambda s, side: _payments(
                s, side, methods=(PaymentMethod.CARD,), statuses=(PaymentStatus.REFUNDED,), at=Payment.updated_at
            )
        ),
        default_side=FinanceUserType.RIDER, methods=frozenset({FinanceMethod.CARD}),
    ),
    Metric(
        "refunds_captains", "refunds", "ردودٌ للكباتن",
        "قيودُ `refund` في محافظ الكباتن في الفترة — ردُّ ما بقي من اشتراكٍ أُلغي.",
        "قيد", _plain(lambda s: _ledger(s, types=(WalletTransactionType.REFUND,), owner=WalletOwnerType.DRIVER)),
        sides=DRIVERS, statuses=LEDGER_STATUSES,
    ),
    Metric(
        "adjustments", "refunds", "تصحيحاتُ المشرفين",
        "قيودُ `adjustment` في الفترة بإشارتها — إلا عكسَ أجر الكبتن عند الاسترداد (البطاقةُ التالية). "
        "وكاتبُها اليومَ بابُ التصحيح في اللوحة وحدَه. والتفصيلُ: إضافةٌ وخصم.",
        "قيد",
        _plain(
            lambda s: _ledger(
                s,
                types=(WalletTransactionType.ADJUSTMENT,),
                where=(
                    or_(
                        WalletTransaction.idempotency_key.is_(None),
                        ~WalletTransaction.idempotency_key.like(_EARNING_REVERSAL_KEY),
                    ),
                ),
            )
        ),
        statuses=LEDGER_STATUSES, breakdown="sign",
    ),
    Metric(
        "earning_reversals", "refunds", "عكسُ أجر الكبتن عند الاسترداد",
        "قيودُ `adjustment` السالبة التي يكتبها ردُّ دفعةٍ على محفظة الكبتن (صافي ما قُيّد له) — بإشارتها.",
        "قيد",
        _plain(
            lambda s: _ledger(
                s,
                types=(WalletTransactionType.ADJUSTMENT,),
                where=(WalletTransaction.idempotency_key.like(_EARNING_REVERSAL_KEY),),
            )
        ),
        sides=DRIVERS, statuses=LEDGER_STATUSES,
    ),
]

# ── حركةُ الدفتر بالنوع — كلُّ نوعٍ في التعداد، فنوعٌ يُضاف غداً يظهر هنا وفي المطابقة بلا سطر
for _type in WalletTransactionType:
    _CATALOG.append(
        Metric(
            f"ledger.{_type.value}", "ledger", LEDGER_LABEL.get(_type.value, _type.value),
            f"قيودُ `{_type.value}` في الفترة بإشارتها كما في الدفتر — للراكب والكبتن.",
            "قيد",
            (lambda t: _plain(lambda s: _ledger(s, types=(t,))))(_type),
            statuses=LEDGER_STATUSES,
        )
    )

METRICS: dict[str, Metric] = {metric.key: metric for metric in _CATALOG}


def metric_of(key: str) -> Metric:
    metric = METRICS.get(key)
    if metric is None:
        raise NotFound("مجموعٌ غير معروف")
    return metric


def not_applicable(metric: Metric, scope: Scope) -> str | None:
    """**علّةُ ألّا ينطبق مرشِّحٌ** على مجموع — أو `None`. **والنصُّ يُرسم كما هو**: «لا ينطبق» بلا علّةٍ يُقرأ عطباً."""
    if scope.user_type is not None and scope.user_type not in metric.sides:
        return "هذا المجموعُ لا يخصّ هذا النوعَ من المستخدمين"
    if scope.method is not None and scope.method not in metric.methods:
        return "لا طريقةَ دفعٍ لهذا المجموع بهذا الاسم"
    if scope.status is not None and scope.status not in metric.statuses:
        return "لا حالَ لهذا المجموع بهذا الاسم"
    return None


async def _context(session: AsyncSession, scope: Scope) -> Context:
    return Context(reserve=await _reserve(session, scope.country), ceiling=await _ceiling(session, scope.country))


def rows_of(metric: Metric, scope: Scope, context: Context) -> Select | CompoundSelect:
    """**الصفوفُ وراء المجموع** — الاستعلامُ الواحدُ الذي تقرؤه البطاقةُ والصفحتان والتصدير."""
    side = scope.user_type or metric.default_side
    return metric.rows(scope, side, context)


# ═════════════════════════════════════════════════════════════ التجميع


@dataclass(frozen=True, slots=True)
class BreakdownLine:
    key: str
    label: str
    amount: Decimal
    count: int


@dataclass(frozen=True, slots=True)
class MetricValue:
    metric: Metric
    applicable: bool
    reason: str | None
    amount: Decimal
    count: int
    users: int
    breakdown: list[BreakdownLine] = field(default_factory=list)


#: **تفصيلُ «إضافة/خصم»** — التصحيحُ يتّجه بالاتجاهين، ومجموعُه الصافي وحدَه يخفي مئةً أُضيفت ومئةً خُصمت
_SIGN_LABEL = {"credit": "إضافة", "debit": "خصم"}


async def _aggregate(session: AsyncSession, metric: Metric, scope: Scope, context: Context) -> MetricValue:
    """**المجموعُ والعددُ والمستخدمون من الصفوف نفسِها** — والمستخدمُ يُعدّ إن لم يكن مجموعُه صفراً (محفظةٌ فارغةٌ ليست «محفظةً عليها مال»).

    **و«المستخدمُ» حسابٌ بدوره** (`subject_id` و`subject_role` معاً) كما في `users_page`: من يحمل الدورين له محفظتان، ومالُ
    محفظة الراكب لا يُعدّ في سطر «كبتن» — فلا يفترق العددُ تحت البطاقة عن صفوف «المستخدمون».
    """
    reason = not_applicable(metric, scope)
    if reason is not None:
        return MetricValue(metric, False, reason, money(0), 0, 0)
    rows = rows_of(metric, scope, context).subquery("rows")
    per_user = (
        select(func.sum(rows.c.amount).label("total"), func.count().label("n"))
        .group_by(rows.c.subject_id, rows.c.subject_role)
        .subquery("per_user")
    )
    total, count, users = (
        await session.execute(
            select(
                func.coalesce(func.sum(per_user.c.total), 0),
                func.coalesce(func.sum(per_user.c.n), 0),
                func.count().filter(per_user.c.total != 0),
            )
        )
    ).one()
    lines: list[BreakdownLine] = []
    if metric.breakdown is not None:
        if metric.breakdown == "sign":
            key = case((rows.c.amount > 0, literal("credit", String)), else_=literal("debit", String))
        else:
            key = getattr(rows.c, metric.breakdown)
        found = await session.execute(
            select(key.label("key"), func.min(rows.c.source), func.sum(rows.c.amount), func.count())
            .group_by(key)
            .order_by(func.sum(rows.c.amount).desc(), key)
        )
        for value, source, amount, number in found.all():
            if metric.breakdown == "sign":
                label = _SIGN_LABEL[value]
            elif metric.breakdown == "status":
                label = status_label(source, value) or str(value)
            else:
                label = kind_label(source, value)
            lines.append(BreakdownLine(str(value), label, money(amount), int(number)))
    return MetricValue(metric, True, None, money(total), int(count), int(users or 0), lines)


@dataclass(frozen=True, slots=True)
class Difference:
    key: str
    label: str
    page_amount: Decimal
    ledger_amount: Decimal

    @property
    def difference_amount(self) -> Decimal:
        return money(self.page_amount - self.ledger_amount)


@dataclass(frozen=True, slots=True)
class Reconciliation:
    reconciled: bool
    checked_at: datetime
    checks: int
    differences: list[Difference]


@dataclass(frozen=True, slots=True)
class Summary:
    scope: Scope
    values: list[MetricValue]
    reconciliation: Reconciliation


async def summary(session: AsyncSession, scope: Scope) -> Summary:
    """**الصفحةُ كلُّها** — كلُّ مجموعٍ في الكتالوج بمرشِّحات النداء، **ومعها المطابقةُ على السوق والفترة وحدَهما**."""
    context = await _context(session, scope)
    values = [await _aggregate(session, metric, scope, context) for metric in METRICS.values()]
    if scope.filtered:
        plain = scope.unfiltered()
        page = {metric.key: (await _aggregate(session, metric, plain, context)).amount for metric in METRICS.values()}
    else:
        page = {value.metric.key: value.amount for value in values}
    return Summary(scope=scope, values=values, reconciliation=await reconcile(session, scope, page))


# ═════════════════════════════════════════════════════════════ ما وراء البطاقة


@dataclass(frozen=True, slots=True)
class UserRow:
    user_id: uuid.UUID | None
    driver_id: uuid.UUID | None
    name: str | None
    phone_masked: str | None
    role: str
    role_label: str
    count: int
    amount: Decimal


@dataclass(frozen=True, slots=True)
class TransactionRow:
    ref_id: uuid.UUID
    occurred_at: datetime
    user_id: uuid.UUID | None
    driver_id: uuid.UUID | None
    name: str | None
    role: str
    role_label: str
    source: str
    kind: str
    kind_label: str
    method: str | None
    method_label: str | None
    status: str | None
    status_label: str | None
    amount: Decimal
    ride_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class Page:
    value: MetricValue
    #: عددُ ما وراء المجموع كلِّه — لا ما في الصفحة؛ **منه تُرقَّم الصفحات** ويُقال إن التصديرَ اقتُطع
    total: int
    rows: list


async def users_page(
    session: AsyncSession, metric: Metric, scope: Scope, *, limit: int, offset: int
) -> Page:
    """**من يصنع الرقم** — مستخدمو المجموع **مرتَّبين من الأكبر**، كلٌّ بمجموعه وعدد صفوفه، من الصفوف نفسِها.

    **ومن مجموعُه صفرٌ لا يُعدّ** (محفظةٌ فارغة، إضافةٌ قابلها خصم) — كعدّ المستخدمين تحت البطاقة، فلا يفترق العددان.

    **والصفُّ حسابٌ بدوره** (`subject_id`, `subject_role`): من يحمل الدورين سطران — راكبٌ وكبتن — **لا سطرٌ واحدٌ يُسمّى «كبتن»**
    ويحمل مالَ محفظة الراكب ويفتح ملفَّ الكبتن. **و«الأكبرُ» بالقيمة المطلقة** كالمعاملات: عكسُ أجرٍ بمئةٍ أثقلُ من إضافة خمسة،
    والترتيبُ بالإشارة كان يضع أصغرَ السوالب أوّلاً في كلِّ مجموعٍ سالب.
    """
    context = await _context(session, scope)
    value = await _aggregate(session, metric, scope, context)
    if not value.applicable:
        return Page(value, 0, [])
    rows = rows_of(metric, scope, context).subquery("rows")
    total_amount = func.sum(rows.c.amount)
    grouped = (
        select(
            rows.c.subject_id.label("user_id"),
            rows.c.subject_role.label("role"),
            func.count().label("n"),
            total_amount.label("total"),
        )
        .group_by(rows.c.subject_id, rows.c.subject_role)
        .having(total_amount != 0)
        .subquery("grouped")
    )
    total = int(await session.scalar(select(func.count()).select_from(grouped)) or 0)
    found = await session.execute(
        select(
            grouped.c.user_id,
            grouped.c.role,
            grouped.c.n,
            grouped.c.total,
            User.name,
            User.phone,
            Driver.id.label("driver_id"),
        )
        .select_from(grouped)
        .outerjoin(User, User.id == grouped.c.user_id)
        # **صفُّ الكبتن وحدَه يحمل ملفَّ الكبتن** — وسطرُ الراكب لحاملِ الدورين يفتح ملفَّ الراكب
        .outerjoin(
            Driver,
            and_(Driver.user_id == grouped.c.user_id, grouped.c.role == WalletOwnerType.DRIVER.value),
        )
        .order_by(func.abs(grouped.c.total).desc(), grouped.c.user_id, grouped.c.role)
        .limit(limit)
        .offset(offset)
    )
    out = [
        UserRow(
            user_id=row.user_id,
            driver_id=row.driver_id,
            name=row.name,
            phone_masked=mask_phone(row.phone) if row.phone else None,
            role=row.role,
            role_label=ROLE_LABEL.get(row.role, row.role),
            count=int(row.n),
            amount=money(row.total),
        )
        for row in found.all()
    ]
    return Page(value, total, out)


async def transactions_page(
    session: AsyncSession, metric: Metric, scope: Scope, *, limit: int, offset: int
) -> Page:
    """**المعاملاتُ وراء المجموع** — الأكبرُ قيمةً أوّلاً (بالقيمة المطلقة: خصمُ مئةٍ أثقلُ من إضافة خمسة)، ثمّ الأحدث."""
    context = await _context(session, scope)
    value = await _aggregate(session, metric, scope, context)
    if not value.applicable:
        return Page(value, 0, [])
    rows = rows_of(metric, scope, context).subquery("rows")
    total = int(await session.scalar(select(func.count()).select_from(rows)) or 0)
    found = await session.execute(
        select(
            rows.c.source,
            rows.c.occurred_at,
            rows.c.subject_id,
            rows.c.subject_role,
            rows.c.kind,
            rows.c.method,
            rows.c.amount,
            rows.c.status,
            rows.c.ride_id,
            rows.c.ref_id,
            User.name,
            Driver.id.label("driver_id"),
        )
        .select_from(rows)
        .outerjoin(User, User.id == rows.c.subject_id)
        .outerjoin(Driver, Driver.user_id == rows.c.subject_id)
        .order_by(func.abs(rows.c.amount).desc(), rows.c.occurred_at.desc(), rows.c.ref_id)
        .limit(limit)
        .offset(offset)
    )
    out = [
        TransactionRow(
            ref_id=row.ref_id,
            occurred_at=row.occurred_at,
            user_id=row.subject_id,
            driver_id=row.driver_id,
            name=row.name,
            role=row.subject_role,
            role_label=ROLE_LABEL.get(row.subject_role, row.subject_role),
            source=row.source,
            kind=row.kind,
            kind_label=kind_label(row.source, row.kind),
            method=row.method,
            method_label=method_label(row.method),
            status=row.status,
            status_label=status_label(row.source, row.status),
            amount=money(row.amount),
            ride_id=row.ride_id,
        )
        for row in found.all()
    ]
    return Page(value, total, out)


# ═════════════════════════════════════════════════════════════ المطابقة


@dataclass(frozen=True, slots=True)
class Check:
    """**سطرُ مطابقة**: رقمُ الصفحة ورقمُ الدفتر الخام لشيءٍ واحد."""

    key: str
    label: str
    page_amount: Decimal
    ledger_amount: Decimal


def compare(checks: list[Check], *, checked_at: datetime) -> Reconciliation:
    """**المقارنةُ وحدَها — دالّةٌ محضة**، فيُغذّيها اختبارٌ بقيمةٍ مزوّرةٍ ويرى التحذير بلا قاعدة.

    **والتساوي بالخانات الثلاث** (`money`): `Decimal("1.2")` و`Decimal("1.200")` واحد، **ولا تقريبَ يمرّ بـfloat**.
    """
    differences = [
        Difference(check.key, check.label, money(check.page_amount), money(check.ledger_amount))
        for check in checks
        if money(check.page_amount) != money(check.ledger_amount)
    ]
    return Reconciliation(
        reconciled=not differences, checked_at=checked_at, checks=len(checks), differences=differences
    )


async def _raw_ledger(session: AsyncSession, scope: Scope) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """**الدفترُ خاماً** — SQL مكتوبٌ بيده **لا يمرّ بالصفوف ولا بشروطها المستعارة**، فخطأٌ في بانٍ هناك لا يتكرّر هنا فيستتر.

    يعيد: أرصدةَ المحافظ الآن بنوع المحفظة، ومجاميعَ الفترة بنوع القيد — **لحسابات السوق الحقيقية وحدها**.
    """
    params = {"country": scope.country.value, "from_at": scope.from_at, "to_at": scope.to_at}
    wallets = await session.execute(
        text(
            "SELECT wt.owner_type::text, COALESCE(SUM(wt.amount), 0) FROM wallet_transactions wt "
            "JOIN users u ON u.id = wt.owner_id "
            "WHERE u.country_code::text = :country AND u.is_test IS NOT TRUE GROUP BY wt.owner_type"
        ),
        params,
    )
    period = await session.execute(
        text(
            "SELECT wt.type::text, COALESCE(SUM(wt.amount), 0) FROM wallet_transactions wt "
            "JOIN users u ON u.id = wt.owner_id "
            "WHERE u.country_code::text = :country AND u.is_test IS NOT TRUE "
            "AND wt.created_at >= :from_at AND wt.created_at < :to_at GROUP BY wt.type"
        ),
        params,
    )
    return (
        {kind: money(total) for kind, total in wallets.all()},
        {kind: money(total) for kind, total in period.all()},
    )


#: **أرصدةُ الكباتن مقسومةً — بـSQL خامٍ مكتوبٍ ثانيةً** من الأصول نفسِها (الدفتر، وطلباتُ السحب القائمة، والمحتجَزُ من إعداد
#: السوق، ورسومُ الإلغاء المحمولة، والتجميد، و`cliq_alias`) **لا من `_positions` ولا `_captains_by_payout`**.
#:
#: **ولمَ لا «القسمان يجمعان إلى الأصل»**: «لم يحِن» يُحسب في الصفحة **رصيداً ناقصاً «يُصرف الآن»**، وقسمةُ الكليك نصفا استعلامٍ
#: واحد — **فالجمعُ يساوي الأصلَ دائماً** مهما أخطأت القسمة، وفحصٌ لا يسقط أبداً يُعدّ في `checks` ولا يحرس شيئاً. **وهنا يُقارَن
#: كلُّ قسمٍ بقرينه الخام**، فبانٍ نسي التجميدَ أو قرأ طلباتٍ مدفوعةً «قائمةً» يصيح.
#:
#: **وحدُّه مكتوب**: القاعدةُ نفسُها (`LEAST(…, GREATEST(…))`) **مكتوبةٌ مرّتين بيدين** — خطأٌ في القاعدة لا في البناء يتكرّر في
#: الاثنتين فيستتر؛ وما يحرسها `test_payable_now_and_not_due_follow_the_withdrawal_rule` بأرقامه المكتوبة.
_RAW_DRIVER_SPLIT = text(
    "WITH balances AS ("
    " SELECT wt.owner_id AS user_id, SUM(wt.amount) AS balance FROM wallet_transactions wt"
    " JOIN users u ON u.id = wt.owner_id"
    " WHERE wt.owner_type::text = 'driver' AND u.country_code::text = :country AND u.is_test IS NOT TRUE"
    " GROUP BY wt.owner_id"
    "), positions AS ("
    " SELECT b.balance,"
    " LENGTH(TRIM(COALESCE(d.cliq_alias, ''))) > 0 AS has_cliq,"
    " EXISTS (SELECT 1 FROM wallet_freezes f WHERE f.user_id = b.user_id AND f.owner_type::text = 'driver') AS frozen,"
    " COALESCE((SELECT SUM(w.amount) FROM withdrawal_requests w"
    "  WHERE w.driver_id = d.id AND w.status::text IN ('pending', 'approved')), 0) AS requested,"
    " (CASE WHEN d.status::text = 'deactivated' THEN 0"
    "  ELSE COALESCE((SELECT ws.withdrawal_reserve_amount FROM wallet_settings ws WHERE ws.country_code::text = :country), 0)"
    "  END)"
    " + COALESCE((SELECT SUM(c.amount) FROM ride_cancellation_charges c"
    "  WHERE c.carrier_driver_id = d.id AND c.status::text = 'pending'), 0) AS held"
    " FROM balances b LEFT JOIN drivers d ON d.user_id = b.user_id"
    ") SELECT"
    " COALESCE(SUM(CASE WHEN frozen THEN 0"
    "  ELSE GREATEST(0, LEAST(balance, GREATEST(requested, balance - held))) END), 0),"
    " COALESCE(SUM(balance) FILTER (WHERE has_cliq), 0)"
    " FROM positions"
)


async def _raw_driver_split(session: AsyncSession, scope: Scope) -> dict[str, Decimal]:
    """`payable`: مجموعُ «يُصرف الآن» لكلِّ الكباتن، و`cliq`: أرصدةُ من في ملفّه حسابُ كليك — **لحسابات السوق الحقيقية وحدها**."""
    payable, cliq = (await session.execute(_RAW_DRIVER_SPLIT, {"country": scope.country.value})).one()
    return {"payable": money(payable), "cliq": money(cliq)}


def checks_for(
    page: dict[str, Decimal],
    wallets: dict[str, Decimal],
    by_type: dict[str, Decimal],
    split: dict[str, Decimal],
) -> list[Check]:
    """**ما يُقارَن بماذا** — كلُّ مجموعٍ من الدفتر في الصفحة بقرينه الخام، **وكلُّ قسمةٍ تُقارَن أقسامُها بأقسامٍ خامٍ** لا بأصلها
    وحدَه (`_RAW_DRIVER_SPLIT`). **وقسمةُ الشحن بقنواته تبقى بأصلها**: قنواتُها ثلاثةُ شروطٍ مستقلّةٍ على صفِّ المصدر، فقناةٌ تُسقط
    شحنةً أو تعدّها مرّتين **تخالف الأصلَ فعلاً** — لا جمعٌ يساوي أصلَه بالبناء.

    والإشارةُ تُقلب حيث قلبها المجموع: العمولةُ مدينةٌ في الدفتر وموجبةٌ في البطاقة.
    """

    def total(*keys: str) -> Decimal:
        return money(sum((page.get(key, Decimal(0)) for key in keys), Decimal(0)))

    t = WalletTransactionType
    rider = wallets.get(WalletOwnerType.RIDER.value, money(0))
    driver = wallets.get(WalletOwnerType.DRIVER.value, money(0))
    payable = split.get("payable", money(0))
    cliq = split.get("cliq", money(0))

    def ledger(kind: WalletTransactionType, sign: int = 1) -> Decimal:
        return money(by_type.get(kind.value, Decimal(0)) * sign)

    checks = [
        Check("rider_wallets", "أرصدةُ الركّاب", total("rider_balances"), rider),
        Check("driver_wallets", "أرصدةُ الكباتن", total("captain_balances"), driver),
        Check("driver_wallets_cliq", "أرصدةُ الكباتن: صرفٌ بكليك", total("captain_balances_cliq"), cliq),
        Check("driver_wallets_other", "أرصدةُ الكباتن: صرفٌ بغير كليك", total("captain_balances_other"), money(driver - cliq)),
        Check("driver_wallets_payable", "أرصدةُ الكباتن: يُصرف الآن", total("captain_payable_now"), payable),
        Check("driver_wallets_not_due", "أرصدةُ الكباتن: لم يحِن بعد", total("captain_not_due"), money(driver - payable)),
        Check("topups", "الشحن", total("topups"), ledger(t.TOPUP)),
        Check("topups_by_channel", "الشحن بقنواته", total("topups_cliq", "topups_card", "topups_cash"), ledger(t.TOPUP)),
        Check("commission", "العمولةُ المحصَّلة", total("commission_collected"), ledger(t.COMMISSION, -1)),
        Check("guarantee", "رسمُ الضمان", total("fee_guarantee"), ledger(t.GUARANTEE_FEE)),
        Check("cashback", "الاستردادُ الأسبوعيّ", total("cashback"), ledger(t.CASHBACK)),
        Check("referrals", "مكافآتُ الإحالة", total("referral_bonuses"), ledger(t.REFERRAL_BONUS)),
        Check("refunds", "الردود", total("refunds_riders", "refunds_captains"), ledger(t.REFUND)),
        Check("adjustments", "التصحيحات", total("adjustments", "earning_reversals"), ledger(t.ADJUSTMENT)),
    ]
    for kind in WalletTransactionType:
        checks.append(Check(f"ledger.{kind.value}", f"قيودُ {kind.value}", total(f"ledger.{kind.value}"), ledger(kind)))
    return checks


async def reconcile(session: AsyncSession, scope: Scope, page: dict[str, Decimal]) -> Reconciliation:
    """**المجاميعُ تتطابق** (القاعدة ٨) — أرقامُ الصفحة بلا مرشِّحات مقابلَ الدفتر الخام للسوق والفترة."""
    wallets, by_type = await _raw_ledger(session, scope)
    split = await _raw_driver_split(session, scope)
    return compare(checks_for(page, wallets, by_type, split), checked_at=scope.now)
