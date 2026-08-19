"""بذر إعدادات التطوير المحلي.

    python -m scripts.seed

يملأ إعدادات الدولتين (التسعير، مفاتيح الميزات، العمولة، خطط الاشتراك) ويكتب
توكنات Mapbox وTelr Sandbox **مشفّرة** في `provider_credentials` — وهو ما تصفه
SPEC بأنه أول خطوة بعد تشغيل النظام (القسم 4). المصدر الرسمي لهذه المفاتيح بعد
ذلك هو صفحة العقود؛ قراءتها من البيئة تحدث هنا فقط ولمرة واحدة.

السكربت idempotent: لا يلمس صفاً موجوداً حتى لا يمحو تعديلات المشرف.
"""

from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import REPO_ROOT, settings
from app.core.currency import currency_for_country
from app.core.db import SessionLocal, engine
from app.core.phone import normalize_phone
from app.core.security import hash_password
from app.models.commission import CommissionSetting
from app.models.enums import (
    CountryCode,
    FeatureKey,
    ProviderKey,
    SubscriptionDurationType,
    UserRole,
    VehicleCategory,
)
from app.models.feature_flag import FeatureFlag
from app.models.pricing import PricingRule
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.services import campaigns
from app.models.payment_setting import (
    DEFAULT_CLIQ_CONFIRMATION_HOURS,
    PaymentSetting,
)
from app.models.sharing import (
    DEFAULT_CORRIDOR_KM,
    DEFAULT_DISCOUNT_PERCENT,
    DEFAULT_MAX_DETOUR_MINUTES,
    RideSharingSetting,
)
from app.models.referral import (
    DEFAULT_REQUIRED_RIDES,
    DEFAULT_REWARD_AMOUNT,
    ReferralSetting,
)
from app.models.advance import (
    DEFAULT_DEDUCTION_PERCENT,
    DEFAULT_TERM_DAYS,
    AdvanceSetting,
)
from app.models.cancellation import (
    DEFAULT_EXEMPT_WITHIN_METERS,
    CancellationSetting,
)
from app.models.otp_setting import (
    DEFAULT_MAX_PER_DAY,
    DEFAULT_MAX_PER_REGISTRATION,
    DEFAULT_MAX_PER_WINDOW,
    OtpSetting,
)
from app.models.wallet_setting import WalletSetting
from app.services.providers import credentials as credentials_service

# ليبيا مرحلة تجريب: كاش فقط. الأردن: كليك وبطاقة ومحفظة، بلا تحويل P2P ولا عمولة.
FEATURE_DEFAULTS: dict[CountryCode, dict[FeatureKey, bool]] = {
    CountryCode.LY: {key: False for key in FeatureKey}
    | {
        FeatureKey.OTP_VERIFICATION_ENABLED: True,
        # **مطفأةٌ صراحةً حتى إطلاقها** (بند الإطلاق، SPEC §24): السوقُ يُبنى
        # بياناتُه وإعداداتُه كما هي، ولا يظهر في التطبيقات — لا في قائمةِ
        # اختيارٍ ولا في تسجيل. وإشعالُ هذا الصفِّ وحدَه يُظهره في اللحظة
        # نفسِها بلا بناءٍ ولا نشر.
        #
        # **وهو مكتوبٌ صريحاً وإن كان صفُّ ليبيا كلُّه `False`**: الغيابُ هنا
        # يُقرأ **ظهوراً** لا إخفاءً (`DEFAULT_ENABLED_FLAGS`)، فصفٌّ ضمنيٌّ
        # في تعبيرٍ عامٍّ ليس قراراً — والقرارُ يُكتب.
        FeatureKey.COUNTRY_VISIBLE: False,
    },
    CountryCode.JO: {
        # **ظاهرةٌ صراحةً**: السكوتُ ظهورٌ أصلاً، لكن صفّاً في اللوحة يُطفأ
        # ويُشعل أوضحُ من افتراضٍ في الكود لا زرَّ له
        FeatureKey.COUNTRY_VISIBLE: True,
        FeatureKey.CLIQ_ENABLED: True,
        FeatureKey.CARD_ENABLED: True,
        FeatureKey.WALLET_ENABLED: True,
        FeatureKey.WALLET_TRANSFER_ENABLED: False,
        # مفتاحٌ حارس: يُكتب صريحاً في الدولتين وإن كان افتراضُه مفعّلاً —
        # صفٌّ ظاهرٌ في اللوحة أوضح من افتراضٍ في الكود (المرحلة 8-ب)
        FeatureKey.OTP_VERIFICATION_ENABLED: True,
        # **مطفأةٌ صراحةً** حتى تُراجَع أجناسُ الكباتن المعتمدين المتراكمين
        # (المرحلة 10-ج): صفٌّ ظاهرٌ بقيمة false أوضح من غيابٍ يعني الشيء
        # نفسه — فالمشرف يرى المفتاح ويعرف أنه قرارٌ لا سهو
        FeatureKey.WOMEN_SERVICE_ENABLED: False,
        # **مطفأةٌ صراحةً** (البند ٥٤): لا خصمَ يُحسب ولا عرضٌ يُعرض حتى يقرّر
        # المالكُ حملتَه الأولى — وصفٌّ ظاهرٌ بقيمة false أوضح من غيابٍ يعني
        # الشيء نفسه
        FeatureKey.SUBSCRIPTION_OFFERS_ENABLED: False,
        # **مطفأٌ صراحةً** (المرحلة 12-ب): الميزةُ مبنيّةٌ كاملةً وتنتظر قرار
        # تشغيل — ورسمُ الانتظار صفرٌ حتى يضبطه المشرف، فتشغيلُ المفتاح وحده
        # يفتح المحطات بلا كلفة. وصفٌّ ظاهرٌ بقيمة false أوضح من غيابٍ يعني
        # الشيء نفسه: المشرف يرى المفتاح فيعرف أنه قرارٌ لا سهو
        FeatureKey.MULTI_STOP_ENABLED: False,
        # **مطفأٌ صراحةً** (المرحلة 12-هـ): قناةُ واتساب مبنيّةٌ كاملةً وتنتظر
        # عقداً حقيقياً — رقمَ أعمالٍ وقالبَ مصادقةٍ معتمداً بلغته. وإشعالُها
        # بلا قالبٍ معتمد يجعل كلَّ تسجيلٍ يرتدّ من ميتا، ومَن يُشعلها يجب أن
        # يرى المفتاح ويعرف أنه قرارٌ لا سهو
        FeatureKey.WHATSAPP_OTP_ENABLED: False,
        # **مطفأٌ صراحةً** (المرحلة 12-و): المبالغُ مبذورةٌ أدناه والقناةُ
        # المحفظة، والإشعالُ قرارُ تشغيلٍ يراه المشرف في الشاشة فيعرف أنه قرار
        FeatureKey.TIPS_ENABLED: False,
        # **مطفأٌ صراحةً** (المرحلة 12-ز): لا رموزَ مبذورة — الحملةُ قرارُ
        # تسويقٍ بميزانيةٍ يكتبها المشرف، وكوبونٌ يُبذر في التطوير يصير عرضاً
        # حقيقياً في الإنتاج بلا أن يقرره أحد
        FeatureKey.PROMO_CODES_ENABLED: False,
        # **مطفأٌ صراحةً** (المرحلة 12-ح): ومبلغُ الحافز صفرٌ فوقه — فالميزةُ
        # تشحن خامدةً مرتين بقرار المالك. **ولا يُربط بـ`women_service_enabled`**:
        # ذاك ينتظر تصفيةَ متراكمِ إثبات الجنس، والحافزُ هو ما يبني العرضَ الذي
        # ينتظره — فربطُهما يجعله ينتظر ما لا سبيلَ لبنائه
        FeatureKey.DRIVER_REFERRALS_ENABLED: False,
        # **ومطفآن صراحةً معه** (تعميمُ 2026-08-16). وثلاثةُ مفاتيحَ لا واحد
        # لأن قراراتِها ثلاثة: من أشعل حافزَ السائقين لأنه يبني **عرضاً** لم
        # يشعل بالضرورة حافزاً يبني **طلباً**، وكوبونُ الترحيب هو المالُ
        # الوحيد فيها الذي تتحمّله الشركةُ **عن الطرف الثاني** — فيُشعَل
        # ويُطفأ بلا مساسٍ بما وُعد به المُحيلون
        FeatureKey.RIDER_REFERRALS_ENABLED: False,
        # **مطفأٌ صراحةً** (البند ٥٣): الميزةُ تشحن خامدةً مرتين — مفتاحٌ مطفأٌ
        # و`level_settings.discount_meters` صفرٌ فوقه. ومطفأً **لا يُحسب مستوىً
        # أصلاً**، فلا تُشحن يوماً مستوياتٌ بُنيت في الظلّ على تعريفٍ لم يره أحد
        FeatureKey.DRIVER_LEVELS_ENABLED: False,
        FeatureKey.REFERRED_REWARD_ENABLED: False,
        # **مطفأٌ صراحةً** (المرحلة 12-ط): الحجزُ وعدٌ بموعد، وسوقٌ لم يُجهَّز
        # عرضُه في الساعات الهادئة يُخلف الوعدَ — فالإشعالُ قرارُ تشغيل
        FeatureKey.SCHEDULED_RIDES_ENABLED: False,
        # **مطفأٌ صراحةً** (المرحلة 12-ي): ونسبةُ الخصم صفرٌ فوقه، فتشحن
        # الميزةُ خامدةً مرتين كالبقشيش وحافزِ الإحالة. والنسبةُ قرارُ مالٍ
        # مقيَّدٌ بشرطٍ صريح — **ما يقبضه الكبتن من رحلتين أعلى بوضوحٍ مما
        # يقبضه من منفردة** — فبذرُ رقمٍ هنا يجعله يبدو قراراً ولم يُقرَّر
        FeatureKey.RIDE_SHARING_ENABLED: False,
        # **مطفأٌ صراحةً** (البند ١٥): وقرارُ المالك «سوقٌ واحدٌ أولاً — الأردن»
        # هو قرارُ **إشعال**، لا بذرٌ مُشعَل. فالبذرةُ تصف ما يشحن، والإشعالُ
        # فعلٌ يقع في اللوحة حين يُقرَّر — وسلفةٌ تُصرف في التطوير بلا قرارٍ
        # تشغيليٍّ هي **مالٌ يخرج**، لا ميزةٌ تُجرَّب
        FeatureKey.DRIVER_ADVANCES_ENABLED: False,
    },
}

# قيم مبدئية للتطوير — تُضبط نهائياً من لوحة الإدارة
PRICING_DEFAULTS: dict[tuple[CountryCode, VehicleCategory], dict[str, str]] = {
    (CountryCode.LY, VehicleCategory.ECONOMY): {
        "base_fare": "3.000",
        "price_per_km": "1.000",
        "price_per_min": "0.150",
        "minimum_fare": "5.000",
        "cancellation_fee": "2.000",
    },
    (CountryCode.LY, VehicleCategory.COMFORT): {
        "base_fare": "5.000",
        "price_per_km": "1.500",
        "price_per_min": "0.200",
        "minimum_fare": "8.000",
        "cancellation_fee": "3.000",
    },
    (CountryCode.JO, VehicleCategory.ECONOMY): {
        "base_fare": "0.800",
        "price_per_km": "0.350",
        "price_per_min": "0.050",
        "minimum_fare": "1.500",
        "cancellation_fee": "0.750",
    },
    (CountryCode.JO, VehicleCategory.COMFORT): {
        "base_fare": "1.200",
        "price_per_km": "0.500",
        "price_per_min": "0.070",
        "minimum_fare": "2.500",
        "cancellation_fee": "1.000",
    },
}

# حدود المحفظة — قيم تطوير تُضبط نهائياً من اللوحة. التحويل معطّل في
# الدولتين بمفتاحه، وهذه الحدود تنتظره جاهزة لا مفتوحة على مصراعيها.
WALLET_DEFAULTS: dict[CountryCode, dict[str, str]] = {
    CountryCode.LY: {
        "transfer_daily_limit": "500.000",
        "transfer_monthly_limit": "5000.000",
        "min_withdrawal_amount": "50.000",
    },
    CountryCode.JO: {
        "transfer_daily_limit": "200.000",
        "transfer_monthly_limit": "2000.000",
        "min_withdrawal_amount": "10.000",
    },
}

PLAN_DEFAULTS: dict[CountryCode, list[tuple[str, SubscriptionDurationType, str]]] = {
    CountryCode.LY: [
        ("اشتراك يومي", SubscriptionDurationType.DAILY, "5.000"),
        ("اشتراك أسبوعي", SubscriptionDurationType.WEEKLY, "30.000"),
        ("اشتراك شهري", SubscriptionDurationType.MONTHLY, "100.000"),
    ],
    CountryCode.JO: [
        ("اشتراك يومي", SubscriptionDurationType.DAILY, "1.500"),
        ("اشتراك أسبوعي", SubscriptionDurationType.WEEKLY, "9.000"),
        ("اشتراك شهري", SubscriptionDurationType.MONTHLY, "30.000"),
    ],
}


def _log(message: str) -> None:
    print(f"[seed] {message}")


def _resolve_path(raw_path: str) -> Path:
    """المسار النسبي يُقاس من مجلد التشغيل أولاً ثم من جذر المستودع.

    الأول يخدم الحاوية (`secrets/` مربوط عند `/app/secrets`)، والثاني تشغيلاً
    محلياً من `backend/`. وكلاهما موضعٌ معلوم لا تخمين.
    """
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return next(
        (
            candidate
            for base in (Path.cwd(), REPO_ROOT)
            if (candidate := base / raw_path).is_file()
        ),
        path,
    )


async def seed_feature_flags(session: AsyncSession) -> None:
    for country, defaults in FEATURE_DEFAULTS.items():
        for key, enabled in defaults.items():
            exists = await session.scalar(
                select(FeatureFlag.id).where(
                    FeatureFlag.country_code == country,
                    FeatureFlag.feature_key == key.value,
                )
            )
            if exists is None:
                session.add(
                    FeatureFlag(
                        country_code=country, feature_key=key.value, enabled=enabled
                    )
                )
                _log(f"مفتاح ميزة: {country.value}/{key.value} = {enabled}")


async def seed_commission(session: AsyncSession) -> None:
    for country in CountryCode:
        exists = await session.scalar(
            select(CommissionSetting.id).where(CommissionSetting.country_code == country)
        )
        if exists is None:
            # العمولة صفر ومعطّلة افتراضياً (SPEC القسم 8)
            session.add(CommissionSetting(country_code=country))
            _log(f"إعداد عمولة: {country.value} (معطّل، 0%)")


async def seed_wallet_settings(session: AsyncSession) -> None:
    """حدود التحويل والسحب — بدونها يبقى التحويل مرفوضاً ولو رُفع مفتاحه."""
    for country, limits in WALLET_DEFAULTS.items():
        exists = await session.scalar(
            select(WalletSetting.id).where(WalletSetting.country_code == country)
        )
        if exists is None:
            session.add(
                WalletSetting(
                    country_code=country,
                    **{key: Decimal(value) for key, value in limits.items()},
                )
            )
            _log(f"حدود محفظة: {country.value}")


# مبالغُ البقشيش المبدئية (المرحلة 12-و) — **قرارُ المالك**، وتُعدَّل من
# اللوحة عند التشغيل الحقيقي. وليبيا أكبرُ رقماً لأن دينارَها أصغرُ قيمةً،
# **وخدمتُها كاشٌ اليوم بلا محافظَ مشحونة** — فالأرقامُ هناك تنتظر التشغيل ولا
# تعمل حتى يُشعل المفتاحُ ومفتاحُ المحفظة معه
TIP_DEFAULTS: dict[CountryCode, dict[str, str]] = {
    CountryCode.JO: {
        "tip_preset_small": "0.500",
        "tip_preset_medium": "1.000",
        "tip_max": "5.000",
    },
    CountryCode.LY: {
        "tip_preset_small": "1.000",
        "tip_preset_medium": "2.000",
        "tip_max": "10.000",
    },
}


async def seed_payment_settings(session: AsyncSession) -> None:
    """مهلةُ تأكيد كليك ومبالغُ البقشيش لكل دولة.

    غيابُ المهلة يترك حوالاتٍ بلا موعدِ فصل، وأصفارُ البقشيش تُخفي الميزةَ حتى
    تُضبط — فالبذرُ يكتب الرقمين معاً كي لا يُشعل المشرفُ مفتاحاً فلا يجد شيئاً.
    """
    for country in CountryCode:
        exists = await session.scalar(
            select(PaymentSetting.id).where(PaymentSetting.country_code == country)
        )
        if exists is None:
            amounts = {
                key: Decimal(value) for key, value in TIP_DEFAULTS[country].items()
            }
            session.add(PaymentSetting(country_code=country, **amounts))
            _log(
                f"سياسات دفع: {country.value} "
                f"(مهلة تأكيد كليك {DEFAULT_CLIQ_CONFIRMATION_HOURS} ساعة، "
                f"بقشيش {amounts['tip_preset_small']}/{amounts['tip_preset_medium']} "
                f"بسقف {amounts['tip_max']})"
            )


async def seed_sharing_settings(session: AsyncSession) -> None:
    """إعداداتُ المشاركة لكل دولة — **الخصمُ صفرٌ حتى يقرّره المالك** (12-ي).

    ويُبذر الصفُّ وإن كانت قيمُه هي الافتراضات، لنفس سببِ بذر حافز الإحالة:
    بغيره لا تجد شاشةُ اللوحة صفاً تعدّله فيبدو الحقلُ عطباً لا «لم يُحدَّد».
    وأرقامُ المطابقة الثلاثة تُبذر بقيمٍ عاملة — فهي **تشغيليةٌ لا مالية**،
    وصفرُها يعني ممرّاً بلا عرضٍ فلا يُطابَق أحدٌ أبداً.
    """
    for country in CountryCode:
        exists = await session.scalar(
            select(RideSharingSetting.id).where(
                RideSharingSetting.country_code == country
            )
        )
        if exists is None:
            session.add(RideSharingSetting(country_code=country))
            _log(
                f"مشاركة الرحلة: {country.value} "
                f"(الخصم {DEFAULT_DISCOUNT_PERCENT}% — لم يُحدَّد بعد، "
                f"وممرّ {DEFAULT_CORRIDOR_KM}كم والتفاف {DEFAULT_MAX_DETOUR_MINUTES}د)"
            )


async def seed_otp_settings(session: AsyncSession) -> None:
    """سقوفُ طلب رمز التحقق لكل دولة (قرارُ المالك 2026-08-16).

    **وقيمُها الافتراضيةُ حارسةٌ لا مفتوحة** — عكسُ أصفار البقشيش والإحالة:
    تلك ميزاتٌ لا تُفتح بالسكوت، وهذه حرّاسٌ لا تُطفأ به. والصفُّ يُبذر ليجد
    المشرفُ أرقاماً في شاشته لا حقولاً فارغةً تُقرأ عطباً.
    """
    for country in CountryCode:
        exists = await session.scalar(
            select(OtpSetting.country_code).where(
                OtpSetting.country_code == country
            )
        )
        if exists is None:
            session.add(OtpSetting(country_code=country))
            _log(
                f"سقوف الرمز: {country.value} "
                f"({DEFAULT_MAX_PER_WINDOW} في النافذة، "
                f"{DEFAULT_MAX_PER_DAY} يومياً، "
                f"{DEFAULT_MAX_PER_REGISTRATION} لتسجيلٍ واحد)"
            )


async def seed_cancellation_settings(session: AsyncSession) -> None:
    """سياسةُ رسم الإلغاء لكل دولة (`design/CANCELLATION-FEE.md`).

    ويُبذر الصفُّ وإن كانت قيمُه هي الافتراضات، كصفِّ سياسة السلف: بغيره تجد
    شاشةُ اللوحة حقولاً فارغةً تُقرأ عطباً لا «لم يُحدَّد بعد».

    **وأصفارُه الثلاثةُ مقصودة**: لا إيقافَ عند التكرار، ولا مهلةَ للحامل، ولا
    إجراءَ على دَينٍ قديم — «لم يُضبط بعد» حتى يقرّر المالك، كأصفار البقشيش
    والإحالة والمشاركة. **وحدَه الإعفاءُ بالقرب مفعَّلٌ افتراضاً** (٣٠٠ متراً)
    لأنه حارسٌ في صالح من سيُخصم منه، وسكوتُه يُحصِّل بلا شرطٍ راجعه أحد.
    """
    for country in CountryCode:
        exists = await session.scalar(
            select(CancellationSetting.country_code).where(
                CancellationSetting.country_code == country
            )
        )
        if exists is None:
            session.add(CancellationSetting(country_code=country))
            _log(
                f"سياسة إلغاء: {country.value} "
                f"(إعفاءٌ دون {DEFAULT_EXEMPT_WITHIN_METERS} متراً، "
                "ولا إيقافَ ولا مهلةَ حاملٍ ولا إجراءَ على دَينٍ قديم)"
            )


async def seed_advance_settings(session: AsyncSession) -> None:
    """سياسةُ السلف لكل دولة — بافتراضاتها، **ونموُّ السقف صفرٌ** (البند ١٥).

    ويُبذر الصفُّ وإن كانت قيمُه هي الافتراضات، كصفِّ حافز الإحالة: بغيره تجد
    شاشةُ اللوحة حقولاً فارغةً تُقرأ عطباً لا «لم يُحدَّد بعد».

    **وصفرُ النموِّ يعني «تبقى عند قيمة الاشتراك اليومي»** — وهو الحدُّ الذي
    يجعل أسوأَ خسارةٍ ممكنةٍ اشتراكاً يومياً واحداً: «الحمايةُ في الحجم لا في
    التحصيل» (قرارُ المالك ٧). ورفعُه قرارٌ يُتخذ بعد أن تُسدَّد سلفٌ فعلاً.
    """
    for country in CountryCode:
        exists = await session.scalar(
            select(AdvanceSetting.id).where(AdvanceSetting.country_code == country)
        )
        if exists is None:
            session.add(AdvanceSetting(country_code=country))
            _log(
                f"سياسة سلف: {country.value} "
                f"(اقتطاع {DEFAULT_DEDUCTION_PERCENT}٪، "
                f"مهلة {DEFAULT_TERM_DAYS} يوماً، ولا نموّ للسقف)"
            )


async def seed_referral_settings(session: AsyncSession) -> None:
    """حافزُ الإحالة لكل دولة — **صفرٌ وثلاثُ رحلات** (قرارُ المالك 2026-08-12).

    ويُبذر الصفُّ وإن كانت قيمُه هي الافتراضات: بغيره لا تجد شاشةُ اللوحة صفاً
    تعدّله، فيبدو الحقلُ فارغاً كأنه عطبٌ لا كأنه «لم يُحدَّد بعد». وصفرُ
    المبلغ يمنع كتابةَ أي قيد — الآليةُ تعمل والمالُ ينتظر قرارَه.
    """
    for country in CountryCode:
        exists = await session.scalar(
            select(ReferralSetting.id).where(ReferralSetting.country_code == country)
        )
        if exists is None:
            session.add(ReferralSetting(country_code=country))
            _log(
                f"حافز إحالة: {country.value} "
                f"(المبلغ {DEFAULT_REWARD_AMOUNT} — لم يُحدَّد بعد، "
                f"وشرطُه {DEFAULT_REQUIRED_RIDES} رحلات)"
            )


async def seed_notification_settings(session: AsyncSession) -> None:
    """ساعاتُ الهدوء لكل دولة — بغيرها تُنشر `null` وتصمت اللوحة عن قاعدةٍ
    تحكم متى تصل الحملات فعلاً."""
    for country in CountryCode:
        await campaigns.get_or_create_settings(session, country)
        _log(f"ساعات هدوء: {country.value}")


async def seed_pricing(session: AsyncSession) -> None:
    for (country, category), amounts in PRICING_DEFAULTS.items():
        exists = await session.scalar(
            select(PricingRule.id).where(
                PricingRule.country_code == country,
                PricingRule.vehicle_category == category,
            )
        )
        if exists is None:
            session.add(
                PricingRule(
                    country_code=country,
                    vehicle_category=category,
                    **{key: Decimal(value) for key, value in amounts.items()},
                )
            )
            _log(f"تسعيرة: {country.value}/{category.value}")


async def seed_plans(session: AsyncSession) -> None:
    for country, plans in PLAN_DEFAULTS.items():
        for name, duration, price in plans:
            exists = await session.scalar(
                select(SubscriptionPlan.id).where(
                    SubscriptionPlan.country_code == country,
                    SubscriptionPlan.name == name,
                )
            )
            if exists is None:
                session.add(
                    SubscriptionPlan(
                        country_code=country,
                        name=name,
                        duration_type=duration,
                        price=Decimal(price),
                        currency=currency_for_country(country),
                    )
                )
                _log(f"خطة اشتراك: {country.value}/{name}")


async def seed_providers(session: AsyncSession) -> None:
    """يكتب عقود Mapbox وTelr من البيئة — مشفّرة — إن لم تكن محفوظة."""
    public_token = os.environ.get("MAPBOX_PUBLIC_TOKEN", "").strip()
    secret_token = os.environ.get("MAPBOX_SECRET_TOKEN", "").strip()

    if public_token and secret_token:
        existing = await credentials_service.get_credential(session, ProviderKey.MAPBOX)
        if existing is None:
            await credentials_service.upsert(
                session,
                provider_key=ProviderKey.MAPBOX,
                country_code=None,
                values={"public_token": public_token, "secret_token": secret_token},
                is_active=True,
                actor=None,
            )
            _log("عقد Mapbox: محفوظ ومفعّل")
    else:
        _log("تخطّي Mapbox — MAPBOX_PUBLIC_TOKEN/MAPBOX_SECRET_TOKEN غير معبّأين")

    store_id = os.environ.get("TELR_STORE_ID", "").strip()
    auth_key = os.environ.get("TELR_AUTH_KEY", "").strip()
    # مزودٌ وهمي حتى يصل حساب Sandbox (SPEC القسم 15): يشغّل مسار البطاقة كاملاً
    # بلا شبكة. **صريحٌ لا افتراضي**: قناةُ دفعٍ لا تُفتَح بالسكوت، ولا يُفعَّل
    # مزودٌ يقول «دُفع» بلا مال إلا بطلب صاحب البيئة.
    use_mock = os.environ.get("TELR_USE_MOCK", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    if not (store_id and auth_key) and not use_mock:
        _log("تخطّي Telr — TELR_STORE_ID/TELR_AUTH_KEY غير معبّأين (وTELR_USE_MOCK مطفأ)")
        return

    existing = await credentials_service.get_credential(
        session, ProviderKey.TELR, CountryCode.JO
    )
    if existing is not None:
        return

    # تفعيله يرفع card_enabled للأردن تلقائياً
    await credentials_service.upsert(
        session,
        provider_key=ProviderKey.TELR,
        country_code=CountryCode.JO,
        values={
            # قيمتان لازمتان في العقد حتى مع المزود الوهمي: الحقلان مطلوبان في
            # سجل المزود، ومطابقةُ الـ webhook تقع على `store_id`
            "store_id": store_id or "mock-store",
            "auth_key": auth_key or "mock-auth-key",
            "test_mode": True,
            "use_mock": use_mock,
        },
        is_active=True,
        actor=None,
    )
    _log(
        "عقد Telr (الأردن): محفوظ ومفعّل — "
        + ("مزود وهمي" if use_mock else "Sandbox")
    )


async def seed_fcm(session: AsyncSession) -> None:
    """يكتب عقد FCM من **مسار** ملف حساب الخدمة — مشفَّراً — إن لم يكن محفوظاً.

    مسارٌ في البيئة لا محتوى: مفتاحُ RSA من ألفٍ وسبعمئة حرفٍ لا يُلصق في ملف
    بيئة، والملفُّ نفسه في `secrets/` المُستثنى من Git. وما إن يُقرأ حتى يُكتب
    مشفَّراً في `provider_credentials` ولا يُقرأ من القرص ثانيةً — نفس ما يفعله
    الـ seed بتوكنات Mapbox (SPEC القسم 14).

    و`use_mock` مطفأ صراحةً: العقد الحقيقي موجود، فلا معنى لمزودٍ وهمي بعده.
    """
    raw_path = os.environ.get("FCM_SERVICE_ACCOUNT_PATH", "").strip()
    if not raw_path:
        _log("تخطّي FCM — FCM_SERVICE_ACCOUNT_PATH غير معبّأ")
        return

    path = _resolve_path(raw_path)
    if not path.is_file():
        _log(f"تخطّي FCM — لا ملف حساب خدمة عند {path}")
        return

    try:
        account = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        _log(f"تخطّي FCM — الملف عند {path} ليس JSON صالحاً")
        return

    project_id = str(account.get("project_id") or "").strip()
    if not project_id or not account.get("private_key"):
        _log("تخطّي FCM — الملف ناقص project_id أو private_key")
        return

    if await credentials_service.get_credential(session, ProviderKey.FCM) is not None:
        return

    await credentials_service.upsert(
        session,
        provider_key=ProviderKey.FCM,
        country_code=None,
        values={
            "project_id": project_id,
            # النصُّ كما هو: `parse_service_account` يفكّه عند الإرسال
            "service_account_json": path.read_text(encoding="utf-8"),
            "use_mock": False,
        }
        | _firebase_web_config(sender=True),
        is_active=True,
        actor=None,
    )
    _log(f"عقد FCM: محفوظ ومفعّل — مشروع {project_id} (بلا مزود وهمي)")


def _firebase_web_config(*, sender: bool) -> dict[str, str]:
    """إعدادُ تطبيق الويب العام — تحتاجه الواجهة لا الخلفية (المرحلة 9).

    قيمٌ عامّةٌ بطبيعتها تُنشر في حزمة كل تطبيق ويب يستعمل Firebase، لكنها قيمُ
    مشروعٍ بعينه — فمكانها العقد لا ملفُّ إعداداتٍ في الواجهة (SPEC القسم 14).
    وغيابُها لا يعطّل شيئاً في الخلفية: تُدخل من صفحة العقود متى وُجد تطبيق.

    `sender=True` لعقد FCM وحده: معرّف المُرسل ومفتاح VAPID لا معنى لهما في
    عقد الدخول.
    """
    keys = {
        "api_key": "FIREBASE_WEB_API_KEY",
        "auth_domain": "FIREBASE_WEB_AUTH_DOMAIN",
        "app_id": "FIREBASE_WEB_APP_ID",
    }
    if sender:
        keys = {
            "api_key": "FIREBASE_WEB_API_KEY",
            "app_id": "FIREBASE_WEB_APP_ID",
            "sender_id": "FIREBASE_WEB_SENDER_ID",
            "vapid_key": "FIREBASE_WEB_VAPID_KEY",
        }

    values = {
        field: os.environ.get(variable, "").strip()
        for field, variable in keys.items()
    }
    return {field: value for field, value in values.items() if value}


async def seed_firebase_auth(session: AsyncSession) -> None:
    """يكتب عقد Firebase للتحقق من الهاتف — عقدٌ مستقل عن `fcm`.

    **معرّف المشروع يُشتق من ملف حساب الخدمة نفسه** ما لم يُذكر صراحةً في
    `FIREBASE_AUTH_PROJECT_ID`: المشروع واحد في الحالة الشائعة، ومتغيرُ بيئةٍ
    ثانٍ يحمل نفس القيمة قيمتان تفترقان يوماً. والعقدان يبقيان مستقلَّين في
    القاعدة على أي حال — إطفاءُ الإشعارات لا يُطفئ الدخول.

    ولا يحتاج هذا العقد سرّاً: التحقق من رمز الهوية يجري بمفاتيح Google
    العامة، فالمخزَّن معرِّفٌ عام لا غير.
    """
    project_id = os.environ.get("FIREBASE_AUTH_PROJECT_ID", "").strip()

    if not project_id:
        raw_path = os.environ.get("FCM_SERVICE_ACCOUNT_PATH", "").strip()
        path = _resolve_path(raw_path) if raw_path else None
        if path is not None and path.is_file():
            try:
                project_id = str(
                    json.loads(path.read_text(encoding="utf-8")).get("project_id") or ""
                ).strip()
            except ValueError:
                project_id = ""

    if not project_id:
        _log("تخطّي Firebase Auth — لا FIREBASE_AUTH_PROJECT_ID ولا ملف حساب خدمة")
        return

    if (
        await credentials_service.get_credential(session, ProviderKey.FIREBASE_AUTH)
        is not None
    ):
        return

    await credentials_service.upsert(
        session,
        provider_key=ProviderKey.FIREBASE_AUTH,
        country_code=None,
        values={"project_id": project_id, "use_mock": False}
        | _firebase_web_config(sender=False),
        is_active=True,
        actor=None,
    )
    _log(
        f"عقد Firebase Auth: محفوظ ومفعّل — مشروع {project_id}. "
        "الدخول صار برمز هوية Firebase"
    )


async def seed_bootstrap_admin(session: AsyncSession) -> None:
    """حساب المشرف الأول — بدونه لا يمكن الوصول للوحة أصلاً.

    التسجيل الذاتي مقصور على الركاب والكباتن، ولا يُنشأ هذا الحساب في الإنتاج:
    هناك يُنشأ يدوياً بكلمة مرور لا تمر من ملف بيئة.
    """
    phone_raw = os.environ.get("BOOTSTRAP_ADMIN_PHONE", "").strip()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "").strip()

    if not phone_raw or not password:
        _log("تخطّي حساب المشرف — BOOTSTRAP_ADMIN_PHONE/PASSWORD غير معبّأين")
        return
    if settings.is_production:
        _log("تخطّي حساب المشرف — ممنوع في بيئة الإنتاج")
        return

    country = CountryCode(os.environ.get("BOOTSTRAP_ADMIN_COUNTRY", "JO"))
    phone = normalize_phone(phone_raw, country)

    exists = await session.scalar(select(User.id).where(User.phone == phone))
    if exists is not None:
        _log(f"حساب المشرف موجود: {phone}")
        return

    # **والدورُ يُكتب في المجموعة معه** (نموذجُ الأدوار): البذرةُ بابُ إنشاءٍ
    # ثانٍ لا يمرّ بـ`create_account`، وحسابٌ بلا صفِّ دورٍ يعتمد على ضمِّ
    # العمود في `has_role_clause` — وهو حارسُ فقدٍ لا مكانٌ يُقصد
    session.add(
        User(
            phone=phone,
            name=os.environ.get("BOOTSTRAP_ADMIN_NAME", "مشرف").strip() or "مشرف",
            role=UserRole.ADMIN,
            country_code=country,
            password_hash=hash_password(password),
            role_grants=[UserRoleGrant(role=UserRole.ADMIN)],
        )
    )
    _log(f"حساب المشرف: {phone}")


async def main() -> None:
    async with SessionLocal() as session:
        await seed_feature_flags(session)
        await seed_commission(session)
        await seed_pricing(session)
        await seed_wallet_settings(session)
        await seed_payment_settings(session)
        await seed_referral_settings(session)
        await seed_advance_settings(session)
        await seed_cancellation_settings(session)
        await seed_otp_settings(session)
        await seed_sharing_settings(session)
        await seed_notification_settings(session)
        await seed_plans(session)
        await seed_providers(session)
        await seed_fcm(session)
        await seed_firebase_auth(session)
        await seed_bootstrap_admin(session)
        await session.commit()
    await engine.dispose()
    _log("تم.")


if __name__ == "__main__":
    asyncio.run(main())
