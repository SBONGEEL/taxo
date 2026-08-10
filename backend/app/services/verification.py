"""إثبات ملكية رقم الهاتف — **تحقّقٌ لا دخول** (المرحلة 8-ب).

هذا هو التحوّل الذي أعاد ترتيب طبقة المصادقة كلها: OTP لم يعد طريقةَ دخول
بل **حدثاً يقع مرتين في عمر الحساب**:

1. **عند التسجيل** — مرةً واحدة، ثم يضع صاحبه كلمة مروره ويدخل بها بعدها.
2. **عند استعادة كلمة المرور** — لأن استعادةً بلا إثبات ملكيةٍ للرقم ليست
   استعادة بل استيلاء.

والدخول اليومي **كلمة مرور دائماً ولكل المستخدمين** (`services/auth`).

**لماذا حُذفت `OtpAuthStrategy` كطريقة دخول ولم يُحذف كودُها؟** لأن مزود SMS
التقليدي لم يمت — تغيّر دورُه. كان بديلاً للدخول فصار **المُحقِّق الثاني**:
حيث لا يعمل Firebase (أو حيث عقدٌ محليٌّ أرخص) يبقى `services/otp.py` بكامله
— توليدُ الرمز وبصمتُه وعدّادُ المحاولات ومهلةُ الإرسال — يخدم نفس الحدثين.
أما إبقاؤه طريقةَ دخولٍ ثانية فكان يعني جوابين متناقضين لسؤال «كيف أدخل»،
وحساباتٍ أُنشئت تحت أحدهما لا تعمل تحت الآخر.

**نقطة القرار صارت في التحقق لا في الدخول**، وترتيبها:
`firebase` ← `sms_otp` ← لا مُحقِّق. ومفتاح `otp_verification_enabled`
يعلوها جميعاً **في التسجيل وحده** — ولا يمسّ الاستعادة أبداً.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.enums import CountryCode, FeatureKey, ProviderKey
from app.models.user import User
from app.services import otp, settings_service

# ما تراه الواجهة فتعرف أيَّ تدفّقٍ ترسم
VerificationMethod = Literal["firebase", "sms_otp", "none"]

FIREBASE = "firebase"
SMS_OTP = "sms_otp"
NONE = "none"


class VerificationUnavailable(AppError):
    """التحقق مطلوب ولا مُحقِّق مُهيأ — عقدٌ ناقص لا خطأُ مستخدم.

    503 صريحة عمداً بدل السماح بالمرور: «لا حساب يُنشأ برقم غير محقق» قاعدةٌ
    لا تُخرق لأن العقد غائب. ومخرجُها إداري: أدخل عقد Firebase أو عقد SMS،
    أو أطفئ `otp_verification_enabled` للطوارئ وأنت تعرف ما تفعل.
    """

    status_code = 503
    code = "verification_unavailable"
    message = "خدمة التحقق من الهاتف غير مهيأة — راجع عقود المزودين في اللوحة"


class PhoneNotVerified(AppError):
    """إجراءٌ يشترط رقماً مُثبتاً على حسابٍ لم يُثبَّت رقمه."""

    status_code = 403
    code = "phone_not_verified"
    message = "يجب إثبات ملكية رقم الهاتف أولاً"


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------- من يُحقِّق


async def active_method(session: AsyncSession) -> VerificationMethod:
    """المُحقِّق المُهيأ الآن — بصرف النظر عن مفتاح الميزة.

    الترتيب: Firebase أولاً لأنه الأقوى إثباتاً والأرخص تشغيلاً (لا رسائل
    ندفع ثمنها ولا recaptcha نبنيه)، ثم مزود SMS التقليدي. والترتيب ثابتٌ لا
    يُقرأ من إعداد: مفتاحٌ يقول «أيّهما أولاً» حالةٌ ثانية قابلة للاختلاف عن
    حالة العقود، ومن أراد الثاني يُطفئ عقد الأول.
    """
    from app.services.firebase_auth import firebase_auth_enabled
    from app.services.providers.credentials import provider_is_active

    if await firebase_auth_enabled(session):
        return FIREBASE
    if await provider_is_active(session, ProviderKey.SMS):
        return SMS_OTP
    return NONE


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


async def challenge(
    session: AsyncSession, redis: Redis, phone: str
) -> otp.Challenge:
    """يبدأ التحدي إن كان المُحقِّق يحتاج ذلك.

    Firebase لا يحتاج: الرسالة تُرسل من جهاز المستخدم، فيعود `sent=false`
    بدل خطأ — والواجهة تسأل دائماً ولا تحتاج أن تعرف المُحقِّق قبل أن تسأل.
    """
    if await active_method(session) == SMS_OTP:
        return await otp.issue(session, redis, phone)
    return otp.Challenge(sent=False)


async def verify(
    session: AsyncSession, redis: Redis, *, phone: str, proof: str
) -> None:
    """يتحقق من إثبات ملكية الرقم، أو يرفع خطأً. لا يعيد شيئاً عند النجاح.

    `proof` رمزُ هوية Firebase أو رمز SMS من ست خانات — حسب المُحقِّق المُهيأ.
    والرقم يُمرَّر بصيغة E.164 كما يُخزَّن (SPEC القسم 4).
    """
    method = await active_method(session)

    if method == FIREBASE:
        from app.services.auth.firebase_identity import verify_phone_ownership

        await verify_phone_ownership(session, phone=phone, id_token=proof)
        return

    if method == SMS_OTP:
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
