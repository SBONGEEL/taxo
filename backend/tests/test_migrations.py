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


async def test_0102_downgrade_does_not_widen_an_admin() -> None:
    """**النزولُ لا يوسّع أحداً** (قِيس ٢٠٢٦-١٠-٠٨): مشرفٌ كلُّ صفوفه من صلاحيتَي `0102` كان يصير بالحذف **بلا صفّ** — والغيابُ
    «افتراضُ الدور»، **وافتراضُ `admin` قبلها الكلّ**. فمن مُنح قراءةَ المحادثات وحدَها كان سيعود مشرفاً كاملاً بنزول ترحيلة.

    **ويُشترط الوجهان**: من لم يبقَ له شيءٌ يُكتب له `read.only` وحدَه، **ومن بقي له صفٌّ آخرُ لا يُزاد عليه شيء**.
    """
    from app.core.security import hash_password
    from app.models.admin_permission import AdminPermissionGrant
    from app.models.enums import AdminPermission, CountryCode, UserRole
    from app.models.user import User
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        only_sensitive = User(
            phone="+962790000061", name="قارئ المحادثات وحدَها", role=UserRole.ADMIN,
            country_code=CountryCode.JO, password_hash=hash_password("StaffSecret123"),
        )
        mixed = User(
            phone="+962790000062", name="مشرفٌ بصفوفٍ أخرى", role=UserRole.ADMIN,
            country_code=CountryCode.JO, password_hash=hash_password("StaffSecret123"),
        )
        session.add_all([only_sensitive, mixed])
        await session.flush()
        session.add_all(
            [
                AdminPermissionGrant(user_id=only_sensitive.id, permission=AdminPermission.TRIP_CHATS_READ),
                AdminPermissionGrant(user_id=only_sensitive.id, permission=AdminPermission.CALL_RECORDINGS_LISTEN),
                AdminPermissionGrant(user_id=mixed.id, permission=AdminPermission.TRIP_CHATS_READ),
                AdminPermissionGrant(user_id=mixed.id, permission=AdminPermission.SETTINGS_WRITE),
            ]
        )
        await session.commit()
        ids = {"only": only_sensitive.id, "mixed": mixed.id}
    await engine.dispose()

    config = alembic_config()
    try:
        await asyncio.to_thread(command.downgrade, config, "0100")
        await engine.dispose()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(text("SELECT user_id, permission::text FROM admin_permissions"))
            ).all()
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()

    held: dict[str, set[str]] = {}
    for user_id, permission in rows:
        held.setdefault(str(user_id), set()).add(permission)
    assert held == {str(ids["only"]): {"read.only"}, str(ids["mixed"]): {"settings.write"}}


async def test_0103_downgrade_does_not_widen_an_admin() -> None:
    """**نزولُ `0103` لا يوسّع أحداً** — قاعدةُ `0102` حرفاً: من كانت «الملخّصاتُ المالية» صلاحيتَه الوحيدةَ يُكتب له `read.only`،
    **وإلا صار بلا صفوفٍ فقُرئ افتراضَ دوره — وافتراضُ `admin` كلُّ ما ليس حسّاساً**. **ومن له صفٌّ آخرُ معها لا يُزاد عليه شيء.**"""
    from app.core.security import hash_password
    from app.models.admin_permission import AdminPermissionGrant
    from app.models.enums import AdminPermission, CountryCode, UserRole
    from app.models.user import User
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        only_summary = User(
            phone="+962790000063", name="قارئ الملخّصات وحدَها", role=UserRole.ADMIN,
            country_code=CountryCode.JO, password_hash=hash_password("StaffSecret123"),
        )
        mixed = User(
            phone="+962790000064", name="مشرفٌ بصفوفٍ أخرى", role=UserRole.ADMIN,
            country_code=CountryCode.JO, password_hash=hash_password("StaffSecret123"),
        )
        session.add_all([only_summary, mixed])
        await session.flush()
        session.add_all(
            [
                AdminPermissionGrant(user_id=only_summary.id, permission=AdminPermission.FINANCE_SUMMARY_READ),
                AdminPermissionGrant(user_id=mixed.id, permission=AdminPermission.FINANCE_SUMMARY_READ),
                AdminPermissionGrant(user_id=mixed.id, permission=AdminPermission.FINANCE_MANAGE),
            ]
        )
        await session.commit()
        ids = {"only": only_summary.id, "mixed": mixed.id}
    await engine.dispose()

    config = alembic_config()
    try:
        await asyncio.to_thread(command.downgrade, config, "0102")
        await engine.dispose()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(text("SELECT user_id, permission::text FROM admin_permissions"))
            ).all()
            members = set(
                (await conn.execute(text("SELECT unnest(enum_range(NULL::admin_permission))::text"))).scalars().all()
            )
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()

    assert "finance.summary" not in members
    held: dict[str, set[str]] = {}
    for user_id, permission in rows:
        held.setdefault(str(user_id), set()).add(permission)
    assert held == {str(ids["only"]): {"read.only"}, str(ids["mixed"]): {"finance.manage"}}


async def test_0111_hides_algeria_the_moment_it_exists() -> None:
    """**الإخفاءُ يولد مع السوق** (SPEC §٧٣-ج/١): الترحيلةُ نفسُها تكتب `country_visible = false` للجزائر — لأن «السكوتُ ظهور»
    (§٢٤)، والإنتاجُ لا يُبذر في الرفع. **ويُقاس بالنزول والصعود** لا بقراءة الملفّ: صفٌّ تكتبه الترحيلةُ يوجد بعدها أو لا يوجد."""
    config = alembic_config()
    try:
        await asyncio.to_thread(command.downgrade, config, "0110")
        await engine.dispose()
        async with engine.connect() as conn:
            before = (
                await conn.execute(
                    text("SELECT count(*) FROM feature_flags WHERE country_code::text = 'DZ'")
                )
            ).scalar_one()
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT feature_key, enabled FROM feature_flags WHERE country_code::text = 'DZ'"
                    )
                )
            ).all()
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()

    assert before == 0
    assert [tuple(row) for row in rows] == [("country_visible", False)]


async def test_0111_downgrade_stops_while_algeria_holds_data() -> None:
    """**نزولٌ يترك بياناتٍ بقيمةٍ لم تعد الشيفرةُ تعرفها أسوأُ من نزولٍ يقف** (درسُ `0104`) — فيُزرع صفٌّ جزائريٌّ غيرُ صفِّ
    الإخفاء ويُشترط الوقوفُ **بنصِّه**، ثمّ يُزال فيمرّ النزول."""
    config = alembic_config()
    seeded = False
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO feature_flags (id, country_code, feature_key, enabled, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), 'DZ', 'tips_enabled', false, now(), now())"
                )
            )
        seeded = True
        with pytest.raises(Exception) as raised:
            await asyncio.to_thread(command.downgrade, config, "0110")
        assert "0111" in str(raised.value) and "feature_flags" in str(raised.value)
    finally:
        if seeded:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM feature_flags WHERE country_code::text = 'DZ' AND feature_key = 'tips_enabled'")
                )
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()


async def test_0117_downgrade_stops_while_an_ios_release_exists() -> None:
    """**نزولٌ لا يحذف صفّاً** (2026-10-12): صفُّ iOS لا مكانَ له في جدولٍ بلا نظام — **فيقف النزولُ بنصِّه**، ثمّ يُزال الصفُّ
    فيمرّ النزولُ والصعودُ، **وصفُّ أندرويد يعود أندرويد**."""
    config = alembic_config()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO app_releases (id, app, platform, build, min_supported_build, download_url, release_notes) "
                    "VALUES (gen_random_uuid(), 'rider', 'ios', 10, 10, 'https://example.com/ios', 'ios'), "
                    "(gen_random_uuid(), 'rider', 'android', 772, 772, 'https://taxo.tajora.ly/download', 'android')"
                )
            )
        with pytest.raises(Exception) as raised:
            await asyncio.to_thread(command.downgrade, config, "0116")
        assert "iOS" in str(raised.value)

        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app_releases WHERE platform = 'ios'"))
        await asyncio.to_thread(command.downgrade, config, "0116")
        await asyncio.to_thread(command.upgrade, config, "head")
        async with engine.begin() as conn:
            rows = (
                await conn.execute(text("SELECT platform::text, build FROM app_releases"))
            ).all()
        assert [tuple(row) for row in rows] == [("android", 772)]
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app_releases"))
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()


async def test_0118_downgrade_keeps_the_owners_written_decisions_and_widens_no_one() -> None:
    """**نزولُ `0118` يقف على قرارٍ مكتوب** (SPEC §٧٤): سماحُ الحدود صفٌّ كتبه المالك ولا يُمحى بنزول — **فيقف بنصِّه**؛ ثمّ يُزال
    فيمرّ، **ومن كانت «الدولُ والحدود» صلاحيتَه الوحيدةَ يُكتب له `read.only`** (قاعدةُ `0103`) فلا يتّسع بالنزول."""
    from app.core.security import hash_password
    from app.models.admin_permission import AdminPermissionGrant
    from app.models.enums import AdminPermission, CountryCode, UserRole
    from app.models.user import User
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        owner = User(
            phone="+962790000083", name="مالكُ الدول وحدَها", role=UserRole.ADMIN,
            country_code=CountryCode.JO, password_hash=hash_password("StaffSecret123"),
        )
        session.add(owner)
        await session.flush()
        session.add(AdminPermissionGrant(user_id=owner.id, permission=AdminPermission.MARKETS_MANAGE))
        await session.commit()
        owner_id = owner.id
    await engine.dispose()

    config = alembic_config()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO border_allowances (id, user_id, reason) VALUES (gen_random_uuid(), :user, 'حسابُ تجربة')"
                ),
                {"user": owner_id},
            )
        with pytest.raises(Exception) as raised:
            await asyncio.to_thread(command.downgrade, config, "0117")
        assert "«الدول»" in str(raised.value)

        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM border_allowances"))
        await asyncio.to_thread(command.downgrade, config, "0117")
        await engine.dispose()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text("SELECT permission::text FROM admin_permissions WHERE user_id = :user"), {"user": owner_id}
                )
            ).scalars().all()
            members = set(
                (await conn.execute(text("SELECT unnest(enum_range(NULL::admin_permission))::text"))).scalars().all()
            )
            tables = set(
                (await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))).scalars().all()
            )
        assert rows == ["read.only"]
        assert "markets.manage" not in members
        assert not {"country_markets", "market_borders", "border_allowances"} & tables
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM admin_permissions"))
        await asyncio.to_thread(command.upgrade, config, "head")
        await engine.dispose()
