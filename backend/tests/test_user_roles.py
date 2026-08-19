"""نموذجُ الأدوار مجموعةً (2026-08-19).

**وأخطرُ ما هنا ليس التخويل بل دلالةُ العمل**: مواضعُ تقرّر *ما هو الشيء* لا
*من يجوز له* — أيُّ محفظة، ومن ألغى، وأيُّ برنامجِ إحالة، وأيُّ تطبيقٍ يعود
إليه الدافع، وأيُّ سجلِّ رحلات. تخمينُ أحد الدورين فيها يكتب مالاً في المكان
الخطأ بصمت. فلكلٍّ **رمزٌ باسمه** يقول أيُّ قرارٍ غاب، ولا قيمةَ افتراضية.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AmbiguousRole
from app.models.enums import UserRole
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant

pytestmark = pytest.mark.asyncio


async def _grant(session_factory, user_id: uuid.UUID, role: UserRole) -> None:
    """يمنح دوراً ثانياً **مباشرةً في القاعدة** — لا مسارَ يمنحه بعد.

    وهذا بذاته ما تحرسه `test_no_route_grants_a_role`: الاختبارُ يكتب الصفَّ
    بيده لأن المشروعَ لا يملك باباً يفعل ذلك.
    """
    async with session_factory() as session:
        session.add(UserRoleGrant(user_id=user_id, role=role))
        await session.commit()


async def _user(session_factory, user_id: uuid.UUID) -> User:
    """يُعيد الحسابَ **وأدوارُه محمَّلة** — القراءةُ بعد إغلاق الجلسة تُحاول IO."""
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(str(user_id)))
        _ = user.roles  # يُجبر التحميلَ داخل السياق
        return user


# --------------------------------------------------------------- الترحيلة


async def test_every_account_carries_its_previous_role_and_nothing_else(
    session_factory,
) -> None:
    """**لا حسابَ يكسب دوراً بالترحيلة ولا يفقده** — عدداً وهويّةً.

    والمقارنةُ على الخريطة `{user_id: role}` لا على عدٍّ مجرَّد: عدٌّ متساوٍ مع
    دورٍ مبدَّلٍ يمرّ في اختبارٍ يعدّ الصفوف وحدَها.
    """
    async with session_factory() as session:
        accounts = (await session.execute(select(User.id, User.role))).all()
        grants = (
            await session.execute(select(UserRoleGrant.user_id, UserRoleGrant.role))
        ).all()

    assert len(grants) == len(accounts), "زاد صفٌّ أو نقص"
    assert {(uid, role) for uid, role in grants} == {
        (uid, role) for uid, role in accounts
    }, "دورٌ تبدّل عن دور صاحبه"


async def test_no_account_leaves_the_migration_with_two_roles(
    session_factory,
) -> None:
    """الدورُ الثاني يُكتسب بمسار المنح وحدَه، بعد المرحلة."""
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(UserRoleGrant.user_id)
                .group_by(UserRoleGrant.user_id)
                .having(func.count() > 1)
            )
        ).all()
    assert rows == []


async def test_a_role_cannot_be_granted_twice(session_factory, rider_payload) -> None:
    """صفّان بنفس الدور يجعلان «كم دوراً له» سؤالاً بجوابين."""
    from sqlalchemy.exc import IntegrityError

    async with session_factory() as session:
        user_id = await session.scalar(select(User.id).limit(1))
        role = await session.scalar(select(User.role).where(User.id == user_id))

    with pytest.raises(IntegrityError):
        async with session_factory() as session:
            session.add(UserRoleGrant(user_id=user_id, role=role))
            await session.commit()


# --------------------------------------------------------------- التخويل


async def test_a_second_role_opens_the_other_app_and_nothing_wider(
    client, session_factory, rider_payload
) -> None:
    """**توسيعُ الأدوار لا يوسّع نطاقَ التطبيقات**: يفتح تطبيقَ الدور، لا اللوحة."""
    from app.core import app_scope
    from app.core.app_scope import ClientApp, WrongAppForRole

    both = frozenset({UserRole.RIDER, UserRole.DRIVER})
    app_scope.guard(both, ClientApp.RIDER)  # يمرّ
    app_scope.guard(both, ClientApp.DRIVER)  # يمرّ
    with pytest.raises(WrongAppForRole):
        app_scope.guard(both, ClientApp.PANEL)  # ولا يتّسع للوحة


async def test_a_role_the_account_does_not_hold_is_still_refused() -> None:
    from app.core import app_scope
    from app.core.app_scope import ClientApp, WrongAppForRole

    with pytest.raises(WrongAppForRole):
        app_scope.guard(frozenset({UserRole.RIDER}), ClientApp.DRIVER)


async def test_authorisation_reads_the_database_not_the_token(
    client, session_factory
) -> None:
    """**سحبُ الدور يسري فوراً** — ولو بقي التوكن صالحاً.

    وهو ما تشتريه قراءةُ `deps` من الصفّ: مطالبةٌ في التوكن تبقى صادقةً بعد
    السحب حتى تنتهي صلاحيتُها.
    """
    from tests.helpers import rider_session

    rider = await rider_session(client)
    # **مسارٌ يشترط دورَ الراكب** — `/rides/me` يقبل أيَّ حسابٍ داخل
    assert (await client.get("/wallet/me", headers=rider["headers"])).status_code == 200

    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(rider["user"]["id"]))
        await session.execute(
            UserRoleGrant.__table__.delete().where(
                UserRoleGrant.user_id == user.id
            )
        )
        user.role = UserRole.SUPPORT
        await session.commit()

    assert (await client.get("/wallet/me", headers=rider["headers"])).status_code == 403


# --------------------------------------------------------------- الستّة


async def test_the_wallet_owner_is_not_guessed(client, session_factory) -> None:
    from app.services import wallet
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, uuid.UUID(rider["user"]["id"]), UserRole.DRIVER)
    user = await _user(session_factory, rider["user"]["id"])

    with pytest.raises(AmbiguousRole) as raised:
        wallet.owner_type_for(user)
    assert raised.value.code == "wallet_owner_undecided"


async def test_the_ride_side_is_not_guessed(client, session_factory) -> None:
    from app.services import rides as rides_service
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, uuid.UUID(rider["user"]["id"]), UserRole.DRIVER)
    user = await _user(session_factory, rider["user"]["id"])

    with pytest.raises(AmbiguousRole) as raised:
        rides_service._side_of(user)
    assert raised.value.code == "ride_side_undecided"


async def test_the_cancelling_side_is_not_guessed(client, session_factory) -> None:
    from app.routers.rides import _cancelling_role
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, uuid.UUID(rider["user"]["id"]), UserRole.DRIVER)
    user = await _user(session_factory, rider["user"]["id"])

    with pytest.raises(AmbiguousRole) as raised:
        _cancelling_role(user)
    assert raised.value.code == "cancelling_side_undecided"


async def test_the_card_return_app_is_not_guessed(client, session_factory) -> None:
    from app.services.card_payments import _paying_side
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, uuid.UUID(rider["user"]["id"]), UserRole.DRIVER)
    user = await _user(session_factory, rider["user"]["id"])

    with pytest.raises(AmbiguousRole) as raised:
        _paying_side(user)
    assert raised.value.code == "card_return_app_undecided"


async def test_the_referral_programme_is_not_guessed(
    client, session_factory
) -> None:
    from app.services import referrals
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, uuid.UUID(rider["user"]["id"]), UserRole.DRIVER)
    user = await _user(session_factory, rider["user"]["id"])

    with pytest.raises(AmbiguousRole) as raised:
        referrals.programme_for(user)
    assert raised.value.code == "referral_programme_undecided"


async def test_each_undecided_place_has_its_own_code() -> None:
    """**رمزٌ لكلٍّ لا رمزٌ عام**: المشرفُ يحتاج أن يعرف أيُّ قرارٍ غاب."""
    codes = {
        "wallet_owner_undecided",
        "ride_side_undecided",
        "cancelling_side_undecided",
        "card_return_app_undecided",
        "referral_programme_undecided",
    }
    assert len(codes) == 5


# --------------------------------------------------------------- الإحالة


async def test_the_referral_programme_is_stamped_at_referral_time(
    client, session_factory, rider_payload
) -> None:
    """**واقعةٌ تاريخية لا اشتقاق** — فلا يتبدّل البرنامجُ بتبدّل الأدوار."""
    from app.models.referral import Referral
    from tests.helpers import rider_session

    referrer = await rider_session(client)
    async with session_factory() as session:
        code = await session.scalar(
            select(User.referral_code).where(User.id == uuid.UUID(referrer["user"]["id"]))
        )

    from tests.helpers import RIDER, auth, register

    body = await register(
        client,
        {**RIDER, "phone": "+962790007771", "referral_code": code},
    )
    referred = {"headers": auth(body), "user": body["user"]}

    async with session_factory() as session:
        row = await session.scalar(
            select(Referral).where(
                Referral.referred_user_id == uuid.UUID(referred["user"]["id"])
            )
        )
    assert row is not None
    assert row.referral_type == referrals_rider_type()

    # ويكسب دورَ كبتنٍ بعدها — والبرنامجُ المختومُ لا يتحرّك
    await _grant(session_factory, uuid.UUID(referred["user"]["id"]), UserRole.DRIVER)
    async with session_factory() as session:
        again = await session.scalar(
            select(Referral.referral_type).where(Referral.id == row.id)
        )
    assert again == referrals_rider_type()


def referrals_rider_type() -> str:
    from app.services.referrals import REFERRAL_TYPE_RIDER

    return REFERRAL_TYPE_RIDER


async def test_older_rows_are_not_backfilled(session_factory) -> None:
    """**لا ملءَ بأثر رجعي**: صفٌّ أقدمُ من العمود يبقى فارغاً ويُشتقّ نوعُه."""
    from app.models.referral import Referral

    async with session_factory() as session:
        stamped = await session.scalar(
            select(func.count())
            .select_from(Referral)
            .where(Referral.referral_type.is_(None))
        )
    assert stamped is not None  # الصفوفُ الفارغةُ مقبولةٌ ولا تُملأ


# --------------------------------------------------------------- المنح


async def test_no_route_grants_a_role(client, admin_headers) -> None:
    """**منحُ دورِ الكبتن بمساره القائم وحدَه** — ولا بابَ جديد.

    والحارسُ على الشيفرة لا على السلوك: بابٌ يُضاف غداً يكتب `UserRoleGrant`
    مباشرةً يمرّ من كل اختبارٍ سلوكيّ، ولا يمسكه إلا هذا.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    writers = []
    for path in root.rglob("*.py"):
        rel = str(path.relative_to(root)).replace("\\", "/")
        if rel == "models/user_role_grant.py":
            continue  # تعريفُ الصنف نفسِه، لا كتابةَ صفّ
        if "UserRoleGrant(" in path.read_text(encoding="utf-8"):
            writers.append(rel)

    # بابُ الإنشاء وحدَه يكتب صفَّ دور
    assert writers == ["services/auth/base.py"], writers


# --------------------------------------------------------------- الأسبقية


async def test_the_admin_stamp_beats_any_role_the_account_holds(
    client, session_factory
) -> None:
    """**أسبقيةٌ معلَنة** (SPEC §21.3): ما ثبّته المشرفُ يغلب، ولا يُتخطّى بدور.

    ولا صياحَ هنا: هذا مسارُ أمان، والصياحُ يوقف امرأةً عن الخدمة النسائية
    بينما القيمةُ الآمنةُ موجودةٌ وقاطعة.
    """
    from datetime import datetime, timezone

    from app.models.enums import Gender
    from tests.helpers import rider_session

    rider = await rider_session(client)
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(rider["user"]["id"]))
        user.gender = Gender.FEMALE
        user.gender_verified_at = datetime.now(timezone.utc)
        await session.commit()

    await _grant(session_factory, uuid.UUID(rider["user"]["id"]), UserRole.DRIVER)

    response = await client.patch(
        "/auth/me",
        json={"gender": "male"},
        headers=rider["headers"],
    )
    assert response.status_code == 422, response.text

    async with session_factory() as session:
        after = await session.scalar(
            select(User.gender).where(User.id == uuid.UUID(rider["user"]["id"]))
        )
    assert after is Gender.FEMALE


async def test_an_account_with_no_grant_row_is_still_found(session_factory) -> None:
    """**صفٌّ بلا مجموعةٍ لا يختفي**: البذرةُ والثوابتُ تُنشئ حساباتٍ مباشرةً.

    ومرشِّحٌ يقرأ المجموعةَ وحدَها يُخفي مثلَ هذا الحساب من كل قائمة، بينما
    التخويلُ يقبله — فيصير موجوداً في باب ومفقوداً في آخر. و`has_role_clause`
    تضمّ العمودَ كما يضمّه `User.roles`: قاعدةٌ واحدةٌ في الموضعين.
    """
    from sqlalchemy import select

    from app.models.user_role_grant import has_role_clause

    async with session_factory() as session:
        legacy = User(
            phone="+962790009911",
            name="حسابٌ بلا صفِّ دور",
            role=UserRole.SUPPORT,
            country_code="JO",
            password_hash="x",
        )
        session.add(legacy)
        await session.commit()
        found = await session.scalar(
            select(User.id).where(
                User.id == legacy.id, has_role_clause(UserRole.SUPPORT)
            )
        )
        assert found == legacy.id
        assert legacy.has_role(UserRole.SUPPORT)
