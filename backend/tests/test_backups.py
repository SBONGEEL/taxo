"""النسخُ الاحتياطي (`design/BACKUP-AND-RESTORE.md`).

**والاختبارُ الذي يستحقّ أن يُقرأ أولاً هو الاحتفاظ**: هناك يُفقد المال. قرارُ
المالك ٢ — **لا يُحذف ما لم يُسحب مهما بلغ العدد** — والخطأُ فيه غيرُ متماثل:
قرصٌ يمتلئ عطبٌ يُصلَح بأمرٍ واحد، ونسخةٌ حُذفت ولم يملكها أحدٌ **لا تعود**.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.models.backup import BackupRun, BackupStatus
from app.services import backups
from types import SimpleNamespace


@pytest.fixture
def backup_root(tmp_path, monkeypatch):
    root = tmp_path / "backups"
    root.mkdir()
    monkeypatch.setattr(backups, "BACKUP_ROOT", root)

    # **قرصُ المضيف ليس مُدخلاً لهذه الاختبارات — فيُثبَّت** (2026-08-24).
    #
    # `alerts()` يقيس امتلاءَ **نظام الملفات كلِّه** (`shutil.disk_usage`)
    # ويُنبّه عند ٨٠٪، **و`any` يجمعه مع تنبيهات النسخ**. فاختبارٌ يؤكّد
    # `any is False` كان يقرأ قرصَ الجهاز الذي يُشغّله — **ويمرّ أو يسقط بحسبه**.
    #
    # **ووقع مقيساً**: التشغيلُ ٤٥ في CI سقط بـ
    # `Alerts(stale_hours=None, unpulled=None, disk_percent=None,
    # filesystem_percent=82)` — **قرصُ العامل ٨٢٪**، ولا علاقةَ له بالنسخ.
    # وهو الشكلُ نفسُه الذي أسقط رسمَ الوقفة و`taxo:taxo`: **قيمةٌ من العالم
    # الحقيقيِّ يقرؤها اختبارٌ لا يملكها، فيوافق جهازاً ويخالف آخر.**
    #
    # **ولا يُضعَّف التأكيد**: `any is False` يبقى كما هو — **الذي تغيّر أن
    # المُدخلَ صار مملوكاً**. وتثبيتُه هنا يجعل ما تقيسه هذه الملفّاتُ
    # **تنبيهاتِ النسخ وحدَها**، وهو ما وُجدت له.
    #
    # **وتنبيهُ نظام الملفات لا يقيسه اختبارٌ واحد** — لا قبل هذا التثبيت ولا
    # بعده. **يُقال ولا يُسكت عنه**: حقلٌ يوقظ إنساناً ولا يحرسه شيء.
    monkeypatch.setattr(
        backups.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=10_000, free=90_000),
    )
    return root


def _make(root, name: str, *, pulled: bool, size: int = 1024) -> None:
    item = root / name
    item.mkdir()
    (item / "db.dump").write_bytes(b"x" * size)
    (item / "manifest.json").write_text(json.dumps({"files": {}}), encoding="utf-8")
    if pulled:
        (item / backups.PULLED_MARKER).write_text("{}", encoding="utf-8")


# ------------------------------------------------------------- الاحتفاظ


async def test_an_unpulled_backup_is_never_deleted_however_many_pile_up(
    session_factory, backup_root
) -> None:
    """**قرارُ المالك ٢ بحرفه**: نسخةٌ لم يملكها أحدٌ لا تُحذف بحال.

    ويُتحقَّق منه بحذف شرط `is_pulled` من `prune`: عندها تُمحى نسخٌ لا نسخةَ لها
    عند أحد، وهو أسوأُ ما يفعله نظامُ نسخٍ احتياطي.
    """
    for index in range(9):
        _make(backup_root, f"taxo-2026081{index}-0300", pulled=False)

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.keep_count = 2
        await session.commit()
        removed = backups.prune(setting)

    assert removed == []
    assert len(backups.existing()) == 9
    assert backups.unpulled_count() == 9


async def test_pulled_backups_beyond_the_keep_count_are_deleted_oldest_first(
    session_factory, backup_root
) -> None:
    """**والسقفُ يقع على المسحوبة وحدَها** — ونسخةٌ عند المالك ليست مفقودة."""
    for index in range(5):
        _make(backup_root, f"taxo-2026081{index}-0300", pulled=True)

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.keep_count = 2
        await session.commit()
        removed = backups.prune(setting)

    # الأقدمُ يُحذف والأحدثُ يبقى
    assert sorted(removed) == [
        "taxo-20260810-0300",
        "taxo-20260811-0300",
        "taxo-20260812-0300",
    ]
    assert [item.name for item in backups.existing()] == [
        "taxo-20260814-0300",
        "taxo-20260813-0300",
    ]


async def test_unpulled_backups_do_not_count_against_the_keep_limit(
    session_factory, backup_root
) -> None:
    """غيرُ المسحوبة **لا تُعدّ في السقف**: لولا ذلك لحذفت نسخةٌ عالقةٌ غيرَها."""
    for index in range(4):
        _make(backup_root, f"taxo-2026081{index}-0300", pulled=False)
    for index in range(4, 8):
        _make(backup_root, f"taxo-2026081{index}-0300", pulled=True)

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.keep_count = 3
        await session.commit()
        removed = backups.prune(setting)

    assert removed == ["taxo-20260814-0300"]
    assert len(backups.existing()) == 7


# ------------------------------------------------------------- التنبيهات


async def test_a_backup_that_never_ran_alerts(session_factory, backup_root) -> None:
    """**أخطرُ عطبٍ في هذا النظام كلِّه نسخةٌ لم تُؤخذ ولم يعلم أحد.**"""
    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        await session.commit()
        alerts = await backups.alerts(session)

    assert alerts.stale_hours == setting.alert_after_hours
    assert alerts.any is True


async def test_a_recent_success_does_not_alert(session_factory, backup_root) -> None:
    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        session.add(
            BackupRun(
                name="taxo-20260816-0300",
                status=BackupStatus.SUCCEEDED,
                finished_at=datetime.now(UTC) - timedelta(hours=2),
            )
        )
        await session.commit()
        alerts = await backups.alerts(session)

    assert alerts.stale_hours is None
    assert alerts.any is False


async def test_a_failed_run_does_not_count_as_a_backup(
    session_factory, backup_root
) -> None:
    """صفٌّ `failed` **ليس نسخة** — ولو عُدّ لصمت التنبيهُ عن قرصٍ ممتلئ."""
    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        session.add(
            BackupRun(
                name="taxo-20260816-0300",
                status=BackupStatus.FAILED,
                finished_at=datetime.now(UTC),
                error="no space left on device",
            )
        )
        await session.commit()
        alerts = await backups.alerts(session)

    assert alerts.stale_hours is not None


async def test_piled_up_unpulled_backups_alert_instead_of_being_deleted(
    session_factory, backup_root
) -> None:
    """**تنبيهٌ لا حذف** — وهو الوجهُ الآخرُ لقرار المالك ٢."""
    for index in range(4):
        _make(backup_root, f"taxo-2026081{index}-0300", pulled=False)

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        setting.alert_unpulled_count = 3
        session.add(
            BackupRun(
                name="x",
                status=BackupStatus.SUCCEEDED,
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()
        alerts = await backups.alerts(session)

    assert alerts.unpulled == 4
    assert len(backups.existing()) == 4


async def test_the_disk_ceiling_warns_at_eighty_percent_and_deletes_nothing(
    session_factory, backup_root
) -> None:
    """**قرارُ المالك ٣**: سقفٌ يُنبَّه عنده ولا يحذف بموجبه."""
    _make(backup_root, "taxo-20260816-0300", pulled=True, size=900)

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        setting.max_bytes = 1000
        session.add(
            BackupRun(
                name="x",
                status=BackupStatus.SUCCEEDED,
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()
        alerts = await backups.alerts(session)
        removed = backups.prune(setting)

    assert alerts.disk_percent is not None and alerts.disk_percent >= 80
    assert removed == []


async def test_disabled_backups_alert_about_nothing(
    session_factory, backup_root
) -> None:
    """مطفأً لا تنبيه: إنذارٌ يومئٌ على قرارٍ اتُّخذ يُهمَل خلال أسبوع — **ثم
    يُهمَل معه الإنذارُ الذي يصدق**."""
    async with session_factory() as session:
        await backups.get_settings(session)
        await session.commit()
        alerts = await backups.alerts(session)

    assert alerts.any is False


# ------------------------------------------------------------- الموعد


async def test_a_disabled_schedule_is_never_due(session_factory, backup_root) -> None:
    async with session_factory() as session:
        await backups.get_settings(session)
        await session.commit()
        assert await backups.is_due(session) is False


async def test_the_hour_is_read_in_the_countrys_clock_not_utc(
    session_factory, backup_root, monkeypatch
) -> None:
    """**من يكتب «٣ صباحاً» يقصد الثالثةَ عنده** (قاعدةُ «يومِ الدولة»).

    والخادمُ بـUTC يأخذها السادسةَ في عمّان لو قيست بساعته — وهي قاعدةٌ يشترك
    فيها هذا الملفُّ مع `services/stats.py` ومهامِّ الشهر.
    """
    from zoneinfo import ZoneInfo

    amman = ZoneInfo("Asia/Amman")

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        setting.hour_local = 3
        await session.commit()

        # الثانيةُ صباحاً بتوقيت عمّان — لم يحن الموعد
        moment = datetime.now(amman).replace(hour=2, minute=0)
        monkeypatch.setattr(backups, "_now", lambda: moment.astimezone(UTC))
        assert await backups.is_due(session) is False

        # الرابعةُ صباحاً — حان ولم تُؤخذ
        moment = datetime.now(amman).replace(hour=4, minute=0)
        monkeypatch.setattr(backups, "_now", lambda: moment.astimezone(UTC))
        assert await backups.is_due(session) is True


async def test_a_backup_taken_inside_todays_window_is_not_due_again(
    session_factory, backup_root, monkeypatch
) -> None:
    """**نافذةُ اليوم لا «مضت ٢٤ ساعة»**: نسخةٌ أمس الثالثةَ وأخرى اليومَ
    الثانيةَ والنصف تجعل الفرقَ ٢٣٫٥ ساعة، فيُتخطّى موعدُ اليوم بلا سبب."""
    from zoneinfo import ZoneInfo

    amman = ZoneInfo("Asia/Amman")
    moment = datetime.now(amman).replace(hour=5, minute=0)

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        setting.hour_local = 3
        session.add(
            BackupRun(
                name="taxo-today",
                status=BackupStatus.SUCCEEDED,
                # أُخذت اليومَ الثالثةَ والنصف — داخل نافذة اليوم
                finished_at=moment.replace(hour=3, minute=30).astimezone(UTC),
            )
        )
        await session.commit()

        monkeypatch.setattr(backups, "_now", lambda: moment.astimezone(UTC))
        assert await backups.is_due(session) is False


# ------------------------------------------------------------- الفشل


async def test_a_failed_dump_writes_a_row_with_its_error_and_never_raises(
    session_factory, backup_root, monkeypatch
) -> None:
    """**الفشلُ الصامتُ ممنوع** — ونصُّ الخطأ يُخزَّن.

    و«فشلت» بلا سببٍ تجعل المالكَ يعيد المحاولةَ في قرصٍ ممتلئٍ عشرَ مرات.
    """

    async def _boom() -> str:
        raise RuntimeError("no space left on device")

    monkeypatch.setattr(backups, "_run_script", _boom)

    async with session_factory() as session:
        run = await backups.take(session, requested_by="admin")

    assert run.status == BackupStatus.FAILED
    assert "no space left" in run.error
    assert run.finished_at is not None
    # **ولا يُرفع الاستثناء**: مهمّةٌ دوريةٌ تنهار تتوقف عن التنبيه أيضاً


async def test_a_backup_taken_over_ssh_counts_even_with_no_run_row(
    session_factory, backup_root, monkeypatch
) -> None:
    """**القرصُ سجلُّ ما وُجد، والجدولُ سجلُّ محاولاتٍ مرّت من التطبيق.**

    والمالكُ يشغّل `backup.sh` عبر SSH (وهو ما يفعله `pull-backup.ps1 -Now`)،
    فتلك نسخةٌ صحيحةٌ بلا صفّ. ولو قُرئ الجدولُ وحدَه لقالت اللوحةُ «لا توجد
    نسخة» وفي جدولها نسخة — **وأخطرُ منه** أن الموعدَ يُعدّ فائتاً فتُؤخذ ثانيةٌ
    بعد دقائقَ من الأولى.
    """
    from zoneinfo import ZoneInfo

    amman = ZoneInfo("Asia/Amman")
    moment = datetime.now(amman).replace(hour=5, minute=0)

    item = backup_root / "taxo-20260816-033000"
    item.mkdir()
    (item / "db.dump").write_bytes(b"x")
    (item / "manifest.json").write_text(
        json.dumps(
            {"taken_at": moment.replace(hour=3, minute=30).astimezone(UTC).isoformat()}
        ),
        encoding="utf-8",
    )

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        setting.hour_local = 3
        await session.commit()

        monkeypatch.setattr(backups, "_now", lambda: moment.astimezone(UTC))
        assert await backups.last_success(session) is not None
        # **ولا تُؤخذ ثانيةٌ**: النسخةُ اليدويةُ تسدّ موعدَ اليوم
        assert await backups.is_due(session) is False


async def test_a_weekly_schedule_takes_its_backup_on_the_chosen_day(
    session_factory, backup_root, monkeypatch
) -> None:
    """**«أسبوعياً» بيومٍ مختارٍ تُؤخذ فيه، ولا تُؤخذ في غيره.**

    وهذا ما كان مكسوراً من جهة الشاشة: `weekday` بلا خانةٍ في اللوحة، فمن
    اختار «أسبوعياً» تركه `None` — و`is_due` تقرأ `weekday is None` فتعيد
    `False` **في كلِّ يوم**. جدولةٌ تبدو مضبوطةً ولا تُؤخذ نسخةٌ أبداً، ولا شيءَ
    يفشل حتى يوم الاستعادة.
    """
    from zoneinfo import ZoneInfo

    amman = ZoneInfo("Asia/Amman")
    # الاثنينُ صفرٌ في `date.weekday()` — والأربعاءُ اثنان
    wednesday = 2

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        setting.frequency = "weekly"
        setting.weekday = wednesday
        setting.hour_local = 3
        await session.commit()

        # نبني لحظةً بعد الساعة في يومٍ معلومٍ بدل انتظار الأسبوع
        base = datetime(2026, 8, 19, 4, 0, tzinfo=amman)  # أربعاء
        assert base.weekday() == wednesday

        monkeypatch.setattr(backups, "_now", lambda: base.astimezone(UTC))
        assert await backups.is_due(session) is True, "لم تُؤخذ في يومها"

        # والخميسُ ليس يومَها
        thursday = base + timedelta(days=1)
        monkeypatch.setattr(backups, "_now", lambda: thursday.astimezone(UTC))
        assert await backups.is_due(session) is False, "أُخذت في غير يومها"


async def test_a_weekly_schedule_with_no_day_never_runs_and_that_is_the_defect(
    session_factory, backup_root, monkeypatch
) -> None:
    """**والحالُ التي كانت تشحن**: «أسبوعياً» بلا يوم ⇒ لا نسخةَ في أيِّ يوم.

    يُثبَّت هنا صراحةً لأنه ليس سلوكاً مرغوباً بل **نتيجةُ حقلٍ بلا خانة** —
    فإن عاد أحدٌ فأزال الخانةَ من اللوحة، هذا الاختبارُ هو ما يقول ماذا يقع.
    """
    from zoneinfo import ZoneInfo

    amman = ZoneInfo("Asia/Amman")

    async with session_factory() as session:
        setting = await backups.get_settings(session)
        setting.enabled = True
        setting.frequency = "weekly"
        setting.weekday = None
        setting.hour_local = 3
        await session.commit()

        for offset in range(7):
            moment = datetime(2026, 8, 17, 4, 0, tzinfo=amman) + timedelta(days=offset)
            monkeypatch.setattr(backups, "_now", lambda m=moment: m.astimezone(UTC))
            assert await backups.is_due(session) is False
