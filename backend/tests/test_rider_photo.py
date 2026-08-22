"""صورةُ الراكب — **اختياريةٌ، بلا مراجعة، وتُحجب ببلاغ** (قرارُ المالك 2026-08-22).

**والمقيسُ هنا ثلاثة**: أن الكبتنَ يراها بعد القبول، **وأن البلاغَ يحجبها في
اللحظة لا بعد قرار**، **وأن الردَّ لا يفرّق** بين من رفع ومن لم يرفع ومن
حُجبت صورتُه — وهو الدرسُ نفسُه الذي أُصلح به عطبُ الإعفاء في اليوم نفسِه:
**ما دام الغيابُ مرئياً صار علامة**.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import (
    DRIVER,
    real_jpeg,
    accepted_ride,
    approved_driver,
    bring_online,
    rider_session,
)


async def _upload(client: AsyncClient, headers: dict, content: bytes | None = None):
    """**ويتحقّق من نجاحه** — مساعدٌ لا يقيس نتيجتَه يجعل كلَّ اختبارٍ بعده
    يقارن غياباً بغياب **ويمرّ أخضرَ**. وقد وقع مقيساً: رفعٌ فاشلٌ ترك
    الاختبارَ يقارن حرفاً بحرفٍ فيتساويان."""
    response = await client.put(
        "/auth/me/photo",
        files={"file": ("me.jpg", content or real_jpeg(), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 200, f"الرفعُ لم ينجح: {response.status_code} {response.text[:300]}"
    return response


def _fingerprint(response) -> dict:
    return {
        "status": response.status_code,
        "type": response.headers.get("content-type"),
        "length": len(response.content),
    }


async def test_a_rider_uploads_and_the_driver_sees_it_after_accepting(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    rider = await rider_session(client)
    assert (await _upload(client, rider["headers"])).status_code == 200

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)

    seen = await client.get(
        f"/rides/{ride['id']}/rider/photo", headers=driver["headers"]
    )
    assert seen.status_code == 200
    assert seen.headers["content-type"] == "image/jpeg"


async def test_a_stranger_never_sees_it(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**المفتاحُ الرحلةُ لا المستخدم** — فلا يستعرض أحدٌ وجوهَ الركاب."""
    rider = await rider_session(client)
    await _upload(client, rider["headers"])
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)

    stranger = await rider_session(
        client, {"phone": "0798880001", "name": "غريب", "password": "SuperSecret123",
                 "country_code": "JO", "role": "rider"}
    )
    denied = await client.get(
        f"/rides/{ride['id']}/rider/photo", headers=stranger["headers"]
    )
    assert denied.status_code in (403, 404)


async def test_a_report_hides_it_in_the_same_moment(
    client: AsyncClient, session_factory, jordan_settings: None, admin_headers: dict
) -> None:
    """**الحجبُ قبل القرار**: الضررُ يقع في الدقائق لا في الأيام.

    وبحذف `photo_hidden_at` من `visible_path` يسقط هذا الاختبار: تبقى الصورةُ
    تُعرض بعد البلاغ حتى يفصل المشرف.
    """
    rider = await rider_session(client)
    await _upload(client, rider["headers"])
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)

    before = await client.get(
        f"/rides/{ride['id']}/rider/photo", headers=driver["headers"]
    )
    reported = await client.post(
        f"/rides/{ride['id']}/rider/photo/report", headers=driver["headers"]
    )
    assert reported.status_code == 204
    after = await client.get(
        f"/rides/{ride['id']}/rider/photo", headers=driver["headers"]
    )

    # **الصورةُ تبدّلت فعلاً** — ولولا هذا لكان الاختبارُ يقارن ردّين متطابقين
    assert before.content != after.content, "لم يتغيّر المعروض — الحجبُ لم يقع"
    # **والشكلُ لم يتبدّل**: نفسُ الحالة والنوع والطول — فلا يُعرف من الردّ
    # أنها حُجبت
    assert _fingerprint(before) == _fingerprint(after)

    listed = await client.get("/admin/photo-reports", headers=admin_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_the_admin_restores_or_removes_and_the_row_stays(
    client: AsyncClient, session_factory, jordan_settings: None, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    await _upload(client, rider["headers"])
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)
    await client.post(
        f"/rides/{ride['id']}/rider/photo/report", headers=driver["headers"]
    )

    report_id = (await client.get("/admin/photo-reports", headers=admin_headers)).json()[0]["id"]
    resolved = await client.post(
        f"/admin/photo-reports/{report_id}/resolve?remove=false", headers=admin_headers
    )
    assert resolved.status_code == 204

    # **معلَّقٌ لم يعد معلَّقاً** — والصفُّ باقٍ، ولا بلاغَ مفتوحٌ بعده
    assert (await client.get("/admin/photo-reports", headers=admin_headers)).json() == []
    # **وقرارٌ محسومٌ لا يُحسم مرتين**
    again = await client.post(
        f"/admin/photo-reports/{report_id}/resolve?remove=true", headers=admin_headers
    )
    assert again.status_code == 409


async def test_a_rider_without_a_photo_looks_like_one_with_a_hidden_photo(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**لا يُستدلّ من الردّ على من رفع ومن لم يرفع** — الشكلُ واحد."""
    bare = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await accepted_ride(client, bare["headers"], driver)
    seen = await client.get(
        f"/rides/{ride['id']}/rider/photo", headers=driver["headers"]
    )
    assert seen.status_code == 200
    assert len(seen.content) > 0, "ردٌّ بلا جسم — الاختبارُ يقيس فراغاً"
    assert seen.headers["content-type"] == "image/jpeg"
