"""البوّابةُ الثانية — **CI الذي يُقرأ هو تشغيلُ الدفع نفسِه، والأحمرُ في التاريخ يمرّ إن أُصلح وحدَه** (قرارُ المالك 2026-10-11).

## ما كانت تفعله، ولمَ سقط

كانت تأخذ **أحدثَ تشغيلٍ اسمُه CI لإيداع الرأس** — أيّاً كان فرعُه. **وقِيس 2026-10-11 أنها قرأت تشغيلَ `redesign`** (دفعةٌ من إيداعٍ
واحد) لأن تشغيلَ دفع `master` لم يكن قد أُنشئ بعد بثوانٍ — **فلم ترَ مجموعةَ الإيداعات لدفعٍ يحمل خمسةَ عشرَ إيداعاً**، واحمرّ ذلك
التشغيلُ بعد الرفع بإيداعين في التاريخ. **فالرأسُ كان أخضرَ والحكمُ صادفَ الصواب، والبوّابةُ لم تقرأ ما وُضعت لتقرأه.**

## ما تفعله الآن — ثلاثةُ أحكام

1. **التشغيلُ تشغيلُ هذا الدفع**: `name == "CI"` · `head_sha` = الرأس · `head_branch` = الفرعُ المدفوع · `event == "push"`. **وغيابُه
   انتظارٌ لا مرور** — وتشغيلُ فرعٍ آخرَ على الإيداع نفسِه **لا يُقرأ أبداً**.
2. **رأسٌ أحمرُ لا يمرّ أبداً**: كلُّ وظيفةٍ ليست «المجموعةُ عند …» — المجموعةُ الكاملة، والحرّاسُ وبناءُ الثلاثة، والملفّاتُ الخمسة،
   وإيداعاتُ الدفعة — **خضراءُ أو متخطّاة**، و«المجموعةُ الكاملة» **موجودةٌ وخضراء**. وإلّا وقف.
3. **وكلُّ إيداعٍ بين الإنتاج والرأس مقيس، وأحمرُه مُصلَح** — وإلّا وقف:
   - يُطلب قياسُه **في هذا التشغيل** («المجموعةُ عند <الإيداع>»)، فإن لم يكن (سقفُ الاثني عشر، أو دفعٌ سابق) **ففي تشغيلٍ آخر**:
     تشغيلٌ رأسُه هذا الإيداع، أو وظيفةُ «المجموعةُ عند <الإيداع>» في تشغيلٍ حديث. **ولا قياسَ في أيٍّ منها ⇒ وقوف** («لم يُقَس»).
   - **وأحمرُه «مُصلَح» بتعريفٍ يُقاس لا يُدَّعى**: كلُّ اختبارٍ سقط هناك **قائمٌ عند الرأس** (ملفُّه ودالّتُه في الإيداع المرفوع)، **بلا
     علامةِ تخطٍّ أو فشلٍ متوقَّع**، **والمجموعةُ الكاملةُ عند الرأس خضراء** — فهو يُشغَّل وينجح الآن. **واختبارٌ حُذف ليس إصلاحاً** — قد
     يكون إخفاءً — فيقف. **وأحمرُ بلا اختبارٍ مسمّى** (مهلةٌ، إلغاءٌ، سقوطٌ قبل pytest) **لا يُعرف ما أُصلح فيه** فيقف.
   - **ووظيفةٌ غيرُ المجموعة حمراءُ عند إيداعٍ وسيط** (بناءٌ أو حارس) **مُصلَحةٌ إن خضرت الوظيفةُ نفسُها باسمها عند الرأس**.

## وحدُّها مكتوبٌ لا مسكوتٌ عنه

- **«ينجح الآن» تقرؤه من خضرة المجموعة الكاملة لا من سطرٍ لكلِّ اختبار**: pytest يُشغَّل بـ`-q` فلا يطبع الناجح. **فاختبارٌ يتخطّى نفسَه
  بشرطٍ في جسمه لا تراه هذه** إلا إن كان `pytest.skip(`/`pytest.xfail(` نصّاً في الدالّة.
- **والمطابقةُ بالاسم**: دالّةٌ أُعيدت كتابتُها بالاسم نفسِه تُقرأ «قائمة» — وهي تُشغَّل عند الرأس وتنجح، وهذا ما يُسأل عنه.

`deploy.sh` يناديها، **والاختبارُ في الاتجاهين** `scripts/tests/deploy-ci-gate.test.sh`.

    python3 scripts/deploy_ci_gate.py --repo O/R --sha <الرأس> --branch master --commits "<إيداعاتُ الإنتاج..الرأس عدا الرأس>"
    python3 scripts/deploy_ci_gate.py --repo O/R --sha <الرأس> --branch master --commits "…" --once    # حكمٌ واحدٌ بلا انتظار
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Protocol

WORKFLOW = "CI"
HEAD_SUITE = "المجموعةُ الكاملة"
BATCH_JOB = re.compile(r"^المجموعةُ عند ([0-9a-f]{7,40})$")
GREEN = {"success", "skipped", "neutral"}
# **سطرُ ملخّص pytest** — قبله ختمُ وقتِ GitHub، وبعده « - سببُه»
FAILED_LINE = re.compile(r"(?:^|\s)(?:FAILED|ERROR) (tests/[^\s:]+\.py(?:::[^\s]+)?)")
SKIP_ATTRS = {"skip", "skipif", "xfail"}
SKIP_CALLS = {"skip", "xfail", "importorskip"}


class Api(Protocol):
    def runs_for_sha(self, sha: str) -> list[dict]: ...
    def jobs(self, run_id: int) -> list[dict]: ...
    def job_log(self, job_id: int) -> str: ...
    def recent_runs(self) -> list[dict]: ...


@dataclass
class Verdict:
    state: str  # "pass" | "stop" | "wait"
    lines: list[str] = field(default_factory=list)
    url: str = ""


# ── التشغيل ──────────────────────────────────────────────────────────────────


def pick_run(runs: list[dict], sha: str, branch: str) -> dict | None:
    """**تشغيلُ هذا الدفع لا أيُّ تشغيلٍ للإيداع** — وأحدثُه إن أُعيد."""
    mine = [
        r
        for r in runs
        if r.get("name") == WORKFLOW
        and r.get("head_sha") == sha
        and r.get("head_branch") == branch
        and r.get("event") == "push"
    ]
    return max(mine, key=lambda r: (r.get("run_attempt", 1), r.get("id", 0)), default=None)


# ── الاختبارات ───────────────────────────────────────────────────────────────


def failed_tests(log: str) -> list[str]:
    return sorted({m.group(1) for m in FAILED_LINE.finditer(log)})


def _skips(expr: ast.AST) -> bool:
    """**علامةُ تخطٍّ أو فشلٍ متوقَّع** — `pytest.mark.skip/skipif/xfail` زخرفاً أو في `pytestmark`."""
    return any(isinstance(n, ast.Attribute) and n.attr in SKIP_ATTRS for n in ast.walk(expr))


def _skips_in_body(fn: ast.AST) -> bool:
    """**`pytest.skip(` أو `pytest.xfail(` أو `pytest.importorskip(` في جسم الدالّة.**"""
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in SKIP_CALLS
        and isinstance(n.func.value, ast.Name) and n.func.value.id == "pytest"
        for n in ast.walk(fn)
    )


def present_at_head(node: str, read_at_head: Callable[[str], str | None]) -> tuple[bool, str]:
    """**أقائمٌ هذا الاختبارُ عند الرأس بلا علامةِ تخطٍّ؟** — يعيد (نعم/لا، العلّة). **بشجرة ast لا بالنصّ**: زخرفٌ على أسطرٍ عدّة
    و`pytestmark` قائمةً يُريان كلُّهما."""
    path, _, rest = node.partition("::")
    source = read_at_head(path)
    if source is None:
        return False, f"{path} غائبٌ عند الرأس"
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False, f"{path} لا يُحلَّل عند الرأس"
    for stmt in tree.body:
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target] if isinstance(stmt, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets) and stmt.value is not None and _skips(stmt.value):
            return False, f"{path} موسومٌ كلُّه بتخطٍّ عند الرأس"
    if not rest:
        return True, ""  # سقوطُ جمعٍ للملفّ كلِّه — والملفُّ قائم والمجموعةُ خضراء
    parts = [p.split("[", 1)[0] for p in rest.split("::")]
    scope: list[ast.stmt] = tree.body
    for index, name in enumerate(parts):
        last = index == len(parts) - 1
        kinds = (ast.FunctionDef, ast.AsyncFunctionDef) if last else (ast.ClassDef,)
        found = next((s for s in scope if isinstance(s, kinds) and s.name == name), None)
        if found is None:
            return False, f"{node}: «{name}» غائبٌ عند الرأس"
        if any(_skips(d) for d in found.decorator_list) or (last and _skips_in_body(found)):
            return False, f"{node}: موسومٌ بتخطٍّ أو فشلٍ متوقَّع عند الرأس"
        scope = found.body
    return True, ""


# ── الحكم ────────────────────────────────────────────────────────────────────


def _red_suite_fixed(api: Api, job: dict, read_at_head) -> tuple[bool, str]:
    nodes = failed_tests(api.job_log(job["id"]))
    if not nodes:
        return False, f"«{job['name']}» حمراءُ بلا اختبارٍ مسمّى في سجلّها — لا يُعرف ما أُصلح"
    for node in nodes:
        ok, why = present_at_head(node, read_at_head)
        if not ok:
            return False, f"«{job['name']}»: {why}"
    return True, f"{len(nodes)} اختباراً سقط هناك، **وكلُّه قائمٌ عند الرأس والمجموعةُ الكاملةُ فيه خضراء**: " + " · ".join(nodes)


def _judge_batch_job(api: Api, job: dict, read_at_head) -> tuple[str, str]:
    """حكمُ «المجموعةُ عند X»: ("ok"|"fixed"|"stop", السطر)."""
    conclusion = job.get("conclusion")
    if conclusion == "success":
        return "ok", ""
    if conclusion != "failure":
        return "stop", f"«{job['name']}» انتهت {conclusion or job.get('status')} — **لم تُقَس**"
    fixed, line = _red_suite_fixed(api, job, read_at_head)
    return ("fixed" if fixed else "stop"), line


def _judge_elsewhere(api: Api, commit: str, head_jobs: dict[str, str], read_at_head, recent_cache: dict) -> tuple[str, str]:
    """إيداعٌ لم يقسه هذا التشغيل — **يُطلب قياسُه في تشغيلٍ آخر، ولا يُفترض**."""
    own = [r for r in api.runs_for_sha(commit) if r.get("name") == WORKFLOW and r.get("status") == "completed"]
    if own:
        run = max(own, key=lambda r: r.get("id", 0))
        if run.get("conclusion") == "success":
            return "ok", f"{commit[:8]}: قِيس رأساً في التشغيل {run.get('id')} — أخضر"
        notes = []
        for job in api.jobs(run["id"]):
            if BATCH_JOB.match(job.get("name", "")) or job.get("conclusion") in GREEN:
                continue  # وظيفةٌ عن إيداعٍ آخر، أو خضراء
            if job.get("name") == HEAD_SUITE:
                if job.get("conclusion") != "failure":
                    return "stop", f"{commit[:8]}: «{HEAD_SUITE}» في التشغيل {run.get('id')} انتهت {job.get('conclusion')} — لم تُقَس"
                fixed, line = _red_suite_fixed(api, job, read_at_head)
                if not fixed:
                    return "stop", f"{commit[:8]} (التشغيل {run.get('id')}): {line}"
                notes.append(line)
            elif head_jobs.get(job.get("name")) == "success":
                notes.append(f"«{job.get('name')}» حمراءُ هناك **وخضراءُ باسمها عند الرأس**")
            else:
                return "stop", f"{commit[:8]}: «{job.get('name')}» حمراءُ في التشغيل {run.get('id')} ولا نظيرَ أخضرَ لها عند الرأس"
        return "fixed", f"{commit[:8]} (التشغيل {run.get('id')}): " + " · ".join(notes)

    if "runs" not in recent_cache:
        recent_cache["runs"] = [r for r in api.recent_runs() if r.get("name") == WORKFLOW]
    wanted = f"المجموعةُ عند {commit}"
    for run in recent_cache["runs"]:
        jobs = recent_cache.setdefault(run["id"], None) or api.jobs(run["id"])
        recent_cache[run["id"]] = jobs
        for job in jobs:
            if job.get("name") == wanted and job.get("status") == "completed":
                state, line = _judge_batch_job(api, job, read_at_head)
                return state, f"{commit[:8]} (التشغيل {run.get('id')}): {line or 'أخضر'}"
    return "stop", f"{commit[:8]} **لم يُقَس في أيِّ تشغيل** — لا رأساً ولا في مجموعة إيداعات"


def judge(api: Api, *, sha: str, branch: str, commits: list[str] | None, read_at_head) -> Verdict:
    run = pick_run(api.runs_for_sha(sha), sha, branch)
    if run is None:
        return Verdict("wait", [f"لا تشغيلَ لدفع «{branch}» عند {sha[:8]} بعد — **وتشغيلُ فرعٍ آخرَ على الإيداع نفسِه لا يُقرأ**"])
    url = run.get("html_url", "")
    if run.get("status") != "completed":
        return Verdict("wait", [f"التشغيل {run.get('id')} {run.get('status')}"], url)

    jobs = api.jobs(run["id"])
    head_jobs = {j["name"]: j.get("conclusion") for j in jobs if not BATCH_JOB.match(j.get("name", ""))}
    if head_jobs.get(HEAD_SUITE) != "success":
        return Verdict("stop", [f"**الرأسُ أحمر**: «{HEAD_SUITE}» {head_jobs.get(HEAD_SUITE) or 'غائبة'}"], url)
    red_head = sorted(n for n, c in head_jobs.items() if c not in GREEN)
    if red_head:
        return Verdict("stop", ["**الرأسُ أحمر**: " + " · ".join(f"«{n}» {head_jobs[n]}" for n in red_head)], url)
    if run.get("conclusion") == "success" and commits is not None and not commits:
        return Verdict("pass", [], url)
    if commits is None:
        return Verdict("stop", ["**إيداعُ الإنتاج مجهول** — فلا يُعرف ما يُرفع، ولا يُحكم على تاريخه"], url)

    batch = {}
    for job in jobs:
        m = BATCH_JOB.match(job.get("name", ""))
        if m:
            batch[m.group(1)] = job
    lines: list[str] = []
    recent_cache: dict = {}
    for commit in commits:
        if commit == sha:
            continue
        job = batch.get(commit) or next((j for k, j in batch.items() if commit.startswith(k) or k.startswith(commit)), None)
        if job is not None:
            state, line = _judge_batch_job(api, job, read_at_head)
            line = f"{commit[:8]}: {line}" if line else ""
        else:
            state, line = _judge_elsewhere(api, commit, head_jobs, read_at_head, recent_cache)
        if state == "stop":
            return Verdict("stop", [line], url)
        if state == "fixed" or (line and job is None):
            lines.append(("أحمرُ مُصلَح — " if state == "fixed" else "") + line)
    return Verdict("pass", lines, url)


# ── GitHub ───────────────────────────────────────────────────────────────────


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - نتبع التحويلَ بأيدينا
        return None


class GitHub:
    """**بالرمز المحصور في هذا المستودع** (المواصفة §27.9) — ولا يُطبع، **ولا يُرسل إلى مضيف التحويل** (سجلُّ الوظيفة رابطٌ موقَّع)."""

    def __init__(self, repo: str, token: str) -> None:
        self.base = f"https://api.github.com/repos/{repo}"
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "taxo-deploy"}
        self.opener = urllib.request.build_opener(_NoRedirect)

    def _get(self, path: str) -> bytes:
        request = urllib.request.Request(self.base + path, headers=self.headers)
        try:
            with self.opener.open(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            location = error.headers.get("Location") if error.code in (301, 302, 303, 307, 308) else None
            if not location:
                raise
            with urllib.request.urlopen(urllib.request.Request(location, headers={"User-Agent": "taxo-deploy"}), timeout=120) as response:
                return response.read()

    def runs_for_sha(self, sha: str) -> list[dict]:
        return json.loads(self._get(f"/actions/runs?head_sha={sha}&per_page=30")).get("workflow_runs", [])

    def jobs(self, run_id: int) -> list[dict]:
        return json.loads(self._get(f"/actions/runs/{run_id}/jobs?per_page=100&filter=latest")).get("jobs", [])

    def job_log(self, job_id: int) -> str:
        return self._get(f"/actions/jobs/{job_id}/logs").decode("utf-8", "replace")

    def recent_runs(self) -> list[dict]:
        return json.loads(self._get("/actions/runs?per_page=40&status=completed")).get("workflow_runs", [])


def _git_reader(prefix: str) -> Callable[[str], str | None]:
    def read(path: str) -> str | None:
        try:
            done = subprocess.run(["git", "show", f"HEAD:{prefix}{path}"], capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None

    return read


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--commits", default=None, help="إيداعاتُ الإنتاج..الرأس مفصولةً بمسافات — وغيابُ الوسيط «مجهول»")
    parser.add_argument("--wait-minutes", type=float, default=180)
    parser.add_argument("--poll-seconds", type=float, default=30)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    # **بايثون ويندوز يكتب إلى الأنبوب بترميز المحلّة** — والسطورُ عربيّة
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    token = os.environ.get("GITHUB_TAXO_TOKEN", "")
    if not token:
        print("  ✗ لا رمزَ لقراءة CI — البوّابةُ لا تُقطع", flush=True)
        return 1
    api = GitHub(args.repo, token)
    commits = None if args.commits is None else args.commits.split()
    read = _git_reader("backend/")
    deadline = time.monotonic() + args.wait_minutes * 60
    last_note = ""
    while True:
        try:
            verdict = judge(api, sha=args.sha, branch=args.branch, commits=commits, read_at_head=read)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            verdict = Verdict("wait", [f"تعذّرت القراءةُ الآن ({type(error).__name__}) — يُعاد"])
        if verdict.state != "wait" or args.once or time.monotonic() >= deadline:
            break
        note = " · ".join(verdict.lines)
        if note != last_note:
            print(f"  CI      : {note}", flush=True)
            last_note = note
        time.sleep(args.poll_seconds)

    for line in verdict.lines:
        print(f"  CI      : {line}", flush=True)
    if verdict.state == "pass":
        print(f"CI_OK {verdict.url}", flush=True)
        return 0
    if verdict.state == "wait":
        print(f"CI_TIMEOUT {verdict.url}", flush=True)
        return 2
    print(f"CI_STOP {verdict.url}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
