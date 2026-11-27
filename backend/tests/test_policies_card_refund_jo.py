"""بندُ «لا استردادَ لاشتراكات البطاقة» في شروط كابتن الأردن (قرارُ المالك ٢٠٢٦-١١-٢٧) — **سطرٌ عاديٌّ آخرَ بنود القسم ٥ بلغات الوثيقة
الثلاث، ونسخةٌ جديدةٌ بلا إعادة موافقة، ومرّةً واحدة، والأردنُّ وحدَه**."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.enums import CountryCode, PolicyApp, PolicyDocType
from app.models.privacy import PrivacyPolicy
from app.services import policies as policies_service
from scripts import policies_card_refund_jo as script

pytestmark = pytest.mark.asyncio

AR = """شروطُ الكابتن
آخر تحديث: 2026-10-14

4) الأجرةُ والعمولة
- تحسب TAXO الأجرة.

5) الدفعُ ومحفظتُك
- الرحلةُ النقديّة: تقبض الأجرةَ بيدك.
- الدفعُ خارج التطبيق لتجاوز العمولة أو الرسوم ممنوع.

6) السُّلَف (حيث تتوفّر)
- قد تمنحك TAXO سلفة."""

EN = """Captain terms
Last updated: 2026-10-14

5) Payment and your wallet
- Cash rides: you collect the fare yourself.
- Payment outside the app to avoid commission or fees is not allowed.

6) Advances (where available)
- TAXO may grant you an advance."""

FR = """Conditions du capitaine
Dernière mise à jour : 2026-10-14

5) Paiement et portefeuille
- Courses en espèces : vous encaissez le prix vous-même.
- Le paiement hors de l'application pour éviter la commission est interdit.

6) Avances (lorsqu'elles sont disponibles)
- TAXO peut vous accorder une avance."""


async def _publish(session_factory, *, country: CountryCode, app: PolicyApp = PolicyApp.DRIVER) -> None:
    async with session_factory() as session:
        row = await policies_service.create_version(
            session, country=country, doc_type=PolicyDocType.TERMS_OF_USE, app=app,
            body_ar=AR, body_en=EN, body_fr=FR, requires_reconsent=False,
        )
        await policies_service.publish(session, row, actor=None)
        await session.commit()


async def _rows(session_factory, country: CountryCode, app: PolicyApp = PolicyApp.DRIVER) -> list[PrivacyPolicy]:
    async with session_factory() as session:
        return list((await session.scalars(
            select(PrivacyPolicy)
            .where(PrivacyPolicy.country_code == country, PrivacyPolicy.app == app, PrivacyPolicy.doc_type == PolicyDocType.TERMS_OF_USE)
            .order_by(PrivacyPolicy.version)
        )).all())


def test_the_clause_is_plain_and_has_no_indic_digits() -> None:
    for lang, text in script.CLAUSE.items():
        assert text.startswith("- ") and "\n" not in text, lang
        assert not any(ch in "٠١٢٣٤٥٦٧٨٩" for ch in text), lang


def test_the_clause_lands_last_in_section_five_and_nowhere_else() -> None:
    out = script.with_clause(AR, "ar")
    lines = out.split("\n")
    at = lines.index(script.CLAUSE["ar"])
    assert lines[at - 1] == "- الدفعُ خارج التطبيق لتجاوز العمولة أو الرسوم ممنوع."
    assert lines[at + 1] == "" and lines[at + 2].startswith("6) ")
    assert out.count(script.CLAUSE["ar"]) == 1 and "آخر تحديث: 2026-11-27" in out
    assert script.with_clause(EN, "en").split("\n")[6] == script.CLAUSE["en"]
    assert "Dernière mise à jour : 2026-11-27" in script.with_clause(FR, "fr")
    with pytest.raises(script.ClauseRefused):
        script.with_clause("نصٌّ بلا قسمِ دفع", "ar")


async def test_published_once_without_reconsent_and_only_for_jordan_captains(session_factory) -> None:
    await _publish(session_factory, country=CountryCode.JO)
    await _publish(session_factory, country=CountryCode.DZ)
    await _publish(session_factory, country=CountryCode.JO, app=PolicyApp.RIDER)

    preview = await script.main_async(write=False, session_factory=session_factory)
    assert preview[0].startswith("JO/driver/terms_of_use: v2 تُنشر (ar · en · fr)")
    assert [row.version for row in await _rows(session_factory, CountryCode.JO)] == [1]

    await script.main_async(write=True, session_factory=session_factory)
    rows = await _rows(session_factory, CountryCode.JO)
    assert [row.version for row in rows] == [1, 2]
    old, new = rows
    assert old.is_published is False and old.body_ar == AR
    assert new.is_published is True and new.requires_reconsent is False
    assert new.min_accepted_version == old.min_accepted_version
    assert script.CLAUSE["ar"] in new.body_ar and script.CLAUSE["en"] in new.body_en and script.CLAUSE["fr"] in new.body_fr

    # **ومرّةً واحدة**، **والجزائرُ وراكبُ الأردن لا يُمسّان**
    again = await script.main_async(write=True, session_factory=session_factory)
    assert "فيها البندُ أصلاً" in again[0]
    assert [row.version for row in await _rows(session_factory, CountryCode.JO)] == [1, 2]
    assert [row.version for row in await _rows(session_factory, CountryCode.DZ)] == [1]
    assert [row.version for row in await _rows(session_factory, CountryCode.JO, PolicyApp.RIDER)] == [1]


async def test_a_draft_above_the_live_text_stops_it(session_factory) -> None:
    await _publish(session_factory, country=CountryCode.JO)
    async with session_factory() as session:
        await policies_service.create_version(
            session, country=CountryCode.JO, doc_type=PolicyDocType.TERMS_OF_USE, app=PolicyApp.DRIVER,
            body_ar=AR + "\nمسوّدة", body_en=None, requires_reconsent=False,
        )
        await session.commit()
    with pytest.raises(script.ClauseRefused):
        await script.main_async(write=True, session_factory=session_factory)
    assert [row.version for row in await _rows(session_factory, CountryCode.JO)] == [1, 2]
