"""مخطّطاتُ أهداف الكبتن (البند ١٦، §٩٧/١٦)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode

Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]


class DriverGoalIn(BaseModel):
    title: Annotated[str, Field(min_length=2, max_length=120)]
    description: Annotated[str | None, Field(max_length=500)] = None
    target: Annotated[int, Field(gt=0, le=1000)]
    starts_at: datetime
    ends_at: datetime
    reward_amount: Money
    budget_cap: Money


class DriverGoalPatch(BaseModel):
    """**الإيقافُ والاسمُ وحدَهما بعد الإنشاء** — مبلغٌ أو هدفٌ يتغيّر تحت كباتنَ يعملون عليه وعدٌ يُنقض؛ يُوقف ويُنشأ غيرُه."""

    title: Annotated[str | None, Field(min_length=2, max_length=120)] = None
    description: Annotated[str | None, Field(max_length=500)] = None
    is_active: bool | None = None


class DriverGoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    title: str
    description: str | None
    target: int
    starts_at: datetime
    ends_at: datetime
    reward_amount: Decimal
    budget_cap: Decimal
    is_active: bool
    spent: Decimal
    awards: int


class MyGoalOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    target: int
    done: int
    reward_amount: Decimal
    starts_at: datetime
    ends_at: datetime
    rewarded: bool


class MyGoalsOut(BaseModel):
    enabled: bool
    #: **عملةُ الدولة** — المبلغُ يُرسم بها في التطبيق لا بعملةٍ مفترضة
    currency: str
    goals: list[MyGoalOut]
