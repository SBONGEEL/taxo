"""علامةُ حياة العامل لفحص الحاوية (SPEC §٧٦/١) — بديلُ `celery inspect ping` الذي كان يستورد التطبيقَ كلَّ ٣٠ ثانية."""

from __future__ import annotations

import importlib
import os
import time

from app.tasks.celery_app import LivenessStep, celery_app, touch_liveness

# الحزمةُ تصدّر كائنَ Celery باسم `celery_app` — فالوحدةُ تُؤخذ من سجلّ الوحدات لا من الحزمة
module = importlib.import_module("app.tasks.celery_app")


class _Timer:
    def __init__(self) -> None:
        self.calls: list[tuple[float, object, int]] = []
        self.cancelled = 0

    def call_repeatedly(self, secs, fun, args=(), kwargs=None, priority=0):  # noqa: ANN001
        self.calls.append((secs, fun, priority))
        timer = self

        class _Ref:
            def cancel(self) -> None:
                timer.cancelled += 1

        return _Ref()


class _Consumer:
    def __init__(self) -> None:
        self.timer = _Timer()


def test_the_step_lives_on_the_consumer_blueprint() -> None:
    # مؤقّتُ المستهلك هو الحلقةُ التي تستقبل المهام — لا مؤقّتُ العامل
    assert LivenessStep in celery_app.steps["consumer"]


def test_touch_refreshes_the_file(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "alive"
    touch_liveness(path)
    first = path.stat().st_mtime
    os.utime(path, (first - 120, first - 120))
    touch_liveness(path)
    assert path.stat().st_mtime > first - 60


def test_start_touches_and_schedules_and_stop_cancels(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    path = tmp_path / "alive"
    monkeypatch.setattr(module, "LIVENESS_FILE", path)
    monkeypatch.setattr(module, "touch_liveness", lambda p=path: p.touch())
    consumer = _Consumer()
    step = LivenessStep(consumer)
    step.start(consumer)
    assert path.exists() and time.time() - path.stat().st_mtime < 5
    assert [c[0] for c in consumer.timer.calls] == [module.LIVENESS_EVERY_SECONDS]
    step.stop(consumer)
    step.stop(consumer)  # إيقافٌ ثانٍ لا يلغي مرّتين
    assert consumer.timer.cancelled == 1


def test_the_interval_is_well_inside_the_stale_window() -> None:
    # الفحصُ في compose يُبيّت الملفَّ بعد ٩٠ ثانية — ثلاثُ لمساتٍ ضائعةٍ على الأقلّ قبل أن يُقرأ ميتاً
    assert module.LIVENESS_EVERY_SECONDS * 3 < 90
