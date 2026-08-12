"""التحقق الثنائي لدخول اللوحة — TOTP (SPEC القسم 14.1، المرحلة 12-د).

**TOTP لا SMS** (قرارُ المالك): مجانيٌّ، ولا ينتظر عقدَ مزوّد، وأقوى من رمزٍ
يمشي في شبكةٍ يمكن تحويلُ رقمها. وهو **للوحة وحدها**: مساراتُه لطاقم اللوحة،
وعاملٌ ثانٍ للراكب قرارُ منتجٍ بكلفةِ دعمٍ حقيقية ولا يطلبه القسم 14.

**ولا تبعيّةَ جديدة**: RFC 4226/6238 خمسةَ عشرَ سطراً من `hmac` و`struct`
القياسيّتين، وهو نفسُ ما فعله المشروع مع `firebase_auth` بدل `firebase-admin`
(القسم 15/أ). حزمةٌ لأجل `hmac.new(...).digest()` تبعيّةٌ بلا مقابل، ورفعُها
يعني إعادةَ بناء صورة الحاوية لا `restart` — وهو خطأٌ وقع في المشروع مرة.

ثلاث قواعد يحملها هذا الملف، وكلٌّ منها حرسٌ لا تجميل:

- **السرُّ يُشفَّر ولا يُهشَّم** (التحقق يقرؤه)، **ورموزُ الاسترداد تُهشَّم ولا
  تُشفَّر** (التحقق يقارنها). التفصيل في `models/totp.py`.
- **رمزٌ قُبِل مرةً لا يُقبل ثانية**: `last_step` يُكتب **تحت قفل الصف**، فمن
  قرأ الرمز من فوق كتف صاحبه لا يملك ثلاثين ثانيةً يستعمله فيها.
- **ورمزُ الاسترداد يُستهلك تحت قفل صفّه** بعد استعلامٍ مفهرسٍ عن بصمته: قفلُ
  الصفِّ الواحد لا مسحُ عشرةٍ تحت قفل.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import settings
from app.core.crypto import get_cipher
from app.core.exceptions import (
    InvalidInput,
    InvalidToken,
    InvalidTotpCode,
    RateLimited,
    TotpAlreadyEnrolled,
    TotpNotEnrolled,
)
from app.models.enums import AuditAction
from app.models.totp import UserRecoveryCode, UserTotp
from app.models.user import User
from app.services import audit

# ---------------------------------------------------------------- ثوابت

DIGITS = 6
PERIOD_SECONDS = 30
# انحرافُ خطوةٍ واحدةٍ في كل اتجاه (±٣٠ث): ساعةُ حاسوبٍ مكتبيٍّ تنحرف، وتوسيعُ
# النافذة يضاعف عمرَ الرمز المسروق
SKEW_STEPS = 1
SECRET_BYTES = 20  # ما توصي به RFC 4226 لـ HMAC-SHA1

ISSUER = "TAXO"

# عشرةُ رموزٍ — عددٌ يكفي لسنواتٍ من هاتفٍ مفقودٍ ولا يُغري بحفظها في ملف
RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_LENGTH = 10
# أبجديةٌ بلا `I O U L 1 0` — الرمزُ يُنسخ بيدٍ ويُقرأ من ورقة، والحرفُ الذي
# يُقرأ رقماً يجعل رمزاً صحيحاً يبدو خاطئاً
RECOVERY_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"

CHALLENGE_TTL_SECONDS = 300
CHALLENGE_MAX_ATTEMPTS = 5
# سقفٌ ثانٍ فوق سقف التحدي: تحدياتٌ متتابعةٌ من كلماتِ مرورٍ صحيحةٍ لا يحدّها
# الأولُ وحده. **ولا قفلَ للحساب**: قفلُ حسابِ مشرفٍ بالمحاولات الخاطئة بابُ
# تعطيلٍ يدفعه من يخمّن سيئاً
USER_ATTEMPT_LIMIT = 20
USER_ATTEMPT_WINDOW_SECONDS = 3600

_CHALLENGE_KEY = "totp:challenge:{token}"


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------- الرمز نفسه (RFC 6238)


def generate_secret() -> str:
    """سرٌّ عشوائيٌّ بترميز base32 بلا حشو — الصيغةُ التي تقرؤها التطبيقات."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode().rstrip("=")


def _secret_bytes(secret: str) -> bytes:
    padded = secret + "=" * (-len(secret) % 8)
    try:
        return base64.b32decode(padded, casefold=True)
    except (ValueError, TypeError) as exc:  # pragma: no cover - سرٌّ تالف
        raise InvalidInput("سرُّ التحقق الثنائي غير صالح") from exc


def code_at(secret: str, step: int) -> str:
    """HOTP لخطوةٍ بعينها (RFC 4226 §5.3) — والـTOTP هو هذا بعدّادِ الزمن."""
    digest = hmac.new(
        _secret_bytes(secret), struct.pack(">Q", step), hashlib.sha1
    ).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{truncated % (10 ** DIGITS):0{DIGITS}d}"


def current_step(at: datetime | None = None) -> int:
    moment = at or _now()
    return int(moment.timestamp()) // PERIOD_SECONDS


def match_step(secret: str, code: str, *, at: datetime | None = None) -> int | None:
    """الخطوةُ التي يوافقها الرمز داخل نافذة الانحراف، أو `None`.

    المقارنة بزمنٍ ثابت (`compare_digest`) كما في `services/otp.py`: فرقُ
    الأزمنة في مقارنةِ نصٍّ يسرّب الأرقام الأولى من الرمز.
    """
    cleaned = code.strip().replace(" ", "")
    if len(cleaned) != DIGITS or not cleaned.isdigit():
        return None
    now_step = current_step(at)
    for offset in range(-SKEW_STEPS, SKEW_STEPS + 1):
        step = now_step + offset
        if hmac.compare_digest(code_at(secret, step), cleaned):
            return step
    return None


def provisioning_uri(secret: str, *, phone: str) -> str:
    """`otpauth://` كما تقرؤه تطبيقات المصادقة — واللوحةُ ترسمه QR **محلياً**.

    خدمةُ QR خارجيةٌ تعني إرسالَ السرِّ إلى طرفٍ ثالث؛ وهي أسهلُ خطأٍ في هذه
    الميزة كلها.
    """
    label = f"{ISSUER}:{phone}"
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={ISSUER}"
        f"&algorithm=SHA1&digits={DIGITS}&period={PERIOD_SECONDS}"
    )


# --------------------------------------------------------- رموز الاسترداد


def _recovery_digest(code: str) -> str:
    """بصمةُ HMAC بمفتاح الخدمة — نسخةُ القاعدة وحدها لا تكفي للتحقق."""
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        normalize_recovery_code(code).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def normalize_recovery_code(code: str) -> str:
    """يقبل ما يكتبه الإنسان: شرطاتٌ ومسافاتٌ وحروفٌ صغيرة."""
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _generate_recovery_code() -> str:
    body = "".join(
        secrets.choice(RECOVERY_ALPHABET) for _ in range(RECOVERY_CODE_LENGTH)
    )
    half = RECOVERY_CODE_LENGTH // 2
    return f"{body[:half]}-{body[half:]}"


# ------------------------------------------------------------ قراءة الصف


async def get_record(
    session: AsyncSession, user_id: uuid.UUID, *, for_update: bool = False
) -> UserTotp | None:
    stmt = select(UserTotp).where(UserTotp.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(stmt)


async def has_confirmed_factor(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """هل لصاحب الحساب عاملٌ **مؤكَّد**؟ تسجيلٌ نصفُ منتهٍ ليس عاملاً."""
    return (
        await session.scalar(
            select(UserTotp.id).where(
                UserTotp.user_id == user_id, UserTotp.confirmed_at.is_not(None)
            )
        )
    ) is not None


@dataclass(frozen=True, slots=True)
class Enrollment:
    """ما يُعرض مرةً واحدةً ولا يُقرأ بعدها من أي مسار."""

    secret: str
    uri: str


# ---------------------------------------------------------- التسجيل والتأكيد


async def enroll(session: AsyncSession, user: User) -> Enrollment:
    """يُنشئ سرّاً **غيرَ مؤكَّد** ويردّه مرةً واحدة.

    وإعادةُ التسجيل تكتب فوق سرٍّ غيرِ مؤكَّد ولا تلمس مؤكَّداً: من يريد تبديلَ
    هاتفه يُطفئ عاملَه برمزٍ حاضر ثم يسجّل — وإلا كان «أعد التسجيل» طريقاً
    لتبديل العامل من جلسةٍ مسروقة بلا رمزٍ واحد.
    """
    record = await get_record(session, user.id, for_update=True)
    if record is not None and record.is_confirmed:
        raise TotpAlreadyEnrolled()

    secret = generate_secret()
    envelope = get_cipher().encrypt({"secret": secret})
    if record is None:
        record = UserTotp(user_id=user.id, secret_encrypted=envelope)
        session.add(record)
    else:
        record.secret_encrypted = envelope
        record.last_step = None

    await audit.record(
        session,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="user_totp",
        entity_id=user.id,
        details={"stage": "enroll"},
    )
    return Enrollment(secret=secret, uri=provisioning_uri(secret, phone=user.phone))


def _secret_of(record: UserTotp) -> str:
    return get_cipher().decrypt(record.secret_encrypted)["secret"]


async def confirm(session: AsyncSession, user: User, code: str) -> list[str]:
    """يختم `confirmed_at` ويولّد عشرةَ رموز استردادٍ **تُعرض مرةً واحدة**.

    ولا مسارَ يعيد قراءتها ولا قراءةَ السرِّ بعد هذه اللحظة: مسارٌ يعرض السرَّ
    ثانيةً يجعل جلسةً مسروقةً كافيةً لاستخراج العامل الذي وُضع ضدها.
    """
    record = await get_record(session, user.id, for_update=True)
    if record is None:
        raise TotpNotEnrolled("ابدأ بتسجيل التحقق الثنائي")
    if record.is_confirmed:
        raise TotpAlreadyEnrolled("التحقق الثنائي مؤكَّدٌ على هذا الحساب")

    step = match_step(_secret_of(record), code)
    if step is None:
        raise InvalidTotpCode()

    record.confirmed_at = _now()
    record.last_step = step

    # رموزُ الاسترداد تُولَّد مع التأكيد لا مع التسجيل: تسجيلٌ لم يُؤكَّد قد
    # يُعاد، ورموزٌ كُتبت له تبقى صالحةً لسرٍّ لم يعد موجوداً
    await _replace_recovery_codes(session, user.id)
    codes = [_generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    for code_value in codes:
        session.add(
            UserRecoveryCode(user_id=user.id, code_hash=_recovery_digest(code_value))
        )

    await audit.record(
        session,
        actor=user,
        action=AuditAction.ACTIVATE,
        entity_type="user_totp",
        entity_id=user.id,
        details={"stage": "confirm", "recovery_codes": RECOVERY_CODE_COUNT},
    )
    return codes


async def _replace_recovery_codes(session: AsyncSession, user_id: uuid.UUID) -> None:
    existing = (
        await session.scalars(
            select(UserRecoveryCode).where(UserRecoveryCode.user_id == user_id)
        )
    ).all()
    for row in existing:
        await session.delete(row)


# ------------------------------------------------------------ التحقق منه


async def verify_code(session: AsyncSession, *, user_id: uuid.UUID, code: str) -> None:
    """يتحقق من رمزٍ لعاملٍ مؤكَّد ويحرقه — يرفع `InvalidTotpCode` وإلا.

    **القفل قبل الفحص** كما تفرض قاعدة المشروع على كل انتقالِ حالة: `last_step`
    حالةٌ تُقرأ ثم تُكتب، فنداءان متزامنان بنفس الرمز يقرآن الخطوةَ نفسها
    ويمرّان معاً — وذاك هو تكرارُ الاستعمال الذي وُضع العمودُ لمنعه.
    """
    record = await get_record(session, user_id, for_update=True)
    if record is None or not record.is_confirmed:
        raise TotpNotEnrolled()

    step = match_step(_secret_of(record), code)
    if step is None:
        raise InvalidTotpCode()
    if record.last_step is not None and step <= record.last_step:
        # رمزٌ صحيحٌ سبق استعمالُه — ونصُّ الخطأ نفسُه: من يعرف أن رمزَه
        # «مستعمَل» يعرف أنه كان صحيحاً
        raise InvalidTotpCode()

    record.last_step = step


async def consume_recovery_code(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    code: str,
    actor: User | None = None,
) -> UserRecoveryCode:
    """يستهلك رمزَ استردادٍ **مرةً واحدة** — القفلُ على صفِّه هو ما يضمن ذلك.

    الاستعلامُ عن البصمة مفهرس، فالقفلُ يقع على الصفِّ الواحد لا على عشرةٍ
    تُقارن تحته. وبحذف `with_for_update` يمرّ نداءان ببصمةٍ واحدة فيُقبل رمزُ
    «المرةِ الواحدة» مرتين — وهو ما يفشل به `test_totp_concurrency.py`.
    """
    digest = _recovery_digest(code)
    row = await session.scalar(
        select(UserRecoveryCode)
        .where(
            UserRecoveryCode.user_id == user_id,
            UserRecoveryCode.code_hash == digest,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or row.is_used:
        raise InvalidTotpCode("رمز الاسترداد غير صحيح أو سبق استعماله")

    row.used_at = _now()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="user_recovery_code",
        entity_id=user_id,
        details={"stage": "consumed"},
    )
    return row


async def remaining_recovery_codes(session: AsyncSession, user_id: uuid.UUID) -> int:
    """كم رمزاً بقي — **بعد flush صريح**.

    جلساتُ المشروع `autoflush=False` (انظر `core/db.py`)، فرمزٌ استُهلك للتوّ في
    نفس المعاملة لا يظهر مستهلَكاً لاستعلامٍ بعده. والرقمُ يُعرض لصاحبه ويُكتب
    في إشعاره، فعدٌّ متأخّرٌ بواحدٍ يخبره أن رمزاً لم يُستهلك وقد استُهلك.
    """
    await session.flush()
    rows = (
        await session.scalars(
            select(UserRecoveryCode.id).where(
                UserRecoveryCode.user_id == user_id,
                UserRecoveryCode.used_at.is_(None),
            )
        )
    ).all()
    return len(rows)


async def verify_recovery_works(session: AsyncSession, user: User, code: str) -> int:
    """يُثبت أن الاسترداد يعمل — **باستهلاك رمزٍ حقيقي** (قرارُ المالك).

    إثباتٌ يُجرَّب لا مربَّعٌ يُؤشَّر: يكلّف واحداً من عشرة، ويخبر صاحبَه أن ما
    نسخه هو ما تحفظه القاعدة فعلاً. وهذا الختمُ شرطُ إشعال مفتاح الإلزام.
    """
    record = await get_record(session, user.id, for_update=True)
    if record is None or not record.is_confirmed:
        raise TotpNotEnrolled()

    await consume_recovery_code(session, user_id=user.id, code=code, actor=user)
    record.recovery_codes_verified_at = _now()
    await audit.record(
        session,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="user_totp",
        entity_id=user.id,
        details={"stage": "recovery_verified"},
    )
    return await remaining_recovery_codes(session, user.id)


async def disable(
    session: AsyncSession,
    user: User,
    *,
    code: str | None = None,
    recovery_code: str | None = None,
) -> None:
    """يُطفئ العامل — **بعاملٍ حاضرٍ لا بجلسةٍ وحدها**.

    جلسةٌ مسروقة تُسقط العاملَ الذي وُضع لأجلها إن كفى وجودُها؛ فالإطفاءُ يطلب
    رمزَ اللحظة أو رمزَ استرداد. ومن رفض الإلزامُ إطفاءه فمخرجُه المشرفُ الأعلى
    أو أمرُ `scripts/totp_reset.py` — لا نداءٌ من داخل اللوحة.
    """
    record = await get_record(session, user.id, for_update=True)
    if record is None or not record.is_confirmed:
        raise TotpNotEnrolled()

    if recovery_code:
        await consume_recovery_code(
            session, user_id=user.id, code=recovery_code, actor=user
        )
    elif code:
        await verify_code(session, user_id=user.id, code=code)
    else:
        raise InvalidInput("مطلوب رمزٌ حاضرٌ أو رمزُ استرداد لإطفاء التحقق الثنائي")

    await _replace_recovery_codes(session, user.id)
    await session.delete(record)
    await audit.record(
        session,
        actor=user,
        action=AuditAction.DEACTIVATE,
        entity_type="user_totp",
        entity_id=user.id,
    )


# ------------------------------------------------------- تحدّي الدخول


@dataclass(frozen=True, slots=True)
class LoginChallenge:
    token: str
    expires_in: int


async def start_challenge(redis: Redis, user: User) -> LoginChallenge:
    """يفتح تحدياً بعد كلمة مرورٍ صحيحة — **بلا توكنٍ ولا نصفِ جلسة**.

    قيمةٌ عشوائيةٌ مفتاحُها في Redis مربوطٌ بالمستخدم، لخمس دقائق، تُستهلَك
    مرةً واحدة، ولا تفتح أيَّ مسار. ورمزٌ مكانه `sub` في توكنٍ حقيقيٍّ «ناقصِ
    صلاحية» يصير جلسةً كاملةً بخطأٍ واحدٍ في حارسٍ واحد.
    """
    token = secrets.token_urlsafe(32)
    await redis.set(
        _CHALLENGE_KEY.format(token=token), str(user.id), ex=CHALLENGE_TTL_SECONDS
    )
    return LoginChallenge(token=token, expires_in=CHALLENGE_TTL_SECONDS)


async def resolve_challenge(redis: Redis, token: str) -> uuid.UUID:
    raw = await redis.get(_CHALLENGE_KEY.format(token=token))
    if raw is None:
        raise InvalidToken("انتهت مهلة التحقق الثنائي — أعد الدخول")
    try:
        return uuid.UUID(raw if isinstance(raw, str) else raw.decode())
    except ValueError as exc:  # pragma: no cover - قيمةٌ تالفة
        raise InvalidToken() from exc


async def guard_attempt(redis: Redis, token: str, user_id: uuid.UUID) -> None:
    """سقفان: على التحدي (خمسٌ ثم يُهدَم) وعلى الحساب في الساعة."""
    per_user = await rate_limit.hit(
        redis,
        f"totp:user:{user_id}",
        limit=USER_ATTEMPT_LIMIT,
        window_seconds=USER_ATTEMPT_WINDOW_SECONDS,
    )
    if not per_user.allowed:
        await drop_challenge(redis, token)
        raise RateLimited(retry_after=per_user.retry_after)

    per_challenge = await rate_limit.hit(
        redis,
        f"totp:challenge:{token}",
        limit=CHALLENGE_MAX_ATTEMPTS,
        window_seconds=CHALLENGE_TTL_SECONDS,
    )
    if not per_challenge.allowed:
        # التحدي يُهدَم فيعود صاحبُه إلى كلمة المرور — ولا يُقفل حسابُه
        await drop_challenge(redis, token)
        raise RateLimited(retry_after=per_challenge.retry_after)


async def drop_challenge(redis: Redis, token: str) -> None:
    await redis.delete(_CHALLENGE_KEY.format(token=token))
    await rate_limit.reset(redis, f"totp:challenge:{token}")


__all__ = [
    "CHALLENGE_MAX_ATTEMPTS",
    "CHALLENGE_TTL_SECONDS",
    "DIGITS",
    "Enrollment",
    "LoginChallenge",
    "PERIOD_SECONDS",
    "RECOVERY_CODE_COUNT",
    "code_at",
    "confirm",
    "consume_recovery_code",
    "current_step",
    "disable",
    "drop_challenge",
    "enroll",
    "generate_secret",
    "get_record",
    "guard_attempt",
    "has_confirmed_factor",
    "match_step",
    "normalize_recovery_code",
    "provisioning_uri",
    "remaining_recovery_codes",
    "resolve_challenge",
    "start_challenge",
    "verify_code",
    "verify_recovery_works",
]
