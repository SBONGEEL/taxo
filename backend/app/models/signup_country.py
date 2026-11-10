"""**حالُ الدول غيرِ الأسواق في مُنتقي الهاتف، وعدُّ المحاولات** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٥).

* `signup_countries` — **صفٌّ لكلِّ دولةٍ غيرِ سوقٍ غيّر المالكُ حالَها**؛ وغيابُ الصفّ «متوقفة» (افتراضُ المالك للدولة الجديدة).
  **والأسواقُ الثلاثةُ ليست هنا**: حالُها من «الدول والحدود» (`country_markets` و`country_visible`) — بيتٌ واحدٌ لكلِّ سوق.
* `signup_attempts_daily` — **عدٌّ يوميٌّ لكلِّ دولةٍ لا غير**: «محاولاتٌ فقط، بلا أرقامِ هواتف» بنصّ المالك. **لا عمودَ لهاتفٍ
  ولا جهازٍ ولا عنوان** — فلا شيءَ هنا يُحذف مع حسابٍ لأن لا حسابَ فيه.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import SignupDisplay


class SignupCountry(TimestampMixin, Base):
    __tablename__ = "signup_countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    display: Mapped[SignupDisplay] = mapped_column(
        pg_enum(SignupDisplay, "signup_display"), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SignupAttemptDaily(Base):
    __tablename__ = "signup_attempts_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    country: Mapped[str] = mapped_column(String(2), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
