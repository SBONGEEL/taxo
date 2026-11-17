"""بروفةُ ليبيا المخفيّة على الإنتاج (أمرُ المالك ١٧/١١) — حسابا التجربة في طرابلس عبر الأبواب الحقيقيّة.
لا يطبع رمزاً ولا كلمةَ مرور. يكتب السجلَّ في rehearsal-out.json.
"""
import asyncio, json, time, uuid, sys
import httpx, websockets
from pathlib import Path

API = "https://api.tajora.ly/api/v1"
WS = API.replace("https://", "wss://") + "/ws"
ACCOUNTS_FILE = Path("/mnt/c/Users/loly3/.taxo-secrets/aldeeb-accounts.txt")  # مسارُ ملفّ حسابات التجربة — لا قيمةَ سرٍّ هنا
PICKUP = {"lat": 32.89520, "lng": 13.18020}   # ميدان الشهداء
DROPOFF = {"lat": 32.88340, "lng": 13.17150}  # قرب شارع عمر المختار
CAP_START = (32.89800, 13.18300)
LOG = []

def log(step, **kw):
    kw = {"t": time.strftime("%H:%M:%S"), "step": step, **kw}
    LOG.append(kw)
    print(json.dumps(kw, ensure_ascii=False)[:400], flush=True)

def creds():
    d = {}
    for line in open(ACCOUNTS_FILE, encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1); d[k] = v
    return d

async def login(http, phone, password, app):
    r = await http.post("/auth/login", json={"phone": phone, "password": password, "country_code": "LY", "app": app})
    r.raise_for_status()
    j = r.json()
    return j.get("access_token") or j["tokens"]["access_token"], j.get("user", {}).get("id")

def H(tok): return {"Authorization": f"Bearer {tok}"}

class Captain:
    def __init__(self, tok):
        self.tok, self.lat, self.lng = tok, *CAP_START
        self.offers = asyncio.Queue(); self.sock = None; self.stop = False
    async def run(self):
        self.sock = await websockets.connect(f"{WS}/driver?token={self.tok}&device_id=ly-rehearsal", open_timeout=30, ping_interval=20)
        asyncio.create_task(self.beat())
        async for raw in self.sock:
            f = json.loads(raw)
            if f.get("type") == "ride_offer": await self.offers.put(f.get("ride") or {})
            elif f.get("type") == "location_request": await self.send()
            elif f.get("type") in ("connected",): log("ws_driver_connected", online=True)
    async def send(self):
        await self.sock.send(json.dumps({"type": "location", "lat": self.lat, "lng": self.lng, "heading": 90}))
    async def beat(self):
        while not self.stop:
            try: await self.send()
            except Exception: return
            await asyncio.sleep(2)
    async def move(self, to, secs=8):
        a = (self.lat, self.lng)
        for k in range(1, secs + 1):
            self.lat = a[0] + (to["lat"] - a[0]) * k / secs; self.lng = a[1] + (to["lng"] - a[1]) * k / secs
            await asyncio.sleep(1)

async def ride(http, rt, ct, cap, method, cancel=False):
    est = await http.post("/rides/estimate", headers=H(rt), json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"})
    log(f"estimate_{method}", status=est.status_code, body=(est.json() if est.status_code == 200 else est.text[:300]))
    r = await http.post("/rides", headers=H(rt), json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", "payment_method": method})
    log(f"request_{method}{'_cancel' if cancel else ''}", status=r.status_code, body=r.text[:300] if r.status_code != 201 else None)
    if r.status_code != 201: return None
    rid = r.json()["id"]
    if cancel:
        await asyncio.sleep(3)
        c = await http.post(f"/rides/{rid}/cancel", headers=H(rt), json={})
        log("cancel", ride=rid, status=c.status_code, body=c.text[:300])
        # عرضٌ وصل قبل الإلغاء يُفرَّغ
        while not cap.offers.empty(): cap.offers.get_nowait()
        return rid
    try:
        offer = await asyncio.wait_for(cap.offers.get(), 90)
    except asyncio.TimeoutError:
        log("no_offer_in_90s", ride=rid); await http.post(f"/rides/{rid}/cancel", headers=H(rt), json={}); return None
    log("offer_received", ride=offer.get("id"), match=offer.get("id") == rid)
    for path in ("accept",):
        a = await http.post(f"/rides/{rid}/{path}", headers=H(ct)); log(path, status=a.status_code, body=a.text[:200] if a.status_code != 200 else None)
        if a.status_code != 200: return rid
    await cap.move(PICKUP, 6)
    a = await http.post(f"/rides/{rid}/arrive", headers=H(ct)); log("arrive", status=a.status_code, body=a.text[:200] if a.status_code != 200 else None)
    await asyncio.sleep(3)
    a = await http.post(f"/rides/{rid}/start", headers=H(ct)); log("start", status=a.status_code, body=a.text[:200] if a.status_code != 200 else None)
    await cap.move(DROPOFF, 12)
    a = await http.post(f"/rides/{rid}/complete", headers=H(ct))
    body = a.json() if a.status_code == 200 else a.text[:300]
    log("complete", status=a.status_code, final_fare=(body.get("final_fare") if isinstance(body, dict) else body),
        lines=(body.get("fare_lines") if isinstance(body, dict) else None))
    p = await http.get(f"/rides/{rid}/payments", headers=H(rt))
    pays = (p.json().get("payments") or []) if p.status_code == 200 else []
    if not pays:
        p = await http.post(f"/rides/{rid}/payments", headers=H(rt), json={"method": method, "idempotency_key": f"ly-reh-{rid}"})
        log(f"pay_{method}", status=p.status_code, body=p.text[:400])
        pays = (p.json().get("payments") or []) if p.status_code < 400 else []
    for pay in pays:
        if pay.get("status") == "pending" and pay.get("method") == "cash":
            c = await http.post(f"/payments/{pay['id']}/confirm", headers=H(ct)); log("cash_confirm", status=c.status_code, body=c.text[:200] if c.status_code != 200 else None)
    p = await http.get(f"/rides/{rid}/payments", headers=H(rt)); log(f"payments_after_{method}", body=p.json() if p.status_code == 200 else p.text[:200])
    return rid

async def main():
    c = creds()
    async with httpx.AsyncClient(base_url=API, timeout=40) as http:
        rt, rid_user = await login(http, c["TEST_RIDER_LY_PHONE"], c["TEST_RIDER_LY_PASSWORD"], "rider")
        ct, cid_user = await login(http, c["TEST_CAPTAIN_LY_PHONE"], c["TEST_CAPTAIN_LY_PASSWORD"], "driver")
        log("login", rider=rid_user, captain=cid_user)
        for who, tok in (("rider", rt), ("captain", ct)):
            w = await http.get("/wallet/me", headers=H(tok)); log(f"wallet_before_{who}", body=w.json() if w.status_code == 200 else w.text[:200])
        dw = await http.get("/wallet/me/driver", headers=H(ct)); log("driver_wallet_before", body=dw.json() if dw.status_code == 200 else dw.text[:200])
        sub = await http.get("/subscriptions/me", headers=H(ct)); log("subscription_before", body=sub.json() if sub.status_code == 200 else sub.text[:300])
        sj = sub.json() if sub.status_code == 200 else {}
        if not (sj.get("active") or sj.get("is_active") or sj.get("subscription")):
            plans = (await http.get("/subscriptions/plans", headers=H(ct))).json()
            daily = next((p for p in plans if p.get("duration_type") == "daily"), None)
            log("plans", plans=[(p.get("name"), p.get("price"), p.get("duration_type")) for p in plans])
            if daily:
                b = await http.post("/subscriptions", headers=H(ct), json={"plan_id": daily["id"], "idempotency_key": f"ly-reh-sub-{uuid.uuid4()}"})
                log("subscription_buy_daily_wallet", status=b.status_code, body=b.text[:400])
        cap = Captain(ct)
        task = asyncio.create_task(cap.run())
        await asyncio.sleep(8)
        try:
            await ride(http, rt, ct, cap, "cash")
            await asyncio.sleep(4)
            await ride(http, rt, ct, cap, "wallet")
            await asyncio.sleep(4)
            await ride(http, rt, ct, cap, "cash", cancel=True)
        finally:
            cap.stop = True
            with __import__("contextlib").suppress(Exception): await cap.sock.close()
            task.cancel()
        await asyncio.sleep(3)
        wd = await http.post("/wallet/me/withdrawals", headers=H(ct), json={"amount": "50.000", "method": "bank"})
        log("withdrawal_request", status=wd.status_code, body=wd.text[:300])
        for q in ("ميدان الشهداء", "مطار معيتيقة", "السرايا الحمراء", "جامعة طرابلس", "برج طرابلس",
                  "مطار بنينا", "جامعة بنغازي", "كورنيش بنغازي", "مطار مصراتة", "ميدان النصر مصراتة"):
            t0 = time.perf_counter()
            r = await http.get("/places/search", headers=H(rt), params={"q": q, "lat": PICKUP["lat"], "lng": PICKUP["lng"]})
            ms = int((time.perf_counter() - t0) * 1000)
            res = (r.json().get("results") or r.json().get("places") or []) if r.status_code == 200 else []
            top = [(x.get("name"), x.get("subtitle") or x.get("city"), x.get("source")) for x in res[:3]]
            log("search", q=q, status=r.status_code, ms=ms, top=top)
        for who, tok in (("rider", rt), ("captain", ct)):
            w = await http.get("/wallet/me", headers=H(tok)); log(f"wallet_after_{who}", body=w.json() if w.status_code == 200 else w.text[:200])
            tx = await http.get("/wallet/me/transactions", headers=H(tok)); log(f"tx_{who}", body=(tx.json()[:8] if tx.status_code == 200 else tx.text[:200]))
        dw = await http.get("/wallet/me/driver", headers=H(ct)); log("driver_wallet_after", body=dw.json() if dw.status_code == 200 else dw.text[:200])
    json.dump(LOG, open("/mnt/c/Users/loly3/taxo-deploy-logs/libya/rehearsal-out.json", "w"), ensure_ascii=False, indent=1)

asyncio.run(main())
