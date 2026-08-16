"""سياسةُ رسم الإلغاء وصفوفُه كما تقرؤها اللوحة (`design/CANCELLATION-FEE.md`).

**والقيمةُ ليست هنا**: مبلغُ الرسم يبقى في `pricing_rules.cancellation_fee` حيث
هو **لكل فئةِ مركبة**، وما هنا سياسةٌ — متى يُستحقّ ومتى يُعفى وماذا يقع إن لم
يُسدَّد. ونقلُه إلى هنا يجعله رقماً واحداً لدولةٍ فيُفقد ما يميّزه.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CancellationChargeStatus,
    CountryCode,
    Currency,
    UnpaidCancellationOutcome,
)


class CancellationSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_code: CountryCode
    exempt_within_meters: int
    exempt_when_location_unknown: bool
    block_after_unpaid: int
    carrier_grace_hours: int
    unpaid_after_days: int
    unpaid_outcome: UnpaidCancellationOutcome
    updated_at: datetime


class CancellationSettingUpdate(BaseModel):
    """ما يُرسَل يُطبَّق وحدَه — والحقلُ الغائب لا يُلمس (نمطُ بقية الإعدادات).

    **وأصفارُها الثلاثةُ تعني «لم يُضبط» لا «صفراً»**: لا إيقاف، ولا مهلةَ
    للحامل، ولا إجراءَ على دَينٍ قديم — وهي حالُ التركيب الأول حتى يقرّر
    المالك، كأصفار `wallet_settings` ومبالغِ البقشيش.
    """

    exempt_within_meters: int | None = Field(default=None, ge=0, le=20_000)
    exempt_when_location_unknown: bool | None = None
    block_after_unpaid: int | None = Field(default=None, ge=0, le=100)
    carrier_grace_hours: int | None = Field(default=None, ge=0, le=720)
    unpaid_after_days: int | None = Field(default=None, ge=0, le=3650)
    unpaid_outcome: UnpaidCancellationOutcome | None = None


class CancellationChargeRow(BaseModel):
    """صفُّ رسمٍ كما يُقرأ في اللوحة — **بطرفَيه لا بمبلغه وحده**.

    والأسماءُ تُضمّ من `users` لأن الجدولَ يحمل مُعرّفات: مشرفٌ يقرأ ثمانيةَ
    محارفَ من UUID لا يعرف عمّن يتكلم، وقرارُ الإعفاء قرارٌ في حقّ إنسانَين.
    """

    id: uuid.UUID
    ride_id: uuid.UUID
    country_code: CountryCode
    amount: Decimal
    currency: Currency
    status: CancellationChargeStatus
    payer_name: str | None
    payer_phone: str | None
    beneficiary_driver_id: uuid.UUID
    beneficiary_name: str | None
    # الحاملُ (§6-أ) — فارغٌ في غير الكاش، وحضورُه يعني أن الراكب سدَّد نقداً
    # وأن المطلوبَ الآن تحويلٌ من يدِ كبتن
    carrier_driver_id: uuid.UUID | None
    carrier_name: str | None
    carrier_due_at: datetime | None
    collected_from_ride_id: uuid.UUID | None
    settled_at: datetime | None
    waive_reason: str | None
    writeoff_reason: str | None
    created_at: datetime


class ChargeReasonRequest(BaseModel):
    """السببُ المكتوبُ إلزاميّ — وهو **محتوى القيد** لا قيمةُ حقلٍ تُخفى.

    استثناءُ «أسماءُ الحقول لا قيمُها» في سجل التدقيق، كسبب إيقاف الكبتن
    وسببِ إطفاء حارس: قرارٌ يُراجَع بعد شهرٍ بلا سببه قرارٌ لا يملكه أحد.
    """

    reason: str = Field(min_length=3, max_length=500)
