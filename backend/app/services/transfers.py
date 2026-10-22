"""**تحويلُ BaridiMob/CCP في الجزائر بمراجعةٍ يدويّة** (SPEC §٨٢-ب، أمرُ المالك ٢٠٢٦-١٠-٢٢).

## ما يُبنى هنا وما يُعاد استعمالُه

**الطلبُ نفسُه طلبُ نظام الدفع القائم** (`payment_requests`): إيصالٌ ورقمُ تحويلٍ إجباريّان، والفهرسان الفريدان يمنعان رقمَ التحويل
وصورةَ الإيصال نفسَيهما مرّتين، **والاعتمادُ قيدٌ واحدٌ بمفتاح الطلب** تحت قفل صفِّه. وما يُضاف هنا ثلاثة:

١. **إعدادُ الطريقة للمالك وحدَه** — RIP بعشرين رقماً، واسما صاحبه بالعربيّة واللاتينيّة، وحدّا المبلغ، ومفتاحُها. **ولا تظهر للناس حتى
   يكتمل ذلك كلُّه ويُشعل** — وحسابُ صديق المالك لا يبدّله أحدٌ غيرُه ولا من الباب العامّ (`require_owner_for`).
٢. **طابورُ المراجعة** — BaridiMob في الجزائر وحدَه، **للمراجع والمالك**، واعتمادٌ واحدٌ من أيّهما يكفي. **والمراجعُ لا يرى من صاحب
   الطلب إلا اسمَه الأوّل وهاتفاً مقنَّعاً** (`+213 5•• ••• 699`)، ولا يغيّر المبلغ.
٣. **حسابُ المراجع ينشئه المالكُ من اللوحة** — بدور `payment_reviewer` وحدَه، **والكلمةُ يضعها المالكُ وتتغيّر عند أوّل دخول**، والعاملُ
   الثاني إلزاميّ (`security_settings.totp_required_for`).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, NotFound, PermissionDenied
from app.core.phone import dial_code_for
from app.models.enums import (
    AuditAction,
    CountryCode,
    PaymentProviderKind,
    PaymentRequestStatus,
    UserRole,
)
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant, has_role_clause
from app.services import admin_credentials, audit, rounding

#: **معرّفُ الطريقة وسوقُها** — ثابتان: الطلباتُ تُقرأ بهما
CODE = "baridimob"
COUNTRY = CountryCode.DZ
#: **اسمُها كما يراه الدافع** — والاسمان الآخران (صاحبُ الحساب) من إعداد المالك
NAME = "BaridiMob / CCP"
#: **RIP بريد الجزائر عشرون رقماً** — يُطبَّع بلا مسافاتٍ قبل الفحص
RIP = re.compile(r"^\d{20}$")


def require_owner_for(provider: PayMethod, actor: User) -> None:
    """**طريقةُ BaridiMob للمالك وحدَه** — الإعدادُ من بطاقته، ولا يبدّلها الباب العامّ لمن يملك `settings.write`."""
    if provider.code == CODE and provider.country_code is COUNTRY and not actor.has_role(UserRole.OWNER):
        raise PermissionDenied("حسابُ BaridiMob يضبطه المالكُ وحدَه")


def normalize_rip(value: str | None) -> str:
    return re.sub(r"[\s\-.]", "", value or "")


def mask_phone(phone: str | None, country: CountryCode) -> str:
    """**هاتفٌ مقنَّع** (§٨٢-ب/٥): الرمزُ الدوليّ، وأوّلُ رقمٍ وطنيّ، وآخرُ ثلاثة — `+213 5•• ••• 699`؛ ولا شيءَ غيرُها."""
    digits = re.sub(r"\D", "", phone or "")
    code = dial_code_for(country)
    national = digits[len(code):] if code and digits.startswith(code) else digits
    if len(national) < 5:
        return "•••"
    return f"+{code} {national[0]}•• ••• {national[-3:]}"


def first_name(name: str | None) -> str:
    parts = (name or "").split()
    return parts[0] if parts else "—"


# ------------------------------------------------------------------ الإعداد


async def method(session: AsyncSession, *, for_update: bool = False) -> PayMethod | None:
    stmt = select(PayMethod).where(PayMethod.country_code == COUNTRY, PayMethod.code == CODE)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(stmt)


def is_configured(provider: PayMethod | None) -> bool:
    """**مكتملٌ ليُشعل** — RIP صحيح، والاسمان، والحدّان."""
    return bool(
        provider is not None
        and RIP.match(provider.account_number or "")
        and (provider.account_holder or "").strip()
        and (provider.account_holder_latin or "").strip()
        and provider.min_amount is not None
        and provider.max_amount is not None
    )


def _masked(value: str | None) -> str | None:
    """**ما يُكتب في التدقيق عن الرقم** — آخرُ أربعةٍ وحدَها؛ والرقمُ كاملاً في صفِّ الطريقة لا في سجلٍّ يُقرأ بعده."""
    return f"…{value[-4:]}" if value else None


async def save_settings(
    session: AsyncSession,
    *,
    actor: User,
    account_number: str | None,
    account_holder: str | None,
    account_holder_latin: str | None,
    min_amount: Decimal | None,
    max_amount: Decimal | None,
    enabled: bool,
) -> PayMethod:
    """**بطاقةُ المالك** — تُنشئ الطريقةَ إن غابت (مطفأةً) وتكتب ما أُرسل، **ولا تُشعل ما لم يكتمل**."""
    rip = normalize_rip(account_number) or None
    if rip is not None and not RIP.match(rip):
        raise InvalidInput("رقمُ RIP عشرون رقماً بالضبط", field="account_number")
    holder = (account_holder or "").strip() or None
    latin = (account_holder_latin or "").strip() or None
    if latin is not None and not re.fullmatch(r"[A-Za-z][A-Za-z .'\-]{1,119}", latin):
        raise InvalidInput("الاسمُ اللاتينيُّ بالحروف اللاتينيّة كما تعرضه بريدُ الجزائر", field="account_holder_latin")
    for field, value in (("min_amount", min_amount), ("max_amount", max_amount)):
        if value is not None:
            if value <= 0:
                raise InvalidInput("المبلغُ أكبرُ من صفر", field=field)
            await rounding.require_multiple_in(session, COUNTRY, value, field=field)
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise InvalidInput("الحدُّ الأدنى أكبرُ من الأعلى", field="min_amount")

    provider = await method(session, for_update=True)
    created = provider is None
    if provider is None:
        provider = PayMethod(
            country_code=COUNTRY, kind=PaymentProviderKind.BANK_TRANSFER, code=CODE, name=NAME,
            enabled=False, for_topup=True, for_subscription=True, sort_order=5,
        )
        session.add(provider)
    before = {
        "account_number": _masked(provider.account_number),
        "account_holder": provider.account_holder,
        "account_holder_latin": provider.account_holder_latin,
        "min_amount": str(provider.min_amount) if provider.min_amount is not None else None,
        "max_amount": str(provider.max_amount) if provider.max_amount is not None else None,
        "enabled": provider.enabled,
    }
    provider.account_number = rip
    provider.account_holder = holder
    provider.account_holder_latin = latin
    provider.min_amount = min_amount
    provider.max_amount = max_amount
    if enabled and not is_configured(provider):
        raise InvalidInput("أكمل RIP والاسمين والحدّين قبل التفعيل", field="enabled")
    provider.enabled = enabled
    await session.flush()
    after = {
        "account_number": _masked(provider.account_number),
        "account_holder": provider.account_holder,
        "account_holder_latin": provider.account_holder_latin,
        "min_amount": str(provider.min_amount) if provider.min_amount is not None else None,
        "max_amount": str(provider.max_amount) if provider.max_amount is not None else None,
        "enabled": provider.enabled,
    }
    changes = {key: {"before": before[key], "after": after[key]} for key in after if before[key] != after[key]}
    if changes or created:
        await audit.record(
            session, actor=actor, action=AuditAction.CREATE if created else AuditAction.UPDATE,
            entity_type="payment_provider", entity_id=provider.id, changes=changes,
        )
    return provider


# ------------------------------------------------------------------ الطابور


def _scope():
    return (PaymentRequest.country_code == COUNTRY, PayMethod.code == CODE, PayMethod.country_code == COUNTRY)


async def queue(
    session: AsyncSession, *, status: PaymentRequestStatus | None, limit: int, offset: int
) -> Sequence[PaymentRequest]:
    stmt = (
        select(PaymentRequest)
        .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
        .where(*_scope())
        .order_by(PaymentRequest.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(PaymentRequest.status == status)
    return (await session.scalars(stmt.limit(limit).offset(offset))).all()


async def scoped(session: AsyncSession, request_id: uuid.UUID, *, for_update: bool = False) -> PaymentRequest:
    """**طلبٌ في نطاق المراجعة وحدَه** — غيرُه ٤٠٤ لا ٤٠٣: لا يُعرف من خارج النطاق أنه موجود."""
    stmt = (
        select(PaymentRequest)
        .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
        .where(PaymentRequest.id == request_id, *_scope())
    )
    if for_update:
        stmt = stmt.with_for_update(of=PaymentRequest).execution_options(populate_existing=True)
    row = await session.scalar(stmt)
    if row is None:
        raise NotFound("طلبُ التحويل غيرُ موجود")
    return row


# ------------------------------------------------------------------ حسابُ المراجع


async def reviewers(session: AsyncSession) -> Sequence[User]:
    return (
        await session.scalars(select(User).where(has_role_clause(UserRole.PAYMENT_REVIEWER)).order_by(User.created_at))
    ).all()


async def create_reviewer(
    session: AsyncSession, redis: Redis, *, actor: User, name: str, username: str, password: str
) -> User:
    """**ينشئه المالكُ من اللوحة** (§٨٢-ب/٥) — دورُ المراجع وحدَه، والجزائر، **والكلمةُ تتغيّر عند أوّل دخول**، والعاملُ الثاني
    إلزاميٌّ قبل أيِّ صفحة. **ولا هاتفَ ولا بريد**: الحسابُ للّوحة وحدَها، وصديقُ المالك لا تُكتب بياناتُه حيث لا حاجة."""
    from app.services.auth.password import set_password

    clean = name.strip()
    if len(clean) < 2:
        raise InvalidInput("اكتب اسمَ المراجع", field="name")
    user = User(
        phone=None,
        name=clean[:120],
        role=UserRole.PAYMENT_REVIEWER,
        country_code=COUNTRY,
        role_grants=[UserRoleGrant(role=UserRole.PAYMENT_REVIEWER)],
    )
    session.add(user)
    await session.flush()
    await set_password(session, redis, user=user, new_password=password)
    credential = await admin_credentials.create(session, user=user, username=username, must_change_password=True)
    await audit.record(
        session, actor=actor, action=AuditAction.CREATE, entity_type="user", entity_id=user.id,
        details={"role": UserRole.PAYMENT_REVIEWER.value, "username": credential.username, "country": COUNTRY.value},
    )
    return user
