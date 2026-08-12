from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import AuditAction


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    # اسمُ من فعل، مضموماً في نفس الاستعلام — و`None` حين حُذف حسابُه
    # (`actor_id` بـ`SET NULL`): يبقى القيدُ ويضيع الاسم، لا العكس. وضمُّه هنا
    # لا نداءً لكل صف: صفحةٌ من مئتي قيدٍ لا تصير مئتي استعلام
    actor_name: str | None = None
    action: AuditAction
    entity_type: str
    entity_id: uuid.UUID | None
    details: dict[str, Any] | None
    created_at: datetime
