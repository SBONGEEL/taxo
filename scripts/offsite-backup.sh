#!/usr/bin/env bash
# النسخُ خارج الموقع على Google Drive المالك (أمرُ المالك ٢٠٢٦-١١-٢٢ الثاني، البند ٣ — `design/OWNER-2026-11-22-SECOND.md`).
#
# ما يفعله، بترتيبه:
#   ١) يختار **أحدثَ نسخةٍ محقَّقة** في `/mnt/d/taxo-backups` (نسخُ بوّابة الرفع الثالثة). وإن كانت أقدمَ من ٢٤ ساعة
#      يأخذ **نسخةً يوميّةً جديدةً** من الإنتاج (تفريغُ القاعدة و`.env`) **باتّصال ssh واحد** — حدُّ الجدار ستُّ محاولاتٍ في ٣٠ ث.
#   ٢) **يشفّرها قبل أن تغادر الجهاز** (gpg متناظر، AES256، عبارةُ المرور في `~/.taxo-secrets/offsite-backup.passphrase`).
#   ٣) يرفعها إلى `gdrive-taxo:TAXO-backups` (rclone بنطاق `drive.file`: **لا يرى إلا ما أنشأه هو** — مجلّدَه وملفّاتِه).
#   ٤) **يقيس ما رُفع**: الحجمُ على Drive = الحجمُ المحلّيّ، وإلا فشل.
#   ٥) **يُبقي آخرَ ١٤** ويُرسل الأقدمَ إلى سلّة Drive (لا حذفَ نهائيّ).
#   ٦) **نبضٌ إلى KV رقيبِ التوفّر** (`backup:last`) — والرقيبُ يبرق للمالك إن غاب النبضُ ٢٦ ساعة؛
#      **والفشلُ يُكتب فوراً** (`backup:fail`) فيبرق في الدقيقة التالية.
#
# ولا يمسّ الإنتاجَ إلا قراءةً (`pg_dump` و`tar` لـ`.env`)، ولا يطبع سرّاً.
set -Eeuo pipefail

SECRETS="${HOME}/.taxo-secrets"  # مجلّدُ الأسرار — مسارٌ لا سرّ
PASS_FILE="$SECRETS/offsite-backup.passphrase"
CF_FILE="$SECRETS/cloudflare-delicate-block-888e.txt"
SRC="${TAXO_BACKUP_DEST:-/mnt/d/taxo-backups}"
REMOTE="${TAXO_OFFSITE_REMOTE:-gdrive-taxo:TAXO-backups}"
KEEP="${TAXO_OFFSITE_KEEP:-14}"
LOGDIR="/mnt/c/Users/loly3/taxo-deploy-logs/offsite"
SSH_KEY="${TAXO_SSH_KEY:-/mnt/c/Users/loly3/.ssh/taxo-contabo}"
PROD="${TAXO_DEPLOY_HOST:-taxo@169.58.207.123}"
COMPOSE="--env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml"
KV_TITLE="taxo-uptime-state"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/offsite-$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "$LOG") 2>&1
WORK="$(mktemp -d)"
STEP="البدء"

say() { printf '%s  %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }

# ── KV رقيبِ التوفّر: بالرمز من الأسرار، ولا يُطبع
cf_kv_put() { # key value
  local acct tok ns
  acct="$(awk 'f{print;exit} /^Account ID/{f=1}' "$CF_FILE" | tr -d ' \r\n')"
  tok="$(awk 'f&&NF{print;exit} /^Your API Token/{f=1}' "$CF_FILE" | tr -d ' \r\n')"
  ns="$(curl -s -m 20 -H "Authorization: Bearer $tok" \
        "https://api.cloudflare.com/client/v4/accounts/$acct/storage/kv/namespaces?per_page=100" \
        | python3 -c "import json,sys;print(next((n['id'] for n in json.load(sys.stdin).get('result',[]) if n['title']=='$KV_TITLE'),''))")"
  [ -n "$ns" ] || { say "⚠ مساحةُ KV «$KV_TITLE» لم توجد — لا نبض"; return 1; }
  curl -s -m 20 -X PUT -H "Authorization: Bearer $tok" -H "Content-Type: text/plain" --data-binary "$2" \
    "https://api.cloudflare.com/client/v4/accounts/$acct/storage/kv/namespaces/$ns/values/$1" \
    | python3 -c "import json,sys;sys.exit(0 if json.load(sys.stdin).get('success') else 1)"
}

on_fail() {
  local why="فشل عند: $STEP"
  say "✗ $why"
  local now_ms; now_ms="$(($(date +%s) * 1000))"
  cf_kv_put "backup:fail" "{\"at\":$now_ms,\"why\":\"$why\"}" && say "  أُبلغ الرقيب (backup:fail)" || say "  ⚠ تعذّر إبلاغُ الرقيب"
  rm -rf "$WORK"
  exit 1
}
trap on_fail ERR

# ── ٠) الشروط
STEP="الشروط"
[ -s "$PASS_FILE" ] || { say "✗ لا عبارةَ مرور في $PASS_FILE"; false; }
if ! rclone listremotes 2>/dev/null | grep -qx "${REMOTE%%:*}:"; then
  # **قبل أن يربط المالكُ Drive: لا إنذار** — الوظيفةُ لم تبدأ بعد، وإنذارٌ يوميٌّ قبل الربط يعلّم تجاهلَ الإنذار
  say "… Drive لم يُربط بعد (${REMOTE%%:*}) — الخطوةُ عند المالك: scripts/offsite-connect.sh"
  trap - ERR; rm -rf "$WORK"; exit 3
fi

# ── ١) المصدر: أحدثُ نسخةٍ محقَّقة، أو نسخةٌ يوميّةٌ جديدة
STEP="اختيارُ النسخة"
NEWEST="$(ls -1 "$SRC" 2>/dev/null | grep -E '^20[0-9]{6}T[0-9]{6}Z$' | sort | tail -1 || true)"
AGE_H=9999
if [ -n "$NEWEST" ]; then
  AGE_H=$(( ( $(date -u +%s) - $(date -u -d "$(sed -E 's/(....)(..)(..)T(..)(..)(..)Z/\1-\2-\3 \4:\5:\6/' <<<"$NEWEST")" +%s) ) / 3600 ))
fi
if [ "$AGE_H" -le 24 ]; then
  NAME="$NEWEST"; DIR="$SRC/$NEWEST"
  say "المصدر: نسخةُ الرفع $NAME (عمرُها ${AGE_H} ساعة)"
else
  STEP="النسخةُ اليوميّةُ من الإنتاج"
  NAME="daily-$(date -u +%Y%m%dT%H%M%SZ)"; DIR="$WORK/$NAME"; mkdir -p "$DIR"
  say "أحدثُ نسخة عمرُها ${AGE_H} ساعة — نسخةٌ يوميّةٌ جديدة: $NAME"
  /mnt/c/Windows/System32/OpenSSH/ssh.exe -i "$(wslpath -w "$SSH_KEY")" -o BatchMode=yes "$PROD" \
    "cd ~/taxo && W=\$(mktemp -d) && docker compose $COMPOSE exec -T db pg_dump -U taxo -d taxo --no-owner | gzip -9 > \$W/taxo.sql.gz && tar -czhf \$W/env.tar.gz .env && tar -cf - -C \$W . && rm -rf \$W" \
    < /dev/null > "$DIR/bundle.tar"
  tar -xf "$DIR/bundle.tar" -C "$DIR" && rm -f "$DIR/bundle.tar"
  gzip -t "$DIR/taxo.sql.gz"
  zcat "$DIR/taxo.sql.gz" | tail -5 | grep -q "PostgreSQL database dump complete" || { say "✗ التفريغُ ناقص"; false; }
  [ "$(tar -xzOf "$DIR/env.tar.gz" .env | grep -c '=')" -ge 3 ] || { say "✗ .env في النسخة بلا قيم"; false; }
fi

OBJ="taxo-$NAME.tar.gpg"
if rclone lsf "$REMOTE" --files-only 2>/dev/null | grep -qx "$OBJ"; then
  say "✓ $OBJ مرفوعةٌ سلفاً — لا رفعَ ثانٍ"
else
  # ── ٢) التشفير قبل المغادرة
  STEP="التشفير"
  tar -C "$(dirname "$DIR")" -cf - "$(basename "$DIR")" \
    | gpg --batch --yes --pinentry-mode loopback --passphrase-file "$PASS_FILE" \
          --symmetric --cipher-algo AES256 --compress-algo none -o "$WORK/$OBJ"
  LOCAL_SIZE="$(stat -c %s "$WORK/$OBJ")"
  # والمشفَّرُ يُفكّ قبل أن يُرفع — نسخةٌ لا تُفكّ ليست نسخة
  gpg --batch --pinentry-mode loopback --passphrase-file "$PASS_FILE" -d "$WORK/$OBJ" 2>/dev/null | tar -tf - >/dev/null
  say "مشفَّرة: $OBJ ($((LOCAL_SIZE / 1048576)) MB) — وتُفكّ ✓"

  # ── ٣) الرفع  ٤) القياس
  STEP="الرفع"
  rclone copyto "$WORK/$OBJ" "$REMOTE/$OBJ" --retries 3 --low-level-retries 10
  STEP="قياسُ ما رُفع"
  REMOTE_SIZE="$(rclone lsjson "$REMOTE/$OBJ" | python3 -c 'import json,sys;print(json.load(sys.stdin)[0]["Size"])')"
  [ "$REMOTE_SIZE" = "$LOCAL_SIZE" ] || { say "✗ الحجمُ على Drive $REMOTE_SIZE ≠ $LOCAL_SIZE"; false; }
  say "✓ رُفعت وقِيست: $REMOTE/$OBJ ($REMOTE_SIZE بايت)"
fi

# ── ٥) آخرُ ١٤ — والأقدمُ إلى سلّة Drive
STEP="الاحتفاظ"
mapfile -t ALL < <(rclone lsf "$REMOTE" --files-only | grep -E '^taxo-.*\.tar\.gpg$' \
                   | sed -E 's/^taxo-(daily-)?(.*)\.tar\.gpg$/\2 &/' | sort | awk '{print $2}')
if [ "${#ALL[@]}" -gt "$KEEP" ]; then
  for old in "${ALL[@]:0:${#ALL[@]}-KEEP}"; do
    rclone deletefile "$REMOTE/$old" --drive-use-trash=true && say "  إلى السلّة: $old"
  done
fi
say "على Drive الآن: $(rclone lsf "$REMOTE" --files-only | grep -c '\.tar\.gpg$') نسخة (الحدّ $KEEP)"

# ── ٥-ب) **رقيبُ نسخة الخادم** (أمرُ المالك ٢٣/١١ الجزء ١): الخادمُ يرفع وحدَه إلى `server/`؛ والحاسوبُ — حين يعمل — يقيس أنّ أحدثَها
#     أحدثُ من ٢٦ ساعة، وإلا كتب `backup:fail` فأبرق الرقيب. **وقبل أوّل نسخةٍ من الخادم لا إنذار**.
STEP="رقيبُ نسخة الخادم"
SRV_NEWEST="$(rclone lsf "$REMOTE/server" --files-only 2>/dev/null | grep -E '^taxo-server-.*\.tar\.gpg$' | sort | tail -1 || true)"
if [ -n "$SRV_NEWEST" ]; then
  SRV_AGE_H=$(( ( $(date -u +%s) - $(date -u -d "$(sed -E 's/^taxo-server-(....)(..)(..)T(..)(..)(..)Z.*/\1-\2-\3 \4:\5:\6/' <<<"$SRV_NEWEST")" +%s) ) / 3600 ))
  if [ "$SRV_AGE_H" -gt 26 ]; then
    say "⚠ أحدثُ نسخةٍ من الخادم عمرُها ${SRV_AGE_H} ساعة ($SRV_NEWEST)"
    cf_kv_put "backup:fail" "{\"at\":$(($(date +%s) * 1000)),\"why\":\"نسخةُ الخادم متأخّرة ${SRV_AGE_H} ساعة\"}" || true
  else
    say "✓ نسخةُ الخادم حديثة: $SRV_NEWEST (${SRV_AGE_H} ساعة)"
  fi
fi

# ── ٦) النبض
STEP="النبض"
cf_kv_put "backup:last" "$(($(date +%s) * 1000))" && say "✓ النبضُ إلى الرقيب (backup:last)"
rm -rf "$WORK"
trap - ERR
say "✓ تمّ"
