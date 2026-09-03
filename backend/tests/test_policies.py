"""السياساتُ والشروط — **البند ١٠ (§39٫١٠، §34، §45)**.

**والجداولُ نامت منذ `0060` بلا قارئ**، فهذا أوّلُ ما يقيسها. وما يُختبر هنا
هو القواعدُ الأربعُ التي تجعل نصّاً قانونياً قابلاً للاعتماد عليه:

1. **كلُّ حفظٍ نسخةٌ جديدة، ولا تحريرَ فوق نفسه** — والرقمُ يتصاعد ولا يُعاد.
2. **والمنشورةُ واحدةٌ لكلِّ (سوق + نوع + تطبيق)** — والنشرُ ينزع سابقَه،
   **ونشرُ الشروط لا يُطفئ الخصوصية** (العطبُ الذي سدّته `0068`).
3. **و`min_accepted_version` بمعادلته**، ومقيسةٌ في الاتجاهين: تُرفع حين
   يُطلب القبولُ ثانيةً، **وتبقى حين لا يُطلب**.
4. **ولا يُمحى نصٌّ وافق عليه أحد** — ولا نصٌّ منشور.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.models.privacy import OrgProfile, PrivacyPolicy, UserPolicyConsent
from app.models.user import User

BODY = "هذه مسوّدةُ نصٍّ للقياس، وفيها فقرةٌ واحدة."


def _body(**overrides: Any) -> dict:
    return {
        "country_code": "JO",
        "doc_type": "privacy_policy",
        "app": "rider",
        "body_ar": BODY,
        "requires_reconsent": False,
        **overrides,
    }


async def _create(client: AsyncClient, headers: dict, **overrides: Any):
    return await client.post("/admin/policies", json=_body(**overrides), headers=headers)


async def _publish(client: AsyncClient, headers: dict, policy_id: str):
    return await client.post(f"/admin/policies/{policy_id}/publish", headers=headers)


# ------------------------------------------------------- النسخةُ لا التحرير


async def test_every_save_is_a_new_version_and_the_number_climbs(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**ولا يُحرَّر صفٌّ فوق نفسه** — فتصحيحُ فاصلةٍ لا يغيّر ما وافقوا عليه."""
    first = await _create(client, admin_headers)
    assert first.status_code == 201, first.text
    assert first.json()["version"] == 1
    assert first.json()["is_published"] is False, "تولد مسوّدةً، والنشرُ فعلٌ ثانٍ"

    second = await _create(client, admin_headers, body_ar=BODY + " وفاصلة.")
    assert second.json()["version"] == 2

    # **ولا بابَ تعديلٍ أصلاً** — والعقدُ يقولها بغياب الفعل لا بتعليق
    patched = await client.patch(
        f"/admin/policies/{first.json()['id']}",
        json={"body_ar": "نصٌّ آخر"},
        headers=admin_headers,
    )
    assert patched.status_code == 405, patched.text


async def test_a_deleted_draft_gives_its_number_back(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**والرقمُ يعود بعد حذف مسوّدة — وهو مقصودٌ لا سهو**.

    **ولا قارئَ رأى ذلك الرقمَ قطّ**: المسوّدةُ لا تُنشر، **ولا تُحذف واحدةٌ
    وافق عليها أحد** (شرطان مفروضان في الخدمة والقاعدة). فـ«النسخة ٢» لم تصل
    إنساناً، **والتدقيقُ يفرّق الصفّين بمعرّفهما** لا برقمهما.

    **وحفظُ الرقم كان يحتاج عدّاداً ثانياً** — بيتاً ثانياً للحقيقة يفترق عن
    الجدول أوّلَ حذفٍ يدويّ، **ثمناً لِما لا يراه أحد**.
    """
    await _create(client, admin_headers)
    second = await _create(client, admin_headers)
    assert (
        await client.delete(
            f"/admin/policies/{second.json()['id']}", headers=admin_headers
        )
    ).status_code == 204

    third = await _create(client, admin_headers)
    assert third.json()["version"] == 2


# ------------------------------------------------------------ النشرُ والنزع


async def test_publishing_pulls_the_previous_one_down(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**منشورةٌ واحدةٌ لكلِّ ثلاثيّة** — والفهرسُ يحرسها، والنزعُ في المعاملة نفسِها."""
    first = await _create(client, admin_headers)
    assert (await _publish(client, admin_headers, first.json()["id"])).status_code == 200

    second = await _create(client, admin_headers)
    published = await _publish(client, admin_headers, second.json()["id"])
    assert published.status_code == 200, published.text
    assert published.json()["is_published"] is True
    assert published.json()["published_at"] is not None

    async with session_factory() as session:
        live = (
            await session.scalars(
                select(PrivacyPolicy).where(PrivacyPolicy.is_published.is_(True))
            )
        ).all()
    assert [row.version for row in live] == [2]


async def test_publishing_terms_does_not_pull_privacy_down(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**العطبُ الذي سدّته `0068`**: كان الفهرسُ على السوق وحدَه، **فنشرُ
    الشروط يُطفئ سياسةَ الخصوصية في السوق نفسِه صامتاً**."""
    privacy = await _create(client, admin_headers, doc_type="privacy_policy")
    await _publish(client, admin_headers, privacy.json()["id"])
    terms = await _create(client, admin_headers, doc_type="terms_of_use")
    await _publish(client, admin_headers, terms.json()["id"])

    listed = await client.get("/admin/policies", headers=admin_headers)
    live = {row["doc_type"] for row in listed.json() if row["is_published"]}
    assert live == {"privacy_policy", "terms_of_use"}


async def test_an_older_text_is_not_published_over_a_newer_one(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**ولا يُنشر نصٌّ أقدمُ فوق أحدث** — والرفضُ بالعربية لا برسالة قاعدة."""
    first = await _create(client, admin_headers)
    second = await _create(client, admin_headers)
    await _publish(client, admin_headers, second.json()["id"])

    refused = await _publish(client, admin_headers, first.json()["id"])
    assert refused.status_code == 409, refused.text


# ---------------------------------------------- «أدنى نسخةٍ تُبرئ» بمعادلتها


async def test_min_accepted_climbs_only_when_consent_is_asked_again(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**المعادلةُ بنصّها** (§34): `requires_reconsent` ? نسخةُ الصفّ : قيمةُ
    المنشورةِ التي قبله. **ومقيسةٌ في الاتجاهين** — فعمودٌ يرتفع دائماً يسأل
    الناسَ عن كلِّ فاصلة، وعمودٌ لا يرتفع أبداً يجعل الموافقةَ دعوى."""
    first = await _create(client, admin_headers)
    assert first.json()["min_accepted_version"] == 1, "أوّلُ وثيقةٍ تُبرئ نفسَها"
    await _publish(client, admin_headers, first.json()["id"])

    # تصحيحُ فاصلة — لا يُسأل أحدٌ ثانيةً
    second = await _create(client, admin_headers, requires_reconsent=False)
    assert second.json()["version"] == 2
    assert second.json()["min_accepted_version"] == 1
    await _publish(client, admin_headers, second.json()["id"])

    # تغييرٌ جوهريّ — يُسأل
    third = await _create(client, admin_headers, requires_reconsent=True)
    assert third.json()["min_accepted_version"] == 3


async def test_min_accepted_version_has_exactly_one_writer(
    client: AsyncClient,
) -> None:
    """**شرطُ §34 مقيساً لا موصوفاً**: «ولا كاتبَ ثانيَ له، ويسقط الاختبارُ
    يومَ يُضاف بابٌ يكتب ولا يُحدِّثه».

    **ويُمسح بمُحلِّل بايثون لا بنصّ**: `grep` يعدّ التعليقاتِ والسلاسلَ
    إسناداً، **وحارسٌ يكذب في اتجاهٍ واحدٍ يُطمأنّ إليه**.
    """
    root = Path(__file__).resolve().parents[1] / "app"
    writers: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == "min_accepted_version"
                ):
                    writers.append(f"{path.name}:{target.lineno}")
            # **`PrivacyPolicy(min_accepted_version=…)` كتابةٌ كذلك** — والفحصُ
            # على **بانِي النموذج وحدَه**: مخطَّطُ الخَرج يحمل الاسمَ نفسَه وهو
            # قراءةٌ لا كتابة، **وحارسٌ يخلطهما يصيح على السليم فيُطفأ**
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "PrivacyPolicy"
            ):
                for keyword in node.keywords:
                    if keyword.arg == "min_accepted_version":
                        writers.append(f"{path.name}:{node.lineno}")

    assert sorted(set(name.split(":")[0] for name in writers)) == ["policies.py"], (
        f"كاتبٌ ثانٍ لـ`min_accepted_version`: {writers}"
    )


# --------------------------------------------------- ما لا يُمحى، ومن يكتب


async def test_a_published_text_is_never_deleted(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**نصٌّ وافق عليه إنسانٌ لا يُمحى** (§39٫٤) — والمنشورُ منه أولى."""
    first = await _create(client, admin_headers)
    await _publish(client, admin_headers, first.json()["id"])
    refused = await client.delete(
        f"/admin/policies/{first.json()['id']}", headers=admin_headers
    )
    assert refused.status_code == 422, refused.text


async def test_a_text_someone_accepted_is_never_deleted(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**والقاعدةُ تمنعه بـ`RESTRICT`** — والرفضُ هنا يقول السببَ بالعربية."""
    first = await _create(client, admin_headers)
    policy_id = first.json()["id"]

    async with session_factory() as session:
        someone = await session.scalar(select(User).limit(1))
        session.add(
            UserPolicyConsent(user_id=someone.id, policy_id=uuid.UUID(policy_id))
        )
        await session.commit()

    refused = await client.delete(f"/admin/policies/{policy_id}", headers=admin_headers)
    assert refused.status_code == 422, refused.text
    assert "وافق" in refused.json()["message"]


async def test_support_reads_and_does_not_write(
    client: AsyncClient, support_headers: dict
) -> None:
    """قراءةٌ للدعم — **والنشرُ لصاحب `settings.write`**."""
    assert (
        await client.get("/admin/policies", headers=support_headers)
    ).status_code == 200
    refused = await _create(client, support_headers)
    assert refused.status_code == 403, refused.text


async def test_the_org_profile_is_one_row_and_empty_is_fine(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**صفٌّ واحدٌ لا صفٌّ لكلِّ سوق**، **وفراغُه حالٌ صحيحةٌ لا خطأ**."""
    empty = await client.get("/admin/policies/org", headers=admin_headers)
    assert empty.status_code == 200
    assert empty.json()["legal_name"] is None

    for name in ("تاكسي تجورا", "تجورا للنقل"):
        saved = await client.put(
            "/admin/policies/org",
            json={"legal_name": name, "privacy_email": "privacy@tajora.ly"},
            headers=admin_headers,
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["legal_name"] == name

    async with session_factory() as session:
        rows = (await session.scalars(select(OrgProfile))).all()
    assert len(rows) == 1, "صفٌّ واحدٌ مهما تكرّر الحفظ"


async def test_publishing_can_be_withdrawn(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**بابُ الرجوع شرطٌ لا ترف**: حالٌ تُدخَل ولا يُخرج منها «بابٌ بلا زرّ في
    اتجاهٍ واحد» — وهي قاعدةٌ مكتوبةٌ في هذا المستودع عن مفتاحٍ بُني ليوقف
    الأذى ولا يُطفأ.

    **ولا يُمحى شيء**: النصُّ باقٍ، **و`published_at` لا يُصفَّر** — «نُشرت
    يومَ كذا ثمّ سُحبت» خبرٌ، و«لم تُنشر قطّ» كذبٌ يمحو ما رآه الناس.
    """
    first = await _create(client, admin_headers)
    await _publish(client, admin_headers, first.json()["id"])

    pulled = await client.post(
        f"/admin/policies/{first.json()['id']}/withdraw", headers=admin_headers
    )
    assert pulled.status_code == 200, pulled.text
    assert pulled.json()["is_published"] is False
    assert pulled.json()["published_at"] is not None, "تاريخُ النشر الأول خبرٌ يبقى"
    assert pulled.json()["body_ar"] == BODY

    # **ولا وثيقةَ قائمةً الآن** — وهي حالٌ صحيحةٌ لا خطأ
    listed = await client.get("/admin/policies", headers=admin_headers)
    assert [row for row in listed.json() if row["is_published"]] == []

    # **ويُعاد نشرُها** — فالسحبُ ليس محواً
    again = await _publish(client, admin_headers, first.json()["id"])
    assert again.status_code == 200, again.text


async def test_withdrawing_a_draft_is_refused(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**ولا يُسحب ما لم يُنشر** — والرفضُ بالعربية."""
    first = await _create(client, admin_headers)
    refused = await client.post(
        f"/admin/policies/{first.json()['id']}/withdraw", headers=admin_headers
    )
    assert refused.status_code == 422, refused.text
