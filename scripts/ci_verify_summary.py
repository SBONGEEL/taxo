"""خلاصةُ «قياسُ إيداع»: ما جُمع وما اختير وما شُغّل وما سقط — تُكتب في ملخّص التشغيل."""
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "reports")
universe = None
selected = ran = 0
failed: list[str] = []
for p in root.rglob("shard-*.collect.json"):
    d = json.loads(p.read_text(encoding="utf-8"))
    universe = len(d["universe"])
    selected += len(d["selected"])
for p in root.rglob("shard-*.run.json"):
    d = json.loads(p.read_text(encoding="utf-8"))
    out = d.get("outcomes", {})
    ran += len(out)
    failed += [k for k, v in out.items() if v in ("failed", "error")]
print(f"- جُمع عند الإيداع: **{universe}** · اختير في الوظائف: **{selected}** · شُغّل: **{ran}**")
print(f"- COUNT collected={universe} selected={selected} ran={ran}")
print(f"- الساقط ({len(failed)}):")
for f in sorted(failed):
    print(f"  - `{f}`")
