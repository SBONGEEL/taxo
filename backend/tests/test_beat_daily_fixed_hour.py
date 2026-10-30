"""المهامُّ اليوميّةُ بساعةٍ ثابتةٍ لا بفترة ٢٤ ساعة (قِيس ٢٠٢٦-١٠-٢٩).

فترةُ `schedule` الرقميّةُ في beat تُعدّ من **إقلاعه**، وكلُّ رفعٍ يعيد الإقلاع — فمهمّةٌ «يوميّة» على خادمٍ يُرفع كلَّ يومٍ
لا تجري أبداً. وقع ذلك للمطابقة اليوميّة (`gateway_reconciliations` فارغٌ منذ بُنيت) وكانت أخواتُها الأربعُ على الشكل نفسِه.
فكلُّ فترةٍ رقميّةٍ تبلغ ساعاتٍ تُرفض هنا: ما كان يوميّاً أو أبطأ يُكتب `crontab`.
"""

from celery.schedules import crontab

from app.tasks.celery_app import celery_app

# أطولُ فترةٍ رقميّةٍ مقبولة: ساعةٌ واحدة — تقع في أوّل ساعةٍ بعد أيِّ رفع، فلا يضيّعها الرفعُ اليوميّ
MAX_NUMERIC_SECONDS = 3600.0


def test_no_beat_task_counts_a_long_interval_from_boot():
    long_ones = {
        name: entry["schedule"]
        for name, entry in celery_app.conf.beat_schedule.items()
        if not isinstance(entry["schedule"], crontab) and float(entry["schedule"]) > MAX_NUMERIC_SECONDS
    }
    assert long_ones == {}, f"فتراتٌ تُعدّ من الإقلاع ويضيّعها الرفع — اكتبها crontab: {long_ones}"


def test_the_four_daily_siblings_run_at_fixed_hours():
    schedule = celery_app.conf.beat_schedule
    expected = {
        "sweep-error-reports": (1, 5),
        "trim-admin-alerts": (1, 25),
        "roll-up-activity": (1, 45),
        "trim-notifications": (2, 5),
    }
    for name, (hour, minute) in expected.items():
        entry = schedule[name]["schedule"]
        assert isinstance(entry, crontab), name
        assert entry.hour == {hour} and entry.minute == {minute}, name
