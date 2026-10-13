"""نشرُ سياسات الجزائر (SPEC §٧٤-ل/١) — **النصُّ كما صِيغ بلا وسم المسوّدة ولا ملاحظات المحامي، بالعربيّة والفرنسيّة، والأسطرُ الأربعةُ تخضرّ**."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import CountryCode
from app.models.privacy import PrivacyPolicy
from app.services import markets
from scripts import algeria_policies_74 as script

pytestmark = pytest.mark.asyncio


async def test_the_four_are_published_in_arabic_and_french_and_jordan_is_untouched(
    client: AsyncClient, session_factory
) -> None:
    async with session_factory() as session:
        before = [line for line in await markets.readiness(session, CountryCode.DZ) if "منشورة" in line]
    assert len(before) == 4
    assert len(script.LEGAL_NOTES) >= 10 and all(note.startswith("[يحتاج") for note in script.LEGAL_NOTES)

    preview = await script.main_async(write=False, session_factory=session_factory)
    assert len(preview) == 4
    await script.main_async(write=True, session_factory=session_factory)
    again = await script.main_async(write=True, session_factory=session_factory)
    assert all("لا يُمسّ" in line for line in again)

    async with session_factory() as session:
        rows = list(await session.scalars(select(PrivacyPolicy)))
        after = [line for line in await markets.readiness(session, CountryCode.DZ) if "منشورة" in line]
    assert after == []
    algeria = [row for row in rows if row.country_code is CountryCode.DZ]
    assert len(algeria) == 4 and all(row.is_published and row.published_by is None for row in algeria)
    assert not any(row.country_code is CountryCode.JO for row in rows)
    for row in algeria:
        assert "مسوّدة" not in row.body_ar and "يحتاج مراجعة" not in row.body_ar and "[" not in row.body_ar
        assert row.body_fr and "(Algérie)" in row.body_fr.splitlines()[0]
        assert not any(ch in "٠١٢٣٤٥٦٧٨٩" for ch in row.body_ar)
    terms = next(row for row in algeria if row.doc_type.value == "terms_of_use" and row.app.value == "rider")
    assert "تُتاح هذه الشروطُ والتطبيقُ بالعربية والفرنسية." in terms.body_ar

    required = await client.get("/public/policies/required", params={"country_code": "DZ", "app": "rider"})
    assert required.status_code == 200
    assert sorted(doc["doc_type"] for doc in required.json()) == ["privacy_policy", "terms_of_use"]
    assert all(doc["body_fr"] for doc in required.json())
