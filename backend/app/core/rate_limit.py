from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int


async def hit(
    redis: Redis, key: str, *, limit: int, window_seconds: int
) -> RateLimitResult:
    """نافذة ثابتة بسيطة على Redis: INCR + EXPIRE عند أول ضربة."""
    full_key = f"ratelimit:{key}"
    pipe = redis.pipeline()
    pipe.incr(full_key)
    pipe.ttl(full_key)
    count, ttl = await pipe.execute()

    if count == 1 or ttl is None or ttl < 0:
        await redis.expire(full_key, window_seconds)
        ttl = window_seconds

    if count > limit:
        return RateLimitResult(False, 0, int(ttl))
    return RateLimitResult(True, limit - int(count), int(ttl))


async def reset(redis: Redis, key: str) -> None:
    """يُستدعى بعد نجاح العملية حتى لا تُعاقب المحاولات الناجحة."""
    await redis.delete(f"ratelimit:{key}")
