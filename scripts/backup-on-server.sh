# shellcheck shell=bash
# **النسخةُ تُبنى وتُقاس على الخادم** (قرارُ المالك ٢٠٢٦-١١-٢٧، `design/OWNER-2026-11-27-BACKUP.md`).
#
# لا يُشغَّل هنا: `deploy.sh` يرفعه **ملتصقاً بـ`backup-metrics.sh`** إلى `$ROOT/.job-$STAMP.sh` ويشغّله هناك منفصلاً
# (`setsid nohup`) — **فانقطاعُ ssh لا يقتله**، ثمّ يقرأ `$ROOT/$STAMP.status` حتى `STATUS=DONE` أو `STATUS=FAIL`.
#
#   $1 مجلّدُ المشروع (~/taxo) · $2 جذرُ النسخ (/home/taxo/backups) · $3 الختم · $4 ملفّاتُ compose · $5 قواعدُ التجاهل الهدف (base64)
#
# **ما يجمعه هو الأربعةُ نفسُها** التي كانت البوّابةُ الثالثةُ تجمعها في اتصالها الواحد، بالأوامر نفسِها — تغيّر **المكانُ** وحدَه.
# **ويُبنى في `$STAMP.partial` ولا يُسمّى `$STAMP` إلا بعد التمام**: نسخةٌ اسمُها كاملٌ ومحتواها مقطوعٌ أخطرُ من غيابها.

set -u
set -o pipefail
PROJECT="$1"; ROOT="$2"; STAMP="$3"; COMPOSE_FILES="$4"
# قواعدُ التجاهل الهدف: وسيطٌ خامس، أو ما ألصقه `deploy.sh` في رأس الملفّ (سطرُ الأوامر على ويندوز محدود)
IGNORE_B64="${5:-${IGNORE_B64_EMBED:-}}"
umask 077
mkdir -p "$ROOT" && chmod 700 "$ROOT"
STATUS="$ROOT/$STAMP.status"

# **وإعادةُ البدء لا تشغّل اثنين**: من بدأ أوّلاً يُكمل ويكتب الحال، والثاني يخرج.
exec 9>"$ROOT/.lock"
flock -n 9 || exit 0
[ -d "$ROOT/$STAMP" ] && grep -q '^STATUS=DONE' "$STATUS" 2>/dev/null && exit 0

_status() { printf '%s\n' "$@" > "$STATUS.tmp" && mv -f "$STATUS.tmp" "$STATUS"; }
fail() { _status "STATUS=FAIL" "REASON=$1"; exit 1; }
_status "STATUS=RUNNING"

W="$ROOT/$STAMP.partial"
P="$W/parts"
rm -rf "$W"
mkdir -p "$P" || fail "تعذّر إنشاءُ $W"

# **ويقف قبل أن يبدأ إن لم يتّسع القرص**: نسخةٌ تُقطع لامتلاء القرص — وقرصُ الإنتاج نفسُه — أسوأُ من رفعٍ لم يبدأ.
free_mb=$(df -Pm "$ROOT" | awk 'NR==2{print $4}')
last=$(find "$ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' | sort | tail -1)
last_mb=0
[ -n "$last" ] && last_mb=$(du -sm "$last" | cut -f1)
need=$(( last_mb * 2 )); [ "$need" -lt 2048 ] && need=2048
[ "${free_mb:-0}" -ge "$need" ] || fail "القرصُ لا يتّسع: حرٌّ ${free_mb:-?}MB والمطلوبُ ${need}MB"

cd "$PROJECT" || fail "لا مجلّدَ للمشروع: $PROJECT"
printf '%s' "$IGNORE_B64" | base64 -d > "$W/target-ignore" 2>/dev/null || : > "$W/target-ignore"

# shellcheck disable=SC2086  # ملفّاتُ compose كلماتٌ مقصودة
docker compose $COMPOSE_FILES exec -T db pg_dump -U taxo -d taxo --no-owner | gzip -9 > "$P/taxo.sql.gz" \
  || fail "تعذّر تفريغُ القاعدة"
tar -czhf "$P/env.tar.gz" .env || fail "تعذّر نسخُ .env"

# **ما خارج الشجرة يُحسب ولا يُكتب بيد** (CLAUDE.md، القاعدةُ الأولى/١) — ولا يدخل فيه جذرُ النسخ نفسُه
HERE=$(pwd)
# shellcheck disable=SC2086
OUT=$({ docker compose $COMPOSE_FILES config 2>/dev/null | sed -n 's/^ *source: \(\/.*\)/\1/p'
        find . -maxdepth 2 -type l -exec readlink -f {} \; 2>/dev/null; } \
      | grep '^/' | grep -v "^$HERE" | grep -v "^$ROOT" \
      | while read -r q; do if [ -d "$q" ]; then echo "$q"; else dirname "$q"; fi; done | sort -u | tr '\n' ' ')
if [ -n "${OUT// /}" ]; then
  # shellcheck disable=SC2086
  tar -czhf "$P/outside.tar.gz" $OUT 2>/dev/null || : > "$P/outside.absent"
else
  : > "$P/outside.absent"
fi
echo "$OUT" > "$P/outside.list"

git ls-files --others --exclude-standard | wc -l > "$P/raw.count"
git ls-files --others --exclude-standard --exclude-from="$W/target-ignore" > "$P/untracked.list"
wc -l < "$P/untracked.list" > "$P/untracked.count"
if [ -s "$P/untracked.list" ]; then
  tar -czhf "$P/untracked.tar.gz" -T "$P/untracked.list" || : > "$P/untracked.absent"
else
  : > "$P/untracked.absent"
fi

# shellcheck disable=SC2086
docker compose $COMPOSE_FILES exec -T db psql -U taxo -d taxo -tAc 'SELECT count(*) FROM driver_documents;' 2>/dev/null \
  | tr -d ' \r\n' > "$P/docs.rows"
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES run --rm --no-deps -T --entrypoint tar backend -czf - -C /app/var/documents . 2>/dev/null \
  > "$P/documents.tar.gz" || : > "$P/documents.absent"
# shellcheck disable=SC2086
if ! docker compose $COMPOSE_FILES exec -T whatsapp-gateway tar -czf - -C /data . 2>/dev/null > "$P/wa_auth.tar.gz" \
   || [ ! -s "$P/wa_auth.tar.gz" ]; then
  rm -f "$P/wa_auth.tar.gz"; : > "$P/wa_auth.absent"
fi

# **حزمةٌ واحدةٌ وختمُها** — هي ما يُنزَّل وما يُطابَق
tar -cf "$W/bundle.tar" -C "$P" . || fail "تعذّر بناءُ الحزمة"
( cd "$W" && sha256sum bundle.tar > bundle.sha256 ) || fail "تعذّر حسابُ sha256"
{
  backup_metrics "$P"
  echo "bundle_bytes=$(stat -c %s "$W/bundle.tar")"
  echo "bundle_sha256=$(cut -d' ' -f1 "$W/bundle.sha256")"
  if tar -tf "$W/bundle.tar" > /dev/null 2>&1; then echo "bundle_tar_ok=1"; else echo "bundle_tar_ok=0"; fi
  echo "server_free_mb=$(df -Pm "$ROOT" | awk 'NR==2{print $4}')"
} > "$W/verify.txt" || fail "تعذّر قياسُ النسخة"

# الأجزاءُ في الحزمة — لا تُحفظ مرّتين على قرص الإنتاج
rm -rf "$P"
chmod 600 "$W"/* && chmod 700 "$W"
mv "$W" "$ROOT/$STAMP" || fail "تعذّرت تسميةُ النسخة"
_status "STATUS=DONE" "$(cat "$ROOT/$STAMP/verify.txt")"
chmod 600 "$STATUS"
rm -f "$ROOT/.job-$STAMP.sh"
