"""بصمةُ القاعدة كلِّها قبل اختبار الحمل وبعده (SPEC §٧٥) — **عددُ صفوف كلِّ جدولٍ وبصمةُ محتواه كلِّه**، قراءةً وحدَها.

    docker compose … run --rm --no-deps backend python -m scripts.stress_fingerprint > fp.json

* **لكلِّ جدولٍ في `public`**: عددُ صفوفه **وبصمةٌ لا تتبع الترتيب** — `md5` لكلِّ صفٍّ بنصّه الكامل، تُرتَّب البصماتُ ثمّ تُجمع بـ`md5`
  واحد. **فصفٌّ تغيّر حرفاً أو أُضيف أو حُذف يغيّر بصمةَ جدوله**، وترتيبُ القراءة لا يغيّرها.
* **وتُسمّى مجموعاتُ المالك** (الإعدادات · الأسعار · متجر المركبات · عقود المزوّدين · المستخدمون · المحفظة/الدفتر · الاشتراكات) **ولا
  يُستثنى جدول** — فالمقارنةُ تقول كلَّ فرقٍ ويُفسَّر، لا تُخفيه.
* **ولا يطبع قيمة صفّ**: بصماتٌ وأعدادٌ وحدَها — ولا سرَّ يخرج (عقودُ المزوّدين مشفَّرةٌ أصلاً، وبصمتُها بصمةُ نصِّها المشفَّر).
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402

#: **مجموعاتُ المالك بأسمائه** (§٧٥-أ) — تُقرأ في التقرير مجموعةً مجموعة؛ وكلُّ جدولٍ آخرَ يُبصم كذلك
GROUPS: dict[str, tuple[str, ...]] = {
    "الإعدادات": ("feature_flags", "payment_settings", "wallet_settings", "service_settings", "commission_settings",
                  "dispatch_settings", "map_settings", "otp_settings", "security_settings", "advance_settings",
                  "referral_settings", "cancellation_settings", "notification_settings"),
    "الأسعار": ("pricing_rules", "pricing_zones", "zone_pricing_rules", "facilities", "subscription_plans", "subscription_offers"),
    "متجر المركبات": ("vehicle_skins", "storefront_items"),
    "عقود المزوّدين": ("provider_credentials",),
    "المستخدمون": ("users", "drivers", "vehicles", "driver_documents"),
    "المحفظة والدفتر": ("wallet_transactions", "money_roundings", "driver_debts", "driver_advances", "withdrawal_requests",
                        "wallet_topup_requests", "payment_requests"),
    "الاشتراكات": ("driver_subscriptions",),
}


async def fingerprint(session) -> dict:
    tables = (
        await session.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'spatial_ref_sys' ORDER BY tablename"
            )
        )
    ).scalars().all()
    out: dict[str, dict] = {}
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        count, digest = (
            await session.execute(
                text(
                    f"SELECT count(*), md5(coalesce(string_agg(h, '' ORDER BY h), '')) "
                    f"FROM (SELECT md5(t::text) AS h FROM {quoted} t) s"
                )
            )
        ).one()
        out[table] = {"rows": int(count), "md5": digest}
    return out


async def main() -> None:
    async with SessionLocal() as session:
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        tables = await fingerprint(session)
        await session.rollback()
    await engine.dispose()
    groups = {name: {t: tables[t] for t in members if t in tables} for name, members in GROUPS.items()}
    print(json.dumps({"taken_at": datetime.now(UTC).isoformat(), "tables": tables, "groups": groups}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
