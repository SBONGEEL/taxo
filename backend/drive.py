# -*- coding: utf-8 -*-
"""يقود رحلةً حقيقيةً خطوةً خطوة، ليُلتقط كلُّ حالٍ من شاشةٍ حقيقية.

**ولا حالَ تُصنع**: كلُّ خطوةٍ نداءٌ على البابِ نفسِه الذي يناديه التطبيق
(`POST /rides` · `/accept` · `/start` · `/complete`) — **فما يُلتقط حالُ نظامٍ
سبّبها مسارٌ حقيقيّ**، لا رسمٌ ولا صفٌّ مكتوبٌ باليد.

**والعناوينُ أردنيةٌ بحتة** من `scenario_demo.py`: «دوار الداخلية، عمّان» →
«شارع الرينبو، جبل عمّان». **صفرُ ذكرٍ لليبيا.**

    docker compose exec -T backend python /app/drive.py <خطوة>

الخطوات: seed · request · accept · arrive · start · complete · state
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys

import httpx

sys.path.insert(0, "/app")

from scenario_demo import (  # noqa: E402
    API,
    DRIVER_M,
    RIDER,
    clear_login_limits,
    ensure_vehicle,
    go_online,
    login,
    seed_accounts,
)

STATE = pathlib.Path("/tmp/drive-state.json")
PICKUP = {"lat": 31.9539, "lng": 35.9106}
DROPOFF = {"lat": 31.9515, "lng": 35.9239}


def _read() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def _write(d: dict) -> None:
    STATE.write_text(json.dumps(d, ensure_ascii=False))


async def run(step: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        if step == "seed":
            await clear_login_limits(quiet=True)
            ids = await seed_accounts()
            print("  ✓ الحسابات جاهزة")
            print("  الراكب :", RIDER[0], "—", RIDER[1])
            print("  الكبتن :", DRIVER_M[0], "—", DRIVER_M[1])
            _write({"ids": {k: str(v) for k, v in ids.items()}})
            return

        rider = await login(client, RIDER[0])
        driver = await login(client, DRIVER_M[0])
        st = _read()

        if step == "request":
            await ensure_vehicle(client, driver, "77-1234")
            await go_online(client, driver)
            r = await client.post(
                f"{API}/rides",
                headers=rider,
                json={
                    "pickup": PICKUP,
                    "dropoff": DROPOFF,
                    "pickup_address": "دوار الداخلية، عمّان",
                    "dropoff_address": "شارع الرينبو، جبل عمّان",
                    "vehicle_category": "economy",
                    "gender_preference": "any",
                },
            )
            r.raise_for_status()
            ride = r.json()
            st["ride"] = ride["id"]
            _write(st)
            print("  ✓ طُلبت رحلةٌ:", ride["id"], "· الحال:", ride.get("status"))
            print("  دوار الداخلية، عمّان ← شارع الرينبو، جبل عمّان")
            return

        rid = st.get("ride")
        if not rid:
            sys.exit("لا رحلةَ في الحال — شغّل request أوّلاً")

        if step == "accept":
            for _ in range(60):
                a = await client.post(f"{API}/rides/{rid}/accept", headers=driver)
                if a.status_code == 200:
                    print("  ✓ قَبِل الكبتن · الحال:", a.json().get("status"))
                    return
                await asyncio.sleep(0.25)
            sys.exit("لم يصل العرضُ إلى الكبتن")

        if step == "arrive":
            a = await client.post(f"{API}/rides/{rid}/arrive", headers=driver)
            print("  ->", a.status_code, a.json().get("status", a.text[:120]))
            return

        if step == "start":
            a = await client.post(f"{API}/rides/{rid}/start", headers=driver)
            print("  ->", a.status_code, a.json().get("status", a.text[:120]))
            return

        if step == "complete":
            a = await client.post(f"{API}/rides/{rid}/complete", headers=driver)
            print("  ->", a.status_code, a.json().get("status", a.text[:120]))
            return

        if step == "state":
            a = await client.get(f"{API}/rides/{rid}", headers=rider)
            print("  ", a.status_code, a.json().get("status"))
            return

    sys.exit("خطوةٌ غيرُ معروفة: " + step)


asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else "state"))
