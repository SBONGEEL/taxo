"""حافزُ إحالة السائقات (SPEC القسم 9.1، المرحلة 12-ح).

قرارُ المالك يُختبر حرفياً: **الآليةُ تعمل والمبلغُ صفر** — فتُسجَّل الإحالةُ
ويُقاس الاستحقاقُ ولا يُكتب قيدٌ حتى يُحدَّد مبلغ. ومعه الشروطُ التي تجعل
الحافزَ لا يُدفع لمن لا يستحقّه: **وسمُ الجنس** لا الإقرار، و**اعتمادُ الحساب**
لا وجودُه، و**عددُ الرحلات** المقروءُ حيّاً.

**وكلُّ قاعدةٍ هنا مُختبَرةٌ بحذفها** — والملاحظاتُ تقول ماذا يقع عند الحذف.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.driver import Driver
from app.models.enums import Gender, WalletTransactionType
from app.models.referral import REFERRAL_TYPE_DRIVER, Referral
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import referrals as referrals_service
from tests.helpers import (
    DRIVER,
    RIDER,
    SECOND_DRIVER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    enable_features,
    register,
    rider_session,
    wallet_of,
)


async def _register_raw(client: AsyncClient, payload: dict):
    """تسجيلٌ يُتوقَّع فشلُه — **بإثبات ملكية الرقم** حتى يكون الفشلُ لِمَا نفحصه.

    وبغير الرمز يرتدّ الطلبُ ٤٢٢ «إثبات ملكية الرقم مطلوب»، فيمرّ اختبارُ
    «رمزُ إحالةٍ يُرفض على الراكب» **لسببٍ آخر** — وهو نجاحٌ كاذبٌ أسوأ من فشل.
    """
    from app.core.phone import normalize_phone
    from app.services.firebase_auth import mock_token

    body = dict(payload)
    body.setdefault(
        "verification_token",
        mock_token(normalize_phone(payload["phone"], payload["country_code"])),
    )
    return await client.post("/auth/register", json=body)


async def _my_referrals(client: AsyncClient, headers: dict) -> dict:
    response = await client.get("/me/referrals", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _program(data: dict, referral_type: str = REFERRAL_TYPE_DRIVER) -> dict:
    """سياسةُ برنامجٍ من الجواب — **صارت قائمةً لا حقولاً مسطّحة** بعد التعميم:
    رمزٌ واحدٌ يخدم برنامجين، فمبلغٌ واحدٌ في الجذر كان سيصف أحدَهما ويكذب على
    الآخر."""
    return next(
        row for row in data["programs"] if row["referral_type"] == referral_type
    )


async def _set_policy(
    client: AsyncClient,
    admin_headers: dict,
    *,
    amount: str | None = None,
    rides: int | None = None,
    female_bonus: str | None = None,
    monthly_cap: int | None = None,
    referral_type: str = REFERRAL_TYPE_DRIVER,
) -> dict:
    body: dict = {}
    if amount is not None:
        body["reward_amount"] = amount
    if rides is not None:
        body["required_rides"] = rides
    if female_bonus is not None:
        body["female_bonus_amount"] = female_bonus
    if monthly_cap is not None:
        body["monthly_cap"] = monthly_cap
    response = await client.put(
        f"/admin/referrals/settings?country_code=JO&referral_type={referral_type}",
        json=body,
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _stamp_female(session_factory, driver_id: uuid.UUID) -> None:
    """وسمُ المشرف — يُكتب مباشرةً هنا كما تفعل بقية الاختبارات مع الحالات."""
    async with session_factory() as session:
        driver = await session.get(Driver, driver_id)
        user = await session.get(User, driver.user_id)
        user.gender = Gender.FEMALE
        user.gender_verified_at = datetime.now(UTC)
        await session.commit()


async def _declare_female_only(session_factory, driver_id: uuid.UUID) -> None:
    """إقرارٌ **بلا وسم** — وهو ما لا يجوز أن يُكافأ عليه."""
    async with session_factory() as session:
        driver = await session.get(Driver, driver_id)
        user = await session.get(User, driver.user_id)
        user.gender = Gender.FEMALE
        user.gender_verified_at = None
        await session.commit()


async def _user_of(session_factory, driver_id: uuid.UUID) -> uuid.UUID:
    """حسابُ صاحبِ صفِّ الكبتن — فطرفا الإحالة حسابان بعد التعميم."""
    async with session_factory() as session:
        return (await session.get(Driver, driver_id)).user_id


async def _referral_of(session_factory, referred_id: uuid.UUID) -> Referral:
    """**والمفتاحُ صار حسابَ المُحال لا صفَّ كبتنه**: طرفا الإحالة حسابان."""
    async with session_factory() as session:
        row = await session.scalar(
            select(Referral).where(
                Referral.referred_user_id == referred_id
            )
        )
        assert row is not None
        return row


# ------------------------------------------------------------------ الرمز


async def test_every_account_gets_a_code_at_signup(client: AsyncClient, session_factory):
    """رمزٌ عند إنشاء الحساب لا عند أول فتحةٍ للشاشة — **ولكل حسابٍ الآن**.

    وتوليدٌ متأخرٌ يحتاج قفلاً على صفٍّ لا يُكتب فيه شيءٌ آخر، وبغيره تُنتج
    ضغطتان رمزين — وأحدُهما يذهب لمن لا يملكه.
    """
    for payload in (DRIVER, RIDER):
        body = await register(client, payload)
        mine = await _my_referrals(client, auth(body))
        assert len(mine["code"]) == referrals_service.CODE_LENGTH
        # لا محارفَ متشابهةٌ في الرمز: يُقرأ من شاشةٍ ويُكتب في أخرى
        assert set(mine["code"]) <= set(referrals_service.ALPHABET)


async def test_a_rider_may_now_sign_up_with_a_code_and_it_is_attributed(
    client: AsyncClient, session_factory
):
    """**عكسُ ما كان** (تعميمُ 2026-08-16)، والقاعدةُ التي أوجبته لم تتغيّر.

    كان يُرفض لأن الحافزَ كان لجذب السائقات وحدَهن، ورمزٌ يُقبل ثم لا يُسند
    شيئاً يبدو أنه عمل. وقد صار له برنامجٌ يُسند إليه، فالرفضُ نفسُه هو ما صار
    كذباً: «الرمز غير صحيح» عن رمزٍ صحيح.

    **والبرنامجُ من دور المُسجِّل لا من دور صاحب الرمز**: كبتنٌ دعا راكباً،
    فالصفُّ يُقاس ببرنامج الركاب.
    """
    driver = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(driver)))["code"]

    rider = await register(client, RIDER | {"referral_code": code})
    assert rider["user"]["id"]

    mine = await _my_referrals(client, auth(driver))
    assert len(mine["referrals"]) == 1
    assert mine["referrals"][0]["referral_type"] == "rider"


async def test_an_unknown_code_is_still_refused_on_both_paths(client: AsyncClient):
    """قبولُ رمزٍ لا وجودَ له ثم إهمالُه هو الشكلُ الذي لم يتغيّر."""
    for payload in (DRIVER, RIDER):
        refused = await _register_raw(client, payload | {"referral_code": "ZZZZZZZZ"})
        assert refused.status_code == 404, refused.text


async def test_the_code_is_case_insensitive_at_signup(
    client: AsyncClient, session_factory
):
    """يُقرأ من ملصقٍ أو رسالةٍ فيُكتب بأي حالة — والمطابقةُ الحسّاسة ترفض الصحيح."""
    first = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(first)))["code"]

    second = await register(
        client, SECOND_DRIVER | {"referral_code": code.lower()}
    )
    assert second["user"]["id"]
    mine = await _my_referrals(client, auth(first))
    assert len(mine["referrals"]) == 1


async def test_an_unknown_code_is_refused_not_swallowed(client: AsyncClient):
    """رمزٌ خاطئٌ يُرفض: حسابٌ يُنشأ بلا إحالةٍ يجعل من أحاله يسأل ولا جواب."""
    refused = await _register_raw(client, DRIVER | {"referral_code": "ZZZZZZZZ"})
    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "referral_code_unknown"


async def test_a_driver_cannot_refer_himself(client: AsyncClient, session_factory):
    """رمزُ نفسِه في تسجيله — مستحيلٌ عملياً (لا حسابَ بعد) فيُختبر في الخدمة."""
    body = await register(client, DRIVER)
    async with session_factory() as session:
        me = await session.get(User, uuid.UUID(body["user"]["id"]))
        try:
            await referrals_service.attach(
                session, referred=me, code=me.referral_code
            )
        except referrals_service.ReferralNotAllowed:
            pass
        else:  # pragma: no cover - الفشلُ هو الغرض
            raise AssertionError("قُبلت إحالةُ النفس")


async def test_one_account_is_referred_once(client: AsyncClient, session_factory):
    """الفريدُ في القاعدة: تسجيلان برمزين لا ينتجان مكافأتين لحسابٍ واحد."""
    first = await register(client, DRIVER)
    code_one = (await _my_referrals(client, auth(first)))["code"]
    second = await register(client, SECOND_DRIVER | {"referral_code": code_one})

    async with session_factory() as session:
        referred = await session.get(User, uuid.UUID(second["user"]["id"]))
        referrer = await session.get(User, uuid.UUID(first["user"]["id"]))
        try:
            await referrals_service.attach(
                session, referred=referred, code=referrer.referral_code
            )
        except referrals_service.ReferralNotAllowed:
            pass
        else:  # pragma: no cover
            raise AssertionError("قُبلت إحالةٌ ثانيةٌ لنفس الحساب")


# ------------------------------------------------------------- الاستحقاق


async def test_the_mechanism_records_while_the_amount_is_zero(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**قرارُ المالك**: الآليةُ والتتبّعُ يعملان والمبلغُ صفرٌ فلا قيد.

    والصفرُ «لم يُحدَّد بعد» لا «مكافأةٌ قدرُها صفر» — فلو قرأه الكودُ مبلغاً
    لكتب قيداً بصفرٍ يرفضه قيدُ الإشارة في القاعدة، أو أسوأ: لوسم الإحالةَ
    مدفوعةً بلا مال.
    """
    await enable_features(session_factory, "driver_referrals_enabled")
    first = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(first)))["code"]
    referred = await register(client, SECOND_DRIVER | {"referral_code": code})

    mine = await _my_referrals(client, auth(first))
    assert _program(mine)["enabled"] is True
    assert Decimal(_program(mine)["reward_amount"]) == 0
    assert len(mine["referrals"]) == 1
    assert mine["referrals"][0]["rewarded"] is False

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 0
        count = await session.scalar(
            select(func.count())
            .select_from(WalletTransaction)
            .where(WalletTransaction.type == WalletTransactionType.REFERRAL_BONUS)
        )
    assert count == 0
    assert referred["user"]["id"]


async def test_the_referral_is_recorded_even_where_the_flag_is_off(
    client: AsyncClient, session_factory
):
    """الإسنادُ سجلٌّ لما وقع، لا قرارُ دفع.

    ولو رُبط بالمفتاح لأُهمل رمزُ من أحال اليومَ صامتاً، فإن أُشعل المفتاحُ غداً
    لم يبق أثرٌ لمن أحال من — وهو ما يجعل الحافزَ بلا ذاكرة.
    """
    first = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(first)))["code"]
    await register(client, SECOND_DRIVER | {"referral_code": code})

    mine = await _my_referrals(client, auth(first))
    assert _program(mine)["enabled"] is False
    assert len(mine["referrals"]) == 1


async def test_a_declared_female_without_the_stamp_is_not_rewarded(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**الوسمُ لا الإقرار**: بلا `gender_verified_at` «سائقة» كلمةٌ عن النفس.

    وبحذف شرط الوسم يصير كلُّ من كتب «أنثى» في تسجيله مستحقاً — وهي الكلمةُ
    التي لا يفحصها أحد.
    """
    await enable_features(session_factory, "driver_referrals_enabled")
    await _set_policy(client, admin_headers, amount="5.000", rides=0)

    first = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(first)))["code"]
    second = await register(client, SECOND_DRIVER | {"referral_code": code})
    async with session_factory() as session:
        referred = await session.scalar(
            select(Driver).where(Driver.user_id == uuid.UUID(second["user"]["id"]))
        )
        referred_id = referred.id
    await _declare_female_only(session_factory, referred_id)

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 0

    mine = await _my_referrals(client, auth(first))
    assert mine["referrals"][0]["female_verified"] is False
    assert mine["referrals"][0]["rewarded"] is False


async def test_an_unapproved_driver_is_not_rewarded(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**الاعتمادُ حارسُ الحسابات الوهمية الحقيقي**: مستنداتٌ راجعها إنسان.

    وعددُ الرحلات وحده يُشترى بثلاث رحلاتٍ من الحساب نفسه، فحذفُ هذا الشرط
    يجعل الحافزَ يُدفع على حسابٍ لم يره أحد.
    """
    await enable_features(session_factory, "driver_referrals_enabled")
    await _set_policy(client, admin_headers, amount="5.000", rides=0)

    first = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(first)))["code"]
    second = await register(client, SECOND_DRIVER | {"referral_code": code})
    async with session_factory() as session:
        referred = await session.scalar(
            select(Driver).where(Driver.user_id == uuid.UUID(second["user"]["id"]))
        )
        referred_id = referred.id
    await _stamp_female(session_factory, referred_id)

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 0

    mine = await _my_referrals(client, auth(first))
    assert mine["referrals"][0]["driver_approved"] is False


async def test_the_rides_condition_is_read_live_not_stamped(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings
):
    """**تغييرُ الحدِّ يعيد تقييمَ الجميع**: عتبةٌ في الخدمة لا عمودٌ في الصف.

    فكبتنةٌ أكملت رحلةً واحدةً لا تستحقّ بحدِّ ثلاثٍ، وتستحقّ لحظةَ يُنزل
    المشرفُ الحدَّ إلى واحدة — بلا أن يُلمس صفُّها.
    """
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(client, admin_headers, amount="5.000", rides=3)

    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]

    referred = await approved_driver(
        client,
        session_factory,
        SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-9001",
    )
    await _stamp_female(session_factory, referred["driver_id"])
    await bring_online(client, referred)
    rider = await rider_session(client)
    await completed_ride(client, rider["headers"], referred)

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 0

    mine = await _my_referrals(client, auth(referrer))
    assert mine["referrals"][0]["rides_done"] == 1
    assert mine["referrals"][0]["qualifies"] is False

    await _set_policy(client, admin_headers, rides=1)
    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 1

    mine = await _my_referrals(client, auth(referrer))
    assert mine["referrals"][0]["rewarded"] is True
    assert Decimal(mine["referrals"][0]["reward_amount"]) == Decimal("5.000")


async def test_the_bonus_credits_the_referrers_wallet_with_no_counter_debit(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**دائنٌ بلا مدين**: الشركةُ تتحمّله كخصم الكوبون.

    ولو كُتب مدينٌ مقابلٌ على أحدٍ لخُصم من محفظةِ من لم يوافق — ووعاءُ الشركة
    ليس محفظةً في هذا النظام.
    """
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(client, admin_headers, amount="4.000", rides=0)

    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]
    referred = await approved_driver(
        client,
        session_factory,
        SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-9002",
    )
    await _stamp_female(session_factory, referred["driver_id"])

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 1
        rows = (
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.type == WalletTransactionType.REFERRAL_BONUS
                )
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].amount == Decimal("4.000")
        assert rows[0].owner_id == uuid.UUID(referrer["user"]["id"])
        # لا قيدٌ آخر في هذه العملية أصلاً
        total = await session.scalar(select(func.count()).select_from(WalletTransaction))
        assert total == 1

    balance = await wallet_of(client, auth(referrer))
    assert Decimal(balance["balance"]) == Decimal("4.000")


async def test_a_second_sweep_does_not_pay_twice(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """`rewarded_at` هو الأثر، ومفتاحُ التكرار حارسُ الدفتر الأخير."""
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(client, admin_headers, amount="3.000", rides=0)

    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]
    referred = await approved_driver(
        client,
        session_factory,
        SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-9003",
    )
    await _stamp_female(session_factory, referred["driver_id"])

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 1
        assert len(await referrals_service.pay_due(session)) == 0
        count = await session.scalar(
            select(func.count())
            .select_from(WalletTransaction)
            .where(WalletTransaction.type == WalletTransactionType.REFERRAL_BONUS)
        )
    assert count == 1


async def test_the_paid_amount_is_frozen_against_a_later_settings_change(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**المالُ لا يُعاد تقييمه**: مبلغٌ دُفع لا يتبع إعداداً تغيّر بعده."""
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(client, admin_headers, amount="2.000", rides=0)

    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]
    referred = await approved_driver(
        client,
        session_factory,
        SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-9004",
    )
    await _stamp_female(session_factory, referred["driver_id"])
    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 1

    await _set_policy(client, admin_headers, amount="9.000")
    row = await _referral_of(session_factory, await _user_of(session_factory, referred["driver_id"]))
    assert row.reward_amount == Decimal("2.000")


async def test_turning_the_flag_off_stops_paying_and_keeps_the_record(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """إطفاءُ المفتاح يوقف الدفعَ ولا يمحو إحالةً سُجّلت."""
    await _set_policy(client, admin_headers, amount="5.000", rides=0)
    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]
    referred = await approved_driver(
        client,
        session_factory,
        SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-9005",
    )
    await _stamp_female(session_factory, referred["driver_id"])

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 0

    mine = await _my_referrals(client, auth(referrer))
    assert len(mine["referrals"]) == 1
    assert mine["referrals"][0]["rewarded"] is False


# ------------------------------------------------------------------ اللوحة


async def test_the_panel_lists_referrals_with_both_names(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """معرِّفٌ لا يُقرأ — فالجدولُ يحمل اسمَي الطرفين ورقميهما."""
    await enable_features(session_factory, "driver_referrals_enabled")
    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]
    await register(client, SECOND_DRIVER | {"referral_code": code})

    response = await client.get("/admin/referrals?country_code=JO", headers=admin_headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["referrer_name"] == DRIVER["name"]
    assert rows[0]["referred_name"] == SECOND_DRIVER["name"]
    assert rows[0]["code_used"] == code


async def test_only_admin_writes_the_policy(
    client: AsyncClient, support_headers: dict
):
    """مبلغُ الحافز قرارٌ ماليّ — والدعمُ يقرأ ولا يكتب (القسم 13/8)."""
    read = await client.get(
        "/admin/referrals/settings?country_code=JO", headers=support_headers
    )
    assert read.status_code == 200, read.text

    write = await client.put(
        "/admin/referrals/settings?country_code=JO",
        json={"reward_amount": "5.000"},
        headers=support_headers,
    )
    assert write.status_code == 403, write.text


# ------------------------------------------------- قراراتُ التعميم الأربعة


async def test_the_female_bonus_is_added_to_the_base_never_instead_of_it(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**علاوةٌ لا برنامجٌ ثالث** (قرارُ المالك الثاني) — والقيدُ واحد.

    ولو كان النسائيُّ برنامجاً بمبلغه، ومبلغُه صفرٌ بينما مبلغُ السائقين مئة،
    لَدُفع **صفرٌ** لمن أحال سائقةً ومئةٌ لمن أحال سائقاً — أي ينقلب الحافزُ
    على غرضه بصمت. **والعلاوةُ تجعل الأسوأَ مساواةً لا عقوبة.**
    """
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(
        client, admin_headers, amount="5.000", rides=0, female_bonus="3.000"
    )
    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]
    referred = await approved_driver(
        client, session_factory, SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-9101",
    )
    await _stamp_female(session_factory, referred["driver_id"])

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 1

    mine = await _my_referrals(client, auth(referrer))
    # **الأساسُ والعلاوةُ معاً، لا العلاوةُ وحدَها**
    assert Decimal(mine["referrals"][0]["reward_amount"]) == Decimal("8.000")


async def test_a_male_referred_driver_is_paid_the_base_alone(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """صفرُ علاوةٍ = مساواة، وعلاوةٌ = تفضيل — ولا عقوبةَ في الحالين."""
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(
        client, admin_headers, amount="5.000", rides=0, female_bonus="3.000"
    )
    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]
    await approved_driver(
        client, session_factory, SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-9102",
    )

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 1

    mine = await _my_referrals(client, auth(referrer))
    assert Decimal(mine["referrals"][0]["reward_amount"]) == Decimal("5.000")


async def test_a_female_bonus_is_never_saved_negative(
    client: AsyncClient, admin_headers: dict
):
    """حارسُ المالك الأول: تُضاف إلى الأساس، فسالبُها يخصم من مكافأةٍ استُحقّت."""
    refused = await client.put(
        "/admin/referrals/settings?country_code=JO&referral_type=driver",
        json={"female_bonus_amount": "-1.000"},
        headers=admin_headers,
    )
    assert refused.status_code == 422


async def test_the_monthly_cap_records_the_referral_and_refuses_the_payment(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**تُسجَّل وتُنسب ولا تُدفع، ويُقال ذلك صراحةً** (شرطُ المالك الثالث).

    «لا صمتَ ولا رقمٌ يختفي»: الصفُّ يبقى في شاشته موسوماً بأنه فوق سقف الشهر —
    ومنعُه عند التسجيل كان سيعاقب **القادمَ الجديد** على سقف غيره.
    """
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(client, admin_headers, amount="5.000", rides=0, monthly_cap=1)
    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]

    await approved_driver(
        client, session_factory, SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-9103",
    )
    await approved_driver(
        client, session_factory,
        SECOND_DRIVER | {"referral_code": code, "phone": "0795550001",
                         "name": "كبتنٌ ثالث"},
        plate_number="AMM-9104",
    )

    async with session_factory() as session:
        # الأول يُدفع، والثاني يقف عند السقف — **ولا يُحذف**
        assert len(await referrals_service.pay_due(session)) == 1
        assert len(await referrals_service.pay_due(session)) == 0

    mine = await _my_referrals(client, auth(referrer))
    assert len(mine["referrals"]) == 2
    assert mine["paid_this_month"] == 1
    assert _program(mine)["monthly_cap"] == 1
    # **والوسمُ يُقال للمُحيل**: استحقّت ولن تُدفع، بسببٍ يُقرأ
    assert [row["over_monthly_cap"] for row in mine["referrals"]].count(True) == 1


async def test_two_referrals_paid_at_once_cannot_pass_one_referrers_cap(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**والقفلُ على المحفظة لا على صفِّ الإحالة** — وهذا ما يملكه هذا الاختبار.

    قفلُ صفِّ الإحالة يحمي **الصفَّ** من دفعتين، ولا يحمي **مُحيلاً** من صفَّين
    مختلفَين يُدفعان معاً: كلٌّ يقفل صفَّه، فيقرآن العدَّ نفسَه (صفراً) ويمرّان
    على سقفٍ واحد. وبحذف `wallet.lock_wallet` من `pay` يصير الجوابُ دفعتين
    بعشرة دنانير على سقفٍ قدرُه واحد — **مالٌ من عدم، بلا استثناءٍ ولا سطرِ سجل**.
    """
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(client, admin_headers, amount="5.000", rides=0, monthly_cap=1)
    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]

    first = await approved_driver(
        client, session_factory, SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-9105",
    )
    second = await approved_driver(
        client, session_factory,
        SECOND_DRIVER | {"referral_code": code, "phone": "0795550002",
                         "name": "كبتنٌ رابع"},
        plate_number="AMM-9106",
    )
    ids = [
        (await _referral_of(
            session_factory, await _user_of(session_factory, row["driver_id"])
        )).id
        for row in (first, second)
    ]

    # **والتشابكُ صريحٌ لا متروكٌ للجدولة** — وهو الدرسُ الذي تكرّر في 12-ح
    # و12-و و«السلف»: `gather` وحدَه يُنهي الأولى قبل أن تبدأ الثانية، فتقرأ
    # الثانيةُ صفّاً مُلتزَماً ويمرّ الاختبارُ **بحذف القفل**. فالأولى تُمسك
    # معاملتَها ٤٠٠ms، والثانيةُ تبدأ بعد ١٠٠ms — فتلتقيان فعلاً على العدّ
    async def _pay(referral_id, *, hold: float, after: float):
        await asyncio.sleep(after)
        async with session_factory() as session:
            paid = await referrals_service.pay(session, referral_id)
            await asyncio.sleep(hold)
            await session.commit()
            return paid is not None

    # **مهلةٌ تحرس الجمود**: قفلان يتشابكان لا يرفعان استثناءً بل يتوقّفان
    results = await asyncio.wait_for(
        asyncio.gather(
            _pay(ids[0], hold=0.4, after=0),
            _pay(ids[1], hold=0, after=0.1),
        ),
        timeout=30,
    )
    assert sum(results) == 1, results

    # **والدفترُ هو الحكم**: قيدٌ واحد، والرصيدُ يساويه
    async with session_factory() as session:
        user_id = await session.scalar(
            select(User.id).where(User.phone == "+962792222222")
        )
        entries = (
            await session.scalars(
                select(WalletTransaction.amount).where(
                    WalletTransaction.owner_id == user_id,
                    WalletTransaction.type
                    == WalletTransactionType.REFERRAL_BONUS,
                )
            )
        ).all()
    assert [Decimal(row) for row in entries] == [Decimal("5.000")]


async def test_a_driver_who_never_bought_a_subscription_is_not_rewarded(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**«اشترى مرةً» لا «نشطٌ لحظةَ الدفع»** (قرارُ المالك الرابع).

    وسببُه بنصِّه: حقٌّ اكتُسب لا يُمحى بمرور الزمن، وقراءةُ «نشطٌ لحظة الدفع»
    تجعل الاستحقاقَ يرقص مع تقويم الكبتن — **والعملُ هو الحكمُ لا التوقيت**.
    وهذا الاختبارُ يحرس النصفَ الآخر: من لم يشترِ قطُّ لم يعمل.
    """
    await enable_features(session_factory, "driver_referrals_enabled", "wallet_enabled")
    await _set_policy(client, admin_headers, amount="5.000", rides=0)
    referrer = await register(client, DRIVER)
    code = (await _my_referrals(client, auth(referrer)))["code"]

    # كبتنٌ سجّل ولم يشترِ اشتراكاً قط
    await register(client, SECOND_DRIVER | {"referral_code": code})

    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 0

    mine = await _my_referrals(client, auth(referrer))
    assert mine["referrals"][0]["has_subscription"] is False
    assert mine["referrals"][0]["qualifies"] is False
