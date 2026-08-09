from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
os.environ.setdefault("SMS_PROVIDER", "")

from app.core.config import get_settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.core.redis_client import close_redis_client, get_redis_client  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
async def _create_test_database() -> AsyncIterator[None]:
    """ينشئ قاعدة اختبار نظيفة ويُسقطها في النهاية."""
    admin_url = _swap_db_name(_base_db_url, "postgres")
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")

    async with admin_engine.connect() as conn:
        await conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}"')
        await conn.exec_driver_sql(f'CREATE DATABASE "{_TEST_DB_NAME}"')

    async with engine.begin() as conn:
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS postgis")
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()
    await close_redis_client()
    async with admin_engine.connect() as conn:
        await conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}"')
    await admin_engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    """كل اختبار يبدأ من جداول فارغة وRedis فارغ."""
    async with engine.begin() as conn:
        tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        await conn.exec_driver_sql(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
    await get_redis_client().flushdb()
    yield


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac


@pytest.fixture
def session_factory() -> async_sessionmaker:
    return async_sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def rider_payload() -> dict:
    return {
        "phone": "0791234567",
        "name": "راكب تجريبي",
        "password": "SuperSecret123",
        "country_code": "JO",
        "role": "rider",
    }


@pytest.fixture
def driver_payload() -> dict:
    return {
        "phone": "0917654321",
        "name": "كبتن تجريبي",
        "password": "SuperSecret123",
        "country_code": "LY",
        "role": "driver",
    }
