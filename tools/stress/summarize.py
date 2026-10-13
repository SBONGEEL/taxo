"""صفٌّ لكلِّ درجة (SPEC §٧٥-أ «يُقاس في كلِّ درجة») — من نتيجة المولّد (`<درجة>.json`) ومراقب الخادم (`<درجة>.monitor.csv`).

    python tools/stress/summarize.py /mnt/d/taxo-stress/p1 s1 s2 …

**وما يُطبع مقيسٌ لا مقدَّر**: أقصى المعالج والحدُّ الأدنى للذاكرة الحرّة واتصالاتُ القاعدة وطابورُ المهامّ وأوامرُ GEOADD في الثانية من
المراقب، والزمنُ والأخطاءُ والعروضُ والرحلاتُ والأجورُ من المولّد.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def monitor(path: Path) -> dict:
    rows = []
    stops = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("STOP"):
                stops.append(line.strip())
                continue
            if line.startswith("ts,") or "," not in line:
                continue
            parts = line.strip().split(",")
            if len(parts) < 20:
                continue
            rows.append(parts)
    if not rows:
        return {"samples": 0, "stops": stops}

    def col(i: int) -> list[float]:
        out = []
        for r in rows:
            try:
                out.append(float(r[i].replace("MiB", "").replace("GiB", "")))
            except ValueError:
                pass
        return out

    geo = col(16)
    geo_rate = None
    if len(geo) > 1 and geo[-1] >= geo[0]:
        geo_rate = round((geo[-1] - geo[0]) / (10 * (len(geo) - 1)), 1)
    return {
        "samples": len(rows),
        "cpu_max": max(col(1), default=None),
        "cpu_avg": round(sum(col(1)) / max(1, len(col(1))), 1),
        "load1_max": max(col(2), default=None),
        "mem_avail_min_pct": min(col(5), default=None),
        "disk_pct": max(col(6), default=None),
        "backend_cpu_max": max(col(7), default=None),
        "worker_cpu_max": max(col(9), default=None),
        "db_cpu_max": max(col(10), default=None),
        "redis_cpu_max": max(col(12), default=None),
        "pg_conns_max": max(col(13), default=None),
        "pg_active_max": max(col(14), default=None),
        "celery_queue_max": max(col(15), default=None),
        "geoadd_per_s": geo_rate,
        "redis_ops_max": max(col(17), default=None),
        "refused": int(max(col(19), default=0)),
        "stops": stops,
    }


def main() -> None:
    base = Path(sys.argv[1])
    for name in sys.argv[2:]:
        gen = json.loads((base / f"{name}.json").read_text(encoding="utf-8"))
        mon = monitor(base / f"{name}.monitor.csv")
        counts = gen.get("counts", {})
        row = {
            "stage": name,
            "load": gen.get("stage"),
            "protocol": gen.get("protocol"),
            "http_avg_ms": gen["http_all"]["avg_ms"],
            "http_p95_ms": gen["http_all"]["p95_ms"],
            "http_n": gen["http_all"]["n"],
            "error_rate": gen.get("error_rate"),
            "errors": gen.get("errors"),
            "offer_avg_ms": gen["offer_latency"]["avg_ms"],
            "offer_p95_ms": gen["offer_latency"]["p95_ms"],
            "assign_p95_ms": gen["assign_latency"]["p95_ms"],
            "rides_requested": counts.get("rides_requested", 0),
            "rides_completed": counts.get("rides_completed", 0),
            "rides_cancelled": counts.get("rides_cancelled", 0),
            "no_driver_found": counts.get("no_driver_found", 0),
            "rides_lost": counts.get("rides_lost", 0),
            "rides_stuck": counts.get("rides_stuck", 0),
            "wrong_fares": len(gen.get("wrong_fares") or []),
            "ws_driver_open": counts.get("ws_driver_open", 0),
            "ws_rider_open": counts.get("ws_rider_open", 0),
            "location_per_s": gen.get("location_sent_per_second"),
            "frames_per_s": gen.get("broadcast_frames_per_second"),
            "generator_cpu": gen.get("generator_cpu_percent_per_shard"),
            "server": mon,
        }
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
