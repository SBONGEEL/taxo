#!/usr/bin/env bash
# monitor_remote.sh <seconds> <interval> — يُشغَّل على الخادم عبر اتصال ssh واحد (`ssh … 'bash -s' < monitor_remote.sh`)
# ويطبع سطراً CSV كلَّ <interval> ثانية — **قراءةٌ وحدَها** (SPEC §٧٥): المعالجُ والذاكرةُ والقرصُ وحاوياتُ الخدمة واتصالاتُ القاعدة
# وطابورُ المهامّ وما عالجه Redis من بثّ الموقع (عددُ أوامر GEOADD منذ تشغيله) — **وسطرُ «STOP» حين يبلغ حدّاً من حدود المالك**
# (ذاكرةٌ حرّةٌ تحت ١٠٪، أو قرصٌ فوق ٩٥٪، أو القاعدةُ ترفض الاتصال).
set -u
DURATION="${1:-600}"
INTERVAL="${2:-10}"
END=$(( $(date +%s) + DURATION ))
read_cpu() { awk '/^cpu /{print $2+$3+$4+$5+$6+$7+$8, $5+$6}' /proc/stat; }
echo "ts,cpu_busy_pct,load1,mem_total_mb,mem_avail_mb,mem_avail_pct,disk_used_pct,backend_cpu,backend_mem_mb,worker_cpu,db_cpu,db_mem_mb,redis_cpu,pg_conns,pg_active,celery_queue,geoadd_calls,redis_ops_per_sec,redis_clients,refused"
read -r T0 I0 < <(read_cpu)
while [ "$(date +%s)" -lt "$END" ]; do
  sleep "$INTERVAL"
  read -r T1 I1 < <(read_cpu)
  CPU=$(awk -v t0="$T0" -v i0="$I0" -v t1="$T1" -v i1="$I1" 'BEGIN{dt=t1-t0; di=i1-i0; if(dt>0) printf "%.1f", 100*(dt-di)/dt; else print 0}')
  T0=$T1; I0=$I1
  LOAD=$(cut -d' ' -f1 /proc/loadavg)
  read -r MT MA < <(awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} END{print int(t/1024), int(a/1024)}' /proc/meminfo)
  MAP=$(awk -v a="$MA" -v t="$MT" 'BEGIN{printf "%.1f", 100*a/t}')
  DISK=$(df --output=pcent / | tail -1 | tr -dc '0-9')
  STATS=$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}' taxo-backend taxo-worker taxo-db taxo-redis 2>/dev/null)
  BC=$(echo "$STATS" | awk '$1=="taxo-backend"{gsub("%","",$2); print $2}')
  BM=$(echo "$STATS" | awk '$1=="taxo-backend"{print $3}')
  WC=$(echo "$STATS" | awk '$1=="taxo-worker"{gsub("%","",$2); print $2}')
  DC=$(echo "$STATS" | awk '$1=="taxo-db"{gsub("%","",$2); print $2}')
  DM=$(echo "$STATS" | awk '$1=="taxo-db"{print $3}')
  RC=$(echo "$STATS" | awk '$1=="taxo-redis"{gsub("%","",$2); print $2}')
  PG=$(docker exec taxo-db psql -U taxo -d taxo -tAc "SELECT count(*), count(*) FILTER (WHERE state='active') FROM pg_stat_activity WHERE datname='taxo'" 2>/dev/null)
  REFUSED=0
  [ -z "$PG" ] && REFUSED=1
  PGC=$(echo "$PG" | cut -d'|' -f1); PGA=$(echo "$PG" | cut -d'|' -f2)
  QUEUE=$(docker exec taxo-redis redis-cli LLEN celery 2>/dev/null | tr -dc '0-9')
  GEO=$(docker exec taxo-redis redis-cli INFO commandstats 2>/dev/null | awk -F'[=,:]' '/^cmdstat_geoadd/{print $3}' | tr -dc '0-9')
  OPS=$(docker exec taxo-redis redis-cli INFO stats 2>/dev/null | awk -F: '/instantaneous_ops_per_sec/{print $2}' | tr -dc '0-9')
  CLI=$(docker exec taxo-redis redis-cli INFO clients 2>/dev/null | awk -F: '/^connected_clients/{print $2}' | tr -dc '0-9')
  echo "$(date -u +%H:%M:%S),$CPU,$LOAD,$MT,$MA,$MAP,$DISK,$BC,$BM,$WC,$DC,$DM,$RC,$PGC,$PGA,${QUEUE:-0},${GEO:-0},${OPS:-0},${CLI:-0},$REFUSED"
  if awk -v p="$MAP" 'BEGIN{exit !(p < 10)}' || [ "${DISK:-0}" -ge 95 ] || [ "$REFUSED" = 1 ]; then
    echo "STOP,mem_avail_pct=$MAP,disk=$DISK,db_refused=$REFUSED"
  fi
done
