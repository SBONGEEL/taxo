"""بلاغُ صورةٍ كما تقرؤه اللوحة."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PhotoReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_id: uuid.UUID
    reported_by: uuid.UUID
    ride_id: uuid.UUID
    created_at: datetime
    #: `null` معلَّق — و`removed`/`restored` بعد القرار
    resolution: str | None = None
