"""**حالُ الدول غيرِ الأسواق في مُنتقي الهاتف، وعدُّ المحاولات** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٥).

* `signup_countries` — **صفٌّ لكلِّ دولةٍ غيرِ سوقٍ غيّر المالكُ حالَها**؛ وغيابُ الصفّ «متوقفة» (افتراضُ المالك للدولة الجديدة).
  **والأسواقُ الثلاثةُ ليست هنا**: حالُها من «الدول والحدود» (`country_markets` و`country_visible`) — بيتٌ واحدٌ لكلِّ سوق.
* `signup_attempts_daily` — **عدٌّ يوميٌّ لكلِّ دولةٍ لا غير**: «محاولاتٌ فقط، بلا أرقامِ هواتف» بنصّ المالك. **لا عمودَ لهاتفٍ
  ولا جهازٍ ولا عنوان** — فلا شيءَ هنا يُحذف مع حسابٍ لأن لا حسابَ فيه.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
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
    #: **نصُّ «ظاهرة»** — يحرّره المشرف؛ وفارغاً يُقال النصُّ الافتراضيّ
    visible_message: Mapped[str | None] = mapped_column(String(300), nullable=True)


class LaunchInterest(UUIDMixin, Base):
    """**«أعلمني فور الإطلاق»** (أمرُ المالك ٢٠٢٦-١١-١٨ الثاني) — رقمٌ تركه صاحبُه بيده في دولةٍ «ظاهرة» غيرِ عاملة.

    **الرقمُ وحدَه والدولة** — لا حسابَ ولا جهازَ ولا عنوان. **ويُحذف بعد رسالة الإطلاق أو بعد ١٢ شهراً** (`PRIVACY-103-NATIVE.md`)،
    والرقمُ نفسُه في الدولة نفسها صفٌّ واحد.
    """

    __tablename__ = "launch_interests"
    __table_args__ = (UniqueConstraint("country", "phone", name="uq_launch_interests_country_phone"),)

    country: Mapped[str] = mapped_column(String(2), nullable=False)
    #: `+` ورمزُ الدولة والرقمُ الوطنيّ — لاتينيٌّ أبداً
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SignupAttemptDaily(Base):
    __tablename__ = "signup_attempts_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    country: Mapped[str] = mapped_column(String(2), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
