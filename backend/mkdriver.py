"""كبتنٌ جديدٌ غيرُ معتمد — من باب `create_account` نفسِه لا بكتابةٍ يدوية."""
import asyncio
from datetime import UTC, datetime

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.schemas.auth import RegisterRequest
from app.services.auth.base import create_account


async def main() -> None:
    async with SessionLocal() as session:
        user = await create_account(
            session,
            phone="+962790011011",
            data=RegisterRequest(
                phone="790011011",
                country_code="JO",
                name="كبتنُ فحصِ الصور",
                password="TaxoTest123",
                role="driver",
            ),
            password_hash=hash_password("TaxoTest123"),
            phone_verified_at=datetime.now(UTC),
        )
        await session.commit()
        print("USER", user.id)


asyncio.run(main())
