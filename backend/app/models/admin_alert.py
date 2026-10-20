"""**إشعاراتُ المالك بنشاط المستخدمين** (SPEC §٨١، أمرُ المالك ٢٠٢٦-١٠-٢٠) — ثلاثةُ جداول، **ولا عمودَ في جدولٍ قائم**.

* `admin_alerts` — **الحدثُ كما يُعرض**: نوعُه وسوقُه ومبلغُه وسجلُّه، **وعددُه** حين تُجمع أحداثٌ متتابعةٌ من نوعٍ واحدٍ في سوقٍ واحد
  (طلباتُ الرحلات وقتَ الذروة) — صفٌّ واحدٌ يكبر عددُه لا صفوفٌ تُغرق القائمة.
* `admin_alert_reads` — **المقروءُ لكلِّ مستلم**: صفُّ قراءةٍ يُكتب ولا يُعدَّل، **وغيابُه «غيرُ مقروء»**؛ وحدثٌ يكبر عددُه تُمحى قراءاتُه
  فيعود غيرَ مقروء لمن قرأه قبل أن يكبر.
* `admin_alert_settings` — **إعدادُ كلِّ مستلم**: كلُّ نوعٍ لكلِّ قناة (اللوحة · المتصفّح · الهاتف) وصوتُ كلِّ فئة. **وغيابُ الصفّ أو المفتاح
  «مشغَّل»** — الافتراضُ بنصِّ المالك: «الكلُّ مشغَّل».

**ولا اسمَ ولا رقمَ هاتفٍ في `data`**: قيمٌ خامٌ تكفي لرسم السطر (الطريقةُ · من ألغى · عددُ النجوم · «ضيف» · «حسابُ تجربة»)، **والتفاصيلُ
في سجلّها** تُفتح باللوحة بعد الدخول. و`kind` نصٌّ يحرسه `services/admin_alerts.CATALOG` لا تعدادٌ في القاعدة — فنوعٌ يُضاف غداً شيفرةٌ
لا ترحيلة (وهو نمطُ `feature_flags.feature_key`).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, Currency


class AdminAlert(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "admin_alerts"
    __table_args__ = (
        Index("ix_admin_alerts_created_at", "created_at"),
        Index("ix_admin_alerts_group", "group_key", "last_event_at"),
    )

    kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    #: **مجموعةُ العرض** (حسابات · مال · رحلات · دعم) — مرشِّحُ «النوع» في القائمة
    category: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    #: **فئةُ الصوت والقناة** — منها صوتُه ولونُه وقناةُ أندرويد
    tone: Mapped[str] = mapped_column(String(16), nullable=False)
    country_code: Mapped[CountryCode | None] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=True, index=True
    )
    #: **كم حدثاً يحمل هذا الصفّ** — ١ لحدثٍ واحد، وأكثرُ حين جُمعت أحداثٌ متتابعة
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    #: **مجموعُ المبالغ** حين تكون العملةُ واحدة — يُحسب في الخلفية (§14) ويُعرض كما هو
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[Currency | None] = mapped_column(pg_enum(Currency, "currency"), nullable=True)
    #: **السجلُّ الذي يُفتح** — نوعُه ومعرّفُه، **والمسارُ يُشتقّ في اللوحة لا يُقرأ من هنا**. فارغان لصفٍّ جُمع (يفتح القائمة)
    record_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    record_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    #: **مفتاحُ الجمع** — النوعُ والسوق: إليه يُضمّ حدثٌ يصل في نافذة الجمع، **وبه يُستبدل الإشعارُ على الجهاز**
    group_key: Mapped[str] = mapped_column(String(80), nullable=False)
    last_event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AdminAlertRead(Base):
    __tablename__ = "admin_alert_reads"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("admin_alerts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AdminAlertSettings(Base):
    __tablename__ = "admin_alert_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    #: `{kind: {"panel": bool, "web": bool, "phone": bool}}` — **ما غاب مشغَّل**
    kinds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    #: `{tone: bool}` — صوتُ كلِّ فئةٍ واللوحةُ مفتوحة
    sounds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
