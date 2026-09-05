"""بوّابةُ القبول — **البند ١٠ يكمل يومَ تُعتمد النصوص** (§34، §45).

**وما يُقاس هنا ستُّ قواعدَ لا يقولها المُترجِم:**

1. **لا حسابَ يولد بلا موافقة** — والرفضُ **يسمّي الناقصَ** لا يقول «ناقص».
2. **وموافقةٌ ناقصةٌ ليست موافقة** — واحدةٌ من اثنتين تُردّ.
3. **والصفُّ يُكتب فعلاً** بالمستخدم والنسخة، **في معاملة التسجيل نفسِها**.
4. **ولكلِّ تطبيقٍ وثيقتُه** — ومعرّفاتُ الكبتن لا تُجيز تسجيلَ راكب.
5. **والمسوّدةُ لا تُطلب** — الواجبُ هو المنشورُ وحدَه.
6. **وبابُ التطبيق لا يمرّ بمفتاح الموقع** — إطفاءُ صفحةِ ويبٍ لا يُسقط
   بوّابةَ القبول في التطبيقين.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import CountryCode, PolicyApp, PolicyDocType, UserRole
from app.models.privacy import PrivacyPolicy, UserPolicyConsent
from app.models.user import User
from app.services import policies as policies_service
from app.services import site as site_service


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


async def _publish(session, *, app: PolicyApp, doc_type: PolicyDocType, body: str):
    actor = await _admin(session)
    policy = await policies_service.create_version(
        session,
        country=CountryCode.JO,
        doc_type=doc_type,
        app=app,
        body_ar=body,
        body_en=None,
        requires_reconsent=False,
    )
    await policies_service.publish(session, policy, actor=actor)
    await session.flush()
    return policy


async def _both(session, app: PolicyApp) -> list[PrivacyPolicy]:
    return [
        await _publish(session, app=app, doc_type=PolicyDocType.PRIVACY_POLICY, body="خصوصية."),
        await _publish(session, app=app, doc_type=PolicyDocType.TERMS_OF_USE, body="شروط."),
    ]


# ─────────────────────────────── ١ · لا حسابَ بلا موافقة


async def test_registration_is_refused_without_consent_and_names_what_is_missing(
    client: AsyncClient, session_factory
) -> None:
    async with session_factory() as session:
        await _both(session, PolicyApp.RIDER)
        await session.commit()

    res = await client.post(
        "/auth/register",
        json={
            "phone": "+962790000901",
            "name": "راكبٌ بلا موافقة",
            "password": "TaxoTest123",
            "country_code": "JO",
            "role": "rider",
            "app": "rider",
        },
    )
    assert res.status_code == 422, res.text
    message = res.json()["message"]
    # **يسمّي الاثنتين** — ورسالةٌ عامّةٌ تجعل التطبيقَ يخمّن
    assert "سياسة الخصوصية" in message and "شروط الاستخدام" in message

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(User).where(User.phone == "+962790000901")
        )
    # **ولا صفَّ نصفَ منشأ** — الفحصُ قبل الإنشاء لا بعده
    assert count == 0


# ─────────────────────────────── ٢ · وموافقةٌ ناقصةٌ ليست موافقة


async def test_partial_consent_is_refused_and_names_only_the_missing_one(
    client: AsyncClient, session_factory
) -> None:
    async with session_factory() as session:
        privacy, terms = await _both(session, PolicyApp.RIDER)
        privacy_id = str(privacy.id)
        await session.commit()

    res = await client.post(
        "/auth/register",
        json={
            "phone": "+962790000902",
            "name": "موافقةٌ ناقصة",
            "password": "TaxoTest123",
            "country_code": "JO",
            "role": "rider",
            "app": "rider",
            "accepted_policy_ids": [privacy_id],
        },
    )
    assert res.status_code == 422, res.text
    message = res.json()["message"]
    assert "شروط الاستخدام" in message
    # **ولا يُذكر ما وافق عليه** — الرسالةُ تقول ما ينقص لا ما تمّ
    assert "سياسة الخصوصية" not in message


# ─────────────────────────────── ٣ · والصفُّ يُكتب فعلاً


async def test_full_consent_creates_the_user_and_writes_one_row_per_document(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    async with session_factory() as session:
        docs = await _both(session, PolicyApp.RIDER)
        ids = [str(doc.id) for doc in docs]
        await session.commit()

    # **وبوّابةُ الرقم تُعطى رمزَها** — المقصودُ قياسُ بوّابة القبول،
    # **وسقوطٌ عند البوّابة التي بعدها لا يقيسها**. والرمزُ من المُحقِّق
    # الوهميِّ نفسِه الذي يستعمله `helpers.register`.
    from app.core.phone import normalize_phone
    from app.services.firebase_auth import mock_token

    phone = "+962790000903"
    res = await client.post(
        "/auth/register",
        json={
            "phone": phone,
            "name": "موافقةٌ كاملة",
            "password": "TaxoTest123",
            "country_code": "JO",
            "role": "rider",
            "app": "rider",
            "accepted_policy_ids": ids,
            "verification_token": mock_token(normalize_phone(phone, "JO")),
        },
    )
    assert res.status_code == 201, res.text
    user_id = uuid.UUID(res.json()["user"]["id"])

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(UserPolicyConsent).where(UserPolicyConsent.user_id == user_id)
            )
        ).all()
    assert {str(row.policy_id) for row in rows} == set(ids)
    # **ولكلِّ صفٍّ تاريخُه** — «وافق يومَ كذا» خبرٌ لا حقلٌ فارغ
    assert all(row.accepted_at is not None for row in rows)


# ─────────────────────────────── ٤ · ولكلِّ تطبيقٍ وثيقتُه


async def test_driver_documents_do_not_satisfy_a_rider_registration(
    client: AsyncClient, session_factory
) -> None:
    async with session_factory() as session:
        await _both(session, PolicyApp.RIDER)
        driver_docs = await _both(session, PolicyApp.DRIVER)
        driver_ids = [str(doc.id) for doc in driver_docs]
        await session.commit()

    res = await client.post(
        "/auth/register",
        json={
            "phone": "+962790000904",
            "name": "وثائقُ كبتنٍ لراكب",
            "password": "TaxoTest123",
            "country_code": "JO",
            "role": "rider",
            "app": "rider",
            "accepted_policy_ids": driver_ids,
        },
    )
    # **نصُّ الكبتن يذكر رخصةً ومركبةً وحسابَ صرف** (§34-٢) — وقبولُه لا يُبرئ
    assert res.status_code == 422, res.text


# ─────────────────────────────── ٥ · والمسوّدةُ لا تُطلب


async def test_only_published_documents_are_required(session_factory) -> None:
    async with session_factory() as session:
        await policies_service.create_version(
            session,
            country=CountryCode.JO,
            doc_type=PolicyDocType.PRIVACY_POLICY,
            app=PolicyApp.RIDER,
            body_ar="مسوّدةٌ لم تُنشر.",
            body_en=None,
            requires_reconsent=False,
        )
        await session.commit()

    async with session_factory() as session:
        required = await policies_service.required_for(
            session, country=CountryCode.JO, app=PolicyApp.RIDER
        )
    # **الواجبُ هو المنشورُ وحدَه** — ولا يُحسب `MAX(version)`
    assert required == []


# ─────────────────────────────── ٦ · وبابُ التطبيق مستقلٌّ عن مفتاح الموقع


async def test_app_door_is_not_gated_by_the_website_switch(
    client: AsyncClient, session_factory
) -> None:
    async with session_factory() as session:
        await _both(session, PolicyApp.RIDER)
        row = await site_service.get_or_create(session)
        row.policies_public = False  # **الموقعُ مغلق**
        await session.commit()

    web = await client.get("/public/policy?doc_type=privacy_policy")
    assert web.json() is None, "بابُ الويب يجب أن يسكت والمفتاحُ مطفأ"

    app_door = await client.get(
        "/public/policies/required?country_code=JO&app=rider"
    )
    # **وإطفاءُ صفحةِ ويبٍ لا يُسقط بوّابةَ القبول في التطبيقين**
    assert app_door.status_code == 200
    assert len(app_door.json()) == 2


# ─────────────────────────────── ٧ · ولا تُكتب موافقةٌ مرّتين


async def test_recording_the_same_consent_twice_writes_one_row(session_factory) -> None:
    async with session_factory() as session:
        docs = await _both(session, PolicyApp.RIDER)
        user = User(
            name="مكرِّر",
            phone="+962790000905",
            role=UserRole.RIDER,
            country_code=CountryCode.JO,
            password_hash="x",
        )
        session.add(user)
        await session.flush()

        first = await policies_service.record_consent(session, user=user, policies=docs)
        second = await policies_service.record_consent(session, user=user, policies=docs)
        await session.commit()
        user_id = user.id

    assert (first, second) == (2, 0)
    async with session_factory() as session:
        total = await session.scalar(
            select(func.count())
            .select_from(UserPolicyConsent)
            .where(UserPolicyConsent.user_id == user_id)
        )
    # **والقيدُ في القاعدة يمنعه أيضاً** — وهذا يمنع رميَه في وجه من يعيد المحاولة
    assert total == 2
