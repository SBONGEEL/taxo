"""**إعداداتُ متابعة الوثائق لكلِّ دولة** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ١ و٢) — تُضبط من اللوحة، وغيابُ الصفِّ افتراضاتُ المالك.

* `exceptional_deadline_days` — **مهلةُ رفع الوثائق** لمن اعتُمد دونها (الافتراضُ ١٤ بنصّ المالك)؛ تذكيرٌ قبلها بثلاثة أيامٍ وبيوم،
  **وبعدها تجميدٌ آليّ** حتى تُرفع.
* `exceptional_reminder_days` — **تكرارُ التذكير** ما دامت الوثائقُ ناقصة: ١ يوميّ · ٣ كلَّ ثلاثة أيام · ٧ أسبوعيّ.
* `expiry_notice_days` — **أيامُ التنبيه قبل انتهاء وثيقة** (كانت ٣٠/٧/١ ثابتةً بقرار ٢٠٢٦-٠٨-٢٥، وصارت من اللوحة بأمر ٢٠٢٦-١١-١٠).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, SmallInteger, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import CountryCode

DEFAULT_DEADLINE_DAYS = 14
DEFAULT_REMINDER_DAYS = 3
DEFAULT_EXPIRY_NOTICE_DAYS: tuple[int, ...] = (30, 7, 1)
REMINDER_CHOICES: frozenset[int] = frozenset({1, 3, 7})


class DocumentSetting(TimestampMixin, Base):
    __tablename__ = "document_settings"

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), primary_key=True)
    exceptional_deadline_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_DEADLINE_DAYS))
    )
    exceptional_reminder_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text(str(DEFAULT_REMINDER_DAYS))
    )
    expiry_notice_days: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, server_default=text("'{30,7,1}'")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
