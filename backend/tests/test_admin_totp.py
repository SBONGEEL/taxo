"""التحقق الثنائي لدخول اللوحة (SPEC القسم 14.1، المرحلة 12-د).

كلُّ اختبارٍ هنا يقابل قاعدةً في المواصفة، ومنها ثلاثٌ تفشل بحذف سطرٍ واحد:
«لا توكنَ قبل العاملين»، و«رمزٌ قُبِل مرةً لا يُقبل ثانية»، و«لا إلزامَ قبل
إثبات استرداد الطالبِ نفسِه».
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode, UserRole
from app.models.notification import UserNotification
from app.models.user import User
from app.services import totp

ADMIN_PHONE = "+962790000001"
ADMIN_PASSWORD = "StaffSecret123"


async def _login(client: AsyncClient, phone: str = ADMIN_PHONE) -> dict:
    response = await client.post(
        "/auth/login", json={"phone": phone, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _next_code(secret: str) -> str:
    """رمزُ الخطوة التالية — داخل نافذة الانحراف وغيرُ محروقٍ أبداً.

    التأكيدُ يحرق خطوتَه (وهو المقصود: رمزٌ قُبِل مرةً لا يُقبل ثانية)، فرمزُ
    اللحظة نفسها بعد التأكيد مرفوضٌ بحق. واختبارٌ يستعمله يختبر الحارس لا
    الدخول — ويُخفي أيَّ خللٍ آخر خلف 401 صحيحة.
    """
    return totp.code_at(secret, totp.current_step() + 1)


async def _enroll_and_confirm(
    client: AsyncClient, headers: dict
) -> tuple[str, list[str]]:
    """يسجّل عاملاً ويؤكّده — ويعيد (السرّ، رموز الاسترداد)."""
    enrolled = await client.post("/auth/me/totp/enroll", headers=headers)
    assert enrolled.status_code == 200, enrolled.text
    secret = enrolled.json()["secret"]

    confirmed = await client.post(
        "/auth/me/totp/confirm",
        json={"code": totp.code_at(secret, totp.current_step())},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    codes = confirmed.json()["recovery_codes"]
    assert len(codes) == totp.RECOVERY_CODE_COUNT
    return secret, codes


async def _forget_sessions(redis, user_id) -> None:
    """يمحو مفاتيحَ جلساتٍ صنعتها الفيكستشر قبل أن تُضبط السياسة.

    فيكستشر `admin_headers` تُصدر توكناً قبل أي إعداد، فمفتاحُها بعمر الأيام
    المعتاد — وقياسُ المهلة على مجموعِ المفاتيح يقيسه معه.
    """
    keys = [key async for key in redis.scan_iter(f"auth:refresh:{user_id}:*")]
    if keys:
        await redis.delete(*keys)


async def _second_admin(session_factory) -> dict[str, str]:
    """مشرفٌ ثانٍ — لا فيكستشر له، ويلزم لاختبار الإلزام على غير من أشعله."""
    from app.core.security import hash_password
    from app.services import token_service

    async with session_factory() as session:
        user = User(
            phone="+962790000009",
            name="مشرف ثانٍ",
            role=UserRole.ADMIN,
            country_code=CountryCode.JO,
            password_hash=hash_password(ADMIN_PASSWORD),
        )
        session.add(user)
        await session.commit()
        tokens = await token_service.issue_token_pair(get_redis_client(), user)
    return {"Authorization": f"Bearer {tokens.access_token}"}


# --------------------------------------------------------------- الدخول


async def test_login_without_a_factor_returns_a_session(
    client: AsyncClient, admin_headers: dict
) -> None:
    body = await _login(client)
    assert body["totp_required"] is False
    assert body["tokens"]["access_token"]
    assert body["challenge_token"] is None


async def test_login_with_a_factor_returns_no_token_at_all(
    client: AsyncClient, admin_headers: dict
) -> None:
    """القاعدةُ الأولى: كلمةُ المرور الصحيحة وحدها لا تُصدر توكناً."""
    secret, _ = await _enroll_and_confirm(client, admin_headers)

    body = await _login(client)
    assert body["totp_required"] is True
    assert body["tokens"] is None
    assert body["user"] is None
    assert body["challenge_token"]

    wrong = await client.post(
        "/auth/login/totp",
        json={"challenge_token": body["challenge_token"], "code": "000000"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "invalid_totp"

    right = await client.post(
        "/auth/login/totp",
        json={
            "challenge_token": body["challenge_token"],
            "code": _next_code(secret),
        },
    )
    assert right.status_code == 200, right.text
    assert right.json()["tokens"]["access_token"]
    assert right.json()["user"]["phone"] == ADMIN_PHONE


async def test_a_code_already_used_is_refused(
    client: AsyncClient, admin_headers: dict
) -> None:
    """رمزٌ قُبِل مرةً لا يُقبل ثانية — وإلا فثلاثون ثانيةً لمن قرأه."""
    secret, _ = await _enroll_and_confirm(client, admin_headers)
    code = _next_code(secret)

    first = await _login(client)
    accepted = await client.post(
        "/auth/login/totp",
        json={"challenge_token": first["challenge_token"], "code": code},
    )
    assert accepted.status_code == 200

    second = await _login(client)
    replayed = await client.post(
        "/auth/login/totp",
        json={"challenge_token": second["challenge_token"], "code": code},
    )
    assert replayed.status_code == 401
    assert replayed.json()["code"] == "invalid_totp"


def test_the_codes_match_the_rfc_6238_vectors() -> None:
    """متجهاتُ RFC 6238 الرسمية — **الاختبارُ الوحيد هنا الذي يأتي من خارجنا**.

    كلُّ اختبارٍ آخر يولّد الرمزَ بـ`code_at` ثم يتحقق منه بـ`match_step`، فلو
    كان قصُّ HOTP خاطئاً لاتفق الطرفان على الخطأ ومرّ كلُّ شيء — ثم لا يدخل أحدٌ
    برمزٍ من Google Authenticator. وهي بالحرف مصيدةُ «فيكستشر يوافق العلّة»
    التي وقعت في `awaiting_confirmation`: بيانٌ مشتقٌّ من الذاكرة لا يثبت شيئاً.

    السرُّ هو `12345678901234567890` من الملحق B، والقيمُ مقصوصةٌ إلى ست خانات.
    """
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32 لـ "12345678901234567890"
    vectors = {
        1: "287082",  # T = 59
        37037036: "081804",  # T = 1111111109
        37037037: "050471",  # T = 1111111111
        41152263: "005924",  # T = 1234567890
        66666666: "279037",  # T = 2000000000
        666666666: "353130",  # T = 20000000000
    }
    for step, expected in vectors.items():
        assert totp.code_at(secret, step) == expected


def test_the_skew_window_is_one_step_each_way() -> None:
    """نافذةُ الانحراف ±خطوة (٣٠ث): ساعةُ حاسوبٍ مكتبيٍّ تنحرف في الاتجاهين.

    اختبارُ دالةٍ لا مسار: النافذةُ حسابٌ خالص، وقياسُها عبر HTTP يخلطها بحارس
    `last_step` — فرمزُ الخطوة السابقة قد يكون مرفوضاً لأنه **مستعمَل** لا
    لأنه خارج النافذة، فيمرّ الاختبارُ وهو يقيس شيئاً آخر.
    """
    secret = totp.generate_secret()
    now = totp.current_step()

    assert totp.match_step(secret, totp.code_at(secret, now)) == now
    assert totp.match_step(secret, totp.code_at(secret, now - 1)) == now - 1
    assert totp.match_step(secret, totp.code_at(secret, now + 1)) == now + 1
    # وخارجها لا يُقبل — وإلا صار عمرُ الرمز المسروق دقيقتين
    assert totp.match_step(secret, totp.code_at(secret, now - 2)) is None
    assert totp.match_step(secret, totp.code_at(secret, now + 2)) is None
    # وما ليس ستَّ خاناتٍ رقميةً يُرفض قبل أي حساب
    assert totp.match_step(secret, "abc123") is None
    assert totp.match_step(secret, "12345") is None


async def test_a_recovery_code_logs_in_once_and_tells_its_owner(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """من فقد هاتفه يدخل برمزِ استرداد — ويجد في صندوقه أن رمزاً استُهلك."""
    _, codes = await _enroll_and_confirm(client, admin_headers)

    body = await _login(client)
    response = await client.post(
        "/auth/login/totp",
        json={"challenge_token": body["challenge_token"], "recovery_code": codes[0]},
    )
    assert response.status_code == 200, response.text

    again = await _login(client)
    reused = await client.post(
        "/auth/login/totp",
        json={"challenge_token": again["challenge_token"], "recovery_code": codes[0]},
    )
    assert reused.status_code == 401

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(UserNotification).where(
                    UserNotification.kind == "recovery_code_used"
                )
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].data["remaining"] == str(totp.RECOVERY_CODE_COUNT - 1)


async def test_wrong_codes_destroy_the_challenge_without_locking_the_account(
    client: AsyncClient, admin_headers: dict
) -> None:
    """السقفُ يُبطئ التخمين، والقفلُ يُسلّم اللوحةَ للمخمّن — فلا قفل."""
    secret, _ = await _enroll_and_confirm(client, admin_headers)
    body = await _login(client)
    token = body["challenge_token"]

    for _ in range(totp.CHALLENGE_MAX_ATTEMPTS):
        failed = await client.post(
            "/auth/login/totp", json={"challenge_token": token, "code": "000000"}
        )
        assert failed.status_code == 401

    burned = await client.post(
        "/auth/login/totp", json={"challenge_token": token, "code": "000000"}
    )
    assert burned.status_code == 429

    # والحسابُ نفسُه سليم: تحدٍّ جديدٌ ورمزٌ صحيحٌ يدخلان
    fresh = await _login(client)
    accepted = await client.post(
        "/auth/login/totp",
        json={
            "challenge_token": fresh["challenge_token"],
            "code": _next_code(secret),
        },
    )
    assert accepted.status_code == 200, accepted.text


async def test_a_spent_challenge_cannot_be_reused(
    client: AsyncClient, admin_headers: dict
) -> None:
    secret, _ = await _enroll_and_confirm(client, admin_headers)
    body = await _login(client)
    code = _next_code(secret)

    first = await client.post(
        "/auth/login/totp",
        json={"challenge_token": body["challenge_token"], "code": code},
    )
    assert first.status_code == 200

    replay = await client.post(
        "/auth/login/totp",
        json={"challenge_token": body["challenge_token"], "code": code},
    )
    assert replay.status_code == 401
    assert replay.json()["code"] == "invalid_token"


# ------------------------------------------------------ التسجيل والإطفاء


async def test_the_secret_is_never_readable_again(
    client: AsyncClient, admin_headers: dict
) -> None:
    """لا مسارَ يعيد عرض السرِّ: جلسةٌ مسروقةٌ لا تستخرج العامل."""
    await _enroll_and_confirm(client, admin_headers)

    status = await client.get("/auth/me/totp", headers=admin_headers)
    assert status.status_code == 200
    assert "secret" not in status.json()
    assert status.json()["confirmed"] is True
    assert status.json()["recovery_codes_remaining"] == totp.RECOVERY_CODE_COUNT

    # وإعادةُ التسجيل على عاملٍ مؤكَّد مرفوضة — وإلا صارت طريقاً لتبديله
    again = await client.post("/auth/me/totp/enroll", headers=admin_headers)
    assert again.status_code == 409
    assert again.json()["code"] == "totp_already_enrolled"


async def test_disabling_needs_a_present_factor(
    client: AsyncClient, admin_headers: dict
) -> None:
    secret, codes = await _enroll_and_confirm(client, admin_headers)

    naked = await client.request(
        "DELETE", "/auth/me/totp", json={}, headers=admin_headers
    )
    assert naked.status_code == 422

    wrong = await client.request(
        "DELETE", "/auth/me/totp", json={"code": "000000"}, headers=admin_headers
    )
    assert wrong.status_code == 401

    ok = await client.request(
        "DELETE",
        "/auth/me/totp",
        json={"code": _next_code(secret)},
        headers=admin_headers,
    )
    assert ok.status_code == 204

    # وبعد الإطفاء يعود الدخول بكلمة المرور وحدها
    body = await _login(client)
    assert body["totp_required"] is False


async def test_riders_have_no_door_to_this_at_all(client: AsyncClient) -> None:
    """عاملٌ ثانٍ للراكب قرارُ منتجٍ لا يطلبه القسم 14 — فالبابُ لطاقم اللوحة."""
    from tests.helpers import RIDER, auth, register

    rider = await register(client, RIDER)
    response = await client.post("/auth/me/totp/enroll", headers=auth(rider))
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


# ------------------------------------------------------------- الإلزام


async def test_enforcement_is_refused_until_recovery_is_proven(
    client: AsyncClient, admin_headers: dict
) -> None:
    """قرارُ المالك: «لا تُلزم أحداً قبل أن أُثبت أن الاسترداد يعمل»."""
    bare = await client.put(
        "/admin/security", json={"admin_totp_required": True}, headers=admin_headers
    )
    assert bare.status_code == 409
    assert bare.json()["code"] == "totp_recovery_proof_required"

    _, codes = await _enroll_and_confirm(client, admin_headers)

    # عاملٌ مؤكَّدٌ ولا استردادَ مُثبَت — ما زال مرفوضاً
    unproven = await client.put(
        "/admin/security", json={"admin_totp_required": True}, headers=admin_headers
    )
    assert unproven.status_code == 409

    proven = await client.post(
        "/auth/me/totp/recovery/verify",
        json={"recovery_code": codes[0]},
        headers=admin_headers,
    )
    assert proven.status_code == 200, proven.text
    # الإثباتُ يستهلك رمزاً حقيقياً — لا مربَّعٌ يُؤشَّر
    assert proven.json()["recovery_codes_remaining"] == totp.RECOVERY_CODE_COUNT - 1
    assert proven.json()["recovery_verified_at"]

    enabled = await client.put(
        "/admin/security", json={"admin_totp_required": True}, headers=admin_headers
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["admin_totp_required"] is True


async def test_an_enforced_admin_without_a_factor_can_only_enroll(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """المشرفُ المُلزَمُ بلا عامل: كلُّ بابٍ إداريٍّ مردود، وبابُ التسجيل مفتوح."""
    _, codes = await _enroll_and_confirm(client, admin_headers)
    await client.post(
        "/auth/me/totp/recovery/verify",
        json={"recovery_code": codes[0]},
        headers=admin_headers,
    )
    await client.put(
        "/admin/security", json={"admin_totp_required": True}, headers=admin_headers
    )

    other = await _second_admin(session_factory)

    refused = await client.get("/admin/settings/pricing", headers=other)
    assert refused.status_code == 403
    assert refused.json()["code"] == "totp_enrollment_required"

    # وبابُ الأمان مفتوحٌ له — وإلا كان الإلزامُ حلقةً مغلقة
    status = await client.get("/auth/me/totp", headers=other)
    assert status.status_code == 200
    assert status.json()["required"] is True
    assert status.json()["enrolled"] is False

    secret, _ = await _enroll_and_confirm(client, other)
    opened = await client.get("/admin/settings/pricing", headers=other)
    assert opened.status_code == 200

    # ومن أُلزم لا يملك إطفاء عامله — مفتاحٌ يُخرج منه الجميع ليس إلزاماً
    escape = await client.request(
        "DELETE",
        "/auth/me/totp",
        json={"code": _next_code(secret)},
        headers=other,
    )
    assert escape.status_code == 409
    assert escape.json()["code"] == "totp_enforcement_active"


async def test_support_is_not_forced_but_its_factor_still_applies(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    """المفتاحُ للـ`admin` (قرارُ المالك)، والعاملُ المؤكَّد يسري على صاحبه أياً كان دورُه."""
    _, codes = await _enroll_and_confirm(client, admin_headers)
    await client.post(
        "/auth/me/totp/recovery/verify",
        json={"recovery_code": codes[0]},
        headers=admin_headers,
    )
    await client.put(
        "/admin/security", json={"admin_totp_required": True}, headers=admin_headers
    )

    status = await client.get("/auth/me/totp", headers=support_headers)
    assert status.json()["required"] is False
    # ولا يُردّ عن مساراته وهو بلا عامل
    assert (await client.get("/admin/rides", headers=support_headers)).status_code == 200

    await _enroll_and_confirm(client, support_headers)
    body = await client.post(
        "/auth/login", json={"phone": "+962790000002", "password": ADMIN_PASSWORD}
    )
    assert body.json()["totp_required"] is True


async def test_only_admins_read_or_write_the_policy(
    client: AsyncClient, support_headers: dict
) -> None:
    assert (await client.get("/admin/security", headers=support_headers)).status_code == 403
    refused = await client.put(
        "/admin/security", json={"admin_idle_timeout_minutes": 15}, headers=support_headers
    )
    assert refused.status_code == 403


# --------------------------------------------------------- مهلة الخمول


@pytest.mark.parametrize("minutes", [1, 61, 1440])
async def test_the_idle_timeout_is_capped_at_sixty_minutes(
    client: AsyncClient, admin_headers: dict, minutes: int
) -> None:
    """السقفُ في الكود لا في يد المشرف: اللوحة تفتح مفاتيح المزوّدين والدفع."""
    response = await client.put(
        "/admin/security",
        json={"admin_idle_timeout_minutes": minutes},
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_staff_refresh_keys_expire_with_the_idle_timeout(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """الطبقةُ الأولى من المهلة: عمرُ مفتاح الـrefresh — لا عمودُ «آخرِ نشاط»."""
    await client.put(
        "/admin/security",
        json={"admin_idle_timeout_minutes": 10},
        headers=admin_headers,
    )
    redis = get_redis_client()

    async with session_factory() as session:
        admin_id = await session.scalar(select(User.id).where(User.phone == ADMIN_PHONE))
    await _forget_sessions(redis, admin_id)

    await _login(client)
    keys = [key async for key in redis.scan_iter(f"auth:refresh:{admin_id}:*")]
    assert len(keys) == 1
    ttl = await redis.ttl(keys[0])
    assert 0 < ttl <= 600

    # والراكبُ لا تمسّه السياسة: تطبيقُه لا يفتح مفتاح مزوّدٍ ولا طلبَ سحب
    from tests.helpers import RIDER, register

    rider = await register(client, RIDER)
    rider_id = uuid.UUID(rider["user"]["id"])
    rider_keys = [key async for key in redis.scan_iter(f"auth:refresh:{rider_id}:*")]
    assert await redis.ttl(rider_keys[0]) > 600


async def test_rotation_renews_the_window(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """التدويرُ لمرةٍ واحدة هو النبضة — فالنشاطُ يمدّ النافذة ولا يلمس عموداً."""
    await client.put(
        "/admin/security",
        json={"admin_idle_timeout_minutes": 10},
        headers=admin_headers,
    )
    redis = get_redis_client()
    async with session_factory() as session:
        admin_id = await session.scalar(
            select(User.id).where(User.phone == ADMIN_PHONE)
        )
    await _forget_sessions(redis, admin_id)

    body = await _login(client)
    refreshed = await client.post(
        "/auth/refresh", json={"refresh_token": body["tokens"]["refresh_token"]}
    )
    assert refreshed.status_code == 200

    keys = [key async for key in redis.scan_iter(f"auth:refresh:{admin_id}:*")]
    # الجلسةُ المدوَّرة وحدها: التدويرُ يحذف مفتاحَه ويكتب مفتاحاً جديداً
    assert len(keys) == 1
    assert 0 < await redis.ttl(keys[0]) <= 600


async def test_the_policy_write_leaves_an_audit_entry(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    from app.models.audit import AdminAuditLog

    await client.put(
        "/admin/security",
        json={"admin_idle_timeout_minutes": 15},
        headers=admin_headers,
    )
    async with session_factory() as session:
        rows = await session.scalar(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "security_settings")
        )
        assert rows == 1

    # وكتابةٌ لا تغيّر شيئاً لا تكتب قيداً — سجلٌّ يملؤه اللاشيء يخفي القرارات
    await client.put(
        "/admin/security",
        json={"admin_idle_timeout_minutes": 15},
        headers=admin_headers,
    )
    async with session_factory() as session:
        rows = await session.scalar(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "security_settings")
        )
        assert rows == 1
