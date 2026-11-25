docker exec -i taxo-backend python - <<'PY'
import asyncio, time
from app.core.redis_client import get_redis_client
from app.services import releases as r
async def main():
    c = get_redis_client()
    seen = await c.hgetall(r.OLD_KEY_SEEN); moved = await c.hgetall(r.OLD_KEY_MOVED)
    first = min((int(v) for v in seen.values()), default=None)
    print(f"seen_devices={len(seen)} moved_devices={len(moved)} asks={await c.get(r.OLD_KEY_ASKS)}"
          f" first_seen={time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(first)) if first else '-'}")
asyncio.run(main())
PY
