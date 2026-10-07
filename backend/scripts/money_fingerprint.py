"""بصمةُ المال — **قراءةٌ وحدَها** (SPEC §٦٥-أ، شرطُ المالك لرفع `redesign`).

    python -m scripts.money_fingerprint > before.json                       # قبل الترحيلات
    python -m scripts.money_fingerprint --as-of <taken_at> > after.json     # بعدها — بحالِ الدفتر لحظةَ «قبل»
    python -m scripts.money_fingerprint --compare before.json after.json

**الشرط**: «لا يتغيّر رصيدٌ قائمٌ ولا قيدٌ قائمٌ في الدفتر — والجداولُ والأعمدةُ الجديدةُ لا بأس بها». **فتُقاس الصفوفُ القائمةُ بأعمدتها
القائمة وحدَها**: ما يُضاف بعد الترحيلة من صفوفٍ أو أعمدةٍ لا يدخل البصمة، وما كان قبلها يُقارَن حرفاً.

**ثلاثُ طبقاتٍ لا واحدة** — فالمجموعُ وحدَه يستر تغيّراً يقابله تغيّرٌ آخر:
1. **رصيدُ كلِّ محفظة** — مجموعُ قيودها بمالكها ونوعه (والعملةُ دولةُ المالك — لا عمودَ لها في الدفتر).
2. **عددُ القيود ومجموعُها لكلِّ نوع.**
3. **بصمةُ كلِّ صفٍّ قائم** — `sha256` على أعمدة المال لكلِّ صفٍّ مرتَّباً بمعرّفه، لكلِّ جدولِ مال.

**و`--as-of` هو ما يجعل المقارنةَ على الإنتاج ممكنة**: بعد الرفع تصل قيودٌ جديدةٌ من حركةٍ حيّة — **والدفترُ لا يُحرَّر** (مشغّلُ
`wallet_transactions_append_only` منذ `0006`)، **فقيودُه حتى لحظة «قبل» هي هي ما كان قبل** — فتُقرأ الطبقاتُ الثلاثُ للدفتر حتى تلك اللحظة.
**أمّا الجداولُ الأخرى فتتغيّر حالُ صفوفها بالحركة الحيّة** (دفعةٌ معلّقةٌ يؤكّدها كبتن): فتُقارَن **صرامةً على نسخة الإنتاج** حيث لا حركة،
**وتُذكر على الإنتاج ولا تُسقط** — والشرطُ نفسُه «الأرصدةُ ومجاميعُ الدفتر».

**ولا كتابةَ فيه**: `SELECT` وحدَه، والمعاملةُ تُختم بـ`ROLLBACK`. **ولا سرَّ في مخرجه** — معرّفاتٌ ومبالغُ وبصمات.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime

from sqlalchemy import text

from app.core.db import SessionLocal, engine

LEDGER = "wallet_transactions"

#: **جداولُ المال وأعمدتُها القائمةُ قبل `redesign`** — أعمدةٌ تُضاف بعده لا تدخل البصمة، فلا يُقرأ «عمودٌ جديد» تغيّراً
TABLES: dict[str, list[str]] = {
    LEDGER: ["id", "owner_id", "owner_type", "type", "amount", "created_at"],
    "payments": ["id", "ride_id", "method", "amount", "currency", "status", "confirmed_at"],
    "driver_debts": ["id", "driver_id", "amount", "collected", "status"],
    "driver_subscriptions": ["id", "driver_id", "amount_paid", "status", "starts_at", "expires_at"],
    "withdrawal_requests": ["id", "amount", "status"],
    "wallet_topup_requests": ["id", "amount", "status"],
    "driver_advances": ["id", "amount", "status"],
    "ride_cancellation_charges": ["id", "amount", "status"],
    "tips": ["id", "amount"],
}


async def _columns(session, table: str) -> set[str]:
    rows = await session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = :t"),
        {"t": table},
    )
    return {row[0] for row in rows}


async def fingerprint(*, as_of: str | None = None, dispose: bool = False) -> dict:
    """البصمة — **و`as_of` يقصر الدفترَ على ما كُتب حتى لحظة «قبل»** (وحدَه: الجداولُ الأخرى تُقرأ كما هي)."""
    out: dict = {"wallets": {}, "ledger_by_type": {}, "tables": {}, "as_of": as_of}
    cutoff = " WHERE created_at <= :as_of" if as_of else ""
    params = {"as_of": datetime.fromisoformat(as_of)} if as_of else {}
    async with SessionLocal() as session:
        out["taken_at"] = str(await session.scalar(text("SELECT now()")))
        rows = await session.execute(
            text(
                f"SELECT owner_id::text, owner_type::text, SUM(amount)::text, COUNT(*) FROM {LEDGER}{cutoff} "  # noqa: S608
                "GROUP BY owner_id, owner_type ORDER BY 1, 2"
            ),
            params,
        )
        for owner, kind, total, count in rows:
            out["wallets"][f"{owner}:{kind}"] = {"balance": total, "entries": count}
        rows = await session.execute(
            text(f"SELECT type::text, COUNT(*), SUM(amount)::text FROM {LEDGER}{cutoff} GROUP BY type ORDER BY 1"),  # noqa: S608
            params,
        )
        for kind, count, total in rows:
            out["ledger_by_type"][kind] = {"count": count, "sum": total}
        for table, wanted in TABLES.items():
            present = await _columns(session, table)
            if not present:
                out["tables"][table] = {"absent": True}
                continue
            cols = [c for c in wanted if c in present]
            select = ", ".join(f"COALESCE({c}::text, '∅')" for c in cols)
            where = cutoff if table == LEDGER else ""
            digest = hashlib.sha256()
            count = 0
            result = await session.stream(text(f"SELECT {select} FROM {table}{where} ORDER BY id"), params)  # noqa: S608
            async for row in result:
                digest.update(("|".join(row) + "\n").encode("utf-8"))
                count += 1
            out["tables"][table] = {"rows": count, "columns": cols, "sha256": digest.hexdigest()}
        await session.rollback()
    if dispose:
        await engine.dispose()
    return out


def compare(before: dict, after: dict) -> tuple[list[str], list[str]]:
    """`(مخالفات، ملاحظات)` — **ما كان قبل يجب أن يبقى حرفاً**، والجديدُ بعده لا يُعدّ تغيّراً.

    الدفترُ ومحافظُه مخالفةٌ دائماً. **والجداولُ الأخرى مخالفةٌ حيث لا `as_of`** (نسخةٌ بلا حركة)، **وملاحظةٌ حيث `as_of`** (إنتاجٌ حيّ)."""
    problems: list[str] = []
    notes: list[str] = []
    for key, value in before["wallets"].items():
        if after["wallets"].get(key) != value:
            problems.append(f"wallet {key}: {value} → {after['wallets'].get(key)}")
    for key, value in before["ledger_by_type"].items():
        if after["ledger_by_type"].get(key) != value:
            problems.append(f"ledger {key}: {value} → {after['ledger_by_type'].get(key)}")
    for table, value in before["tables"].items():
        if after["tables"].get(table) != value:
            line = f"table {table}: {value} → {after['tables'].get(table)}"
            (notes if after.get("as_of") and table != LEDGER else problems).append(line)
    return problems, notes


def main() -> int:
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "--compare":
        with open(args[1], encoding="utf-8") as fb, open(args[2], encoding="utf-8") as fa:
            before, after = json.load(fb), json.load(fa)
        problems, notes = compare(before, after)
        print(f"wallets {len(before['wallets'])} · ledger types {len(before['ledger_by_type'])} · tables {len(before['tables'])}"
              f" · as_of {after.get('as_of') or '—'}")
        for line in notes:
            print("  ملاحظة (حركةٌ حيّة):", line)
        if problems:
            print("✗ تغيّر ما كان قائماً:")
            for line in problems:
                print("  ", line)
            return 1
        print("✓ لم يتغيّر رصيدٌ قائمٌ ولا قيدٌ قائم — مطابقةٌ تامّة")
        return 0
    as_of = args[1] if len(args) == 2 and args[0] == "--as-of" else None
    print(json.dumps(asyncio.run(fingerprint(as_of=as_of, dispose=True)), ensure_ascii=False, sort_keys=True, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
