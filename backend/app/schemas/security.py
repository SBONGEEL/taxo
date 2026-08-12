"""مخطّطاتُ التحقق الثنائي وسياسةِ دخول اللوحة (القسم 14.1، المرحلة 12-د)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.security_setting import (
    MAX_IDLE_TIMEOUT_MINUTES,
    MIN_IDLE_TIMEOUT_MINUTES,
)
from app.services.totp import DIGITS, PERIOD_SECONDS

# الرمزُ ستُّ خانات، والحدُّ هنا حدُّ **نقل** يتسع لمسافةٍ يلصقها المستخدم؛
# والتحققُ نفسُه في `services/totp.match_step`
TotpCode = Field(min_length=DIGITS, max_length=16)
RecoveryCode = Field(min_length=8, max_length=32)


class TotpEnrollOut(BaseModel):
    """ما يُعرض مرةً واحدةً ولا يُقرأ بعدها من أي مسار.

    `uri` هو ما ترسمه اللوحةُ QR **محلياً**، و`secret` للإدخال اليدوي حين
    يرفض الهاتفُ الكاميرا. وكلاهما يختفي من كل جوابٍ لاحق.
    """

    secret: str
    uri: str
    digits: int = DIGITS
    period_seconds: int = PERIOD_SECONDS


class TotpConfirmRequest(BaseModel):
    code: str = TotpCode


class TotpConfirmOut(BaseModel):
    """رموزُ الاسترداد **مرةً واحدة** — بعدها لا مسارَ يعرضها.

    فالشاشةُ التي تعرضها هي الشاشةُ الوحيدة، ومن أغلقها بلا نسخٍ يُطفئ عاملَه
    برمزٍ حاضرٍ ويسجّل من جديد.
    """

    confirmed_at: datetime
    recovery_codes: list[str]


class TotpRecoveryVerifyRequest(BaseModel):
    """إثباتُ أن الاسترداد يعمل — **يستهلك رمزاً حقيقياً** (قرارُ المالك)."""

    recovery_code: str = RecoveryCode


class TotpDisableRequest(BaseModel):
    """الإطفاءُ بعاملٍ حاضرٍ لا بجلسةٍ وحدها — أحدُ الحقلين مطلوب."""

    code: str | None = Field(default=None, min_length=DIGITS, max_length=16)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)

    @model_validator(mode="after")
    def _one_of_them(self) -> TotpDisableRequest:
        if not self.code and not self.recovery_code:
            raise ValueError("مطلوب رمزٌ حاضرٌ أو رمزُ استرداد")
        return self


class TotpStatusOut(BaseModel):
    """حالةُ عامل صاحب الحساب — ما تحتاجه شاشةُ «الأمان» لترسم نفسها.

    و`required` ليس تكراراً لمفتاح الإعدادات: هو جوابُ «هل **أنا** مُلزَم؟»
    بعد قراءة الدور، وهو ما يجعل الشاشةَ تقول للـ`support` «اختياري» وللـ
    `admin` «مطلوب» من نفس الحقل.
    """

    enrolled: bool
    confirmed: bool
    confirmed_at: datetime | None = None
    recovery_verified_at: datetime | None = None
    recovery_codes_remaining: int
    required: bool


class SecuritySettingOut(BaseModel):
    """السياسةُ ومعها حالةُ عاملِ من يقرأ.

    الحالةُ في نفس الجواب عمداً: زرُّ الإلزام يُرفض إن لم يكن للطالب عاملٌ
    مؤكَّدٌ واستردادٌ مُثبَت، **وزرٌّ يعمل ثم يرتدّ 409 يُعلّم المشرفَ أن يعيد
    المحاولة** بينما زرٌّ مُعطَّلٌ يقول سببَه يُعلّمه أن يُصلح — وهي القاعدةُ
    نفسُها التي رسمت زرَّ «اعتماد الكبتن» في شاشة السائقين.
    """

    model_config = ConfigDict(from_attributes=True)

    admin_totp_required: bool
    admin_idle_timeout_minutes: int
    min_idle_timeout_minutes: int = MIN_IDLE_TIMEOUT_MINUTES
    max_idle_timeout_minutes: int = MAX_IDLE_TIMEOUT_MINUTES
    my_factor: TotpStatusOut


class SecuritySettingUpdate(BaseModel):
    """ما يملك المشرفُ تغييره — والسقفُ محروسٌ هنا وفي الخدمة وفي القاعدة."""

    admin_totp_required: bool | None = None
    admin_idle_timeout_minutes: int | None = Field(
        default=None, ge=MIN_IDLE_TIMEOUT_MINUTES, le=MAX_IDLE_TIMEOUT_MINUTES
    )
