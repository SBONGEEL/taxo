from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import AuditAction


class AdminAuditLog(UUIDMixin, TimestampMixin, Base):
    """سجل تدقيق لكل إجراء إداري (SPEC القسم 14).

    `details` لا يحمل قيماً سرية أبداً — أسماء الحقول المتغيّرة فقط.
    `actor_id` يبقى بعد حذف الحساب (SET NULL) حتى لا يضيع أثر الإجراء.
    """

    __tablename__ = "admin_audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[AuditAction] = mapped_column(
        pg_enum(AuditAction, "audit_action"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<AdminAuditLog {self.action} {self.entity_type}>"
