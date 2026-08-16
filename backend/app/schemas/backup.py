"""مخطّطاتُ النسخ الاحتياطي (`design/BACKUP-AND-RESTORE.md`)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BackupSettingsOut(BaseModel):
    enabled: bool
    frequency: str
    weekday: int | None = None
    hour_local: int
    keep_count: int
    alert_after_hours: int
    alert_unpulled_count: int
    max_bytes: int | None = None


class BackupSettingsIn(BaseModel):
    enabled: bool | None = None
    frequency: str | None = Field(default=None, pattern="^(daily|weekly)$")
    weekday: int | None = Field(default=None, ge=0, le=6)
    hour_local: int | None = Field(default=None, ge=0, le=23)
    keep_count: int | None = Field(default=None, ge=1, le=365)
    alert_after_hours: int | None = Field(default=None, ge=1, le=720)
    alert_unpulled_count: int | None = Field(default=None, ge=1, le=365)
    max_bytes: int | None = Field(default=None, ge=1)


class BackupRowOut(BaseModel):
    """صفٌّ في الجدول — **ومصدرُه القرصُ لا جدولُ القاعدة**.

    فنسخةٌ حُذفت بيدٍ أو نُقلت تختفي من اللوحة كما اختفت من الواقع، ولا يبقى
    صفٌّ يَعِد بملفٍّ ليس هناك.
    """

    name: str
    taken_at: datetime | None = None
    alembic_revision: str | None = None
    encrypted: bool = False
    size_bytes: int
    pulled: bool


class BackupStateOut(BaseModel):
    settings: BackupSettingsOut
    backups: list[BackupRowOut]
    last_success_at: datetime | None = None
    # **حقائقُ لا جملٌ**: النصَّ تبنيه الشاشة (قاعدةُ `data` في الإشعار)
    stale_hours: int | None = None
    unpulled: int | None = None
    disk_percent: int | None = None
    total_bytes: int


class BackupDownloadIn(BaseModel):
    """**إعادةُ إدخال كلمة المرور** قبل توليد الرابط (الخطة §٦)."""

    password: str = Field(min_length=1)
    file: str = Field(min_length=1, max_length=64)


class BackupDownloadOut(BaseModel):
    token: str
    expires_in: int
