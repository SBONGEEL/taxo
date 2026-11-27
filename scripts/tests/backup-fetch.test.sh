#!/usr/bin/env bash
# **النسخةُ على الخادم أوّلاً، والحاسوبُ بعد الرفع** (قرارُ المالك ٢٠٢٦-١١-٢٧، `design/OWNER-2026-11-27-BACKUP.md`).
#
# يُقاس **السلوكُ** على خادمٍ مزيَّف (ssh يُشغّل الأمرَ هنا في مجلّدٍ مؤقّت) — لا شبكةَ ولا خادم:
#  ١) انقطاعٌ في منتصف التنزيل ⇒ **يُكمَل من البايت نفسِه لا من الصفر**، ويطابق sha256، ويُعلَّم pc-verified.
#  ٢) الاستبقاء ⇒ أحدثُ KEEP تبقى، **وما لا علامةَ عليه لا يُحذف** ولو كان أقدم.
#  ٣) sha256 مخالف ⇒ لا علامة، ولا حذفَ على الخادم، والملفُّ يُنحّى ولا يُحذف.
#  ٤) إعاداتٌ تنفد ⇒ يخرج بغير الصفر، **والجزءُ باقٍ يُكمَل منه**، والخادمُ كما هو.
#  ٥) الحَكَم ⇒ يُسقط ما كانت البوّابةُ الرابعةُ تُسقطه (وخاتمةَ التفريغ الغائبة)، ويُخضِّر السليم.
set -uo pipefail
cd "$(dirname "$0")/../.."
# **ولا يرث متغيّراتِ git من خطّاف الإيداع** (قِيس ٢٠٢٦-١١-٢٧): تحت `pre-commit` يحمل البيتُ `GIT_DIR`/`GIT_INDEX_FILE`، فكان
# `git commit` في «المشروع المزيَّف» أدناه **يُودِع فهرسَ المستودع الحقيقيّ** بإيداعٍ اسمُه «init». فيُنزع كلُّ `GIT_*` قبل أيِّ git.
while IFS= read -r _v; do unset "$_v"; done < <(compgen -e | grep '^GIT_')

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok()  { printf '  ✓ %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  ✗ %s\n     %s\n' "$1" "${2:0:300}"; fail=$((fail+1)); }

ROOT="$TMP/root"; mkdir -p "$ROOT"
# ssh مزيَّف: الأمرُ هو آخرُ وسيط، ويُشغَّل هنا. وملفُّ drop يقطع البثَّ بعد عددٍ من البايتات (count مرّةً)
cat > "$TMP/fake-ssh" <<EOF
#!/usr/bin/env bash
cmd="\${@: -1}"
printf '%s\n' "\$cmd" >> "$TMP/ssh.log"
if [[ "\$cmd" == tail\ -c* ]] && [ -s "$TMP/drop" ]; then
  read -r bytes count < "$TMP/drop"
  if [ "\$count" -gt 0 ]; then
    echo "\$bytes \$((count - 1))" > "$TMP/drop"
    bash -c "\$cmd" | head -c "\$bytes"
    exit 255
  fi
fi
exec bash -c "\$cmd"
EOF
chmod +x "$TMP/fake-ssh"
export TAXO_SSH="$TMP/fake-ssh" TAXO_SSH_GAP=0 TAXO_FETCH_RETRY_SECONDS=0 TAXO_SERVER_BACKUPS="$ROOT" TAXO_SERVER_KEEP=2

make_backup() { # ختم — يبني نسخةً سليمةً على «الخادم»
  local s="$1" p="$TMP/parts-$1"
  mkdir -p "$p" "$TMP/env-$1"
  { echo "-- PostgreSQL database dump"; for i in $(seq 1 25); do echo "CREATE TABLE t$i (id int);"; done
    head -c 200000 /dev/urandom | base64; echo "-- PostgreSQL database dump complete"; } | gzip -9 > "$p/taxo.sql.gz"
  printf 'A_ONE=1\nB_TWO=2\nC_THREE=3\nD_FOUR=4\nE_FIVE=5\n' > "$TMP/env-$1/.env"
  tar -czf "$p/env.tar.gz" -C "$TMP/env-$1" .env
  echo 0 > "$p/raw.count"; echo 0 > "$p/untracked.count"; : > "$p/outside.list"
  mkdir -p "$ROOT/$s"
  tar -cf "$ROOT/$s/bundle.tar" -C "$p" .
  ( cd "$ROOT/$s" && sha256sum bundle.tar > bundle.sha256 )
}

printf '\n  النسخةُ على الخادم أوّلاً، والحاسوبُ بعد الرفع\n\n'

# ١ و٢) انقطاعٌ ثمّ إكمال، ثمّ الاستبقاء
S1=20261127T030000Z
make_backup "$S1"
for old in 20250101T000000Z 20250102T000000Z 20250103T000000Z; do mkdir -p "$ROOT/$old"; done
touch "$ROOT/20250101T000000Z/pc-verified" "$ROOT/20250103T000000Z/pc-verified"
echo "4096 1" > "$TMP/drop"; : > "$TMP/ssh.log"
out="$(bash scripts/backup-fetch.sh "$S1" "$TMP/pc/$S1" 2>&1)"; code=$?
tails="$(grep -c '^tail -c' "$TMP/ssh.log")"
if [ "$code" -eq 0 ] && grep -q '^tail -c +1 ' "$TMP/ssh.log" && grep -q '^tail -c +4097 ' "$TMP/ssh.log" && [ "$tails" -eq 2 ]; then
  ok "انقطع عند 4096 فأكمل من البايت 4097 — لا من الصفر (محاولتان)"
else bad "لم يُكمَل من موضع الانقطاع" "code=$code tails=$tails $(tr '\n' '|' < "$TMP/ssh.log") $out"; fi
if [ -f "$ROOT/$S1/pc-verified" ] && [ -s "$TMP/pc/$S1/taxo.sql.gz" ] && [ ! -e "$TMP/pc/$S1/bundle.tar.part" ]; then
  ok "طابق sha256 وفُتحت الأجزاءُ على الحاسوب، وعُلِّمت النسخةُ على الخادم"
else bad "لم يُعلَّم أو لم يُفتح" "$out"; fi
if [ -d "$ROOT/$S1" ] && [ -d "$ROOT/20250103T000000Z" ] && [ -d "$ROOT/20250102T000000Z" ] && [ ! -e "$ROOT/20250101T000000Z" ]; then
  ok "الاستبقاء: أحدثُ اثنتين باقيتان، والأقدمُ بلا علامةٍ باقية، والأقدمُ المعلَّمةُ وحدَها حُذفت"
else bad "الاستبقاءُ مسّ ما لا يُمسّ أو لم يحذف المعلَّم" "$(ls "$ROOT" | tr '\n' ' ') $out"; fi

# ٣) sha256 مخالف
S2=20261127T040000Z
make_backup "$S2"
echo "0000000000000000000000000000000000000000000000000000000000000000  bundle.tar" > "$ROOT/$S2/bundle.sha256"
: > "$TMP/drop"
out="$(bash scripts/backup-fetch.sh "$S2" "$TMP/pc/$S2" 2>&1)"; code=$?
if [ "$code" -ne 0 ] && [ ! -e "$ROOT/$S2/pc-verified" ] && [ -s "$ROOT/$S2/bundle.tar" ] && ls "$TMP/pc/$S2"/bundle.tar.mismatch-* >/dev/null 2>&1; then
  ok "sha256 المخالف: لا علامة، ونسخةُ الخادم كما هي، والملفُّ نُحّي ولم يُحذف"
else bad "sha256 المخالف عومل كسليم أو حُذف شيء" "code=$code $out"; fi

# ٤) إعاداتٌ تنفد
S3=20261127T050000Z
make_backup "$S3"
echo "1000 99" > "$TMP/drop"
out="$(TAXO_FETCH_TRIES=3 bash scripts/backup-fetch.sh "$S3" "$TMP/pc/$S3" 2>&1)"; code=$?
part_size=$(stat -c %s "$TMP/pc/$S3/bundle.tar.part" 2>/dev/null || echo 0)
if [ "$code" -ne 0 ] && [ "$part_size" -eq 3000 ] && [ ! -e "$ROOT/$S3/pc-verified" ] && [ -s "$ROOT/$S3/bundle.tar" ] \
   && printf '%s' "$out" | grep -q "لم يُحذف شيء"; then
  ok "ثلاثُ محاولاتٍ نفدت: الجزءُ باقٍ (3000 بايت يُكمَل منها)، والخادمُ كما هو، ويقول «لم يُحذف شيء»"
else bad "الإعاداتُ النافدة حذفت أو علّمت" "code=$code part=$part_size $out"; fi
# ويُكمَل لاحقاً من الجزء نفسِه
: > "$TMP/drop"; : > "$TMP/ssh.log"
out="$(bash scripts/backup-fetch.sh "$S3" "$TMP/pc/$S3" 2>&1)"; code=$?
if [ "$code" -eq 0 ] && grep -q '^tail -c +3001 ' "$TMP/ssh.log" && [ -f "$ROOT/$S3/pc-verified" ]; then
  ok "وإعادةُ التشغيل لاحقاً أكملت من البايت 3001 وعلّمت"
else bad "إعادةُ التشغيل لم تُكمل من الجزء" "code=$code $(tr '\n' '|' < "$TMP/ssh.log")"; fi

# ٥) الحَكَم
good='present_taxo=1
bytes_taxo=900
gzip_taxo=1
sql_header=1
sql_tables=40
sql_complete=1
present_env=1
bytes_env=300
gzip_env=1
env_lines=12
present_documents=1
bytes_documents=5000
gzip_documents=1
doc_files=37
doc_rows=37
present_wa_auth=0
bundle_bytes=9000
bundle_sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
bundle_tar_ok=1'
judge() { printf '%s\n' "$1" | bash scripts/backup-judge.sh > /dev/null 2>&1; }
judge "$good" && ok "الحَكَم: نسخةٌ سليمةٌ تخضرّ" || bad "الحَكَم أسقط نسخةً سليمة" "$(printf '%s\n' "$good" | bash scripts/backup-judge.sh)"
for case in 'sql_complete=0|تفريغٌ بلا خاتمة' 'doc_files=0|صفوفٌ بلا ملفّات' 'doc_rows=|صفوفٌ لم تُقرأ' 'env_lines=0|.env وصلةٌ بلا سرّ' \
            'sql_tables=3|جداولُ أقلُّ من عشرين' 'gzip_taxo=0|قاعدةٌ لا تُفتح' 'bundle_tar_ok=0|حزمةٌ لا تُفتح' 'present_env=0|.env غائب'; do
  kv="${case%%|*}"; label="${case#*|}"; key="${kv%%=*}"
  m="$(printf '%s\n' "$good" | grep -v "^$key=")"$'\n'"$kv"
  if judge "$m"; then bad "الحَكَم خضّر: $label" "$kv"; else ok "الحَكَم يُسقط: $label"; fi
done

# ٦) مهمّةُ الخادم نفسُها — على مشروعٍ مزيَّف وdocker مزيَّف: تبني وتقيس وتسمّي بعد التمام، والصلاحيّاتُ 600، والحَكَمُ يخضرّ
P6="$TMP/srv-project"; OUTSIDE="$TMP/srv-secrets"; BIN="$TMP/bin"; R6="$TMP/srv-backups"
mkdir -p "$P6" "$OUTSIDE/cloudflared" "$BIN"
echo '{}' > "$OUTSIDE/cloudflared/t.json"; echo id > "$OUTSIDE/tunnel-id"
printf 'A_ONE=1\nB_TWO=2\nC_THREE=3\nD_FOUR=4\nE_FIVE=5\n' > "$P6/.env"
( cd "$P6" && git init -q && git -c user.email=t@t -c user.name=t commit -q --allow-empty -m init && echo x > stray.txt )
cat > "$BIN/docker" <<EOF
#!/usr/bin/env bash
a="\$*"
case "\$a" in
  *pg_dump*) echo "-- PostgreSQL database dump"; for i in \$(seq 1 22); do echo "CREATE TABLE t\$i (id int);"; done; echo "-- PostgreSQL database dump complete" ;;
  *psql*) echo " 2" ;;
  *" config"*) echo "      source: $OUTSIDE" ;;
  *"run --rm"*) d=\$(mktemp -d); echo a > "\$d/one.pdf"; echo b > "\$d/two.pdf"; tar -czf - -C "\$d" . ;;
  *whatsapp-gateway*) d=\$(mktemp -d); echo '{}' > "\$d/creds.json"; tar -czf - -C "\$d" . ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$BIN/docker"
JOB6="$TMP/job6.sh"
{ printf "IGNORE_B64_EMBED='%s'\n" "$(printf 'stray-ignored/\n' | base64 -w0)"; cat scripts/backup-metrics.sh scripts/backup-on-server.sh; } > "$JOB6"
S6=20261127T060000Z
PATH="$BIN:$PATH" bash "$JOB6" "$P6" "$R6" "$S6" "-f a.yml" > "$TMP/job6.log" 2>&1
st="$(sed -n 's/^STATUS=//p' "$R6/$S6.status" 2>/dev/null | head -1)"
perm_dir=$(stat -c %a "$R6/$S6" 2>/dev/null); perm_b=$(stat -c %a "$R6/$S6/bundle.tar" 2>/dev/null)
if [ "$st" = DONE ] && [ ! -e "$R6/$S6.partial" ] && [ "$perm_dir" = 700 ] && [ "$perm_b" = 600 ] && [ ! -e "$R6/$S6/parts" ] \
   && ( cd "$R6/$S6" && sha256sum -c --quiet bundle.sha256 ); then
  ok "مهمّةُ الخادم: بنت وسمّت بعد التمام، والمجلّدُ 700 والحزمةُ 600، وsha256 يطابق، ولا أجزاءَ مكرَّرة"
else bad "مهمّةُ الخادم لم تتمّ كما ينبغي" "st=$st dir=$perm_dir bundle=$perm_b $(tail -5 "$TMP/job6.log")"; fi
if grep -v '^STATUS=' "$R6/$S6.status" | bash scripts/backup-judge.sh > "$TMP/judge6.out" 2>&1 \
   && grep -q 'بيانُ النفق ومعرِّفُه: 2' "$TMP/judge6.out" && grep -q 'الوثائق — 2 ملفّاً · 2 صفّاً' "$TMP/judge6.out"; then
  ok "وأرقامُها تخضرّ في الحَكَم: الخاتمة، و.env، والنفق، والوثائقُ مقابل صفوفها"
else bad "الحَكَمُ لم يخضرّ على مهمّة الخادم" "$(cat "$TMP/judge6.out")"; fi
mt=$(stat -c %Y "$R6/$S6/bundle.tar")
PATH="$BIN:$PATH" bash "$JOB6" "$P6" "$R6" "$S6" "-f a.yml" > /dev/null 2>&1
[ "$(stat -c %Y "$R6/$S6/bundle.tar")" = "$mt" ] && ok "وإعادةُ بدئها بعد التمام لا تعيد البناء" || bad "إعادةُ البدء أعادت البناء" ""
# وقفلٌ مأخوذٌ ⇒ الثانيةُ تخرج ولا تبني (كأنّ الأولى ما زالت تعمل)
S7=20261127T070000Z
( exec 9>"$R6/.lock"; flock 9; PATH="$BIN:$PATH" bash "$JOB6" "$P6" "$R6" "$S7" "-f a.yml" > /dev/null 2>&1 )
[ ! -e "$R6/$S7" ] && [ ! -e "$R6/$S7.partial" ] && ok "والقفلُ يمنع مهمّتين معاً" || bad "مهمّتان بنتا معاً" ""

printf '\n  ✓ %s · ✗ %s\n\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
