"""مسوّداتُ سياسات الجزائر وشروطها (SPEC §٧٣-هـ المرحلة ٧) — **تُكتب غيرَ منشورة، وبنصِّها هي، والأردنُ كما كان**.

**ما يُقاس**: البذرُ يكتب للجزائر أربعَ وثائقَ غيرَ منشورة · نصُّها لا يذكر كليك ويذكر طرقَ الجزائر والدينارَ بلا كسور · **وكلُّ وثيقةٍ تحمل
وسمَ «يحتاج مراجعة قانونية»** فلا تُنشر بلا محامٍ ويُرى ذلك · الأردنُ بنصِّه (كليك فيه كما كان) · وبذرٌ ثانٍ لا يكتب شيئاً.
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.enums import CountryCode
from app.models.privacy import PrivacyPolicy
from scripts import seed_policies


async def test_algeria_gets_its_own_unpublished_drafts_and_jordan_keeps_its_text(session_factory) -> None:
    async with session_factory() as session:
        written = await seed_policies.seed_policy_drafts(session)
        await session.commit()
    assert written == 8
    async with session_factory() as session:
        rows = list(await session.scalars(select(PrivacyPolicy)))
    assert not any(row.is_published for row in rows)
    algeria = [row for row in rows if row.country_code is CountryCode.DZ]
    jordan = [row for row in rows if row.country_code is CountryCode.JO]
    assert len(algeria) == len(jordan) == 4
    for row in algeria:
        assert "كليك" not in row.body_ar and "CliQ" not in row.body_ar
        assert "يحتاج مراجعة قانونية" in row.body_ar
        assert "مسوّدة" in row.body_ar.splitlines()[0]
        assert not any(ch in "٠١٢٣٤٥٦٧٨٩" for ch in row.body_ar)
    joined = "\n".join(row.body_ar for row in algeria)
    for phrase in ("بريدي موب", "CCP", "بلا كسور", "Chargily", "بطاقة TAXO", "18-07"):
        assert phrase in joined, phrase
    # **الأردنُ بنصِّه كما كان حرفاً** — وكليك فيه
    by_type = {(row.doc_type, row.app): row.body_ar for row in jordan}
    for doc_type, app, body in seed_policies.DRAFTS:
        assert by_type[(doc_type, app)] == body.strip() + "\n"


async def test_a_second_seed_writes_nothing(session_factory) -> None:
    async with session_factory() as session:
        await seed_policies.seed_policy_drafts(session)
        await session.commit()
    async with session_factory() as session:
        assert await seed_policies.seed_policy_drafts(session) == 0
