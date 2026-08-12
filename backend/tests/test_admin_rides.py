"""سجل الرحلات في اللوحة (SPEC القسم 13/4).

ثلاثةُ أشياء يختبرها هذا الملف، وكلُّها عن **حدود** ما يُعرض لا عن العرض:

- **الجمعُ في القاعدة**: `paid_amount` و`payment_methods` مجموعان في
  الاستعلام لا في اللوحة، والدفعُ المختلط صفّان على رحلةٍ واحدة — فقناةٌ
  واحدة في الصف تخفي نصف الواقعة.
- **صفٌّ واحدٌ لكل رحلة مهما تعددت دفعاتُها**: ضمُّ الدفعات إلى استعلام
  القائمة كان سيضاعف الصفوف، فتُعدّ الرحلةُ مرتين في صفحةٍ مسقوفة.
- **والمسارُ الفعلي دليلٌ لا زينة** (القسم 5.7/13.4): يخرج في التفاصيل وحدها،
  ولا يخرج في القائمة أصلاً.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import (
    DRIVER,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    broadcast_location,
    completed_ride,
    pay_ride,
    register,
    rider_session,
    started_ride,
    topup_wallet,
)


async def _rides(client: AsyncClient, headers: dict, **params) -> list[dict]:
    response = await client.get(
        "/admin/rides", headers=headers, params={"country_code": "JO", **params}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_list_carries_both_parties_and_a_settled_amount(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    assert paid.status_code == 201, paid.text
    # الردُّ على «ادفع» **قائمةٌ دائماً**: الدفع المختلط صفّان على رحلة واحدة
    payment = paid.json()["payments"][0]
    confirmed = await client.post(
        f"/payments/{payment['id']}/confirm", headers=driver["headers"]
    )
    assert confirmed.status_code == 200, confirmed.text

    rows = await _rides(client, admin_headers)
    assert len(rows) == 1
    row = rows[0]

    assert row["rider"]["name"] == RIDER["name"]
    assert row["driver"]["name"] == DRIVER["name"]
    # اللوحةُ الوحيدة للكبتن تُعرض مع صفّه — يُقارَن بها بلا فتح الملف
    assert row["driver"]["plate_number"] == "AMM-4242"
    assert row["payment_methods"] == ["cash"]
    assert row["paid_amount"] == row["final_fare"]
    assert row["has_open_dispute"] is False


async def test_mixed_payment_stays_one_row_with_two_channels(
    client: AsyncClient,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
    admin_headers: dict,
) -> None:
    """رحلةٌ بدفعتين تبقى **صفّاً واحداً** ويحمل القناتين.

    هذا هو ما يحرسه الاستعلامان المنفصلان: ضمُّ الدفعات إلى القائمة يضاعف
    الصفَّ بعدد دفعاته، فتُعدّ الرحلةُ مرتين وتُقصّ الصفحة على رحلةٍ ناقصة.
    وبحذف الفصل يسقط هذا الاختبار على `len(rows) == 1`.
    """
    # `jordan_wallet` يرفع مفتاحَي المحفظة بنفسه — رفعُهما ثانيةً يخالف القيد
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    # رصيدٌ جزئي: يُخصم المتاح ويبقى الباقي كاشاً (SPEC القسم 6)
    rider_id = await _rider_id(client, rider["headers"])
    await topup_wallet(client, admin_headers, rider_id, "2.000")

    # نداءٌ واحد يُخرج صفّين: المتاحُ من المحفظة والباقي كاشاً (القسم 6)
    paid = await pay_ride(
        client, rider["headers"], ride["id"], "wallet", key="mixed-wallet-01"
    )
    assert paid.status_code == 201, paid.text
    assert len(paid.json()["payments"]) == 2, paid.text

    rows = await _rides(client, admin_headers)
    assert len(rows) == 1, rows
    assert sorted(rows[0]["payment_methods"]) == ["cash", "wallet"]
    # المحفظةُ تُقيَّد فوراً والكاشُ ينتظر تأكيد الكبتن، فالمُحصَّل نصيبُ
    # المحفظة وحده
    assert rows[0]["paid_amount"] == "2.000"


async def _rider_id(client: AsyncClient, headers: dict) -> str:
    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return me.json()["id"]


async def test_detail_carries_the_route_as_dispute_evidence(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """نقاطُ المسار تخرج في التفاصيل — وهي الغرضُ الثاني لوجود الجدول."""
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await started_ride(client, rider["headers"], driver)

    await broadcast_location(client, driver, 31.9600, 35.9100)

    response = await client.get(f"/admin/rides/{ride['id']}", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["route_truncated"] is False
    assert len(body["route"]) >= 1
    assert body["route"][0]["lat"] and body["route"][0]["lng"]
    # القائمةُ لا تحمل المسار أصلاً — دليلٌ لكل صفٍّ في صفحةٍ من خمسين
    assert "route" not in (await _rides(client, admin_headers))[0]


async def test_search_matches_a_party_and_the_ride_id(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    by_driver = await _rides(client, admin_headers, q=DRIVER["name"])
    assert [row["id"] for row in by_driver] == [ride["id"]]

    by_id = await _rides(client, admin_headers, q=ride["id"])
    assert [row["id"] for row in by_id] == [ride["id"]]

    assert await _rides(client, admin_headers, q="لا أحد بهذا الاسم") == []


async def test_log_is_scoped_to_the_requested_country(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    await completed_ride(client, rider["headers"], driver)

    assert len(await _rides(client, admin_headers)) == 1
    assert await _rides(client, admin_headers, country_code="LY") == []


async def test_support_reads_the_log_and_anonymous_does_not(
    client: AsyncClient, jordan_settings: None, support_headers: dict
) -> None:
    """`support` يعالج النزاعات، ولا يُعالَج نزاعٌ على رحلةٍ لا تُقرأ."""
    allowed = await client.get(
        "/admin/rides", headers=support_headers, params={"country_code": "JO"}
    )
    assert allowed.status_code == 200, allowed.text

    anonymous = await client.get("/admin/rides", params={"country_code": "JO"})
    assert anonymous.status_code == 401


async def test_rider_cannot_read_the_admin_log(
    client: AsyncClient, jordan_settings: None
) -> None:
    """المسارُ إداريٌّ: راكبٌ يحمل جلسةً صحيحة يُردّ 403 لا 200 منقوصاً."""
    body = await register(client, dict(RIDER_FOR_ROLE_CHECK))
    response = await client.get(
        "/admin/rides", headers=auth(body), params={"country_code": "JO"}
    )
    assert response.status_code == 403


RIDER_FOR_ROLE_CHECK = {
    "phone": "0796767671",
    "name": "راكبٌ فضولي",
    "password": "SuperSecret123",
    "country_code": "JO",
    "role": "rider",
}
