from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode, UserRole


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20, examples=["0791234567"])
    name: str = Field(min_length=2, max_length=120)
    # الحقل نفسه يحمل كلمة مرور أو رمز OTP حسب المزود المفعّل (المرحلة 8)،
    # فالحدُّ الأدنى هنا حدُّ **نقلٍ** لا سياسة: سياسة كلمة المرور (8 خانات)
    # في `PasswordAuthStrategy`، وسقفٌ في المخطط يمنع رمزاً من ستة أرقام
    # يعطّل الطريق الآخر بدل أن يحرس هذا
    password: str = Field(min_length=4, max_length=128)
    country_code: CountryCode
    # التسجيل الذاتي للركاب والكباتن فقط — حسابات admin/support تُنشأ من اللوحة
    role: Literal[UserRole.RIDER, UserRole.DRIVER] = UserRole.RIDER


class LoginRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=1, max_length=128)
    country_code: CountryCode | None = None


class ChallengeRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    country_code: CountryCode | None = None


class ChallengeResponse(BaseModel):
    """جواب «أرسل الرمز».

    `sent=false` في وضع كلمة المرور: المسار موجودٌ دائماً فلا تحتاج الواجهة
    أن تعرف أيَّ استراتيجية تعمل قبل أن تسأل.
    """

    sent: bool
    expires_in: int | None = None
    resend_after: int | None = None


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
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenPair


class AuthMethodResponse(BaseModel):
    """تخبر الواجهة بطريقة الدخول الحالية دون أن تقرّرها بنفسها."""

    method: Literal["password", "otp"]
    otp_length: int | None = None
