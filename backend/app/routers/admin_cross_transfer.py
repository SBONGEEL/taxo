"""**«التحويل بين الدول» في اللوحة** (أمرُ المالك ٢٠٢٦-١١-٢٢): أسعارُ الصرف الستّة ورسومُها، وحدّا كلِّ دولة.

**المفتاحُ نفسُه ليس هنا** — هو `cross_country_transfer_enabled` في «الإعدادات ← المفاتيح» كبقيّة المفاتيح، **والمالكُ وحدَه يُشعله**
بعد مراجعة الجانب القانونيّ. وهذه الصفحةُ تضبط ما يحتاجه حين يُشعَل؛ **وضبطُها لا يُشعل شيئاً**.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.cross_transfer import FxRate
from app.models.enums import CountryCode
from app.models.user import User
from app.schemas.cross_transfer import CrossLimitOut, CrossLimitUpdate, FxRateOut, FxRateUpdate
from app.services import cross_transfer

router = APIRouter(prefix="/admin/cross-transfer", tags=["admin-cross-transfer"])


@router.get("/rates", response_model=list[FxRateOut])
async def list_rates(_staff: StaffUser, session: DbSession) -> list[FxRateOut]:
    """**الاتّجاهاتُ الستّة دائماً** — ما لم يُضبط يُعرض فارغاً ليُرى أنه غائب، لا يُخفى."""
    rows = {(row.from_currency, row.to_currency): row for row in (await session.scalars(select(FxRate))).all()}
    names: dict = {}
    setters = {row.set_by for row in rows.values() if row.set_by is not None}
    if setters:
        names = {user.id: user.name for user in (await session.scalars(select(User).where(User.id.in_(setters)))).all()}
    out: list[FxRateOut] = []
    for source, target in cross_transfer.all_pairs():
        row = rows.get((source, target))
        out.append(
            FxRateOut(
                from_currency=source,
                to_currency=target,
                rate=None if row is None else format(row.rate.normalize(), "f"),
                fee_percent=None if row is None else format(row.fee_percent.normalize(), "f"),
                set_at=None if row is None else row.set_at,
                set_by_name=None if row is None or row.set_by is None else names.get(row.set_by),
            )
        )
    return out


@router.put("/rates", response_model=FxRateOut)
async def put_rate(payload: FxRateUpdate, admin: SettingsWriter, session: DbSession) -> FxRateOut:
    row = await cross_transfer.set_rate(
        session,
        actor=admin,
        source=payload.from_currency,
        target=payload.to_currency,
        rate=payload.rate,
        fee_percent=payload.fee_percent,
    )
    await session.commit()
    return FxRateOut(
        from_currency=row.from_currency,
        to_currency=row.to_currency,
        rate=format(row.rate.normalize(), "f"),
        fee_percent=format(row.fee_percent.normalize(), "f"),
        set_at=row.set_at,
        set_by_name=admin.name,
    )


@router.get("/limits", response_model=list[CrossLimitOut])
async def list_limits(_staff: StaffUser, session: DbSession) -> list[CrossLimitOut]:
    """**الدولُ الثلاث دائماً** — وما لم يُضبط صفران، وصفرٌ يعني «لم يُضبط فيُردّ التحويل»."""
    rows = {CountryCode(row.country_code): row for row in await cross_transfer.list_limits(session)}
    out: list[CrossLimitOut] = []
    for country in (CountryCode.LY, CountryCode.JO, CountryCode.DZ):
        row = rows.get(country)
        out.append(
            CrossLimitOut(
                country_code=country,
                currency=currency_for_country(country),
                daily_limit=row.daily_limit if row else 0,
                monthly_limit=row.monthly_limit if row else 0,
            )
        )
    return out


@router.put("/limits/{country_code}", response_model=CrossLimitOut)
async def put_limits(
    country_code: CountryCode, payload: CrossLimitUpdate, admin: SettingsWriter, session: DbSession
) -> CrossLimitOut:
    row = await cross_transfer.set_limits(
        session, actor=admin, country_code=country_code, daily=payload.daily_limit, monthly=payload.monthly_limit
    )
    await session.commit()
    return CrossLimitOut(
        country_code=country_code,
        currency=currency_for_country(country_code),
        daily_limit=row.daily_limit,
        monthly_limit=row.monthly_limit,
    )
