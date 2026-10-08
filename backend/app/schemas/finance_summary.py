"""الملخّصاتُ المالية (SPEC §٦٥-د) — **ما يُنشر للّوحة، والمبالغُ نصوصٌ بثلاث خانات** (`NUMERIC(12,3)` لا float).

**والعملةُ في كلِّ ردّ** لا في الشاشة: السوقُ يحدّدها (`currency_for_country`)، **ولا ردَّ يجمع سوقين**.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import CountryCode, Currency
from app.services.finance_summary import (
    FinancePeriod,
    FinanceMethod,
    FinanceStatus,
    FinanceUserType,
    Group,
    MetricValue,
    Page,
    Reconciliation,
    Scope,
    TransactionRow,
    UserRow,
)


class FinanceBreakdownOut(BaseModel):
    key: str
    label: str
    amount: Decimal
    count: int


class FinanceMetricOut(BaseModel):
    """مجموعٌ واحد — **رقمُه وتعريفُه وهل ينطبق عليه المرشِّح**."""

    key: str
    label: str
    #: ما يجمعه بالضبط — يُرسم تحت البطاقة كما هو
    definition: str
    unit: str
    #: **رصيدٌ الآن لا حركةُ فترة** — اللوحةُ تقول ذلك ولا تقرن الرقمَ بالفترة
    stock: bool
    warn: bool
    applicable: bool
    #: علّةُ «لا ينطبق» — وفارغةٌ حين ينطبق
    reason: str | None = None
    amount: Decimal
    #: عددُ الصفوف وراء الرقم (دفعاتٌ · قيودٌ · رحلات)
    count: int
    #: من مجموعُه غيرُ صفرٍ بين أصحاب الصفوف — **وهو العددُ تحت بطاقة الرصيد** (محافظُ عليها مال)
    users: int
    breakdown: list[FinanceBreakdownOut]

    @classmethod
    def of(cls, value: MetricValue) -> FinanceMetricOut:
        metric = value.metric
        return cls(
            key=metric.key,
            label=metric.label,
            definition=metric.definition,
            unit=metric.unit,
            stock=metric.stock,
            warn=metric.warn,
            applicable=value.applicable,
            reason=value.reason,
            amount=value.amount,
            count=value.count,
            users=value.users,
            breakdown=[
                FinanceBreakdownOut(key=line.key, label=line.label, amount=line.amount, count=line.count)
                for line in value.breakdown
            ],
        )


class FinanceGroupOut(BaseModel):
    key: str
    title: str
    layout: str
    metrics: list[FinanceMetricOut]


class FinanceDifferenceOut(BaseModel):
    key: str
    label: str
    page_amount: Decimal
    ledger_amount: Decimal
    difference_amount: Decimal


class FinanceReconciliationOut(BaseModel):
    """**{reconciled, checked_at, differences}** — والشاشةُ تصيح بالأحمر حين `reconciled` كاذبة."""

    reconciled: bool
    checked_at: datetime
    checks: int
    differences: list[FinanceDifferenceOut]

    @classmethod
    def of(cls, value: Reconciliation) -> FinanceReconciliationOut:
        return cls(
            reconciled=value.reconciled,
            checked_at=value.checked_at,
            checks=value.checks,
            differences=[
                FinanceDifferenceOut(
                    key=item.key,
                    label=item.label,
                    page_amount=item.page_amount,
                    ledger_amount=item.ledger_amount,
                    difference_amount=item.difference_amount,
                )
                for item in value.differences
            ],
        )


class FinanceFiltersOut(BaseModel):
    """المرشِّحاتُ المطبَّقة كما فهمها الخادم — **شاراتٌ تُرسم منها** لا من حالِ الشاشة."""

    user_type: FinanceUserType | None = None
    method: FinanceMethod | None = None
    status: FinanceStatus | None = None


class FinanceWindowOut(BaseModel):
    country_code: CountryCode
    currency: Currency
    period: FinancePeriod
    #: **بيوم السوق** — بداية الفترة ونهايتُها (نصفُ مفتوحة) بتوقيتٍ صريح
    from_at: datetime
    to_at: datetime
    timezone: str
    filters: FinanceFiltersOut

    @classmethod
    def of(cls, scope: Scope) -> FinanceWindowOut:
        return cls(
            country_code=scope.country,
            currency=scope.currency,
            period=scope.period,
            from_at=scope.from_at,
            to_at=scope.to_at,
            timezone=str(scope.zone),
            filters=FinanceFiltersOut(user_type=scope.user_type, method=scope.method, status=scope.status),
        )


class FinanceSummaryOut(BaseModel):
    window: FinanceWindowOut
    groups: list[FinanceGroupOut]
    reconciliation: FinanceReconciliationOut


def groups_out(groups: tuple[Group, ...], values: list[MetricValue]) -> list[FinanceGroupOut]:
    """**بترتيب الكتالوج** — والمجموعةُ تجمع ما يحمل مفتاحَها، فلا تُكتب القائمةُ مرّتين."""
    return [
        FinanceGroupOut(
            key=group.key,
            title=group.title,
            layout=group.layout,
            metrics=[FinanceMetricOut.of(value) for value in values if value.metric.group == group.key],
        )
        for group in groups
    ]


class FinanceUserRowOut(BaseModel):
    user_id: uuid.UUID | None = None
    #: **`drivers.id` لفتح ملفِّ الكبتن** — والراكبُ يُفتح بـ`user_id`؛ خلطُهما يفتح ملفَّ إنسانٍ آخر
    driver_id: uuid.UUID | None = None
    name: str | None = None
    phone_masked: str | None = None
    role: FinanceUserType
    role_label: str
    count: int
    amount: Decimal

    @classmethod
    def of(cls, row: UserRow) -> FinanceUserRowOut:
        return cls(
            user_id=row.user_id,
            driver_id=row.driver_id if row.role == FinanceUserType.DRIVER.value else None,
            name=row.name,
            phone_masked=row.phone_masked,
            role=FinanceUserType(row.role),
            role_label=row.role_label,
            count=row.count,
            amount=row.amount,
        )


class FinanceTransactionRowOut(BaseModel):
    ref_id: uuid.UUID
    occurred_at: datetime
    user_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    name: str | None = None
    role: FinanceUserType
    role_label: str
    source: str
    kind: str
    kind_label: str
    method: str | None = None
    method_label: str | None = None
    status: str | None = None
    status_label: str | None = None
    amount: Decimal
    ride_id: uuid.UUID | None = None

    @classmethod
    def of(cls, row: TransactionRow) -> FinanceTransactionRowOut:
        return cls(
            ref_id=row.ref_id,
            occurred_at=row.occurred_at,
            user_id=row.user_id,
            driver_id=row.driver_id if row.role == FinanceUserType.DRIVER.value else None,
            name=row.name,
            role=FinanceUserType(row.role),
            role_label=row.role_label,
            source=row.source,
            kind=row.kind,
            kind_label=row.kind_label,
            method=row.method,
            method_label=row.method_label,
            status=row.status,
            status_label=row.status_label,
            amount=row.amount,
            ride_id=row.ride_id,
        )


class FinanceUsersOut(BaseModel):
    """**«المستخدمون»** وراء مجموع — مرتَّبين من الأكبر، **والعددُ الكاملُ** (`total`) لترقيم الصفحات."""

    window: FinanceWindowOut
    metric: FinanceMetricOut
    total: int
    limit: int
    offset: int
    rows: list[FinanceUserRowOut]

    @classmethod
    def of(cls, scope: Scope, page: Page, *, limit: int, offset: int) -> FinanceUsersOut:
        return cls(
            window=FinanceWindowOut.of(scope),
            metric=FinanceMetricOut.of(page.value),
            total=page.total,
            limit=limit,
            offset=offset,
            rows=[FinanceUserRowOut.of(row) for row in page.rows],
        )


class FinanceTransactionsOut(BaseModel):
    """**«المعاملات»** وراء مجموع — الأكبرُ قيمةً أوّلاً، والعددُ الكامل لترقيم الصفحات."""

    window: FinanceWindowOut
    metric: FinanceMetricOut
    total: int
    limit: int
    offset: int
    rows: list[FinanceTransactionRowOut]

    @classmethod
    def of(cls, scope: Scope, page: Page, *, limit: int, offset: int) -> FinanceTransactionsOut:
        return cls(
            window=FinanceWindowOut.of(scope),
            metric=FinanceMetricOut.of(page.value),
            total=page.total,
            limit=limit,
            offset=offset,
            rows=[FinanceTransactionRowOut.of(row) for row in page.rows],
        )
