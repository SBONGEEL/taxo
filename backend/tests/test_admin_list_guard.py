"""حراسةُ القوائم الأربعِ بصلاحيةٍ مسمّاة — الفرع ٧ (§٤٧٫١٠، ٢٠٢٦-٠٩-٠٤).

**البندُ كان مفتوحاً بنصِّه**: «المصفوفةُ مبنيّةٌ منذ §41 وفيها `READ_ONLY`
و`USERS_MANAGE` و`FINANCE_MANAGE`، **ولا واحدةٌ منها تحرس قائمةً من هذه
الأربع** — يقرؤها `support` كما يقرؤها `admin`».

## وما يقيسه هذا الملفُّ شقّان لا شقّ

١. **أن شيئاً لم يتبدّل**: `admin` و`support` يقرآن الأربعَ والبحثَ كما كانا
   حرفاً — **وهذا هو الشرط**، فحراسةٌ تبدّل سلوكاً قائماً ليست تسميةَ حارس.
٢. **وأن الحارسَ يقع فعلاً**: مشرفٌ مُنح صفوفاً **لا `read.only` فيها**
   يُردّ ٤٠٣ عن الأربعِ وعن البحث. **ولا يُقاس هذا على من لا صفَّ له** —
   الغيابُ «افتراضُ الدور» لا «ممنوع»، **فاختبارٌ عليه يخضرّ والحارسُ غائب**.

**والثاني هو الاختبار**: قبل اليوم كان يسقط، لأن `StaffUser` لا يسأل عن
صلاحية. **وهو الفرقُ الذي يجعل المصفوفةَ تحكم أبواباً لا جدولاً في شاشة.**
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("jordan_settings")

#: القوائمُ الأربعُ ومعها البابُ الذي يلخّصها — **حارسُهنّ واحد**
GUARDED = [
    "/admin/users",
    "/admin/drivers",
    "/admin/rides",
    "/admin/topups",
    "/admin/search?q=قياس",
]


async def test_the_named_guard_changes_no_answer_on_its_first_day(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    """**الدورانِ يملكان `read.only`**، فالأربعُ والبحثُ يُقرأن كما كانا."""
    for path in GUARDED:
        for who, headers in (("admin", admin_headers), ("support", support_headers)):
            answer = await client.get(path, headers=headers)
            assert answer.status_code == 200, f"{who} · {path} · {answer.text}"


async def test_stripping_read_only_closes_all_five(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    """**وبالنقض**: مجموعةٌ ممنوحةٌ بلا `read.only` تُغلق الخمسةَ جميعاً.

    **ولا تُقاس بحسابٍ بلا صفوف**: من لا صفَّ له يُقرأ بافتراض دوره وفيه
    `read.only` — **فيمرّ، والحارسُ لم يُسأل**.

    **و`payments.resolve` تبقى ممنوحةً** كي يُقاس المنعُ على القراءة وحدَها:
    حسابٌ نُزعت عنه كلُّ صلاحياته يُردّ عن كلِّ شيء، **وذلك لا يقول أيُّ
    صلاحيةٍ حرست أيَّ باب**.
    """
    listed = await client.get("/admin/permissions", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    support = next(row for row in listed.json() if "support" in row["roles"])

    # **قبل النزع: الخمسةُ مفتوحة**
    for path in GUARDED:
        assert (
            await client.get(path, headers=support_headers)
        ).status_code == 200, path

    stripped = await client.put(
        f"/admin/permissions/{support['user_id']}",
        json={"permissions": ["payments.resolve"]},
        headers=admin_headers,
    )
    assert stripped.status_code == 200, stripped.text
    assert stripped.json()["permissions"] == ["payments.resolve"]

    # **وبعده: الخمسةُ مغلقة** — والبحثُ معها، فلا يبقى بابٌ يعرض ما مُنعت
    for path in GUARDED:
        refused = await client.get(path, headers=support_headers)
        assert refused.status_code == 403, f"{path} · {refused.text}"

    # **والإعادةُ تفتحها ثانيةً** — فالحارسُ يقرأ الصفوفَ لا لحظةَ الإقلاع
    await client.put(
        f"/admin/permissions/{support['user_id']}",
        json={"permissions": ["read.only", "payments.resolve"]},
        headers=admin_headers,
    )
    for path in GUARDED:
        assert (
            await client.get(path, headers=support_headers)
        ).status_code == 200, path


async def test_the_search_is_never_wider_than_the_lists_it_summarises(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    """**البحثُ لا يبقى مفتوحاً حين تُغلق الأربع** — وإلا صار التفافاً.

    **وهذا هو ما كان يقع لو بقي `StaffUser`**: من نُزعت عنه `read.only`
    يُردّ عن القوائم **ويقرأ صفوفَها في درج البحث** — والصفُّ نفسُه، باسمه
    ورقمه.
    """
    listed = await client.get("/admin/permissions", headers=admin_headers)
    support = next(row for row in listed.json() if "support" in row["roles"])
    await client.put(
        f"/admin/permissions/{support['user_id']}",
        json={"permissions": ["payments.resolve"]},
        headers=admin_headers,
    )

    lists = [
        (await client.get(path, headers=support_headers)).status_code
        for path in GUARDED[:-1]
    ]
    search = await client.get("/admin/search?q=قياس", headers=support_headers)

    assert set(lists) == {403}
    assert search.status_code == 403, search.text
