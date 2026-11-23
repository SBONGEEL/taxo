#!/usr/bin/env bash
# **ينقل إذنَ Drive إلى الخادم ويركّب نسختَه اليوميّة** (أمرُ المالك ٢٠٢٦-١١-٢٣، الجزء ١). يُشغَّل في WSL **بعد** `offsite-connect.sh`.
#
#   ١) يقرأ رقمَ مجلّد «TAXO-backups» على Drive، ويبني إعدادَ rclone للخادم **بجذرٍ هو المجلّدُ وحدَه** (`root_folder_id`) ونطاقِ `drive.file`.
#   ٢) **يشفّره في الذاكرة** (gpg AES256 بمفتاحٍ عشوائيٍّ جديد) ويرسله إلى `~/secrets/rclone.conf.gpg`، ومفتاحَه إلى `~/secrets/rclone-conf.key`
#      — كلاهما 600 — **ولا يُكتب الإعدادُ صريحاً على أيِّ قرص**، ولا يُطبع.
#   ٣) يرسل rclone إلى `~/bin/rclone`، وعنوانَ التنبيه إلى `~/secrets/offsite.env`، ويركّب سطرَ crontab (02:30Z = 05:30 عمّان).
# كلُّ اتّصال ssh بفاصل ٧ ثوانٍ (حدُّ الجدار).
set -euo pipefail
NAME="gdrive-taxo"; FOLDER="TAXO-backups"
SSH_KEY="${TAXO_SSH_KEY:-/mnt/c/Users/loly3/.ssh/taxo-contabo}"; PROD="${TAXO_DEPLOY_HOST:-taxo@169.58.207.123}"
ALERT_TO="${TAXO_ALERT_TO:?عنوانُ تنبيه المالك — TAXO_ALERT_TO}"
ssh_() { sleep 7; /mnt/c/Windows/System32/OpenSSH/ssh.exe -i "$(wslpath -w "$SSH_KEY")" -o BatchMode=yes "$PROD" "$@"; }

rclone listremotes | grep -qx "$NAME:" || { echo "✗ Drive لم يُربط على الحاسوب بعد — شغّل offsite-connect.sh أوّلاً"; exit 1; }
FID="$(rclone lsjson "$NAME:" --dirs-only | python3 -c "import json,sys;print(next(d['ID'] for d in json.load(sys.stdin) if d['Name']=='$FOLDER'))")"
[ -n "$FID" ] || { echo "✗ لم يوجد مجلّد $FOLDER"; exit 1; }
echo "✓ مجلّد $FOLDER موجود"

SHM="$(mktemp -d /dev/shm/taxo-inst.XXXXXX)"; chmod 700 "$SHM"; trap 'rm -rf "$SHM"' EXIT
openssl rand -base64 48 | tr -d '\n' > "$SHM/key"; chmod 600 "$SHM/key"
rclone config dump | FID="$FID" python3 -c '
import json, os, sys
r = json.load(sys.stdin)["gdrive-taxo"]
out = ["[gdrive-taxo]", "type = drive", "scope = drive.file", "root_folder_id = " + os.environ["FID"], "token = " + r["token"]]
for k in ("client_id", "client_secret", "team_drive"):
    if r.get(k): out.append(f"{k} = {r[k]}")
sys.stdout.write("\n".join(out) + "\n")' \
  | gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$SHM/key" --symmetric --cipher-algo AES256 -o "$SHM/rclone.conf.gpg"
echo "✓ الإعدادُ مشفَّرٌ في الذاكرة"

ssh_ 'umask 077; cat > ~/secrets/rclone-conf.key && chmod 600 ~/secrets/rclone-conf.key' < "$SHM/key"
ssh_ 'umask 077; cat > ~/secrets/rclone.conf.gpg && chmod 600 ~/secrets/rclone.conf.gpg' < "$SHM/rclone.conf.gpg"
ssh_ 'mkdir -p ~/bin && cat > ~/bin/rclone && chmod 755 ~/bin/rclone && ~/bin/rclone version | head -1' < "$(command -v rclone)"
printf 'ALERT_TO=%s\n' "$ALERT_TO" | ssh_ 'umask 077; cat > ~/secrets/offsite.env && chmod 600 ~/secrets/offsite.env'
ssh_ '( crontab -l 2>/dev/null | grep -v offsite-backup-server.sh; echo "30 2 * * * \$HOME/taxo/scripts/offsite-backup-server.sh >/dev/null 2>&1" ) | crontab - && crontab -l | grep -c offsite-backup-server.sh && stat -c "%a %n" ~/secrets/rclone.conf.gpg ~/secrets/rclone-conf.key ~/secrets/offsite.env'
echo "✓ رُكّب: إذنُ Drive مشفَّرٌ على الخادم، وrclone، والتنبيه، وcrontab اليوميّ"
