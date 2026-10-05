from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RatingRaterType, RatingTag


class RatingCreate(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)
    # **وسومُ R10** (§٦٢-ج/٢٥) — خمسةٌ على الأكثر بلا تكرار؛ وللراكب وحدَه
    tags: list[RatingTag] = Field(default_factory=list, max_length=5)


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ride_id: uuid.UUID
    rater_type: RatingRaterType
    stars: int
    comment: str | None
    tags: list[RatingTag] = Field(default_factory=list)
    created_at: datetime
