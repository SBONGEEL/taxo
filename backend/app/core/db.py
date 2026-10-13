from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# **حارسُ الكتابة يُسجَّل حيث تولد الجلسة** (SPEC §٧٣-ج/٧): كلُّ من يكتب يمرّ بها، فلا مستوردَ ينساه
import app.core.money_guard  # noqa: E402,F401

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_pre_ping=True,
    # **ميزانيّةٌ لكلِّ عمليّة** (§٧٥-د/٢) — الخلفيةُ أربعُ عمليّاتٍ على الإنتاج
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """جلسة لكل طلب: commit عند النجاح، rollback عند أي استثناء."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
