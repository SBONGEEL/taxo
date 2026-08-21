"""المصادقة: دخولٌ بكلمة المرور دائماً، وتحقّقٌ من الرقم في حدثين (8-ب).

الحدثان اللذان يحتاجان إثبات ملكية الرقم — ولا ثالث لهما:

1. **التسجيل**: يُثبَت الرقم مرةً ثم تُوضع كلمة المرور، فيُنشأ حسابٌ محقق.
2. **الاستعادة**: يُثبَت الرقم ثم تُكتب كلمةٌ جديدة وتُبطَل كل الجلسات.

ومفتاح `otp_verification_enabled` يعفي **التسجيل** وحده حين يُطفأ للطوارئ؛
والاستعادةُ لا يعفيها شيء — عفوُها يجعل إطفاء المفتاح طريقاً للاستيلاء على
أي حساب بمجرد معرفة رقمه.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core import rate_limit
from app.core.app_scope import ClientApp
from app.core.config import settings
from app.core import app_scope
from app.core.deps import (
    ClientIP,
    CurrentUser,
    DbSession,
    RedisDep,
    SecuritySelfUser,
)
from app.core.exceptions import (
    HandoffBlockedByActiveWork,
    InvalidCredentials,
    InvalidInput,
    InvalidToken,
    NotFound,
    RateLimited,
    TotpEnforcementActive,
)
from app.core.phone import InvalidPhoneNumber, normalize_phone, resolve_phone
from app.models.enums import CountryCode, UserRole
from app.models.user import User
from app.schemas.auth import (
    HandoffExchange,
    HandoffStart,
    HandoffToken,
    AuthMethodResponse,
    AuthResponse,
    ChallengeRequest,
    ChallengeResponse,
    LoginRequest,
    LoginResponse,
    PasswordResetRequest,
    ProfileUpdate,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    TotpLoginRequest,
    UserOut,
    VerifyPhoneRequest,
)
from app.schemas.security import (
    TotpConfirmOut,
    TotpConfirmRequest,
    TotpDisableRequest,
    TotpEnrollOut,
    TotpRecoveryVerifyRequest,
    TotpStatusOut,
)
from app.services import (
    admin_credentials,
    handoff,
    rides as rides_service,
    notifications,
    otp,
    security_settings,
    token_service,
    totp,
    verification,
)
from app.services.auth import password_strategy
from app.core.security import verify_password
from app.services.auth.password import set_password
from app.models.otp_template import OtpTemplatePurpose

router = APIRouter(prefix="/auth", tags=["auth"])

# **سقفُ الرقم ليس هنا** (توحيدٌ 2026-08-19): كان `OTP_PHONE_LIMIT = 5` بجانب
# `otp_settings.max_per_window` — بيتان لحقيقةٍ واحدة، **بعدّين مختلفين
# ورسالتين مختلفتين**، فمن رُفض لا يعرف أيُّهما رفضه. وقِيس الفرقُ حيّاً على
# رقمٍ واحد: عدّادُ الراوتر **٢** وعدّادُ الإعدادات **١**، لأن الأول يُحسب قبل
# الإرسال والثاني بعد نجاحه — والفرقُ يظهر بالضبط لحظةَ سقوط القناة.
#
# والسقفُ المركزيُّ هو `services/otp_limits.guard` داخل `otp.issue`: ثلاثةُ
# سقوفٍ per-country يحرّرها المشرف (نافذة · يوميّ · عمرُ التسجيل)، تُحسب
# **بعد الإرسال الناجح** فلا تستهلك عطبُ قناتنا حصّةَ أحد، وكلُّ رفضٍ يحمل
# `retry_after` يرسمه التطبيقان عدّاً تنازلياً.
#
# **وسقفُ الـ IP يبقى هنا** لأنه ليس نسخةً من شيء: `otp_limits` يعدّ على
# الرقم عمداً (عشراتُ المستخدمين خلف شبكةٍ واحدةٍ لا يخنق بعضُهم بعضاً)،
# وهذا يمنع مسحاً على أرقامٍ كثيرةٍ من مصدرٍ واحد — سؤالٌ آخر لا بيتٌ ثانٍ.
OTP_IP_LIMIT = 20
OTP_WINDOW_SECONDS = 3600

# **سقف الاستعادة يومي لا ساعي**: محاولةُ الاستيلاء على حسابٍ بعينه لا
# تُستعجل، فنافذةٌ ساعيةٌ تعطي المهاجم مئةً وعشرين محاولة في اليوم بلا أثر.
# والرقمُ سخيٌّ لمن نسي كلمته فعلاً ويكفي لتعثّرٍ أو تعثّرين
PASSWORD_RESET_DAILY_LIMIT = 5
PASSWORD_RESET_WINDOW_SECONDS = 86_400


async def _resolve(phone: str, country_code=None) -> str:
    try:
        return resolve_phone(phone, country_code)
    except InvalidPhoneNumber as exc:
        raise InvalidInput(str(exc)) from exc


async def _guard(redis, *keys_and_caps) -> None:
    for key, cap, window in keys_and_caps:
        limit = await rate_limit.hit(redis, key, limit=cap, window_seconds=window)
        if not limit.allowed:
            raise RateLimited(retry_after=limit.retry_after)


async def _issue(session, redis, user: User) -> TokenPair:
    """كلُّ إصدارِ زوجِ توكناتٍ يمرّ من هنا — ومعه مهلةُ خمول اللوحة.

    بابٌ واحد لأن الطبقةَ الأولى من المهلة (القسم 14.1) هي عمرُ مفتاح الـ
    refresh: مسارٌ يصدر التوكنات بنفسه ينسى المهلةَ، فتبقى جلسةُ مشرفٍ حيّةً
    أياماً لأن كلمةَ مروره كُتبت من مسارٍ آخر.
    """
    ttl = await security_settings.refresh_ttl_for(session, user)
    return await token_service.issue_token_pair(redis, user, refresh_ttl_seconds=ttl)


# ------------------------------------------------------------------ الوصف


@router.get("/method", response_model=AuthMethodResponse)
async def auth_method(
    session: DbSession, country_code: CountryCode | None = None
) -> AuthMethodResponse:
    """الدخول ثابتٌ والمُحقِّق متغيّر — تقرؤهما الواجهة بدل أن تفترضهما.

    و`country_code` لازمٌ منذ 12-هـ: قناةُ واتساب مفتاحُها per-country،
    فجوابٌ بلا دولةٍ يُعلن قناةً غير التي ستُستعمل فعلاً. وبغيابه تُقرأ الدولةُ
    الافتراضية — وهو ما ترسله الواجهاتُ الثلاث أصلاً من `GET /config`.
    """
    country = country_code or settings.default_country_code
    methods = await verification.available_methods(session, country)
    method = methods[0] if methods else verification.NONE
    return AuthMethodResponse(
        login="password",
        verification=method,
        otp_length=(
            otp.CODE_LENGTH if method in verification.CODE_CHANNELS else None
        ),
        channels=list(methods),
    )


@router.post("/challenge", response_model=ChallengeResponse)
async def start_challenge(
    payload: ChallengeRequest,
    session: DbSession,
    redis: RedisDep,
    ip: ClientIP,
) -> ChallengeResponse:
    """«أرسل رمز التحقق» — للتسجيل. وللاستعادة مسارُها بسقفها الخاص.

    **وسقفُ الرقم ليس هنا**: بيتُه `otp_settings` عبر `otp_limits.guard` داخل
    `otp.issue` — سقفٌ واحدٌ لمفهومٍ واحد، يحرّره المشرفُ لكل سوقٍ ورسالتُه
    واحدة. وما يبقى هنا سقفُ الـ IP، وهو سؤالٌ آخر: مسحٌ على أرقامٍ كثيرةٍ من
    مصدرٍ واحد.
    """
    phone = await _resolve(payload.phone, payload.country_code)
    await _guard(redis, (f"otp:ip:{ip}", OTP_IP_LIMIT, OTP_WINDOW_SECONDS))

    # **الغرضُ يُصرَّح عند البابِ لا يُستنتج** (قوالبُ الرمز، 2026-08-19):
    # هذا بابُ التسجيل، فقالبُه قالبُ التسجيل. ولو تُرك افتراضاً في العمق
    # لصار خلطُ القالبين خطأً **صامتاً** — كلاهما يحمل رمزاً صحيحاً، فلا شيءَ
    # يفشل ولا أحدَ يشتكي، ويقرأ صاحبُ الرقم «استعادةُ كلمة المرور» وهو يسجّل.
    challenge = await verification.challenge(
        session,
        redis,
        phone,
        channel=payload.channel,
        purpose=OtpTemplatePurpose.REGISTRATION,
    )
    return ChallengeResponse(
        sent=challenge.sent,
        expires_in=challenge.expires_in,
        resend_after=challenge.resend_after,
        channel=challenge.channel,
    )


# ------------------------------------------------------- التسجيل والدخول


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    payload: RegisterRequest,
    session: DbSession,
    redis: RedisDep,
    ip: ClientIP,
) -> AuthResponse:
    """حسابٌ جديد: رقمٌ مُثبَت + كلمة مرور يضعها صاحبه.

    الترتيب مقصود: يُتحقق من الرقم **قبل** إنشاء الصف، فلا يبقى حسابٌ نصفُ
    مُنشأ لرمزٍ لم يُقبل.
    """
    limit = await rate_limit.hit(
        redis, f"register:{ip}", limit=10, window_seconds=3600
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    try:
        phone = normalize_phone(payload.phone, payload.country_code)
    except InvalidPhoneNumber as exc:
        raise InvalidInput(str(exc)) from exc

    # **قبل الرمز وقبل الصف**: تسجيلُ راكبٍ من تطبيق الكبتن يُنشئ حساباً لا
    # يستطيع صاحبُه الدخولَ إليه من التطبيق الذي أنشأه — حسابٌ يولد مقفلاً
    app_scope.guard(payload.role, payload.app)

    verified_at = None
    if await verification.required_for_signup(session, payload.country_code):
        if not payload.verification_token:
            raise InvalidInput("إثبات ملكية الرقم مطلوب للتسجيل")
        await verification.verify(
            session, redis, phone=phone, proof=payload.verification_token
        )
        verified_at = verification.verified_now()

    user = await password_strategy.register(
        session, payload, phone=phone, verified_at=verified_at
    )
    await session.commit()
    await session.refresh(user)

    tokens = await _issue(session, redis, user)
    return AuthResponse(user=UserOut.model_validate(user), tokens=tokens)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    session: DbSession,
    redis: RedisDep,
    ip: ClientIP,
) -> LoginResponse:
    """كلمةُ المرور أولاً دائماً (المرحلة 8-ب)، ثم عاملٌ ثانٍ إن كان مسجّلاً.

    **والعاملُ يُسأل بعد كلمة المرور لا قبلها**: جوابٌ يقول «هذا الحساب محميٌّ
    بعاملٍ ثانٍ» قبل إثبات كلمة المرور يخبر من لا يملكها بما لا يحتاج معرفته.
    ولا شيء في هذا الجواب يُعلن السياسة قبل ذلك، ولا ينشرها `GET /config`:
    «هل تكفي كلمةُ المرور هنا» سؤالٌ لا يفيد إلا من لا يملكها.
    """
    # **مُعرِّفٌ واحدٌ لا اثنان**: رقمٌ أو اسمُ مستخدم. وإرسالُهما معاً غموضٌ
    # لا يُخمَّن — أيُّهما يُصدَّق لو تعارضا؟
    if bool(payload.phone) == bool(payload.username):
        raise InvalidInput("أرسل رقمَ الهاتف أو اسمَ المستخدم — لا كليهما")

    if payload.username:
        # **والسقفُ على الاسم كما هو على الرقم**: حسابٌ يُخمَّن بالاسم يُخمَّن
        # بالقدر نفسِه، فلا يُترك بلا حدّ لأن مُعرِّفَه تغيّر
        identity = f"login:username:{payload.username.strip().lower()}"
    else:
        phone = await _resolve(payload.phone, payload.country_code)
        identity = f"login:phone:{phone}"

    # **ولا سقفَ على دخول اللوحة** (قرارُ المالك 2026-08-21).
    #
    # الخمسةُ في خمس دقائق سقفٌ مقاسٌ على **الراكب والكبتن**: هاتفٌ في يدِ صاحبه،
    # وكلمةٌ يكتبها بإبهامه، وخطؤه المتكرّر عَرَضٌ لا هجوم. والمشرفُ حالٌ أخرى:
    # كلمتُه **مولَّدةٌ طويلة** تُلصَق لا تُكتب، ولصقةٌ واحدةٌ خاطئةٌ تحبسه خمسَ
    # دقائقَ عن نظامٍ قد يكون واقفاً ينتظره.
    #
    # **وثمنُه يُقال ولا يُخفى**: هذا يفتح بابَ اللوحة للتخمين الآليّ، واللوحةُ
    # منشورةٌ على الإنترنت منذ اليوم (§27.6). فما يحمل الحمايةَ بعدها:
    # **العاملُ الثاني** — ولهذا صار إشعالُه أهمَّ مما كان قبل هذا السطر، لا
    # أقلّ — وطولُ الكلمةِ المولَّدة، وسجلُّ التدقيق، وحظرُ الحساب.
    #
    # **وإعادتُه سطرٌ واحد**: احذف الشرطَ فيعود السقفان كما كانا.
    if payload.app != ClientApp.PANEL:
        # حدّان: على المُعرِّف (منع تخمين كلمة مرور حساب بعينه) وعلى الـ IP
        await _guard(
            redis,
            (
                identity,
                settings.login_rate_limit_attempts,
                settings.login_rate_limit_window_seconds,
            ),
            (
                f"login:ip:{ip}",
                settings.login_rate_limit_attempts,
                settings.login_rate_limit_window_seconds,
            ),
        )

    if payload.username:
        user = await password_strategy.authenticate_by_username(
            session, payload.username, payload.password
        )
    else:
        user = await password_strategy.authenticate(session, phone, payload.password)

    # **بعد كلمة المرور لا قبلها**: «هذا حسابُ كبتن» جوابٌ عن الحساب، فلا
    # يُقال إلا لمن أثبت أنه صاحبُه — نفسُ ترتيبِ العامل الثاني فوق. وقبل
    # التحدي أيضاً: تحدٍّ يُفتح لبابٍ سيُغلق عملٌ لا ينتهي إلى شيء
    app_scope.guard(user.roles, payload.app)

    await rate_limit.reset(redis, identity)

    # **دخولُ حسابِ الطوارئ حدثٌ يُسجَّل ساعةَ وقوعه** — لا بعد شهرٍ من قراءة
    # سجلٍّ لا يميّزه. وهو الغرضُ من الحساب الثاني: بابٌ نائمٌ يُعرف حين يُفتح.
    # **ويُكتب قبل العامل الثاني**: من بلغ كلمةَ المرور بلغ الباب، وسقوطُه في
    # التحدي لا يجعل المحاولةَ غيرَ جديرةٍ بالذكر.
    if payload.username:
        await admin_credentials.note_login(session, user, redis=redis)
        await session.commit()

    if await totp.has_confirmed_factor(session, user.id):
        challenge = await totp.start_challenge(redis, user)
        return LoginResponse(
            totp_required=True,
            challenge_token=challenge.token,
            expires_in=challenge.expires_in,
        )

    tokens = await _issue(session, redis, user)
    return LoginResponse(user=UserOut.model_validate(user), tokens=tokens)


@router.post("/login/totp", response_model=AuthResponse)
async def login_with_totp(
    payload: TotpLoginRequest,
    session: DbSession,
    redis: RedisDep,
) -> AuthResponse:
    """الخطوةُ الثانية — وهنا وحدها تُصدر التوكنات (القسم 14.1).

    الترتيب مقصود: يُهدَم التحدي **قبل** الإصدار، فلا يبقى تحدٍّ مستعملٌ صالحاً
    لو انقطع الطلبُ بعده؛ ورمزُ الاسترداد يُقبل كرمزِ اللحظة لأن من فقد هاتفه
    لا يملك الثاني — ثم يُخبَر صاحبُ الحساب أن رمزاً استُهلك، فهو أوّلُ من يجب
    أن يعرف إن لم يكن هو من فعل.
    """
    user_id = await totp.resolve_challenge(redis, payload.challenge_token)
    await totp.guard_attempt(redis, payload.challenge_token, user_id)

    user = await session.get(User, user_id)
    if user is None or user.is_blocked:
        await totp.drop_challenge(redis, payload.challenge_token)
        raise InvalidToken()

    app_scope.guard(user.roles, payload.app)

    used_recovery = bool(payload.recovery_code)
    if used_recovery:
        await totp.consume_recovery_code(
            session, user_id=user.id, code=payload.recovery_code, actor=user
        )
    elif payload.code:
        await totp.verify_code(session, user_id=user.id, code=payload.code)
    else:
        raise InvalidInput("مطلوب رمزُ التحقق الثنائي أو رمزُ استرداد")

    await session.commit()
    await totp.drop_challenge(redis, payload.challenge_token)
    # المحاولاتُ الناجحة لا تُعاقَب (كما في `/auth/login`): سقفٌ يعدّ النجاحات
    # يُقفل مشرفاً يعمل في يومٍ مزدحمٍ على مكتبين
    await rate_limit.reset(redis, f"totp:user:{user.id}")

    if used_recovery:
        remaining = await totp.remaining_recovery_codes(session, user.id)
        await notifications.publish_security_event(
            session,
            redis,
            user_id=user.id,
            kind="recovery_code_used",
            title="استُخدم رمز استرداد",
            body=f"دخلتَ اللوحة برمز استرداد. بقي {remaining} من رموزك.",
            data={"remaining": str(remaining)},
        )

    tokens = await _issue(session, redis, user)
    return AuthResponse(user=UserOut.model_validate(user), tokens=tokens)


# ------------------------------------------------- التحقق بعد الإنشاء


@router.post("/me/verify-phone", response_model=UserOut)
async def verify_my_phone(
    payload: VerifyPhoneRequest,
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
) -> UserOut:
    """يُثبت رقمَ حسابٍ قائم — لمن أُنشئ حسابه والمفتاح مطفأ.

    يطلبه التطبيق عند أول فرصة بعد إعادة تفعيل المفتاح، ويشترطه اعتمادُ
    الكبتن دائماً (SPEC القسم 13.2).
    """
    if user.phone_verified:
        return UserOut.model_validate(user)

    await verification.verify(
        session, redis, phone=user.phone, proof=payload.verification_token
    )
    verification.mark_verified(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


# ------------------------------------------------- استعادة كلمة المرور


@router.post("/password-reset/challenge", response_model=ChallengeResponse)
async def start_password_reset(
    payload: ChallengeRequest,
    session: DbSession,
    redis: RedisDep,
    ip: ClientIP,
) -> ChallengeResponse:
    """يبدأ تحدي الاستعادة — بسقفٍ يومي لكل رقم.

    **لا يكشف وجود الحساب**: الجواب واحد سواء أكان الرقم مسجّلاً أم لا،
    فمسارُ الاستعادة لا يصير عدّاداً للحسابات.
    """
    phone = await _resolve(payload.phone, payload.country_code)
    await _guard(
        redis,
        (
            f"password-reset:phone:{phone}",
            PASSWORD_RESET_DAILY_LIMIT,
            PASSWORD_RESET_WINDOW_SECONDS,
        ),
        (f"otp:ip:{ip}", OTP_IP_LIMIT, OTP_WINDOW_SECONDS),
    )

    # بابُ الاستعادة — وقالبُه قالبُها وحدَه (انظر التعليق في `/challenge`)
    challenge = await verification.challenge(
        session,
        redis,
        phone,
        channel=payload.channel,
        purpose=OtpTemplatePurpose.PASSWORD_RESET,
    )
    return ChallengeResponse(
        sent=challenge.sent,
        expires_in=challenge.expires_in,
        resend_after=challenge.resend_after,
        channel=challenge.channel,
    )


@router.post("/password-reset", response_model=AuthResponse)
async def reset_password(
    payload: PasswordResetRequest,
    session: DbSession,
    redis: RedisDep,
    ip: ClientIP,
) -> AuthResponse:
    """يُثبت الرقم ثم يكتب كلمةً جديدة ويُبطل كل الجلسات.

    **التحقق مطلوبٌ هنا دائماً** ولا يعفيه `otp_verification_enabled`: عفوُه
    يجعل إطفاء المفتاح طريقاً للاستيلاء على أي حساب بمجرد معرفة رقمه.

    والتوكنات تُصدر **بعد** كتابة الكلمة لا بعد التحقق: إثباتُ ملكية الرقم
    وحده لا يفتح جلسة، فلو انقطع الطلب بعده لم يبق للمهاجم شيء.
    """
    phone = await _resolve(payload.phone, payload.country_code)
    await _guard(
        redis,
        (
            f"password-reset:phone:{phone}",
            PASSWORD_RESET_DAILY_LIMIT,
            PASSWORD_RESET_WINDOW_SECONDS,
        ),
        (f"otp:ip:{ip}", OTP_IP_LIMIT, OTP_WINDOW_SECONDS),
    )

    await verification.verify(
        session, redis, phone=phone, proof=payload.verification_token
    )

    user = await session.scalar(select(User).where(User.phone == phone))
    if user is None:
        # بعد إثبات ملكية الرقم لم يعد الكشف تعداداً للحسابات: صاحب الطلب
        # يملك الرقم فعلاً، وإخفاءُ الحقيقة عنه إرباكٌ بلا فائدة
        raise NotFound("لا يوجد حساب بهذا الرقم")

    await set_password(session, redis, user=user, new_password=payload.new_password)
    # استعادةٌ ناجحة تُثبت الرقم أيضاً — أُثبِت للتوّ
    verification.mark_verified(user)
    await session.commit()
    await session.refresh(user)

    await rate_limit.reset(redis, f"password-reset:phone:{phone}")
    tokens = await _issue(session, redis, user)
    return AuthResponse(user=UserOut.model_validate(user), tokens=tokens)


# ------------------------------------------------------------- الجلسات


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest, session: DbSession, redis: RedisDep
) -> TokenPair:
    user_id, _ = await token_service.rotate_refresh_token(redis, payload.refresh_token)

    user = await session.get(User, user_id)
    if user is None or user.is_blocked:
        # حساب محذوف أو محظور: أبطل بقية جلساته أيضاً
        await token_service.revoke_all_for_user(redis, user_id)
        raise InvalidToken()

    return await _issue(session, redis, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, redis: RedisDep) -> None:
    await token_service.revoke_refresh_token(redis, payload.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


# ------------------------------------------- التحقق الثنائي (المرحلة 12-د)
#
# كلُّها `SecuritySelfUser` لا `StaffUser`: الحارسُ الذي يردّ المشرفَ المُلزَمَ
# بلا عامل يجب أن يستثني بابَ التسجيل نفسه، وإلا صار الإلزامُ حلقةً مغلقة —
# «سجّل عاملاً» على بابٍ لا يُفتح قبل تسجيل عامل. والاستثناءُ **تبعيّةٌ أخرى
# صريحة** لا مطابقةُ مسارٍ بالنصّ: مسارٌ يُطابَق باسمه يُنسى عند أول إعادة تسمية.


@router.get("/me/totp", response_model=TotpStatusOut)
async def totp_status(user: SecuritySelfUser, session: DbSession) -> TotpStatusOut:
    record = await totp.get_record(session, user.id)
    return TotpStatusOut(
        enrolled=record is not None,
        confirmed=bool(record and record.is_confirmed),
        confirmed_at=record.confirmed_at if record else None,
        recovery_verified_at=record.recovery_codes_verified_at if record else None,
        recovery_codes_remaining=await totp.remaining_recovery_codes(session, user.id),
        required=await security_settings.totp_required_for(session, user),
        session_idle_timeout_minutes=await security_settings.idle_timeout_minutes(
            session
        ),
    )


@router.post("/me/totp/enroll", response_model=TotpEnrollOut)
async def totp_enroll(user: SecuritySelfUser, session: DbSession) -> TotpEnrollOut:
    """يُنشئ سرّاً غيرَ مؤكَّدٍ ويردّه **مرةً واحدة**."""
    enrollment = await totp.enroll(session, user)
    await session.commit()
    return TotpEnrollOut(secret=enrollment.secret, uri=enrollment.uri)


@router.post("/me/totp/confirm", response_model=TotpConfirmOut)
async def totp_confirm(
    payload: TotpConfirmRequest, user: SecuritySelfUser, session: DbSession
) -> TotpConfirmOut:
    """يؤكّد العامل ويردّ رموزَ الاسترداد **مرةً واحدة**.

    **ولا تُبطَل الجلسات هنا، بخلاف الإطفاء** — والفرقُ اتجاهُ التغيير: الإطفاءُ
    يُضعف الحماية فتبقى جلساتٌ فُتحت بسياسةٍ أقوى، والتأكيدُ يقوّيها وكلمةُ
    المرور التي فتحت الجلسة لم تتبدّل. وإخراجُ صاحبها لا يحمي شيئاً: التوكنُ
    الحاليُّ لا يُبطَل قبل انتهائه أصلاً (القسم 14)، فالإبطالُ يقتل تجديدَه
    وحده — خروجٌ صامتٌ بعد ربع ساعة، ومعه رمزُ الخطوة المحروقة للتوّ في التأكيد
    يجعل أول دخولٍ يبدو رفضاً.
    """
    codes = await totp.confirm(session, user, payload.code)
    await session.commit()

    record = await totp.get_record(session, user.id)
    return TotpConfirmOut(confirmed_at=record.confirmed_at, recovery_codes=codes)


@router.post("/me/totp/recovery/verify", response_model=TotpStatusOut)
async def totp_verify_recovery(
    payload: TotpRecoveryVerifyRequest, user: SecuritySelfUser, session: DbSession
) -> TotpStatusOut:
    """يُثبت أن الاسترداد يعمل **باستهلاك رمزٍ حقيقي** — شرطُ إشعال الإلزام."""
    remaining = await totp.verify_recovery_works(session, user, payload.recovery_code)
    await session.commit()

    record = await totp.get_record(session, user.id)
    return TotpStatusOut(
        enrolled=True,
        confirmed=True,
        confirmed_at=record.confirmed_at,
        recovery_verified_at=record.recovery_codes_verified_at,
        recovery_codes_remaining=remaining,
        required=await security_settings.totp_required_for(session, user),
        session_idle_timeout_minutes=await security_settings.idle_timeout_minutes(
            session
        ),
    )


@router.delete("/me/totp", status_code=status.HTTP_204_NO_CONTENT)
async def totp_disable(
    payload: TotpDisableRequest,
    user: SecuritySelfUser,
    session: DbSession,
    redis: RedisDep,
) -> None:
    """يُطفئ العامل **بكلمةِ المرور وعاملٍ حاضرٍ معاً** — ويُرفض وقتَ الإلزام.

    **وكلمةُ المرور تُفحص أولاً وبرسالةٍ لا تفرّق**: «كلمةُ المرور أو الرمز غيرُ
    صحيح» — فمن يجرّب لا يعرف أيَّهما أصاب، وهي قاعدةُ الدخول نفسُها مطبَّقةً
    على بابٍ يُنقص الحماية.
    """
    if await security_settings.totp_required_for(session, user):
        raise TotpEnforcementActive()

    # **ما يعرفه قبل ما يملكه**: جلسةٌ مسروقةٌ على شاشةٍ مفتوحةٍ تملك الثانيَ
    # ولا تملك الأول، وهي الحالُ التي يوجد هذا الشرطُ لأجلها.
    if not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise InvalidCredentials()

    await totp.disable(
        session, user, code=payload.code, recovery_code=payload.recovery_code
    )
    await session.commit()
    await token_service.revoke_all_for_user(redis, user.id)

    await notifications.publish_security_event(
        session,
        redis,
        user_id=user.id,
        kind="totp_disabled",
        title="أُطفئ التحقق الثنائي",
        body="أُطفئ التحقق الثنائي على حسابك. إن لم تكن أنت من فعل، راجع الإدارة فوراً.",
    )


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: ProfileUpdate, user: CurrentUser, session: DbSession
) -> UserOut:
    """ما يغيّره صاحبُ الحساب في نفسه (المرحلة 10-ج).

    **والكبتن لا يكتب جنسه هنا**: يضبطه المشرف من هويته المرفوعة، وبغير هذا
    الحارس يصير «سائقة للنساء» حقلاً يملؤه من يشاء. أما تفضيلُه فمكانه
    `PATCH /drivers/me` — تفضيلٌ دائم لا اختيارُ رحلة.
    """
    if payload.gender is not None:
        # **أسبقيةٌ معلَنة، لا خطأٌ مسمّى** (قرارُ المالك 2026-08-19، SPEC §21.3):
        # ختمُ المشرف يغلب دائماً حين يوجد، أياً كانت أدوارُ الحساب الأخرى.
        # وهذا مسارُ **أمان** لا مسارُ مال: الصياحُ هنا يوقف امرأةً عن استعمال
        # الخدمة النسائية، والغيابُ يفتح ما هو أخطر — كبتنٌ يعلن عن نفسه خلافَ
        # ما ثبّته المشرف ليصل إلى ما ليس له. والقيمةُ الآمنةُ موجودةٌ وقاطعة،
        # فلا تخمينَ أصلاً. ويُقرأ **الختم** لا الدور: من يحمل دورَ الكبتن بلا
        # ختمٍ لم يُثبَّت جنسُه بعد، فإعلانُه عن نفسه يقيّد رحلتَه هو وحدَها.
        if user.has_role(UserRole.DRIVER) or user.gender_verified_at is not None:
            raise InvalidInput("جنس الكبتن يثبّته المشرف من الهوية")
        # إعلانُ الراكبة بلا ختم — والختمُ شرطُ جانب الكبتن وحده
        user.gender = payload.gender
    if payload.ride_gender_preference is not None:
        user.ride_gender_preference = payload.ride_gender_preference

    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


# ------------------------------------------------------- التبديل بين التطبيقين


@router.post("/handoff", response_model=HandoffToken)
async def start_handoff(
    payload: HandoffStart,
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
) -> HandoffToken:
    """يفتح تسليمَ جلسةٍ إلى التطبيق الآخر — **لمن يملك دورَه وحدَه**.

    والحارسُ هنا هو `app_scope` نفسُه لا حارسٌ ثانٍ: من لا يملك دورَ الهدف
    يُرفض بنفس الرسالة التي تقول **أين يذهب**. ولا يمنح الرمزُ دوراً — يُفحص
    قبل إصداره ويُفحص ثانيةً عند المبادلة، فسحبُ الدور بينهما يُبطله.
    """
    app_scope.guard(user.roles, payload.target)

    # **ولا تبديلَ أثناء عملٍ قائم** — والفحصُ هنا لا في الشاشة: شرطٌ في
    # الواجهة يزول بتعديل ملفٍ في المتصفح، وثمنُه راكبٌ ينتظر كبتناً بدّل تطبيقَه
    if await rides_service.has_any_active_ride(session, user):
        raise HandoffBlockedByActiveWork()

    token = await handoff.issue(redis, user_id=user.id, target=payload.target)
    return HandoffToken(token=token, expires_in=handoff.TOKEN_TTL_SECONDS)


@router.post("/handoff/exchange", response_model=AuthResponse)
async def exchange_handoff(
    payload: HandoffExchange, session: DbSession, redis: RedisDep
) -> AuthResponse:
    """يبادل رمزَ التسليم بجلسةٍ في التطبيق المستقبِل.

    **ولا كلمةَ مرورٍ ولا رمزَ تحقق**: صاحبُ الرمز أثبت هويّتَه في التطبيق الذي
    أصدره قبل ثوانٍ. **والفحصُ يُعاد كاملاً** — الحسابُ يُقرأ من القاعدة،
    والحظرُ يُقرأ، و`app_scope` يُسأل ثانيةً: رمزٌ صدر ثم سُحب دورُ صاحبه لا
    يفتح شيئاً.
    """
    user_id = await handoff.consume(redis, token=payload.token, target=payload.app)

    user = await session.get(User, user_id)
    if user is None or user.is_blocked:
        raise InvalidToken("تعذّر التبديل — أعد الدخول")

    app_scope.guard(user.roles, payload.app)
    tokens = await _issue(session, redis, user)
    return AuthResponse(user=UserOut.model_validate(user), tokens=tokens)
