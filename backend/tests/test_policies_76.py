"""السياساتُ والشروطُ الكاملة (SPEC §٧٦/٣) — **كلُّ وثيقةٍ تُرسم بلا موضعٍ فارغ، وتُنشر نسخةً جديدةً والسابقةُ مؤرشفة، والإنجليزيُّ يصل الموقع**."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import CountryCode, PolicyApp, PolicyDocType
from app.models.privacy import PrivacyPolicy
from app.services import policies as policies_service
from app.services import trip_chat
from scripts import policies_76 as script
from scripts import policy_texts_76 as texts

pytestmark = pytest.mark.asyncio

ALL = [
    (country, lang, doc, app)
    for country, langs in script.MARKETS.items()
    for lang in langs
    for doc, app in script.DOCS
]


@pytest.mark.parametrize(("country", "lang", "doc", "app"), ALL)
def test_every_document_renders_whole(country, lang, doc, app) -> None:
    body = texts.render(doc=doc.value, app=app.value, country=country.value, lang=lang, date="2026-10-14")
    assert "{" not in body and "}" not in body
    assert texts.OPERATOR in body and texts.PRIVACY_EMAIL in body
    # **لا خاناتٍ عربيّةً هنديّة** — الأرقامُ لاتينيّةٌ في كلِّ نصٍّ معروض (GUARDS: «Latin digits everywhere»)
    assert not any(ch in "٠١٢٣٤٥٦٧٨٩" for ch in body)
    # **ولا سطرَ فارغاً داخل قائمة** — متغيّرٌ فارغٌ يُسقط سطرَه لا يتركه فراغاً
    assert "\n\n\n" not in body
    if doc is PolicyDocType.PRIVACY_POLICY:
        assert texts.DELETE_PAGE in body
    if doc is PolicyDocType.PRIVACY_POLICY and lang == "ar":
        # **عنوانا القسمين بحرفهما** — `policies.publish` يرفض سياسةً بلاهما ما دامت المحادثةُ أو المكالمةُ أو التسجيلُ مشتعلاً
        # (`trip_chat.require_line_kept`). **وقِيس ساقطاً ٢٠٢٦-١٠-١٤**: «ومكالماتُها» جمعاً و«تسجيلُ المكالمة» مفرداً مرّا هنا
        # وفي CI لأن مفاتيحَ قاعدة الاختبار مطفأة — **وردّهما نشرُ التطوير** حيث المحادثةُ مشتعلة
        assert trip_chat.CHAT_PRIVACY_MARKER in body
        assert trip_chat.RECORDING_PRIVACY_MARKER in body
    if app is PolicyApp.DRIVER and doc is PolicyDocType.PRIVACY_POLICY:
        # **بندُ موقع الخلفية** — ما يقرؤه مراجعُ Google قبل غيره
        marker = {"ar": "في الخلفية", "en": "background", "fr": "arrière-plan"}[lang]
        assert marker in body


async def test_publish_archives_the_old_version_and_asks_again(client: AsyncClient, session_factory) -> None:
    async with session_factory() as session:
        old = await policies_service.create_version(
            session,
            country=CountryCode.JO,
            doc_type=PolicyDocType.PRIVACY_POLICY,
            app=PolicyApp.RIDER,
            body_ar="نسخةٌ قديمة",
            body_en=None,
            requires_reconsent=False,
        )
        await policies_service.publish(session, old, actor=None)
        await session.commit()
        old_id = old.id

    preview = await script.main_async(write=False, session_factory=session_factory)
    assert len(preview) == 12
    async with session_factory() as session:
        assert len(list(await session.scalars(select(PrivacyPolicy)))) == 1  # المعاينةُ لا تكتب

    await script.main_async(write=True, session_factory=session_factory)
    again = await script.main_async(write=True, session_factory=session_factory)
    assert all("لا تُمسّ" in line for line in again)

    async with session_factory() as session:
        rows = list(await session.scalars(select(PrivacyPolicy)))
        archived = await session.get(PrivacyPolicy, old_id)
    assert len(rows) == 13
    assert archived is not None and not archived.is_published and archived.body_ar == "نسخةٌ قديمة"
    live = [row for row in rows if row.is_published]
    assert len(live) == 12
    assert all(row.requires_reconsent and row.body_en for row in live)
    assert all((row.body_fr is not None) == (row.country_code is CountryCode.DZ) for row in live)
    jordan = next(row for row in live if row.country_code is CountryCode.JO and row.app is PolicyApp.RIDER and row.doc_type is PolicyDocType.PRIVACY_POLICY)
    assert jordan.version == 2 and jordan.min_accepted_version == 2


async def test_the_public_page_door_returns_english(client: AsyncClient, session_factory, admin_headers) -> None:
    await script.main_async(write=True, session_factory=session_factory)
    from app.services import site as site_service

    async with session_factory() as session:
        row = await site_service.get_or_create(session)
        row.policies_public = True
        await session.commit()
    answer = await client.get("/public/policy", params={"doc_type": "privacy_policy", "app": "driver", "country": "LY"})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["country_code"] == "LY" and body["body_en"].startswith("Privacy Policy — TAXO Captain App in Libya")
    required = await client.get("/public/policies/required", params={"country_code": "DZ", "app": "rider"})
    assert all(doc["body_en"] and doc["body_fr"] for doc in required.json())
