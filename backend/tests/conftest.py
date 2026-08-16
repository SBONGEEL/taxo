from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from httpx_ws.transport import ASGIWebSocketTransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]

# قاعدة بيانات وقاعدة Redis منفصلتان عن التطوير — تُضبط قبل استيراد التطبيق
_TEST_DB_NAME = "taxo_test"
_TEST_REDIS_DB = 15


def _swap_db_name(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{name}"))


def _swap_redis_db(url: str, index: int) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{index}"))


_base_db_url = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://taxo:taxo@localhost:5432/taxo"
)
_base_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

os.environ["DATABASE_URL"] = _swap_db_name(_base_db_url, _TEST_DB_NAME)
os.environ["REDIS_URL"] = _swap_redis_db(_base_redis_url, _TEST_REDIS_DB)
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
# مفتاح Fernet ثابت للاختبارات — لا علاقة له بمفتاح التطوير أو الإنتاج
os.environ.setdefault(
    "CREDENTIALS_ENCRYPTION_KEY", "dGVzdC1vbmx5LWtleS10ZXN0LW9ubHkta2V5LXRlc3Q="
)

from app.core.config import get_settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.core.redis_client import close_redis_client, get_redis_client  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

get_settings.cache_clear()


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # env.py يقرأ الرابط من الإعدادات (المضبوطة أعلاه على قاعدة الاختبار)
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return cfg


@pytest.fixture(scope="session", autouse=True)
async def _create_test_database() -> AsyncIterator[None]:
    """ينشئ قاعدة اختبار نظيفة، يبني مخططها بالترحيلات، ويُسقطها في النهاية."""
    admin_url = _swap_db_name(_base_db_url, "postgres")
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")

    async with admin_engine.connect() as conn:
        await conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}"')
        await conn.exec_driver_sql(f'CREATE DATABASE "{_TEST_DB_NAME}"')

    # المخطط يُبنى من الترحيلات نفسها التي تعمل في الإنتاج — لا create_all —
    # حتى تختبر الاختبارات ما سيُنشر فعلاً. يعمل في خيط منفصل لأن env.py
    # يستدعي asyncio.run الذي لا يعمل داخل حلقة أحداث قائمة.
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")

    yield

    await engine.dispose()
    await close_redis_client()
    async with admin_engine.connect() as conn:
        await conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}"')
    await admin_engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    """كل اختبار يبدأ من جداول فارغة وRedis فارغ.

    مهام التوزيع تُوقف أولاً: مهمة ناجية من اختبار سابق ستقرأ رحلة حُذف صفها.
    """
    from app.services import dispatch, tracking

    await dispatch.shutdown()
    await tracking.shutdown()
    async with engine.begin() as conn:
        tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        await conn.exec_driver_sql(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
    await get_redis_client().flushdb()
    yield
    await dispatch.shutdown()
    await tracking.shutdown()


@pytest.fixture(autouse=True)
async def phone_verification(_clean_state) -> None:
    """عقد تحقُّقٍ وهمي في كل اختبار — لأن التسجيل يشترط إثبات الرقم.

    منذ المرحلة 8-ب لا حساب يُنشأ برقم غير محقق (SPEC القسم 4)، والمفتاح
    `otp_verification_enabled` مفعّلٌ افتراضاً. فبيئة الاختبار تشبه الإنتاج:
    مُحقِّقٌ مُهيأ وحساباتٌ محققة — لا مفتاحٌ مطفأ يخفي الحارس عن كل اختبار.
    ومن أراد اختبار غيابه يُعطّل العقد أو يُطفئ المفتاح صراحةً.

    الصفُّ يُكتب مباشرةً لا عبر `credentials_service.upsert`: ذاك يترك قيد
    تدقيقٍ في كل اختبار فيُفسد ما يعدّ القيود.
    """
    from app.core.crypto import get_cipher
    from app.models.enums import ProviderKey
    from app.models.provider_credential import ProviderCredential

    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        session.add(
            ProviderCredential(
                provider_key=ProviderKey.FIREBASE_AUTH,
                country_code=None,
                credentials=get_cipher().encrypt(
                    {"project_id": "taxo-test-project", "use_mock": True}
                ),
                is_active=True,
            )
        )
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac


@asynccontextmanager
async def ws_client() -> AsyncIterator[AsyncClient]:
    """عميل يفتح مقابس WebSocket على نفس تطبيق ASGI وفي نفس حلقة الأحداث.

    ليس fixture عمداً: ناقل httpx-ws يفتح مجموعة مهام anyio، وanyio يرفض
    الخروج منها في مهمة غير التي دخلتها — وpytest-asyncio ينفّذ تفكيك الـ
    fixture في مهمة أخرى. فتحُه داخل جسم الاختبار يبقي الدخول والخروج معاً.
    """
    transport = ASGIWebSocketTransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac


@pytest.fixture
def session_factory() -> async_sessionmaker:
    return async_sessionmaker(bind=engine, expire_on_commit=False)


async def _staff_headers(role: str, phone: str, name: str) -> dict[str, str]:
    """حسابات admin/support تُنشأ من اللوحة لا بالتسجيل الذاتي — ننشئها مباشرة."""
    from app.core.security import hash_password
    from app.models.enums import CountryCode, UserRole
    from app.models.user import User
    from app.services import token_service

    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        user = User(
            phone=phone,
            name=name,
            role=UserRole(role),
            country_code=CountryCode.JO,
            password_hash=hash_password("StaffSecret123"),
        )
        session.add(user)
        await session.commit()
        tokens = await token_service.issue_token_pair(get_redis_client(), user)

    return {"Authorization": f"Bearer {tokens.access_token}"}


@pytest.fixture
async def admin_headers() -> dict[str, str]:
    return await _staff_headers("admin", "+962790000001", "مشرف الاختبار")


@pytest.fixture
async def support_headers() -> dict[str, str]:
    return await _staff_headers("support", "+962790000002", "دعم الاختبار")


@pytest.fixture(autouse=True)
def document_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """جذر تخزينٍ خاص بكل اختبار (المرحلة 9-ب).

    بغيره يكتب اختبارُ الرفع في مجلد المستودع فيتسرب ملفٌ إلى Git، وتتقاسم
    الاختبارات مجلداً واحداً فيرى أحدُها بقايا الآخر. و`core/storage.py`
    يقرأ الجذر عند كل نداء لا عند الاستيراد — ولهذا السبب بالضبط.
    """
    from app.core.config import settings

    root = tmp_path / "documents"
    root.mkdir()
    monkeypatch.setattr(settings, "document_storage_root", root)
    return root


@pytest.fixture(autouse=True)
def fast_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """يضغط مهل التوزيع.

    قيم SPEC الحقيقية (20 ثانية للعرض، دقيقتان للمحاولة كلها) صحيحة في
    التشغيل ومستحيلة في اختبار. عدد المحاولات (5) يبقى كما هو لأنه جزء من
    السلوك المُختبَر لا من سرعته.

    **وهذه الأرقامُ لا تُمسّ** (2026-08-16، بعد محاولتين خاطئتين). والقصةُ
    تستحق البقاء لأن درسَها أعمُّ من التوزيع:

    كان `test_card_payments::test_card_money_never_passes_through_the_riders_
    wallet` يفشل في التشغيل الكامل وحدَه بـ`ride_offer_expired` وينجح منفرداً —
    **إنذارٌ كاذبٌ في كل تشغيل**، وهو أسوأُ ما يصير إليه اختبار: يُفحص مرةً ثم
    يُتجاهَل، ويُتجاهَل معه ما يصدق. وسببُه سباقٌ في **المساعد** لا في المُختبَر:
    `accepted_ride` ترى العرضَ في Redis ثم تُرسل `POST /accept` في **رحلةٍ
    ثانيةٍ على الشبكة**، وتحت الحمل يتجاوز ما بينهما مهلةَ العرض.

    ثم كُسر اختباران آخران في محاولتَي إصلاحه، وكلاهما بسبب لمس رقمٍ هنا:

    1. **رفعُ مهلة العرض إلى عشرٍ** ظنّاً أنه مجانيّ (الحلقةُ محكومةٌ
       بـ`TOTAL_TIMEOUT_SECONDS` فلا يطول اختبار). وكان خطأً: **نسبةُ العرض إلى
       الكلّية تقرّر كم كبتناً يُجرَّب** لا طولَ الاختبار وحدَه — فبعشرٍ مقابل
       خمسٍ لا يدور العرضُ على كبتنٍ ثانٍ أبداً، وسقط
       `test_admin_reports::test_top_drivers_are_ranked_by_completed_rides`.
    2. **رفعُ الكلّية إلى خمسَ عشرة** لتتّسع الفرص. فصار `no_driver_found` يصل
       بعد خمسَ عشرةَ ثانية، وسقط `test_ws::test_rider_is_told_when_no_driver_
       is_found` على مهلة استقبال المقبس.

    **والدرس: رقمٌ في تجهيزةٍ مشتركة نصفُ قطرِ أثره هو المجموعةُ كلُّها**، وأيُّ
    تعديلٍ فيه يُصلح واحداً ويكسر ما لم يخطر ببال. **والإصلاحُ الصحيح كان في
    المساعد نفسِه** حيث السباق: `helpers.accepted_ride` تعيد المحاولة حين تنقضي
    المهلة، فتصير لها ثلاثُ فرصٍ في النافذة الأصلية بدل واحدة — **بلا أن يتغيّر
    توقيتٌ واحدٌ يقرؤه اختبارٌ آخر**.

    **ومن يقيس انقضاءَ المهلة يضبطها بنفسه** (`test_silence_expires_the_offer_
    and_moves_on`): المهلةُ موضوعُ ذلك الاختبار لا ظرفُه — ويبقى كذلك وإن وافقت
    قيمتُه المشتركةَ اليوم، فلا يصمت إن مُسّت غداً.
    """
    from app.services import dispatch, tracking

    monkeypatch.setattr(dispatch, "OFFER_TIMEOUT_SECONDS", 2)
    monkeypatch.setattr(dispatch, "TOTAL_TIMEOUT_SECONDS", 5)
    monkeypatch.setattr(dispatch, "IDLE_POLL_SECONDS", 0.2)
    # المراقبة تسأل أسرع؛ حكمُها (اختفاء الحضور) يبقى كما هو
    monkeypatch.setattr(tracking, "CHECK_INTERVAL_SECONDS", 0.2)


@pytest.fixture(autouse=True)
def stub_mapbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """يستبدل نداء Mapbox وحده — قراءة التوكن من عقود المزودين تبقى حقيقية."""
    from app.services import directions
    from app.services.directions import Route
    from tests.helpers import MAPBOX_SECRET, STUB_ROUTE

    async def _fetch_route(token: str, *waypoints, with_geometry: bool = False):
        assert token == MAPBOX_SECRET, "التوكن السري يجب أن يأتي من جدول العقود"
        # **المسافةُ تكبر بعدد السيقان** (المرحلة 12-ب): بغير ذلك تعطي رحلةٌ
        # بمحطتين نفسَ مسافة رحلةٍ مباشرة، فيمرّ تسعيرٌ لا يمرّ بالمحطات
        legs = max(1, len(waypoints) - 1)
        return Route(
            distance_km=STUB_ROUTE.distance_km * legs,
            duration_min=STUB_ROUTE.duration_min * legs,
            # **والشكلُ يُعطى حين يُطلب وحدَه** (البند ٨): البديلُ يحاكي المزوّد
            # لا يبسّطه — فاختبارٌ يمرّ مع بديلٍ يعطي شكلاً دائماً لا يحرس
            # القاعدةَ التي تمنع طلبَه على مسار التسعير
            geometry=(
                [[point.lng, point.lat] for point in waypoints]
                if with_geometry
                else None
            ),
        )

    monkeypatch.setattr(directions, "fetch_route", _fetch_route)


@pytest.fixture
async def jordan_settings(session_factory) -> None:
    """تسعيرة الأردن + عقد Mapbox مفعّل — أدنى ما تحتاجه رحلة."""
    from decimal import Decimal

    from app.models.enums import CountryCode, ProviderKey, VehicleCategory
    from app.models.pricing import PricingRule
    from app.services.providers import credentials as credentials_service
    from tests.helpers import CANCELLATION_FEE, MAPBOX_SECRET

    async with session_factory() as session:
        for category in VehicleCategory:
            session.add(
                PricingRule(
                    country_code=CountryCode.JO,
                    vehicle_category=category,
                    base_fare=Decimal("1.000"),
                    price_per_km=Decimal("0.500"),
                    price_per_min=Decimal("0.100"),
                    minimum_fare=Decimal("2.000"),
                    cancellation_fee=Decimal(CANCELLATION_FEE),
                )
            )
        await credentials_service.upsert(
            session,
            provider_key=ProviderKey.MAPBOX,
            country_code=None,
            values={"public_token": "pk.test", "secret_token": MAPBOX_SECRET},
            is_active=True,
        )
        await session.commit()


@pytest.fixture
async def jordan_wallet(session_factory) -> None:
    """محفظة الأردن مفعّلة بالتحويل وبحدود مضبوطة — أدنى ما يحتاجه تحويل.

    المفتاحان يُرفعان صراحةً: غياب الصف يعني معطّلاً، ولا اختبار يفترض غير ذلك.
    """
    from decimal import Decimal

    from app.models.enums import CountryCode, FeatureKey
    from app.models.feature_flag import FeatureFlag
    from app.models.wallet_setting import WalletSetting
    from tests.helpers import (
        TRANSFER_DAILY_LIMIT,
        TRANSFER_MONTHLY_LIMIT,
        MIN_WITHDRAWAL,
    )

    async with session_factory() as session:
        for key in (FeatureKey.WALLET_ENABLED, FeatureKey.WALLET_TRANSFER_ENABLED):
            session.add(
                FeatureFlag(
                    country_code=CountryCode.JO, feature_key=key.value, enabled=True
                )
            )
        session.add(
            WalletSetting(
                country_code=CountryCode.JO,
                transfer_daily_limit=Decimal(TRANSFER_DAILY_LIMIT),
                transfer_monthly_limit=Decimal(TRANSFER_MONTHLY_LIMIT),
                min_withdrawal_amount=Decimal(MIN_WITHDRAWAL),
            )
        )
        await session.commit()


def _signup(phone: str, name: str, country: str, role: str) -> dict:
    """حمولة تسجيلٍ صالحة — ومنها **إثبات ملكية الرقم**.

    منذ المرحلة 8-ب لا يُقبل تسجيلٌ بلا إثبات (SPEC القسم 4)، فالحمولة
    «الصالحة» تحمله. والرمز من المُحقِّق الوهمي الذي يثبّته `phone_verification`.
    """
    from app.core.phone import normalize_phone
    from app.services.firebase_auth import mock_token

    return {
        "phone": phone,
        "name": name,
        "password": "SuperSecret123",
        "country_code": country,
        "role": role,
        "verification_token": mock_token(normalize_phone(phone, country)),
    }


@pytest.fixture
def rider_payload() -> dict:
    return _signup("0791234567", "راكب تجريبي", "JO", "rider")


@pytest.fixture
def driver_payload() -> dict:
    return _signup("0917654321", "كبتن تجريبي", "LY", "driver")
