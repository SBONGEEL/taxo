"""usage: python -I run105.py <server.py dir> <index> <places_105.json> [--misses]"""
import importlib.util
import json
import math
import os
import sys
import time

sys.path.insert(0, sys.argv[1])
os.environ["PLACES_INDEX"] = sys.argv[2]
spec = importlib.util.spec_from_file_location("srv", os.path.join(sys.argv[1], "server.py"))
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)
cases = json.load(open(sys.argv[3], encoding="utf-8"))
show = "--misses" in sys.argv


def km(a, b, c, d):
    return math.hypot((c - a) * 111, (d - b) * 111 * math.cos(math.radians(a)))


total = {}
for cc in ("JO", "DZ", "LY"):
    hits, times = 0, []
    for q, lat, lng, radius, city, kind in cases[cc]:
        near = tuple(cases["near"][city])
        t = time.perf_counter()
        items = srv.search(q, cc, near, 5)
        times.append(time.perf_counter() - t)
        ok = any(km(lat, lng, i["lat"], i["lng"]) <= radius for i in items)
        hits += ok
        if show and not ok:
            print(f"  MISS {cc} {q!r}: " + " / ".join(f"{i['name']} ({km(lat, lng, i['lat'], i['lng']):.1f}km)" for i in items[:3]))
    total[cc] = (hits, len(cases[cc]), sum(times) / len(times), max(times))
    print(f"{cc}: {hits}/{len(cases[cc])} = {100 * hits / len(cases[cc]):.0f}%  avg {1000 * total[cc][2]:.0f} ms  max {1000 * total[cc][3]:.0f} ms", flush=True)
