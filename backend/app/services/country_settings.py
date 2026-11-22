"""**كلُّ إعدادٍ لكلِّ دولة — من مصدرٍ واحد** (أمرُ المالك ٢٠٢٦-١١-١٨ الثاني، «عمولةُ الجزائر»).

**العطبُ الذي بُني له**: شاشةُ «الإعدادات» ترسم قسمَ الدولة **إن وُجد صفُّها**، والصفوفُ كتبها البذرُ يومَ ٢٠٢٦-٠٨-٢٠ — قبل أن تُضاف
الجزائرُ إلى `CountryCode` بشهرين (`906e4f73`، ٢٠٢٦-١٠-١١). **فلا صفَّ عمولةٍ للجزائر قطّ**، والشاشةُ تقول «لا إعداد عمولة لهذه الدولة»
والخادمُ يعمل بالافتراض (صفر). **وأخواتُه ستٌّ قِيست على الإنتاج**: السلفُ والإلغاءُ والرموزُ في الجزائر، والتوزيعُ والخريطةُ والتفاوضُ في ليبيا.

**والحلُّ ثلاثة، وكلٌّ يُقاس**:

١) **`FALLBACKS`** — لكلِّ جدولِ إعدادٍ واحدٍ لكلِّ دولة **صفُّه كما يقرؤه الخادمُ حين يغيب** (افتراضُ خدمته حرفاً). فما تعرضه اللوحةُ
   لدولةٍ بلا صفٍّ **هو ما يسري فعلاً**، لا شيءٌ يشبهه — و`tests/test_country_settings.py` يقيس لكلِّ جدولٍ أن الصفَّ المصنوعَ يُقرأ
   كالغياب **حقلاً حقلاً**، فإنشاؤه لا يغيّر شيئاً.
٢) **`for_every_country`** — أبوابُ اللوحة تُرجع صفّاً **لكلِّ دولةٍ في `CountryCode`** (المصدرُ الواحد)، فدولةٌ جديدةٌ تظهر في كلِّ شاشةٍ
   بإعداداتها الآمنة **يومَ تُضاف**، ويُكتب صفُّها أوّلَ حفظ. **ولا يكتب البابُ شيئاً** — مسارُ قراءة.
٣) **`missing`** — تحذيرٌ عند إقلاع الخادم بكلِّ (جدول، دولة) بلا صفّ، **ومعه ما يسري بدلَه**.

**وما ليس هنا محصيٌّ بعلّته** (`DECLARED`): جداولُ لكلِّ دولةٍ لا يُصنع لها صفٌّ هنا — ويُسقط الاختبارُ جدولاً جديداً ليس في أيٍّ منهما.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.advance import (
    DEFAULT_DEDUCTION_PERCENT,
    DEFAULT_MIN_COMPLETED_RIDES,
    DEFAULT_TERM_DAYS,
    AdvanceSetting,
)
from app.models.cancellation import (
    DEFAULT_BLOCK_AFTER_UNPAID,
    DEFAULT_CARRIER_GRACE_HOURS,
    DEFAULT_EXEMPT_WITHIN_METERS,
    DEFAULT_UNPAID_AFTER_DAYS,
    CancellationSetting,
)
from app.models.commission import CommissionSetting
from app.models.dispatch_setting import DispatchSetting
from app.models.enums import CommissionAppliesTo, CountryCode, UnpaidCancellationOutcome
from app.models.map_setting import DEFAULT_NEARBY_MAX_COUNT, DEFAULT_NEARBY_RADIUS_KM, MapSetting
from app.models.negotiation import NegotiationSetting
from app.models.otp_setting import (
    DEFAULT_LOCKOUT_MINUTES,
    DEFAULT_MAX_PER_DAY,
    DEFAULT_MAX_PER_REGISTRATION,
    DEFAULT_MAX_PER_WINDOW,
    DEFAULT_RESEND_BASE_SECONDS,
    DEFAULT_RESEND_MAX_SECONDS,
    DEFAULT_WINDOW_MINUTES,
    OtpSetting,
)

log = logging.getLogger(__name__)


def _commission(country: CountryCode) -> CommissionSetting:
    # **غيابُ الصفِّ صفر** (`settings_service.get_commission_percent`): مطفأةٌ بنسبة 0
    return CommissionSetting(
        country_code=country,
        commission_enabled=False,
        commission_percent=Decimal("0.00"),
        applies_to=CommissionAppliesTo.ALL_RIDES,
    )


def _advance(country: CountryCode) -> AdvanceSetting:
    # `advances.policy_for` حين يغيب الصفّ — والسلفُ نفسُها خلف مفتاح `driver_advances_enabled`
    return AdvanceSetting(
        country_code=country,
        deduction_percent=DEFAULT_DEDUCTION_PERCENT,
        min_kept_amount=Decimal("0.000"),
        term_days=DEFAULT_TERM_DAYS,
        min_completed_rides=DEFAULT_MIN_COMPLETED_RIDES,
        min_rating=Decimal("0.0"),
        growth_percent_per_repaid=0,
        max_multiplier_percent=100,
    )


def _cancellation(country: CountryCode) -> CancellationSetting:
    # `cancellation.settings_for` حين يغيب الصفّ
    return CancellationSetting(
        country_code=country,
        exempt_within_meters=DEFAULT_EXEMPT_WITHIN_METERS,
        exempt_when_location_unknown=True,
        block_after_unpaid=DEFAULT_BLOCK_AFTER_UNPAID,
        carrier_grace_hours=DEFAULT_CARRIER_GRACE_HOURS,
        unpaid_after_days=DEFAULT_UNPAID_AFTER_DAYS,
        unpaid_outcome=UnpaidCancellationOutcome.KEEP_PENDING,
    )


def _otp(country: CountryCode) -> OtpSetting:
    # `otp_limits.policy_for` حين يغيب الصفّ
    return OtpSetting(
        country_code=country,
        window_minutes=DEFAULT_WINDOW_MINUTES,
        max_per_window=DEFAULT_MAX_PER_WINDOW,
        max_per_day=DEFAULT_MAX_PER_DAY,
        max_per_registration=DEFAULT_MAX_PER_REGISTRATION,
        lockout_minutes=DEFAULT_LOCKOUT_MINUTES,
        resend_base_seconds=DEFAULT_RESEND_BASE_SECONDS,
        resend_max_seconds=DEFAULT_RESEND_MAX_SECONDS,
    )


def _map(country: CountryCode) -> MapSetting:
    # `map_settings.limits_for` و`pickup_suggest_enabled` حين يغيب الصفّ
    return MapSetting(
        country_code=country,
        nearby_radius_km=Decimal(DEFAULT_NEARBY_RADIUS_KM),
        nearby_max_count=DEFAULT_NEARBY_MAX_COUNT,
        pickup_suggest_enabled=True,
    )


def _dispatch(country: CountryCode) -> DispatchSetting:
    from app.services.dispatch_settings import DEFAULTS

    return DispatchSetting(country_code=country, **asdict(DEFAULTS))


def _negotiation(country: CountryCode) -> NegotiationSetting:
    from app.services.negotiation import DISABLED

    values = asdict(DISABLED)
    values["categories"] = list(values["categories"])
    return NegotiationSetting(country_code=country, **values)


#: **الجدولُ ← صانعُ صفِّه كما يُقرأ غائباً**
FALLBACKS: dict[str, tuple[type, Callable[[CountryCode], object]]] = {
    "commission_settings": (CommissionSetting, _commission),
    "advance_settings": (AdvanceSetting, _advance),
    "cancellation_settings": (CancellationSetting, _cancellation),
    "otp_settings": (OtpSetting, _otp),
    "map_settings": (MapSetting, _map),
    "dispatch_settings": (DispatchSetting, _dispatch),
    "negotiation_settings": (NegotiationSetting, _negotiation),
}

#: **جداولُ لكلِّ دولةٍ لا يُصنع لها صفٌّ هنا — بعلّتها**. والاختبارُ يُسقط جدولاً جديداً ليس هنا ولا في `FALLBACKS`.
DECLARED: dict[str, str] = {
    "service_settings": "بابُ اللوحة يُرجع صفّاً لكلِّ دولةٍ بافتراضاته منذ §٦٣ (`list_service_settings`)",
    "payment_settings": "صفُّه شرطُ الدفع نفسِه، ومكتوبٌ للأسواق الثلاثة؛ وغيابُه يُحذَّر منه عند الإقلاع (`REQUIRED`)",
    "wallet_settings": "حدودُ التحويل والسحب — غيابُها رفضٌ لا افتراض (`seed_wallet_settings`)؛ ويُحذَّر منه عند الإقلاع (`REQUIRED`)",
    "ride_sharing_settings": "المشاركةُ خلف مفتاحها، وصفُّها مكتوبٌ للثلاثة؛ ويُحذَّر من غيابه عند الإقلاع (`REQUIRED`)",
    "notification_settings": "منطقةُ الدولة الزمنيّة وساعاتُ الهدوء — مكتوبةٌ للثلاثة؛ ويُحذَّر من غيابها عند الإقلاع (`REQUIRED`)",
    "country_markets": "حالُ السوق وظهورُه في المنتقي — بابُه «الدول والحدود»، وغيابُه «مخفية» بقرار المالك ١٨/١١",
    "document_settings": "غائبٌ في الدول الثلاث، وشاشتُه تعرض الافتراضَ وتكتب الصفَّ أوّلَ حفظ",
    "quality_settings": "غائبٌ في الدول الثلاث، وشاشتُه تعرض الافتراضَ وتكتب الصفَّ أوّلَ حفظ",
    "loyalty_rules": "غائبٌ في الدول الثلاث، والولاءُ خلف مفتاحه المطفأ",
    "taxo_card_settings": "غائبٌ في الدول الثلاث، والبطاقاتُ خلف مفتاحها",
    "support_settings": "غائبٌ في الدول الثلاث، وشاشتُه تعرض الافتراضَ وتكتب الصفَّ أوّلَ حفظ",
    "quick_reply_settings": "غائبٌ في الدول الثلاث، وبطاقتُه في «الطوارئ» تعرض الافتراضَ وتكتب الصفَّ أوّلَ حفظ؛ والميزةُ خلف مفتاحها",
    "cross_transfer_limits": "حدودُ التحويل بين الدول — غائبةٌ في الدول الثلاث، **وغيابُها رفضٌ لا افتراض**، والميزةُ خلف مفتاحها المطفأ (§١١٢)",
}

#: **ما لا افتراضَ معروضاً له** — غيابُه يُكتب تحذيراً أعلى عند الإقلاع
REQUIRED: dict[str, type] = {}


def _required() -> dict[str, type]:
    if not REQUIRED:
        from app.models.notification import NotificationSetting
        from app.models.payment_setting import PaymentSetting
        from app.models.sharing import RideSharingSetting
        from app.models.wallet_setting import WalletSetting

        REQUIRED.update(
            {
                "payment_settings": PaymentSetting,
                "wallet_settings": WalletSetting,
                "ride_sharing_settings": RideSharingSetting,
                "notification_settings": NotificationSetting,
            }
        )
    return REQUIRED


async def for_every_country(session: AsyncSession, table: str) -> list:
    """**صفٌّ لكلِّ دولةٍ في `CountryCode`** — المحفوظُ كما هو، والغائبُ بصانعه (غيرُ مضافٍ إلى الجلسة: مسارُ قراءةٍ لا يكتب)."""
    model, make = FALLBACKS[table]
    rows = {row.country_code: row for row in await session.scalars(select(model))}
    return [rows.get(country) or make(country) for country in CountryCode]


async def missing(session: AsyncSession) -> dict[str, list[str]]:
    """كلُّ (جدول، دولة) بلا صفّ — لما في `FALLBACKS` و`REQUIRED`."""
    out: dict[str, list[str]] = {}
    tables = {name: model for name, (model, _) in FALLBACKS.items()} | _required()
    for name, model in tables.items():
        present = set(await session.scalars(select(model.country_code)))
        absent = [country.value for country in CountryCode if country not in present]
        if absent:
            out[name] = absent
    return out


async def warn_on_startup(session_maker) -> None:
    """**تحذيرٌ واضحٌ عند الإقلاع** (أمرُ المالك) — ولا يكتب شيئاً، ولا يُسقط الإقلاعَ إن تعذّرت القراءة."""
    try:
        async with session_maker() as session:
            gaps = await missing(session)
    except Exception:  # noqa: BLE001 — تحذيرٌ لا يوقف خادماً
        log.warning("فحصُ إعدادات الدول عند الإقلاع تعذّر", exc_info=True)
        return
    for table, countries in gaps.items():
        if table in FALLBACKS:
            log.warning(
                "إعدادُ دولةٍ بلا صفّ: %s في %s — يسري الافتراضُ وتعرضه اللوحة، ويُكتب الصفُّ أوّلَ حفظ",
                table,
                ",".join(countries),
            )
        else:
            log.error("⚠ إعدادُ دولةٍ بلا صفٍّ ولا افتراضٍ معروض: %s في %s — يُضبط من اللوحة قبل فتح السوق", table, ",".join(countries))
