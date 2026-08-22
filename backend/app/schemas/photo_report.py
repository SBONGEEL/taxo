"""بلاغُ صورةٍ كما تقرؤه اللوحة."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PhotoReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_id: uuid.UUID
    # **الاسمُ والرقمُ يخرجان هنا وحدَهما** — كالخريطةِ الحيّة: قرارٌ بشريٌّ
    # على شخصٍ بعينه لا يُتّخذ على معرّفٍ سُداسيٍّ عشريّ
    subject_name: str | None = None
    subject_phone: str | None = None
    reported_by: uuid.UUID
    reporter_name: str | None = None
    ride_id: uuid.UUID
    created_at: datetime
    #: `null` معلَّق — و`removed`/`restored` بعد القرار
    resolution: str | None = None
