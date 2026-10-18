"""إعادةُ القبول — **قرارُ المالك ٢٠٢٦-١٠-١٨** (SPEC §٧٦-ع/٧ البند ٣).

**وما يُقاس هنا سبعُ قواعد:**

1. **من قبل نسخةً أقدمَ من «أدنى ما يُبرئ» يُسأل** — ومعه ما تغيّر **بلا سطر التاريخ**، و«أوافق» يكتب صفّاً بالنسخة وتاريخِها.
2. **وتصحيحٌ بلا إعادةِ قبولٍ لا يسأله ثانيةً** — `min_accepted_version` هو الحكم لا «أحدثُ رقم».
3. **ومن لم يقبل منها شيئاً قطُّ يُسأل** — وبلا «ما تغيّر» (`None` لا قائمةٌ فارغة).
4. **ونسخةٌ لم تعد المنشورة لا يُسجَّل قبولُها.**
5. **ولا قبولَ جزئيّ** — والناقصُ يُسمّى.
6. **وضغطتان معاً صفٌّ واحدٌ وجوابان سليمان** — لا `IntegrityError` في وجه من وافق.
7. **وتطبيقُ الكبتن لا يسأل راكباً.**
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import CountryCode, PolicyApp, PolicyDocType, UserRole
from app.models.privacy import PrivacyPolicy, UserPolicyConsent
from app.models.user import User
from app.services import policies as policies_service
from tests.helpers import RIDER, auth, register

OLD = "آخر تحديث: 2026-09-05. هذه مقدّمةُ السياسة.\n\n- لا نرسل اسمَك إلى مزوّد الدفع.\n\nفقرةٌ لا تتغيّر."
NEW = "آخر تحديث: 2026-10-18. هذه مقدّمةُ السياسة.\n\n- نشارك مزوّدَ الدفع اسمَك ورقمَ هاتفك.\n\nفقرةٌ لا تتغيّر."


async def _admin(session) -> User:
    user = User(
        name="مشرفُ القياس",
        phone=f"+96279{uuid.uuid4().int % 10**7:07d}",
        role=UserRole.ADMIN,
        country_code=CountryCode.JO,
        password_hash="x",
    )
    session.add(user)
    await session.flush()
    return user


async def _publish(
    session_factory,
    body: str,
    *,
    reconsent: bool,
    doc_type: PolicyDocType = PolicyDocType.PRIVACY_POLICY,
    app: PolicyApp = PolicyApp.RIDER,
) -> str:
    async with session_factory() as session:
        policy = await policies_service.create_version(
            session,
            country=CountryCode.JO,
            doc_type=doc_type,
            app=app,
            body_ar=body,
            body_en=None,
            requires_reconsent=reconsent,
        )
        await policies_service.publish(session, policy, actor=await _admin(session))
        await session.commit()
        return str(policy.id)


async def _rider(client: AsyncClient, accepted: list[str]) -> dict:
    return auth(await register(client, RIDER | {"accepted_policy_ids": accepted}))


async def _pending(client: AsyncClient, headers: dict, app: str = "rider") -> list[dict]:
    res = await client.get(f"/account/policies/pending?app={app}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["pending"]


async def _accept(client: AsyncClient, headers: dict, ids: list[str]):
    return await client.post("/account/policies/accept", json={"app": "rider", "policy_ids": ids}, headers=headers)


async def _consents(session_factory, policy_id: str) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(UserPolicyConsent).where(UserPolicyConsent.policy_id == uuid.UUID(policy_id))
        )


# ─────────────────────────────── ١ · نسخةٌ أقدمُ ← يُسأل، وما تغيّر بلا التاريخ، و«أوافق» يكتب


async def test_an_older_acceptance_is_asked_again_with_what_changed_and_agreeing_records_it(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    v1 = await _publish(session_factory, OLD, reconsent=False)
    headers = await _rider(client, [v1])
    assert await _pending(client, headers) == []

    v2 = await _publish(session_factory, NEW, reconsent=True)
    [doc] = await _pending(client, headers)
    assert doc["id"] == v2 and doc["version"] == 2 and doc["accepted_version"] == 1
    assert doc["accepted_at"] is not None and doc["body_ar"] == NEW
    # **السطرُ الذي تغيّر وحدَه** — سطرُ «آخر تحديث» تغيّر تاريخُه فقط فلا يُعدّ، والفقرةُ الثابتةُ لا تظهر
    assert doc["changes_ar"] == ["- نشارك مزوّدَ الدفع اسمَك ورقمَ هاتفك."]
    assert doc["changes_fr"] is None

    res = await _accept(client, headers, [v2])
    assert res.status_code == 200, res.text
    assert res.json()["pending"] == []
    assert await _pending(client, headers) == []

    async with session_factory() as session:
        row = await session.scalar(select(UserPolicyConsent).where(UserPolicyConsent.policy_id == uuid.UUID(v2)))
        policy = await session.get(PrivacyPolicy, row.policy_id)
    # **بتاريخه ونسخته**
    assert row.accepted_at is not None and policy.version == 2
    # **والقديمُ يبقى** — «وافق على الأولى يومَ كذا» خبرٌ لا يُمحى
    assert await _consents(session_factory, v1) == 1


# ─────────────────────────────── ٢ · تصحيحٌ بلا إعادةِ قبولٍ لا يسأله


async def test_a_correction_without_reconsent_does_not_ask_again(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    v1 = await _publish(session_factory, OLD, reconsent=False)
    headers = await _rider(client, [v1])
    await _publish(session_factory, OLD + "\n\nتصحيحُ فاصلة.", reconsent=False)
    assert await _pending(client, headers) == []

    # **وبعد إعادة قبولٍ، فتصحيحٍ بلا إعادة**: من قبل الثانيةَ برئ من الثالثة
    v2 = await _publish(session_factory, NEW, reconsent=True)
    assert [doc["id"] for doc in await _pending(client, headers)] == [v2]
    assert (await _accept(client, headers, [v2])).status_code == 200
    await _publish(session_factory, NEW + "\n\nتصحيحٌ ثانٍ.", reconsent=False)
    assert await _pending(client, headers) == []


# ─────────────────────────────── ٣ · من لم يقبل شيئاً قطُّ يُسأل، وبلا «ما تغيّر»


async def test_someone_who_never_accepted_is_asked_without_a_change_list(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    # **سجّل قبل أن تُنشر وثيقة** — كما سجّل كلُّ من سبق ٢٠٢٦-٠٩-٠٥
    headers = await _rider(client, [])
    v1 = await _publish(session_factory, OLD, reconsent=False)
    [doc] = await _pending(client, headers)
    assert doc["id"] == v1 and doc["accepted_version"] is None and doc["accepted_at"] is None
    assert doc["changes_ar"] is None
    assert (await _accept(client, headers, [v1])).status_code == 200
    assert await _pending(client, headers) == []


# ─────────────────────────────── ٤ · نسخةٌ لم تعد المنشورة لا يُسجَّل قبولُها


async def test_a_version_that_is_no_longer_published_is_not_recorded(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    v1 = await _publish(session_factory, OLD, reconsent=False)
    headers = await _rider(client, [v1])
    v2 = await _publish(session_factory, NEW, reconsent=True)
    # نُشرت الثالثةُ بين فتح الشاشة والضغط
    v3 = await _publish(session_factory, NEW + "\n\nإضافة.", reconsent=True)

    res = await _accept(client, headers, [v2])
    assert res.status_code == 422, res.text
    assert await _consents(session_factory, v2) == 0
    assert [doc["id"] for doc in await _pending(client, headers)] == [v3]


# ─────────────────────────────── ٥ · لا قبولَ جزئيّ


async def test_agreeing_to_one_of_two_is_refused_and_names_the_other(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    headers = await _rider(client, [])
    privacy = await _publish(session_factory, OLD, reconsent=False)
    terms = await _publish(session_factory, "شروط.", reconsent=False, doc_type=PolicyDocType.TERMS_OF_USE)
    assert {doc["id"] for doc in await _pending(client, headers)} == {privacy, terms}

    res = await _accept(client, headers, [privacy])
    assert res.status_code == 422, res.text
    assert "شروط الاستخدام" in res.json()["message"]
    assert await _consents(session_factory, privacy) == 0

    assert (await _accept(client, headers, [privacy, terms])).status_code == 200
    assert await _pending(client, headers) == []


# ─────────────────────────────── ٦ · ضغطتان معاً


async def test_two_taps_at_once_write_one_row_and_both_answer_cleanly(
    client: AsyncClient, session_factory, jordan_settings, monkeypatch
) -> None:
    v1 = await _publish(session_factory, OLD, reconsent=False)
    headers = await _rider(client, [v1])
    v2 = await _publish(session_factory, NEW, reconsent=True)

    # **تداخلٌ مرتَّبٌ لا مصادفة**: الضغطاتُ الثلاثُ تقرأ «ينتظر» كلُّها ثمّ تكتب معاً — **وبلا الحاجز تمرّ متتاليةً** فتخضرّ مع
    # «اسأل ثمّ اكتب» أيضاً (قِيس: خضراءُ على الشيفرة القديمة قبل الحاجز)
    barrier = asyncio.Barrier(3)
    original = policies_service.record_consent

    async def _together(*args, **kwargs):
        await barrier.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(policies_service, "record_consent", _together)

    responses = await asyncio.wait_for(
        asyncio.gather(*(_accept(client, headers, [v2]) for _ in range(3))), timeout=30
    )
    # **ثلاثُ ضغطاتٍ ثلاثةُ أجوبةٍ سليمة** — و«اسأل ثمّ اكتب» كان يُسقط ما بعد الأولى بخطأ قاعدة
    assert Counter(r.status_code for r in responses) == Counter({200: 3}), [r.text for r in responses]
    assert await _consents(session_factory, v2) == 1


# ─────────────────────────────── ٧ · تطبيقُ الكبتن لا يسأل راكباً


async def test_the_captain_app_does_not_ask_a_rider(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    headers = await _rider(client, [])
    await _publish(session_factory, "خصوصيةُ الكبتن.", reconsent=True, app=PolicyApp.DRIVER)
    assert await _pending(client, headers, app="driver") == []
    assert await _pending(client, headers, app="rider") == []


def test_changed_lines_ignore_a_date_only_change_and_say_none_without_a_base() -> None:
    assert policies_service.changed_lines(OLD, NEW) == ["- نشارك مزوّدَ الدفع اسمَك ورقمَ هاتفك."]
    assert policies_service.changed_lines(OLD, OLD.replace("2026-09-05", "2026-10-18")) == []
    assert policies_service.changed_lines(None, NEW) is None
    assert policies_service.changed_lines(OLD, None) is None
