from __future__ import annotations

import asyncio

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, inspect

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
    assert revision == "0004"
    assert {
        "users",
        "drivers",
        "vehicles",
        "driver_documents",
        "pricing_rules",
        "feature_flags",
        "commission_settings",
        "subscription_plans",
        "provider_credentials",
        "admin_audit_logs",
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
