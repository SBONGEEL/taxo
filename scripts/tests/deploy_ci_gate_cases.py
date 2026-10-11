"""**البوّابةُ الثانية في الاتجاهين** (قاعدةُ كلِّ حارس، قرارُ المالك 2026-08-20) — `scripts/deploy_ci_gate.py` على GitHub مزيَّف.

**تقف حين يجب**: تشغيلُ فرعٍ آخرَ وحدَه · تشغيلٌ جارٍ · رأسٌ أحمر (المجموعة، أو حارسٌ وبناء، أو غيابُ المجموعة) · أحمرُ في التاريخ
**لم يُصلَح** (اختبارُه حُذف، أو تُخطّي بزخرفٍ على أسطرٍ عدّة، أو بـ`pytestmark`، أو بـ`pytest.skip(` في جسمه) · أحمرُ بلا اختبارٍ مسمّى ·
وظيفةٌ أُلغيت · إيداعٌ لم يُقَس في أيِّ تشغيل · إنتاجٌ مجهول.
**وتمرّ حين يجب**: كلُّه أخضر · أحمرُ في التاريخ **مُصلَحٌ** عند الرأس (معلَّماتٌ وصنف) · سقوطُ جمعٍ لملفٍّ قائم · إيداعٌ خارج السقف قِيس
رأساً في تشغيله أو في مجموعة إيداعاتِ تشغيلٍ آخر · وظيفةُ بناءٍ حمراءُ في الوسط خضراءُ باسمها عند الرأس.

**ولا شبكة**: كلُّ قراءةٍ من قواميسَ هنا.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("deploy_ci_gate", Path(__file__).resolve().parents[1] / "deploy_ci_gate.py")
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate  # `dataclass` يقرأ وحدتَه من `sys.modules`
spec.loader.exec_module(gate)

HEAD = "f" * 40
A, B, C = "a" * 40, "b" * 40, "c" * 40
STAMP = "2026-10-11T19:09:50.2521151Z "

TESTS_AT_HEAD = {
    "tests/test_two_doors.py": "import pytest\n\nasync def test_every_payload_is_classified(client):\n    assert True\n",
    "tests/test_param.py": "import pytest\n\n@pytest.mark.parametrize('n', [1, 2])\ndef test_n(n):\n    assert n\n\nclass TestBox:\n    def test_inside(self):\n        assert True\n",
    "tests/test_skipped.py": (
        "import pytest\n\n@pytest.mark.parametrize(\n    'n',\n    [1, 2],\n)\n@pytest.mark.skipif(\n    True,\n    reason='later',\n)\n"
        "def test_hidden(n):\n    assert n\n\ndef test_skips_itself():\n    pytest.skip('not now')\n"
    ),
    "tests/test_module_skip.py": "import pytest\n\npytestmark = [\n    pytest.mark.usefixtures('x'),\n    pytest.mark.skipif(True, reason='off'),\n]\n\ndef test_a():\n    assert True\n",
    "tests/test_collect.py": "def test_ok():\n    assert True\n",
}


def read_at_head(path: str) -> str | None:
    return TESTS_AT_HEAD.get(path)


def log(*nodes: str) -> str:
    body = "".join(f"{STAMP}FAILED {n} - AssertionError: سقط\n" for n in nodes)
    return f"{STAMP}=== short test summary info ===\n{body}{body}{STAMP}1 failed, 2113 passed\n"


def run(rid: int, sha: str, branch: str, status: str = "completed", conclusion: str | None = "success", event: str = "push") -> dict:
    return {"id": rid, "name": "CI", "head_sha": sha, "head_branch": branch, "event": event, "status": status,
            "conclusion": conclusion, "html_url": f"https://ci/{rid}"}


def job(jid: int, name: str, conclusion: str = "success", status: str = "completed") -> dict:
    return {"id": jid, "name": name, "status": status, "conclusion": conclusion}


def head_jobs(suite: str = "success", build: str = "success") -> list[dict]:
    return [job(1, "المجموعةُ الكاملة", suite), job(2, "الحرّاسُ وبناءُ الثلاثة (customer-app, https://api.tajora.ly)", build),
            job(3, "الملفّاتُ الخمسة"), job(4, "إيداعاتُ الدفعة"), job(5, "الحزمُ وإصدارُها", "skipped")]


class Fake:
    def __init__(self, runs: dict[str, list[dict]], jobs: dict[int, list[dict]], logs: dict[int, str] | None = None,
                 recent: list[dict] | None = None) -> None:
        self._runs, self._jobs, self._logs, self._recent = runs, jobs, logs or {}, recent or []

    def runs_for_sha(self, sha):
        return self._runs.get(sha, [])

    def jobs(self, run_id):
        return self._jobs.get(run_id, [])

    def job_log(self, job_id):
        return self._logs.get(job_id, "")

    def recent_runs(self):
        return self._recent


def verdict(api: Fake, commits: list[str] | None = (A, B)) -> gate.Verdict:
    return gate.judge(api, sha=HEAD, branch="master", commits=None if commits is None else list(commits), read_at_head=read_at_head)


def master_run(batch: list[dict], *, suite: str = "success", build: str = "success", conclusion: str = "failure") -> dict:
    return {"runs": {HEAD: [run(100, HEAD, "master", conclusion=conclusion), run(90, HEAD, "redesign")]},
            "jobs": {100: head_jobs(suite, build) + batch}}


CASES: list[tuple[str, str, gate.Verdict]] = []


def case(name: str, expect: str, got: gate.Verdict) -> None:
    CASES.append((name, expect, got))


# ── تقف حين يجب ──────────────────────────────────────────────────────────────
case("تشغيلُ redesign أخضرُ على الإيداع نفسِه ولا تشغيلَ لـmaster — **ينتظر ولا يمرّ**", "wait",
     verdict(Fake({HEAD: [run(90, HEAD, "redesign"), run(91, HEAD, "agent/dz")]}, {90: head_jobs(), 91: head_jobs()})))
case("تشغيلُ «push» لـmaster من حدثٍ آخر لا يُقرأ — ينتظر", "wait",
     verdict(Fake({HEAD: [run(92, HEAD, "master", event="workflow_dispatch")]}, {92: head_jobs()})))
case("تشغيلُ master جارٍ — ينتظر", "wait",
     verdict(Fake({HEAD: [run(100, HEAD, "master", status="in_progress", conclusion=None)]}, {})))
m = master_run([], suite="failure")
case("**الرأسُ أحمر**: المجموعةُ الكاملة", "stop", verdict(Fake(m["runs"], m["jobs"]), []))
m = master_run([], build="failure")
case("**الرأسُ أحمر**: حارسٌ وبناءُ تطبيق", "stop", verdict(Fake(m["runs"], m["jobs"]), []))
m = {"runs": {HEAD: [run(100, HEAD, "master", conclusion="failure")]}, "jobs": {100: head_jobs()[1:]}}
case("**الرأسُ أحمر**: المجموعةُ الكاملةُ غائبة", "stop", verdict(Fake(m["runs"], m["jobs"]), []))
m = master_run([job(11, f"المجموعةُ عند {A}", "failure"), job(12, f"المجموعةُ عند {B}")])
case("أحمرُ في التاريخ **اختبارُه حُذف عند الرأس** — ليس إصلاحاً", "stop",
     verdict(Fake(m["runs"], m["jobs"], {11: log("tests/test_gone.py::test_x")})))
case("أحمرُ في التاريخ **دالّتُه حُذفت** وملفُّها قائم", "stop",
     verdict(Fake(m["runs"], m["jobs"], {11: log("tests/test_two_doors.py::test_renamed_away")})))
case("أحمرُ في التاريخ **تُخطّي بزخرفٍ على أسطرٍ عدّة**", "stop",
     verdict(Fake(m["runs"], m["jobs"], {11: log("tests/test_skipped.py::test_hidden[1]")})))
case("أحمرُ في التاريخ **يتخطّى نفسَه بـpytest.skip( في جسمه**", "stop",
     verdict(Fake(m["runs"], m["jobs"], {11: log("tests/test_skipped.py::test_skips_itself")})))
case("أحمرُ في التاريخ **وملفُّه كلُّه موسومٌ بتخطٍّ في pytestmark**", "stop",
     verdict(Fake(m["runs"], m["jobs"], {11: log("tests/test_module_skip.py::test_a")})))
case("أحمرُ في التاريخ **بلا اختبارٍ مسمّى** (مهلةٌ أو سقوطٌ قبل pytest)", "stop",
     verdict(Fake(m["runs"], m["jobs"], {11: f"{STAMP}##[error]The job running on runner has exceeded the maximum execution time\n"})))
m = master_run([job(11, f"المجموعةُ عند {A}", "cancelled"), job(12, f"المجموعةُ عند {B}")])
case("مجموعةُ إيداعٍ **أُلغيت** — لم تُقَس", "stop", verdict(Fake(m["runs"], m["jobs"])))
m = master_run([job(12, f"المجموعةُ عند {B}")], conclusion="success")
case("إيداعٌ **لم يُقَس في أيِّ تشغيل** (خارج السقف ولا تشغيلَ له)", "stop", verdict(Fake(m["runs"], m["jobs"])))
case("**إيداعُ الإنتاج مجهول**", "stop", verdict(Fake(m["runs"], m["jobs"]), None))
own = {HEAD: m["runs"][HEAD], A: [run(70, A, "agent/dz", conclusion="failure")]}
case("إيداعٌ خارج السقف **قِيس رأساً فاحمرّت مجموعتُه، واختبارُه حُذف**", "stop",
     verdict(Fake(own, {**m["jobs"], 70: head_jobs(suite="failure")}, {1: log("tests/test_gone.py::test_y")})))
case("إيداعٌ خارج السقف **حارسُه أحمرُ هناك ولا نظيرَ أخضرَ له عند الرأس**", "stop",
     verdict(Fake(own, {**m["jobs"], 70: head_jobs()[:1] + [job(6, "حارسٌ لم يعد موجوداً", "failure")]})))

# ── وتمرّ حين يجب ────────────────────────────────────────────────────────────
m = master_run([job(11, f"المجموعةُ عند {A}"), job(12, f"المجموعةُ عند {B}")], conclusion="success")
case("كلُّه أخضر", "pass", verdict(Fake(m["runs"], m["jobs"])))
m = master_run([job(11, f"المجموعةُ عند {A}", "failure"), job(12, f"المجموعةُ عند {B}", "failure")])
case("أحمران في التاريخ **مُصلَحان عند الرأس** — دالّةٌ ومعلَّماتٌ وصنف", "pass",
     verdict(Fake(m["runs"], m["jobs"], {11: log("tests/test_two_doors.py::test_every_payload_is_classified"),
                                         12: log("tests/test_param.py::test_n[2]", "tests/test_param.py::TestBox::test_inside")})))
m = master_run([job(11, f"المجموعةُ عند {A}", "failure"), job(12, f"المجموعةُ عند {B}")])
case("سقوطُ جمعٍ لملفٍّ **قائمٍ عند الرأس**", "pass",
     verdict(Fake(m["runs"], m["jobs"], {11: f"{STAMP}ERROR tests/test_collect.py - ImportError: x\n"})))
m = master_run([job(12, f"المجموعةُ عند {B}")], conclusion="success")
case("إيداعٌ خارج السقف **قِيس رأساً في تشغيله فخضر**", "pass",
     verdict(Fake({**m["runs"], A: [run(70, A, "agent/dz")]}, m["jobs"])))
case("إيداعٌ خارج السقف **قِيس في مجموعة إيداعاتِ تشغيلٍ آخر، وأحمرُه مُصلَح**", "pass",
     verdict(Fake(m["runs"], {**m["jobs"], 60: [job(61, f"المجموعةُ عند {A}", "failure")]},
                  {61: log("tests/test_two_doors.py::test_every_payload_is_classified")}, recent=[run(60, C, "agent/dz", conclusion="failure")])))
case("إيداعٌ خارج السقف **بناؤه أحمرُ هناك وخضراءُ باسمه عند الرأس**", "pass",
     verdict(Fake({**m["runs"], A: [run(70, A, "agent/dz", conclusion="failure")]},
                  {**m["jobs"], 70: head_jobs(build="failure")})))

# ── وقراءةُ السجلّ نفسِها ─────────────────────────────────────────────────────
parsed = gate.failed_tests(log("tests/test_a.py::test_b[x-1]", "tests/test_c.py::K::test_d") + f"{STAMP}ERROR tests/test_e.py - boom\n")
picked = gate.pick_run([run(90, HEAD, "redesign"), run(100, HEAD, "master"), run(95, HEAD, "master", event="pull_request")], HEAD, "master")

fails = 0
for name, expect, got in CASES:
    ok = got.state == expect
    fails += not ok
    print(f"  {'✓' if ok else '✗'} {name} → {got.state}" + ("" if ok else f" (المتوقَّع {expect}) — {' · '.join(got.lines)}"))
for name, ok in [
    ("قراءةُ «FAILED/ERROR» من سجلٍّ مختوم، بلا تكرار", parsed == ["tests/test_a.py::test_b[x-1]", "tests/test_c.py::K::test_d", "tests/test_e.py"]),
    ("اختيارُ تشغيل دفع master لا أحدثَ تشغيلٍ للإيداع", picked and picked["id"] == 100),
]:
    fails += not ok
    print(f"  {'✓' if ok else '✗'} {name}")
stops = sum(1 for _, e, _ in CASES if e != "pass")
print(f"\n{len(CASES) + 2 - fails}/{len(CASES) + 2} — تقف أو تنتظر {stops} وتمرّ {len(CASES) - stops}" + (" — **سقط**" if fails else ""))
sys.exit(1 if fails else 0)
