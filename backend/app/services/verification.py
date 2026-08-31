"""إثبات ملكية رقم الهاتف — **تحقّقٌ لا دخول** (المرحلة 8-ب، ثم 12-هـ).

هذا هو التحوّل الذي أعاد ترتيب طبقة المصادقة كلها: OTP لم يعد طريقةَ دخول
بل **حدثاً يقع مرتين في عمر الحساب**:

1. **عند التسجيل** — مرةً واحدة، ثم يضع صاحبه كلمة مروره ويدخل بها بعدها.
2. **عند استعادة كلمة المرور** — لأن استعادةً بلا إثبات ملكيةٍ للرقم ليست
   استعادة بل استيلاء.

والدخول اليومي **كلمة مرور دائماً ولكل المستخدمين** (`services/auth`).

**لماذا حُذفت `OtpAuthStrategy` كطريقة دخول ولم يُحذف كودُها؟** لأن مزود SMS
التقليدي لم يمت — تغيّر دورُه. كان بديلاً للدخول فصار **مُحقِّقاً**: حيث لا
يعمل Firebase (أو حيث عقدٌ محليٌّ أرخص) يبقى `services/otp.py` بكامله —
توليدُ الرمز وبصمتُه وعدّادُ المحاولات ومهلةُ الإرسال — يخدم نفس الحدثين.
أما إبقاؤه طريقةَ دخولٍ ثانية فكان يعني جوابين متناقضين لسؤال «كيف أدخل»،
وحساباتٍ أُنشئت تحت أحدهما لا تعمل تحت الآخر.

**نقطة القرار في التحقق لا في الدخول**، وترتيبها بعد المرحلة 12-هـ:
`whatsapp_otp` ← `sms_otp` ← `firebase` ← لا مُحقِّق. ومفتاح
`otp_verification_enabled` يعلوها جميعاً **في التسجيل وحده** — ولا يمسّ
الاستعادة أبداً.

**والترتيبُ تبدّل بقرار المالك** (كان Firebase أولاً، وكانت حجّتُه أنه الأقوى
إثباتاً والأرخص تشغيلاً): واتساب أوثقُ وصولاً في السوقين — لا شريحةَ تُبدَّل ولا
رسالةٌ تضيع في بوابةٍ محلية، والناسُ يقرؤونه أولاً. **وتبعتُه صريحة**: عقدُ
Firebase مفعّلاً لا يُستعمل ما دام قبله عقدٌ مفعّل، فمن أراده يُطفئ ما قبله.
والترتيبُ ثابتٌ في الكود لا يُقرأ من إعداد: مفتاحٌ يقول «أيُّها أولاً» حالةٌ
ثانية تختلف يوماً عن حالة العقود نفسها.

**والقناةُ الأولى وحدها تُختار تلقائياً؛ وما بعدها يُطلب صراحةً.** فشلُ إرسالِ
واتساب لا يُبدّل القناةَ في صمت: الرمزُ ربما وصل فعلاً، وتبديلٌ صامتٌ يجعل
صاحبَه يقرأ رمزاً من قناةٍ ويكتب رمزاً من أخرى فيُحرق الرمزان. فيُرفع
`VerificationSendFailed` حاملاً **القناةَ التالية المتاحة**، والواجهةُ ترسم
زرَّها — رفضٌ بلا مخرجٍ ليس رفضاً.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.phone import country_for_phone
from app.models.enums import CountryCode, FeatureKey, ProviderKey
from app.models.user import User
from app.services import otp, settings_service
from app.models.enums import VerificationMethod as VerificationMethodEnum
from app.models.otp_template import OtpTemplatePurpose

# ما تراه الواجهة فتعرف أيَّ تدفّقٍ ترسم
VerificationMethod = Literal["firebase", "sms_otp", "whatsapp_otp", "none"]

# **من التعداد لا من سلاسلَ هنا** (2026-08-30): القيمُ هي هي حرفاً، غير أنّ
# `check:enums` لا يقرأ إلا `models/enums.py` — فثوابتُ وحدةٍ تجعله يقرأ مرآةَ
# التطبيقين الصادقةَ قيماً مخترعة.
FIREBASE = VerificationMethodEnum.FIREBASE.value
SMS_OTP = VerificationMethodEnum.SMS_OTP.value
WHATSAPP_OTP = VerificationMethodEnum.WHATSAPP_OTP.value
EMAIL_OTP = VerificationMethodEnum.EMAIL_OTP.value
NONE = VerificationMethodEnum.NONE.value

# القنواتُ التي نولّد فيها الرمز ونرسله نحن — يخدمها `services/otp.py`.
# وFirebase ليست منها: الرسالةُ تُرسل من جهاز المستخدم ولا رمزَ عندنا أصلاً
CODE_CHANNELS: tuple[str, ...] = (WHATSAPP_OTP, SMS_OTP)


class VerificationUnavailable(AppError):
    """التحقق مطلوب ولا مُحقِّق مُهيأ — عقدٌ ناقص لا خطأُ مستخدم.

    503 صريحة عمداً بدل السماح بالمرور: «لا حساب يُنشأ برقم غير محقق» قاعدةٌ
    لا تُخرق لأن العقد غائب. ومخرجُها إداري: أدخل عقد واتساب أو Firebase أو
    عقد SMS، أو أطفئ `otp_verification_enabled` للطوارئ وأنت تعرف ما تفعل.
    """

    status_code = 503
    code = "verification_unavailable"
    message = "التحقق من رقم هاتفك غير متاح حالياً. حاول بعد قليل."


class ChannelUnavailable(AppError):
    """قناةٌ طُلبت صراحةً وليست متاحةً لهذا الرقم.

    400 لا 503: المطلوبُ خاطئ لا النظامُ معطَّل. وتُرفض ولا تُستبدل بالمتاح —
    طلبٌ يُنفَّذ في قناةٍ غير المطلوبة أسوأ من طلبٍ يُرفض بوضوح.
    """

    status_code = 400
    code = "verification_channel_unavailable"
    message = "قناة التحقق المطلوبة غير متاحة لهذا الرقم"


class VerificationSendFailed(AppError):
    """تعذّر إيصالُ الرمز في القناة المختارة — **ومعه المخرج**.

    502 لأن العطل عند مزودٍ خارجي لا في مدخلات المستخدم. و`fallback_channel`
    في جسم الخطأ هو ما يجعل الرفضَ ذا مخرج: الواجهةُ ترسم زرَّ القناة التالية
    بدل أن تُعلّق صاحبَ الرقم أمام رسالةٍ لا تفعل شيئاً. وغيابُه (`null`) جوابٌ
    صادقٌ أيضاً — لا قناةَ أخرى مهيأة، ومكانُ إصلاحه صفحةُ العقود لا هذه الشاشة.
    """

    status_code = 502
    code = "verification_send_failed"
    message = "تعذّر إرسال رمز التحقق"

    def __init__(
        self,
        *,
        channel: str,
        fallback: str | None,
        detail: str | None = None,
        reason: str = "channel_down",
    ) -> None:
        super().__init__(detail or self.message)
        # **`reason` يفرّق ما كان النصُّ وحدَه يفرّقه** (2026-08-31):
        # `not_on_channel` خبرٌ عن الوجهة يخصّ صاحبَها، و`channel_down` عطبٌ
        # عندنا. **ومطابقةُ نصٍّ عربيٍّ ليست عقداً** — تنكسر بأول تحرير.
        self.extra = {
            "channel": channel,
            "fallback_channel": fallback,
            "reason": reason,
        }


class PhoneNotVerified(AppError):
    """إجراءٌ يشترط رقماً مُثبتاً على حسابٍ لم يُثبَّت رقمه."""

    status_code = 403
    code = "phone_not_verified"
    message = "يجب إثبات ملكية رقم الهاتف أولاً"


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------- من يُحقِّق


async def available_methods(
    session: AsyncSession, country_code: CountryCode | None = None
) -> list[VerificationMethod]:
    """المُحقِّقون المُهيأون **بترتيب الأولوية** — وأوّلُهم هو المُختار تلقائياً.

    وواتساب يشترط **العقدَ والمفتاحَ معاً**: العقدُ عامٌّ (رقمُ أعمالٍ واحد عند
    ميتا يخدم السوقين) والمفتاحُ per-country — فالعقدُ يقول «نستطيع» والمفتاحُ
    يقول «نفعل في هذا السوق». **وبلا دولةٍ معروفة لا تُعرض القناة**: مفتاحٌ
    per-country لا يُقرأ بلا دولة، و«افترض الدولةَ الافتراضية» يجعل سوقاً يُرسل
    بقناةٍ أُطفئت فيه.
    """
    from app.services.firebase_auth import firebase_auth_enabled
    from app.services.providers.credentials import provider_is_active

    methods: list[VerificationMethod] = []

    if (
        country_code is not None
        and await settings_service.is_feature_enabled(
            session, country_code, FeatureKey.WHATSAPP_OTP_ENABLED
        )
        and await provider_is_active(session, ProviderKey.WHATSAPP)
    ):
        methods.append(WHATSAPP_OTP)

    if await provider_is_active(session, ProviderKey.SMS):
        methods.append(SMS_OTP)
    if await firebase_auth_enabled(session):
        methods.append(FIREBASE)

    return methods


async def active_method(
    session: AsyncSession, country_code: CountryCode | None = None
) -> VerificationMethod:
    """المُحقِّق المُختار الآن — بصرف النظر عن `otp_verification_enabled`."""
    methods = await available_methods(session, country_code)
    return methods[0] if methods else NONE


async def method_for_phone(
    session: AsyncSession, phone: str
) -> tuple[VerificationMethod, list[VerificationMethod]]:
    """(المُختار، المتاحون) لرقمٍ بصيغة E.164 — والدولةُ تُشتق من الرقم نفسه.

    فحيث يوجد الرقم لا يُخمَّن السوق: بادئتُه تقول دولته، والمفتاحُ per-country
    يُقرأ لها. وهو ما يجعل **ما يُعلنه `/auth/method` وما يقع في `challenge`
    شيئاً واحداً** — وإعلانُ قناةٍ لا تُستعمل هو بعينه عطبُ «قاعدةٍ بلا باب»
    الذي تكرر في هذا المشروع.
    """
    methods = await available_methods(session, country_for_phone(phone))
    return (methods[0] if methods else NONE), methods


async def required_for_signup(
    session: AsyncSession, country_code: CountryCode
) -> bool:
    """هل يشترط التسجيلُ إثباتَ الرقم في هذه الدولة؟

    مفتاحٌ per-country **افتراضُه مفعّل** (`DEFAULT_ENABLED_FLAGS`): غيابُ
    الصف هنا لا يعني إطفاءَ الحارس.
    """
    return await settings_service.is_feature_enabled(
        session, country_code, FeatureKey.OTP_VERIFICATION_ENABLED
    )


# ------------------------------------------------------------- التحدي


def _next_code_channel(
    methods: list[VerificationMethod], after: str
) -> str | None:
    """القناةُ التالية التي نرسل فيها رمزاً — أو `None` إن لم يبق مخرج."""
    remaining = [m for m in methods if m in CODE_CHANNELS and m != after]
    return remaining[0] if remaining else None


async def challenge(
    session: AsyncSession,
    redis: Redis,
    phone: str,
    *,
    channel: str | None = None,
    purpose: str = OtpTemplatePurpose.REGISTRATION,
) -> otp.Challenge:
    """يبدأ التحدي إن كان المُحقِّق يحتاج ذلك.

    Firebase لا يحتاج: الرسالة تُرسل من جهاز المستخدم، فيعود `sent=false`
    بدل خطأ — والواجهة تسأل دائماً ولا تحتاج أن تعرف المُحقِّق قبل أن تسأل.

    و`channel` هو **اختيارُ المستخدم الصريح** بعد فشل قناة (زرُّ «أرسله برسالة
    نصية»)، ويُرفض إن لم تكن القناةُ متاحةً لهذا الرقم.
    """
    chosen, methods = await method_for_phone(session, phone)
    # **دولةُ الرقم هي سوقُ السقوف**: الأرقامُ per-country، ومن يطلب رمزاً على
    # رقمٍ ليبيٍّ يخضع لسقوف ليبيا مهما كان مصدرُ الطلب — الرقمُ يحمل دولتَه
    market = country_for_phone(phone)

    if channel is not None:
        if channel not in methods:
            raise ChannelUnavailable()
        chosen = channel  # type: ignore[assignment]

    if chosen == WHATSAPP_OTP:
        from app.services.whatsapp import (
            WhatsAppError,
            WhatsAppNumberUnknown,
            get_provider_or_none,
        )

        provider = await get_provider_or_none(session)
        if provider is None:
            # عقدٌ اختفى بين قراءةٍ وأخرى — يُعامل كفشل إرسالٍ لا كعطل نظام:
            # صاحبُ الرقم يحتاج مخرجاً لا تشخيصاً
            raise VerificationSendFailed(
                channel=WHATSAPP_OTP,
                fallback=_next_code_channel(methods, WHATSAPP_OTP),
            )
        # **يُسأل قبل الإرسال لا داخله** (2026-08-31): «أهذا الرقم على
        # واتساب؟» جوابٌ يخصّ صاحبَ الرقم، **ويُعرف قبل أن يُشرَع في إرسالٍ
        # لا يصل**. وكان محبوساً داخل `send_code` فيسافر نصّاً تحت رمزٍ عامّ،
        # **فلا تستطيع الشاشةُ أن تفرّق إلا بمطابقة عربيّة**.
        #
        # **ولا يُبتلع خطؤه**: تعذّرُ السؤال عطبُ قناةٍ يوجب الارتداد كما كان.
        try:
            await provider.check_number(phone)
        except WhatsAppNumberUnknown:
            # **رمزٌ يفرّق لا نصّ** — والواجهةُ تقرّر بلا قراءة عربية
            raise VerificationSendFailed(
                channel=WHATSAPP_OTP,
                fallback=_next_code_channel(methods, WHATSAPP_OTP),
                detail=(
                    "هذا الرقم غير مسجَّل على واتساب — رمزُ التحقّق يُرسل عبر "
                    "واتساب. تأكّد من الرقم أو استعمل رقماً عليه واتساب."
                ),
                reason="not_on_channel",
            ) from None
        except WhatsAppError:
            # **عطبُ قناةٍ لا خبرُ رقم** — يمرّ إلى المعالج أدناه كما كان
            pass

        try:
            sent = await otp.issue(
                session,
                redis,
                phone,
                country=market,
                sender=provider,
                purpose=purpose,
            )
        except WhatsAppError as exc:
            fallback = _next_code_channel(methods, WHATSAPP_OTP)
            # **ولا يُقال «جرّب قناةً أخرى» حيث لا قناةَ أخرى.** رسائلُ المزوّد
            # مكتوبةٌ على فرض وجود مخرج («هذا الرقم ليس على واتساب — جرّب
            # الرسائل القصيرة»)، وحين يُطفأ عقدُ SMS يصير ذلك **إحالةً إلى بابٍ
            # غيرِ موجود**: زرٌّ لا يُرسم ونصٌّ يطلب الضغطَ عليه.
            #
            # وهي «رفضٌ بلا مخرج» بعينها — القاعدةُ التي أصلحت التفضيلَ المجنَّس
            # في 10-ج. فالنصُّ يُقصّ عند الشرطة ويُستبدل بما يملكه صاحبُ الرقم
            # فعلاً: أن يجرّب رقماً آخرَ عليه واتساب.
            detail = exc.message
            if fallback is None and "—" in detail:
                detail = detail.split("—")[0].strip()
                detail = f"{detail} — جرّب رقماً آخر عليه واتساب"
            raise VerificationSendFailed(
                channel=WHATSAPP_OTP,
                fallback=fallback,
                detail=detail,
                reason="channel_down",
            ) from exc
        return otp.Challenge(
            sent=sent.sent,
            expires_in=sent.expires_in,
            resend_after=sent.resend_after,
            channel=WHATSAPP_OTP,
        )

    if chosen == SMS_OTP:
        sent = await otp.issue(
            session, redis, phone, country=market, purpose=purpose
        )
        return otp.Challenge(
            sent=sent.sent,
            expires_in=sent.expires_in,
            resend_after=sent.resend_after,
            channel=SMS_OTP,
        )

    return otp.Challenge(sent=False, channel=chosen)


async def verify(
    session: AsyncSession, redis: Redis, *, phone: str, proof: str
) -> None:
    """يتحقق من إثبات ملكية الرقم، أو يرفع خطأً. لا يعيد شيئاً عند النجاح.

    `proof` رمزُ هوية Firebase أو رمزٌ من ست خانات — حسب المُحقِّق المُهيأ.
    والرقم يُمرَّر بصيغة E.164 كما يُخزَّن (SPEC القسم 4).
    """
    method, _ = await method_for_phone(session, phone)

    if method == FIREBASE:
        from app.services.auth.firebase_identity import verify_phone_ownership

        await verify_phone_ownership(session, phone=phone, id_token=proof)
        return

    # **بابُ تحقّقٍ واحد لكل الرموز**: واتساب والرسائل كلتاهما تُوصل رمزاً
    # ولّده `services/otp.py` وحفظ بصمتَه **بالرقم لا بالقناة**. فمن أُرسل إليه
    # في واتساب ثم ارتدّ إلى الرسائل يُتحقق منه هنا بلا أن نسأل من أوصله — ولو
    # كان التحققُ مرتبطاً بالقناة لبطل الرمزُ بمجرد الارتداد، وذاك هو الفخُّ
    # الذي يجعل «الارتداد الآمن» غيرَ آمن
    if method in CODE_CHANNELS:
        await otp.verify(redis, phone, proof)
        return

    raise VerificationUnavailable()


def verified_now() -> datetime:
    """لحظةُ الإثبات — دالةٌ واحدة كي لا يتناثر `datetime.now` في المسارات."""
    return _now()


def mark_verified(user: User) -> User:
    """يختم الحساب بلحظة الإثبات. الـ commit مسؤولية المستدعي."""
    user.phone_verified_at = _now()
    return user


def require_verified(user: User) -> None:
    if user.phone_verified_at is None:
        raise PhoneNotVerified()


# ═══════════════════════ البريدُ قناةً بديلة (قرارُ المالك 2026-08-31) ═══════════════════════
#
# ## والبريدُ يُثبت البريدَ لا الهاتف — **وهذا هو كلُّ التصميم**
#
# **لا يدخل `available_methods` ولا `challenge` ولا `verify`**: تلك ثلاثتُها
# تجيب سؤالاً واحداً — «ما الذي يُثبت **ملكيةَ هذا الرقم**؟» — **ورمزٌ يصل
# صندوقَ بريدٍ لا يثبت أن صاحبَه يملك الرقم**.
#
# **وإدخالُه هناك كان سيكون العطبَ بعينه**: بابٌ يُسمّى «إثباتَ رقم» ويقبل
# إثباتاً من قناةٍ أخرى، **فيُنشأ حسابٌ كاملُ الصلاحية برقمٍ لم يملكه أحد** —
# وهو ما بُني `otp_verification_enabled` ليمنعه، ولا يُلتفّ عليه بقناةٍ ثالثة.
#
# ## فماذا يفعل إذاً
#
# **يفتح حساباً محدوداً**: بريدٌ مُثبَتٌ · ورقمٌ **محجوزٌ لا مملوك**
# (`phone_pending`) · **ولا رحلةَ ولا محفظة**. **وهو مخرجٌ لا التفاف**: حين
# تسقط واتساب، من لا قناةَ له **لا يستطيع حتى أن يبدأ** — فيبدأ ببريده،
# ويُكمل حين تعود القناة.


async def email_signup_available(
    session: AsyncSession, country_code: CountryCode | None = None
) -> bool:
    """أيُعرض بابُ «سجّل ببريدك» في هذا السوق؟ — **العقدُ والمفتاحُ معاً**.

    **كواتساب حرفاً**: العقدُ عامٌّ يقول «نستطيع»، والمفتاحُ per-country يقول
    «نفعل هنا». **وبلا دولةٍ معروفةٍ لا يُعرض** — مفتاحٌ per-country لا يُقرأ
    بلا دولة، و«افترض الافتراضية» يفتح باباً في سوقٍ أُطفئ فيه.
    """
    from app.services.email import get_email_provider_or_none

    if country_code is None:
        return False
    if not await settings_service.is_feature_enabled(
        session, country_code, FeatureKey.EMAIL_OTP_ENABLED
    ):
        return False
    return await get_email_provider_or_none(session) is not None


async def challenge_email(
    session: AsyncSession,
    redis: Redis,
    email: str,
    *,
    country_code: CountryCode,
    purpose: str = OtpTemplatePurpose.REGISTRATION,
) -> otp.Challenge:
    """يرسل رمزاً إلى عنوانٍ بريديّ — **ويمرّ بسقوف `otp.issue` نفسِها**.

    **ولا سقفَ ثانٍ يُخترع**: `otp.issue` هو البابُ الذي تعيش فيه السقوف،
    **وقناةٌ تلتفّ عليه تفتح ما أُغلق** — من استنفد محاولاته على رقمه لا
    يشتري محاولاتٍ جديدةً بتبديل القناة، **ومن أغرق عنواناً لا يفعلها مرّتين**.
    وعدّاداتُ العنوان مستقلّةٌ عن عدّادات الرقم لأن المفتاحَ يُبنى على القيمة.
    """
    from app.services.email import EmailError, get_email_provider_or_none

    if not await email_signup_available(session, country_code):
        raise ChannelUnavailable(
            "التحقّق بالبريد غير مفعَّل في هذا السوق"
        )
    provider = await get_email_provider_or_none(session)
    if provider is None:  # pragma: no cover - سُئل قبل سطرين
        raise VerificationSendFailed(channel=EMAIL_OTP, fallback=None)

    try:
        sent = await otp.issue(
            session,
            redis,
            email,
            country=country_code,
            sender=otp.EmailCodeSender(provider),
            purpose=purpose,
        )
    except EmailError as exc:
        # **ولا ارتدادَ من البريد إلى غيره**: البريدُ نفسُه هو الارتداد — من
        # جاء إليه جاء لأن ما قبله سقط. **و`fallback=None` جوابٌ صادق**،
        # ومكانُ إصلاحه صفحةُ العقود لا هذه الشاشة.
        raise VerificationSendFailed(
            channel=EMAIL_OTP, fallback=None, detail=exc.message
        ) from exc

    return otp.Challenge(
        sent=sent.sent,
        expires_in=sent.expires_in,
        resend_after=sent.resend_after,
        channel=EMAIL_OTP,
    )


async def verify_email(redis: Redis, *, email: str, code: str) -> None:
    """يتحقّق من رمز البريد — **بالبابِ نفسِه الذي يتحقّق من رموز الهاتف**.

    البصمةُ محفوظةٌ بالموضوع (العنوان هنا، الرقمُ هناك)، **وعدّادُ المحاولات
    وحرقُ الرمز واحدٌ للقناتين** — فلا ينشأ بابُ تحقّقٍ ثانٍ بسياسةٍ أضعف.
    """
    await otp.verify(redis, email, code)


def mark_email_verified(user: User, *, email: str) -> User:
    """يختم البريدَ بلحظته. الـ commit مسؤوليةُ المستدعي."""
    user.email = email
    user.email_verified_at = _now()
    return user


class PhonePending(AppError):
    """إجراءٌ يشترط رقماً مملوكاً على حسابٍ رقمُه **محجوزٌ لا مملوك**.

    **403 لا 402**: ليست حدوداً تُشترى بل خطوةٌ لم تُتمّ. **ورسالتُها تقول
    ما يُفعل** — رفضٌ بلا مخرجٍ ليس رفضاً، وهي قاعدةُ التفضيل المجنَّس نفسُها.
    """

    status_code = 403
    code = "phone_pending"
    message = (
        "أكّد رقم هاتفك أولاً — سجّلتَ ببريدك، والرقمُ محجوزٌ باسمك ولم يُثبَت بعد."
    )


def require_owned_phone(user: User) -> None:
    """**الحسابُ المحدود**: لا رحلةَ ولا محفظةَ حتى يُثبَت الرقم.

    **ولمَ هذان بالذات** (قرارُ المالك): الرحلةُ تضع إنساناً في سيارةِ إنسان،
    **والرقمُ هو ما يُتّصل به حين يقع شيء**. والمحفظةُ مال — **ومالٌ يدخل
    حساباً برقمٍ لا يملكه صاحبُه لا يُعرف لمن يُردّ**.
    """
    if user.phone_pending:
        raise PhonePending()
