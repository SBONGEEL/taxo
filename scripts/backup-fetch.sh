#!/usr/bin/env bash
# **نسخةُ الحاسوب بعد الرفع** (قرارُ المالك ٢٠٢٦-١١-٢٧، `design/OWNER-2026-11-27-BACKUP.md`).
#
#   bash scripts/backup-fetch.sh <STAMP> [مجلّدُ الوجهة]
#
# ينزّل حزمةَ نسخةٍ **تحقّقت على الخادم** (`deploy.sh` البوّابةُ الثالثة) إلى الحاسوب:
#   · **يُكمل من البايت الذي وقف عنده** (`tail -c +N`) — لا يبدأ من الصفر بعد انقطاع؛
#   · **يطابق sha256** في الآخر، ثمّ يفتح الحزمةَ **ويعيد الحكمَ نفسَه** (`backup-judge.sh`) على ما وصل؛
#   · **وإن سقط بعد الإعادات: نسخةُ الخادم باقية، والجزءُ المنزَّل باقٍ يُكمَل منه، ولا يُحذف شيء** — ويخرج بغير الصفر.
# وبعد التحقّق وحدَه يكتب على الخادم علامةَ `pc-verified`، **ثمّ** يستبقي أحدثَ `TAXO_SERVER_KEEP` نسخ (٣) ولا يحذف
# أقدمَ منها **إلا ما عليه العلامة** — نسخةٌ لم تصل الحاسوبَ لا تُمسّ.
#
# **ولا يكتب على القاعدة ولا على المشروع** — جذرُ النسخ على الخادم وحدَه.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

STAMP="${1:-}"
[[ "$STAMP" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || { echo "✗ الاستعمال: bash scripts/backup-fetch.sh <STAMP مثل 20261127T030000Z>"; exit 2; }
HOST="${TAXO_DEPLOY_HOST:-taxo@169.58.207.123}"
ROOT="${TAXO_SERVER_BACKUPS:-/home/taxo/backups}"
KEEP="${TAXO_SERVER_KEEP:-3}"; [ "$KEEP" -ge 1 ] 2>/dev/null || KEEP=1
TRIES="${TAXO_FETCH_TRIES:-8}"
WAIT="${TAXO_FETCH_RETRY_SECONDS:-35}"
SRV="$ROOT/$STAMP"

_backup_dest() {
  [ -n "${TAXO_BACKUP_DEST:-}" ] && { printf '%s' "$TAXO_BACKUP_DEST"; return; }
  local r; for r in /mnt/d /d; do [ -d "$r" ] && { printf '%s/taxo-backups' "$r"; return; }; done
  printf '/mnt/d/taxo-backups'
}
D="${2:-$(_backup_dest)/$STAMP}"

# **العميلُ كما في `deploy.sh`**: وكيلُ ويندوز إن كانت فيه مفاتيحُ حيّة، وإلا ssh هذه البيئة — والتصريحُ فوق القياس
_pick_ssh() {
  [ -n "${TAXO_SSH:-}" ] && { printf '%s' "$TAXO_SSH"; return; }
  local root
  for root in /c/Windows/System32/OpenSSH /mnt/c/Windows/System32/OpenSSH; do
    if [ -x "$root/ssh.exe" ] && "$root/ssh-add.exe" -l >/dev/null 2>&1; then printf '%s' "$root/ssh.exe"; return; fi
  done
  printf 'ssh'
}
SSH="$(_pick_ssh)"
SSH_OPTS=(-o StrictHostKeyChecking=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=8
          -i "${TAXO_SSH_KEY:-$HOME/.ssh/taxo-contabo}")
# **ولا يُطرق أسرعَ من حدِّ الجدار** (ufw: ستٌّ في ثلاثين ثانية) — المباعدةُ نفسُها التي في `deploy.sh`
_GAP="${TAXO_SSH_GAP:-12}"; _LAST=0
_ssh() {
  local gap=$(( $(date +%s) - _LAST ))
  [ "$gap" -lt "$_GAP" ] && sleep $(( _GAP - gap ))
  _LAST=$(date +%s)
  "$SSH" "${SSH_OPTS[@]}" "$HOST" "$@" < /dev/null
}
say() { printf '%s\n' "$*"; }
keep_msg() { say "  نسخةُ الخادم باقيةٌ في $SRV **ولم يُحذف شيء**. الإكمالُ لاحقاً: bash scripts/backup-fetch.sh $STAMP"; }

mkdir -p "$D" || { say "✗ تعذّر إنشاءُ $D"; keep_msg; exit 1; }
PART="$D/bundle.tar.part"

say "══ نسخةُ الحاسوب — $STAMP"
INFO=""
for n in $(seq 1 "$TRIES"); do
  INFO="$(_ssh "test -s $SRV/bundle.tar && stat -c %s $SRV/bundle.tar && cut -d' ' -f1 $SRV/bundle.sha256" 2>/dev/null | tr -d '\r')" && [ -n "$INFO" ] && break
  INFO=""; say "    (لم يُقرأ حجمُ النسخة — إعادةٌ $n/$TRIES بعد ${WAIT}ث)"; sleep "$WAIT"
done
SIZE="$(printf '%s\n' "$INFO" | sed -n 1p)"; SHA="$(printf '%s\n' "$INFO" | sed -n 2p)"
if ! [[ "$SIZE" =~ ^[0-9]+$ && "$SHA" =~ ^[0-9a-f]{64}$ ]]; then
  say "✗ لا نسخةَ محقَّقةً على الخادم بهذا الختم ($SRV) — أو تعذّر قراءتُها."; keep_msg; exit 1
fi
say "  على الخادم: $SIZE بايت · sha256 ${SHA:0:12}…"

n=0
while :; do
  have=$(stat -c %s "$PART" 2>/dev/null || echo 0)
  [ "$have" -eq "$SIZE" ] && break
  if [ "$have" -gt "$SIZE" ]; then
    # **أكبرُ من الأصل = ليس منه** — يُنحّى باسمٍ يدلّ عليه، ولا يُحذف
    mv "$PART" "$PART.oversize-$(date -u +%Y%m%dT%H%M%SZ)"
    say "✗ الجزءُ المنزَّل أكبرُ من نسخة الخادم ($have > $SIZE) — نُحّي جانباً."; keep_msg; exit 1
  fi
  n=$((n + 1))
  if [ "$n" -gt "$TRIES" ]; then
    say "✗ لم يكتمل التنزيلُ بعد $TRIES محاولة — وقف عند $have من $SIZE بايت. **والجزءُ باقٍ يُكمَل منه.**"; keep_msg; exit 1
  fi
  say "  · محاولة $n/$TRIES: من البايت $((have + 1)) ($(( have * 100 / SIZE ))٪)"
  if ! _ssh "tail -c +$((have + 1)) $SRV/bundle.tar" >> "$PART"; then
    now=$(stat -c %s "$PART" 2>/dev/null || echo 0)
    say "    (انقطع عند $now — إكمالٌ من هناك بعد ${WAIT}ث)"
    sleep "$WAIT"
  fi
done

GOT="$(sha256sum "$PART" | cut -d' ' -f1)"
if [ "$GOT" != "$SHA" ]; then
  BAD="$D/bundle.tar.mismatch-$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$PART" "$BAD"
  say "✗ sha256 لا يطابق: وصل ${GOT:0:12}… والخادمُ ${SHA:0:12}… — الملفُّ نُحّي إلى $BAD ولم يُحذف."; keep_msg; exit 1
fi
mv "$PART" "$D/bundle.tar"
say "  ✓ sha256 يطابق — $SIZE بايت"

if ! tar -xf "$D/bundle.tar" -C "$D"; then
  say "✗ الحزمةُ طابقت ختمَها ولا تُفتح هنا — بقيت في $D/bundle.tar."; keep_msg; exit 1
fi
# shellcheck source=scripts/backup-metrics.sh
. scripts/backup-metrics.sh
{
  backup_metrics "$D"
  echo "bundle_bytes=$SIZE"; echo "bundle_sha256=$GOT"; echo "bundle_tar_ok=1"
} > "$D/pc-verify.txt"
say "  الحكمُ على ما وصل:"
if ! bash scripts/backup-judge.sh < "$D/pc-verify.txt"; then
  say "✗ ما وصل لا يجتاز الحكم — بقي في $D كما هو."; keep_msg; exit 1
fi
rm -f "$D/bundle.tar"   # الأجزاءُ مفتوحةٌ ومحكومٌ عليها، والحزمةُ على الخادم

# **العلامةُ بعد التحقّق وحدَه** — هي وحدَها ما يأذن بحذف نسخة الخادم لاحقاً
marked=0
for n in 1 2 3; do
  if _ssh "test -d $SRV && touch $SRV/pc-verified && chmod 600 $SRV/pc-verified && echo MARKED" 2>/dev/null | grep -q MARKED; then marked=1; break; fi
  sleep "$WAIT"
done
if [ "$marked" -ne 1 ]; then
  say "⚠ النسخةُ على الحاسوب محقَّقةٌ في $D، **وتعذّرت كتابةُ العلامة على الخادم** — فلا يُحذف منه شيء."; exit 1
fi
say "  ✓ على الحاسوب: $D ($(du -sh "$D" | cut -f1)) — وعُلِّمت على الخادم pc-verified"

# **الاستبقاء**: أحدثُ KEEP تبقى أيّاً كانت، وما أقدمُ منها لا يُحذف إلا وعليه العلامة
PRUNE="cd $ROOT 2>/dev/null || exit 0
k=0
for d in \$(find . -mindepth 1 -maxdepth 1 -type d -name '20*Z' -printf '%f\n' | sort -r); do
  k=\$((k + 1))
  [ \"\$k\" -le $KEEP ] && continue
  if [ -f \"\$d/pc-verified\" ]; then rm -rf \"\$d\" \"\$d.status\" \"\$d.log\" && echo \"DELETED \$d\"; else echo \"KEPT \$d (لا نسخةَ محقَّقةً على الحاسوب)\"; fi
done
echo \"FREE_MB \$(df -Pm . | awk 'NR==2{print \$4}')\""
_ssh "$PRUNE" 2>/dev/null | tr -d '\r' | sed 's/^/  · /' || say "  ⚠ تعذّر الاستبقاء — لم يُحذف شيء"
exit 0
