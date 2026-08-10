from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode, UserRole

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


class LoginRequest(BaseModel):
    """الدخول بكلمة المرور — الطريقة الوحيدة (المرحلة 8-ب)."""

    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=1, max_length=128)
    country_code: CountryCode | None = None


class ChallengeRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    country_code: CountryCode | None = None


class ChallengeResponse(BaseModel):
    """جواب «أرسل لي رمز التحقق».

    `sent=false` حين لا يحتاج المُحقِّقُ تحدياً من عندنا — Firebase ترسل من
    جهاز المستخدم — أو حين لا مُحقِّق أصلاً. فالواجهة تسأل دائماً ولا تحتاج
    أن تعرف المُحقِّق قبل أن تسأل.
    """

    sent: bool
    expires_in: int | None = None
    resend_after: int | None = None


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
    country_code: CountryCode
    is_blocked: bool
    # يقرؤه التطبيق فيطالب صاحبه بالتحقق، وتفلتر به اللوحة (SPEC القسم 13)
    phone_verified: bool
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenPair


class AuthMethodResponse(BaseModel):
    """ما تحتاج الواجهة معرفته قبل رسم شاشة الدخول.

    **الدخول ثابت** (`password`) والمتغيّر هو **المُحقِّق**: تدفّق Firebase في
    التطبيق، أو شاشةُ رمزٍ نرسله نحن (`otp_length`)، أو لا تحقق.
    """

    login: Literal["password"] = "password"
    verification: Literal["firebase", "sms_otp", "none"]
    otp_length: int | None = None
