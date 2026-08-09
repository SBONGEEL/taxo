from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AdminAuditLog
from app.models.enums import AuditAction
from app.models.user import User


async def record(
    session: AsyncSession,
    *,
    actor: User | None,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AdminAuditLog:
    """يضيف قيد تدقيق للجلسة — الـ commit مسؤولية الراوتر.

    يبقى القيد في نفس معاملة التغيير: إن فشل التغيير لا يبقى أثر كاذب،
    وإن نجح فلا يمكن أن ينجح بلا قيد.
    """
    entry = AdminAuditLog(
        actor_id=actor.id if actor is not None else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    session.add(entry)
    return entry
