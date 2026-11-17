import asyncio
from sqlalchemy import text
from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
R="21165ca8-a669-4eb4-a1c8-67bdd56fdc42"; C="b349a918-c679-4c82-b541-788be5773316"
async def main():
    async with SessionLocal() as s:
        await s.execute(text("SET TRANSACTION READ ONLY"))
        for r in await s.execute(text("select id::text, status, final_fare, created_at from rides where rider_id=:r and created_at > now()-interval '2 hours' order by created_at"),{"r":R}): print("RIDE",tuple(r))
        for r in await s.execute(text("select owner_id::text=:r as is_rider, owner_type, type, amount, balance_after, ride_id::text, created_at from wallet_transactions where created_at > now()-interval '2 hours' order by created_at"),{"r":R}): print("TX",tuple(r))
        for r in await s.execute(text("select ride_id::text, method, status, amount from payments where created_at > now()-interval '2 hours'")): print("PAY",tuple(r))
        for r in await s.execute(text("select count(*) from ride_cancellation_charges where created_at > now()-interval '2 hours'")): print("CANCEL_CHARGES",tuple(r))
        await s.rollback()
    red = get_redis_client()
    keys=[k async for k in red.scan_iter("geo:presence:*")]
    print("PRESENCE_KEYS", len(keys))
asyncio.run(main())
