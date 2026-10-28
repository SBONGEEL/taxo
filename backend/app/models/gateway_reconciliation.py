"""**تقريرُ المطابقة اليوميّة** (SPEC §٨٧/٣، أمرُ المالك ٢٠٢٦-١٠-٢٨) — ما يقوله الوسيطُ عن كلِّ دفعةٍ مقابلَ ما عندنا.

**تقريرٌ لا يكتب في الدفتر ولا يغيّر حالَ دفعة** — الافتراقُ يُعرض ويُشعَر به المالك، والتصحيحُ يمرّ بأبوابه المبنيّة.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class GatewayReconciliation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gateway_reconciliations"
    __table_args__ = (Index("ix_gateway_reconciliations_created_at", "created_at"),)

    integration: Mapped[str] = mapped_column(String(40), nullable=False)
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    mismatched: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    unreachable: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    #: **الافتراقاتُ بتفصيلها** (`items`) ومجاميعُ دفتر الوسيط حيث يُقرأ (`ledger`) — معرّفاتٌ ومبالغُ لا أسماءَ ولا هواتف
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    #: `daily` من الدورة اليوميّة، `manual` من زرِّ المالك
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="daily", server_default=text("'daily'"))
