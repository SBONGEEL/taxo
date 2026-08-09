from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import DocumentReviewStatus, DocumentType, DriverStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.vehicle import Vehicle


class Driver(UUIDMixin, TimestampMixin, Base):
    """امتداد لـ users لحساب الكبتن."""

    __tablename__ = "drivers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[DriverStatus] = mapped_column(
        pg_enum(DriverStatus, "driver_status"),
        nullable=False,
        default=DriverStatus.PENDING,
        index=True,
    )
    cliq_alias: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rating_avg: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0.00")
    )
    is_online: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    # المفتاح الأجنبي لجدول rides يُضاف في المرحلة 3 عند إنشاء الجدول
    current_ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="driver")
    vehicles: Mapped[list["Vehicle"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    documents: Mapped[list["DriverDocument"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<Driver {self.id} ({self.status})>"


class DriverDocument(UUIDMixin, TimestampMixin, Base):
    """مستندات الكبتن: مسار الملف + حالة مراجعة مستقلة لكل مستند."""

    __tablename__ = "driver_documents"

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        pg_enum(DocumentType, "document_type"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    review_status: Mapped[DocumentReviewStatus] = mapped_column(
        pg_enum(DocumentReviewStatus, "document_review_status"),
        nullable=False,
        default=DocumentReviewStatus.PENDING,
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    driver: Mapped["Driver"] = relationship(back_populates="documents")
