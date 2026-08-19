from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.app_scope import ClientApp
from app.models.enums import CountryCode, Gender, GenderPreference, UserRole

# رمزُ إثبات ملكية الرقم: رمز هوية Firebase (JWT بألف حرف أو تزيد) أو رمز
# SMS من ست خانات — حسب المُحقِّق المُهيأ. حدّاه هنا حدّا **نقلٍ** يتسعان
# للاثنين، والتحقق نفسه في `services/verification.py`
VerificationToken = Field(min_length=4, max_length=4096)

# كلمة المرور: الحدّان هنا للنقل، والسياسةُ في `auth/password.validate_password`
Password = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20, examples=["0791234567"])
    name: str = Field(min_length=2, max_length=120)
    password: str = Password
    country_code: CountryCode
    # التسجيل الذاتي للركاب والكباتن فقط — حسابات admin/support تُنشأ من اللوحة
    role: Literal[UserRole.RIDER, UserRole.DRIVER] = UserRole.RIDER
    # إثبات ملكية الرقم. مطلوبٌ ما لم يُطفئ المشرف `otp_verification_enabled`
    # لهذه الدولة — وحينها يُنشأ الحساب غير محقق ويبقى موسوماً
    verification_token: str | None = Field(default=None, max_length=4096)
    # تعلنه الراكبة عن نفسها (المرحلة 10-ج). **ويُرفض على مسار الكبتن**: جنسُه
    # يضبطه المشرف من هويته المرفوعة، وحقلٌ يكتبه هو عن نفسه يجعل «سائقة
    # للنساء» شيئاً يُدّعى لا شيئاً يُثبَت
    gender: Gender | None = None
    # رمزُ إحالةٍ اختياري (المرحلة 12-ح). **ولا بابَ غيرَ هذا**: إسنادٌ رجعيٌّ
    # لحسابٍ قائمٍ هو بابُ التلاعب الوحيد الذي لا يُغلق بعد فتحه — من يملك
    # حسابين يُحيل نفسه متى شاء (SPEC القسم 9.1). **ويُرفض على مسار الراكب**
    # لا يُهمَل: الحافزُ لجذب السائقات، ورمزٌ يُقبل ثم لا يُسند شيئاً يبدو أنه
    # عمل — نفسُ قاعدةِ `gender` على مسار الكبتن
    referral_code: str | None = Field(default=None, min_length=4, max_length=16)
    # **أيُّ تطبيقٍ يطلب** (`core/app_scope.py`، قرارُ المالك 2026-08-15):
    # كلُّ تطبيقٍ لدوره وحدَه. وغيابُه يمرّ — دعوى تضييقٍ لا توسيع
    app: ClientApp | None = None


class ProfileUpdate(BaseModel):
    """ما يملك صاحبُ الحساب تغييره بنفسه (المرحلة 10-ج).

    الحقلان معاً إعلانٌ عن الذات واختيارٌ لها، وكلاهما للراكبة: جنسُ الكبتن
    ليس منهما، وتفضيلُه الدائم في `PATCH /drivers/me`.
    """

    gender: Gender | None = None
    ride_gender_preference: GenderPreference | None = None


class LoginRequest(BaseModel):
    """الدخول بكلمة المرور — الطريقة الوحيدة (المرحلة 8-ب)."""

    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=1, max_length=128)
    country_code: CountryCode | None = None
    # **أيُّ تطبيقٍ يطلب** (`core/app_scope.py`، قرارُ المالك 2026-08-15):
    # كلُّ تطبيقٍ لدوره وحدَه. وغيابُه يمرّ — دعوى تضييقٍ لا توسيع
    app: ClientApp | None = None


class ChallengeRequest(BaseModel):
    """«أرسل لي رمز التحقق» — و`channel` اختيارُ المستخدم الصريح (12-هـ).

    غيابُه يعني «القناةُ الأولى المتاحة» وهو الطبيعي؛ ووجودُه يعني أن صاحبَ
    الرقم ضغط «أرسله برسالة نصية» بعد أن فشل واتساب. ولا يُقبل إلا لقناةٍ
    متاحةٍ فعلاً لهذا الرقم — وإلا رُفض بلا استبدالٍ صامت.
    """

    phone: str = Field(min_length=6, max_length=20)
    country_code: CountryCode | None = None
    channel: Literal["whatsapp_otp", "sms_otp"] | None = None


class ChallengeResponse(BaseModel):
    """جواب «أرسل لي رمز التحقق».

    `sent=false` حين لا يحتاج المُحقِّقُ تحدياً من عندنا — Firebase ترسل من
    جهاز المستخدم — أو حين لا مُحقِّق أصلاً. فالواجهة تسأل دائماً ولا تحتاج
    أن تعرف المُحقِّق قبل أن تسأل.
    """

    sent: bool
    expires_in: int | None = None
    resend_after: int | None = None
    # القناةُ التي أُرسل فيها الرمز فعلاً (12-هـ) — تقولها الشاشة لصاحبها: من
    # ينتظر رسالةً نصيةً وقد وصله واتساب يفتح تطبيقاً خطأً ثم يطلب إعادة
    # الإرسال، وكلُّ إعادةٍ رسالةٌ مدفوعة
    channel: str | None = None


class VerifyPhoneRequest(BaseModel):
    """إثبات رقمِ حسابٍ قائم — لمن أُنشئ حسابه والمفتاح مطفأ."""

    verification_token: str = VerificationToken


class PasswordResetRequest(BaseModel):
    """استعادة كلمة المرور: إثباتُ الرقم وتعيينُ الكلمة في طلبٍ واحد.

    **لا توكن دخولٍ يُصدر بمجرد التحقق**: الإثبات وحده لا يفتح جلسة، فلو
    انقطع الطلب بعده لم يبق للمهاجم شيء. الجلسة تُفتح بعد أن تُكتب الكلمة
    الجديدة فعلاً.
    """

    phone: str = Field(min_length=6, max_length=20)
    country_code: CountryCode | None = None
    verification_token: str = VerificationToken
    new_password: str = Password


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    name: str
    role: UserRole
    # **كلُّ ما يملكه من أدوار** (نموذجُ الأدوار §21): به يعرف التطبيقُ الآخرَ
    # أيرسم «تبديلاً» أم «سجّل ككبتن» — وسؤالُ الخلفية عند كل ضغطةٍ يجعل الزرَّ
    # ينتظر شبكةً ليقول ما يمكن قولُه من الجلسة نفسِها
    roles: list[UserRole] = Field(default_factory=list, validation_alias='roles_list')
    country_code: CountryCode
    is_blocked: bool
    # يقرؤه التطبيق فيطالب صاحبه بالتحقق، وتفلتر به اللوحة (SPEC القسم 13)
    phone_verified: bool
    # حسابُ صاحبه يقرأ إعلانه وتفضيله ليرسمهما في ملفه (المرحلة 10-ج).
    # وجنسُ **غيره** لا يصل إليه من أي مسار: ليس في `RideDriverOut` ولا في
    # إطار `nearby_drivers` ولا في أي مخرَجٍ يراه الطرف الآخر
    gender: Gender | None = None
    # لحظةُ ختم المشرف — تقرؤها **الكبتنة في شاشة وثائقها** لتعرف أن جنسها
    # ثُبِّت ومتى، وأنه ليس حقلاً تعدّله هي. وفارغةٌ عند الراكبة دائماً:
    # إعلانُها عن نفسها لا يُختم (المرحلة 10-ج)
    gender_verified_at: datetime | None = None
    ride_gender_preference: GenderPreference = GenderPreference.ANY
    created_at: datetime


class UserBlockUpdate(BaseModel):
    """حظرُ حسابٍ أو رفعُ الحظر (SPEC القسم 13/3) — **بسببٍ إلزامي عند الحظر**.

    السببُ يدخل سجل التدقيق ولا يصل صاحبَ الحساب: هو جوابُ «لماذا حُظر؟» حين
    يُسأل بعد شهر، لا رسالةٌ إليه. ورفعُ الحظر لا يشترطه.
    """

    reason: str | None = Field(default=None, max_length=255)


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenPair


class TotpLoginRequest(BaseModel):
    """الخطوةُ الثانية من دخول اللوحة (القسم 14.1، المرحلة 12-د).

    **ورمزُ الاسترداد مقبولٌ هنا** لا في مسارٍ آخر: من فقد هاتفه لا يملك رمزَ
    اللحظة، ورموزُ الاسترداد وُجدت لهذه اللحظة بالذات — فمسارٌ لا يقبلها يجعل
    هاتفاً مفقوداً حساباً مفقوداً بينما الرموزُ في جيب صاحبه.
    """

    challenge_token: str = Field(min_length=8, max_length=128)
    code: str | None = Field(default=None, min_length=6, max_length=16)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)
    # **أيُّ تطبيقٍ يطلب** (`core/app_scope.py`، قرارُ المالك 2026-08-15):
    # كلُّ تطبيقٍ لدوره وحدَه. وغيابُه يمرّ — دعوى تضييقٍ لا توسيع
    app: ClientApp | None = None


class LoginResponse(BaseModel):
    """جوابُ الدخول — إمّا جلسةٌ كاملة، وإمّا تحدٍّ ثانٍ **بلا توكن**.

    شكلٌ واحدٌ لا اتحادٌ بين شكلين: التطبيقان يقرآن `user`/`tokens` كما كانا
    (فـ`totp_required=false` حقلٌ زائدٌ لا يضرّهما)، واللوحةُ تفحص العلم أولاً.

    **ولا توكنَ قبل العاملين**: حين يكون العاملُ مطلوباً يخرج هذا الجواب
    بـ`user=None` و`tokens=None`. وهي قاعدةُ استعادة كلمة المرور نفسُها —
    إثباتٌ ناقصٌ لا يفتح جلسة، فلو انقطع الطلبُ بعده لم يبق للمهاجم شيء.
    """

    totp_required: bool = False
    user: UserOut | None = None
    tokens: TokenPair | None = None
    challenge_token: str | None = None
    expires_in: int | None = None


class AuthMethodResponse(BaseModel):
    """ما تحتاج الواجهة معرفته قبل رسم شاشة الدخول.

    **الدخول ثابت** (`password`) والمتغيّر هو **المُحقِّق**: تدفّق Firebase في
    التطبيق، أو شاشةُ رمزٍ نرسله نحن (`otp_length`)، أو لا تحقق.
    """

    login: Literal["password"] = "password"
    verification: Literal["firebase", "sms_otp", "whatsapp_otp", "none"]
    otp_length: int | None = None
    # كلُّ القنوات المهيأة بترتيب الأولوية (12-هـ): الأولى هي `verification`،
    # وما بعدها مخرجٌ ترسمه الواجهة عند الفشل — قائمةٌ بلا بابٍ تعني زرَّ ارتدادٍ
    # لا يظهر حين يلزم
    channels: list[str] = []


class HandoffStart(BaseModel):
    """طلبُ تسليمٍ إلى تطبيقٍ آخر — **الهدفُ يُصرَّح ولا يُستنتج**."""

    target: ClientApp


class HandoffToken(BaseModel):
    token: str
    expires_in: int


class HandoffExchange(BaseModel):
    """مبادلةُ الرمز — و`app` هنا هو التطبيقُ المستقبِل نفسُه.

    ويُقارَن بالهدف المختوم في الرمز: رمزٌ صدر لتطبيقٍ لا يُقبل في غيره.
    """

    token: str
    app: ClientApp
