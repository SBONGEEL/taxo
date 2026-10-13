"""تنظيفُ اختبار الحمل (SPEC §٧٥) — **كلُّ صفٍّ يرجع إلى حسابٍ موسومٍ في النطاق المحجوز يُحذف، ولا يُمسّ غيرُه، ويُبرهَن**.

    docker compose … run --rm --no-deps backend python -m scripts.stress_cleanup            # معاينة: ما سيُحذف جدولاً جدولاً
    … --apply                                                                              # الحذفُ في معاملةٍ واحدة

## كيف يجد ما يُحذف — **من خريطة القاعدة نفسِها لا من قائمةٍ تُكتب بيد**

١. **البذرةُ**: المستخدمون الموسومون بالتجربة **ورقمُهم في النطاق المحجوز** (`services/stress`) — الشرطان معاً.
٢. **الإغلاقُ بالمفاتيح الأجنبيّة** (`pg_constraint`): كلُّ صفٍّ في أيِّ جدولٍ يشير بمفتاحٍ أجنبيٍّ إلى صفٍّ في الإغلاق يدخله — مرّةً بعد مرّة حتى لا
   يدخل جديد. **فرحلةٌ ودفعتُها ونقاطُ مسارها ودَينُ عمولتها وإشعاراتُ صاحبها وجلساتُه** تُعرف بلا أن تُسمّى.
٣. **وما يُشير بلا مفتاحٍ أجنبيّ**: سجلُّ التدقيق (`entity_id` · `actor_id`) — **يدخل الإغلاقَ ما سمّى صفّاً فيه**.
٤. **الحذفُ من الأبناء إلى الآباء** بمحاولاتٍ متكرّرةٍ تحت نقاط حفظ — **والمفاتيحُ الأجنبيّةُ تبقى حارسةً كلَّ لحظة** (لا تُطفأ).

## ما يقف عنده ولا يُصلحه

* **قيدٌ في الدفتر لحسابٍ موسوم** (`wallet_transactions` — يُضاف إليه ولا يُحذف): **الاختبارُ مبنيٌّ ألّا يكتب فيه شيئاً** (نقدٌ وحدَه،
  واشتراكٌ بلا مال، ورصيدُ الكبتن صفرٌ فلا عمولةَ تُحصَّل منه) — **فظهورُه خبرٌ يُعرض ولا يُحذف**.
* **و`money_roundings` يُضاف إليه ولا يُحذف** (مشغّلُ «append-only»، `0104`) — **وكلُّ أجرةٍ مقرَّبةٍ تكتب فيه صفّاً**. فيُطفأ مشغّلُه
  **داخل معاملة الحذف وحدَها** (`ALTER TABLE … DISABLE TRIGGER`) **ويُشعَل قبل الالتزام** — والقاعدةُ تُطبّق الاثنين معاً أو لا شيء،
  **ولا يُحذف منه إلا صفوفُ الإغلاق**. ويُقال في التقرير.
* **وبعد الحذف يُمسح كلُّ عمودِ معرّفٍ في كلِّ جدول**: صفرُ صفٍّ يحمل معرّفاً حُذف — **وإلا تراجعٌ** والجدولُ يُسمّى.

## `--keep-ledger` — **حين وقع القيدُ فعلاً** (قِيس على الإنتاج ٢٠٢٦-١٠-١٣)

إلغاءٌ سبق قبولاً فصار إلغاءً بعد القبول: رسمٌ −1.000 وتعويضٌ +1.000 لكبتنِ اختبار (صافيهما صفر). **والقيدُ لا يُحذف** — فيبقى **هو وما
يشير إليه وحدَه** (الرحلةُ وراكبُها وكبتنُها ومركبتُه — آباؤه بالمفاتيح الأجنبيّة، مرّةً بعد مرّة)، وسطرُ التدقيق الذي يسمّي شيئاً منها،
**ويُحذف كلُّ ما سواه**. **ويُطبع الباقي جدولاً جدولاً** ليُذكر في التقرير. **ولا يُشعَل هذا الطورُ إلا بقرار** (العَلَم)، والافتراضُ
وقوفٌ كما كان.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402
from app.services import stress  # noqa: E402

APPEND_ONLY_DELETABLE = {"money_roundings": "money_roundings_append_only"}
REFUSED_TABLES = ("wallet_transactions",)


class CleanupRefused(RuntimeError):
    pass


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


async def _edges(session: AsyncSession) -> list[tuple[str, str, str, str]]:
    """(الجدولُ الابن، عمودُه، الجدولُ الأب، عمودُه) — **لكلِّ مفتاحٍ أجنبيٍّ بعمودٍ واحد** في `public`."""
    rows = await session.execute(
        text(
            """
            SELECT c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text, af.attname
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
            JOIN pg_attribute af ON af.attrelid = c.confrelid AND af.attnum = c.confkey[1]
            WHERE c.contype = 'f' AND array_length(c.conkey, 1) = 1
              AND c.connamespace = 'public'::regnamespace
            """
        )
    )
    return [(child.strip('"'), col, parent.strip('"'), pcol) for child, col, parent, pcol in rows.all()]


async def _closure(session: AsyncSession) -> dict[str, set[str]]:
    """**ما يُحذف: ctid كلِّ صفٍّ لكلِّ جدول** — والقيمُ التي يُشار بها إليه تُجمع في جداول مؤقّتة تُبنى منها الدورةُ التالية."""
    await session.execute(text("CREATE TEMP TABLE stress_rows (tbl text, rid tid, PRIMARY KEY (tbl, rid)) ON COMMIT DROP"))
    await session.execute(
        text(
            "INSERT INTO stress_rows SELECT 'users', ctid FROM users WHERE is_test AND phone LIKE :prefix"
        ),
        {"prefix": stress.STRESS_PHONE_PREFIX + "%"},
    )
    edges = await _edges(session)
    changed = True
    while changed:
        changed = False
        for child, col, parent, pcol in edges:
            added = (
                await session.execute(
                    text(
                        f"INSERT INTO stress_rows SELECT :child, c.ctid FROM {q(child)} c "
                        f"WHERE c.{q(col)} IN (SELECT p.{q(pcol)} FROM {q(parent)} p "
                        f"JOIN stress_rows s ON s.tbl = :parent AND s.rid = p.ctid) "
                        f"ON CONFLICT DO NOTHING"
                    ),
                    {"child": child, "parent": parent},
                )
            ).rowcount
            if added:
                changed = True
        # **سجلُّ التدقيق يسمّي بلا مفتاح** — كياناً في الإغلاق (`entity_id`)؛ والفاعلُ مفتاحٌ أجنبيٌّ تجمعه الدورةُ أعلاه
        await _ids_table(session)
        added = (
            await session.execute(
                text(
                    "INSERT INTO stress_rows SELECT 'admin_audit_logs', a.ctid FROM admin_audit_logs a "
                    "WHERE a.entity_id IN (SELECT id FROM stress_ids) ON CONFLICT DO NOTHING"
                )
            )
        ).rowcount
        if added:
            changed = True
    counts = defaultdict(set)
    for tbl, rid in (await session.execute(text("SELECT tbl, rid::text FROM stress_rows"))).all():
        counts[tbl].add(rid)
    return counts


async def _keep_ledger(session: AsyncSession, edges) -> dict[str, int]:
    """**قيودُ الدفتر وآباؤها** تُنزع من الإغلاق — صفُّ الأب يبقى ما دام ابنٌ باقٍ يشير إليه؛ **ولا يُبقى إلا ما في الإغلاق أصلاً**."""
    await session.execute(text("CREATE TEMP TABLE stress_keep (tbl text, rid tid, PRIMARY KEY (tbl, rid)) ON COMMIT DROP"))
    await session.execute(
        text("INSERT INTO stress_keep SELECT tbl, rid FROM stress_rows WHERE tbl = ANY(:t)"), {"t": list(REFUSED_TABLES)}
    )
    changed = True
    while changed:
        changed = False
        for child, col, parent, pcol in edges:
            added = (
                await session.execute(
                    text(
                        f"INSERT INTO stress_keep SELECT :parent, p.ctid FROM {q(parent)} p "
                        f"JOIN stress_rows r ON r.tbl = :parent AND r.rid = p.ctid "
                        f"WHERE p.{q(pcol)} IN (SELECT c.{q(col)} FROM {q(child)} c "
                        f"JOIN stress_keep k ON k.tbl = :child AND k.rid = c.ctid) "
                        f"ON CONFLICT DO NOTHING"
                    ),
                    {"child": child, "parent": parent},
                )
            ).rowcount
            if added:
                changed = True
    # وسطرُ التدقيق الذي يسمّي صفّاً باقياً يبقى معه — تاريخُه لا يُمحى وهو قائم
    kept_ids = set()
    for tbl in (await session.execute(text("SELECT DISTINCT tbl FROM stress_keep"))).scalars().all():
        has_id = await session.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
                "AND column_name='id' AND data_type='uuid'"
            ),
            {"t": tbl},
        )
        if has_id:
            kept_ids.update(
                (
                    await session.execute(
                        text(f"SELECT t.id FROM {q(tbl)} t JOIN stress_keep k ON k.tbl = :t AND k.rid = t.ctid"), {"t": tbl}
                    )
                ).scalars().all()
            )
    if kept_ids:
        await session.execute(
            text(
                "INSERT INTO stress_keep SELECT 'admin_audit_logs', a.ctid FROM admin_audit_logs a "
                "JOIN stress_rows r ON r.tbl = 'admin_audit_logs' AND r.rid = a.ctid WHERE a.entity_id = ANY(:ids) "
                "ON CONFLICT DO NOTHING"
            ),
            {"ids": list(kept_ids)},
        )
    await session.execute(text("DELETE FROM stress_rows r USING stress_keep k WHERE r.tbl = k.tbl AND r.rid = k.rid"))
    kept = defaultdict(int)
    for tbl, n in (await session.execute(text("SELECT tbl, count(*) FROM stress_keep GROUP BY tbl"))).all():
        kept[tbl] = int(n)
    return dict(kept)


async def _ids_table(session: AsyncSession) -> bool:
    """**كلُّ معرّفٍ (`id`) لصفٍّ في الإغلاق** — به يُعرف ما يسمّيه سجلُّ التدقيق بلا مفتاح، **وبه يُمسح بعد الحذف**."""
    await session.execute(text("DROP TABLE IF EXISTS stress_ids"))
    await session.execute(text("CREATE TEMP TABLE stress_ids (id uuid PRIMARY KEY) ON COMMIT DROP"))
    tables = (await session.execute(text("SELECT DISTINCT tbl FROM stress_rows"))).scalars().all()
    for tbl in tables:
        has_id = await session.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name=:t "
                "AND column_name='id' AND data_type='uuid'"
            ),
            {"t": tbl},
        )
        if has_id:
            await session.execute(
                text(
                    f"INSERT INTO stress_ids SELECT t.id FROM {q(tbl)} t JOIN stress_rows s ON s.tbl = :t AND s.rid = t.ctid "
                    "ON CONFLICT DO NOTHING"
                ),
                {"t": tbl},
            )
    return True


async def _delete(session: AsyncSession, plan: dict[str, set[str]]) -> dict[str, int]:
    remaining = {tbl for tbl, rids in plan.items() if rids}
    deleted: dict[str, int] = {}
    for table, trigger in APPEND_ONLY_DELETABLE.items():
        if table in remaining:
            await session.execute(text(f"ALTER TABLE {q(table)} DISABLE TRIGGER {q(trigger)}"))
    for _ in range(len(remaining) + 2):
        if not remaining:
            break
        progressed = False
        for tbl in sorted(remaining):
            savepoint = await session.begin_nested()
            try:
                count = (
                    await session.execute(
                        text(f"DELETE FROM {q(tbl)} t USING stress_rows s WHERE s.tbl = :t AND s.rid = t.ctid"), {"t": tbl}
                    )
                ).rowcount
                await savepoint.commit()
                deleted[tbl] = deleted.get(tbl, 0) + count
                remaining.discard(tbl)
                progressed = True
            except Exception:  # noqa: BLE001 — ابنٌ لم يُحذف بعد يشير إليه؛ يُعاد في الدورة التالية
                await savepoint.rollback()
        if not progressed:
            break
    for table, trigger in APPEND_ONLY_DELETABLE.items():
        await session.execute(text(f"ALTER TABLE {q(table)} ENABLE TRIGGER {q(trigger)}"))
    if remaining:
        raise CleanupRefused(f"لم يُحذف كلُّه — يشير إليه ما ليس في الإغلاق: {sorted(remaining)}")
    return deleted


async def _leftovers(session: AsyncSession) -> dict[str, int]:
    """**مسحُ كلِّ عمودِ معرّفٍ في كلِّ جدول** بعد الحذف — صفرٌ يحمل معرّفاً حُذف."""
    columns = (
        await session.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND data_type='uuid'"
            )
        )
    ).all()
    found: dict[str, int] = {}
    for table, column in columns:
        n = await session.scalar(text(f"SELECT count(*) FROM {q(table)} WHERE {q(column)} IN (SELECT id FROM stress_ids)"))
        if n:
            found[f"{table}.{column}"] = int(n)
    return found


async def run(*, write: bool, session_factory=SessionLocal, keep_ledger: bool = False) -> dict:
    async with session_factory() as session:
        plan = await _closure(session)
        sizes = {tbl: len(rids) for tbl, rids in sorted(plan.items())}
        kept: dict[str, int] = {}
        for table in REFUSED_TABLES:
            if sizes.get(table) and not keep_ledger:
                await session.rollback()
                raise CleanupRefused(f"{table}: {sizes[table]} صفّاً لحسابات الحمل — يُضاف إليه ولا يُحذف؛ يُعرض على المالك")
        if keep_ledger and any(sizes.get(t) for t in REFUSED_TABLES):
            kept = await _keep_ledger(session, await _edges(session))
            plan = defaultdict(set)
            for tbl, rid in (await session.execute(text("SELECT tbl, rid::text FROM stress_rows"))).all():
                plan[tbl].add(rid)
            sizes = {tbl: len(rids) for tbl, rids in sorted(plan.items())}
        await _ids_table(session)
        deleted = await _delete(session, plan)
        left = await _leftovers(session)
        if left:
            await session.rollback()
            raise CleanupRefused(f"بقي ما يحمل معرّفاً محذوفاً: {left}")
        users_left = await session.scalar(
            text("SELECT count(*) FROM users WHERE phone LIKE :prefix"), {"prefix": stress.STRESS_PHONE_PREFIX + "%"}
        )
        if users_left != kept.get("users", 0):
            await session.rollback()
            raise CleanupRefused(f"بقي {users_left} حساباً في النطاق المحجوز")
        if write:
            await session.commit()
        else:
            await session.rollback()
    return {"plan": sizes, "deleted": deleted, "kept": kept}


def main() -> int:
    parser = argparse.ArgumentParser(description="تنظيفُ اختبار الحمل (SPEC §٧٥)")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--keep-ledger", action="store_true", help="قيودُ الدفتر وما تشير إليه تبقى، ويُحذف ما سواها")
    args = parser.parse_args()
    try:
        result = asyncio.run(run(write=args.apply, keep_ledger=args.keep_ledger))
    except CleanupRefused as exc:
        print(f"✗ {exc}")
        return 1
    finally:
        asyncio.run(engine.dispose())
    for tbl, n in result["plan"].items():
        print(f"  {tbl}: {n}")
    for tbl, n in result["kept"].items():
        print(f"  ↺ باقٍ (قيدٌ في الدفتر وما يشير إليه) {tbl}: {n}")
    print(("✓ حُذف كلُّه والتُزم" if args.apply else "· معاينة — حُذف ثمّ تُراجع (أعد بـ--apply)") + f" · {sum(result['deleted'].values())} صفّاً")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
