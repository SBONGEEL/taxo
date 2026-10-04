"""جلساتُ الدخول — **تبقى حتى يخرج صاحبُها** (SPEC §60، قرارُ المالك ٢٠٢٦-١٠-٠٤).

**الجلسةُ صفٌّ في `auth_sessions` لا مفتاحٌ في Redis**: Redis للحدود والحضور،
وسقوطُه كان يُخرج الجميع. **ولا عمرَ لها ولا مهلةَ خمول** — تنتهي بفعلٍ لا
بساعة: الخروج، وإنهاءُ الكلّ، وتغييرُ كلمة المرور واستعادتُها، وطلبُ الحذف،
وإطفاءُ العامل الثاني، والحظر، **وعودةُ رمزٍ مستهلَك**.

**والتدويرُ باقٍ** («جلساتٌ طويلةٌ تدور بأمان» بنصِّ القرار): رمزُ التجديد
يُستهلك مرّةً ويُستبدل. **ومهلةُ سماحٍ قصيرة** (`GRACE`) لمن قدّم الرمزَ الذي
استُبدل للتوّ — جوابٌ ضاع في الشبكة، أو تبويبان جدّدا في اللحظة نفسِها — **فيُعطى
الرمزَ الحاليَّ نفسَه مُعاداً سكُّه حرفاً**، لا رمزاً ثالثاً يفرّع السلسلة. ومن
قدّم أقدمَ منه **أُبطلت الجلسةُ كلُّها**: مستهلَكٌ يعود علامةُ سرقة، والإبطالُ
يقتل نسختَي اللصّ وصاحبِ الحساب معاً، فيعود صاحبُه بكلمة مروره ولا يعود اللصّ.

**وتوكنُ الوصول يحمل `sid` ويُسأل عنها في كلِّ طلب** (`authenticate_access`)
— فالخروجُ وإنهاءُ الكلّ يسريان عند الطلب التالي لا بعد انتهاء التوكن.

**وكلُّ تغييرٍ لحال صفٍّ يقفله أوّلاً** (`FOR UPDATE` قبل الفحص)، ولا يدخل ترتيبَ
الأقفال: لا رحلةَ ولا دفعَ ولا محفظةَ في هذه المسارات.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import InvalidToken
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.auth_session import AuthSession
from app.models.device import DeviceToken
from app.models.enums import UserRole
from app.models.security_setting import DEFAULT_IDLE_TIMEOUT_MINUTES
from app.models.user import User
from app.schemas.auth import TokenPair

#: مهلةُ السماح للرمز الذي استُبدل للتوّ — تجديدان متزامنان بينهما أجزاءُ ثانية،
#: وإعادةُ جوابٍ ضاع ثوانٍ. **وأطولُ منها بابٌ لِلِصٍّ بنسخةٍ قديمة.**
GRACE = timedelta(seconds=60)

#: **غيابُ حساب الطوارئ** — فجوةٌ بين تجديدين تعني أنه عاد بعد غياب، فيصيح
#: (`admin_credentials.note_resume`). **ومقدارُها مهلةُ خمول اللوحة قبل §60 فوق عمر
#: توكن الوصول**: من يعمل يجدّد كلَّ عمرِ توكن، فما زاد عليه بنصف ساعةٍ غيابٌ حقيقيّ
#: — **وهي الفجوةُ التي كانت تُسقط الجلسةَ فيُعاد الدخولُ ويُكتب الصياح**.
BREAK_GLASS_RESUME_GAP = timedelta(
    minutes=DEFAULT_IDLE_TIMEOUT_MINUTES + settings.access_token_expire_minutes
)

#: أسبابُ الإبطال — نصٌّ قصيرٌ في `auth_sessions.revoked_reason`
REVOKE_LOGOUT = "logout"
REVOKE_ALL = "logout_all"
REVOKE_REUSE = "reuse_detected"
REVOKE_ACCOUNT = "account_inactive"
REVOKE_PASSWORD_CHANGED = "password_changed"
REVOKE_PASSWORD_RESET = "password_reset"
REVOKE_DELETION = "account_deletion"
REVOKE_TWO_FACTOR_OFF = "two_factor_disabled"
REVOKE_TOTP_RESET = "totp_reset"

# **مفاتيحُ ما قبل §60** — رموزٌ صدرت وجلستُها مفتاحٌ في Redis. تُقبل مرّةً عند
# أوّل تجديدٍ وتصير صفّاً (`_adopt_legacy`)، **فالتحويلُ لا يُخرج أحداً**.
_LEGACY_PREFIX = "auth:refresh"

_GONE = "جلسة منتهية أو أُبطلت مسبقاً"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _second(moment: datetime) -> datetime:
    """**بالثانية** — `iat` عددٌ صحيح، والرمزُ يُعاد سكُّه منه حرفاً."""
    return moment.replace(microsecond=0)


def _pair(user: User, auth: AuthSession) -> TokenPair:
    access, _, access_expires = create_access_token(
        str(user.id),
        {
            "role": user.role.value,
            "country": user.country_code.value,
            "sid": str(auth.id),
        },
    )
    refresh, _, _ = create_refresh_token(
        str(user.id),
        sid=str(auth.id),
        jti=auth.current_jti,
        issued_at=auth.current_issued_at,
    )
    return TokenPair(
        access_token=access, refresh_token=refresh, expires_at=access_expires
    )


async def issue_token_pair(session: AsyncSession, user: User) -> TokenPair:
    """جلسةٌ جديدةٌ وزوجُها الأوّل — **والصفُّ يُلتزم هنا**: رمزٌ يُسلَّم لجلسةٍ لم
    تُكتب يرتدّ عند أوّل طلب. وكلُّ بابٍ يناديه التزم ما قبله أصلاً."""
    now = _second(_now())
    auth = AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        current_jti=uuid.uuid4().hex,
        current_issued_at=now,
        last_used_at=now,
    )
    session.add(auth)
    await session.commit()
    return _pair(user, auth)


def _inactive(user: User | None) -> bool:
    return user is None or user.is_blocked or user.deactivated_at is not None


async def _locked(session: AsyncSession, sid: uuid.UUID) -> AuthSession | None:
    return await session.scalar(
        select(AuthSession)
        .where(AuthSession.id == sid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def rotate(
    session: AsyncSession, redis: Redis, refresh_token: str
) -> tuple[User, TokenPair]:
    """التجديد — **يقفل الصفَّ ثم يفحص**، ويُعيد زوجاً جديداً.

    - الرمزُ الحاليّ ⇒ يُستهلك ويُكتب غيرُه.
    - الرمزُ السابقُ في مهلة السماح ⇒ **الرمزُ الحاليُّ نفسُه** (لا تغييرَ في الصفّ).
    - ما عدا ذلك ⇒ **علامةُ سرقة**: تُبطل الجلسةُ كلُّها ويُرفض.
    - حسابٌ محظورٌ أو مُغلَق ⇒ تُبطل كلُّ جلساته ويُرفض (كما كان).
    """
    try:
        payload = decode_token(refresh_token, "refresh")
    except TokenError as exc:
        raise InvalidToken() from exc

    if not payload.get("sid"):
        return await _adopt_legacy(session, redis, payload)

    try:
        sid = uuid.UUID(payload["sid"])
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise InvalidToken() from exc

    auth = await _locked(session, sid)
    if auth is None or auth.user_id != user_id:
        raise InvalidToken()
    if auth.revoked_at is not None:
        raise InvalidToken(_GONE)

    now = _now()
    jti = payload["jti"]
    if jti == auth.current_jti:
        auth.previous_jti = auth.current_jti
        auth.current_jti = uuid.uuid4().hex
        auth.current_issued_at = _second(now)
    elif jti == auth.previous_jti and now - auth.current_issued_at <= GRACE:
        pass  # **الحاليُّ نفسُه يُعاد سكُّه** — لا فرعَ ثالث في السلسلة
    else:
        auth.revoked_at = now
        auth.revoked_reason = REVOKE_REUSE
        await session.commit()
        await kick(redis, user_id, sid=sid)
        raise InvalidToken(_GONE)

    user = await session.get(User, user_id)
    if _inactive(user):
        # حسابٌ محذوفٌ أو محظور: تُبطل بقيةُ جلساته أيضاً — كما كان قبل §60
        await revoke_all_for_user(session, redis, user_id, reason=REVOKE_ACCOUNT)
        await session.commit()
        await kick(redis, user_id)
        raise InvalidToken()

    assert user is not None
    if now - auth.last_used_at > BREAK_GLASS_RESUME_GAP and user.has_role(
        UserRole.ADMIN, UserRole.SUPPORT
    ):
        from app.services import admin_credentials

        await admin_credentials.note_resume(session, user)
    auth.last_used_at = now
    await session.commit()
    return user, _pair(user, auth)


async def _adopt_legacy(
    session: AsyncSession, redis: Redis, payload: dict
) -> tuple[User, TokenPair]:
    """**رمزٌ صدر قبل §60** — بلا `sid` ومفتاحُه في Redis. يُقبل **مرّةً** إن كان
    مفتاحُه حيّاً، ويُستهلك، ويصير جلسةً في القاعدة. وعمرُه القديمُ (`exp`)
    فحصه `decode_token` قبل الوصول إلى هنا."""
    subject = payload["sub"]
    deleted = await redis.delete(f"{_LEGACY_PREFIX}:{subject}:{payload['jti']}")
    if not deleted:
        raise InvalidToken(_GONE)
    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise InvalidToken() from exc
    user = await session.get(User, user_id)
    if _inactive(user):
        await revoke_all_for_user(session, redis, user_id, reason=REVOKE_ACCOUNT)
        await session.commit()
        await kick(redis, user_id)
        raise InvalidToken()
    assert user is not None
    return user, await issue_token_pair(session, user)


async def revoke_session(
    session: AsyncSession, redis: Redis, refresh_token: str
) -> None:
    """الخروج — **يُنهي الجلسةَ على الخادم** لا على الجهاز وحدَه (§60-ب/٢).

    **ومعه رمزُ الحضور** (§23.4): من سجّل خروجَه لا يبقى جهازُه يبثّ موقعَه.
    **وأيُّ رمزٍ من الجلسة يكفي لإنهائها**، حاليّاً كان أو أقدم: الإنهاءُ يضيّق ولا
    يوسّع. ورمزٌ تالفٌ يُعامل كأنه أُبطل — الخروجُ عمليةٌ لا تفشل.
    """
    try:
        payload = decode_token(refresh_token, "refresh")
    except TokenError:
        return

    subject = payload["sub"]
    sid_raw = payload.get("sid")
    if sid_raw:
        try:
            sid = uuid.UUID(sid_raw)
        except ValueError:
            return
        auth = await _locked(session, sid)
        if auth is not None and str(auth.user_id) == subject and auth.revoked_at is None:
            auth.revoked_at = _now()
            auth.revoked_reason = REVOKE_LOGOUT
            await session.commit()
            await kick(redis, auth.user_id, sid=sid)
    else:
        await redis.delete(f"{_LEGACY_PREFIX}:{subject}:{payload['jti']}")

    from app.services import presence_token

    await presence_token.revoke(redis, user_id=subject)


async def revoke_all_for_user(
    session: AsyncSession,
    redis: Redis,
    user_id: uuid.UUID | str,
    *,
    reason: str,
    except_sid: uuid.UUID | None = None,
) -> int:
    """إبطالُ كلِّ جلسات المستخدم — **بابٌ واحدٌ لكلِّ من يُبطلها** (حظر · تغيير كلمة
    مرور · استعادتُها · طلبُ الحذف · إطفاءُ العامل الثاني · `totp_reset`).

    **والالتزامُ على المنادي** كما كان كلُّ شيءٍ في هذا المشروع؛ **وإغلاقُ
    المقابس بعده** (`kick`) لا قبله — إعلانُ ما قد يُتراجع عنه يُغلق مقبساً بلا سبب.
    **ومفاتيحُ ما قبل §60 تُمحى معها**، وإلا عادت جلسةٌ أُبطلت عند أوّل تجديد.

    و`except_sid` لمن غيّر كلمتَه بنفسه: **يُخرج غيرَه لا نفسَه** — وهو المقصودُ
    المكتوبُ في `routers/admin_account.py` منذ بُني.
    """
    condition = [AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)]
    if except_sid is not None:
        condition.append(AuthSession.id != except_sid)
    result = await session.execute(
        update(AuthSession)
        .where(*condition)
        .values(revoked_at=func.now(), revoked_reason=reason)
    )
    removed = result.rowcount or 0
    async for key in redis.scan_iter(match=f"{_LEGACY_PREFIX}:{user_id}:*", count=100):
        removed += await redis.delete(key)
    return removed


async def end_all_sessions(session: AsyncSession, redis: Redis, user: User) -> int:
    """**إنهاءُ كلِّ الجلسات** (§60-ب/١) — لهاتفٍ أو حاسوبٍ ضاع.

    ثلاثةٌ لا واحد: **الجلساتُ كلُّها** (وهذه منها) · **ورموزُ الإشعار لكلِّ أجهزته**
    — هاتفٌ تُبطَل جلستُه ويبقى يتلقّى إشعاراتِ الحساب وطلباتِه ليس هاتفاً أُخرج ·
    **ورمزُ الحضور** كما يفعل الخروج. **ثمّ تُغلق مقابسُه المفتوحة** بعد الالتزام.
    """
    count = await revoke_all_for_user(session, redis, user.id, reason=REVOKE_ALL)
    await session.execute(delete(DeviceToken).where(DeviceToken.user_id == user.id))
    await session.commit()
    from app.services import presence_token

    await presence_token.revoke(redis, user_id=str(user.id))
    await kick(redis, user.id)
    return count


async def kick(
    redis: Redis,
    user_id: uuid.UUID | str,
    *,
    sid: uuid.UUID | None = None,
    keep: uuid.UUID | None = None,
) -> None:
    """**تُغلق المقابسُ المفتوحة** لجلسةٍ أُبطلت (أو لكلِّ جلساته بلا `sid`،
    **إلا `keep`** إن سُمّيت — وهي ما استثناه `except_sid` من الإبطال).

    المقبسُ يُصادَق عند فتحه وحدَه، **فمقبسُ هاتفٍ ضائعٍ مفتوحٌ يبقى يتلقّى
    الطلباتِ والأحداث** بعد إبطال جلسته. فيُنشر على قناته أمرٌ يقرؤه المقبسُ
    نفسُه ويُغلق (`ws/routes.py::_pump`) — ولا يصل التطبيق. **وبعد الالتزام**
    كقاعدة كلِّ نشرٍ في هذا المشروع.
    """
    from app.ws import events

    await events.publish_session_revoked(redis, user_id, sid=sid, keep=keep)


def access_sid(token: str) -> uuid.UUID | None:
    """جلسةُ توكن وصولٍ **صادقه غيرُ هذه الدالّة** — لا تُصادِق شيئاً، وتُرجع
    `None` لكلِّ ما لا تقرؤه. لمن يُبطل جلساتِ صاحبه **إلا التي يتكلّم منها**."""
    try:
        payload = decode_token(token, "access")
        return uuid.UUID(payload["sid"]) if payload.get("sid") else None
    except (TokenError, ValueError, KeyError):
        return None


async def authenticate_access(session: AsyncSession, token: str) -> tuple[User, uuid.UUID | None]:
    """**توكنُ الوصول وجلستُه** — يُسأل عنها في كلِّ طلبٍ وعند فتح كلِّ مقبس.

    توكنٌ بلا `sid` صدر قبل §60 — يُقبل حتى ينتهي عمرُه القصير كما كان.
    ويُرجع الجلسةَ مع المستخدم ليعرف المقبسُ أيَّ أمرِ إغلاقٍ يخصّه.
    """
    try:
        payload = decode_token(token, "access")
        user_id = uuid.UUID(payload["sub"])
        sid = uuid.UUID(payload["sid"]) if payload.get("sid") else None
    except (TokenError, ValueError) as exc:
        raise InvalidToken() from exc

    if sid is not None:
        auth = await session.get(AuthSession, sid)
        if auth is None or auth.user_id != user_id or auth.revoked_at is not None:
            raise InvalidToken(_GONE)

    user = await session.get(User, user_id)
    if user is None:
        raise InvalidToken()
    return user, sid


__all__ = [
    "GRACE",
    "access_sid",
    "authenticate_access",
    "end_all_sessions",
    "issue_token_pair",
    "kick",
    "revoke_all_for_user",
    "revoke_session",
    "rotate",
]
