"""الدولُ والحدود — **البيتُ الواحدُ لكلِّ سؤالٍ عن سوقٍ مفتوحٍ أو مغلق، وعن الحدود** (SPEC §٧٤-أ/٢–٣، أمرُ المالك ٢٠٢٦-١٠-١٣).

## حالُ السوق

**مفتوحة = مفتاحُ `country_visible` مشتعل** (§٢٤) — لا عمودَ ثانٍ يفترق عنه. **والجديدُ معنى الإغلاق** بنصّ المالك:
- **لا يُطلب جديد** — رحلةٌ وتقديرُها، وحجزٌ مجدول، ومقعدُ بين المدن، والمشوارُ الثابت (`require_open_for` عند كلِّ بابِ طلب)؛
- **والجاري يكتمل** — لا شيءَ هنا يمسّ رحلةً قائمة، **والحجزُ الذي سبق الإغلاقَ يُنفَّذ**: طلبٌ وقع قبله؛
- **والمحافظُ لا تُمسّ ولا تُحذف بيانات** — الإغلاقُ لا يكتب إلا مفتاحاً؛
- **والدخولُ قائم**، والتسجيلُ يُردّ (`require_signup_open`).

**وحساباتُ التجربة تصل كلَّ سوقٍ ولو مغلقاً** (§٧٤-أ/١٠) — **وكلُّ طلبٍ منها في سوقٍ مغلقٍ سطرٌ في التدقيق**.

## الفتح

**يمرّ بفحص الجاهزيّة** (`readiness`) — أسعارٌ لكلِّ فئةٍ تُطلب ولا صفرَ فيها · طريقةُ دفعٍ عاملةٌ للمحفظة والاشتراك · السياساتُ
الأربعُ منشورة · قاعدةُ التقريب مضبوطة — **فإن نقص شيءٌ رُدّ الفتحُ بما نقص، وللمالك أن يفتح رغم ذلك بسببٍ مكتوبٍ مدقَّق**.

## الحدود

**حدُّ نطاق الخدمة يبقى في `core/service_area.py` كما هو** — صندوقٌ لكلِّ دولة. **والجديدُ مفتاحٌ يرفعه** (قرارُ المالك ٢٠٢٦-١٠-١٣، ينسخ
«ثابتٌ بلا زرّ» من ٢٠٢٦-٠٩-١٠ **بلفظه هو**): مفروضةً كاليوم، أو مرفوعةً فيعمل التطبيقُ من أيِّ مكانٍ **بسوق الحساب نفسِه**؛ **وقائمةُ
سماحٍ** لحساباتٍ بعينها والحدودُ مفروضة. **ورفعُها لا يفتح سوقاً مغلقاً أبداً** — السؤالان في دالّتين لا تقرأ إحداهما الأخرى.

**ولا قفلَ هنا**: لا مالَ يتحرّك ولا حالَ صفٍّ تتنازعه طلبات — كتابةُ مفتاحٍ أو صفِّ إعدادٍ بقيدِ تدقيق، **فلا موضعَ لها في ترتيب الأقفال**.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import service_area
from app.core.currency import COUNTRY_NAME
from app.core.exceptions import Conflict, InvalidInput, MarketClosed, MarketNotReady, NotFound, SignupClosed
from app.models.enums import (
    AuditAction,
    CountryCode,
    FeatureKey,
    MarketStatus,
    PolicyApp,
    PolicyDocType,
    ProviderKey,
    SignupDisplay,
    SignupState,
)
from app.models.market import BorderAllowance, CountryMarket, MarketBorders
from app.models.pricing import PricingRule
from app.models.user import User
from app.services import audit, settings_service

#: **أقصرُ سببٍ يُقبل لفتحٍ رغم النقص ولرفع الحدود** — طولُ سبب إطفاء الحرّاس نفسُه (`admin_settings`)
MIN_REASON = 8

#: **ما يُفحص في كلِّ تسعيرة** — الأساسُ والكيلومترُ والدقيقةُ والحدُّ الأدنى: «لا صفرَ فيها» بنصّ المالك
_PRICE_FIELDS: tuple[tuple[str, str], ...] = (
    ("base_fare", "الأساس"),
    ("price_per_km", "سعرُ الكيلومتر"),
    ("price_per_min", "سعرُ الدقيقة"),
    ("minimum_fare", "الحدُّ الأدنى"),
)

_DOC_LABEL = {PolicyDocType.PRIVACY_POLICY: "سياسةُ الخصوصية", PolicyDocType.TERMS_OF_USE: "الشروط"}
_APP_LABEL = {PolicyApp.RIDER: "للراكب", PolicyApp.DRIVER: "للكبتن"}


def _now() -> datetime:
    return datetime.now(UTC)


def _written(reason: str | None, *, what: str) -> str:
    text = (reason or "").strip()
    if len(text) < MIN_REASON:
        raise InvalidInput(f"{what} — اكتب السبب ({MIN_REASON} أحرف على الأقل)")
    return text


# ------------------------------------------------------------------ حالُ السوق


async def is_open(session: AsyncSession, country: CountryCode) -> bool:
    """**مفتوحةٌ للعموم؟** — مفتاحُ `country_visible`، وسكوتُه «مفتوحة» (§٢٤: الإخفاءُ صفٌّ صريحٌ يكتبه إنسان)."""
    return await settings_service.is_feature_enabled(session, country, FeatureKey.COUNTRY_VISIBLE)


async def status_of(session: AsyncSession, country: CountryCode) -> MarketStatus:
    return MarketStatus.OPEN if await is_open(session, country) else MarketStatus.CLOSED


async def open_countries(session: AsyncSession) -> list[CountryCode]:
    return [country for country in CountryCode if await is_open(session, country)]


async def signup_display(session: AsyncSession, country: CountryCode) -> SignupDisplay:
    """ظهورُ المغلقة في التسجيل — **وغيابُ الصفِّ «قريباً»** (افتراضُ المالك بلفظه)."""
    row = await session.get(CountryMarket, country)
    return row.signup_display if row is not None else SignupDisplay.SOON


async def signup_state(session: AsyncSession, country: CountryCode) -> SignupState:
    """**ما يراه التسجيلُ محسوباً** — المفتوحةُ تُختار دائماً، والمغلقةُ «قريباً» أو لا تُرسم."""
    if await is_open(session, country):
        return SignupState.OPEN
    display = await signup_display(session, country)
    return SignupState.HIDDEN if display is SignupDisplay.HIDDEN else SignupState.SOON


async def require_signup_open(session: AsyncSession, country: CountryCode) -> None:
    """**التسجيلُ في المغلقة يُردّ** — قبل الرمز وقبل الصفّ، كحارس الرقم. والدخولُ لا يمرّ من هنا أبداً."""
    if not await is_open(session, country):
        raise SignupClosed(country)


async def require_open_for(session: AsyncSession, user: User, *, door: str, record: bool = True) -> None:
    """**بابُ كلِّ طلبٍ جديد** — سوقُ الحساب مفتوح، **أو الحسابُ حسابُ تجربة** (§٧٤-أ/١٠).

    **واستعمالُ التجربة لسوقٍ مغلقٍ يُدقَّق** (بنصّ المالك «وكلُّ استعمالٍ مدقَّق») — إلا حيث لا يُكتب شيءٌ أصلاً (`record=False`:
    التقديرُ قراءةٌ خالصة، وسطرُ تدقيقٍ فيه يجعله كتابة).
    """
    if await is_open(session, user.country_code):
        return
    if not user.is_test:
        raise MarketClosed(user.country_code)
    if record:
        await audit.record(
            session,
            actor=user,
            action=AuditAction.CREATE,
            entity_type="test_market_use",
            entity_id=user.id,
            details={"country_code": CountryCode(user.country_code).value, "door": door},
        )


# ------------------------------------------------------------------ الجاهزيّة


async def _pricing_gaps(session: AsyncSession, country: CountryCode) -> list[str]:
    from app.services import categories

    rules = {
        rule.vehicle_category: rule
        for rule in await session.scalars(select(PricingRule).where(PricingRule.country_code == country))
    }
    keys = await categories.requestable_keys(session, country)
    if not keys:
        return ["لا فئةَ رحلةٍ تُطلب في هذا السوق"]
    faces = {row.key: row for row in await categories.for_country(session, country)}
    gaps: list[str] = []
    for key in keys:
        name = faces[key].name if key in faces and faces[key].name else key
        rule = rules.get(key)
        if rule is None:
            gaps.append(f"تسعيرةُ «{name}» غيرُ مضبوطة")
            continue
        zero = [label for field, label in _PRICE_FIELDS if not getattr(rule, field) or getattr(rule, field) <= 0]
        if zero:
            gaps.append(f"تسعيرةُ «{name}» فيها صفر: {' · '.join(zero)}")
    return gaps


async def _payment_ready(session: AsyncSession, country: CountryCode) -> bool:
    """**طريقةُ دفعٍ عاملةٌ للمحفظة والاشتراك** — فالكاشُ في الرحلة متاحٌ دائماً ولا يُسأل عنه، **والسؤالُ: أيدفع الكبتنُ اشتراكَه
    ويشحن الراكبُ رصيدَه بطريقةٍ ما؟** وإلا فُتح سوقٌ لا يعمل فيه كبتن."""
    from app.services import payment_requests
    from app.services.providers.credentials import provider_is_active

    pay = await settings_service.get_payment_settings(session, country)
    if await settings_service.is_feature_enabled(session, country, FeatureKey.CLIQ_ENABLED) and pay and pay.cliq_alias:
        return True
    if await settings_service.is_feature_enabled(session, country, FeatureKey.CARD_ENABLED) and await provider_is_active(
        session, ProviderKey.TELR, country
    ):
        return True
    return await payment_requests.is_enabled(session, country) and bool(
        await payment_requests.providers_for(session, country)
    )


async def readiness(session: AsyncSession, country: CountryCode) -> list[str]:
    """**ما ينقص لفتح السوق** — قائمةٌ فارغةٌ تعني «جاهز». **ولا تكتب شيئاً.**"""
    from app.services import policies

    missing = await _pricing_gaps(session, country)
    if not await _payment_ready(session, country):
        missing.append("لا طريقةَ دفعٍ عاملةً لشحن المحفظة ودفعِ الاشتراك")
    for app in (PolicyApp.RIDER, PolicyApp.DRIVER):
        for doc in (PolicyDocType.PRIVACY_POLICY, PolicyDocType.TERMS_OF_USE):
            if await policies.published(session, country=country, doc_type=doc, app=app) is None:
                missing.append(f"{_DOC_LABEL[doc]} {_APP_LABEL[app]} غيرُ منشورة")
    pay = await settings_service.get_payment_settings(session, country)
    if pay is None or (pay.rounding_enabled and not (pay.rounding_unit and pay.rounding_unit > 0)):
        missing.append("قاعدةُ التقريب غيرُ مضبوطة")
    return missing


async def set_status(
    session: AsyncSession,
    *,
    country: CountryCode,
    open_: bool,
    actor: User,
    reason: str | None = None,
    force: bool = False,
) -> MarketStatus:
    """**فتحٌ بفحصٍ أو إغلاق** — والمفتاحُ يُكتب بالباب القائم (`set_flag`، ومعه سطرُه)، **وسطرُ «الدول» فوقه** بما نقص وبالسبب."""
    current = await is_open(session, country)
    missing: list[str] = []
    text: str | None = (reason or "").strip() or None
    if open_ and not current:
        missing = await readiness(session, country)
        if missing and not force:
            raise MarketNotReady(missing=missing)
        if missing:
            text = _written(reason, what="الفتحُ رغم النقص قرارٌ يُسأل عنه")
    if open_ == current:
        return MarketStatus.OPEN if current else MarketStatus.CLOSED
    await settings_service.set_flag(
        session,
        country_code=country,
        feature_key=FeatureKey.COUNTRY_VISIBLE,
        enabled=open_,
        actor=actor,
        reason=text,
    )
    details: dict[str, object] = {"country_code": country.value, "status": "open" if open_ else "closed"}
    if missing:
        details |= {"forced": True, "missing": missing}
    if text:
        details["reason"] = text
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.ACTIVATE if open_ else AuditAction.DEACTIVATE,
        entity_type="market",
        details=details,
    )
    return MarketStatus.OPEN if open_ else MarketStatus.CLOSED


async def set_signup_display(
    session: AsyncSession, *, country: CountryCode, display: SignupDisplay, actor: User
) -> SignupDisplay:
    row = await session.get(CountryMarket, country)
    before = row.signup_display if row is not None else SignupDisplay.SOON
    if row is None:
        row = CountryMarket(country_code=country, signup_display=display, updated_by=actor.id)
        session.add(row)
    else:
        row.signup_display = display
        row.updated_by = actor.id
    if before is not display:
        await audit.record(
            session,
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type="market_signup_display",
            details={"country_code": country.value, "changes": {"signup_display": {"from": before.value, "to": display.value}}},
        )
    await session.flush()
    return display


# ------------------------------------------------------------------ الحدود


async def _borders_row(session: AsyncSession) -> MarketBorders | None:
    return await session.scalar(select(MarketBorders))


async def borders_enforced(session: AsyncSession) -> bool:
    """**الحدودُ مفروضة؟** — وغيابُ الصفِّ «مفروضة»: السكوتُ لا يُسقط حدّاً."""
    row = await _borders_row(session)
    return True if row is None else row.enforced


async def set_borders(session: AsyncSession, *, enforced: bool, actor: User, reason: str | None) -> bool:
    """**رفعُ الحدود إسقاطُ حدٍّ بقرار** — فيُشترط سببُه مكتوباً كإطفاء الحرّاس؛ **والإعادةُ بلا شرط**."""
    row = await _borders_row(session)
    before = True if row is None else row.enforced
    if before == enforced:
        return enforced
    text = _written(reason, what="رفعُ الحدود قرارٌ يُسأل عنه") if not enforced else (reason or "").strip() or None
    if row is None:
        row = MarketBorders(enforced=enforced, updated_by=actor.id)
        session.add(row)
    else:
        row.enforced = enforced
        row.updated_by = actor.id
    details: dict[str, object] = {"enforced": enforced}
    if text:
        details["reason"] = text
    await audit.record(session, actor=actor, action=AuditAction.UPDATE, entity_type="market_borders", details=details)
    await session.flush()
    return enforced


async def allowances(session: AsyncSession, *, include_revoked: bool = False) -> list[BorderAllowance]:
    stmt = select(BorderAllowance).order_by(BorderAllowance.created_at.desc())
    if not include_revoked:
        stmt = stmt.where(BorderAllowance.revoked_at.is_(None))
    return list((await session.scalars(stmt)).all())


async def active_allowance(session: AsyncSession, user_id: uuid.UUID) -> BorderAllowance | None:
    return await session.scalar(
        select(BorderAllowance).where(BorderAllowance.user_id == user_id, BorderAllowance.revoked_at.is_(None))
    )


async def grant(session: AsyncSession, *, user: User, reason: str, actor: User | None) -> BorderAllowance:
    """**`actor` فارغٌ لسكربت الإنشاء وحدَه** (§٧٤-ز) — لا مشرفَ قرّره، **وقيدٌ يسمّي من لم يفعل أسوأُ من قيدٍ لا يسمّي أحداً**."""
    text = (reason or "").strip()
    if len(text) < 3:
        raise InvalidInput("اكتب سببَ السماح (3 أحرف على الأقل)")
    if await active_allowance(session, user.id) is not None:
        raise Conflict("هذا الحسابُ في قائمة السماح سلفاً")
    row = BorderAllowance(user_id=user.id, reason=text[:200], granted_by=actor.id if actor else None)
    session.add(row)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.CREATE,
        entity_type="border_allowance",
        entity_id=row.id,
        details={"user_id": str(user.id), "reason": row.reason},
    )
    return row


async def revoke(session: AsyncSession, *, allowance_id: uuid.UUID, actor: User) -> BorderAllowance:
    """**النزعُ ختمٌ لا حذف** — من سُمح له ومتى ومن نزع يبقى سطراً."""
    row = await session.get(BorderAllowance, allowance_id)
    if row is None:
        raise NotFound("لا سماحَ بهذا المعرّف")
    if row.revoked_at is not None:
        return row
    row.revoked_at = _now()
    row.revoked_by = actor.id
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.DEACTIVATE,
        entity_type="border_allowance",
        entity_id=row.id,
        details={"user_id": str(row.user_id)},
    )
    await session.flush()
    return row


async def may_work_outside(session: AsyncSession, user: User) -> bool:
    """**أيعمل هذا الحسابُ من خارج حدود سوقه؟** — الحدودُ مرفوعة، أو هو في قائمة السماح."""
    if not await borders_enforced(session):
        return True
    return await active_allowance(session, user.id) is not None


async def require_inside(session: AsyncSession, user: User, points: Iterable[service_area.Point]) -> None:
    """**حدُّ نطاق الخدمة بمفتاحه** — البابُ الذي يناديه التقديرُ والطلبُ معاً بدل `service_area` مباشرة.

    **والسوقُ سوقُ الحساب دائماً** — رفعُ الحدود يُسقط سؤالَ «أين» لا سؤالَ «بأيِّ سوق»، **ولا يفتح سوقاً مغلقاً** (ذلك `require_open_for`).
    """
    if await may_work_outside(session, user):
        return
    service_area.require_inside_market(user.country_code, points)


def country_label(country: CountryCode) -> str:
    return COUNTRY_NAME[country]
