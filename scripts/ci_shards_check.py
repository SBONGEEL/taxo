#!/usr/bin/env python3
"""**لا اختبارَ يسقط بين وظيفتين** — حارسُ التقسيم (قرارُ المالك 2026-11-15).

    python3 scripts/ci_shards_check.py <مجلّدُ التقارير> <عددُ الوظائف> <مخرجُ الأزمنة> [الأزمنةُ السابقة]

يقرأ `shard-*.collect.json` و`shard-*.run.json` من كلِّ وظيفة ويُسقط CI إن:

1. **غاب تقريرُ وظيفة** — وظيفةٌ لم تكتب ما جمعت لا يُعرف ما شغّلت.
2. **افترق ما جمعته الوظائف** (`universe_sha`) — فالتقسيمُ حُسب على مجموعتين، وقد يسقط بينهما اختبار.
3. **تداخلت الوظائف أو نقص اتحادُها عن الكلّ** — اختبارٌ في وظيفتين أو في لا وظيفة.
4. **اختيرَ اختبارٌ ولم يُشغَّل** (لا نتيجةَ له في `.run.json`).
5. **مجموعُ ما شُغّل < مجموعُ ما جُمع** — الشرطُ الذي طلبه المالكُ نصّاً.
6. **سقط اختبار** — ويُطبع `FAILED tests/…` بصيغة pytest، فيقرؤه `scripts/deploy_ci_gate.py` من سجلِّ هذه الوظيفة.

ويكتب الأزمنةَ المدموجة لتُحفظ ويُقسَم بها التشغيلُ التالي، **ويقول إن نقص العددُ عن التشغيل السابق** — ولا يُسقط بذلك
وحدَه: حذفُ اختبارٍ قرارٌ قد يكون صحيحاً، **وقرارٌ يُرى لا قرارٌ يُمنع**.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BAD = {"failed", "error"}
TARGET_SECONDS = 600


def main(argv: list[str]) -> int:
    folder, count, out = Path(argv[1]), int(argv[2]), Path(argv[3])
    previous = Path(argv[4]) if len(argv) > 4 else None
    problems: list[str] = []
    collects, runs = {}, {}
    for k in range(1, count + 1):
        c = next(folder.rglob(f"shard-{k}.collect.json"), None)
        r = next(folder.rglob(f"shard-{k}.run.json"), None)
        if c is None or r is None:
            problems.append(f"الوظيفة {k}/{count}: لا تقرير ({'collect' if c is None else 'run'}) — لا يُعرف ما شغّلت")
            continue
        collects[k] = json.loads(c.read_text(encoding="utf-8"))
        runs[k] = json.loads(r.read_text(encoding="utf-8"))

    universe: set[str] = set()
    shas = {v["universe_sha"] for v in collects.values()}
    if len(shas) > 1:
        problems.append(f"الوظائفُ جمعت مجموعاتٍ مختلفة ({len(shas)} بصمات) — التقسيمُ لا يُوثق")
    for v in collects.values():
        universe.update(v["universe"])

    owner: dict[str, int] = {}
    for k, v in sorted(collects.items()):
        for nodeid in v["selected"]:
            if nodeid in owner:
                problems.append(f"{nodeid} في الوظيفتين {owner[nodeid]} و{k}")
            owner[nodeid] = k
    lost = sorted(universe - set(owner))
    if lost:
        problems.append(f"{len(lost)} اختباراً في لا وظيفة: " + " · ".join(lost[:10]))

    executed: dict[str, str] = {}
    for k, r in sorted(runs.items()):
        outcomes = r.get("outcomes", {})
        missing = sorted(set(collects.get(k, {}).get("selected", [])) - set(outcomes))
        if missing:
            problems.append(f"الوظيفة {k}: {len(missing)} اختباراً اختير ولم يُشغَّل: " + " · ".join(missing[:10]))
        executed.update(outcomes)

    collected_total = max((v["collected"] for v in collects.values()), default=0)
    ran = len(set(executed) & universe)
    print(f"جُمع: {collected_total} · في الكلِّ المقسوم: {len(universe)} · شُغّل: {ran} · الوظائف: {len(runs)}/{count}")
    if ran < collected_total:
        problems.append(f"**شُغّل {ran} من {collected_total} جُمعت** — التقسيمُ أسقط اختبارات")

    failed = sorted(n for n, o in executed.items() if o in BAD)
    for nodeid in failed:
        print(f"FAILED {nodeid}")

    # **الأزمنةُ المدموجة** — يُقسَم بها التشغيلُ التالي
    files: dict[str, dict] = {}
    for r in runs.values():
        for name, entry in r.get("files", {}).items():
            agg = files.setdefault(name, {"seconds": 0.0, "tests": 0})
            agg["seconds"] += entry["seconds"]
            agg["tests"] += entry["tests"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"run": os.environ.get("GITHUB_RUN_ID", "local"), "total_tests": collected_total, "files": files}, ensure_ascii=False),
        encoding="utf-8",
    )
    serial = sum(v["seconds"] for v in files.values())
    print(f"زمنُ الاختبارات متتابعاً: {serial:.0f}ث")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    notes = [f"**{ran}** اختباراً شُغّل من **{collected_total}** جُمع، على **{len(runs)}** وظيفة"]
    if previous and previous.is_file():
        try:
            before = json.loads(previous.read_text(encoding="utf-8")).get("total_tests", 0)
        except ValueError:
            before = 0
        if before and collected_total < before:
            notes.append(f"⚠ **عددُ الاختبارات نقص**: {before} ⇐ {collected_total} — حذفٌ يُرى لا يُخفى")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(f"- {n}" for n in notes) + "\n")

    for p in problems:
        print(f"✗ {p}")
    if problems or failed:
        return 1
    print("✓ كلُّ ما جُمع شُغّل مرّةً واحدةً في وظيفةٍ واحدة، ولا سقوط.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
