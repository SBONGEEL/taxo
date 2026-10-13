#!/bin/bash
# restore_check.sh <label> — (WSL) تُستعاد النسخةُ في حاويةِ PostGIS عابرةٍ محلّيّة، وتُبصم بالملفّ نفسِه، وتُقارن ببصمة الإنتاج جدولاً جدولاً
set -uo pipefail
D="/mnt/d/taxo-backups/stress-$1"
N=taxo-restore-check
FP=~/prj/TAXO-rd-dz/tools/stress/fingerprint.sql
docker rm -f $N >/dev/null 2>&1
docker run -d --name $N -e POSTGRES_USER=taxo -e POSTGRES_PASSWORD=restorecheck -e POSTGRES_DB=taxo postgis/postgis:16-3.4 >/dev/null || exit 1
# **والجاهزيّةُ الأولى كاذبة** (قِيس ٢٠٢٦-١٠-١٣): الصورةُ تُقلع خادماً مؤقّتاً تبني عليه PostGIS ثمّ تعيد التشغيل — و`pg_isready`
# يجيب «جاهز» على المؤقّت، **فانقطعت الاستعادةُ بعد سطرها الأوّل وخرجت بصفر أخطاء**. فيُنتظر «ready to accept connections» مرّتين
for i in $(seq 1 90); do
  [ "$(docker logs $N 2>&1 | grep -c 'database system is ready to accept connections')" -ge 2 ] && break
  sleep 2
done
docker exec $N pg_isready -U taxo -d taxo >/dev/null || { echo "✗ القاعدةُ المستعادة لم تقُم"; exit 1; }
gunzip -c "$D/taxo.sql.gz" | docker exec -i $N psql -U taxo -d taxo -q -v ON_ERROR_STOP=0 > "$D/restore.log" 2>&1
echo "restore errors: $(grep -c ERROR "$D/restore.log")"
grep ERROR "$D/restore.log" | sort | uniq -c | head -8
docker exec -i $N psql -U taxo -d taxo -v ON_ERROR_STOP=1 -P pager=off -tA -F '|' < $FP | grep '|' > "$D/restored_fp.txt"
python3 - "$D" <<'EOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
def load(n):
    return {l.split("|")[0]: l.split("|")[1:] for l in (d / n).read_text().splitlines() if "|" in l}
p, r = load("prod_fp.txt"), load("restored_fp.txt")
same = [t for t in p if r.get(t) == p[t]]
diff = [t for t in p if t in r and r[t] != p[t]]
miss = [t for t in p if t not in r]
extra = [t for t in r if t not in p]
rows = sum(int(v[0]) for v in p.values())
print(f"tables prod={len(p)} restored={len(r)} identical={len(same)} differ={len(diff)} missing={len(miss)} extra={len(extra)} rows={rows}")
for t in diff:
    print(f"  differ {t}: prod rows={p[t][0]} restored rows={r[t][0]}")
for t in miss:
    print(f"  missing {t}")
EOF
docker rm -f $N >/dev/null
