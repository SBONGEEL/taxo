"""«المالية العامة» وأسعارُ الصرف (SPEC §٧٤-أ/٩) — **قراءةٌ وحدَها بصلاحية المالية المستقلّة، وكلُّ عرضٍ وتصديرٍ سطرٌ في التدقيق**.

**و«مالية الدولة» هي `/admin/finance/summary` القائمة نفسُها** (الدولةُ إلزاميّةٌ فيها) — وهذه تضعها متجاورةً، **كلٌّ بعملته**، ومعها
مجموعٌ تقريبيٌّ اختياريٌّ بعملةٍ مرجعيّة. **والكتابةُ الوحيدة سطرُ التدقيق، وضبطُ سعر صرفٍ للعرض** — لا مالَ يُكتب ولا يتحرّك.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Query
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Font
from pydantic import BaseModel, Field

from app.core.currency import currency_for_country
from app.core.deps import DbSession, FinanceSummaryReader
from app.models.enums import AuditAction, CountryCode, Currency
from app.schemas.finance_summary import FinanceReconciliationOut, FinanceSummaryOut, FinanceWindowOut, groups_out
from app.services import audit, finance_export, finance_overview
from app.services import finance_summary as fs

router = APIRouter(prefix="/admin/finance", tags=["admin"])


class RateOut(BaseModel):
    currency: Currency
    rate: Decimal
    set_at: datetime


class RatesOut(BaseModel):
    reference: str | None
    rates: list[RateOut]
    note: str = finance_overview.APPROX_NOTE


class RateIn(BaseModel):
    currency: Currency
    rate: Decimal = Field(gt=0, max_digits=18, decimal_places=8)


class RatesIn(BaseModel):
    reference: str = Field(min_length=3, max_length=3)
    rates: list[RateIn] = Field(min_length=1)


class CombinedMetricOut(BaseModel):
    key: str
    label: str
    #: **نصٌّ بخانتين** بالعملة المرجعيّة — `null` حين نقص سعرُ عملةٍ لها مبلغ
    approx_value: str | None
    missing: list[Currency]


class CombinedOut(BaseModel):
    reference: str
    note: str
    rates: list[RateOut]
    metrics: list[CombinedMetricOut]


class FinanceOverviewOut(BaseModel):
    countries: list[FinanceSummaryOut]
    #: **حكمٌ واحدٌ على الكلّ** — كلُّ دولةٍ تطابق دفترَها
    reconciled: bool
    combined: CombinedOut | None


async def _rates_out(session) -> RatesOut:
    reference, rows = await finance_overview.current_rates(session)
    return RatesOut(reference=reference, rates=[RateOut(currency=r.currency, rate=r.rate, set_at=r.set_at) for r in rows])


async def _overview(session, **query) -> finance_overview.Overview:
    return await finance_overview.overview(session, now=datetime.now(UTC), **query)


async def _audit(session, admin, query: dict, *, export: bool, reconciled: bool) -> None:
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.READ,
        entity_type="finance_summary",
        details={
            "view": "overview",
            "period": query["period"],
            "from_date": query["from_date"].isoformat() if query["from_date"] else None,
            "to_date": query["to_date"].isoformat() if query["to_date"] else None,
            "user_type": query["user_type"].value if query["user_type"] else None,
            "method": query["method"].value if query["method"] else None,
            "status": query["status"].value if query["status"] else None,
            "export": export,
            "reconciled": reconciled,
        },
    )


def _query(period, from_date, to_date, user_type, method, status) -> dict:
    return {"period": period, "from_date": from_date, "to_date": to_date, "user_type": user_type, "method": method, "status": status}


@router.get("/overview", response_model=FinanceOverviewOut)
async def read_overview(
    admin: FinanceSummaryReader,
    session: DbSession,
    period: fs.FinancePeriod = Query(default="month"),
    from_date: date | None = None,
    to_date: date | None = None,
    user_type: fs.FinanceUserType | None = None,
    method: fs.FinanceMethod | None = None,
    status: fs.FinanceStatus | None = None,
) -> FinanceOverviewOut:
    query = _query(period, from_date, to_date, user_type, method, status)
    result = await _overview(session, **query)
    reconciled = all(summary.reconciliation.reconciled for summary in result.summaries)
    await _audit(session, admin, query, export=False, reconciled=reconciled)
    await session.commit()
    combined = None
    if result.reference is not None and result.combined is not None:
        combined = CombinedOut(
            reference=result.reference,
            note=finance_overview.APPROX_NOTE,
            rates=[RateOut(currency=r.currency, rate=r.rate, set_at=r.set_at) for r in result.rates],
            metrics=[
                CombinedMetricOut(
                    key=m.key,
                    label=m.label,
                    approx_value=None if m.amount is None else f"{m.amount:.2f}",
                    missing=m.missing,
                )
                for m in result.combined
            ],
        )
    return FinanceOverviewOut(
        countries=[
            FinanceSummaryOut(
                window=FinanceWindowOut.of(summary.scope),
                groups=groups_out(fs.GROUPS, summary.values),
                reconciliation=FinanceReconciliationOut.of(summary.reconciliation),
            )
            for summary in result.summaries
        ],
        reconciled=reconciled,
        combined=combined,
    )


@router.get("/overview/export")
async def export_overview(
    admin: FinanceSummaryReader,
    session: DbSession,
    period: fs.FinancePeriod = Query(default="month"),
    from_date: date | None = None,
    to_date: date | None = None,
    user_type: fs.FinanceUserType | None = None,
    method: fs.FinanceMethod | None = None,
    status: fs.FinanceStatus | None = None,
) -> Response:
    """**المالية العامة إلى `.xlsx`** — عمودٌ لكلِّ دولةٍ بعملته، **والمجموعُ التقريبيُّ عمودٌ موسومٌ بسعره وتاريخه**."""
    query = _query(period, from_date, to_date, user_type, method, status)
    result = await _overview(session, **query)
    reconciled = all(summary.reconciliation.reconciled for summary in result.summaries)
    book = Workbook()
    sheet = book.active
    sheet.title = "المالية العامة"
    sheet.sheet_view.rightToLeft = True
    bold = Font(bold=True)
    head = ["المجموعة", "البند"] + [f"{s.scope.country.value} ({currency_for_country(s.scope.country).value})" for s in result.summaries]
    if result.combined is not None:
        head.append(f"{finance_overview.APPROX_NOTE} ({result.reference})")
    sheet.append(head)
    for cell in sheet[1]:
        cell.font = bold
    titles = {group.key: group.title for group in fs.GROUPS}
    combined = {m.key: m for m in result.combined or []}
    for metric in fs.METRICS.values():
        row: list[object] = [titles[metric.group], metric.label]
        for summary in result.summaries:
            value = next(item for item in summary.values if item.metric.key == metric.key)
            row.append(value.amount if value.applicable else None)
        if result.combined is not None:
            approx = combined[metric.key].amount
            row.append(approx)
        sheet.append(row)
    sheet.append([])
    sheet.append(["المطابقةُ مع الدفتر"] + ["", ""] + ["تتطابق" if s.reconciliation.reconciled else "لا تتطابق" for s in result.summaries])
    if result.combined is not None:
        sheet.append([finance_overview.APPROX_NOTE, result.reference])
        for rate in result.rates:
            sheet.append([rate.currency.value, rate.rate, rate.set_at.replace(tzinfo=None)])
    sheet.append(["حساباتُ التجربة", "مستثناةٌ دائماً"])
    out = BytesIO()
    book.save(out)
    await _audit(session, admin, query, export=True, reconciled=reconciled)
    await session.commit()
    return Response(
        content=out.getvalue(),
        media_type=finance_export.XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": 'attachment; filename="taxo-finance-overview.xlsx"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/rates", response_model=RatesOut)
async def read_rates(admin: FinanceSummaryReader, session: DbSession) -> RatesOut:
    return await _rates_out(session)


@router.put("/rates", response_model=RatesOut)
async def write_rates(payload: RatesIn, admin: FinanceSummaryReader, session: DbSession) -> RatesOut:
    """**أسعارُ صرفٍ يضعها المالك** — صفٌّ جديدٌ لكلِّ سعرٍ (التاريخُ يُحفظ)، وسطرٌ في التدقيق."""
    await finance_overview.set_rates(
        session, reference=payload.reference, rates={item.currency: item.rate for item in payload.rates}, actor=admin
    )
    await session.commit()
    return await _rates_out(session)
