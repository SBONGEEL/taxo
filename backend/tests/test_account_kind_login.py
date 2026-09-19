"""الدخولُ والتسجيلُ والاستعادةُ على المفتاح المركّب — 1-أ/4 (`SPEC-DELIVERY.md` §D9.1).

**ما يُقاس**: رقمٌ واحدٌ يحمل حسابَ `taxo` وحسابَ `market` معاً (قرارُ المالك §D1.4)،
**فكلُّ بابٍ يبحث بالرقم يجب أن يعرف أيَّ الحسابين يعني** — والتطبيقُ المُعلَن يقول،
والسكوتُ `taxo`. وحسابُ `market` يُكتب في القاعدة **قبل** حساب `taxo` في كلِّ
اختبار عمداً: بحثٌ بالرقم وحده يعيد أوّلَ صفٍّ، فيقع على الخطأ ويحمرّ بدل أن يمرّ
صدفةً.

**ولا تطبيقَ للسوق بعد** (`ClientApp` بلا قيمته حتى المرحلة 7)، فحسابُ `market`
يُقاس من الخدمة لا من باب الدخول.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.core import app_scope
from app.core.phone import normalize_phone
from app.core.redis_client import get_redis_client
from app.core.security import hash_password, verify_password
from app.models.enums import AccountKind, ClientApp, CountryCode, UserRole
from app.models.user import User
from app.services.firebase_auth import mock_token
from tests.helpers import RIDER, register

PHONE = normalize_phone(RIDER["phone"], RIDER["country_code"])
MARKET_PASSWORD = "MarketSecret456"


async def _market_account_first(session_factory) -> None:
    """حسابُ زبونٍ بالرقم نفسِه — **يُكتب قبل حساب الراكب** (انظر رأس الملف)."""
    async with session_factory() as session:
        session.add(
            User(
                phone=PHONE,
                name="زبون السوق",
                role=UserRole.RIDER,
                country_code=CountryCode.JO,
                account_kind=AccountKind.MARKET,
                password_hash=hash_password(MARKET_PASSWORD),
            )
        )
        await session.commit()


async def _row(session_factory, kind: AccountKind) -> User:
    async with session_factory() as session:
        return await session.scalar(
            select(User).where(User.phone == PHONE, User.account_kind == kind)
        )


# ---------------------------------------------------------------- الخريطة


def test_every_client_app_names_its_account_kind() -> None:
    """**خريطةٌ كاملةٌ على `ClientApp`**، و`None` ⇒ `taxo` (عميلٌ لم يُعلن)."""
    assert set(app_scope._ACCOUNT_KIND) == set(ClientApp)
    assert app_scope.account_kind_for(None) is AccountKind.TAXO


# ---------------------------------------------------------------- التسجيل


async def test_a_number_with_a_market_account_can_still_register_its_taxo_account(
    client: AsyncClient, session_factory
) -> None:
    """الرفضُ لحسابٍ ثانٍ **من النوع نفسِه** وحدَه — لا لكلِّ رقمٍ رآه الجدول."""
    await _market_account_first(session_factory)

    body = await register(client, RIDER)

    taxo = await _row(session_factory, AccountKind.TAXO)
    assert taxo is not None and str(taxo.id) == body["user"]["id"]


# ------------------------------------------------------------------ الدخول


async def test_login_reaches_the_taxo_account_and_not_the_market_one(
    client: AsyncClient, session_factory
) -> None:
    """كلمةُ الراكب تفتح حسابَه، **وكلمةُ الزبون لا تفتح شيئاً** من تطبيق الراكب —
    بجوابِ الكلمة الخاطئة نفسِه، فلا يُكشف أن للرقم حساباً آخر."""
    await _market_account_first(session_factory)
    body = await register(client, RIDER)

    ok = await client.post(
        "/auth/login",
        json={"phone": RIDER["phone"], "country_code": "JO",
              "password": RIDER["password"], "app": "rider"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["user"]["id"] == body["user"]["id"]

    wrong = await client.post(
        "/auth/login",
        json={"phone": RIDER["phone"], "country_code": "JO",
              "password": MARKET_PASSWORD, "app": "rider"},
    )
    assert wrong.status_code == 401, wrong.text
    assert wrong.json()["code"] == "invalid_credentials"


async def test_the_login_limit_is_kept_per_number_and_kind(
    client: AsyncClient, session_factory
) -> None:
    """**السقفُ على الرقم ونوعِ الحساب** (Q42): المفتاحُ يحمل النوع."""
    await register(client, RIDER)
    await client.post(
        "/auth/login",
        json={"phone": RIDER["phone"], "country_code": "JO",
              "password": "WrongPassword999", "app": "rider"},
    )
    redis = get_redis_client()
    assert await redis.exists(f"ratelimit:login:phone:taxo:{PHONE}")
    assert not await redis.exists(f"ratelimit:login:phone:{PHONE}")


async def test_the_market_account_authenticates_only_as_market(session_factory) -> None:
    """من الخدمة (لا تطبيقَ للسوق بعد): النوعُ يختار الصفّ، والكلمةُ تُفحص عليه."""
    from app.core.exceptions import InvalidCredentials
    from app.services.auth.password import PasswordAuthStrategy

    await _market_account_first(session_factory)
    strategy = PasswordAuthStrategy()
    async with session_factory() as session:
        user = await strategy.authenticate(
            session, PHONE, MARKET_PASSWORD, account_kind=AccountKind.MARKET
        )
        assert user.account_kind is AccountKind.MARKET
        try:
            await strategy.authenticate(
                session, PHONE, MARKET_PASSWORD, account_kind=AccountKind.TAXO
            )
        except InvalidCredentials:
            pass
        else:  # pragma: no cover - هو العطبُ نفسُه
            raise AssertionError("كلمةُ الزبون فتحت حسابَ الراكب")


# ------------------------------------------------------------------ الاستعادة


async def test_a_reset_rewrites_the_declared_account_alone(
    client: AsyncClient, session_factory
) -> None:
    """الاستعادةُ من تطبيق الراكب (أو بلا إعلان) تمسّ حسابَ `taxo` وحدَه."""
    await _market_account_first(session_factory)
    await register(client, RIDER)

    reset = await client.post(
        "/auth/password-reset",
        json={"phone": RIDER["phone"], "country_code": "JO",
              "verification_token": mock_token(PHONE),
              "new_password": "BrandNewSecret789"},
    )
    assert reset.status_code == 200, reset.text

    taxo = await _row(session_factory, AccountKind.TAXO)
    market = await _row(session_factory, AccountKind.MARKET)
    assert verify_password("BrandNewSecret789", taxo.password_hash)
    assert verify_password(MARKET_PASSWORD, market.password_hash)
