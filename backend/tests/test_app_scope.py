"""حارسُ الدور على باب الدخول (`core/app_scope.py`، قرارُ المالك 2026-08-15).

**الواقعةُ التي وُجد لأجلها**: كتب المالكُ بياناتِ كبتنٍ في تطبيق الراكب فدخل.
والحارسُ يُرفض في الخلفية لا في الواجهة، ولذلك يُختبر من باب HTTP نفسِه.

**والمسحُ من الجدول لا من قائمةٍ مكتوبة**: كلُّ زوجٍ (تطبيق × دور) يُجرَّب،
فتطبيقٌ رابعٌ أو دورٌ خامسٌ يُضاف غداً يدخل هذه الاختباراتِ تلقائياً — وهي
نفسُ قاعدةِ `test_settlement.py`: اختبارٌ يشتقّ من التعداد لا يعدّ قيمَ اليوم.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.app_scope import ClientApp, _ROLES
from app.models.enums import UserRole
from tests import helpers

STAFF_PASSWORD = "StaffSecret123"

PWA_APPS = (ClientApp.RIDER, ClientApp.DRIVER)


async def _login(
    client: AsyncClient, phone: str, password: str, app: ClientApp | None
) -> tuple[int, dict]:
    response = await client.post(
        "/auth/login",
        json={
            "phone": phone,
            "password": password,
            "country_code": "JO",
            **({} if app is None else {"app": app.value}),
        },
    )
    return response.status_code, response.json()


@pytest.mark.parametrize("app", list(ClientApp))
@pytest.mark.parametrize("role", [UserRole.RIDER, UserRole.DRIVER])
async def test_every_app_and_self_signup_role_pair_is_decided(
    client: AsyncClient, app: ClientApp, role: UserRole
) -> None:
    """كلُّ زوجٍ يُجرَّب: يُقبل إن كان الدورُ في التطبيق، ويُرفض ٤٠٣ إن لم يكن.

    ويشمل ذلك **الاتجاه المعاكس** الذي طلبه المالك: راكبٌ في تطبيق الكبتن كما
    كبتنٌ في تطبيق الراكب — والعطبُ الذي رآه كان في اتجاهٍ واحدٍ فقط.
    """
    payload = (helpers.RIDER if role is UserRole.RIDER else helpers.DRIVER) | {
        "role": role.value
    }
    await helpers.register(client, payload)

    status, body = await _login(client, payload["phone"], payload["password"], app)

    if role in _ROLES[app]:
        assert status == 200, body
        assert body["tokens"] is not None
    else:
        assert status == 403, body
        assert body["code"] == "wrong_app_for_role"
        # النصُّ يقول **أين يذهب**: «ممنوع» وحدَها تجعله يسجّل حساباً ثانياً
        assert "ادخل من" in body["message"]


@pytest.mark.parametrize("app", PWA_APPS)
@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.SUPPORT])
async def test_staff_accounts_enter_neither_pwa(
    client: AsyncClient, app: ClientApp, role: UserRole
) -> None:
    """قرارُ المالك نصّاً: `admin`/`support` لا يدخلان تطبيقَي الراكب والكبتن."""
    from app.core.security import hash_password
    from app.models.enums import CountryCode
    from app.models.user import User
    from tests.conftest import engine

    from sqlalchemy.ext.asyncio import async_sessionmaker

    phone = "+96279000009" + ("1" if role is UserRole.ADMIN else "2")
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        session.add(
            User(
                phone=phone,
                name="موظف",
                role=role,
                country_code=CountryCode.JO,
                password_hash=hash_password(STAFF_PASSWORD),
            )
        )
        await session.commit()

    status, body = await _login(client, phone, STAFF_PASSWORD, app)
    assert status == 403, body
    assert body["code"] == "wrong_app_for_role"

    # واللوحةُ تقبله — وإلا كان الحارسُ قفلاً على كل الأبواب لا على بابٍ خطأ
    status, body = await _login(client, phone, STAFF_PASSWORD, ClientApp.PANEL)
    assert status == 200, body


async def test_a_client_that_declares_nothing_still_logs_in(
    client: AsyncClient,
) -> None:
    """غيابُ الإعلان يمرّ: هذا يمنع لبسَ الأدوار، وليس بابَ مصادقةٍ ثانياً.

    ولولاه لأخرجت إضافةُ الحارس كلَّ عميلٍ قائمٍ — و`curl` وأدواتِ الفحص معه.
    """
    await helpers.register(client, helpers.RIDER)
    status, body = await _login(
        client, helpers.RIDER["phone"], helpers.RIDER["password"], None
    )
    assert status == 200, body


async def test_signing_up_from_the_wrong_app_is_refused_before_the_row(
    client: AsyncClient,
) -> None:
    """حسابٌ يولد مقفلاً لا يُنشأ: التسجيلُ يُرفض قبل أن يُكتب الصف."""
    from app.core.phone import normalize_phone
    from app.services.firebase_auth import mock_token

    payload = helpers.DRIVER | {
        "verification_token": mock_token(
            normalize_phone(helpers.DRIVER["phone"], "JO")
        ),
        "app": ClientApp.RIDER.value,
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "wrong_app_for_role"

    # ولا صفَّ خلفه: الدخولُ بعده يقول «لا يوجد حساب» لا «كلمة مرور خاطئة»
    status, _ = await _login(
        client, helpers.DRIVER["phone"], helpers.DRIVER["password"], ClientApp.DRIVER
    )
    assert status == 401
