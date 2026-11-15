"""**تقسيمُ المجموعة على وظائفَ متوازية** (قرارُ المالك 2026-11-15: «Tests always run split across parallel jobs»).

يُحمَّل بـ`-p tests.shard_plugin` من `scripts/suite.sh` وحدَه، وبلا خياراته لا يفعل شيئاً — فالتشغيلُ العاديُّ كما كان.

## ما يفعله

1. **`--shard-select`**: ملفٌّ بأسماء ملفّات اختبار — يُبقي ما فيه ويُسقط الباقي (المجموعةُ السريعةُ للإيداعات الوسيطة،
   `scripts/ci_fast_set.py`). **والرأسُ لا يُمرَّر له هذا أبداً.**
2. **`--shard=i/N`**: يقسم الملفّات على N وظيفةً **بالأزمنة المقيسة** (`--shard-durations`) — الأطولُ أوّلاً إلى أخفِّ وظيفة
   (LPT). **ولا قائمةَ يدويّة**: ملفٌّ جديدٌ يقع في وظيفةٍ وحدَه، وزمنُه يُقدَّر بعدد اختباراته حتى يُقاس. والتقسيمُ حتميّ:
   الوظائفُ كلُّها تحسب الشيءَ نفسَه من المدخلات نفسِها، **وتقسيمٌ يفترق يمسكه `scripts/ci_shards_check.py`**.
3. **`--shard-report`**: يكتب ما جُمع وما اختير (`.collect.json`) وما شُغّل فعلاً بنتيجته وزمنه (`.run.json`)، **فيُثبَت أن
   مجموعَ ما شُغّل في الوظائف كلِّها = كلُّ ما جُمع** — لا اختبارَ يسقط بين وظيفتين.

## وما لا يفعله — يُقال

· **لا يقسم داخل الملفّ**: الملفُّ وحدةُ التوزيع بين الوظائف، والاختبارُ وحدتُه بين عمّال الوظيفة (`pytest -n`).
· **ولا يحكم أن الاختبار صحيح**: يثبت أنه شُغّل، والحكمُ لنتيجته.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

import pytest

#: **زمنُ اختبارٍ لم يُقَس** — متوسّطُ المجموعة المقيسُ في CI ‏43707658269 (3278ث لـ2760 اختباراً متتابعاً)
DEFAULT_TEST_SECONDS = 1.2


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("taxo-shard")
    group.addoption("--shard", default=None, help="i/N — هذه الوظيفةُ من N")
    group.addoption("--shard-durations", default=None, help="JSON بأزمنة الملفّات المقيسة")
    group.addoption("--shard-select", default=None, help="ملفٌّ بأسماء ملفّات الاختبار المختارة (المجموعةُ السريعة)")
    group.addoption("--shard-report", default=None, help="بادئةُ ملفّات التقرير")


def _file_of(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def _parse_shard(value: str | None) -> tuple[int, int]:
    if not value:
        return 1, 1
    index, _, count = value.partition("/")
    i, n = int(index), int(count)
    if not (1 <= i <= n):
        raise pytest.UsageError(f"--shard={value}: الرقمُ خارج 1..N")
    return i, n


def plan(files: dict[str, int], durations: dict[str, dict], count: int) -> dict[str, int]:
    """**الملفُّ ← رقمُ وظيفته (1..N)** — الأطولُ أوّلاً إلى أخفِّ وظيفة، والتعادلُ بالاسم فالنتيجةُ حتميّة."""
    measured = {f: d for f, d in durations.items() if isinstance(d, dict) and d.get("tests")}
    per_test = (
        sum(d["seconds"] for d in measured.values()) / sum(d["tests"] for d in measured.values())
        if measured
        else DEFAULT_TEST_SECONDS
    )

    def weight(name: str) -> float:
        known = measured.get(name)
        if known:
            # **زمنُ الملفِّ مقيساً، مُعايَراً بعدد اختباراته اليوم** — ملفٌّ زادت اختباراتُه يثقل بقدر ما زاد
            return known["seconds"] * files[name] / known["tests"]
        return per_test * files[name]

    loads = [0.0] * count
    out: dict[str, int] = {}
    for name in sorted(files, key=lambda f: (-weight(f), f)):
        target = min(range(count), key=lambda k: (loads[k], k))
        loads[target] += weight(name)
        out[name] = target + 1
    return out


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    index, count = _parse_shard(config.getoption("--shard"))
    select_path = config.getoption("--shard-select")
    report = config.getoption("--shard-report")
    if count == 1 and not select_path and not report:
        return

    collected = [item.nodeid for item in items]
    keep = list(items)
    if select_path:
        wanted = {line.strip() for line in Path(select_path).read_text(encoding="utf-8").splitlines() if line.strip()}
        keep = [item for item in keep if _file_of(item.nodeid) in wanted]

    universe = [item.nodeid for item in keep]
    if count > 1:
        sizes: dict[str, int] = defaultdict(int)
        for item in keep:
            sizes[_file_of(item.nodeid)] += 1
        durations_path = config.getoption("--shard-durations")
        durations = json.loads(Path(durations_path).read_text(encoding="utf-8")) if durations_path and Path(durations_path).is_file() else {}
        owner = plan(dict(sizes), durations.get("files", {}), count)
        keep = [item for item in keep if owner[_file_of(item.nodeid)] == index]

    kept_ids = {id(item) for item in keep}
    dropped = [item for item in items if id(item) not in kept_ids]
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = keep

    # **التقريرُ من عاملٍ واحد** — العمّالُ كلُّهم يجمعون الشيءَ نفسَه، فـ`gw0` (أو التشغيلُ المتتابع) يكتب
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if report and worker in (None, "gw0"):
        Path(f"{report}.collect.json").write_text(
            json.dumps(
                {
                    "shard": f"{index}/{count}",
                    "collected": len(collected),
                    "universe": universe,
                    "universe_sha": hashlib.sha256("\n".join(sorted(universe)).encode()).hexdigest(),
                    "selected": [item.nodeid for item in keep],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


class _RunLog:
    """**ما شُغّل فعلاً** — يُسجَّل حيث تصل التقاريرُ كلُّها (المُتحكِّمُ في xdist، أو التشغيلُ المتتابع نفسُه)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.outcomes: dict[str, str] = {}
        self.seconds: dict[str, float] = defaultdict(float)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.seconds[report.nodeid] += report.duration
        if report.when == "call":
            self.outcomes[report.nodeid] = "xfailed" if hasattr(report, "wasxfail") and report.skipped else report.outcome
        elif report.when == "setup" and report.outcome != "passed":
            self.outcomes[report.nodeid] = "skipped" if report.skipped else "error"
        elif report.when == "teardown" and report.outcome == "failed":
            self.outcomes[report.nodeid] = "error"

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        files: dict[str, dict] = defaultdict(lambda: {"seconds": 0.0, "tests": 0})
        for nodeid, secs in self.seconds.items():
            entry = files[_file_of(nodeid)]
            entry["seconds"] += secs
            entry["tests"] += 1
        Path(f"{self.path}.run.json").write_text(
            json.dumps({"outcomes": self.outcomes, "files": files, "exitstatus": int(exitstatus)}, ensure_ascii=False),
            encoding="utf-8",
        )


def pytest_configure(config: pytest.Config) -> None:
    report = config.getoption("--shard-report")
    # **المُتحكِّمُ وحدَه يسجّل** — العاملُ (`workerinput`) يرسل تقاريرَه إليه، وتسجيلُها هناك أيضاً يضاعفها
    if report and not hasattr(config, "workerinput"):
        config.pluginmanager.register(_RunLog(report), "taxo-shard-runlog")
