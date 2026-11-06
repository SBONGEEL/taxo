"""«الإحصاءات» — زياراتُ الموقع وتحميلاتُه وأرقامُ Play (أمرُ المالك ٢٠٢٦-١١-٠٤، `design/SITE-STATS.md`).

**مجاميعُ يوميّةٌ وحدَها**: لا عمودَ لمستخدمٍ ولا لجهازٍ ولا لعنوان. **والمفتاحُ طبيعيٌّ مركّب** (اليوم والبُعد)، فالعدُّ `INSERT … ON
CONFLICT DO UPDATE SET n = n + 1` ذرّيٌّ في القاعدة نفسِها — **لا قراءةَ ثمّ كتابة، فلا قفلَ يلزم ولا عدَّ يضيع بين طلبين**.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

#: مصادرُ الزيارة — **المُحيلُ يُصنَّف ثمّ يُرمى**، فلا يُحفظ رابطٌ قد يحمل معرّفاً
SOURCES = ("facebook", "google", "direct", "other")
#: التطبيقان على الموقع
APPS = ("rider", "driver")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class SiteDaily(Base):
    """زياراتُ صفحةٍ في يومٍ من مصدرٍ وبلد. **والفريدُ يقوله متصفّحُ الزائر** («أوّلُ زيارةٍ لي اليوم») لا معرّفٌ عندنا."""

    __tablename__ = "site_daily"
    __table_args__ = (CheckConstraint(_in("source", SOURCES), name="ck_site_daily_source"),)

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    path: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(12), primary_key=True)
    country: Mapped[str] = mapped_column(String(2), primary_key=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    uniques_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    uniques_week: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    uniques_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))


class SiteDownloadDaily(Base):
    """تحميلاتُ حزمةٍ من الموقع في يومٍ وبلد: **الملفُّ الكاملُ** (`downloads`) والضغطُ على الزرّ (`clicks`) منفصلين."""

    __tablename__ = "site_downloads_daily"
    __table_args__ = (CheckConstraint(_in("app", APPS), name="ck_site_downloads_daily_app"),)

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    app: Mapped[str] = mapped_column(String(8), primary_key=True)
    country: Mapped[str] = mapped_column(String(2), primary_key=True)
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))


class PlayStatsDaily(Base):
    """أرقامُ Play ليومٍ وحزمةٍ وبلد — **من تقارير Play الرسميّة** (`stats/installs/…_country.csv`)، تُستورد يوميّاً وتُستبدل بآخر نسخة."""

    __tablename__ = "play_stats_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    package: Mapped[str] = mapped_column(String(64), primary_key=True)
    country: Mapped[str] = mapped_column(String(2), primary_key=True)
    installs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    uninstalls: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    active_devices: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class StatsImport(UUIDMixin, TimestampMixin, Base):
    """استيرادٌ واحد — **ومنه «آخرُ استيراد» في رأس الشاشة**، ناجحاً أو بعلّة سقوطه."""

    __tablename__ = "stats_imports"
    __table_args__ = (
        CheckConstraint("status IN ('ok', 'failed')", name="ck_stats_imports_status"),
        Index("ix_stats_imports_ran_at", "ran_at"),
    )

    source: Mapped[str] = mapped_column(String(16), nullable=False)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(8), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
