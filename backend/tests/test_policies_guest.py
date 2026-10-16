"""فقرةُ «وضع الضيف» في سياسة الخصوصية (SPEC §٧٦-ن/٧) — **نسخةٌ جديدةٌ فوق المنشورة بكلِّ لغاتها، والسابقةُ مؤرشفة، ومرّةً واحدة**."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.enums import CountryCode, PolicyApp, PolicyDocType
from app.models.privacy import PrivacyPolicy
from app.services import policies as policies_service
from scripts import policies_guest as script

pytestmark = pytest.mark.asyncio


def test_the_section_has_no_indic_digits_and_says_thirty_days() -> None:
    for lang, text in script.SECTION.items():
        assert not any(ch in "٠١٢٣٤٥٦٧٨٩" for ch in text), lang
        assert "30" in text, lang
    assert script.MARKER in script.SECTION["ar"]


async def test_the_section_is_published_once_over_the_live_text(session_factory) -> None:
    async with session_factory() as session:
        old = await policies_service.create_version(
            session,
            country=CountryCode.DZ,
            doc_type=PolicyDocType.PRIVACY_POLICY,
            app=PolicyApp.DRIVER,
            body_ar="سياسةٌ قائمة",
            body_en="Live policy",
            body_fr="Politique en vigueur",
            requires_reconsent=False,
        )
        await policies_service.publish(session, old, actor=None)
        await session.commit()

    lines = await script.main_async(write=True, session_factory=session_factory)
    assert any(line.startswith("DZ/driver/privacy_policy: v2 تُنشر (ar · en · fr)") for line in lines), lines

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(PrivacyPolicy)
                .where(PrivacyPolicy.country_code == CountryCode.DZ, PrivacyPolicy.app == PolicyApp.DRIVER)
                .order_by(PrivacyPolicy.version)
            )
        ).all()
    assert [r.version for r in rows] == [1, 2]
    assert rows[0].is_published is False and rows[0].body_ar == "سياسةٌ قائمة"
    live = rows[1]
    assert live.is_published and live.requires_reconsent is False
    assert live.body_ar.startswith("سياسةٌ قائمة") and script.MARKER in live.body_ar
    assert "Guest mode" in live.body_en and "Mode invité" in live.body_fr

    # **ومرّةً واحدة** — الثانيةُ لا تكتب
    again = await script.main_async(write=True, session_factory=session_factory)
    assert any("فيها الفقرةُ أصلاً" in line for line in again)
