"""البحثُ العامُّ في رأس اللوحة — **ما يقيسه هذا الملفّ** (§39٫١٢٫٤ و§39٫١٢٫٧).

## أربعةُ شروطٍ من نصِّ البند

1. **يقفز إلى مستخدمٍ أو كبتنٍ أو رحلةٍ أو مطالبة** — أربعةُ أصنافٍ لا ثلاثة.
2. **بالرقم أو الاسم أو المرجع** — والمرجعُ هو ما تُطابَق به مطالبةُ كليك.
3. **ولا اقتراحَ يعرض ما لا يملك المشرفُ صلاحيتَه** (§39٫١٢٫٧).
4. **ومعرّفُ الكبتن `drivers.id`** — فالدرجُ يفتح ملفَّه لا ملفَّ سواه.

## ⚠ والثالثُ يُقاس بالسلوك لا بقراءة الاعتماديّات

**قراءةُ `Depends` من الموجّه تقيس شكلاً**، ومن أضاف حارساً بطريقةٍ أخرى يمرّ.
**والمقيسُ هنا الجواب**: `support` يبلغ البحثَ **وكلَّ قائمةٍ يلخّصها**. فإن
حُرست إحداها بصلاحيةٍ يوماً، سقط هذا الاختبارُ بنصٍّ يقول ماذا يُفعل —
**ولا يصير البابُ التفافاً على حارسٍ من حيث لا يُرى**.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import DRIVER, RIDER, approved_driver, rider_session, topup_wallet

#: القوائمُ التي يلخّصها البحثُ العامّ — **صنفٌ لكلٍّ منها**
SOURCE_LISTS = [
    "/admin/users",
    "/admin/drivers",
    "/admin/rides",
    "/admin/topups",
]


async def test_a_single_letter_is_not_a_search(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**حرفٌ واحدٌ يعيد فراغاً** — ولا يمسح الجدولَ على كلِّ ضغطة مفتاح.

    **والفراغُ هنا ليس «لا نتائج»**: هو «لم يُبحث بعد» — والواجهةُ تقولها
    نصّاً مختلفاً، وهو ما يفعله `Picker` بحدِّ الحرفين نفسِه.
    """
    await rider_session(client)

    for value in ("", " ", RIDER["name"][:1]):
        answer = await client.get(
            "/admin/search", params={"q": value}, headers=admin_headers
        )
        assert answer.status_code == 200, answer.text
        assert answer.json()["hits"] == [], f"q={value!r} بحث وما كان ينبغي"


async def test_it_finds_a_rider_by_name_and_a_captain_by_phone(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**الاسمُ والرقمُ كلاهما يجد** — والرقمُ مخزَّنٌ `E.164` فالاحتواءُ شرط."""
    await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)

    by_name = await client.get(
        "/admin/search", params={"q": RIDER["name"][:4]}, headers=admin_headers
    )
    assert by_name.status_code == 200, by_name.text
    users = [hit for hit in by_name.json()["hits"] if hit["kind"] == "user"]
    assert users, "لم يجد حساباً باسمه"

    by_phone = await client.get(
        "/admin/search", params={"q": DRIVER["phone"][-5:]}, headers=admin_headers
    )
    assert by_phone.status_code == 200
    drivers = [hit for hit in by_phone.json()["hits"] if hit["kind"] == "driver"]
    assert drivers, "لم يجد كبتناً بجزءٍ من رقمه"

    # **٤) ومعرّفُ الكبتن `drivers.id` لا `users.id`** — وخلطُهما يفتح ملفَّ
    # إنسانٍ آخر، **ولا يصيح شيء** لأن كليهما UUID صالح
    assert drivers[0]["id"] == str(driver["driver_id"])
    assert drivers[0]["id"] != str(driver["user_id"])


async def test_a_claim_is_found_by_its_reference(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings,
    jordan_wallet,
) -> None:
    """**«أو المرجع» من نصِّ البند** — وهو ما يُطابَق به الإيصالُ بعد شهر.

    **ولا يجده بحثُ الاسم وحدَه**: من يمسك ورقةً في يده يملك مرجعَها لا اسمَ
    صاحبها — **وبابُ `/admin/topups` كان يبحث بالصاحب فقط**، فوُسّع معه كي لا
    يفترق البابان (الشكلُ الثامن).
    """
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "5.000")

    answer = await client.get(
        "/admin/search", params={"q": "شحن اختبار"}, headers=admin_headers
    )
    assert answer.status_code == 200, answer.text
    claims = [hit for hit in answer.json()["hits"] if hit["kind"] == "claim"]
    assert claims, "لم يجد مطالبةً بمرجعها"
    assert claims[0]["label"] == "شحن اختبار"
    # **والتلميحُ اسمُ صاحبها** — «مؤكَّدة» لا تفرّق مطالبتين في درجٍ واحد
    assert claims[0]["hint"] == RIDER["name"]


async def test_the_list_door_finds_the_same_claim_by_the_same_reference(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings,
    jordan_wallet,
) -> None:
    """**بابان ينشران الشيءَ نفسَه فلا يفترقان** — الشكلُ الثامن.

    **ولو وُسّع البحثُ العامُّ وحدَه** لَوجد المشرفُ المطالبةَ في الدرج ثم لم
    يجدها في صفحتها بالمرجع نفسِه — **ويُقرأ ذلك عطباً في البيانات**.
    """
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "5.000")

    answer = await client.get(
        "/admin/topups", params={"q": "شحن اختبار"}, headers=admin_headers
    )
    assert answer.status_code == 200, answer.text
    assert [row["reference"] for row in answer.json()] == ["شحن اختبار"]


async def test_a_percent_sign_is_a_character_not_a_wildcard(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**`%` تُهرَّب** — ومن كتبها بلا تهريبٍ رأى كلَّ شيءٍ وظنّه نتيجةَ بحثه.

    **وهو عطبٌ وقع مقيساً ٢٠٢٦-٠٩-٠٢ في ثلاثة مواضع**، وبيتُه الواحد
    `admin_search.like` — **ونسخةٌ رابعةٌ هنا كانت ستفوته من جديد**.
    """
    await rider_session(client)

    answer = await client.get(
        "/admin/search", params={"q": "%%"}, headers=admin_headers
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["hits"] == []


async def test_the_global_search_never_outreaches_the_lists_it_summarises(
    client: AsyncClient, support_headers: dict
) -> None:
    """**§39٫١٢٫٧ بحرفه**: لا اقتراحَ يعرض ما لا يملك المشرفُ صلاحيتَه.

    **والأربعُ محروسةٌ بـ`read.only` منذ ٢٠٢٦-٠٩-٠٤** (§٤٧٫١٠) **والبحثُ
    بحارسِها نفسِه** — فهذا البابُ يعطي ما تعطيه هي حرفاً. **ومن ضيّق إحداها
    غداً يسقط هنا** بنصٍّ يقول ماذا يُفعل، فلا يبقى البابُ يعرض ما صارت هي
    تمنعه.

    **وهذا الملفُّ يقيس الاتّساع، و`tests/test_admin_list_guard.py` يقيس
    الضيق**: أن نزعَ `read.only` يغلق الخمسةَ معاً.
    """
    await rider_session(client)

    search = await client.get(
        "/admin/search", params={"q": RIDER["name"][:4]}, headers=support_headers
    )
    assert search.status_code == 200, search.text

    for path in SOURCE_LISTS:
        answer = await client.get(path, headers=support_headers)
        assert answer.status_code == 200, (
            f"`{path}` صارت محروسةً و`/admin/search` ما زال يلخّصها — "
            "أضِف الحارسَ نفسَه إلى البحث، أو انزع صنفَها منه"
        )


async def test_support_sees_what_admin_sees(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    """**ولا ينقص `support` اقتراحاً يملك قائمتَه** — والعكسُ هو العطب.

    **إخفاءُ الواجهة راحةٌ لا حماية** (§21): درجٌ يُخفي ما يفتحه البابُ يجعل
    المشرفَ يظنّ الصفَّ غيرَ موجودٍ فيبحث عنه في مكانٍ آخر.
    """
    await rider_session(client)
    term = RIDER["name"][:4]

    as_admin = await client.get(
        "/admin/search", params={"q": term}, headers=admin_headers
    )
    as_support = await client.get(
        "/admin/search", params={"q": term}, headers=support_headers
    )
    assert as_admin.status_code == 200 and as_support.status_code == 200
    assert as_support.json() == as_admin.json()


async def test_a_term_that_matches_nobody_returns_nothing(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**نصٌّ لا يطابق أحداً يعيد فراغاً** — لا الكلَّ."""
    await rider_session(client)

    answer = await client.get(
        "/admin/search", params={"q": "زقنقلٌ لا يوجد ٩٩٩"}, headers=admin_headers
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["hits"] == []


async def test_a_stranger_is_refused(client: AsyncClient) -> None:
    """**ولا يبلغه من ليس طاقماً** — والحراسةُ على الباب لا في الشرط."""
    rider = await rider_session(client)

    answer = await client.get(
        "/admin/search", params={"q": RIDER["name"][:4]}, headers=rider["headers"]
    )
    assert answer.status_code == 403, answer.text
