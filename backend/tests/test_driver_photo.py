"""الصورةُ الشخصية للسائق (البند ٥٢، وقرارُ المالك 2026-08-16).

**وثلاثةُ أشياء تُقاس هنا، كلُّها قواعدُ تُنقض بحسن نية:**

* **الاستثناءُ يقرأ الوسمَ لا الإقرار**: لو قُرئ `users.gender` وحدَه لسقط
  شرطُ التعرّف **بكلمةٍ يكتبها أيُّ أحدٍ عن نفسه** — وهو بابٌ يُفتح بسطرٍ واحدٍ
  ويبدو صحيحاً في المراجعة.
* **ولا أثرَ رجعياً**: الشرطُ لمن يُعتمد بعده، ومن اعتُمد قبله **لا يُسقَط
  اعتمادُه ولا يُعاقَب على الامتثال** — ورفعُه الصورةَ لأول مرة ليس استبدالاً
  لشيءٍ رآه مشرف.
* **والمنفذُ أضيقُ من منفذ المستندات**: مفتاحُه الرحلةُ لا الكبتن، ولا يردّ
  صورةً لم تُراجَع — فما ينتظر المراجعة قد يكون وجهَ شخصٍ آخر.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select

from app.models.driver import Driver
from app.models.enums import DriverStatus
from app.models.user import User
from tests.helpers import (
    DRIVER,
    JPEG_BYTES,
    accepted_ride,
    approve_all_documents,
    approved_driver,
    auth,
    bring_online,
    register,
    review_document,
    rider_session,
    upload_document,
)


async def _driver_row(session_factory, phone: str) -> Driver:
    async with session_factory() as session:
        return await session.scalar(
            select(Driver).join(User, User.id == Driver.user_id).where(User.phone == phone)
        )


async def _stamp_female(session_factory, phone: str) -> None:
    """ختمُ الإدارة — وهو ما يقرؤه الاستثناء، لا ما يكتبه صاحبُ الحساب."""
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.phone == phone))
        user.gender = "female"
        user.gender_verified_at = datetime.now(UTC)
        await session.commit()


async def _declare_female(session_factory, phone: str) -> None:
    """إقرارٌ بلا ختم — الحالُ التي **لا** تُعفي."""
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.phone == phone))
        user.gender = "female"
        user.gender_verified_at = None
        await session.commit()


# ------------------------------------------------------------ شرطُ الاعتماد


async def test_a_driver_is_not_approved_without_a_profile_photo(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """ما يراه الراكبُ ليس أقلَّ من الرخصة في هذا الباب."""
    body = await register(client, DRIVER)
    headers = auth(body)
    driver = await _driver_row(session_factory, "+962792222222")

    for doc_type in (
        "driving_license",
        "national_id",
        "vehicle_registration",
        "vehicle_front",
        "vehicle_back",
        "vehicle_plate",
    ):
        document = await upload_document(client, headers, doc_type=doc_type)
        await review_document(
            client, admin_headers, driver_id=driver.id, document_id=document["id"]
        )

    refused = await client.post(
        f"/admin/drivers/{driver.id}/approve", headers=admin_headers
    )
    assert refused.status_code == 409
    assert "الصورة الشخصية" in refused.json()["message"]

    photo = await upload_document(client, headers, doc_type="profile_photo")
    await review_document(
        client, admin_headers, driver_id=driver.id, document_id=photo["id"]
    )
    assert (
        await client.post(
            f"/admin/drivers/{driver.id}/approve", headers=admin_headers
        )
    ).status_code == 200


async def test_a_stamped_female_driver_is_approved_without_one(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """الاستثناءُ الذي وُجدت الخدمةُ النسائية لأجل ما وراءه.

    ونشرُ وجه امرأةٍ على كل من يطلب رحلةً كلفةٌ أمنيةٌ لا يقابلها في حالتها ما
    يقابلها في حاله.
    """
    body = await register(client, DRIVER)
    headers = auth(body)
    driver = await _driver_row(session_factory, "+962792222222")
    await _stamp_female(session_factory, "+962792222222")

    for doc_type in (
        "driving_license",
        "national_id",
        "vehicle_registration",
        "vehicle_front",
        "vehicle_back",
        "vehicle_plate",
    ):
        document = await upload_document(client, headers, doc_type=doc_type)
        await review_document(
            client, admin_headers, driver_id=driver.id, document_id=document["id"]
        )

    assert (
        await client.post(
            f"/admin/drivers/{driver.id}/approve", headers=admin_headers
        )
    ).status_code == 200

    # **ولا تُطالَب بها في شاشتها**: «ينقصك» ما لا ينقصها هو عطبُ المرحلة ١٣
    documents = (await client.get("/drivers/me/documents", headers=headers)).json()
    assert "profile_photo" not in documents["required"]
    assert "profile_photo" not in documents["awaiting_upload"]


async def test_a_declaration_alone_never_lifts_the_requirement(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**الوسمُ لا الإقرار** — وإلا سقط شرطُ التعرّف بكلمةٍ يكتبها أيُّ أحد.

    وهي قراءةُ التوفيق في 10-ج ومكافأةِ الإحالة في 12-ح نفسُها: ما يمسّ غيرَك
    يحتاج ختماً، وما يقيّدك وحدَك يكفيه أن يُكتب.
    """
    body = await register(client, DRIVER)
    headers = auth(body)
    driver = await _driver_row(session_factory, "+962792222222")
    await _declare_female(session_factory, "+962792222222")

    for doc_type in (
        "driving_license",
        "national_id",
        "vehicle_registration",
        "vehicle_front",
        "vehicle_back",
        "vehicle_plate",
    ):
        document = await upload_document(client, headers, doc_type=doc_type)
        await review_document(
            client, admin_headers, driver_id=driver.id, document_id=document["id"]
        )

    refused = await client.post(
        f"/admin/drivers/{driver.id}/approve", headers=admin_headers
    )
    assert refused.status_code == 409
    assert "الصورة الشخصية" in refused.json()["message"]


# ------------------------------------------------------------ المتراكمون


async def test_an_already_approved_driver_keeps_working_and_is_listed(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**لا أثرَ رجعيّ** (قرارُ المالك 2026-08-16) — والمتراكمُ يُرى ليُلاحَق.

    وإسقاطُ اعتمادِ من يعمل اليوم بشرطٍ أُضيف اليوم يوقف سوقاً لأجل صورة.
    """
    driver = await approved_driver(client, session_factory, DRIVER)

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        assert row.status is DriverStatus.APPROVED

    listed = await client.get(
        f"/admin/drivers?q={DRIVER['name']}", headers=admin_headers
    )
    rows = [
        row
        for row in listed.json()
        if row["driver_id"] == str(driver["driver_id"])
    ]
    assert rows and "profile_photo" in rows[0]["missing_required"]


async def test_a_first_photo_never_costs_an_approved_driver_his_approval(
    client: AsyncClient, admin_headers: dict, session_factory,
    jordan_settings: None,
) -> None:
    """**ولا يُعاقَب على الامتثال** — وهذا هو ما يجعل الملاحقةَ ممكنةً أصلاً.

    قاعدةُ 9-ب تُسقط الاعتمادَ على من **بدّل** ما اعتُمد عليه؛ ورفعُ نوعٍ لا
    صفَّ له لا يناقض شيئاً رآه مشرف. ولولا هذا الفرقُ لأسقط أوّلُ امتثالٍ من
    المتراكمين اعتمادَهم — أي لكان الردُّ على «ارفع صورتك» إيقافَهم عن العمل.
    """
    driver = await approved_driver(client, session_factory, DRIVER)

    upload = await upload_document(
        client, driver["headers"], doc_type="profile_photo", content=JPEG_BYTES,
        filename="face.jpg", envelope=True,
    )
    assert upload["approval_reverted"] is False
    assert upload["driver_status"] == "approved"

    # **والاستبدالُ بعد الاعتماد عليها يُسقطه** — فالقاعدةُ لم تُلغَ بل قُيّدت
    await review_document(
        client, admin_headers, driver_id=driver["driver_id"], document_id=upload["document"]["id"]
    )
    again = await upload_document(
        client, driver["headers"], doc_type="profile_photo", content=JPEG_BYTES,
        filename="face2.jpg", envelope=True,
    )
    assert again["approval_reverted"] is True


# ------------------------------------------------------------ منفذُ القراءة


async def test_the_photo_is_served_to_a_party_of_the_ride_only(
    client: AsyncClient, admin_headers: dict, session_factory,
    jordan_settings: None,
) -> None:
    """مفتاحُه **الرحلةُ** لا الكبتن — فلا مسارَ يعرض وجوهَ الكباتن بالمعرّفات."""
    driver = await approved_driver(client, session_factory, DRIVER)
    photo = await upload_document(
        client, driver["headers"], doc_type="profile_photo", content=JPEG_BYTES,
        filename="face.jpg",
    )
    await review_document(
        client, admin_headers, driver_id=driver["driver_id"],
        document_id=photo["id"],
    )

    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)

    mine = await client.get(
        f"/rides/{ride['id']}/driver/photo", headers=rider["headers"]
    )
    assert mine.status_code == 200
    assert mine.headers["content-type"].startswith("image/")
    assert mine.headers["cache-control"] == "private, no-store"

    # وغريبٌ عن الرحلة لا يراها — 404 لا 403: وجودُ الرحلة ليس معلومةً له
    stranger = await rider_session(client, {**DRIVER, "phone": "0796666666",
                                            "name": "راكبٌ غريب", "role": "rider"})
    assert (
        await client.get(
            f"/rides/{ride['id']}/driver/photo", headers=stranger["headers"]
        )
    ).status_code == 404


async def test_an_unreviewed_photo_is_never_published(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """ما ينتظر المراجعةَ قد يكون وجهَ شخصٍ آخر — وعرضُه يُبطل المراجعة.

    **والجوابُ صار صورةً لا ٤٠٤** (عطبُ الإعفاء 2026-08-22): كان ٤٠٤ لمن لا
    صورةَ مقبولةً له، **والحالان متطابقين في اللحظة** — لكنّ الوشايةَ في
    **الحالة المستقرّة**: من لا تظهر صورتُه أبداً مُعفاةٌ، أي امرأة. فصار
    البابُ يردّ **حرفاً مرسوماً في الخادم** بطولٍ ثابت.

    **والمعنى لم يتغيّر**: ما ينتظر المراجعةَ **لا يصل الراكبَ** — والمقيسُ
    هنا أن بايتاتِ الملفِّ المرفوع **ليست في الردّ**.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    await upload_document(
        client, driver["headers"], doc_type="profile_photo", content=JPEG_BYTES,
        filename="face.jpg",
    )
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)

    seen = await client.get(
        f"/rides/{ride['id']}/driver/photo", headers=rider["headers"]
    )
    assert seen.status_code == 200
    assert seen.headers["content-type"] == "image/jpeg"
    # **الملفُّ المرفوع لم يُنشر** — وهو المعنى الذي وُجد له هذا الاختبار
    assert JPEG_BYTES not in seen.content
