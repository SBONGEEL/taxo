from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission import CommissionSetting
from app.models.enums import AuditAction, CountryCode, FeatureKey
from app.models.feature_flag import FeatureFlag
from app.models.payment_setting import PaymentSetting
from app.models.user import User
from app.models.wallet_setting import WalletSetting
from app.services import audit

# **الاستثناء الوحيد لقاعدة «غياب الصف = معطّل»** (SPEC القسم 4).
#
# القاعدة الأصلية تحرس من أن تُفتح ميزةٌ ماليةٌ بالسكوت. وهذه المفاتيح ليست
# ميزاتٍ تُفتح بل **حرّاساً يُطفأون**: غيابُ صفّها يعني «لم يقرر أحدٌ إطفاءه»،
# وقراءتُه معطّلاً تُسقط الحارس بلا قرار — وهو نقيضُ ما وُضعت القاعدة له.
# القائمة مقصورةٌ على ما إطفاؤه أخطرُ من تفعيله، ولا يُضاف إليها مفتاح ميزة.
DEFAULT_ENABLED_FLAGS: frozenset[str] = frozenset(
    {
        FeatureKey.OTP_VERIFICATION_ENABLED.value,
        # **وظهورُ الدولة، وهو ليس ميزةً ولا حارساً بل صفةُ سوق.** لو قُرئ
        # الغيابُ إخفاءً لاختفت كلُّ دولةٍ على تثبيتٍ لم يُبذر — تطبيقٌ بلا
        # دولةٍ واحدة، ولا شاشةَ دخولٍ تُرسم. فالإخفاءُ صفٌّ صريحٌ يكتبه إنسان.
        FeatureKey.COUNTRY_VISIBLE.value,
        # **وحارسا المال** (2026-08-23): صفٌّ غائبٌ يجب أن يُقرأ «يعمل»، وإلا
        # أوقف أوّلُ تنصيبٍ غيرِ مبذورٍ التسعيرَ والصرفَ معاً — وهو بعينه ما
        # تمنعه علّةُ هذه القائمة: السكوتُ لا يُسقط حارساً ولا يُوقف نظاماً.
        FeatureKey.PRICING_WRITES_ENABLED.value,
        FeatureKey.WITHDRAWAL_PAYOUT_ENABLED.value,
    }
)

# **والسببُ المكتوب مجموعةٌ ثانيةٌ، لا هذه** (2026-08-19). كانتا واحدةً لأن
# عضوَها كان واحداً، فبدا «السكوتُ يُشعل» و«الإطفاءُ يحتاج سبباً» صفةً واحدة —
# وهما مفهومان: الأولُ **كيف يُقرأ الغياب**، والثاني **ما ثمنُ الإطفاء**.
#
# فرّقهما دخولُ `country_visible`: سكوتُه ظهورٌ لأنه صفةُ سوق، وإخفاءُ سوقٍ
# **قرارُ إطلاقٍ لا إجراءُ طوارئ** — ولو ورث الشرطَ لطالب المالكَ بسببٍ مكتوبٍ
# ورسالتُه تقول «مفتاح التحقق»، وهي جملةٌ لا علاقةَ لها بما ضغط.
GUARDED_FLAGS: frozenset[str] = frozenset(
    {
        FeatureKey.OTP_VERIFICATION_ENABLED.value,
        # **وإطفاءُ حارسِ مالٍ قرارٌ يُسأل عنه بعد شهر**: «من جمّد التسعير
        # ولماذا؟» سؤالٌ يُطرح، والسببُ المكتوب هو جوابُه الوحيد — وهو
        # الاستثناءُ المصرَّحُ به من «التدقيقُ يحمل أسماءَ الحقول لا قيمَها».
        FeatureKey.PRICING_WRITES_ENABLED.value,
        FeatureKey.WITHDRAWAL_PAYOUT_ENABLED.value,
    }
)


def default_for(feature_key: FeatureKey | str) -> bool:
    key = feature_key.value if isinstance(feature_key, FeatureKey) else feature_key
    return key in DEFAULT_ENABLED_FLAGS


async def get_flags(session: AsyncSession, country_code: CountryCode) -> dict[str, bool]:
    """كل المفاتيح المعروفة للدولة — الغائب منها معطّل.

    لا نفترض التفعيل أبداً عند غياب الصف (SPEC: ليبيا كاش فقط).
    """
    rows = (
        await session.scalars(
            select(FeatureFlag).where(FeatureFlag.country_code == country_code)
        )
    ).all()
    flags = {key.value: default_for(key) for key in FeatureKey}
    flags.update({row.feature_key: row.enabled for row in rows})
    return flags


async def is_feature_enabled(
    session: AsyncSession, country_code: CountryCode, feature_key: FeatureKey | str
) -> bool:
    key = feature_key.value if isinstance(feature_key, FeatureKey) else feature_key
    enabled = await session.scalar(
        select(FeatureFlag.enabled).where(
            FeatureFlag.country_code == country_code, FeatureFlag.feature_key == key
        )
    )
    if enabled is None:
        return default_for(key)
    return bool(enabled)


async def set_flag(
    session: AsyncSession,
    *,
    country_code: CountryCode,
    feature_key: FeatureKey | str,
    enabled: bool,
    actor: User | None = None,
    reason: str | None = None,
) -> FeatureFlag:
    """ينشئ المفتاح أو يحدّثه. الـ commit مسؤولية المستدعي."""
    key = feature_key.value if isinstance(feature_key, FeatureKey) else feature_key
    flag = await session.scalar(
        select(FeatureFlag).where(
            FeatureFlag.country_code == country_code, FeatureFlag.feature_key == key
        )
    )

    if flag is None:
        flag = FeatureFlag(country_code=country_code, feature_key=key, enabled=enabled)
        session.add(flag)
        await session.flush()
        action = AuditAction.CREATE
    elif flag.enabled != enabled:
        flag.enabled = enabled
        action = AuditAction.UPDATE
    else:
        return flag

    details: dict[str, object] = {
        "country_code": CountryCode(country_code).value,
        "feature_key": key,
        "enabled": enabled,
    }
    if reason:
        details["reason"] = reason
    await audit.record(
        session,
        actor=actor,
        action=action,
        entity_type="feature_flag",
        entity_id=flag.id,
        details=details,
    )
    return flag


async def commission_percent_for(
    session: AsyncSession, country_code: CountryCode
) -> Decimal:
    """النسبة السارية الآن — صفر ما لم يكن `commission_enabled` مرفوعاً.

    قراءة فقط: طلبُ رحلة لا يجوز أن يُنشئ صف إعدادات. تقرأها المرحلة 3 مرة
    واحدة لتُجمّدها في `rides.commission_percent_at_ride`؛ نطاق التطبيق
    (`applies_to`) يُقيَّم لحظة الدفع في المرحلة 6.
    """
    setting = await session.scalar(
        select(CommissionSetting).where(CommissionSetting.country_code == country_code)
    )
    if setting is None or not setting.commission_enabled:
        return Decimal("0.00")
    return setting.commission_percent


async def get_or_create_commission(
    session: AsyncSession, country_code: CountryCode
) -> CommissionSetting:
    """إعداد عمولة الدولة — يُنشأ معطّلاً بنسبة صفر إن لم يوجد (SPEC القسم 8)."""
    setting = await session.scalar(
        select(CommissionSetting).where(CommissionSetting.country_code == country_code)
    )
    if setting is None:
        setting = CommissionSetting(country_code=country_code)
        session.add(setting)
        await session.flush()
    return setting


async def get_payment_settings(
    session: AsyncSession, country_code: CountryCode
) -> PaymentSetting | None:
    """قراءة فقط — مسار قراءةٍ لا يجوز أن يكتب صف إعدادات."""
    return await session.scalar(
        select(PaymentSetting).where(PaymentSetting.country_code == country_code)
    )


async def get_or_create_payment_settings(
    session: AsyncSession, country_code: CountryCode
) -> PaymentSetting:
    """سياساتُ الدفع للدولة — تُنشأ بمهلة التأكيد الافتراضية (القسم 6.2).

    وهنا **لا يصلح الصفر افتراضاً** كما في حدود المحفظة: صفرُ ساعاتٍ يعني
    نزاعاً فورياً على كل حوالة، والسكوتُ لا يجوز أن يُنتج ذلك — فالافتراض
    قيمةٌ صريحة في `models/payment_setting.py`.
    """
    setting = await session.scalar(
        select(PaymentSetting).where(PaymentSetting.country_code == country_code)
    )
    if setting is None:
        setting = PaymentSetting(country_code=country_code)
        session.add(setting)
        await session.flush()
    return setting


async def get_wallet_settings(
    session: AsyncSession, country_code: CountryCode
) -> WalletSetting | None:
    """قراءة فقط — مسار قراءةٍ لا يجوز أن يكتب صف إعدادات."""
    return await session.scalar(
        select(WalletSetting).where(WalletSetting.country_code == country_code)
    )


async def get_or_create_wallet_settings(
    session: AsyncSession, country_code: CountryCode
) -> WalletSetting:
    """حدود محفظة الدولة — تُنشأ بأصفار إن لم توجد (SPEC القسم 7/9).

    الصفر هنا «لم يُضبط بعد» ويمنع التحويل، لا «حدٌّ مقداره صفر»: قيمةٌ مالية
    غائبة لا يجوز أن يخترع لها الكودُ افتراضاً سخياً.
    """
    setting = await session.scalar(
        select(WalletSetting).where(WalletSetting.country_code == country_code)
    )
    if setting is None:
        setting = WalletSetting(country_code=country_code)
        session.add(setting)
        await session.flush()
    return setting
