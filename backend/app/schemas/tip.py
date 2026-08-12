"""مخطّطاتُ البقشيش (SPEC القسم 6.5، المرحلة 12-و)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TipCreate(BaseModel):
    """المبلغُ وحده — **ولا `method`**: القناةُ المحفظةُ وحدها اليوم.

    وحقلٌ يقبل قناةً لا توجد إلا واحدةٌ منها يجعل العميلَ يظنّ أن له اختياراً،
    ثم يُرفض ما يختاره. ويومَ تُضاف البطاقةُ يُضاف الحقلُ معها.

    والحدُّ الأعلى هنا حدُّ **نقلٍ** لا سياسة: السقفُ الحقيقي
    `payment_settings.tip_max` per-country، ويُفحص في الخدمة.
    """

    amount: Decimal = Field(gt=0, le=1000, decimal_places=3)


class TipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ride_id: uuid.UUID
    amount: Decimal
    currency: str
    created_at: datetime


class TipOptionsOut(BaseModel):
    """ما ترسمه شاشةُ التقييم — **أو لا ترسمه**.

    `offered=false` يعني ألّا تظهر الأزرارُ أصلاً: مفتاحٌ مطفأ، أو محفظةٌ
    معطّلة (القناةُ الوحيدة)، أو مبالغُ لم تُضبط. **ولا زرَّ معطَّلاً**: زرُّ
    بقشيشٍ لا يعمل يرفع توقّعَ الكبتن ثم يخيّبه، ويجعل الراكبَ يظن أن الخدمة
    معطوبة لا أنها غير مفعّلة.
    """

    offered: bool
    currency: str
    presets: list[Decimal] = []
    max_amount: Decimal = Decimal("0")
    # البقشيشُ المُعطى على هذه الرحلة إن وُجد — فالشاشةُ تعرض «شكرتَ الكبتن»
    # بدل أزرارٍ تُرفض بـ409 عند الضغط
    given: TipOut | None = None
