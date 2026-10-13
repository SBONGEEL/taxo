#!/usr/bin/env bash
# tools/stress/phase.sh <أمر> … — اختبارُ الحمل على الإنتاج (SPEC §٧٥، المرحلتان ١ و٣) **من جهاز المولّد** (Git Bash على ويندوز + WSL).
#
#   RUN=p1 bash tools/stress/phase.sh backup           نسخةٌ كاملةٌ إلى D: ثمّ استعادتُها في PostGIS محلّيّ ومطابقتُها جدولاً جدولاً
#   RUN=p1 bash tools/stress/phase.sh baseline         T0 · بصمةُ القاعدة كلِّها · بصمةُ الصفوف القائمة · العدّاداتُ (Mapbox · أجهزة · رسائل)
#   RUN=p1 bash tools/stress/phase.sh provision 100 200 1    حساباتُ الحمل (تزايديّ) وجلساتُها إلى ملفّ أسرارٍ على الخادم ونسخةٍ 600 محلّيّة
#   RUN=p1 bash tools/stress/phase.sh stub on|off|status      مسارُ Mapbox المحاكى لحسابات الحمل وحدَها
#   RUN=p1 bash tools/stress/phase.sh stage s1 100:200:20 5 legacy 1   درجةٌ: المراقبُ على الخادم + المولّدُ من هنا، ثمّ `check`
#   RUN=p1 bash tools/stress/phase.sh check s1         شروطُ الوقوف: ذاكرةٌ/قرصٌ/قاعدة · صفٌّ قائمٌ تغيّر · نداءٌ مدفوع · رسالة
#   RUN=p1 bash tools/stress/phase.sh cleanup          الحذفُ والمفتاحُ والبصمةُ بعد = قبل
#
# **قراءةٌ وحدَها** إلا `provision` و`stub` و`cleanup` — والثلاثةُ لا تمسّ إلا حساباتِ النطاق المحجوز (`+962719…`) ومفتاحَ Redis
# الخاصَّ بها. **ولا يُطبع سرٌّ**: الجلساتُ في ملفّاتٍ بإذن 600، وكلمةُ Redis من بيئة الحاوية.
set -uo pipefail
RUN="${RUN:?RUN مطلوب — مثل p1}"
H=taxo@169.58.207.123
SSH=/c/Windows/System32/OpenSSH/ssh.exe
O=(-i "$HOME/.ssh/taxo-contabo" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=20 -o ServerAliveInterval=15)
F="--env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml"
REPO=//wsl.localhost/Ubuntu-24.04/home/loly3/prj/TAXO-rd-dz
WREPO=/home/loly3/prj/TAXO-rd-dz
OUT=/d/taxo-stress/$RUN
WOUT=/mnt/d/taxo-stress/$RUN
mkdir -p "$OUT"
wsl() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- "$@"; }
# **جدارُ الخادم يحدّ اتصالات ssh** (قِيس ٢٠٢٦-١٠-١٣: انقطع المنفذ ٢٢ نحو أربعين ثانيةً بعد دفعةِ اتصالاتٍ قصيرة) — فبين كلِّ اتصالين
# ستُّ ثوانٍ ونصف على الأقلّ، فلا يتجاوز خمسةً في نصف دقيقة. وطابعُ آخر اتصالٍ في ملفّ لأن الأوامرَ تنادي بعضَها في عمليّاتٍ منفصلة
pace() {
  local stamp="$OUT/.last_ssh" now last
  now=$(date +%s%N); last=$(cat "$stamp" 2>/dev/null || echo 0)
  local wait_ms=$(( 6500 - (now - last) / 1000000 ))
  [ "$wait_ms" -gt 0 ] && sleep "$(awk -v m="$wait_ms" 'BEGIN{printf "%.2f", m/1000}')"
  date +%s%N > "$stamp"
}
remote() { pace; "$SSH" "${O[@]}" "$H" "$@" < /dev/null; }
sql() {  # ملفُّ SQL قراءةٍ وحدَها عبر stdin
  grep -q "^BEGIN TRANSACTION READ ONLY;" "$1" && grep -q "^ROLLBACK;" "$1" || { echo "✗ ليس قراءةً وحدَها: $1"; return 1; }
  pace
  "$SSH" "${O[@]}" "$H" "cd ~/taxo && docker compose $F exec -T db psql -U taxo -d taxo -v ON_ERROR_STOP=1 -P pager=off -tA -F '|'" < "$1"
}
redis_py() {  # أمرٌ قصيرٌ على Redis الإنتاج من داخل الخلفية — والكلمةُ لا تخرج من الحاوية
  remote "cd ~/taxo && docker compose $F exec -T backend python -c \"$1\""
}

case "${1:-}" in
backup)
  D="/d/taxo-backups/stress-$RUN"; mkdir -p "$D"
  remote "cd ~/taxo && docker compose $F exec -T db pg_dump -U taxo -d taxo --no-owner | gzip -9" > "$D/taxo.sql.gz"
  pace; "$SSH" "${O[@]}" "$H" "cd ~/taxo && docker compose $F exec -T db psql -U taxo -d taxo -v ON_ERROR_STOP=1 -P pager=off -tA -F '|'" \
    < "$REPO/tools/stress/fingerprint.sql" | grep '|' > "$D/prod_fp.txt"
  gzip -t "$D/taxo.sql.gz" || { echo "✗ الأرشيفُ تالف"; exit 1; }
  echo "· النسخة $(wc -c < "$D/taxo.sql.gz") بايت · $(wc -l < "$D/prod_fp.txt") جدولاً · $D"
  wsl bash "$WREPO/tools/stress/restore_check.sh" "$RUN"
  ;;
baseline)
  date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT/T0"
  sed "s/__T0__/$(cat "$OUT/T0")/g" "$REPO/tools/stress/existing.sql" > "$OUT/existing.sql"
  sql "$OUT/existing.sql" | grep '|' > "$OUT/existing_base.txt"
  remote "cd ~/taxo && docker compose $F run --rm --no-deps -T backend python -m scripts.stress_fingerprint" | tail -1 > "$OUT/fp_before.json"
  "$0" counters > "$OUT/counters_before.txt"
  echo "· T0 $(cat "$OUT/T0") · $(wc -l < "$OUT/existing_base.txt") جدولاً قائماً · بصمةٌ $(wc -c < "$OUT/fp_before.json") بايت"
  cat "$OUT/counters_before.txt"
  ;;
counters)
  redis_py "
import asyncio
from app.core.redis_client import get_redis_client
from app.services import stress
async def m():
    r = get_redis_client()
    print('mapbox_calls_today', int(await r.get(stress.calls_key()) or 0))
    print('stub_answers', int(await r.get(stress.STUB_COUNT_KEY) or 0))
asyncio.run(m())
" 2>/dev/null | grep -E '^(mapbox|stub)'
  cat > "$OUT/.counters.sql" <<'Q'
BEGIN TRANSACTION READ ONLY;
SELECT 'stress_users', count(*) FROM users WHERE phone LIKE '+962719%';
SELECT 'stress_device_tokens', count(*) FROM device_tokens d JOIN users u ON u.id = d.user_id WHERE u.phone LIKE '+962719%';
SELECT 'notification_deliveries', count(*) FROM notification_deliveries;
SELECT 'stress_ledger_rows', count(*) FROM wallet_transactions w JOIN users u ON u.id = w.owner_id WHERE u.phone LIKE '+962719%';
ROLLBACK;
Q
  sql "$OUT/.counters.sql" | grep '|' | tr '|' ' '
  # **ما أُرسل لا ما سُجّل** (قِيس ٢٠٢٦-١٠-١٣): بوّابةُ واتساب تسجّل كلَّ رسالةٍ يرسلها هاتفُ الحساب المربوط نفسُه («failed to decrypt»
  # و`fromMe`) — ضجيجٌ بمعدّله قبل الاختبار. **فيُعدّ ما ترسله TAXO**: أحداثُ الإرسال في البوّابة، ونداءاتُ الخلفية والعامل إليها
  SINCE="$(cat "$OUT/T0" 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
  remote "echo whatsapp_gateway_send_events \$(docker logs --since $SINCE taxo-whatsapp-gateway 2>&1 | grep -ciE '\"msg\":\"[^\"]*(send|sent|relay)'); echo backend_whatsapp_posts \$(docker logs --since $SINCE taxo-backend 2>&1 | grep -ciE 'POST http://whatsapp-gateway'); echo worker_whatsapp_posts \$(docker logs --since $SINCE taxo-worker 2>&1 | grep -ciE 'POST http://whatsapp-gateway')"
  ;;
provision)
  C="$2"; R="$3"; N="$4"
  remote "cd ~/taxo && docker compose $F run --rm --no-deps -T --user \$(id -u):\$(id -g) -v /home/taxo/secrets:/out backend python -m scripts.stress_provision --captains $C --riders $R --tokens-file /out/stress-tokens-$RUN-$N.json --apply" | tail -2
  remote "cat /home/taxo/secrets/stress-tokens-$RUN-$N.json" > "$OUT/tokens-$N.json"
  chmod 600 "$OUT/tokens-$N.json" 2>/dev/null
  wsl bash -c "mkdir -p ~/stress-prod && chmod 700 ~/stress-prod && cp '$WOUT/tokens-$N.json' ~/stress-prod/$RUN-$N.json && chmod 600 ~/stress-prod/$RUN-$N.json && rm -f '$WOUT/tokens-$N.json'"
  echo "· جلساتٌ: $(wsl python3 -c "import json;print(len(json.load(open('/home/loly3/stress-prod/$RUN-$N.json'))))")"
  ;;
stub)
  case "$2" in
    on) redis_py "
import asyncio
from app.core.redis_client import get_redis_client
from app.services import stress
async def m():
    r = get_redis_client(); await r.set(stress.SWITCH_KEY, '1', ex=stress.SWITCH_TTL_SECONDS); print('stub', await r.ttl(stress.SWITCH_KEY))
asyncio.run(m())
" 2>/dev/null | tail -1 ;;
    off) redis_py "
import asyncio
from app.core.redis_client import get_redis_client
from app.services import stress
async def m():
    r = get_redis_client(); await r.delete(stress.SWITCH_KEY); print('stub_exists', await r.exists(stress.SWITCH_KEY))
asyncio.run(m())
" 2>/dev/null | tail -1 ;;
    status) redis_py "
import asyncio
from app.core.redis_client import get_redis_client
from app.services import stress
async def m():
    r = get_redis_client(); print('stub_ttl', await r.ttl(stress.SWITCH_KEY))
asyncio.run(m())
" 2>/dev/null | tail -1 ;;
  esac
  ;;
stage)
  NAME="$2"; STAGE="$3"; MIN="$4"; PROTO="$5"; N="$6"; SHARDS="${SHARDS:-6}"
  SECS=$(awk -v m="$MIN" 'BEGIN{print int(m*60 + 330)}')
  pace; "$SSH" "${O[@]}" "$H" "bash -s $SECS 10" < "$REPO/tools/stress/monitor_remote.sh" > "$OUT/$NAME.monitor.csv" 2>&1 &
  MON=$!
  wsl bash -c "cd $WREPO && ~/stress-venv/bin/python tools/stress/loadgen.py --tokens ~/stress-prod/$RUN-$N.json --stage $STAGE --minutes $MIN \
    --out $WOUT/$NAME.json --shards $SHARDS --protocol $PROTO > $WOUT/$NAME.log 2>&1"
  echo "· المولّد انتهى ($?)"
  kill "$MON" 2>/dev/null; wait "$MON" 2>/dev/null
  "$0" check "$NAME"
  ;;
check)
  NAME="$2"
  sql "$OUT/existing.sql" | grep '|' > "$OUT/existing_$NAME.txt"
  CHANGED=$(diff <(sort "$OUT/existing_base.txt") <(sort "$OUT/existing_$NAME.txt") | grep '^>' | cut -d'|' -f1 | tr -d '> ' | tr '\n' ' ')
  echo "· صفوفٌ قائمةٌ تغيّرت: ${CHANGED:-لا شيء}"
  grep -h '^STOP' "$OUT/$NAME.monitor.csv" | head -3 | sed 's/^/· ⛔ /'
  "$0" counters > "$OUT/counters_$NAME.txt"; cat "$OUT/counters_$NAME.txt"
  ;;
cleanup)
  remote "cd ~/taxo && docker compose $F run --rm --no-deps -T backend python -m scripts.stress_cleanup --apply" | tail -25
  "$0" stub off
  remote "rm -f /home/taxo/secrets/stress-tokens-$RUN-*.json; ls /home/taxo/secrets | grep -c stress-tokens"
  wsl bash -c "rm -f ~/stress-prod/$RUN-*.json; ls ~/stress-prod | wc -l"
  remote "cd ~/taxo && docker compose $F run --rm --no-deps -T backend python -m scripts.stress_fingerprint" | tail -1 > "$OUT/fp_after.json"
  sql "$OUT/existing.sql" | grep '|' > "$OUT/existing_after.txt"
  diff <(sort "$OUT/existing_base.txt") <(sort "$OUT/existing_after.txt") > /dev/null && echo "✓ الصفوفُ القائمةُ بعد = قبل" || echo "✗ صفوفٌ قائمةٌ تغيّرت"
  "$0" counters > "$OUT/counters_after.txt"; cat "$OUT/counters_after.txt"
  ;;
*)
  sed -n '2,12p' "$0"; exit 2 ;;
esac
