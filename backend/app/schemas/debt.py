"""مخطّطاتُ دَينِ الكبتن — **شاشةٌ تقول ثلاثةً لا «حسابك مجمَّد»**.

**نصُّ المحجوب يقول ثلاثةً** (قرارُ المالك 2026-08-30): **المبلغَ بالضبط**،
**وسبيلَ السداد**، **وأن العملَ يعود فور السداد**. فالحقولُ الثلاثةُ حاضرةٌ في
الردّ — **ولا تخترعها الشاشة**: الرقمُ من الجدول، والحسابُ من إعدادات السوق،
والوعدُ من الخلفية التي تعرف متى يُرفع المنع.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    Currency,
    DriverDebtSource,
    DriverDebtStatus,
    ProviderOrderStatus,
)


class DriverDebtRowOut(BaseModel):
    """صفٌّ واحدٌ — **ومعه رحلتُه**، فمن سأل «مِمَّ نشأ؟» وجد الجواب."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: DriverDebtSource
    amount: Decimal
    collected: Decimal
    currency: Currency
    status: DriverDebtStatus
    ride_id: uuid.UUID | None = None
    created_at: datetime


class DriverDebtStateOut(BaseModel):
    """حالُ الدَّين — **نداءٌ واحدٌ لشاشةٍ واحدة**، كـ`AdvanceStateOut`."""

    total: Decimal
    currency: Currency
    #: **العَلَمُ الذي يقرؤه التوزيع** — لا حسابٌ تعيده الشاشة
    blocked: bool
    #: **`null` = لا سقفَ مضبوط**، فلا يُقال للكبتن رقمٌ لا وجود له
    ceiling: Decimal | None = None
    #: **سبيلُ السداد** — حسابُ كليك للسوق، و`null` تعني «لم يُضبط بعد»
    cliq_alias: str | None = None
    review_min_minutes: int
    review_max_minutes: int
    rows: list[DriverDebtRowOut]


class DebtPaymentIn(BaseModel):
    """**المبلغُ يكتبه الكبتن** لأنه يختار كم يسدّد — والجزئيُّ مقبول."""

    amount: Decimal = Field(gt=0)


class DebtClaimOut(BaseModel):
    """مطالبةُ سدادٍ يدويّة — نفسُ شكل مطالبة الاشتراك، وهو مقصود."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cart_id: str
    amount: Decimal
    currency: Currency
    status: ProviderOrderStatus
    failure_reason: str | None = None
    created_at: datetime
    qr_url: str | None = None
    alias: str = ""
    review_min_minutes: int = 3
    review_max_minutes: int = 5


class DebtConfirmIn(BaseModel):
    """**ما وصل فعلاً** لا ما فُتحت به المطالبة — يقرؤه المشرفُ من كشفه."""

    credited: Decimal = Field(gt=0)


class AdminDebtOut(BaseModel):
    """صفُّ الدَّين كما تقرؤه اللوحة — ومعه صاحبُه."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_id: uuid.UUID
    driver_name: str
    driver_phone: str | None = None
    amount: Decimal
    collected: Decimal
    currency: Currency
    status: DriverDebtStatus
    source: DriverDebtSource
    ride_id: uuid.UUID | None = None
    created_at: datetime


class DebtWriteOffIn(BaseModel):
    """**شطبٌ بسببٍ مكتوب** — ولا شطبَ بلا سبب."""

    reason: str = Field(min_length=3, max_length=300)
