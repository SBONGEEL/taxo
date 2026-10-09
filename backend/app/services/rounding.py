"""لا كسورَ في المال: التقريبُ إلى وحدة الدولة (SPEC §٧٠) — **بيتٌ واحدٌ للقاعدة والإعداد والسجلّ**.

**القاعدةُ الواحدة** (§٧٠-ج/١): لكلِّ مبلغٍ يدفعه شخصٌ أو يقبضه — **ما يُحسب يُقرَّب**، وما يختاره الشخصُ يُشترط أن يكون من
مضاعفات الوحدة. **والتقريبُ مرّةً واحدةً على المبلغ النهائيّ** بعد كلِّ نسبة (القسائمُ والخصوماتُ أوّلاً).

**ثلاثةُ أشياءَ هنا لا غير**:
1. **الإعداد** (`policy_for`): من `payment_settings` لكلِّ سوق. **مطفأً هو الهويّة** — `round_amount` يعيد المبلغَ نفسَه وفرقاً
   صفراً، **فلا يتغيّر مبلغٌ واحدٌ عمّا كان** في سوقٍ لم يُشعَل (وهو حالُ السوقين بعد الترحيلة `0104`).
2. **الحساب** (`round_amount` · `floor_to_unit` · `is_multiple`): بـ`Decimal` وحدَه، على دقّة `0.001`. **و«الأقرب» نصفُه للأعلى**:
   `2.249 ⇐ 2.000` · `2.250 ⇐ 2.500` · `2.750 ⇐ 3.000` بوحدة `0.500`. و«للأعلى» سقفٌ و«للأدنى» أرضيّة.
3. **السجلّ** (`record`): صفٌّ في `money_roundings` لكلِّ فرق — **القيدُ الصريحُ لكلِّ فلس** (§٧٠-ج/٣)، بمفتاحٍ فريدٍ على المصدر.

**والرحلةُ** (`apply_to_ride`) أوّلُ من يستعمله: عند الإنهاء، بعد الخصم، يُقرَّب ما بقي على الراكب مرّةً (§٧٠-ج/٤).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AmountNotMultiple, Conflict
from app.models.enums import CountryCode, FareLineKind, RoundingMode, RoundingSource
from app.models.payment import OWING_PAYMENT_STATUSES, PLATFORM_WRITTEN_METHODS, Payment
from app.models.payment_setting import DEFAULT_ROUNDING_UNIT, PaymentSetting
from app.models.ride import Ride
from app.models.rounding import MoneyRounding
from app.services.pricing import FareLine, round_money

if TYPE_CHECKING:
    from app.models.enums import WalletOwnerType
    from app.models.user import User
    from app.models.wallet import WalletTransaction

ZERO = Decimal("0.000")
_HALF = Decimal("0.5")


@dataclass(frozen=True, slots=True)
class RoundingPolicy:
    """إعدادُ سوقٍ واحد — **و`enabled=False` هويّةٌ لا تقريبٌ بوحدةٍ ما**."""

    enabled: bool
    unit: Decimal
    mode: RoundingMode


#: **المطفأ** — ما يُقرأ لسوقٍ بلا صفّ إعداداتٍ أو بمفتاحٍ مطفأ
DISABLED = RoundingPolicy(enabled=False, unit=DEFAULT_ROUNDING_UNIT, mode=RoundingMode.NEAREST)


# ------------------------------------------------------------------ الإعداد


def policy_of(setting: PaymentSetting | None) -> RoundingPolicy:
    if setting is None or not setting.rounding_enabled:
        return DISABLED
    return RoundingPolicy(
        enabled=True, unit=setting.rounding_unit, mode=RoundingMode(setting.rounding_mode)
    )


async def policy_for(session: AsyncSession, country: CountryCode) -> RoundingPolicy:
    """إعدادُ السوق الآن — **قراءةٌ لا تُنشئ صفّاً**، وغيابُ الصفِّ مطفأ."""
    setting = await session.scalar(
        select(PaymentSetting).where(PaymentSetting.country_code == country)
    )
    return policy_of(setting)


def frozen_policy(ride: Ride) -> RoundingPolicy:
    """**سياسةُ العرض المجمَّدةُ على الرحلة لحظةَ طلبها** — للعدّاد الحيّ في بثٍّ بلا جلسة (`RideOut.from_ride`).

    **ورحلةُ الساعة تُجمَّد عليها ثانيةً عند البدء** (`hourly.prepay_on_start`): السياسةُ التي قُرِّب بها المقدَّم — **وبها وحدَها
    يُقرَّب باقيها عند الإنهاء** (`apply_to_ride`).

    **ورحلةُ المشوار الثابت لا تُقرَّب**: سعرُها مدفوعٌ مقدّماً بقناة `commute` كاملاً (`apply_to_ride` يقول لمَ).
    """
    if (
        ride.rounding_unit_at_ride is None
        or ride.rounding_mode_at_ride is None
        or ride.commute_id is not None
    ):
        return DISABLED
    return RoundingPolicy(
        enabled=True, unit=ride.rounding_unit_at_ride, mode=RoundingMode(ride.rounding_mode_at_ride)
    )


def freeze_on(ride: Ride, policy: RoundingPolicy) -> None:
    """يجمّد سياسةَ العرض على رحلةٍ تُنشأ الآن — و`NULL` للمطفأ فتبقى الرحلةُ كما كانت حرفاً."""
    ride.rounding_unit_at_ride = policy.unit if policy.enabled else None
    ride.rounding_mode_at_ride = policy.mode.value if policy.enabled else None


# ------------------------------------------------------------------ الحساب


def round_amount(amount: Decimal, policy: RoundingPolicy) -> tuple[Decimal, Decimal]:
    """`(المقرَّب، الفرق)` — والفرقُ **المقرَّبُ ناقصَ الدقيق**، موجبٌ إن زاد ما يُدفع.

    **مطفأً يعود المبلغُ نفسُه وفرقٌ صفريّ** — لا `round_money` ولا شيء: الهويّةُ حرفاً.

    **و«الأقرب» أرضيّةُ (الخطوات + نصف)** لا `ROUND_HALF_UP`، وهما سواءٌ على كلِّ موجب. **والفرقُ في السالب وحدَه**:
    `ROUND_HALF_UP` يبعد النصفَ عن الصفر (`−0.250 ⇐ −0.500`)، وهذا يرفعه نحو الأعلى (`−0.250 ⇐ 0.000`) — **وهو ما يحتاجه
    باقٍ سالبٌ على رحلةٍ بالساعة** دُفع مقدَّمُها مقرَّباً للأعلى (`apply_to_ride`): «نصفُه للأعلى» بمعناه لا باسم الدالّة.
    """
    if not policy.enabled:
        return amount, ZERO
    steps = amount / policy.unit
    if policy.mode is RoundingMode.UP:
        whole = steps.to_integral_value(rounding=ROUND_CEILING)
    elif policy.mode is RoundingMode.DOWN:
        whole = steps.to_integral_value(rounding=ROUND_FLOOR)
    else:
        whole = (steps + _HALF).to_integral_value(rounding=ROUND_FLOOR)
    rounded = round_money(whole * policy.unit)
    return rounded, round_money(rounded - amount)


def rounded(amount: Decimal, policy: RoundingPolicy) -> Decimal:
    """المقرَّبُ وحدَه — **للعرض** (التقدير ومعاينةُ القسيمة): ما سيدفعه الراكبُ لا ما يُحفظ."""
    return round_amount(amount, policy)[0]


async def shown_in(session: AsyncSession, country: CountryCode, amount: Decimal | None) -> Decimal | None:
    """**مبلغٌ يُعرض قبل أن يُدفع — مقرَّباً بإعداد سوقه الآن** (§٧٠-ج/٤: «والعرضُ مقرَّبٌ بالقاعدة نفسِها») — لحقولٍ تحفظ الدقيقَ
    وتعرضه: تقديرُ الحجز المجدول، وسعرُ مقعد بين المدن وسيارتِها في القوائم (مراجعةُ المال البند ١٣). **المحفوظُ لا يُمسّ**،
    والتطبيقاتُ تعرض ما وصل. ومطفأً أو `None` يعود كما هو."""
    if amount is None:
        return None
    return rounded(amount, await policy_for(session, country))


def floor_to_unit(amount: Decimal, policy: RoundingPolicy) -> Decimal:
    """**أكبرُ مضاعفٍ للوحدة لا يتجاوز المبلغ** — ما تدفعه محفظةٌ رصيدُها بكسور (§٧٠-ج/٤): الكسرُ يبقى فيها لصاحبه.

    مطفأً يعود المبلغُ نفسُه.
    """
    if not policy.enabled:
        return amount
    whole = (amount / policy.unit).to_integral_value(rounding=ROUND_FLOOR)
    return round_money(whole * policy.unit)


def ceil_to_unit(amount: Decimal, policy: RoundingPolicy) -> Decimal:
    """**أصغرُ مضاعفٍ للوحدة لا ينقص عن المبلغ** — «ادفع الدَّين كلَّه» (§٧٠-ج/٦): يُقرَّب للأعلى والزائدُ يُردّ صراحةً
    (`return_excess`). مطفأً يعود المبلغُ نفسُه."""
    if not policy.enabled:
        return amount
    whole = (amount / policy.unit).to_integral_value(rounding=ROUND_CEILING)
    return round_money(whole * policy.unit)


def toward(policy: RoundingPolicy, mode: RoundingMode) -> RoundingPolicy:
    """**سياسةُ السوق نفسُها باتجاهٍ يفرضه المسار** — ووحدتُها هي هي.

    مساراتٌ لا يحكمها اتجاهُ السوق، **وكلٌّ بعلّته**: غرامةُ الضمان **للأدنى** (لا تأخذ أكثرَ من رصيده) · الاستردادُ النسبيُّ
    للاشتراك **للأعلى** (شرطُ المالك القائم: «الكسور تُقرَّب لصالح الكبتن») · «ادفع الدَّين كلَّه» وسدادُ السلفة الكامل
    **للأعلى** والزائدُ يُردّ (§٧٠-ج/٦) — فلا يبقى على أحدٍ كسرٌ ولا يُؤخذ منه فلس.
    **ويُكتب الاتجاهُ المفروضُ في صفِّ السجلّ** لا اتجاهُ السوق — فالصفُّ يقول ما وقع. ومطفأً يبقى مطفأً.
    """
    return replace(policy, mode=mode) if policy.enabled else policy


def is_multiple(amount: Decimal, policy: RoundingPolicy) -> bool:
    """هل المبلغُ مضاعفٌ للوحدة؟ — مطفأً كلُّ مبلغٍ مقبول."""
    return not policy.enabled or amount % policy.unit == 0


def require_multiple(amount: Decimal, policy: RoundingPolicy, *, field: str | None = None) -> None:
    """**ما يختاره الشخصُ مضاعفٌ للوحدة وإلا رُدّ برسالةٍ عربيّة** (§٧٠-ج/٦) — **لا يُبدَّل رقمٌ كتبه أحدٌ بيده من وراء ظهره**.

    **ورمزُه `amount_not_multiple`** (`AmountNotMultiple`) ومعه الوحدةُ والمضاعفان المجاوران — فالشاشةُ تقترحهما ولا تحسبهما
    (§14). ومطفأً لا يُردّ شيء.
    """
    if not is_multiple(amount, policy):
        lower = floor_to_unit(amount, policy)
        upper = round_money(lower + policy.unit)
        raise AmountNotMultiple(
            f"المبلغُ يكون من مضاعفات {round_money(policy.unit)} — {lower} أو {upper}",
            unit=str(round_money(policy.unit)),
            lower=str(lower),
            upper=str(upper),
            **({"field": field} if field else {}),
        )


async def require_multiple_in(
    session: AsyncSession, country: CountryCode, amount: Decimal, *, field: str | None = "amount"
) -> RoundingPolicy:
    """`require_multiple` بإعداد السوق الآن — **لأبواب ما يختاره الشخص** (الشحنُ والسحبُ والتحويلُ والبقشيشُ والسلفةُ وسدادُ
    الدَّين). ويعيد السياسةَ لمن يحتاجها بعده."""
    policy = await policy_for(session, country)
    require_multiple(amount, policy, field=field)
    return policy


# ------------------------------------------------------------------ السجلّ


async def record(
    session: AsyncSession,
    *,
    country: CountryCode,
    source: RoundingSource,
    source_id: uuid.UUID,
    user_id: uuid.UUID | None,
    precise: Decimal,
    rounded_amount: Decimal,
    policy: RoundingPolicy,
) -> MoneyRounding | None:
    """يكتب فرقَ تقريبٍ واحداً — **أو لا شيء حين لا فرق**.

    **ولمَ لا صفَّ لفرقٍ صفريّ** (قرارٌ مكتوبٌ لا سهو): شرطُ المالك «**كلُّ فرقِ** تقريبٍ يُقيَّد صراحةً» — **والصفرُ ليس فرقاً**:
    لا فلسَ تحرّك فلا ما يُقيَّد. وصفٌّ لكلِّ معاملةٍ بلا فرقٍ يملأ السجلَّ بما لا يقول شيئاً **فيُخفي ما يقول**؛ و«قُرِّب أم لا»
    يُقرأ من المبلغ نفسِه (مضاعفٌ للوحدة). **والقاعدةُ تحرس ذلك** (`difference <> 0`).

    **ومرّةً لكلِّ مصدر**: يُنادى وصفُّ المصدر مقفولٌ بيد المستدعي (الرحلةُ في `complete_ride`)، فالقراءةُ ثمّ الكتابةُ متسلسلتان؛
    **وصفٌّ قائمٌ بقيمٍ أخرى يُرفض لا يُبتلع** — تقريبان مختلفان لمعاملةٍ واحدةٍ هما بعينهما الفلسُ الضائعُ بصمت. والقيدُ الفريدُ
    في القاعدة آخرُ الحرّاس.
    """
    difference = round_money(rounded_amount - precise)
    if difference == 0 or not policy.enabled:
        return None
    existing = await session.scalar(
        select(MoneyRounding).where(
            MoneyRounding.source_kind == source.value, MoneyRounding.source_id == source_id
        )
    )
    if existing is not None:
        if existing.precise == round_money(precise) and existing.difference == difference:
            return existing
        raise Conflict("تقريبٌ آخرُ مسجَّلٌ لهذه المعاملة بقيمٍ أخرى")
    row = MoneyRounding(
        country_code=country,
        source_kind=source.value,
        source_id=source_id,
        user_id=user_id,
        precise=round_money(precise),
        rounded=round_money(rounded_amount),
        difference=difference,
        unit=policy.unit,
        mode=policy.mode.value,
    )
    session.add(row)
    await session.flush()
    return row


async def difference_of(
    session: AsyncSession, source: RoundingSource, source_id: uuid.UUID
) -> Decimal:
    """فرقُ تقريب مصدرٍ — **وصفرٌ حين لا صفّ**."""
    value = await session.scalar(
        select(MoneyRounding.difference).where(
            MoneyRounding.source_kind == source.value, MoneyRounding.source_id == source_id
        )
    )
    return value if value is not None else ZERO


async def ride_difference(session: AsyncSession, ride_id: uuid.UUID) -> Decimal:
    """**فرقُ تقريب الرحلة** — يقرؤه وعاءُ العمولة (`payments._commission_amount`) ليُخرجه منه كرسوم الكبتن."""
    return await difference_of(session, RoundingSource.RIDE, ride_id)


async def return_excess(
    session: AsyncSession,
    *,
    owner: User,
    owner_type: WalletOwnerType,
    country: CountryCode,
    source: RoundingSource,
    source_id: uuid.UUID,
    precise: Decimal,
    paid: Decimal,
    policy: RoundingPolicy,
    idempotency_key: str,
    reference: str,
    created_by: uuid.UUID | None = None,
    advance_id: uuid.UUID | None = None,
) -> WalletTransaction | None:
    """**«سدّد كلَّ ما عليك» مقرَّباً للأعلى — والزائدُ يُردّ إلى محفظته قيداً صريحاً** (SPEC §٧٠-ج/٦) — **لا يُبتلع**.

    قيدان لا قيدٌ واحد، **وكلٌّ يقول نصفَه**: قيدُ دفترٍ من نوع `rounding` بالزائد (`paid − precise`، موجب) في محفظة صاحبه،
    **وصفٌّ في السجلّ** (الدقيقُ ما كان عليه، والمقرَّبُ ما دفعه). فصافيه ما كان عليه حرفاً، **ولا فلسَ تحرّك بلا سطرٍ يقوله**.

    يُنادى **ومحفظتُه مقفولة** في مسار المستدعي (`wallet.record` يأخذ القفلَ نفسَه ثانيةً بلا ثمن)، **ومفتاحُ التكرار من
    المستدعي** فتأكيدٌ يُعاد لا يردّ مرّتين. ومطفأً أو بلا زائد لا يكتب شيئاً.

    **و`advance_id` لسداد السلفة**: الزائدُ جزءٌ من سدادها، فيحمل معرّفَها — وما سُدِّد منها (`advances.repaid_amount`) وأرباحُ
    الكبتن (`earnings`) يقرآنه معه، **فالمسدَّدُ المتبقّي بعينه لا المقرَّب**.
    """
    excess = round_money(paid - precise)
    if excess <= 0 or not policy.enabled:
        return None
    from app.models.enums import WalletTransactionType
    from app.services import wallet

    entry = await wallet.record(
        session,
        owner=owner,
        owner_type=owner_type,
        tx_type=WalletTransactionType.ROUNDING,
        amount=excess,
        advance_id=advance_id,
        reference=reference,
        created_by=created_by,
        idempotency_key=idempotency_key,
    )
    await record(
        session,
        country=country,
        source=source,
        source_id=source_id,
        user_id=owner.id,
        precise=precise,
        rounded_amount=paid,
        policy=policy,
    )
    return entry


# ------------------------------------------------------------------ الرحلة


async def apply_to_ride(session: AsyncSession, ride: Ride) -> MoneyRounding | None:
    """**التقريبُ المحفوظُ للرحلة — مرّةً عند الإنهاء، بعد الخصم** (SPEC §٧٠-ج/٤).

    يُنادى من `rides.complete_ride` **وصفُّ الرحلة مقفول**، و`final_fare` الأجرةُ الدقيقةُ بسطورها، **وصفوفُ الخصم مفتوحةٌ
    بمبالغها على الدقيقة** (القسيمةُ والمشاركة — `promo/sharing.open_discount`) **ولم تُسوَّ بعد**: تسويتُها تقرأ وعاءَ العمولة،
    والوعاءُ يحتاج الفرق.

    - **ما يبقى على الراكب** = الأجرة − كلُّ دفعةٍ قائمة (الخصمان، **ومقدَّمُ الساعة** إن دُفع عند البدء) — **يُقرَّب مرّةً**.
    - **الفرقُ سطرُ «تقريب»** في `fare_lines` ويُضاف إلى `final_fare`، فتُجمع السطورُ إليها حرفاً، **وما على الراكب = النهائيّة −
      المدفوع = مضاعفٌ للوحدة**.
    - **وصفٌّ في `money_roundings`**: الدقيقُ هنا **مجموعُ ما على الراكب في الرحلة كلِّها** (الأجرة − خصمُ المنصّة)، والمقرَّبُ
      هو بعد الفرق — فمقدَّمُ الساعة المقرَّبُ وباقيها المقرَّبُ يُقرآن مبلغاً واحداً.

    **ومقدَّمُ الساعة لا يُقرَّب مرّتين** (`hourly.prepay_on_start` يقرّبه ويجمّد سياستَه على الرحلة): مضاعفٌ للوحدة + تقريبُ
    الباقي = تقريبُ المجموع مرّةً حرفاً. **وباقٍ سالبٌ أقلُّ من وحدة** (مقدَّمٌ قُرِّب للأعلى ولم يزد شيء) يُقرَّب إلى صفر فيرتفع
    الفرقُ إلى ما دُفع — **فلا يبقى فلسٌ دفعه الراكبُ خارج الأجرة بلا سطر**.

    **ورحلةُ الساعة تُقرَّب بالسياسة المجمَّدة عند البدء لا بإعداد لحظة الإنهاء** (`frozen_policy`): معاملتُها بدأت بالمقدَّم،
    **وتغييرُ الإعداد في أثنائها كان يفصل الجزأين** — إطفاءٌ يترك فرقَ المقدَّم (`+0.125`) بلا سطرٍ ولا صفّ والراكبُ دفعه، واتجاهٌ
    آخرُ يكتب في السجلّ ما لم يُدفع، ووحدةٌ أخرى تجعل المجموعَ غيرَ مضاعف. **فالجزآن بسياسةٍ واحدة**، والباقي السالبُ يُقرَّب بها
    إلى سطر «تقريب» وصفّ. ورحلةُ ساعةٍ بدأت قبل هذا البناء بلا سياسةٍ مجمَّدة: مقدَّمُها لم يُقرَّب فلا يُقرَّب باقيها.

    **ولا تُقرَّب** (يعود `None`):
    - **في سوقٍ مطفأ** — الأجرةُ كما كانت حرفاً.
    - **رحلةُ المشوار الثابت**: سعرُها مدفوعٌ مقدّماً بقناة `commute` تساوي الأجرةَ كلَّها (`commute.settle_ride`)، **فلا شيءَ
      يبقى على الراكب** — وتقريبُها هنا يغيّر أجرةً يدفعها صفٌّ لم يُكتب بعد. **وسعرُ المشوار نفسُه يُقرَّب عند شرائه** (§٧٠-ج/٥).
    - **ما تغطّيه المنصّةُ كلَّه** (خصمٌ يبلغ الأجرة) — لا شيءَ يدفعه الراكبُ ليُقرَّب.
    - **فرقٌ صفريّ** — الباقي مضاعفٌ أصلاً.
    """
    if ride.final_fare is None or ride.commute_id is not None:
        return None
    policy = frozen_policy(ride) if ride.ride_type == "hourly" else await policy_for(session, ride.country_code)
    if not policy.enabled:
        return None

    rows = (
        await session.execute(
            select(Payment.method, Payment.amount).where(
                Payment.ride_id == ride.id, Payment.status.in_(OWING_PAYMENT_STATUSES)
            )
        )
    ).all()
    platform = sum((amount for method, amount in rows if method in PLATFORM_WRITTEN_METHODS), ZERO)
    covered = sum((amount for _, amount in rows), ZERO)

    rider_total = round_money(ride.final_fare - platform)
    if rider_total <= 0:
        return None
    remaining = round_money(ride.final_fare - covered)
    _, difference = round_amount(remaining, policy)
    if difference == 0 or rider_total + difference < 0:
        return None

    ride.final_fare = round_money(ride.final_fare + difference)
    # **سطرٌ بذاته** (§٧٠-أ/٩) — وقائمةٌ جديدةٌ لا إلحاقٌ في مكانها: عمودُ JSONB لا يرى تغيّراً داخل القائمة نفسِها
    if ride.fare_lines:
        ride.fare_lines = [*ride.fare_lines, FareLine(FareLineKind.ROUNDING.value, difference).as_json()]
    return await record(
        session,
        country=ride.country_code,
        source=RoundingSource.RIDE,
        source_id=ride.id,
        user_id=ride.rider_id,
        precise=rider_total,
        rounded_amount=rider_total + difference,
        policy=policy,
    )


def ride_display_fare(ride: Ride, fare: Decimal) -> Decimal:
    """**أجرةُ رحلةٍ لم تنتهِ كما ستُحفظ لو انتهت الآن** — العدّادُ الحيُّ (`RideOut.current_fare`) وإشعاراتُ العرض (§٧٠-ج/٤).

    الخصمان أوّلاً على الأجرة دون رسوم الكبتن **بقاعدتيهما المجمَّدتين** (الدالّتان نفسُهما اللتان يُحسب بهما عند الإنهاء)،
    **ثمّ يُقرَّب ما بقي على الراكب**، ويُضاف فرقُه إلى الأجرة — فبلا خصمٍ هي الأجرةُ مقرَّبة، ومع خصمٍ هي الأجرةُ التي سيقرؤها
    الراكبُ في إيصاله. **وبسياسة لحظة الطلب المجمَّدة** (`frozen_policy`): يُنادى حيث لا جلسة. **والمحفوظُ لا يُحسب هنا** — مرّةً
    عند الإنهاء بإعداد لحظته (`apply_to_ride`). ومطفأً هي الأجرةُ حرفاً كما كانت.
    """
    policy = frozen_policy(ride)
    if not policy.enabled:
        return fare
    return ride_fare_with_rounding(fare, _frozen_discounts(ride, fare), policy)


def _frozen_discounts(ride: Ride, fare: Decimal) -> Decimal:
    """الخصمان (القسيمةُ والمشاركة) على أجرةٍ ما **بقاعدتيهما المجمَّدتين** — الدالّتان نفسُهما اللتان يُحسبان بهما عند الإنهاء."""
    from app.services import pricing, promo, sharing

    base = pricing.discountable(fare, ride.captain_fees_at_ride)
    discounts = promo.discount_on_ride(ride, base)
    if ride.share_discount_percent_at_ride > 0:
        discounts += sharing.discount_on(base, ride.share_discount_percent_at_ride)
    return discounts


def rider_estimate(ride: Ride) -> Decimal:
    """**ما يعرضه عدّادُ الراكب قبل الأجرة النهائيّة** (`RideOut.rider_estimate`) — مراجعةُ المال ٢٠٢٦-١٠-٠٩، البند ٨.

    - **مطفأً هو `estimated_fare` حرفاً** — ما عرضه العدّادُ قبل §٧٠، **فلا يتغيّر سلوكٌ بلا إذن المالك** (لا انتظارَ ولا وقفاتٍ
      تدخله، ولا خصمَ يُطرح منه).
    - **ومشتعلاً هو ما سيدفعه الراكبُ من التقدير**: المقدَّرةُ ناقصَ الخصمين المجمَّدين، **مقرَّبةً مرّةً** بسياسة الرحلة المجمَّدة
      — مضاعفٌ للوحدة، وهو الرقمُ الذي سيدفعه نقداً أو من محفظته إن لم يتراكم انتظار. **ولا تُضاف الوقفاتُ والانتظارُ هنا**: العدّادُ
      لم يعرضها قبل §٧٠، وإضافتُها تغييرٌ في معناه لم يُقرّه المالك (مكتوبٌ في التقرير).
    - **ورحلةُ المشوار الثابت** سياستُها مطفأةٌ بالبناء (`frozen_policy`) فتُعرض بسعرها المجمَّد كما كانت.

    **يُبنى حيث لا جلسة** (بثُّ المقبس) — فمن الرحلة وحدَها.
    """
    policy = frozen_policy(ride)
    if not policy.enabled:
        return ride.estimated_fare
    rider = round_money(ride.estimated_fare - _frozen_discounts(ride, ride.estimated_fare))
    if rider <= 0:
        return ZERO
    return rounded(rider, policy)


def ride_fare_with_rounding(fare: Decimal, discounts: Decimal, policy: RoundingPolicy) -> Decimal:
    """**الأجرةُ كما ستُحفظ لو انتهت الرحلةُ الآن** — للعرض (العدّادُ الحيّ)، بالقاعدة نفسِها: الخصمُ أوّلاً ثمّ تقريبُ الباقي.

    بلا خصمٍ هي الأجرةُ مقرَّبة. **ومقدَّمُ الساعة لا يدخلها**: مضاعفٌ للوحدة فلا يغيّر الفرق.
    """
    rider = round_money(fare - discounts)
    if not policy.enabled or rider <= 0:
        return fare
    _, difference = round_amount(rider, policy)
    return round_money(fare + difference)
