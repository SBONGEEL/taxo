from __future__ import annotations

import asyncio

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect, text

from app.core.db import engine
from app.core.migration_filters import include_object
from app.models import Base
from tests.conftest import alembic_config


def _describe(diff) -> str:
    """يحوّل عنصر فرق من alembic إلى سطر مقروء."""
    if isinstance(diff, list):  # فروق الأعمدة تأتي كقائمة متداخلة
        return " / ".join(_describe(item) for item in diff)
    kind = diff[0]
    details = ", ".join(
        getattr(part, "name", None) or str(part) for part in diff[1:] if part is not None
    )
    return f"{kind}: {details}"


def _collect_diffs(sync_conn: Connection) -> list:
    context = MigrationContext.configure(
        sync_conn,
        opts={
            "compare_type": True,
            "compare_server_default": True,
            "include_object": include_object,
        },
    )
    return compare_metadata(context, Base.metadata)


async def test_migrations_match_models() -> None:
    """يفشل لو انحرفت الموديلات عن الترحيلات.

    قاعدة الاختبار مبنية بـ `alembic upgrade head`، فإن اكتشف autogenerate أي
    فرق فمعناه أن موديلاً تغيّر بلا ترحيلة مقابلة (أو العكس).
    """
    async with engine.connect() as conn:
        diffs = await conn.run_sync(_collect_diffs)

    assert not diffs, (
        "الموديلات لا تطابق الترحيلات — ولّد ترحيلة جديدة "
        "(alembic revision --autogenerate):\n  "
        + "\n  ".join(_describe(diff) for diff in diffs)
    )


async def test_schema_is_built_by_migrations() -> None:
    """يتأكد أن المخطط جاء من alembic لا من create_all."""
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        revision = await conn.run_sync(
            lambda c: MigrationContext.configure(c).get_current_revision()
        )

    assert "alembic_version" in tables
    # الرأس يُقرأ من مجلد الترحيلات لا يُكتب هنا: رقمٌ مكتوب بيدٍ يعني تعديل
    # هذا الاختبار مع كل مرحلة، والمقصود أصلاً «القاعدة على الرأس» لا رقمُه
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    assert revision == head
    assert {
        "users",
        "drivers",
        "vehicles",
        "driver_documents",
        "rides",
        "pricing_rules",
        "feature_flags",
        "commission_settings",
        "subscription_plans",
        "provider_credentials",
        "admin_audit_logs",
        "wallet_transactions",
        "wallet_topup_requests",
        "withdrawal_requests",
        "wallet_settings",
    } <= tables


async def test_downgrade_then_upgrade_is_clean() -> None:
    """دورة كاملة للخلف وللأمام — تكشف نسيان إسقاط أنواع ENUM في downgrade."""
    config = alembic_config()
    try:
        await asyncio.to_thread(command.downgrade, config, "base")
        await asyncio.to_thread(command.upgrade, config, "head")
    finally:
        # ضمان بقاء القاعدة على head مهما حدث، حتى لا تنهار بقية الاختبارات
        await asyncio.to_thread(command.upgrade, config, "head")
        # أنواع ENUM أُعيد إنشاؤها بـ OIDs جديدة؛ اتصالات المجمع تحمل ذاكرة
        # أنواع قديمة في asyncpg فتفشل لاحقاً بـ "cache lookup failed for type"
        await engine.dispose()

    async with engine.connect() as conn:
        diffs = await conn.run_sync(_collect_diffs)
    assert not diffs


async def test_0068_refuses_to_reshape_a_table_that_has_rows() -> None:
    """**حارسُ `0068` يُقاس بالنفي** — وحارسٌ لم يصح قطُّ لم يُثبت أنه يصيح.

    `0068` تُصلح شكلاً **قِيس فارغاً**: تضيف عمودَي «النوع» و«التطبيق»
    `NOT NULL` **بلا افتراض**، فلا تملك ما تسم به صفّاً قائماً. **وقرارُ
    المالك (2026-09-02) أن تقيس ساعةَ التشغيل لا أن تفترض**: «فتقيس على
    الإنتاج ساعةَ الترقية بدل أن نقيس اليوم بمفتاحٍ لا يعمل».

    **وهذا الاختبارُ يزرع صفّاً ثمّ يشترط الوقوف**: بلاه تبقى الدعوى
    «ستقف إن وجدت» غيرَ مقيسة — وهي بعينها «خُضرةُ ما لم يُقَس».

    **ويُعيد القاعدةَ إلى الرأس مهما وقع**، كدورة الصعود والنزول فوقه:
    اختبارٌ يترك المخطَّطَ على `0067` يُسقط كلَّ ما بعده لأسبابٍ لا علاقةَ لها به.
    """
    config = alembic_config()
    seeded = False
    try:
        await asyncio.to_thread(command.downgrade, config, "0067")
        await engine.dispose()

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO privacy_policies "
                    "(id, country_code, version, body_ar, is_published, "
                    " requires_reconsent) "
                    "VALUES (gen_random_uuid(), 'JO', 1, 'نصٌّ كُتب بيد', "
                    " false, false)"
                )
            )
        seeded = True

        with pytest.raises(RuntimeError) as raised:
            await asyncio.to_thread(command.upgrade, config, "0068")

        # **ويُشترط نصُّها لا مجرّدُ الوقوف**: أيُّ عطبٍ آخرَ يرمي `RuntimeError`
        # أيضاً، **فوقوفٌ بلا اسمٍ يُقرأ حراسةً وهو صدفة**
        assert "0068 توقّفت" in str(raised.value)
        assert "privacy_policies=1" in str(raised.value)
    finally:
        if seeded:
            async with engine.begin() as conn:
                await conn.execute(text("DELETE FROM privacy_policies"))
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()
