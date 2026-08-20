"""النسخُ الاحتياطي — الأخذُ والاحتفاظُ والتنبيه (`design/BACKUP-AND-RESTORE.md`).

**والمنفِّذُ Celery beat لا cron النظام**: cron يُحرَّر بيدٍ ثانية فيصير للموعد
**مصدرا حقيقةٍ** يفترقان أوّلَ تعديلٍ من اللوحة. والشكلُ هو شكلُ
`subscriptions.renew_due`: **دورةٌ ثابتةٌ في الكود تسأل «هل حان الموعدُ ولم
تُؤخذ نسخةٌ بعدُ اليوم؟»**، والموعدُ بيانٌ في القاعدة.

**والاحتفاظُ هو القرارُ الذي يُفقد به المال** (قرارُ المالك ٢): **لا يُحذف ما لم
يُسحب مهما بلغ العدد**. فالحذفُ يقع على المسحوبةِ الزائدةِ عن `keep_count`؛ وإن
تجاوزت **غيرُ المسحوبة** العددَ **يُنبَّه ولا يُحذف** — لأن الخطأ غيرُ متماثل:
قرصٌ يمتلئ عطبٌ يُصلَح بأمرٍ واحد، ونسخةٌ حُذفت ولم يملكها أحدٌ **لا تعود**.

**والحذفُ بعد نجاح التالية لا قبلها**: من يحذف ليُفرغ مكاناً ثم يفشل دمبُه يكون
قد سلّم نسختين مقابل صفر.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import settings
from app.core.exceptions import Conflict
from app.models.backup import (
    DEFAULT_ALERT_AFTER_HOURS,
    BackupRun,
    BackupSetting,
    BackupStatus,
)
from app.models.enums import CountryCode

logger = logging.getLogger(__name__)

BACKUP_ROOT = Path(os.getenv("BACKUP_ROOT", "/app/var/backups"))
SCRIPT = Path(os.getenv("BACKUP_SCRIPT", "/app/scripts/backup.sh"))

# **قفلٌ يمنع نسختين معاً**: دمبان متزامنان يملآن القرصَ ويتنازعان I/O في أسوأ
# لحظة. وعمرُه ساعةٌ — أطولُ من أيِّ دمبٍ معقول، وأقصرُ من أن يُعطّل يوماً كاملاً
LOCK_KEY = "backup:running"
LOCK_TTL_SECONDS = 3600

# علامةُ السحب — **يكتبها سكربتُ السحب على القرص لا التطبيق**: السحبُ يقع عبر
# SSH بلا مرورٍ بالـAPI (وهو شرطُ الخطة: اللحظةُ التي تحتاج فيها نسخةً هي
# اللحظةُ التي يكون فيها التطبيقُ ساقطاً)، فعمودٌ ينتظر نداءً لن يأتي يكذب دائماً
PULLED_MARKER = ".pulled"


class BackupAlreadyRunning(Conflict):
    code = "backup_already_running"
    message = "نسخةٌ احتياطيةٌ قيد الأخذ الآن"


def _now() -> datetime:
    return datetime.now(UTC)


async def get_settings(session: AsyncSession) -> BackupSetting:
    """صفُّ الإعدادات — يُنشأ بقيمِ الافتراض إن لم يكن. الـcommit للمستدعي."""
    row = await session.scalar(select(BackupSetting).limit(1))
    if row is None:
        row = BackupSetting()
        session.add(row)
        await session.flush()
    return row


async def _zone(session: AsyncSession) -> ZoneInfo:
    """مِنطقةُ الأردن — **من `services/stats.py` نفسِه** لا نسخةٌ ثانية."""
    from app.services.stats import _zone as stats_zone

    return await stats_zone(session, CountryCode.JO)


# ------------------------------------------------------------ الأخذ


@dataclass(frozen=True)
class BackupResult:
    name: str
    size_bytes: int
    alembic_revision: str | None
    encrypted: bool


def _read_manifest(path: Path) -> dict:
    return json.loads((path / "manifest.json").read_text(encoding="utf-8"))


def _dir_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


async def _run_script() -> str:
    """يشغّل `backup.sh` ويعيد اسمَ النسخة. يرفع `RuntimeError` بنصِّ الخطأ.

    **ولا يُعاد كتابةُ الدمب بلغةِ بايثون**: السكربتُ هو ما يناديه المالكُ عبر
    SSH أيضاً، وبابان يُنتجان نسخةً بشكلين هما بابان يفترقان.
    """
    process = await asyncio.create_subprocess_exec(
        "/bin/bash",
        str(SCRIPT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    output = (stdout or b"").decode("utf-8", "replace")
    if process.returncode != 0:
        raise RuntimeError(output.strip()[-2000:] or "فشل السكربت بلا مخرجات")
    for line in reversed(output.splitlines()):
        if line.startswith("OK "):
            return Path(line[3:].strip()).name
    raise RuntimeError(output.strip()[-2000:] or "لم يُعلن السكربتُ اسمَ النسخة")


async def take(
    session: AsyncSession, *, requested_by: str | None = None
) -> BackupRun:
    """يأخذ نسخةً ويكتب صفَّها. الـcommit للمستدعي.

    **والصفُّ يُكتب قبل أن تبدأ** ويُثبَّت وحدَه: لو مات العاملُ في منتصف الدمب
    لبقي صفٌّ `running` يُقرأ «محاولةٌ لم تكتمل» — وهو أصدقُ من غيابٍ يُقرأ «لم
    تُطلب نسخةٌ أصلاً»، وهذا النظامُ كلُّه قائمٌ على ألّا يقع فشلٌ صامت.
    """
    run = BackupRun(
        name=f"pending-{_now():%Y%m%d-%H%M%S}",
        status=BackupStatus.RUNNING,
        requested_by=requested_by,
    )
    session.add(run)
    await session.commit()

    try:
        name = await _run_script()
    except Exception as exc:  # noqa: BLE001 - يُخزَّن نصُّه ويُعاد رفعُه
        run.status = BackupStatus.FAILED
        run.finished_at = _now()
        run.error = str(exc)[:4000]
        await session.commit()
        logger.error("backup failed: %s", exc)
        return run

    path = BACKUP_ROOT / name
    manifest = _read_manifest(path)
    run.name = name
    run.status = BackupStatus.SUCCEEDED
    run.finished_at = _now()
    run.size_bytes = _dir_size(path)
    run.alembic_revision = manifest.get("alembic_revision")
    run.encrypted = bool(manifest.get("encrypted"))
    await session.commit()

    # **والتنظيفُ بعد نجاحها لا قبلها** — انظر رأسَ الملف
    prune(await get_settings(session))
    return run


# ------------------------------------------------------------ الاحتفاظ


def is_pulled(path: Path) -> bool:
    return (path / PULLED_MARKER).exists()


def existing() -> list[Path]:
    """النسخُ على القرص، الأحدثُ أولاً — **والقرصُ هو المصدر لا الجدول**.

    فنسخةٌ حُذفت بيدٍ أو نُقلت تختفي من اللوحة كما اختفت من الواقع، ولا يبقى
    صفٌّ يَعِد بملفٍّ ليس هناك.
    """
    if not BACKUP_ROOT.exists():
        return []
    return sorted(
        (
            item
            for item in BACKUP_ROOT.iterdir()
            if item.is_dir() and not item.name.startswith(".")
        ),
        key=lambda item: item.name,
        reverse=True,
    )


def prune(setting: BackupSetting) -> list[str]:
    """يحذف **المسحوبةَ** الزائدةَ عن `keep_count` ويعيد أسماءَ ما حُذف.

    **وغيرُ المسحوبة لا تُعدّ في السقف ولا تُحذف** — قرارُ المالك ٢.
    """
    pulled = [item for item in existing() if is_pulled(item)]
    removed: list[str] = []
    for item in pulled[setting.keep_count :]:
        shutil.rmtree(item, ignore_errors=True)
        removed.append(item.name)
    if removed:
        logger.info("pruned pulled backups: %s", ", ".join(removed))
    return removed


def unpulled_count() -> int:
    return sum(1 for item in existing() if not is_pulled(item))


def total_bytes() -> int:
    return sum(_dir_size(item) for item in existing())


# ------------------------------------------------------------ الموعد


async def is_due(session: AsyncSession) -> bool:
    """هل حان الموعدُ ولم تُؤخذ نسخةٌ ناجحةٌ بعدُ في نافذته؟

    **والمقارنةُ بالتوقيت المحلي** (قاعدةُ «يومِ الدولة»): من يكتب «٣ صباحاً»
    يقصد الثالثةَ عنده، وخادمٌ بـUTC يأخذها السادسةَ في عمّان.
    """
    setting = await get_settings(session)
    if not setting.enabled:
        return False

    local = _now().astimezone(await _zone(session))
    if local.hour < setting.hour_local:
        return False
    if setting.frequency == "weekly":
        if setting.weekday is None or local.weekday() != setting.weekday:
            return False

    last = await last_success(session)
    if last is None:
        return True
    # **نافذةُ اليوم لا «مضت ٢٤ ساعة»**: نسخةٌ أُخذت أمس الثالثةَ وأخرى اليومَ
    # الثانيةَ والنصف تجعل الفرقَ ٢٣٫٥ ساعة، فيُتخطّى موعدُ اليوم بلا سبب
    window_start = local.replace(
        hour=setting.hour_local, minute=0, second=0, microsecond=0
    )
    if setting.frequency == "weekly":
        window_start -= timedelta(days=7)
    return last.astimezone(local.tzinfo) < window_start


def _newest_on_disk() -> datetime | None:
    """وقتُ أحدث نسخةٍ **موجودةٍ فعلاً** — من بيانها لا من جدولٍ يصف محاولة."""
    for item in existing():
        try:
            taken = _read_manifest(item).get("taken_at")
        except (OSError, ValueError):  # pragma: no cover - بيانٌ تالف
            continue
        if taken:
            return datetime.fromisoformat(taken)
    return None


async def last_success(session: AsyncSession) -> datetime | None:
    """آخرُ نسخةٍ ناجحة — **والقرصُ يسبق الجدول**.

    `backup_runs` سجلُّ **محاولاتٍ** مرّت من هذا التطبيق؛ والقرصُ سجلُّ **ما
    وُجد**. والمالكُ يشغّل `backup.sh` عبر SSH أيضاً (وهو ما يفعله
    `pull-backup.ps1 -Now`)، فتلك نسخةٌ صحيحةٌ بلا صفّ.
    
    ولو قُرئ الجدولُ وحدَه لوقع أمران: اللوحةُ تقول «لا توجد نسخة» وفي جدولها
    نسخة، **وأخطرُ منه** أن `is_due` يعدّ الموعدَ فائتاً فيأخذ نسخةً ثانيةً بعد
    دقائقَ من الأولى.

    **والأحدثُ منهما هو الجواب** لا أحدُهما: صفٌّ ناجحٌ لنسخةٍ حُذفت بيدٍ لا
    يجوز أن يُبقي «آخرَ نجاح» متأخراً عن قرصٍ فيه أحدثُ منها، والعكسُ كذلك.
    """
    row = await session.scalar(
        select(BackupRun.finished_at)
        .where(BackupRun.status == BackupStatus.SUCCEEDED)
        .order_by(desc(BackupRun.finished_at))
        .limit(1)
    )
    disk = _newest_on_disk()
    if row is None:
        return disk
    if disk is None:
        return row
    return max(row, disk)


# ------------------------------------------------------------ التنبيهات


@dataclass(frozen=True)
class Alerts:
    """ما يستحقّ أن يوقظ أحداً — **حقائقُ لا جملٌ**، والنصُّ يُبنى عند الإرسال."""

    stale_hours: int | None
    unpulled: int | None
    disk_percent: int | None
    # امتلاءُ **نظام الملفات** كلِّه — لا النسخُ وحدَها
    filesystem_percent: int | None = None
    documents_bytes: int = 0

    @property
    def any(self) -> bool:
        return (
            self.stale_hours is not None
            or self.unpulled is not None
            or self.disk_percent is not None
            or self.filesystem_percent is not None
        )


async def alerts(session: AsyncSession) -> Alerts:
    setting = await get_settings(session)
    if not setting.enabled:
        # **مطفأً لا تنبيه**: من أطفأها يعرف، وإنذارٌ يومئٌ على قرارٍ اتُّخذ
        # يُهمَل خلال أسبوع — ثم يُهمَل معه الإنذارُ الذي يصدق
        return Alerts(None, None, None)

    last = await last_success(session)
    threshold = setting.alert_after_hours or DEFAULT_ALERT_AFTER_HOURS
    stale = None
    if last is None:
        stale = threshold
    else:
        hours = int((_now() - last).total_seconds() // 3600)
        if hours >= threshold:
            stale = hours

    waiting = unpulled_count()
    unpulled = waiting if waiting >= setting.alert_unpulled_count else None

    disk = None
    if setting.max_bytes:
        percent = int(total_bytes() * 100 / setting.max_bytes)
        if percent >= 80:
            disk = percent

    # **والقرصُ نفسُه يُقاس، لا النسخُ وحدَها** (2026-08-20).
    #
    # كان التنبيهُ يقارن حجمَ النسخ بسقفٍ مضبوط، **فقرصٌ يمتلئ بالوثائق لا
    # يُرى**: الكبتنُ يرفع إحدى عشرةَ وثيقة، وألفٌ وثمانمئة كبتنٍ يبلغون مئةَ
    # جيجا. وحين يمتلئ يتوقف كلُّ شيء — القاعدةُ والنسخُ والسجلات معاً —
    # **ويكون أولُ ما يفشل هو النسخةُ التي كانت ستنقذنا**.
    #
    # ولا سقفَ يُضبط هنا: القرصُ يقول سعتَه بنفسه.
    filesystem = None
    try:
        usage = shutil.disk_usage(storage.root())
        used = int((usage.total - usage.free) * 100 / usage.total)
        if used >= 80:
            filesystem = used
    except OSError:  # pragma: no cover - مسارٌ غيرُ متاح
        pass

    return Alerts(
        stale_hours=stale,
        unpulled=unpulled,
        disk_percent=disk,
        filesystem_percent=filesystem,
        documents_bytes=documents_bytes(),
    )


def documents_bytes() -> int:
    """حجمُ وثائق الكباتن — يُقرأ ليُعرف **ما يملأ القرص**، لا لسقفٍ يُقارَن به."""
    total = 0
    try:
        for path in storage.root().rglob("*"):
            if path.is_file():
                total += path.stat().st_size
    except OSError:  # pragma: no cover
        return 0
    return total
