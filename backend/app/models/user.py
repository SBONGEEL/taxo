from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, UserRole

if TYPE_CHECKING:
    from app.models.driver import Driver


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # الهاتف هو مُعرّف الدخول — مخزّن بصيغة E.164
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), nullable=False, default=UserRole.RIDER
    )
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # nullable: حسابات OTP-only بعد تفعيل مزود SMS لن يكون لها كلمة مرور
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    driver: Mapped["Driver | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<User {self.phone} ({self.role})>"
