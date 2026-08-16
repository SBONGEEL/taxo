"""النسخُ الاحتياطي — الجدولةُ والسجلّ (`design/BACKUP-AND-RESTORE.md`).

**جدولٌ واحدٌ عامٌّ لا per-country**: الخادمُ واحدٌ وقاعدةُ البيانات واحدة — كـ
`security_settings` بالضبط وللسبب نفسِه. وإعدادٌ per-country هنا يعني سوقين
يطلبان نسخةً من قاعدةٍ واحدة، فتُؤخذ مرتين أو تُقرأ إحداهما «لم تُؤخذ».

**والفشلُ صفٌّ يُكتب لا صمت**: أخطرُ عطبٍ في هذا النظام كلِّه **نسخةٌ لم تُؤخذ
ولم يعلم أحد** — فالصفُّ يُكتب بحالته ونصِّ خطئه، ومنه يُبنى التنبيه.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

# **٢٦ ساعةً لا ٢٤** (الخطة §٣): نسخةٌ يوميةٌ في الثالثة صباحاً قد تتأخر ربعَ
# ساعةٍ بحكم دورة beat، وتنبيهٌ عند ٢٤ يُطلق إنذاراً كاذباً كلَّ يومٍ تقريباً —
# وإنذارٌ يُقرأ كاذباً مرةً يُهمل في المرة التي يصدق فيها.
DEFAULT_ALERT_AFTER_HOURS = 26
DEFAULT_KEEP_COUNT = 7
DEFAULT_ALERT_UNPULLED = 3
DEFAULT_HOUR_LOCAL = 3


class BackupStatus:
    """**نصٌّ لا ENUM**: ثلاثُ حالاتٍ لا تدخل استعلاماً بشرطٍ مركّب، وقيمةٌ رابعةٌ
    يوماً تصير بياناً لا ترحيلةً بـ`ALTER TYPE` وذاكرةِ asyncpg."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class BackupSetting(UUIDMixin, TimestampMixin, Base):
    """صفٌّ واحدٌ للنظام كلِّه."""

    __tablename__ = "backup_settings"
    __table_args__ = (
        CheckConstraint(
            "hour_local >= 0 AND hour_local <= 23", name="backup_hour_in_day"
        ),
        CheckConstraint(
            "weekday IS NULL OR (weekday >= 0 AND weekday <= 6)",
            name="backup_weekday_in_week",
        ),
        CheckConstraint("keep_count > 0", name="backup_keep_positive"),
        CheckConstraint(
            "max_bytes IS NULL OR max_bytes > 0", name="backup_max_bytes_positive"
        ),
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # `daily` أو `weekly` — نصٌّ لنفس سبب `BackupStatus`
    frequency: Mapped[str] = mapped_column(
        String(16), nullable=False, default="daily", server_default="daily"
    )
    # ٠ = الاثنين (كـ`date.weekday`)، ولا معنى له في `daily`
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # **بالتوقيت المحلي للأردن لا UTC**: من يكتب «٣ صباحاً» يقصد الثالثةَ عنده
    hour_local: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_HOUR_LOCAL, server_default=text("3")
    )

    keep_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_KEEP_COUNT, server_default=text("7")
    )
    alert_after_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_ALERT_AFTER_HOURS,
        server_default=text("26"),
    )
    alert_unpulled_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_ALERT_UNPULLED,
        server_default=text("3"),
    )
    # **سقفُ مساحةٍ يُنبَّه عند ٨٠٪ منه ولا يحذف** (قرارُ المالك ٣): الحذفُ
    # الآليُّ بموجب مساحةٍ يمحو ما لم يملكه أحد، والخطأُ هنا غيرُ متماثل —
    # قرصٌ يمتلئ يُصلَح بأمر، ونسخةٌ حُذفت ولم تُسحب **لا تعود**
    max_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class BackupRun(UUIDMixin, TimestampMixin, Base):
    """نسخةٌ واحدةٌ كما وقعت — **وصفُّها يُكتب قبل أن تبدأ**.

    فلو مات العاملُ في منتصف الدمب لبقي صفٌّ `running` عالقاً يُقرأ **محاولةً لم
    تكتمل**، وهو أصدقُ من غيابٍ يُقرأ «لم تُطلب نسخةٌ أصلاً».

    **و«سُحبت» ليست عموداً يُكتب من التطبيق** بل علامةٌ على القرص
    (`<name>/.pulled`) يكتبها سكربتُ السحب: السحبُ يقع عبر SSH بلا مرورٍ بالـAPI
    — وهو شرطُ الخطة — فعمودٌ ينتظر نداءً لن يأتي يكذب دائماً.
    """

    __tablename__ = "backup_runs"

    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=BackupStatus.RUNNING
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    alembic_revision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    encrypted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # **نصُّ الخطأ يُخزَّن**: «فشلت» بلا سببٍ تجعل المالكَ يعيد المحاولةَ في
    # قرصٍ ممتلئٍ عشرَ مرات
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # من طلبها بيده — و`NULL` تعني المهمّةَ الدورية (قاعدةُ `totp_reset`:
    # صفٌّ ينسب فعلاً إلى من لم يفعله أسوأُ من صفٍّ بلا فاعل)
    requested_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
