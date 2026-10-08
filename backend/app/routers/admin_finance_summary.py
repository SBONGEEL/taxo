"""الملخّصاتُ المالية في اللوحة (SPEC §٦٥-د) — **صفحةُ قراءةٍ بصلاحيةٍ مستقلّة، وكلُّ عرضٍ وتصديرٍ سطرٌ في التدقيق**.

**ولا بابَ هنا يكتب مالاً** — أربعةُ أبوابٍ كلُّها `GET`: الملخّص، ومستخدمو مجموع، ومعاملاتُه، والتصدير. **والكتابةُ الوحيدةُ
سطرُ التدقيق** (`AuditAction.READ` بنوع كيانٍ مستقلٍّ `finance_summary` — **كما فعل فرعُ المحادثة**، فلا يُضاف عضوٌ إلى تعداد
`AuditAction` يُلزم اللوحةَ بترجمته).

**والصلاحيةُ `finance.summary` لا يملكها أحدٌ افتراضاً** (`permissions.SENSITIVE`): «صلاحيةٌ إداريةٌ مستقلّة لا تُعطى لكلِّ
مشرفٍ افتراضاً» بنصِّ المالك. **وحارسُها قبل كلِّ شيء**: الردُّ بـ٤٠٣ يقع قبل أن يُقرأ رقمٌ أو يُكتب سطر.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.deps import DbSession, FinanceSummaryReader
from app.models.enums import AuditAction, CountryCode
from app.models.user import User
from app.schemas.finance_summary import (
    FinanceSummaryOut,
    FinanceTransactionsOut,
    FinanceUsersOut,
    FinanceReconciliationOut,
    FinanceWindowOut,
    groups_out,
)
from app.services import audit, finance_export
from app.services import finance_summary as fs

router = APIRouter(prefix="/admin/finance/summary", tags=["admin"])

#: **نوعُ الكيان في التدقيق** — مستقلٌّ عن كلِّ ما سواه، فيُقرأ «من فتح الملخّصات» بمرشِّحٍ واحد
AUDIT_ENTITY = "finance_summary"


async def _scope(
    session: DbSession,
    *,
    country_code: CountryCode,
    period: fs.FinancePeriod,
    from_date: date | None,
    to_date: date | None,
    user_type: fs.FinanceUserType | None,
    method: fs.FinanceMethod | None,
    status: fs.FinanceStatus | None,
) -> fs.Scope:
    return await fs.build_scope(
        session,
        country=country_code,
        period=period,
        now=datetime.now(UTC),
        from_date=from_date,
        to_date=to_date,
        user_type=user_type,
        method=method,
        status=status,
    )


async def _audit(
    session: DbSession,
    actor: User,
    scope: fs.Scope,
    *,
    view: fs.FinanceView,
    metric: str | None,
    export: bool,
    extra: dict[str, Any] | None = None,
) -> None:
    """**سطرُ التدقيق بما يكفي لإعادة العرض**: من، والسوق، والفترةُ بحدّيها، والمرشِّحات، وأيُّ عرضٍ، وأتصديرٌ هو."""
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.READ,
        entity_type=AUDIT_ENTITY,
        details={
            "country_code": scope.country.value,
            "period": scope.period,
            "from_at": scope.from_at.isoformat(),
            "to_at": scope.to_at.isoformat(),
            "user_type": scope.user_type.value if scope.user_type else None,
            "method": scope.method.value if scope.method else None,
            "status": scope.status.value if scope.status else None,
            "view": view.value,
            "metric": metric,
            "export": export,
            **(extra or {}),
        },
    )


@router.get("", response_model=FinanceSummaryOut)
async def read_summary(
    admin: FinanceSummaryReader,
    session: DbSession,
    country_code: CountryCode,
    period: fs.FinancePeriod = Query(default="month"),
    from_date: date | None = None,
    to_date: date | None = None,
    user_type: fs.FinanceUserType | None = None,
    method: fs.FinanceMethod | None = None,
    status: fs.FinanceStatus | None = None,
) -> FinanceSummaryOut:
    """**الصفحةُ كلُّها** — المجاميعُ بمجموعاتها، والمطابقةُ مع الدفتر. **والسوقُ إلزاميّ**: لا رقمَ يجمع دينارين."""
    scope = await _scope(
        session, country_code=country_code, period=period, from_date=from_date, to_date=to_date,
        user_type=user_type, method=method, status=status,
    )
    result = await fs.summary(session, scope)
    await _audit(
        session, admin, scope, view=fs.FinanceView.SUMMARY, metric=None, export=False,
        extra={"reconciled": result.reconciliation.reconciled},
    )
    await session.commit()
    return FinanceSummaryOut(
        window=FinanceWindowOut.of(scope),
        groups=groups_out(fs.GROUPS, result.values),
        reconciliation=FinanceReconciliationOut.of(result.reconciliation),
    )


@router.get("/export")
async def export_view(
    admin: FinanceSummaryReader,
    session: DbSession,
    country_code: CountryCode,
    view: fs.FinanceView = Query(default=fs.FinanceView.SUMMARY),
    metric: str | None = None,
    period: fs.FinancePeriod = Query(default="month"),
    from_date: date | None = None,
    to_date: date | None = None,
    user_type: fs.FinanceUserType | None = None,
    method: fs.FinanceMethod | None = None,
    status: fs.FinanceStatus | None = None,
) -> Response:
    """**تصديرُ أيِّ عرضٍ إلى `.xlsx`** — بالدوالّ نفسِها التي يرسمها العرض، **وسطرُ تدقيقٍ قبل أن يخرج الملفّ**."""
    scope = await _scope(
        session, country_code=country_code, period=period, from_date=from_date, to_date=to_date,
        user_type=user_type, method=method, status=status,
    )
    extra: dict[str, Any] = {}
    if view is fs.FinanceView.SUMMARY:
        result = await fs.summary(session, scope)
        content = finance_export.summary_workbook(result)
        extra["reconciled"] = result.reconciliation.reconciled
        metric = None
    else:
        chosen = fs.metric_of(metric or "")
        reader = fs.users_page if view is fs.FinanceView.USERS else fs.transactions_page
        page = await reader(session, chosen, scope, limit=finance_export.EXPORT_MAX_ROWS, offset=0)
        content = (
            finance_export.users_workbook(scope, page)
            if view is fs.FinanceView.USERS
            else finance_export.transactions_workbook(scope, page)
        )
        extra.update(rows=len(page.rows), total=page.total, truncated=page.total > len(page.rows))
    await _audit(session, admin, scope, view=view, metric=metric, export=True, extra=extra)
    await session.commit()
    stamp = scope.from_at.astimezone(scope.zone).date().isoformat()
    name = f"taxo-finance-{scope.country.value}-{view.value}-{stamp}.xlsx"
    return Response(
        content=content,
        media_type=finance_export.XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            # **ملفُّ مالٍ لا يُخزَّن في وسيط** — كصورة الوثيقة
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{metric}/users", response_model=FinanceUsersOut)
async def read_users(
    metric: str,
    admin: FinanceSummaryReader,
    session: DbSession,
    country_code: CountryCode,
    period: fs.FinancePeriod = Query(default="month"),
    from_date: date | None = None,
    to_date: date | None = None,
    user_type: fs.FinanceUserType | None = None,
    method: fs.FinanceMethod | None = None,
    status: fs.FinanceStatus | None = None,
    limit: int = Query(default=50, ge=1, le=fs.MAX_PAGE),
    offset: int = Query(default=0, ge=0),
) -> FinanceUsersOut:
    """**«المستخدمون»** وراء مجموع — **فيرى المشرفُ من يصنع الألفَ دينار** (بنصِّ المالك)، مرتَّبين من الأكبر."""
    chosen = fs.metric_of(metric)
    scope = await _scope(
        session, country_code=country_code, period=period, from_date=from_date, to_date=to_date,
        user_type=user_type, method=method, status=status,
    )
    page = await fs.users_page(session, chosen, scope, limit=limit, offset=offset)
    await _audit(
        session, admin, scope, view=fs.FinanceView.USERS, metric=chosen.key, export=False,
        extra={"limit": limit, "offset": offset},
    )
    await session.commit()
    return FinanceUsersOut.of(scope, page, limit=limit, offset=offset)


@router.get("/{metric}/transactions", response_model=FinanceTransactionsOut)
async def read_transactions(
    metric: str,
    admin: FinanceSummaryReader,
    session: DbSession,
    country_code: CountryCode,
    period: fs.FinancePeriod = Query(default="month"),
    from_date: date | None = None,
    to_date: date | None = None,
    user_type: fs.FinanceUserType | None = None,
    method: fs.FinanceMethod | None = None,
    status: fs.FinanceStatus | None = None,
    limit: int = Query(default=50, ge=1, le=fs.MAX_PAGE),
    offset: int = Query(default=0, ge=0),
) -> FinanceTransactionsOut:
    """**«المعاملات»** وراء مجموع — الأكبرُ قيمةً أوّلاً، مرقَّمةً."""
    chosen = fs.metric_of(metric)
    scope = await _scope(
        session, country_code=country_code, period=period, from_date=from_date, to_date=to_date,
        user_type=user_type, method=method, status=status,
    )
    page = await fs.transactions_page(session, chosen, scope, limit=limit, offset=offset)
    await _audit(
        session, admin, scope, view=fs.FinanceView.TRANSACTIONS, metric=chosen.key, export=False,
        extra={"limit": limit, "offset": offset},
    )
    await session.commit()
    return FinanceTransactionsOut.of(scope, page, limit=limit, offset=offset)
