"""صفحةُ «الدول» ومفتاحُ «العمل خارج حدود الدول» (SPEC §٧٤-أ/٢–٣، أمرُ المالك ٢٠٢٦-١٠-١٣).

**القراءةُ للفريق (`StaffUser`)** — رؤيةُ حال الأسواق سياقٌ لا قرار، كـ`/admin/countries`. **والكتابةُ كلُّها `markets.manage`**:
بنصّ المالك «بصلاحية المالك»، **فلا يملكها أحدٌ افتراضاً ولا المشرفُ الكامل** (`permissions.SENSITIVE`)، وكلُّ تغييرٍ سطرٌ في التدقيق
(`services/markets`).

**وهذا بابُ حال السوق الوحيد**: بابُ المفاتيح العامّ (`PUT /admin/settings/feature-flags`) يردّ `country_visible` — فلا فتحَ يتخطّى
فحصَ الجاهزيّة ولا الصلاحية.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.currency import COUNTRY_NAME, CURRENCY_LABEL, currency_for_country
from app.core.deps import DbSession, MarketsManager, StaffUser
from app.core.exceptions import InvalidInput, NotFound
from app.core.phone import InvalidPhoneNumber, resolve_phone
from app.models.enums import AccountKind, CountryCode, RideStatus
from app.models.market import BorderAllowance
from app.models.ride import Ride
from app.models.user import User
from app.schemas.markets import (
    AllowanceIn,
    AllowanceRow,
    BordersIn,
    MarketRow,
    MarketsOut,
    MarketStatusIn,
    SignupDisplayIn,
)
from app.services import markets

router = APIRouter(prefix="/admin/markets", tags=["admin"])

#: **الجاريةُ ما لم تنتهِ** — من الطلب حتى الإكمال أو الإلغاء
_RUNNING = (
    RideStatus.REQUESTED,
    RideStatus.SEARCHING,
    RideStatus.ACCEPTED,
    RideStatus.ARRIVED,
    RideStatus.IN_PROGRESS,
    RideStatus.AT_STOP,
)


async def _row(session, country: CountryCode) -> MarketRow:
    currency = currency_for_country(country)
    running = await session.scalar(
        select(func.count()).select_from(Ride).where(Ride.country_code == country, Ride.status.in_(_RUNNING))
    )
    return MarketRow(
        country_code=country,
        name=COUNTRY_NAME[country],
        status=await markets.status_of(session, country),
        signup_display=await markets.signup_display(session, country),
        readiness=await markets.readiness(session, country),
        active_rides=int(running or 0),
        currency=currency.value,
        currency_label=CURRENCY_LABEL[currency],
    )


async def _allowance_row(session, row: BorderAllowance) -> AllowanceRow:
    user = await session.get(User, row.user_id)
    granter = await session.get(User, row.granted_by) if row.granted_by else None
    return AllowanceRow(
        id=row.id,
        user_id=row.user_id,
        name=user.name if user else None,
        phone=user.phone if user else None,
        role=user.role,
        country_code=user.country_code,
        is_test=bool(user.is_test),
        reason=row.reason,
        granted_at=row.created_at,
        granted_by_name=granter.name if granter else None,
    )


async def _out(session) -> MarketsOut:
    return MarketsOut(
        countries=[await _row(session, country) for country in CountryCode],
        borders_enforced=await markets.borders_enforced(session),
        allowances=[await _allowance_row(session, row) for row in await markets.allowances(session)],
    )


@router.get("", response_model=MarketsOut)
async def list_markets(session: DbSession, _: StaffUser) -> MarketsOut:
    return await _out(session)


@router.put("/{country_code}/status", response_model=MarketsOut)
async def set_market_status(
    country_code: CountryCode, payload: MarketStatusIn, session: DbSession, admin: MarketsManager
) -> MarketsOut:
    """**فتحٌ بفحص الجاهزيّة، أو إغلاق** — الرفضُ يحمل ما نقص (`missing`)، والفتحُ رغم النقص `force` وسببٌ مكتوب."""
    await markets.set_status(
        session, country=country_code, open_=payload.open, actor=admin, reason=payload.reason, force=payload.force
    )
    await session.commit()
    return await _out(session)


@router.put("/{country_code}/signup-display", response_model=MarketsOut)
async def set_signup_display(
    country_code: CountryCode, payload: SignupDisplayIn, session: DbSession, admin: MarketsManager
) -> MarketsOut:
    await markets.set_signup_display(session, country=country_code, display=payload.display, actor=admin)
    await session.commit()
    return await _out(session)


@router.put("/borders", response_model=MarketsOut)
async def set_borders(payload: BordersIn, session: DbSession, admin: MarketsManager) -> MarketsOut:
    await markets.set_borders(session, enforced=payload.enforced, actor=admin, reason=payload.reason)
    await session.commit()
    return await _out(session)


@router.post("/borders/allowances", response_model=MarketsOut)
async def grant_allowance(payload: AllowanceIn, session: DbSession, admin: MarketsManager) -> MarketsOut:
    """**حسابٌ بعينه يعمل من الخارج والحدودُ مفروضة** — بمعرّفه، أو برقمه ودولته (حسابُ TAXO لا حسابُ التوصيل)."""
    user: User | None = None
    if payload.user_id is not None:
        user = await session.get(User, payload.user_id)
    elif payload.phone:
        try:
            phone = resolve_phone(payload.phone, payload.country_code)
        except InvalidPhoneNumber as exc:
            raise InvalidInput(str(exc)) from exc
        user = await session.scalar(
            select(User).where(User.phone == phone, User.account_kind == AccountKind.TAXO)
        )
    else:
        raise InvalidInput("اختر الحسابَ أو اكتب رقمَه")
    if user is None or user.deleted_at is not None:
        raise NotFound("لا حسابَ بهذا الرقم")
    await markets.grant(session, user=user, reason=payload.reason, actor=admin)
    await session.commit()
    return await _out(session)


@router.post("/borders/allowances/{allowance_id}/revoke", response_model=MarketsOut)
async def revoke_allowance(allowance_id: uuid.UUID, session: DbSession, admin: MarketsManager) -> MarketsOut:
    await markets.revoke(session, allowance_id=allowance_id, actor=admin)
    await session.commit()
    return await _out(session)
