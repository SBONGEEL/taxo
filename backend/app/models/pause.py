"""الوقفةُ غير المخطَّطة وانتظارُ الوصول (SPEC §5.10-ب).

**وهي ليست المحطاتِ الوسيطة وإن تشابه الحساب**، والفرقُ يقرّر الشكلَ كلَّه:
المحطةَ يقرّرها **الراكبُ قبل الطلب** فتدخل التقدير والمسافةَ والرسم، والوقفةَ
يقرّرها **الكبتنُ أثناء الرحلة** بضغطة — **بعد أن قُدِّرت الأجرة**. ولذلك
**جدولٌ مستقلٌّ لا عمودٌ على `ride_stops`**: صفوفُ المحطات تدخل `stops_count`
وسقفَ المحطات وبطاقةَ العرض والتسعير، ووقفةٌ تُدسّ بينها تُغيّر أربعةَ أشياء لم
يطلبها أحد.

**ولا رسمَ ثابتٌ هنا** (بخلاف `stop_fee` للمحطات): الوقفةُ لم تُطلب في التقدير،
**فالمحاسبةُ على الوقت وحدَه**.

**ولا عمودَ «دقائق منتظَرة»**: تُقاس من `started_at`/`ended_at` كما تُقاس
المحطات — عمودان لمدةٍ واحدةٍ يفترقان.

**والمعاملاتُ تُجمَّد لحظةَ وقوعها** كـ`commission_percent_at_ride`: تعديلُ
اللوحة يحكم ما يأتي لا وقفةً يقف فيها كبتنٌ الآن.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin

# **نوعان بمصدرين مختلفين وحسابٍ واحد** — ونصٌّ لا ENUM لقاعدة
# `feature_flags.feature_key`: نوعٌ ثالثٌ يوماً بيانٌ لا ترحيلة.
#
# `pause`: وقفةٌ في منتصف الرحلة — «الراكبُ ينزل عند محلٍّ ويعود»، والعدّادُ
#          يبدأ **بالضغطة فوراً** (لا مهلةَ مجانية: الوقفةُ لم تُقدَّر أصلاً).
# `arrival`: انتظارٌ عند الوصول — يبدأ بعد «وصلتُ إلى الراكب» **ومهلةٍ مجانية**.
PAUSE_KIND_PAUSE = "pause"
PAUSE_KIND_ARRIVAL = "arrival"
PAUSE_KINDS: tuple[str, ...] = (PAUSE_KIND_PAUSE, PAUSE_KIND_ARRIVAL)


class RidePause(UUIDMixin, TimestampMixin, Base):
    """وقفةٌ واحدة — تُنشأ لحظةَ الضغط وتُغلق لحظةَ الاستئناف."""

    __tablename__ = "ride_pauses"
    __table_args__ = (
        # **وقفةٌ مفتوحةٌ واحدةٌ لكل رحلة** — فهرسٌ جزئيٌّ في القاعدة لا فحصٌ في
        # الخدمة: ضغطتان متزامنتان تقرآن «لا وقفةَ مفتوحة» فتفتحان اثنتين،
        # فيُحتسب الوقتُ **مرتين** على راكبٍ وقف مرة. وهي قاعدةُ
        # `uq_rides_active_driver` نفسُها: ما يُنتج مالاً من عدمٍ يحرسه فهرس
        Index(
            "uq_ride_pauses_open",
            "ride_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ride_pause_ends_after_it_starts",
        ),
        CheckConstraint(
            "price_per_min_at_pause >= 0 AND free_minutes_at_pause >= 0 "
            "AND max_minutes_at_pause >= 0",
            name="ride_pause_amounts_non_negative",
        ),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- المجمَّدُ لحظةَ الوقوف ---
    price_per_min_at_pause: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default="0"
    )
    free_minutes_at_pause: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    # **صفرٌ يعني «لا سقف»** لا «سقفٌ مقداره صفر» — كما يُقرأ صفرُ حدِّ التحويل
    # «لم يُضبط». وسقفٌ مقداره صفرٌ كان سينبّه الطرفين لحظةَ الضغط
    max_minutes_at_pause: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    # **تنبيهُ السقف يُختم هنا** كما يُختم على المحطة: عاملان يمرّان على الصفِّ
    # نفسِه لا يُنبِّهان مرتين (قاعدةُ `tasks/stops.py`)
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
