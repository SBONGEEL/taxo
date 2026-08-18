"""خدمة التوصيل النسائي — المطابقة في اتجاهين (المرحلة 10-ج).

القاعدةُ التي يحرسها هذا الملف هي أن **الاتجاهين مستقلان**: ما تطلبه الراكبة
وما يقبله الكبتن شرطان منفصلان، وسكوتُ أحدهما لا يُلغي الآخر. وأهمُّ حالةٍ
هنا هي الثانية — راكبٌ اختار «لا يهمّني» لا يُعرض طلبُه على كبتنةٍ قصرت عملها
على النساء — لأنها الحالة التي يسقطها كلُّ تنفيذٍ يقرأ تفضيل الراكب وحده،
وسقوطُها يعني وضعَ امرأةٍ في سيارةٍ مع رجلٍ لم تختره ووضعَ سائقةٍ مع راكبٍ
رفضت مسبقاً أن تُقلّه.

ويحرس معها ثلاثة قيود:

- **الجنسُ غير المختوم لا يُرشَّح لطلبٍ مجنَّس**: بغير الختم يصير الحقل
  ادّعاءً، و«سائقة للنساء» شيئاً يكتبه المرء عن نفسه.
- **والمفتاح المطفأ يعني لا مطابقة أصلاً** لا «مطابقةً بتفضيلٍ فارغ»: تفضيلٌ
  قديم على حساب كبتنٍ في سوقٍ لا خدمةَ فيه كان سيحجب عنه الطلبات صامتاً.
- **ولا يتسرّب جنسُ أحدٍ إلى الطرف الآخر**: لا في تمثيل الرحلة ولا في
  السيارات القريبة.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    FeatureKey,
    Gender,
    GenderPreference,
    UserRole,
    VehicleCategory,
)
from app.models.ride import Ride
from app.models.user import User
from app.services import dispatch
from tests.helpers import (
    DRIVER,
    NEAR_PICKUP,
    PICKUP,
    RIDER,
    SECOND_DRIVER,
    approved_driver,
    auth,
    bring_online,
    enable_features,
    register,
    wait_for_offer,
    wait_for_status,
)

WOMEN = FeatureKey.WOMEN_SERVICE_ENABLED.value


async def _eligible(session_factory, ride_id: str, *candidates) -> set:
    """من يصلح لهذا الطلب فعلاً — سؤالٌ يُطرح على الدالة التي تملك القاعدة.

    ولا يُستعاض عنه بـ«انتهت الرحلة إلى `no_driver_found`»: تلك الحالة تُبلَغ
    أيضاً حين يُعرض الطلبُ على الكبتن ولا يقبله حتى تنقضي المهلة — فاختبارٌ
    يقنع بها يمرّ والقاعدةُ محذوفة، وهو ما وقع فعلاً في أول صياغةٍ لهذا الملف.
    """
    async with session_factory() as session:
        ride = await session.get(Ride, uuid.UUID(ride_id))
        match = await dispatch.gender_match_for(
            session,
            ride=ride,
            gender=await dispatch.rider_gender(session, ride.rider_id),
        )
        return await dispatch.eligible_driver_ids(
            session,
            [driver["driver_id"] for driver in candidates],
            VehicleCategory.ECONOMY,
            gender=match,
        )


async def _rider(
    client: AsyncClient,
    payload: dict = RIDER,
    *,
    gender: str | None = None,
) -> dict:
    body = await register(client, payload | ({"gender": gender} if gender else {}))
    return {"headers": auth(body), "user_id": body["user"]["id"], "body": body}


async def _driver_with(
    client: AsyncClient,
    session_factory,
    payload: dict,
    *,
    plate_number: str,
    gender: Gender | None = None,
    verified: bool = True,
    prefers: GenderPreference = GenderPreference.ANY,
) -> dict:
    """كبتنٌ جاهزٌ للتوزيع، بجنسٍ مختومٍ أو غير مختوم وتفضيلٍ دائم."""
    from datetime import UTC, datetime

    driver = await approved_driver(
        client, session_factory, payload, plate_number=plate_number
    )
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        row.gender_preference = prefers
        user = await session.get(User, row.user_id)
        user.gender = gender
        user.gender_verified_at = (
            datetime.now(UTC) if (gender is not None and verified) else None
        )
        await session.commit()
    await bring_online(client, driver, NEAR_PICKUP)
    return driver


async def _request(client: AsyncClient, headers: dict, preference: str | None) -> dict:
    payload = {
        "pickup": PICKUP,
        "dropoff": {"lat": 31.9800, "lng": 35.8600},
        "vehicle_category": "economy",
    }
    if preference is not None:
        payload["gender_preference"] = preference
    response = await client.post("/rides", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ------------------------------------------------------- ما تطلبه الراكبة


async def test_a_female_request_reaches_only_a_verified_female_driver(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    male = await _driver_with(
        client, session_factory, DRIVER, plate_number="AMM-1", gender=Gender.MALE
    )
    female = await _driver_with(
        client,
        session_factory,
        SECOND_DRIVER,
        plate_number="AMM-2",
        gender=Gender.FEMALE,
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="female")
    ride = await _request(client, rider["headers"], "female")

    assert await _eligible(session_factory, ride["id"], male, female) == {
        female["driver_id"]
    }
    offered = await wait_for_offer(ride["id"], female["driver_id"])
    # والرجل لم يُعرض عليه أصلاً — لا «عُرض ثم رُفض»
    assert offered != male["driver_id"]


async def test_an_unstamped_female_driver_is_not_a_candidate(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """جنسٌ بلا ختمٍ لا يُرشَّح — وهو ما يفصل الإثبات عن الادّعاء.

    ولولا هذا الشرط لكان بلوغُ «سائقة للنساء» بكتابة كلمةٍ في حقل.
    """
    unstamped = await _driver_with(
        client,
        session_factory,
        DRIVER,
        plate_number="AMM-1",
        gender=Gender.FEMALE,
        verified=False,
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="female")
    ride = await _request(client, rider["headers"], "female")

    assert await _eligible(session_factory, ride["id"], unstamped) == set()
    await wait_for_status(client, rider["headers"], ride["id"], "no_driver_found")


# -------------------------------------------------------- ما يقبله الكبتن


async def test_a_female_only_driver_is_not_offered_a_male_rider(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الحالةُ التي يسقطها كلُّ تنفيذٍ يقرأ تفضيل الراكب وحده.

    الراكب اختار «لا يهمّني»، والكبتنة قصرت عملها على النساء — فالطلبُ لا
    يصلها. الاتجاه الثاني لا يُلغيه سكوتُ الأول.
    """
    selective = await _driver_with(
        client,
        session_factory,
        DRIVER,
        plate_number="AMM-1",
        gender=Gender.FEMALE,
        prefers=GenderPreference.FEMALE,
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="male")
    ride = await _request(client, rider["headers"], "any")

    assert await _eligible(session_factory, ride["id"], selective) == set()
    await wait_for_status(client, rider["headers"], ride["id"], "no_driver_found")


async def test_a_female_only_driver_is_offered_a_female_rider(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await _driver_with(
        client,
        session_factory,
        DRIVER,
        plate_number="AMM-1",
        gender=Gender.FEMALE,
        prefers=GenderPreference.FEMALE,
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="female")
    ride = await _request(client, rider["headers"], "any")

    await wait_for_offer(ride["id"], driver["driver_id"])


async def test_a_rider_who_declared_nothing_matches_no_selective_driver(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """من لم يعلن جنسه لا يطابق كبتناً اشترط جنساً — ولا يُخمَّن عنه."""
    selective = await _driver_with(
        client,
        session_factory,
        DRIVER,
        plate_number="AMM-1",
        gender=Gender.MALE,
        prefers=GenderPreference.MALE,
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client)  # بلا إعلان
    ride = await _request(client, rider["headers"], None)

    assert await _eligible(session_factory, ride["id"], selective) == set()
    await wait_for_status(client, rider["headers"], ride["id"], "no_driver_found")


# ------------------------------------------------------------- المفتاح


async def test_the_switch_off_means_no_matching_at_all(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """بالمفتاح مطفأً يعمل الجميع كما كانوا — ولو بقيت تفضيلاتٌ مكتوبة.

    وهذا هو الفرق بين «لا مطابقة» و«مطابقةٌ بتفضيلٍ فارغ»: الثانية كانت
    ستُبقي تفضيلَ الكبتنة نافذاً فتحجب عنها الطلبات في سوقٍ لا خدمةَ فيه،
    بلا أن يفهم أحدٌ لماذا جفّت طلباتُها.
    """
    driver = await _driver_with(
        client,
        session_factory,
        DRIVER,
        plate_number="AMM-1",
        gender=Gender.FEMALE,
        prefers=GenderPreference.FEMALE,
    )

    rider = await _rider(client, gender="male")
    ride = await _request(client, rider["headers"], None)

    await wait_for_offer(ride["id"], driver["driver_id"])


async def test_a_gendered_request_is_refused_while_the_switch_is_off(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """التطبيق لا يعرض المفتاح أصلاً، فما يصل هنا طلبٌ مصنوع — ولا يُبتلع."""
    rider = await _rider(client, gender="female")
    response = await client.post(
        "/rides",
        headers=rider["headers"],
        json={
            "pickup": PICKUP,
            "dropoff": {"lat": 31.9800, "lng": 35.8600},
            "vehicle_category": "economy",
            "gender_preference": "female",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "women_service_unavailable"


async def test_the_flag_is_published_and_defaults_off(client: AsyncClient) -> None:
    """التطبيق يقرأ المفتاح من `/config` فيخفي الاختيار كلَّه وهو مطفأ."""
    response = await client.get("/config", params={"country_code": "JO"})
    assert response.status_code == 200
    features = response.json()["countries"][0]["features"]
    assert features[WOMEN] is False


# ------------------------------------------------------- التفضيل الافتراضي


async def test_the_profile_default_travels_to_the_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """تضبطه مرةً في حسابها فيسري على كل طلبٍ لا تختار فيه شيئاً."""
    female = await _driver_with(
        client,
        session_factory,
        DRIVER,
        plate_number="AMM-1",
        gender=Gender.FEMALE,
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="female")
    updated = await client.patch(
        "/auth/me",
        headers=rider["headers"],
        json={"ride_gender_preference": "female"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["ride_gender_preference"] == "female"

    ride = await _request(client, rider["headers"], None)
    assert ride["gender_preference"] == "female"
    await wait_for_offer(ride["id"], female["driver_id"])


async def test_a_driver_cannot_declare_his_own_gender(
    client: AsyncClient, session_factory
) -> None:
    """لا عند التسجيل ولا من ملفه — يثبّته المشرف من الهوية وحده."""
    refused = await client.post("/auth/register", json=DRIVER | {"gender": "female"})
    assert refused.status_code == 422, refused.text

    body = await register(client, DRIVER)
    headers = auth(body)
    from_profile = await client.patch(
        "/auth/me", headers=headers, json={"gender": "female"}
    )
    assert from_profile.status_code == 422, from_profile.text


async def _declare_female(client: AsyncClient, session_factory, payload: dict) -> dict:
    """كبتنةٌ أقرّت جنسَها عند التسجيل — والإقرارُ يُكتب مباشرةً هنا.

    ومسارُ التسجيل يرفض `gender` للكبتن عمداً (المرحلة 10-ج)، فالإقرارُ في
    الواقع يقع من التطبيق قبل الاعتماد؛ وما يُختبر هنا هو ما بعده.
    """
    from app.models.enums import Gender

    driver = await approved_driver(client, session_factory, payload)
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(driver["user_id"]))
        user.gender = Gender.FEMALE
        user.gender_verified_at = None
        await session.commit()
    return driver


async def test_a_stamp_that_contradicts_her_declaration_needs_a_reason(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**ختمٌ يخالف الإقرار يُلغي الوضعَ النسائي، فسببُه مطلوب** (2026-08-13).

    والسببُ هو **فائدةُ قيد التدقيق** حينها لا اسمُ الحقل: من يقرأ السجلَّ بعد
    شهرٍ يسأل «لماذا أُلغي عن هذا الحساب» لا «أيُّ عمودٍ كُتب».
    """
    driver = await _declare_female(client, session_factory, DRIVER)

    refused = await client.put(
        f"/admin/drivers/{driver['driver_id']}/gender",
        headers=admin_headers,
        json={"gender": "male"},
    )
    assert refused.status_code == 422, refused.text
    assert "سبب" in refused.json()["message"]

    # والإقرارُ لم يُلمس بالمحاولة الفاشلة
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(driver["user_id"]))
        assert user.gender is not None and user.gender.value == "female"


async def test_a_contradicting_stamp_revokes_women_mode_with_audit_and_notice(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """الإلغاءُ ثلاثةُ أشياءَ معاً: الجنسُ المختوم، وقيدٌ بسببه، وإشعارٌ لها.

    **ولا عمودَ «مُلغى»**: الوضعُ النسائيُّ مبنيٌّ على `gender = female` وحده،
    فالختمُ المخالف يُلغيه بنفسه — وعمودٌ ثانٍ يقول الشيءَ نفسَه يفترق عنه.
    """
    from app.models.audit import AdminAuditLog
    from app.models.notification import UserNotification

    driver = await _declare_female(client, session_factory, DRIVER)

    response = await client.put(
        f"/admin/drivers/{driver['driver_id']}/gender",
        headers=admin_headers,
        json={"gender": "male", "reason": "الهوية المرفوعة تقول ذكر"},
    )
    assert response.status_code == 200, response.text

    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(driver["user_id"]))
        assert user.gender is not None and user.gender.value == "male"
        # والختمُ موجود: المطابقةُ تقرأ المختوم، والإلغاءُ ليس محوَ ختم
        assert user.gender_verified_at is not None

        entry = await session.scalar(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_id == user.id)
            .order_by(AdminAuditLog.created_at.desc())
        )
        assert entry is not None
        assert entry.details.get("women_mode_revoked") is True
        assert entry.details.get("reason") == "الهوية المرفوعة تقول ذكر"

        # وإشعارٌ صريحٌ لها: اختفاءُ لونٍ وميزةٍ بلا تفسيرٍ تذكرةُ دعمٍ فوراً
        inbox = await session.scalars(
            select(UserNotification).where(UserNotification.user_id == user.id)
        )
        kinds = [row.kind for row in inbox]
    assert "women_mode_revoked" in kinds


async def test_a_matching_stamp_needs_no_reason_and_revokes_nothing(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """والختمُ المطابقُ يمرّ بلا سبب — سببٌ على كل ختمٍ حقلٌ يُملأ ليمرّ الطلب."""
    from app.models.notification import UserNotification

    driver = await _declare_female(client, session_factory, DRIVER)
    response = await client.put(
        f"/admin/drivers/{driver['driver_id']}/gender",
        headers=admin_headers,
        json={"gender": "female"},
    )
    assert response.status_code == 200, response.text

    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(driver["user_id"]))
        assert user.gender_verified_at is not None
        inbox = await session.scalars(
            select(UserNotification).where(UserNotification.user_id == user.id)
        )
        kinds = [row.kind for row in inbox]
    assert "women_mode_revoked" not in kinds


async def test_admin_stamps_the_gender_and_it_is_audited(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """حقلٌ يضبطه المشرف مباشرةً — بلا دورة اعتمادٍ جديدة، وبقيدِ تدقيق."""
    from app.models.audit import AdminAuditLog

    driver = await approved_driver(client, session_factory, DRIVER)

    response = await client.put(
        f"/admin/drivers/{driver['driver_id']}/gender",
        headers=admin_headers,
        json={"gender": "female"},
    )
    assert response.status_code == 200, response.text
    # ولم يخرج من الاعتماد: تفريغُ المتراكم لا يمرّ بطابور المراجعة
    assert response.json()["status"] == "approved"

    async with session_factory() as session:
        user = await session.scalar(
            select(User).where(User.id == driver["user_id"])
        )
        entry = await session.scalar(
            select(AdminAuditLog).where(AdminAuditLog.entity_id == user.id)
        )

    assert user.gender is Gender.FEMALE
    assert user.gender_verified_at is not None
    # القيدُ يحمل أسماء الحقول لا قيمها، كبقية كتابات اللوحة
    assert entry.details == {"fields": ["gender", "gender_verified_at"]}
    assert "female" not in str(entry.details)


async def test_support_cannot_stamp_a_gender(
    client: AsyncClient, session_factory, support_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    response = await client.put(
        f"/admin/drivers/{driver['driver_id']}/gender",
        headers=support_headers,
        json={"gender": "female"},
    )
    assert response.status_code == 403, response.text


# ------------------------------------------------------------ لا تسريب


async def test_no_endpoint_leaks_the_other_party_gender(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """جنسُ الطرف الآخر لا يغادر الخلفية — لا في الرحلة ولا في السيارات.

    وما يخرج هو **تفضيلُ الطلب** لا جنسُ صاحبه: تطبيق الكبتن يحتاجه ليرسم
    شارة «طلب نسائي»، وهو وصفٌ للطلب لا كشفٌ عن شخص.
    """
    female = await _driver_with(
        client,
        session_factory,
        DRIVER,
        plate_number="AMM-1",
        gender=Gender.FEMALE,
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="female")
    ride = await _request(client, rider["headers"], "female")
    await wait_for_offer(ride["id"], female["driver_id"])

    accepted = await client.post(
        f"/rides/{ride['id']}/accept", headers=female["headers"]
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()

    assert body["gender_preference"] == "female"
    assert "gender" not in body["driver"]
    assert "gender" not in body

    nearby = await client.get(
        "/drivers/nearby",
        headers=rider["headers"],
        params={"lat": PICKUP["lat"], "lng": PICKUP["lng"]},
    )
    assert nearby.status_code == 200
    for row in nearby.json():
        assert "gender" not in row


# ------------------------------------------- الإلغاء بلا عقوبة، والبلاغ


async def _accept(client: AsyncClient, ride: dict, driver: dict) -> dict:
    await wait_for_offer(ride["id"], driver["driver_id"])
    response = await client.post(
        f"/rides/{ride['id']}/accept", headers=driver["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _cancel(client: AsyncClient, headers: dict, ride_id: str, **body) -> dict:
    return await client.post(f"/rides/{ride_id}/cancel", headers=headers, json=body)


async def test_a_woman_refusing_a_mismatched_driver_pays_nothing(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """امرأةٌ طلبت سائقةً فوجدت غيرها لا تُغرَّم لأنها رفضت الركوب.

    ولولا هذا لكان الأرخصَ لها أن تركب — وهو ثمنٌ لا يجوز أن نضعه على أحد.
    """
    driver = await _driver_with(
        client, session_factory, DRIVER, plate_number="AMM-1", gender=Gender.FEMALE
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="female")
    ride = await _request(client, rider["headers"], "female")
    await _accept(client, ride, driver)

    response = await _cancel(
        client,
        rider["headers"],
        ride["id"],
        reason_code="gender_mismatch",
        reason="السائق رجل",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "cancelled_by_rider"
    # الرسمُ ساقط رغم أنها ألغت **بعد** القبول
    assert Decimal(body["cancellation_fee"]) == Decimal("0.000")

    async with session_factory() as session:
        reported = await session.get(User, uuid.UUID(driver["user_id"]))
    assert reported.gender_mismatch_reports == 1


async def test_the_same_cancellation_without_the_code_still_costs(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الإسقاطُ معلّقٌ بالسبب لا بالرحلة — وإلا صار كلُّ إلغاءٍ مجانياً."""
    driver = await _driver_with(
        client, session_factory, DRIVER, plate_number="AMM-1", gender=Gender.FEMALE
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="female")
    ride = await _request(client, rider["headers"], "female")
    await _accept(client, ride, driver)

    response = await _cancel(client, rider["headers"], ride["id"], reason="غيّرت رأيي")
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["cancellation_fee"]) > 0


async def test_the_code_is_refused_on_a_ride_that_asked_for_nobody(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """بابُ الإفلات من الرسوم مُغلق: لا تفضيلَ في الرحلة فلا محلَّ للسبب."""
    driver = await _driver_with(
        client, session_factory, DRIVER, plate_number="AMM-1", gender=Gender.MALE
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="male")
    ride = await _request(client, rider["headers"], "any")
    await _accept(client, ride, driver)

    response = await _cancel(
        client, rider["headers"], ride["id"], reason_code="gender_mismatch"
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "cancel_reason_not_applicable"

    # والرحلةُ لم تُلغَ بالمحاولة الفاشلة
    still = await client.get(f"/rides/{ride['id']}", headers=rider["headers"])
    assert still.json()["status"] == "accepted"


async def test_a_selective_driver_cancels_free_and_reports_the_rider(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """والاتجاه الآخر: كبتنةٌ قصرت عملها على النساء فجاءها رجل."""
    driver = await _driver_with(
        client,
        session_factory,
        DRIVER,
        plate_number="AMM-1",
        gender=Gender.FEMALE,
        prefers=GenderPreference.FEMALE,
    )
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="female")
    ride = await _request(client, rider["headers"], "any")
    await _accept(client, ride, driver)

    response = await _cancel(
        client,
        driver["headers"],
        ride["id"],
        reason_code="gender_mismatch",
        reason="الراكب ليس امرأة",
    )
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["cancellation_fee"]) == Decimal("0.000")

    async with session_factory() as session:
        reported = await session.get(User, uuid.UUID(rider["user_id"]))
    assert reported.gender_mismatch_reports == 1


async def test_the_flag_is_a_question_about_the_count(
    client: AsyncClient, session_factory
) -> None:
    """الوسمُ يُحسب من العدد ولا يُكتب عموداً — فتغييرُ الحدّ يعيد تقييم الجميع."""
    from app.services import rides as rides_service

    user = User(
        phone="+962790099099",
        name="حسابٌ للاختبار",
        role=UserRole.RIDER,
        country_code=CountryCode.JO,
        # صفرٌ صراحةً: القيمة الافتراضية تُكتب عند الإدراج، وهذا صفٌّ لم يُدرَج
        gender_mismatch_reports=0,
    )
    assert rides_service.is_flagged_for_gender_mismatch(user) is False

    user.gender_mismatch_reports = rides_service.GENDER_MISMATCH_FLAG_THRESHOLD - 1
    # بلاغٌ واحدٌ دون الحدّ لا يسم: قد يكون سوءَ فهمٍ أو ضوءاً خافتاً
    assert rides_service.is_flagged_for_gender_mismatch(user) is False

    user.gender_mismatch_reports += 1
    assert rides_service.is_flagged_for_gender_mismatch(user) is True


# --------------------------------------------------------- المدى الأوسع

# ~8.5 كم شمال نقطة الانطلاق: **خارج** دائرة السبعة و**داخل** العشرة
BEYOND_SEVEN_KM = {"lat": 32.0300, "lng": 35.9106}


async def test_a_gendered_request_reaches_further_than_seven_kilometres(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """كبتنةٌ على ~٨٫٥ كم: يصلها الطلبُ المجنَّس ولا يصلها العادي.

    والاختبارُ يفرّق الحالتين بنفس السائقة ونفس الموقع، فما يتغيّر هو التفضيل
    وحده — ولو كان الاتساعُ مطبَّقاً على الطلبات كلها لسقط النصف الثاني.
    """
    driver = await _driver_with(
        client,
        session_factory,
        DRIVER,
        plate_number="AMM-1",
        gender=Gender.FEMALE,
    )
    await bring_online(client, driver, BEYOND_SEVEN_KM)
    await enable_features(session_factory, WOMEN)

    rider = await _rider(client, gender="female")
    gendered = await _request(client, rider["headers"], "female")
    assert await wait_for_offer(gendered["id"]) == driver["driver_id"]

    cancelled = await _cancel(client, rider["headers"], gendered["id"])
    assert cancelled.status_code == 200, cancelled.text

    plain = await _request(client, rider["headers"], "any")
    await wait_for_status(client, rider["headers"], plain["id"], "no_driver_found")
