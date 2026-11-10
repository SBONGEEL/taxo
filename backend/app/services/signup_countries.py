"""**مُنتقي الدول — الحالُ والعدّ** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٥).

## الحالاتُ الأربع بلفظ المالك
- **نشطة** — تعمل كالمعتاد. **ولا تكون إلا لسوق** (الأردن · الجزائر · ليبيا) ومن «الدول والحدود» وحدَها: فتحُ سوقٍ له فحصُ
  جاهزيّته (`markets.set_status`)، **ودولةٌ بلا قواعدِ أرقامٍ لا تُفتح للتسجيل أصلاً** — لا رمزَ يُرسل إلى رقمٍ لا يُطبَّع.
- **قريباً** — شارة، والمتابعةُ «قريباً في [الدولة]» بلا رمز. **ليبيا هنا** حتى يقول المالك.
- **متوقفة** — المتابعةُ «خادم الدولة متوقف حالياً» بلا رمز. **افتراضُ كلِّ دولةٍ جديدة** (غيابُ صفِّها).
- **مخفية** — لا تُرسم.

**والحالُ تُقرأ في كلِّ طلبٍ لـ`/config`** — فتغييرُها من اللوحة يسري بلا تحديثِ تطبيق.

## العدّ — «محاولاتٌ فقط، بلا أرقام»
`record_attempt` يزيد عدّاً يوميّاً لدولةٍ واحدة — **ولا يستقبل البابُ رقماً أصلاً** (`SignupAttemptIn` بلا حقل هاتف)، فلا شيءَ
يُخزَّن ولا شيءَ يُطبع. **ويُحدّ لكلِّ عنوانٍ في الساعة** (`rate_limit`، بلا تخزينٍ للعنوان خارج مفتاحٍ ينتهي بساعته) — كي لا
يصير العدّادُ رقماً يكتبه من يشاء.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.countries import BY_CODE, CATALOGUE, Country
from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import AuditAction, CountryCode, SignupDisplay, SignupState
from app.models.signup_country import SignupAttemptDaily, SignupCountry
from app.models.user import User
from app.services import audit, markets

MARKETS: frozenset[str] = frozenset(code.value for code in CountryCode)


@dataclass(frozen=True, slots=True)
class Entry:
    country: Country
    state: SignupState
    market: bool


def _state(display: SignupDisplay) -> SignupState:
    return {
        SignupDisplay.SOON: SignupState.SOON,
        SignupDisplay.HIDDEN: SignupState.HIDDEN,
        SignupDisplay.STOPPED: SignupState.STOPPED,
    }[display]


async def state_of(session: AsyncSession, code: str) -> SignupState:
    """**حالُ دولةٍ واحدة** — السوقُ من «الدول والحدود»، وغيرُها من صفِّها أو «متوقفة»."""
    if code in MARKETS:
        return await markets.signup_state(session, CountryCode(code))
    row = await session.get(SignupCountry, code)
    return _state(row.display) if row is not None else SignupState.STOPPED


async def catalogue(session: AsyncSession) -> list[Entry]:
    """**كلُّ الدول بحالها** — بترتيب القائمة. والمخفيّةُ معها (اللوحةُ تراها؛ `/config` يُسقطها)."""
    rows = {row.code: row for row in (await session.scalars(select(SignupCountry))).all()}
    out: list[Entry] = []
    for country in CATALOGUE:
        if country.code in MARKETS:
            state = await markets.signup_state(session, CountryCode(country.code))
        else:
            row = rows.get(country.code)
            state = _state(row.display) if row is not None else SignupState.STOPPED
        out.append(Entry(country=country, state=state, market=country.code in MARKETS))
    return out


async def set_display(session: AsyncSession, *, code: str, display: SignupDisplay, actor: User) -> None:
    """**حالُ دولةٍ غيرِ سوق** — قريباً · متوقفة · مخفية. **والسوقُ يُضبط من بابه** (`markets.set_signup_display`)."""
    country = BY_CODE.get(code)
    if country is None:
        raise NotFound("الدولةُ ليست في القائمة")
    if code in MARKETS:
        raise InvalidInput("هذه سوقٌ — حالُها من «الدول والحدود» أعلاه")
    row = await session.get(SignupCountry, code, with_for_update=True)
    before = row.display if row is not None else SignupDisplay.STOPPED
    if row is None:
        session.add(SignupCountry(code=code, display=display, updated_by=actor.id))
    else:
        row.display = display
        row.updated_by = actor.id
    if before is not display:
        await audit.record(
            session,
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type="signup_country_display",
            details={"country_code": code, "changes": {"display": {"from": before.value, "to": display.value}}},
        )
    await session.flush()


async def record_attempt(session: AsyncSession, *, code: str, now: datetime | None = None) -> SignupState:
    """**محاولةٌ في دولةٍ غيرِ نشطة تُعدّ** — ويُعاد حالُها ليقول التطبيقُ نصَّها. **والنشطةُ لا تُعدّ** (ليست محاولةً فاشلة)."""
    if code not in BY_CODE:
        raise NotFound("الدولةُ ليست في القائمة")
    state = await state_of(session, code)
    if state is SignupState.OPEN:
        return state
    day = (now or datetime.now(UTC)).date()
    stmt = insert(SignupAttemptDaily).values(day=day, country=code, attempts=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[SignupAttemptDaily.day, SignupAttemptDaily.country],
        set_={"attempts": SignupAttemptDaily.attempts + 1},
    )
    await session.execute(stmt)
    return state


async def attempts(session: AsyncSession, *, days: int = 30, today: date | None = None) -> list[tuple[str, int]]:
    """**مجموعُ المحاولات لكلِّ دولةٍ في آخر `days` يوماً** — الأكثرُ أوّلاً."""
    since = (today or datetime.now(UTC).date()) - timedelta(days=days - 1)
    rows = await session.execute(
        select(SignupAttemptDaily.country, func.sum(SignupAttemptDaily.attempts))
        .where(SignupAttemptDaily.day >= since)
        .group_by(SignupAttemptDaily.country)
        .order_by(func.sum(SignupAttemptDaily.attempts).desc())
    )
    return [(country, int(total or 0)) for country, total in rows.all()]


def message_for(state: SignupState, name: str) -> str:
    """**نصُّ المالك لكلِّ حال** — عربيّاً، ويُترجم بلغة الطلب حيث يُجاب."""
    if state is SignupState.STOPPED:
        return "خادم الدولة متوقف حالياً"
    return f"قريباً في {name}"
