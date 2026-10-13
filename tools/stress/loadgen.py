"""مولّدُ الحمل لاختبار الإنتاج (SPEC §٧٥) — **يُشغَّل من خارج الخادم ويمرّ عبر Cloudflare والنفق كالمستخدم الحقيقيّ**.

    ~/stress-venv/bin/python tools/stress/loadgen.py --tokens tokens.json --stage 100:200:20 --minutes 5 \\
        --out results/stage-1.json [--api https://api.tajora.ly/api/v1] [--shards 4] [--location-seconds 3]

## ما يفعله — **كما يفعل التطبيقان بقواعد البثّ المرفوعة**

* **الكبتن**: يفتح مقبسَه (`/ws/driver` — فتحُه رفعُ «متّصل»)، **ويبثّ موقعَه كلَّ `--location-seconds`** (٣ ثوانٍ — `--protocol legacy`)،
  **أو بالبثّ المتكيّف** (`--protocol adaptive`، §٧٥-ج — المرحلة ٣): سياسةُ الخادم من «connected» وحيّةً بعده، متاحٌ بفاصلها وقاعدةِ الثلاثين
  متراً (نصفُ المتاحين واقفٌ ونصفُهم يتجوّل)، في الطريق كلَّ ١٠، **والرحلةُ نقطةٌ كلَّ ٢ ث ودفعةٌ كلَّ ١٥ بإقرار** وآخرُها قبل الإنهاء، والنبضة،
  **ويجيب «location_request» فوراً** كالتطبيق؛
  ويقبل كلَّ طلبٍ يصله ثمّ يسير إلى الراكب ← «وصلت» ← «بدأت» ← يسير إلى الوجهة ← «انتهت» **فتُسجَّل الأجرة** ← يؤكّد الدفعَ النقديّ.
* **الراكب**: يفتح مقبسَه (`/ws/rider`) ويرسل مركزَ خريطته فتصله السيّاراتُ القريبة كلَّ خمس ثوانٍ (كالتطبيق)، **ويطلب**: تقديرٌ ثمّ طلبٌ
  نقداً؛ **وبعضُهم يلغي قبل القبول** (`--cancel-share`).
* **الرحلاتُ المتزامنة** تُضبط بالعدد: كلّما انتهت رحلةٌ طلب راكبٌ خامل أخرى حتى يبقى العددُ قائماً.

## ولمَ «شظايا» بالمدن

عمليّةُ بايثون واحدةٌ لآلاف المقابس تبلغ حدَّ معالجٍ واحدٍ **فيصير المولّدُ هو عنقَ الزجاجة لا الخادم**. فتُقسَم الحساباتُ على عمليّاتٍ
**لكلٍّ مدينةٌ** (عمّان · الزرقاء · إربد · السلط · مادبا · المفرق)، **والتوزيعُ جغرافيّ فلا يعبر طلبٌ مدينته** — فيُقاس «من الطلب حتى
وصوله إلى كبتن» بساعة العمليّة نفسِها بلا فرق ساعاتٍ بين جهازين.

## ما يُقاس (لكلِّ درجة) ويُكتب في `--out`

زمنُ كلِّ بابٍ (المتوسّطُ وأبطأُ ٥٪) والأخطاءُ بحالها · **من الطلب حتى وصول العرض إلى كبتن** · من الطلب حتى الإسناد · الرحلاتُ المكتملة
والملغاة و«لا كبتن» والضائعة (بلا جوابٍ في دقيقتين) والعالقة · **الأجورُ الخاطئة** (المجموعُ لا يساوي سطورَه، أو صفر) · المقابسُ التي
فُتحت وسقطت · **البثُّ المُرسَل في الثانية** · **ومعالجُ جهاز المولّد نفسِه** (إن بلغ حدَّه قيل إن الحدَّ هنا لا في الخادم).

**ولا يمسّ حساباً غيرَ ما في ملفّ الجلسات**، ولا يطبع رمزاً.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import multiprocessing as mp
import os
import random
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

CITIES = [
    ("عمّان", 31.9539, 35.9106),
    ("الزرقاء", 32.0728, 36.0880),
    ("إربد", 32.5568, 35.8469),
    ("السلط", 32.0392, 35.7272),
    ("مادبا", 31.7160, 35.7939),
    ("المفرق", 32.3429, 36.2080),
]
SPREAD_DEG = 0.03          # ~٣ كم حول مركز المدينة
HEADING_SECONDS = 20       # السيرُ إلى الراكب
WAIT_SECONDS = 5           # انتظارُ الراكب بعد «وصلت»
TRIP_SECONDS = 40          # الرحلة
LOST_AFTER_SECONDS = 120   # طلبٌ بلا عرضٍ ولا جوابٍ في دقيقتين ضائع
REFRESH_EVERY_SECONDS = 20 * 60
#: سياسةُ الخادم قبل وصولها — قيمُ الترحيلة نفسُها (تُستبدل بما في «connected»)
DEFAULT_POLICY = {"available_seconds": 15, "heading_seconds": 10, "trip_send_seconds": 15, "trip_record_seconds": 2,
                  "move_meters": 30, "heartbeat_seconds": 60}


def meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rad = math.radians
    h = math.sin(rad(lat2 - lat1) / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(rad(lng2 - lng1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1))
    return ordered[k]


def summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "avg_ms": None, "p95_ms": None, "max_ms": None}
    return {"n": len(values), "avg_ms": round(statistics.fmean(values), 1), "p95_ms": round(percentile(values, 95), 1),
            "max_ms": round(max(values), 1)}


@dataclass
class Metrics:
    http: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    offer_ms: list[float] = field(default_factory=list)
    assign_ms: list[float] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    wrong_fares: list[str] = field(default_factory=list)
    location_sent: int = 0
    #: البثُّ المتكيّف — ما أُرسل بأنواعه
    heartbeats: int = 0
    batches: int = 0
    batch_points: int = 0
    acks: int = 0
    location_requests: int = 0

    def to_json(self) -> dict:
        return {
            "http": {k: v for k, v in self.http.items()},
            "errors": dict(self.errors),
            "offer_ms": self.offer_ms,
            "assign_ms": self.assign_ms,
            "counts": dict(self.counts),
            "wrong_fares": self.wrong_fares[:50],
            "location_sent": self.location_sent,
            "heartbeats": self.heartbeats,
            "batches": self.batches,
            "batch_points": self.batch_points,
            "acks": self.acks,
            "location_requests": self.location_requests,
        }


class Account:
    def __init__(self, row: dict, center: tuple[float, float]) -> None:
        self.role = row["role"]
        self.user_id = row["user_id"]
        self.access = row["access"]
        self.refresh = row["refresh"]
        self.refreshed_at = time.monotonic()
        self.lat = center[0] + random.uniform(-SPREAD_DEG, SPREAD_DEG)
        self.lng = center[1] + random.uniform(-SPREAD_DEG, SPREAD_DEG)
        self.busy = False
        # ── البثُّ المتكيّف (§٧٥-ج)
        self.policy: dict = dict(DEFAULT_POLICY)
        self.mode = "available"
        #: نصفُ المتاحين واقفٌ ونصفُهم يتجوّل — والواقفُ لا يرسل إلا نبضتَه
        self.parked = random.random() < 0.5
        self.sent: tuple[float, float, float] | None = None
        self.last_frame = 0.0
        self.holding = False
        self.buffer: list[dict] = []
        self.pending: dict[int, dict] = {}
        self.seq = int(time.time() * 1000)
        self.last_record = 0.0
        self.last_batch = 0.0
        self.socket = None
        self.mode_since = time.monotonic()
        self.window_closed = False

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access}"}


class Shard:
    def __init__(self, args, rows: list[dict], city: tuple[str, float, float], trips: int) -> None:
        self.args = args
        self.center = (city[1], city[2])
        self.city = city[0]
        self.captains = [Account(r, self.center) for r in rows if r["role"] == "driver"]
        self.riders = [Account(r, self.center) for r in rows if r["role"] == "rider"]
        self.trips = trips
        self.metrics = Metrics()
        self.requested_at: dict[str, float] = {}
        self.ride_rider: dict[str, Account] = {}
        self.active: set[str] = set()
        self.assign_started: dict[str, float] = {}
        #: طلباتٌ أُطلقت ولم تُكتب رحلتُها بعد — تُعدّ مع القائمة فلا يُطلق المجدولُ فوق العدد
        self.launching = 0
        self.deadline = time.monotonic() + args.minutes * 60
        self.stop = asyncio.Event()

    # ------------------------------------------------------------------ HTTP
    async def call(self, http, method: str, path: str, who: Account, body: dict | None = None, label: str | None = None):
        label = label or f"{method} {path.split('/')[1] if path.count('/') else path}"
        start = time.perf_counter()
        try:
            response = await http.request(method, path, headers=who.headers, json=body)
        except Exception as exc:  # noqa: BLE001 — يُعدّ ولا يُسقط المولّد
            self.metrics.errors[f"{label} ⇐ {type(exc).__name__}"] += 1
            return None
        self.metrics.http[label].append((time.perf_counter() - start) * 1000)
        if response.status_code >= 400:
            self.metrics.errors[f"{label} ⇐ {response.status_code}"] += 1
        return response

    async def refresh_if_needed(self, http, who: Account) -> None:
        if time.monotonic() - who.refreshed_at < REFRESH_EVERY_SECONDS:
            return
        who.refreshed_at = time.monotonic()
        response = await http.post("/auth/refresh", json={"refresh_token": who.refresh})
        if response.status_code == 200:
            pair = response.json()
            who.access, who.refresh = pair["access_token"], pair["refresh_token"]
        else:
            self.metrics.errors[f"POST auth/refresh ⇐ {response.status_code}"] += 1

    # ------------------------------------------------------------------ الكبتن
    async def captain(self, http, who: Account) -> None:
        import websockets

        url = f"{self.args.ws}/driver?token={who.access}&device_id=stress-{who.user_id[:8]}"
        try:
            socket = await websockets.connect(url, open_timeout=30, ping_interval=20, max_queue=None)
        except Exception as exc:  # noqa: BLE001
            self.metrics.errors[f"WS driver connect ⇐ {type(exc).__name__}"] += 1
            return
        self.metrics.counts["ws_driver_open"] += 1
        who.socket = socket
        who.mode_since = time.monotonic()
        adaptive = self.args.protocol == "adaptive"
        sender = asyncio.create_task(self.adaptive(socket, who) if adaptive else self.broadcast(socket, who))
        try:
            async for raw in socket:
                frame = json.loads(raw)
                kind = frame.get("type")
                if adaptive:
                    if kind == "connected" and frame.get("broadcast"):
                        who.policy.update({k: v for k, v in frame["broadcast"].items() if k in DEFAULT_POLICY})
                    elif kind == "broadcast_policy":
                        who.policy.update({k: v for k, v in frame.items() if k in DEFAULT_POLICY})
                        self.metrics.counts[f"policy_available_{frame.get('available_seconds')}"] += 1
                    elif kind == "location_request":
                        self.metrics.location_requests += 1
                        await self.send_location(socket, who)
                    elif kind == "points_ack":
                        self.metrics.acks += 1
                        who.pending.pop(frame.get("seq"), None)
                if kind == "ride_offer":
                    ride = frame.get("ride") or {}
                    ride_id = ride.get("id")
                    if ride_id in self.requested_at:
                        self.metrics.offer_ms.append((time.monotonic() - self.requested_at.pop(ride_id)) * 1000)
                    self.metrics.counts["offers_received"] += 1
                    if not who.busy and ride_id:
                        asyncio.create_task(self.drive(http, who, ride))
                # **ولا يُغلق مقبسُ كبتنٍ في رحلة** عند انتهاء الدرجة — فتكتمل الرحلةُ وتُحسب، ولا يُقرأ إغلاقُنا عطباً في الخادم
                if self.stop.is_set() and not who.busy:
                    break
        except Exception as exc:  # noqa: BLE001
            self.metrics.errors[f"WS driver dropped ⇐ {type(exc).__name__}"] += 1
        finally:
            sender.cancel()
            await socket.close()

    async def broadcast(self, socket, who: Account) -> None:
        try:
            await self._broadcast(socket, who)
        finally:
            self.close_window(who)

    async def _broadcast(self, socket, who: Account) -> None:
        await asyncio.sleep(random.uniform(0, self.args.location_seconds))
        while not (self.stop.is_set() and not who.busy):
            if not who.busy:
                who.lat += random.uniform(-0.0003, 0.0003)
                who.lng += random.uniform(-0.0003, 0.0003)
            try:
                await socket.send(json.dumps({"type": "location", "lat": who.lat, "lng": who.lng, "heading": 90}))
                self.metrics.location_sent += 1
                self.metrics.counts[f"frames_{who.mode}"] += 1
            except Exception:  # noqa: BLE001
                return
            await asyncio.sleep(self.args.location_seconds)

    # ------------------------------------------------- البثُّ المتكيّف (§٧٥-ج)
    async def send_location(self, socket, who: Account) -> None:
        await socket.send(json.dumps({"type": "location", "lat": who.lat, "lng": who.lng, "heading": 90}))
        self.metrics.location_sent += 1
        self.metrics.counts[f"frames_{who.mode}"] += 1
        who.sent = (who.lat, who.lng, time.monotonic())
        who.last_frame = time.monotonic()
        who.holding = False

    async def send_batch(self, socket, who: Account) -> None:
        who.last_batch = time.monotonic()
        if who.buffer:
            who.seq += 1
            who.pending[who.seq] = {"seq": who.seq, "points": who.buffer}
            who.buffer = []
        for batch in list(who.pending.values()):
            await socket.send(json.dumps({"type": "locations", **batch}))
            self.metrics.batches += 1
            self.metrics.counts[f"frames_{who.mode}"] += 1
            self.metrics.batch_points += len(batch["points"])
        who.last_frame = time.monotonic()

    async def adaptive(self, socket, who: Account) -> None:
        """**دورةُ قرارٍ كلَّ ثانية** كما في `driver-app/src/lib/socket.ts` — والتجوّلُ لمن ليس واقفاً."""
        await asyncio.sleep(random.uniform(0, 3))
        try:
            await self.send_location(socket, who)
            while not (self.stop.is_set() and not who.busy):
                await asyncio.sleep(1)
                now = time.monotonic()
                policy = who.policy
                if who.mode == "trip":
                    if now - who.last_record >= policy["trip_record_seconds"]:
                        who.last_record = now
                        who.buffer.append({"lat": who.lat, "lng": who.lng, "heading": 90, "t": int(time.time() * 1000)})
                    if now - who.last_batch >= policy["trip_send_seconds"]:
                        await self.send_batch(socket, who)
                    continue
                if who.mode == "available" and not who.parked and not who.busy and random.random() < 1 / 3:
                    who.lat += random.uniform(-0.0003, 0.0003)
                    who.lng += random.uniform(-0.0003, 0.0003)
                interval = policy["heading_seconds"] if who.mode == "heading" else policy["available_seconds"]
                moved = who.sent is None or meters(who.sent[0], who.sent[1], who.lat, who.lng) >= policy["move_meters"]
                due = who.sent is None or now - who.sent[2] >= interval
                if moved and (who.holding or due):
                    await self.send_location(socket, who)
                    continue
                if not moved and due:
                    who.holding = True
                if now - who.last_frame >= policy["heartbeat_seconds"]:
                    await socket.send(json.dumps({"type": "heartbeat"}))
                    self.metrics.heartbeats += 1
                    self.metrics.counts[f"frames_{who.mode}"] += 1
                    who.last_frame = now
        except Exception:  # noqa: BLE001 — مقبسٌ سقط: حلقةُ الاستقبال تعدّه
            pass
        finally:
            # **نافذةُ القياس تُغلق حين يكفّ الإرسال** — فلا تُحسب ثواني المهلة بعد الدرجة بلا إطارات
            self.close_window(who)

    def close_window(self, who: Account) -> None:
        if not who.window_closed:
            self.note_mode(who, who.mode)
            who.window_closed = True

    def note_mode(self, who: Account, mode: str) -> None:
        """ثواني كلِّ حال — مقامُ «إطاراتٌ في الثانية لكلِّ كبتنٍ في هذه الحال»."""
        now = time.monotonic()
        if not who.window_closed:
            self.metrics.counts[f"seconds_{who.mode}"] += now - who.mode_since
        who.mode_since = now
        who.mode = mode

    async def set_mode(self, who: Account, mode: str) -> None:
        if self.args.protocol != "adaptive" or who.socket is None:
            self.note_mode(who, mode)
            return
        if who.mode == "trip" and mode != "trip":
            # **آخرُ النقاط قبل الإنهاء** — كالتطبيق (`flushTrip`): الأجرةُ تُقاس بما وصل
            who.buffer.append({"lat": who.lat, "lng": who.lng, "heading": 90, "t": int(time.time() * 1000)})
            await self.send_batch(who.socket, who)
            for _ in range(30):
                if not who.pending:
                    break
                await asyncio.sleep(0.1)
        self.note_mode(who, mode)
        who.last_record = who.last_batch = 0.0
        await self.send_location(who.socket, who)

    async def move(self, who: Account, lat: float, lng: float, seconds: float) -> None:
        """**مسارٌ على شكل L** (عرضاً ثمّ طولاً) — أطولُ من الخطّ المستقيم بنحو ما يطول الطريقُ الحقيقيّ."""
        if self.args.protocol == "adaptive":
            # الحركةُ ثانيةً ثانية — والبثُّ تقرّره دورتُه لا خطوةُ الحركة
            steps = max(1, int(seconds))
            corner = (lat, who.lng)
            half = steps // 2 or 1
            start = (who.lat, who.lng)
            for k in range(1, steps + 1):
                if k <= half:
                    who.lat, who.lng = start[0] + (corner[0] - start[0]) * (k / half), start[1]
                else:
                    who.lat, who.lng = corner[0], corner[1] + (lng - corner[1]) * ((k - half) / max(1, steps - half))
                await asyncio.sleep(1)
            return
        steps = max(1, int(seconds / self.args.location_seconds))
        corner = (lat, who.lng)
        half = steps // 2 or 1
        start = (who.lat, who.lng)
        for k in range(1, steps + 1):
            if k <= half:
                f = k / half
                who.lat, who.lng = start[0] + (corner[0] - start[0]) * f, start[1]
            else:
                f = (k - half) / max(1, steps - half)
                who.lat, who.lng = corner[0], corner[1] + (lng - corner[1]) * f
            await asyncio.sleep(self.args.location_seconds)

    async def drive(self, http, who: Account, ride: dict) -> None:
        who.busy = True
        ride_id = ride["id"]
        try:
            accepted = await self.call(http, "POST", f"/rides/{ride_id}/accept", who, label="POST rides/accept")
            if accepted is None or accepted.status_code != 200:
                return
            pickup = ride.get("pickup") or {}
            dropoff = ride.get("dropoff") or {}
            await self.set_mode(who, "heading")
            await self.move(who, float(pickup.get("lat", who.lat)), float(pickup.get("lng", who.lng)), HEADING_SECONDS)
            await self.call(http, "POST", f"/rides/{ride_id}/arrive", who, label="POST rides/arrive")
            await asyncio.sleep(WAIT_SECONDS)
            started = await self.call(http, "POST", f"/rides/{ride_id}/start", who, label="POST rides/start")
            if started is None or started.status_code != 200:
                return
            await self.set_mode(who, "trip")
            await self.move(who, float(dropoff.get("lat", who.lat)), float(dropoff.get("lng", who.lng)), TRIP_SECONDS)
            await self.set_mode(who, "available")
            done = await self.call(http, "POST", f"/rides/{ride_id}/complete", who, label="POST rides/complete")
            if done is None or done.status_code != 200:
                return
            body = done.json()
            self.check_fare(ride_id, body)
            self.metrics.counts["rides_completed"] += 1
            rider = self.ride_rider.get(ride_id)
            if rider is not None:
                listed = await self.call(http, "GET", f"/rides/{ride_id}/payments", rider, label="GET rides/payments")
                payments = (listed.json().get("payments") if listed is not None and listed.status_code == 200 else []) or []
                if not payments:
                    paid = await self.call(http, "POST", f"/rides/{ride_id}/payments", rider,
                                           {"method": "cash", "idempotency_key": f"stress-{ride_id}"}, label="POST rides/payments")
                    payments = (paid.json().get("payments") if paid is not None and paid.status_code < 400 else []) or []
                for payment in payments:
                    if payment.get("method") == "cash" and payment.get("status") == "pending":
                        confirmed = await self.call(http, "POST", f"/payments/{payment['id']}/confirm", who,
                                                    label="POST payments/confirm")
                        if confirmed is not None and confirmed.status_code == 200:
                            self.metrics.counts["cash_confirmed"] += 1
        finally:
            who.busy = False
            if who.mode != "available":
                with contextlib.suppress(Exception):
                    await self.set_mode(who, "available")

    def check_fare(self, ride_id: str, body: dict) -> None:
        try:
            final = Decimal(str(body.get("final_fare")))
            lines = sum((Decimal(str(line["amount"])) for line in body.get("fare_lines") or []), Decimal(0))
        except Exception:  # noqa: BLE001
            self.metrics.wrong_fares.append(f"{ride_id}: أجرةٌ لا تُقرأ")
            return
        if final <= 0 or (body.get("fare_lines") and lines != final):
            self.metrics.wrong_fares.append(f"{ride_id}: {final} ≠ {lines}")

    # ------------------------------------------------------------------ الراكب
    async def rider(self, who: Account) -> None:
        import websockets

        url = f"{self.args.ws}/rider?token={who.access}&device_id=stress-{who.user_id[:8]}"
        try:
            socket = await websockets.connect(url, open_timeout=30, ping_interval=20, max_queue=None)
        except Exception as exc:  # noqa: BLE001
            self.metrics.errors[f"WS rider connect ⇐ {type(exc).__name__}"] += 1
            return
        self.metrics.counts["ws_rider_open"] += 1
        try:
            await socket.send(json.dumps({"type": "viewport", "lat": who.lat, "lng": who.lng}))
            async for raw in socket:
                frame = json.loads(raw)
                kind = frame.get("type")
                if kind == "nearby_drivers" or kind == "nearby":
                    self.metrics.counts["nearby_frames"] += 1
                ride = frame.get("ride") or {}
                ride_id = ride.get("id")
                if kind == "driver_assigned" and ride_id in self.assign_started:
                    self.metrics.assign_ms.append((time.monotonic() - self.assign_started.pop(ride_id)) * 1000)
                if kind in ("ride_completed", "ride_cancelled", "no_driver_found") and ride_id:
                    if kind == "no_driver_found":
                        self.metrics.counts["no_driver_found"] += 1
                    self.finish(ride_id)
                # **ولا مقبسُ راكبٍ في رحلة** — كان يُغلق فلا يصله «اكتملت» فتُعدّ رحلتُه «عالقة» وليست كذلك (قِيس على التطوير ٢٠٢٦-١٠-١٣)
                if self.stop.is_set() and not who.busy:
                    break
        except Exception as exc:  # noqa: BLE001
            self.metrics.errors[f"WS rider dropped ⇐ {type(exc).__name__}"] += 1
        finally:
            await socket.close()

    def finish(self, ride_id: str) -> None:
        self.active.discard(ride_id)
        rider = self.ride_rider.get(ride_id)
        if rider is not None:
            rider.busy = False

    async def request(self, http, who: Account) -> None:
        """**إطلاقٌ واحدٌ يُحسب مرّةً**: يُعدّ في `launching` حتى تُكتب رحلتُه (فتُعدّ في `active` ويُنزع من الإطلاق) أو يسقط."""
        who.busy = True
        launched = {"open": True}
        try:
            await self._request(http, who, launched)
        finally:
            if launched["open"]:
                self.launching -= 1

    async def _request(self, http, who: Account, launched: dict) -> None:
        await self.refresh_if_needed(http, who)
        pickup = {"lat": who.lat, "lng": who.lng}
        dropoff = {"lat": who.lat + random.uniform(0.01, 0.02), "lng": who.lng + random.uniform(-0.015, 0.015)}
        await self.call(http, "POST", "/rides/estimate", who,
                        {"pickup": pickup, "dropoff": dropoff, "vehicle_category": "economy"}, label="POST rides/estimate")
        t0 = time.monotonic()
        created = await self.call(http, "POST", "/rides", who,
                                  {"pickup": pickup, "dropoff": dropoff, "vehicle_category": "economy", "payment_method": "cash"},
                                  label="POST rides")
        if created is None or created.status_code != 201:
            who.busy = False
            return
        ride_id = created.json()["id"]
        self.metrics.counts["rides_requested"] += 1
        self.requested_at[ride_id] = t0
        self.assign_started[ride_id] = t0
        self.ride_rider[ride_id] = who
        self.active.add(ride_id)
        launched["open"] = False
        self.launching -= 1
        if random.random() < self.args.cancel_share:
            await asyncio.sleep(random.uniform(2, 6))
            if ride_id in self.assign_started:  # **لم يُسند بعد** — إلغاءٌ قبل القبول بلا رسم
                cancelled = await self.call(http, "POST", f"/rides/{ride_id}/cancel", who, {}, label="POST rides/cancel")
                if cancelled is not None and cancelled.status_code == 200:
                    self.metrics.counts["rides_cancelled"] += 1
                    self.assign_started.pop(ride_id, None)
                    self.requested_at.pop(ride_id, None)
                    self.finish(ride_id)
                    return
        await asyncio.sleep(LOST_AFTER_SECONDS)
        if ride_id in self.assign_started:
            self.metrics.counts["rides_lost"] += 1
            self.assign_started.pop(ride_id, None)
            self.finish(ride_id)

    async def scheduler(self, http) -> None:
        await asyncio.sleep(10)  # **المقابسُ تُفتح أوّلاً**
        while time.monotonic() < self.deadline:
            idle = [r for r in self.riders if not r.busy]
            while len(self.active) + self.launching < self.trips and idle:
                who = idle.pop(random.randrange(len(idle)))
                self.launching += 1
                asyncio.create_task(self.request(http, who))
                await asyncio.sleep(0.05)
            await asyncio.sleep(1)
        self.stop.set()

    async def run(self) -> dict:
        import httpx

        limits = httpx.Limits(max_connections=self.args.http_connections, max_keepalive_connections=self.args.http_connections)
        async with httpx.AsyncClient(base_url=self.args.api, timeout=30, limits=limits) as http:
            tasks = []
            for who in self.captains:
                tasks.append(asyncio.create_task(self.captain(http, who)))
                await asyncio.sleep(self.args.ramp_seconds / max(1, len(self.captains) + len(self.riders)))
            for who in self.riders:
                tasks.append(asyncio.create_task(self.rider(who)))
                await asyncio.sleep(self.args.ramp_seconds / max(1, len(self.captains) + len(self.riders)))
            await self.scheduler(http)
            grace = time.monotonic() + 150
            while self.active and time.monotonic() < grace:
                await asyncio.sleep(2)
            self.metrics.counts["rides_stuck"] = len(self.active)
            for who in self.captains:
                if who.socket is not None:
                    self.close_window(who)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return self.metrics.to_json()


def run_shard(args, rows, city, trips, out_path) -> None:
    try:
        import uvloop

        uvloop.install()
    except ImportError:  # pragma: no cover
        pass
    import psutil

    proc = psutil.Process(os.getpid())
    proc.cpu_percent(None)
    shard = Shard(args, rows, city, trips)
    result = asyncio.run(shard.run())
    result["cpu_percent"] = proc.cpu_percent(None)
    result["city"] = city[0]
    Path(out_path).write_text(json.dumps(result), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="مولّدُ الحمل (SPEC §٧٥)")
    parser.add_argument("--tokens", type=Path, required=True)
    parser.add_argument("--stage", required=True, help="كباتن:ركّاب:رحلاتٌ متزامنة — مثل 100:200:20")
    parser.add_argument("--minutes", type=float, default=5)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--api", default="https://api.tajora.ly/api/v1")
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--location-seconds", type=float, default=3.0)
    parser.add_argument("--protocol", choices=("legacy", "adaptive"), default="legacy",
                        help="legacy: موقعٌ كلَّ --location-seconds (المرحلة ١) · adaptive: البثُّ المتكيّف §٧٥-ج (المرحلة ٣)")
    parser.add_argument("--cancel-share", type=float, default=0.1)
    parser.add_argument("--ramp-seconds", type=float, default=60)
    parser.add_argument("--http-connections", type=int, default=100)
    args = parser.parse_args()
    args.ws = args.api.replace("https://", "wss://").replace("http://", "ws://") + "/ws"
    captains, riders, trips = (int(x) for x in args.stage.split(":"))
    rows = json.loads(args.tokens.read_text(encoding="utf-8"))
    cap_rows = [r for r in rows if r["role"] == "driver"][:captains]
    rider_rows = [r for r in rows if r["role"] == "rider"][:riders]
    if len(cap_rows) < captains or len(rider_rows) < riders:
        print(f"✗ الجلساتُ أقلُّ من الدرجة: {len(cap_rows)} كبتناً و{len(rider_rows)} راكباً")
        return 1
    shards = min(args.shards, len(CITIES))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    procs = []
    outs = []
    for k in range(shards):
        part = cap_rows[k::shards] + rider_rows[k::shards]
        out_path = args.out.with_suffix(f".shard{k}.json")
        outs.append(out_path)
        share = trips // shards + (1 if k < trips % shards else 0)
        p = mp.get_context("spawn").Process(target=run_shard, args=(args, part, CITIES[k], share, str(out_path)))
        p.start()
        procs.append(p)
    started = time.time()
    for p in procs:
        p.join()
    merged = Metrics()
    cpu = []
    for out_path in outs:
        if not out_path.exists():
            merged.errors["shard crashed"] += 1
            continue
        part = json.loads(out_path.read_text(encoding="utf-8"))
        for k, v in part["http"].items():
            merged.http[k].extend(v)
        for k, v in part["errors"].items():
            merged.errors[k] += v
        merged.offer_ms.extend(part["offer_ms"])
        merged.assign_ms.extend(part["assign_ms"])
        for k, v in part["counts"].items():
            merged.counts[k] += v
        merged.wrong_fares.extend(part["wrong_fares"])
        merged.location_sent += part["location_sent"]
        for key in ("heartbeats", "batches", "batch_points", "acks", "location_requests"):
            setattr(merged, key, getattr(merged, key) + part.get(key, 0))
        cpu.append(part.get("cpu_percent"))
    seconds = time.time() - started
    all_http = [ms for values in merged.http.values() for ms in values]
    total_errors = sum(merged.errors.values())
    report = {
        "stage": args.stage,
        "minutes": args.minutes,
        "wall_seconds": round(seconds, 1),
        "http_all": summary(all_http),
        "http": {k: summary(v) for k, v in sorted(merged.http.items())},
        "error_rate": round(total_errors / max(1, len(all_http) + total_errors), 4),
        "errors": dict(sorted(merged.errors.items(), key=lambda kv: -kv[1])),
        "offer_latency": summary(merged.offer_ms),
        "assign_latency": summary(merged.assign_ms),
        "counts": dict(merged.counts),
        "wrong_fares": merged.wrong_fares,
        "location_sent_per_second": round(merged.location_sent / max(1.0, args.minutes * 60), 1),
        # **كلُّ إطاراتِ البثّ في الثانية** — الموقعُ والنبضةُ والدفعة: ما يعالجه الخادمُ فعلاً
        "broadcast_frames_per_second": round(
            (merged.location_sent + merged.heartbeats + merged.batches) / max(1.0, args.minutes * 60), 1
        ),
        "protocol": args.protocol,
        # **إطاراتُ الثانية لكلِّ كبتنٍ في كلِّ حال** — مقيسةً: إطاراتُ الحال ÷ ثوانيها مجموعةً على الكباتن
        "frames_per_captain_second": {
            mode: round(merged.counts.get(f"frames_{mode}", 0) / merged.counts[f"seconds_{mode}"], 4)
            for mode in ("available", "heading", "trip")
            if merged.counts.get(f"seconds_{mode}")
        },
        "generator_cpu_percent_per_shard": cpu,
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("stage", "http_all", "error_rate", "offer_latency", "counts",
                                             "location_sent_per_second", "generator_cpu_percent_per_shard")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
