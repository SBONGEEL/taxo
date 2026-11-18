"""**كلُّ إعدادٍ لكلِّ دولة** (أمرُ المالك ٢٠٢٦-١١-١٨ الثاني، «عمولةُ الجزائر») — `app/services/country_settings.py`.

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**

١) **كلُّ جدولِ إعدادٍ واحدٍ لكلِّ دولةٍ محصيٌّ** — في `FALLBACKS` أو `DECLARED` بعلّته. جدولٌ جديدٌ مفتاحُه الفريدُ `country_code` وحدَه
   **يُسقط هذا** حتى يُقال كيف تراه الدولةُ الجديدة.
٢) **الصفُّ المصنوعُ يُقرأ كالغياب حقلاً حقلاً** — بخدمة كلِّ جدولٍ نفسِها. فعرضُه في اللوحة يقول ما يسري، وكتابتُه لا تغيّر شيئاً.
٣) **كلُّ بابٍ في اللوحة يُرجع كلَّ دولة** — على قاعدةٍ فارغة. والعطبُ الذي بُني له: الجزائرُ بلا صفِّ عمولة، فلم تُرسم عمولتُها قطّ.
٤) **التحذيرُ عند الإقلاع يسمّي الناقص** — ويصمت حين لا ينقص شيء.
"""

from __future__ import annotations

import dataclasses
import logging

import pytest
from httpx import AsyncClient
from sqlalchemy import UniqueConstraint

from app.models.base import Base
from app.models.enums import CountryCode
from app.services import country_settings

pytestmark = pytest.mark.asyncio

DOORS = {
    "commission_settings": "/admin/settings/commission",
    "advance_settings": "/admin/settings/advances",
    "cancellation_settings": "/admin/settings/cancellation",
    "map_settings": "/admin/settings/map",
    "otp_settings": "/admin/settings/otp",
    "dispatch_settings": "/admin/settings/dispatch",
    "negotiation_settings": "/admin/settings/negotiation",
}


def _one_per_country(table) -> bool:
    """مفتاحُه الفريدُ (أوّليّاً أو قيداً أو فهرساً) `country_code` وحدَه."""
    if "country_code" not in table.columns:
        return False
    keys = [{c.name for c in table.primary_key.columns}]
    keys += [{c.name for c in con.columns} for con in table.constraints if isinstance(con, UniqueConstraint)]
    # **والفهرسُ الجزئيُّ ليس «صفّاً لكلِّ دولة»** — «حملةٌ نشطةٌ واحدةٌ لكلِّ دولة» بياناتٌ تُضاف لا إعداد
    keys += [
        {c.name for c in ix.columns}
        for ix in table.indexes
        if ix.unique and ix.dialect_options["postgresql"].get("where") is None
    ]
    keys += [{c.name} for c in table.columns if c.unique]
    return {"country_code"} in keys


def test_every_one_per_country_table_is_counted() -> None:
    tables = {name for name, table in Base.metadata.tables.items() if _one_per_country(table)}
    counted = set(country_settings.FALLBACKS) | set(country_settings.DECLARED)
    assert tables - counted == set(), "جدولُ إعدادٍ لكلِّ دولةٍ بلا صانعٍ ولا علّة — الدولةُ الجديدةُ لا يُعرف ما تراه فيه"
    assert counted - tables == set(), "اسمٌ محصيٌّ لا جدولَ له — بقيّةُ جدولٍ أُعيدت تسميتُه"


def _plain(value):
    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items() if k not in {"id", "created_at", "updated_at", "updated_by"}}
    if hasattr(value, "__table__"):
        return _plain({c.name: getattr(value, c.name) for c in value.__table__.columns})
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


async def _read(session, table: str, country: CountryCode):
    """**ما يقرؤه الخادمُ فعلاً** — بخدمة كلِّ جدولٍ نفسِها."""
    from app.services import advances, cancellation, dispatch_settings, map_settings, negotiation, otp_limits, settings_service

    if table == "commission_settings":
        return await settings_service.commission_percent_for(session, country)
    if table == "advance_settings":
        policy = dataclasses.asdict(await advances.policy_for(session, country))
        policy.pop("enabled", None)  # المفتاحُ لا الصفّ
        return policy
    if table == "cancellation_settings":
        return await cancellation.settings_for(session, country)
    if table == "otp_settings":
        return await otp_limits.policy_for(session, country)
    if table == "map_settings":
        return (await map_settings.limits_for(session, country), await map_settings.pickup_suggest_enabled(session, country))
    if table == "dispatch_settings":
        return await dispatch_settings.rules_for(session, country)
    if table == "negotiation_settings":
        return await negotiation.rules_for(session, country)
    raise AssertionError(f"لا قارئَ لـ{table} — أضِفه هنا مع صانعه")


def _dispatch_defaults_as_written(monkeypatch) -> None:
    # **قيمُ الإنتاج لا قيمُ الاختبار**: `conftest` يضغط `DEFAULTS` (مهلةُ ٢ ث) لسرعة التوزيع، وهي تحت حدِّ القاعدة (٣–١٢٠) —
    # فتُقرأ القيمُ المكتوبةُ في الوحدة من نسخةٍ طازجةٍ منها، لا من المرقَّعة
    import importlib.util

    from app.services import dispatch_settings

    spec = importlib.util.spec_from_file_location("_dispatch_settings_as_written", dispatch_settings.__file__)
    fresh = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = fresh  # `dataclass` يطلب وحدتَه في `sys.modules`
    try:
        spec.loader.exec_module(fresh)
    finally:
        sys.modules.pop(spec.name, None)
    monkeypatch.setattr(
        dispatch_settings, "DEFAULTS", dispatch_settings.DispatchRules(**dataclasses.asdict(fresh.DEFAULTS))
    )


@pytest.mark.parametrize("table", sorted(country_settings.FALLBACKS))
async def test_the_made_row_reads_exactly_as_its_absence(table: str, session_factory, monkeypatch) -> None:
    if table == "dispatch_settings":
        _dispatch_defaults_as_written(monkeypatch)
    country = CountryCode.DZ
    async with session_factory() as session:
        absent = _plain(await _read(session, table, country))
    _, make = country_settings.FALLBACKS[table]
    async with session_factory() as session:
        session.add(make(country))
        await session.commit()
    async with session_factory() as session:
        present = _plain(await _read(session, table, country))
    assert present == absent, f"{table}: الصفُّ المصنوعُ يُقرأ غيرَ غيابه — عرضُه في اللوحة يكذب، وكتابتُه تغيّر ما يسري"


@pytest.mark.parametrize("table", sorted(DOORS))
async def test_every_panel_door_returns_every_country(table: str, client: AsyncClient, admin_headers: dict) -> None:
    assert set(DOORS) == set(country_settings.FALLBACKS), "صانعٌ بلا بابٍ مقيس"
    answer = await client.get(DOORS[table], headers=admin_headers)
    assert answer.status_code == 200, answer.text
    assert sorted(row["country_code"] for row in answer.json()) == sorted(c.value for c in CountryCode), (
        "دولةٌ غائبةٌ عن شاشةٍ لكلِّ دولة — وهي عطبُ عمولة الجزائر بعينه"
    )


async def test_algeria_commission_is_shown_off_at_zero_and_saved_on_first_edit(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    rows = {row["country_code"]: row for row in (await client.get("/admin/settings/commission", headers=admin_headers)).json()}
    assert rows["DZ"]["commission_enabled"] is False and rows["DZ"]["commission_percent"] in {"0.00", "0"}
    async with session_factory() as session:
        from sqlalchemy import func, select

        from app.models.commission import CommissionSetting

        assert await session.scalar(select(func.count()).select_from(CommissionSetting)) == 0, "بابُ القراءة لا يكتب"


async def test_startup_names_what_is_missing_and_stays_quiet_otherwise(session_factory, caplog, monkeypatch) -> None:
    # **`fileConfig` في `alembic/env.py` يعطّل المسجِّلات القائمة** حين تبني التهيئةُ المخطّطَ في العمليّة نفسِها — وفي الإنتاج تعمل
    # الترحيلةُ في عمليّةٍ غيرِ الخادم، فلا يُعطَّل هناك
    monkeypatch.setattr(country_settings.log, "disabled", False)
    _dispatch_defaults_as_written(monkeypatch)
    caplog.set_level(logging.WARNING, logger=country_settings.log.name)
    # **مُعالِجُ الالتقاط على المسجِّل نفسِه** — إعدادُ السجلّ في التطبيق قد يقطع الصعودَ إلى الجذر
    country_settings.log.addHandler(caplog.handler)
    try:
        await country_settings.warn_on_startup(session_factory)
    finally:
        country_settings.log.removeHandler(caplog.handler)
    text = caplog.text
    assert "commission_settings" in text and "DZ" in text
    assert "payment_settings" in text, "ما لا افتراضَ له يُسمّى أعلى"

    async with session_factory() as session:
        for _, (_, make) in country_settings.FALLBACKS.items():
            for country in CountryCode:
                session.add(make(country))
        await session.commit()
    async with session_factory() as session:
        left = await country_settings.missing(session)
    assert set(left) <= set(country_settings._required()), "صفوفُ الصانع كُتبت ولا يزال الفحصُ يراها ناقصة"
