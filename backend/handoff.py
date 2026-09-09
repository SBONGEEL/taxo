# -*- coding: utf-8 -*-
"""يصدر رمزَ تسليمٍ إلى تطبيق الكبتن — ولا يطبع كلمةَ مرور.

الرمزُ عمرُه ثوانٍ ويُستهلك مرّةً واحدة؛ يُكتب في ملفٍّ لا في السجل.
"""
import asyncio
import sys

import httpx

sys.path.insert(0, "/app")
from scenario_demo import API, DRIVER_M, login  # noqa: E402


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        h = await login(c, DRIVER_M[0])
        r = await c.post(f"{API}/auth/handoff", headers=h, json={"target": "driver"})
        if r.status_code != 200:
            print("  فشل:", r.status_code, str(r.text)[:200])
            raise SystemExit(3)
        token = r.json()["token"]
        with open("/tmp/handoff.txt", "w", encoding="utf-8") as fh:
            fh.write(token)
        print("  رمزٌ صدر · طولُه", len(token), "· عمرُه", r.json()["expires_in"], "ثانية")


asyncio.run(main())
