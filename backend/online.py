# -*- coding: utf-8 -*-
"""يُشعل الكبتن ويطبع جوابَ كلِّ باب — فلا يُقرأ صمتٌ نجاحاً."""
import asyncio
import sys

import httpx

sys.path.insert(0, "/app")
from scenario_demo import API, DRIVER_M, login  # noqa: E402


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        h = await login(c, DRIVER_M[0])
        r1 = await c.post(f"{API}/drivers/me/online", headers=h)
        print("  online   ->", r1.status_code, str(r1.text)[:200])
        r2 = await c.post(
            f"{API}/drivers/me/location",
            headers=h,
            json={"lat": 31.9560, "lng": 35.9100, "heading": 45},
        )
        print("  location ->", r2.status_code, str(r2.text)[:200])
        r3 = await c.get(f"{API}/drivers/me", headers=h)
        d = r3.json() if r3.status_code == 200 else {}
        drv = d.get("driver", {})
        print("  الحال    :", drv.get("status"), "· متّصل:", drv.get("is_online"))


asyncio.run(main())
