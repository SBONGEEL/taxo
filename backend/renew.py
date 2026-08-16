import asyncio
from app.core.redis_client import get_redis_client
from app.services import subscriptions

async def main() -> None:
    redis = get_redis_client()
    print("renewed:", await subscriptions.renew_due(redis))

asyncio.run(main())
