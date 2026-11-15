#!/usr/bin/env python3
"""**كم وظيفةً تحتاج المجموعة؟** — يُحسب في كلِّ تشغيلٍ من الأزمنة المقيسة، لا يُكتب بيد (قرارُ المالك 2026-11-15).

    python3 scripts/ci_plan.py backend/.ci/durations.json   # يكتب shards/count في $GITHUB_OUTPUT

**القاعدة**: زمنُ المجموعة المتتابعُ المقيس ÷ (ميزانيةُ الوظيفة × كفاءةُ العمّال) — مقرَّباً لأعلى، **ولا يقلّ عن الحدِّ الأدنى**.
فحين تكبر المجموعةُ يكبر عددُ الوظائف وحدَه، **وحين يتجاوز التشغيلُ عشرَ دقائق يقوله `ci_shards_check.py` في الملخّص**.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

#: **ميزانيةُ الوظيفة للاختبارات وحدَها** — والباقي من العشر للبناء والقاعدة والتجميع (~٢ د مقيسة)
SHARD_BUDGET_SECONDS = 330
#: **عمّالُ الوظيفة الفعّالون** — أربعُ أنوية، والقاعدةُ مشتركةٌ بينها فلا تبلغ الأربعة
WORKER_EFFICIENCY = 3.0
MIN_SHARDS = 6
#: **سقفٌ يمنع الانفلات** — والتشغيلاتُ المتزامنةُ في الحساب المجّانيّ عشرون
MAX_SHARDS = 14
#: **حين لا قياسَ بعد** — المجموعةُ المتتابعةُ في CI ‏43707658269
FALLBACK_SERIAL_SECONDS = 3278


def shard_count(durations: dict) -> tuple[int, float, str]:
    files = durations.get("files") or {}
    total = sum(float(v.get("seconds", 0)) for v in files.values() if isinstance(v, dict))
    source = f"مقيسٌ في التشغيل {durations.get('run', '؟')}"
    if total <= 0:
        total, source = float(FALLBACK_SERIAL_SECONDS), "لا قياسَ بعد — زمنُ CI ‏43707658269"
    need = math.ceil(total / (SHARD_BUDGET_SECONDS * WORKER_EFFICIENCY))
    return max(MIN_SHARDS, min(MAX_SHARDS, need)), total, source


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else None
    durations = {}
    if path and path.is_file():
        try:
            durations = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            durations = {}
    count, total, source = shard_count(durations)
    print(f"المجموعةُ المتتابعة: {total:.0f}ث ({source}) ⇐ {count} وظيفة")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"count={count}\n")
            fh.write(f"shards={json.dumps(list(range(1, count + 1)))}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
