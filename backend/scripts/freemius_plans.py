"""**خططُ Freemius الأربع بأسعار اللوحة الحاليّة** (أمرُ المالك ٢٠٢٦-١١-٢٦، البند ٢) — تُقرأ ثمّ يُنشأ الناقصُ وحدَه.

    python -m scripts.freemius_plans --keys /in/freemius.env            # معاينة: ما هو قائمٌ وما سيُنشأ
    python -m scripts.freemius_plans --keys /in/freemius.env --apply    # إنشاءُ الناقص، وكتابةُ معرّفاتها في الملفّ نفسِه

**الأسعارُ من `digistore24.PRICE_MAP` لا من هنا** — لا يُخترع سعرٌ ولا يُغيَّر: 3 ⇐ 4.25$ · 17 ⇐ 24.00$ · 45 ⇐ 63.50$ · 60 ⇐ 84.50$.
**ودورتُها `lifetime`** (دفعةٌ واحدةٌ لا تتجدّد)، **ومدّتُها في اسمها** فلا يظنّ الدافعُ أنه يشتري وصولاً دائماً — ومدّةُ الاشتراك تحسبها TAXO.

**لا يُطبع سرّ**: ملفُّ المفاتيح (`product_id`, `public_key`, `secret_key`, `api_token`, و`developer_id` إن وُجد) يُقرأ ولا يُعرض منه
إلا معرّفُ المنتج والخطط. **والإنشاءُ بمفتاح المنتج قد يُرفض** (واجهتُهم تجعل إنشاءَ الخطط في نطاق المطوّر) — فيُقال ذلك بنصّه ويُنشئها
المالكُ من اللوحة بالأسماء والأسعار المطبوعة هنا.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from decimal import Decimal

import httpx

from app.services.payment_gateways.digistore24 import PRICE_MAP

API = "https://api.freemius.com/v1"

#: **اسمُ كلِّ خطّةٍ عندهم بمدّتها** — والمعرّفُ النصّيُّ (`name`) لاتينيٌّ صغيرٌ كما تشترط واجهتُهم
TITLES = {
    "daily": ("x1", "X1 · TAXO Driver · 1 day"),
    "weekly": ("x7", "X7 · TAXO Driver · 7 days"),
    "monthly": ("x30", "X30 · TAXO Driver · 30 days (TAXO MAN 45)"),
    "monthly_full": ("x30-full", "X30-FULL · TAXO Driver · 30 days"),
}


def read_keys(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    missing = [k for k in ("product_id", "api_token") if not values.get(k)]
    if missing:
        sys.exit(f"ينقص الملفَّ: {', '.join(missing)}")
    return values


def write_plan_ids(path: pathlib.Path, ids: dict[str, str]) -> None:
    """يُكتب `plan_<خطّة>=<معرّف>` في الملفّ نفسِه — والسطورُ الأخرى (والأسرار) كما هي حرفاً."""
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("plan_")]
    lines += [f"plan_{plan}={pid}" for plan, pid in ids.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys", required=True, type=pathlib.Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    keys = read_keys(args.keys)
    pid = keys["product_id"]
    client = httpx.Client(base_url=API, timeout=20, headers={"Authorization": f"Bearer {keys['api_token']}"})

    product = client.get(f"/products/{pid}.json")
    if product.status_code != 200:
        sys.exit(f"المنتجُ لم يُقرأ: HTTP {product.status_code}")
    developer_id = keys.get("developer_id") or str(product.json().get("developer_id") or "")
    print(f"المنتج {pid}: {product.json().get('title')!r}")

    existing = {row.get("name"): row for row in client.get(f"/products/{pid}/plans.json").json().get("plans", [])}
    wanted = {usd_plan: usd for _amount, (usd_plan, usd) in PRICE_MAP.items()}
    ids: dict[str, str] = {}
    for plan, (slug, title) in TITLES.items():
        usd = Decimal(str(wanted[plan]))
        row = existing.get(slug)
        if row:
            prices = client.get(f"/products/{pid}/plans/{row['id']}/pricing.json").json().get("pricing", [])
            lifetime = {Decimal(str(p.get("lifetime_price"))) for p in prices if p.get("lifetime_price") is not None}
            state = "✓" if lifetime == {usd} else f"⚠ سعرُها عندهم {sorted(lifetime)} لا {usd}"
            print(f"  {slug:9} قائمة ({row['id']}) {state}")
            ids[plan] = str(row["id"])
            continue
        print(f"  {slug:9} ناقصة — {title} · {usd}$ مرّةً واحدة")
        if not args.apply:
            continue
        if not developer_id:
            sys.exit("لا معرّفَ للمطوّر — يُنشئها المالكُ من اللوحة بالأسماء والأسعار أعلاه")
        made = client.post(
            f"/developers/{developer_id}/products/{pid}/plans.json",
            json={"name": slug, "title": title, "is_require_subscription": False, "is_block_features": True},
        )
        if made.status_code not in (200, 201):
            sys.exit(f"إنشاءُ الخطّة رُفض: HTTP {made.status_code} — يُنشئها المالكُ من اللوحة بالأسماء والأسعار أعلاه")
        plan_id = str(made.json()["id"])
        priced = client.post(
            f"/developers/{developer_id}/products/{pid}/plans/{plan_id}/pricing.json",
            json={"licenses": 1, "lifetime_price": float(usd), "currency": "usd"},
        )
        if priced.status_code not in (200, 201):
            sys.exit(f"سعرُ الخطّة {slug} رُفض: HTTP {priced.status_code} — الخطّةُ {plan_id} أُنشئت بلا سعر")
        print(f"    أُنشئت ({plan_id}) بسعر {usd}$")
        ids[plan] = plan_id
    if args.apply and len(ids) == len(TITLES):
        write_plan_ids(args.keys, ids)
        print("كُتبت معرّفاتُ الخطط الأربع في ملفّ المفاتيح")


if __name__ == "__main__":
    main()
