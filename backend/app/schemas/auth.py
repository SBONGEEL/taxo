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
    # **ما وافق عليه بعينه** (البند ١٠، §34 — بُني ٢٠٢٦-٠٩-٠٥ يومَ اعتُمدت
    # النصوص). **ومعرّفاتٌ لا `true`**: علامةٌ منطقيةٌ تقول «وافق» ولا تقول
    # **على ماذا**، **فتستنتج الخلفيةُ «المنشورَ الآن»** — ونشرةٌ تقع بين
    # عرض النصِّ وإرساله تكتب موافقةً على نصٍّ لم يقرأه أحد.
    accepted_policy_ids: list[uuid.UUID] = Field(default_factory=list, max_length=8)


class EmailChallengeRequest(BaseModel):
    """«أرسل رمزاً إلى بريدي» — **والدولةُ إلزاميّةٌ لا مشتقّة**.

    **ولا تُشتقّ من الرقم كما في قناة الهاتف**: هنا لا رقمَ بعد. والمفتاحُ
    per-country، **وافتراضُ الدولة الافتراضية يفتح القناةَ في سوقٍ أُطفئت فيه**.
    """

    #: يُطبَّع في المسار بـ`core/email.normalize_email` — **بيتٌ واحد**
    email: str = Field(min_length=3, max_length=320)
    country_code: CountryCode


class EmailRegisterRequest(BaseModel):
    """تسجيلٌ بالبريد — **حسابٌ محدود، ورقمٌ محجوزٌ لا مملوك**.

    **والرقمُ مطلوبٌ رغم أنه لا يُثبَت**: هو مُعرِّفُ الدخول في هذا النظام
    (`ARCHITECTURE.md`: «Phone number is the login identity»)، **وحسابٌ بلا
    رقمٍ لا يستطيع صاحبُه الدخولَ إليه غداً**. فيُحجز الآن ويُملَك لاحقاً.
    """

    phone: str = Field(min_length=6, max_length=20)
    email: str = Field(min_length=3, max_length=320)
    #: رمزُ البريد — **ست خانات كرموز القنوات الأخرى**، من الباب نفسِه
    email_code: str = Field(min_length=4, max_length=8)
    name: str = Field(min_length=2, max_length=120)
    password: str = Password
    country_code: CountryCode
    role: Literal[UserRole.RIDER, UserRole.DRIVER] = UserRole.RIDER
    gender: Gender | None = None
    referral_code: str | None = Field(default=None, min_length=4, max_length=16)
    app: ClientApp | None = None


class ProfileUpdate(BaseModel):
    """ما يملك صاحبُ الحساب تغييره بنفسه (المرحلة 10-ج).

    الحقلان معاً إعلانٌ عن الذات واختيارٌ لها، وكلاهما للراكبة: جنسُ الكبتن
    ليس منهما، وتفضيلُه الدائم في `PATCH /drivers/me`.
    """

    gender: Gender | None = None
    ride_gender_preference: GenderPreference | None = None


class LoginRequest(BaseModel):
    """الدخول بكلمة المرور — الطريقة الوحيدة (المرحلة 8-ب).

    **ومُعرِّفان لا واحد** (قرارُ المالك 2026-08-20): الراكبُ والكبتنُ برقمهما
    كما كانا، **والمشرفُ باسمِ مستخدمٍ لا رقمَ له**. وأحدُهما يُرسل لا كلاهما.

    **ولا يصير اسمُ المستخدم مدخلاً بديلاً للتطبيقين**: `app_scope.guard` يعمل
    بعد كلمة المرور كما كان، ويرفض `admin` في تطبيقَي الراكب والكبتن — فالحارسُ
    لم يُمسّ، وما أُضيف مُعرِّفٌ لا بابٌ ثانٍ.
    """

    phone: str | None = Field(default=None, min_length=6, max_length=20)
    username: str | None = Field(default=None, min_length=3, max_length=64)
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
    # **`None` للمشرف** (2026-08-20): يدخل باسمِ مستخدمٍ لا برقم. والتطبيقان
    # يقرآنه لصاحبِهما وهو موجودٌ دائماً هناك — فالتغييرُ يمسّ اللوحةَ وحدَها
    phone: str | None
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
    # **الرقمُ محجوزٌ ولا يُملَك** (قرارُ المالك 2026-08-31) — من سجّل ببريده.
    #
    # **ولا يُشتقّ من `phone_verified == False`**: لتلك معنيان — حسابٌ أُنشئ
    # والمفتاحُ مطفأٌ للطوارئ (**كاملُ الصلاحية**)، وحسابٌ سجّل ببريده
    # (**محدودٌ عمداً**). **والتطبيقُ يرسم لهما سطرين مختلفين**: الأولُ
    # «أكّد رقمك» دعوةً، والثاني «أكّد رقمك — لا رحلةَ ولا محفظةَ قبله».
    phone_pending: bool = False
    # **السببُ والطريقُ لمن أُوقف** — أو `null` (حملةُ تأكيد الأرقام).
    #
    # **ويُبنى في الخلفية لا في الشاشة**: «التطبيقُ لا يكتب عربيّةً لخطأٍ
    # سمّاه الخادم» — ونصّان لحالٍ واحدةٍ يفترقان أوّلَ تحرير. **ومن بيته
    # الواحد** في `models/verification_campaign`، يقرؤه معه الخطأُ الذي يَردّ.
    #
    # **ولا يُشتقّ من `phone_pending`**: ذاك حسابٌ **وُلد محدوداً** لأنه سجّل
    # ببريده، وهذا **كان كاملاً فأُوقف** بانقضاء مهلة — ورسالتاهما مختلفتان.
    suspension: dict[str, str] | None = None
    # **وبريدُه إن أثبته** — يقرؤه ليعرضه في ملفّه، و`null` تعني لا بريدَ
    # مُثبَت. **ولا يُنشر بريدُ غيره من أيِّ مسار.**
    email: str | None = None
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


class AdminPermissionsOut(BaseModel):
    """ما يملكه مشرفٌ — **ومن أين جاء** (البند ٥، §39٫٥)."""

    user_id: uuid.UUID
    name: str
    roles: list[UserRole]
    permissions: list[str]
    #: **أصفوفٌ ممنوحةٌ أم افتراضُ الدور؟** — والغيابُ ليس «لا يملك شيئاً»،
    #: **وبغير هذا الحقل يظنّ القارئُ أن مشرفاً بلا صفوفٍ بلا صلاحيات**.
    explicit: bool


class AdminPermissionsIn(BaseModel):
    """المجموعةُ الكاملة — **استبدالٌ لا إضافة**، فالنزعُ ممكن."""

    permissions: list[str]


class UserProfileUpdate(BaseModel):
    """تعديلُ بيانات حسابٍ من الملفِّ الشخصيّ — **البند ١١ (§39٫١١، §46)**.

    **وحقلان لا أكثر، وكلُّ غائبٍ غائبٌ بعلّته:**

    - **الهاتفُ لا يُحرَّر**: هو مُعرِّفُ الدخول نفسُه (`users.phone` فريد)،
      **وتحريرُه من اللوحة استيلاءٌ على حساب** لا تصحيحُ حقل. **وتغييرُ صاحبه
      رقمَه بابُه التحقّق** لا مشرف.
    - **والسوقُ لا يُحرَّر**: منه تُشتقّ العملةُ ويُختم على كلِّ رحلةٍ ودفعة،
      **ونقلُ حسابٍ بين سوقين يجعل دفترَه بعملتين**.
    - **والأدوارُ بابُها مصفوفةُ الصلاحيات** (§41)، **والحظرُ بابُه `block`
      بسببٍ إلزاميّ**، **وجنسُ الكبتن بابُه ختمُ المشرف** بسببٍ مكتوب — **وبابٌ
      ثانٍ لأيٍّ منها يقفز فوق حارسه**.
    - **و`marketing_push_enabled` مفتاحُ صاحبه**: مشرفٌ يشعله يلتفّ على رفضٍ
      صريح.
    """

    #: **يُرسَل حين يُقصد تغييرُه** — والغيابُ ليس محواً
    name: str | None = Field(default=None, min_length=2, max_length=120)
    #: **مُعرِّفُ تواصلٍ لا مُعرِّفُ دخول**، و`""` تمحوه.
    #:
    #: **وكتابتُه من اللوحة تُسقط إثباتَه دائماً**: العنوانُ المُثبَت وحدَه
    #: يحجز ويصلح قناةَ استرجاع (§31 والفهرسُ الجزئيُّ على المُثبَت) — **فبريدٌ
    #: يكتبه مشرفٌ ويبقى مُثبتاً بابُ استيلاءٍ على حساب**. فيبقى بياناً يُراسَل
    #: به، **ولا يُملَك حتى يُثبته صاحبُه**.
    email: str | None = Field(default=None, max_length=320)


class UserMessageIn(BaseModel):
    """رسالةٌ فرديةٌ إلى صاحب حساب — **نصُّها بالعربية ومختومٌ في التدقيق**."""

    title: str = Field(min_length=2, max_length=80)
    body: str = Field(min_length=2, max_length=600)
