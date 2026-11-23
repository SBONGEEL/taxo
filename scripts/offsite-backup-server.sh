#!/usr/bin/env bash
# **النسخُ خارج الموقع من الخادم نفسِه** (أمرُ المالك ٢٠٢٦-١١-٢٣، الجزء ١) — فلا تتوقّف النسخةُ اليوميّةُ على حاسوب المالك.
# يُشغَّل من crontab المستخدم taxo يوميّاً، **ونسخةُ الحاسوب (`scripts/offsite-backup.sh`) باقيةٌ نسخةً ثانية**.
#
# ما يفعله، بترتيبه:
#   ١) تفريغُ القاعدة + `.env` (بـ`-h`: الوصلةُ لا تُنسخ فارغة) + الوثائق + مجلّدُ الأسرار **عدا عبارةِ المرور وإذنِ Drive**
#      (لا يوضع مفتاحُ الفكّ بجوار ما يفكّه، ولا إذنُ الرفع في ما يُرفع).
#   ٢) **يشفّرها قبل أن تغادر** (gpg متناظر AES256، العبارةُ `~/secrets/offsite-backup.passphrase` 600) ويفكّها للتحقّق قبل الرفع.
#   ٣) يرفعها إلى `TAXO-backups/server/` — **إذنُ Drive مشفَّرٌ على القرص** (`~/secrets/rclone.conf.gpg`، ومفتاحُه `~/secrets/rclone-conf.key` 600)
#      ويُفكّ إلى ذاكرةٍ (`/dev/shm`) وقتَ التشغيل وحدَه، ثم يُعاد تشفيرُه (Google يجدّد الرمز). والجذرُ مجلّدُ TAXO-backups وحدَه
#      (`root_folder_id`، ونطاقُ `drive.file`): لا يرى rclone شيئاً غيرَه.
#   ٤) يقيس الحجمَ على Drive = المحلّيّ · ٥) يُبقي آخرَ ١٤ في `server/` والأقدمُ إلى سلّة Drive.
#   ٦) **الفشلُ بريدٌ فوريٌّ للمالك** عبر مُرسِل البريد في الخلفيّة (Resend) — والعنوانُ في `~/secrets/offsite.env` لا في المستودع.
#      **وغيابُ نسخة الخادم ٢٦ ساعةً** يرصده الحاسوب (`offsite-backup.sh`) فيبرق رقيبُ التوفّر.
set -Eeuo pipefail
SEC="${HOME}/secrets"
PASS_FILE="${SEC}/offsite-backup.passphrase"
CONF_GPG="${SEC}/rclone.conf.gpg"
CONF_KEY="${SEC}/rclone-conf.key"
RCLONE="${HOME}/bin/rclone"
REMOTE="gdrive-taxo:server"
KEEP="${TAXO_OFFSITE_KEEP:-14}"
APP="${HOME}/taxo"
COMPOSE=(docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml)
LOGDIR="${HOME}/offsite-logs"; mkdir -p "$LOGDIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
exec > >(tee -a "$LOGDIR/offsite-$STAMP.log") 2>&1
WORK="$(mktemp -d "${HOME}/offsite-work.XXXXXX")"; chmod 700 "$WORK"
SHM="$(mktemp -d /dev/shm/taxo-rc.XXXXXX)"; chmod 700 "$SHM"; CONF="$SHM/rclone.conf"
STEP="البدء"
say() { printf '%s  %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }
cleanup() { rm -rf "$WORK"; [ -f "$CONF" ] && shred -u "$CONF" 2>/dev/null; rm -rf "$SHM"; }
trap cleanup EXIT

alert() { # النصُّ للمالك — لا سرَّ فيه
  local to; to="$(grep -m1 '^ALERT_TO=' "$SEC/offsite.env" 2>/dev/null | cut -d= -f2- || true)"
  [ -n "$to" ] || { say "⚠ لا عنوانَ تنبيهٍ في offsite.env"; return 1; }
  ( cd "$APP" && "${COMPOSE[@]}" exec -T -e TO="$to" -e WHY="$1" backend python -c '
import asyncio, os
from app.core.db import SessionLocal
from app.models.enums import ProviderKey
from app.services.email import build_provider
from app.services.providers import credentials as cs
async def main():
    async with SessionLocal() as s:
        v = await cs.get_values(s, ProviderKey.EMAIL)
    await build_provider(v).send(os.environ["TO"], subject="⚠ TAXO: النسخةُ الخارجيّةُ من الخادم لم تُرفع",
        body="فشل رفعُ النسخة المشفَّرة من الخادم إلى Google Drive.\nالسبب: " + os.environ["WHY"] +
             "\nالسجلّ على الخادم: ~/offsite-logs\nنسخةُ الحاسوب الثانية تعمل مستقلّةً عنها.")
asyncio.run(main())' ) >/dev/null 2>&1
}
on_fail() { say "✗ فشل عند: $STEP"; alert "فشل عند: $STEP" && say "  أُبلغ المالكُ بالبريد" || say "  ⚠ تعذّر بريدُ التنبيه"; exit 1; }
trap on_fail ERR

STEP="الشروط"
[ -s "$PASS_FILE" ] || { say "✗ لا عبارةَ مرور"; false; }
if [ ! -s "$CONF_GPG" ] || [ ! -x "$RCLONE" ]; then
  say "… Drive لم يُربط على الخادم بعد (rclone.conf.gpg) — لا رفعَ ولا تنبيه"; trap - ERR; exit 3
fi
gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$CONF_KEY" -d "$CONF_GPG" > "$CONF"; chmod 600 "$CONF"
rc() { "$RCLONE" --config "$CONF" "$@"; }
reseal() { # الرمزُ المجدَّد يعود مشفَّراً إلى القرص
  gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$CONF_KEY" --symmetric --cipher-algo AES256 -o "$CONF_GPG.new" "$CONF" \
    && chmod 600 "$CONF_GPG.new" && mv "$CONF_GPG.new" "$CONF_GPG"
}

STEP="التفريغ"
NAME="taxo-server-$STAMP"; DIR="$WORK/$NAME"; mkdir -p "$DIR"
cd "$APP"
"${COMPOSE[@]}" exec -T db pg_dump -U taxo -d taxo --no-owner | gzip -9 > "$DIR/taxo.sql.gz"
zcat "$DIR/taxo.sql.gz" | tail -5 | grep -q "PostgreSQL database dump complete" || { say "✗ التفريغُ ناقص"; false; }
tar -czhf "$DIR/env.tar.gz" .env
[ "$(tar -xzOf "$DIR/env.tar.gz" .env | grep -c '=')" -ge 3 ] || { say "✗ .env بلا قيم"; false; }
"${COMPOSE[@]}" run --rm --no-deps -T --entrypoint tar backend -czf - -C /app/var/documents . 2>/dev/null > "$DIR/documents.tar.gz"
gzip -t "$DIR/documents.tar.gz"
tar -czf "$DIR/secrets.tar.gz" -C "$HOME" --exclude='secrets/offsite-backup.passphrase' --exclude='secrets/rclone*' secrets
say "مُفرَّغة: القاعدة $(du -h "$DIR/taxo.sql.gz" | cut -f1) · الوثائق $(du -h "$DIR/documents.tar.gz" | cut -f1)"

STEP="التشفير"
OBJ="$NAME.tar.gpg"
tar -C "$WORK" -cf - "$NAME" | gpg --batch --yes --pinentry-mode loopback --passphrase-file "$PASS_FILE" \
  --symmetric --cipher-algo AES256 --compress-algo none -o "$WORK/$OBJ"
gpg --batch --pinentry-mode loopback --passphrase-file "$PASS_FILE" -d "$WORK/$OBJ" 2>/dev/null | tar -tf - >/dev/null
LOCAL_SIZE="$(stat -c %s "$WORK/$OBJ")"
say "مشفَّرة وتُفكّ ✓ ($((LOCAL_SIZE / 1048576)) MB)"

STEP="الرفع"
rc copyto "$WORK/$OBJ" "$REMOTE/$OBJ" --retries 3 --low-level-retries 10
STEP="قياسُ ما رُفع"
REMOTE_SIZE="$(rc lsjson "$REMOTE/$OBJ" | python3 -c 'import json,sys;print(json.load(sys.stdin)[0]["Size"])')"
[ "$REMOTE_SIZE" = "$LOCAL_SIZE" ] || { say "✗ الحجمُ على Drive $REMOTE_SIZE ≠ $LOCAL_SIZE"; false; }
say "✓ رُفعت وقِيست: $REMOTE/$OBJ"

STEP="الاحتفاظ"
mapfile -t ALL < <(rc lsf "$REMOTE" --files-only | grep -E '^taxo-server-.*\.tar\.gpg$' | sort)
if [ "${#ALL[@]}" -gt "$KEEP" ]; then
  for old in "${ALL[@]:0:${#ALL[@]}-KEEP}"; do rc deletefile "$REMOTE/$old" --drive-use-trash=true && say "  إلى السلّة: $old"; done
fi
say "على Drive (server/): $(rc lsf "$REMOTE" --files-only | grep -c '\.tar\.gpg$') نسخة (الحدّ $KEEP)"
reseal
find "$LOGDIR" -name 'offsite-*.log' -mtime +30 -delete
trap - ERR
say "✓ تمّ"
