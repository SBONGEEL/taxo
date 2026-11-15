#!/usr/bin/env python3
"""**المجموعةُ السريعةُ لإيداعٍ وسيط** (قرارُ المالك 2026-11-15).

    python3 scripts/ci_fast_set.py <جذرُ شجرة الإيداع> <الإيداع> <ملفُّ المخرج>

**الرأسُ المرفوعُ يُختبر بالمجموعة الكاملة دائماً** — وهذا للإيداعات التي قبله واحداً واحداً، ويختار:

1. **كلَّ اختبارات المال والدفتر والدفع والأمن والصلاحيات** — بأسماء ملفّاتها (`ALWAYS`)، في كلِّ إيداعٍ بلا استثناء.
2. **وحرّاسَ العقد** (البابان، الترحيلات، الأقفال، صيغةُ المال…) — رخيصةٌ وتمسك ما لا يُرى.
3. **واختباراتِ ما غيّره الإيداع**: ملفُّ اختبارٍ تغيّر، **وكلُّ اختبارٍ يذكر وحدةً تغيّرت** (`services/rides.py` ⇐ كلُّ اختبارٍ فيه
   `rides`).

**ولا قائمةَ ملفّاتٍ تُكتب بيد**: ملفُّ اختبارٍ جديدٌ باسمٍ ماليٍّ أو أمنيٍّ يقع في (١) وحدَه، وغيرُه يقع في (٣) يومَ تتغيّر وحدتُه.
**وما لا يمسكه**: اختبارٌ غيرُ ماليٍّ لوحدةٍ لم تتغيّر في هذا الإيداع — والرأسُ يقيسه كاملاً قبل أيِّ رفع.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ALWAYS = re.compile(
    r"(wallet|ledger|payment|pay_|_pay|paid|money|topup|top_up|withdraw|subscri|card|refund|commission|fare|pric|cliq|advance|"
    r"settle|charge|transfer|payout|telr|gateway|nowpay|moonpay|chargily|sofiz|crypto|invoice|bonus|reward|referral|promo|"
    r"coupon|discount|cashback|earning|finance|dispute|receipt|balance|"
    r"auth|security|permission|role|idor|owner|staff|password|otp|token|secret|credential|login|totp|two_factor|2fa|session|"
    r"rate_limit|ratelimit|audit|account|signup|register|"
    r"lock|concurren|migration|two_doors|guard|contract|no_shortcut|money_format|digit|label_gender|notification_data)",
    re.IGNORECASE,
)


def changed(root: Path, commit: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", f"{commit}^", commit],
        capture_output=True, text=True, check=False,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def main(argv: list[str]) -> int:
    root, commit, out = Path(argv[1]), argv[2], Path(argv[3])
    tests_dir = root / "backend" / "tests"
    tests = sorted(p for p in tests_dir.rglob("test_*.py"))
    rel = {p: "tests/" + p.relative_to(tests_dir).as_posix() for p in tests}
    pick: dict[str, str] = {}
    for p, name in rel.items():
        if ALWAYS.search(p.name):
            pick[name] = "مالٌ/أمنٌ/حارس"

    diff = changed(root, commit)
    modules: set[str] = set()
    for path in diff:
        if path.startswith("backend/tests/") and Path(path).name.startswith("test_") and path.endswith(".py"):
            name = path.removeprefix("backend/")
            if (root / path).is_file():
                pick.setdefault(name, "تغيّر في الإيداع")
        elif path.startswith("backend/app/") and path.endswith(".py"):
            stem = Path(path).stem
            if stem != "__init__":
                modules.add(stem)
    if modules:
        words = re.compile(r"\b(" + "|".join(re.escape(m) for m in sorted(modules)) + r")\b")
        for p, name in rel.items():
            if name not in pick and words.search(p.read_text(encoding="utf-8", errors="ignore")):
                pick[name] = "يذكر وحدةً تغيّرت"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(sorted(pick)) + "\n", encoding="utf-8")
    by_reason: dict[str, int] = {}
    for reason in pick.values():
        by_reason[reason] = by_reason.get(reason, 0) + 1
    print(f"{commit[:8]}: {len(pick)} ملفّاً من {len(rel)} — " + " · ".join(f"{r}: {n}" for r, n in sorted(by_reason.items())))
    print(f"الوحداتُ المتغيّرة: {', '.join(sorted(modules)) or 'لا شيء في الخلفية'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
