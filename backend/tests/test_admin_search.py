"""بحثُ قوائم اللوحة — **مرشِّحٌ فقط، ويُقاس أنه لم يمسّ شيئاً** (البند ١٢).

## الشرطُ الذي يقيسه هذا الملفّ، بنصِّ المالك

> «لا تمسّ الترتيبَ ولا حدودَ الصفحات ولا منطقاً قائماً، **ويقيس اختبارٌ أن
> النتائجَ بـ`q` فارغةٍ مطابقةٌ تماماً لما كانت قبل التغيير — في القوائم
> كلِّها لا في واحدة**.»

**و«ما كانت قبل التغيير» يُقاس بالنداء بلا `q` أصلاً**: قبل التغيير لم يكن
للمُعامل وجود، **فالنداءُ الذي لا يذكره هو النداءُ القديمُ حرفاً**. فإن طابقه
`q=""` و`q="   "` فالمرشِّحُ لم يضف شرطاً — لا `WHERE TRUE` ولا `LIKE '%%'`.

**والقوائمُ كلُّها في جدولٍ واحد**: قائمةٌ تُنسى تمرّ صامتةً — **ومن أضاف
قائمةً مرقَّمةً بعد اليوم يضيف سطرَها هنا**، وإلا فالحارسُ يحرس ما يعرفه وحدَه.

## وثلاثةٌ تُقاس فوق التطابق

* **أن البحثَ يجد**: اسمٌ وجزءُ رقمٍ يجدان صاحبَهما — **وإلا فهو حقلٌ يزيّن**.
* **وأنه لا يجد ما ليس فيه**: نصٌّ لا يطابق أحداً يعيد فراغاً لا الكلَّ.
* **وأن حروفَ `LIKE` تُهرَّب**: `%` تُقرأ محرفاً لا «أيَّ شيء» — **ومن كتب
  `%` بلا تهريبٍ رأى الجدولَ كلَّه وظنّه نتيجةَ بحثه**.

## ⚠ وثغرةٌ في هذا الملفِّ نفسِه، قِيست 2026-09-02

**«أن البحثَ يجد» كان مقيساً على قائمةٍ واحدةٍ من أربعَ عشرة** (`/admin/drivers`)
بينما التطابقُ مقيسٌ على الأربعَ عشرة — **فمرَّت ثلاثُ قوائمَ لا يبحث فيها
نصفُ الشرط**: الدفعاتُ وطلباتُ الصرف ورسومُ الإلغاء كانت تقارن **`users.id`
بعمودٍ يشير إلى `drivers.id`**، فلا تطابق كبتناً أبداً.

**ولم يصح منها شيءٌ خطأً**: النتيجةُ فراغٌ، **والفراغُ جوابٌ مشروعٌ لبحثٍ
سليم** — فلا اختبارَ عامٌّ يفرّقه عن بحثٍ لا يبحث. **والذي أمسكه شرطُ شكلٍ
لا شرطُ نتيجة**: `admin_search._must_point_at` يقرأ الجدولَ الذي يشير إليه
العمود **من المخطَّط**، فصار الموضعُ الخاطئ يصيح في أوّل نداءٍ يحمل `q` —
**ويمسكه `test_a_term_that_matches_nobody_returns_nothing` على القوائم كلِّها
لأنه وحدَه يمرّر `q` غيرَ فارغة**.

**وتحته اختباران يقيسان الوجدانَ لا الشكل** على القائمتين اللتين يمكن بذرُهما.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import (
    DRIVER,
    RIDER,
    approved_driver,
    bring_online,
    completed_ride,
    pay_ride,
    rider_session,
    set_cliq_alias,
    topup_wallet,
)

# ═══════════════════════ القوائمُ المرقَّمةُ كلُّها — مسارٌ لكلٍّ
#
# **ولا واحدةَ تُترك**: القائمةُ مأخوذةٌ من مسحِ كلِّ `@router.get` يحمل
# `limit` في موجّهات `admin_*`.
PAGED_LISTS = [
    "/admin/users",
    "/admin/drivers",
    "/admin/drivers/advances",
    "/admin/drivers/debts",
    "/admin/rides",
    "/admin/payments",
    "/admin/topups",
    "/admin/withdrawals",
    "/admin/subscriptions",
    "/admin/campaigns",
    "/admin/referrals",
    "/admin/cancellation-charges",
    "/admin/settings/audit-logs",
    "/admin/vehicle-skins/purchases",
]


@pytest.mark.parametrize("path", PAGED_LISTS)
async def test_empty_q_changes_nothing(
    client: AsyncClient, admin_headers: dict, path: str
) -> None:
    """**النداءُ بلا `q` = النداءُ بـ`q=""` = النداءُ بـ`q="   "`** — بايتاً.

    **وهذا هو «ما كانت عليه قبل التغيير»**: المُعامل لم يكن موجوداً، فالنداءُ
    الذي لا يذكره هو النداءُ القديم.
    """
    plain = await client.get(path, headers=admin_headers)
    assert plain.status_code == 200, plain.text

    for value in ("", "   "):
        with_q = await client.get(path, params={"q": value}, headers=admin_headers)
        assert with_q.status_code == 200, with_q.text
        assert with_q.json() == plain.json(), f"{path} تغيّرت بـq={value!r}"


@pytest.mark.parametrize("path", PAGED_LISTS)
async def test_a_term_that_matches_nobody_returns_nothing(
    client: AsyncClient, admin_headers: dict, path: str
) -> None:
    """**نصٌّ لا يطابق أحداً يعيد فراغاً** — لا الكلَّ.

    **والعكسُ هو العطب**: مرشِّحٌ يُهمَل صامتاً يجعل حقلَ البحث زينةً — يكتب
    المشرفُ فيه ويرى القائمةَ كما هي فيظنّ أن كلَّ هؤلاء نتيجةُ بحثه.
    """
    answer = await client.get(
        path, params={"q": "زقنقلٌ لا يوجد ٩٩٩"}, headers=admin_headers
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    rows = body if isinstance(body, list) else body.get("rows", body.get("items", []))
    assert rows == [], f"{path} لم تُرشِّح"


async def test_a_percent_sign_is_a_character_not_a_wildcard(
    client: AsyncClient, admin_headers: dict, rider_payload: dict
) -> None:
    """**`%` تُهرَّب** — ومن كتبها بلا تهريبٍ رأى الجدولَ كلَّه."""
    await rider_session(client, rider_payload)

    everyone = await client.get("/admin/users", headers=admin_headers)
    assert len(everyone.json()) >= 1

    percent = await client.get(
        "/admin/users", params={"q": "%"}, headers=admin_headers
    )
    assert percent.status_code == 200
    # **لا اسمَ فيه `%` في البذور** — فالنتيجةُ فراغٌ لا الكلّ
    assert percent.json() == []


async def test_search_finds_by_name_and_by_part_of_the_phone(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**يجد باسمه وبجزءٍ من رقمه** — والرقمُ مخزَّنٌ `E.164` فالاحتواءُ شرط."""
    driver = await approved_driver(client, session_factory, DRIVER)
    # **`driver_id` كائنُ `UUID` والردُّ نصّ** — والمقارنةُ بلا `str` تسقط أبداً
    driver_id = str(driver["driver_id"])
    name = DRIVER["name"]
    tail = DRIVER["phone"][-5:]

    by_name = await client.get(
        "/admin/drivers", params={"q": name[:4]}, headers=admin_headers
    )
    assert by_name.status_code == 200, by_name.text
    assert any(row["driver_id"] == driver_id for row in by_name.json())

    by_phone = await client.get(
        "/admin/drivers", params={"q": tail}, headers=admin_headers
    )
    assert by_phone.status_code == 200
    assert any(row["driver_id"] == driver_id for row in by_phone.json())


async def test_search_does_not_widen_what_a_role_may_see(
    client: AsyncClient, support_headers: dict, rider_payload: dict
) -> None:
    """**البحثُ لا يفتح باباً مغلقاً**: الحراسةُ على الباب لا في الشرط.

    **ولو كان الترشيحُ حارساً لَفتحه بحثٌ** — فمن يملك القائمةَ يملكها كلَّها،
    ومن لا يملكها لا يبلغ الشرطَ أصلاً.
    """
    await rider_session(client, rider_payload)
    # `support` يقرأ الحسابات (SPEC §21) — والبحثُ لا يزيده ولا ينقصه
    plain = await client.get("/admin/users", headers=support_headers)
    searched = await client.get(
        "/admin/users", params={"q": RIDER["name"][:3]}, headers=support_headers
    )
    assert plain.status_code == searched.status_code
    if plain.status_code == 200:
        assert len(searched.json()) <= len(plain.json())


# ═══════════════════════ الوجدانُ حيث كان الشرطُ على الجدول الخطأ
#
# **هذان يقيسان ما لا يقيسه شرطُ الشكل**: أن الصفَّ يُوجد فعلاً باسم كبتنه —
# لا أن الشرطَ بُني على العمود الصحيح.


async def test_a_payment_is_found_by_the_name_of_its_captain(
    client: AsyncClient,
    session_factory,
    admin_headers: dict,
    rider_payload: dict,
    jordan_settings,
    jordan_wallet,
) -> None:
    """**دفعةُ رحلةٍ تُوجد باسم كبتنها** — لا براكبها وحدَه.

    **وكان هذا نصفَ البحث الساقط**: `rides.driver_id` عمودُ `drivers.id`،
    وشرطُ `users.id = …` عليه لا يطابق أبداً — **فمن بحث عن دفعاتِ كبتنٍ
    باسمه قرأ «لا نتائج» وهو «لا يبحث»**.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client, rider_payload)
    ride = await completed_ride(client, rider["headers"], driver)
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    assert paid.status_code in (200, 201), paid.text

    by_captain = await client.get(
        "/admin/payments", params={"q": DRIVER["name"][:4]}, headers=admin_headers
    )
    assert by_captain.status_code == 200, by_captain.text
    assert [row["ride_id"] for row in by_captain.json()] == [ride["id"]]

    by_rider = await client.get(
        "/admin/payments",
        params={"q": rider_payload["name"][:4]},
        headers=admin_headers,
    )
    assert by_rider.status_code == 200
    assert [row["ride_id"] for row in by_rider.json()] == [ride["id"]]


async def test_a_withdrawal_is_found_by_the_name_of_its_captain(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    """**طلبُ صرفٍ يُوجد باسم صاحبه** — و`driver_id` هنا `drivers.id` قصداً.

    وهو مكتوبٌ في `ARCHITECTURE.md` بحرفه: العمودُ يشير إلى `drivers` كما
    ينصّ القسم 4، **وتمريرُه حيث يُنتظر `users.id` يعيد صفراً صامتاً**.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    await set_cliq_alias(session_factory, driver["driver_id"])
    await topup_wallet(client, admin_headers, driver["user_id"], "80.000")

    created = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": "30.000", "method": "cliq"},
        headers=driver["headers"],
    )
    assert created.status_code == 201, created.text

    found = await client.get(
        "/admin/withdrawals", params={"q": DRIVER["name"][:4]}, headers=admin_headers
    )
    assert found.status_code == 200, found.text
    assert [row["id"] for row in found.json()] == [created.json()["id"]]

    # **ونصٌّ لا يخصّ أحداً يعيد فراغاً** — كي لا يُقرأ النجاحُ من شرطٍ ملغيّ
    none = await client.get(
        "/admin/withdrawals", params={"q": "لا أحدَ بهذا الاسم"}, headers=admin_headers
    )
    assert none.status_code == 200
    assert none.json() == []
