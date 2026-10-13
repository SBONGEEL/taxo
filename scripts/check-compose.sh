#!/usr/bin/env bash
# check-compose.sh — **كلُّ تركيبةِ ملفّاتِ compose تُقرأ بالأداة نفسِها التي يرفع بها الخادم** (`docker compose config --quiet`).
#
# **العلّةُ مقيسة** (٢٠٢٦-١٠-١٣، SPEC §٧٥-هـ): كتلتا `environment` لخدمةٍ واحدةٍ في `docker-compose.prod-tunnel.yml` — YAML يرفضه compose —
# **مرّتا من الحرّاس كلِّها ومن CI** لأن أحداً لا يقرأ ذلك الملفّ قبل الخادم، **فوقف الرفعُ في بوّابته الخامسة** على الإنتاج.
#
# **والقيمُ المطلوبة** (`${VAR:?}`) **تُولَّد عشوائيّةً لكلِّ تشغيل** — لا سرَّ مكتوباً ولا بيئةَ حقيقيّةً تُقرأ. **وغيابُ docker يُسقط الحارس**:
# أداةُ قياسٍ غائبةٌ لا تُقرأ سلامة.
set -uo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null 2>&1 || { echo "✗ check:compose — لا docker هنا: لم يُقَس"; exit 1; }
E="$(mktemp)"; trap 'rm -f "$E"' EXIT
grep -ohE '\$\{[A-Z_][A-Z0-9_]*:\?' docker-compose*.yml | tr -d '${:?' | sort -u | while read -r v; do
  printf '%s=%s\n' "$v" "$(openssl rand -hex 16)"
done > "$E"
bad=0
checked=0
# **التركيباتُ من مصادرها لا من قائمةٍ تُكتب هنا**: افتراضُ `deploy.sh` (الأردن) وكلُّ هدفٍ في `scripts/deploy-targets/*.conf` (الجزائر —
# ملفُّها فوق ملفّ الإنتاج لا وحدَه)، **ثمّ الأساسُ وحدَه، والأساسُ مع كلِّ ملفٍّ لا يستعمله هدفُ رفع** (ملفّاتُ التطوير)
lists=()
lists+=("$(sed -n 's/^COMPOSE_FILES="\${TAXO_COMPOSE_FILES:-\(.*\)}"$/\1/p' scripts/deploy.sh)")
for conf in scripts/deploy-targets/*.conf; do
  [ -f "$conf" ] && lists+=("$(sed -n 's/^TAXO_COMPOSE_FILES=//p' "$conf" | tr -d '"')")
done
combos=("docker-compose.yml")
used=" "
for list in "${lists[@]}"; do
  combo="$(echo "$list" | tr ' ' '
' | grep -v '^-f$' | grep -v '^$' | paste -sd: -)"
  [ -n "$combo" ] && combos+=("$combo") && used+="$(echo "$combo" | tr ':' ' ') "
done
for extra in docker-compose.*.yml; do
  [ -f "$extra" ] || continue
  case "$used" in *" $extra "*) ;; *) combos+=("docker-compose.yml:$extra") ;; esac
done
# **`--list` يطبع التركيبات ولا يقرؤها** — لمن يريد أن يرى ما يُحرس
[ "${1:-}" = "--list" ] && { printf '%s
' "${combos[@]}"; exit 0; }
for combo in "${combos[@]}"; do
  files=(); found=0
  IFS=: read -ra parts <<< "$combo"
  for f in "${parts[@]}"; do [ -f "$f" ] && { files+=(-f "$f"); found=$((found + 1)); }; done
  # **تركيبةٌ ملفُّها غائبٌ تُتخطّى** (شجرةٌ بلا ملفِّ الفرع) — **والعدُّ بالملفّات لا بالوسائط**: كلُّ ملفٍّ وسيطان (`-f` واسمُه)، وكانت
  # المقارنةُ بالوسائط تتخطّى كلَّ تركيبةٍ فيخضرّ الحارسُ بلا قياس (قِيس بطفرةٍ قبل الإيداع)
  [ "$found" -eq "${#parts[@]}" ] || continue
  checked=$((checked + 1))
  if ! out="$(TAXO_ENV_FILE="$E" COMPOSE_PROJECT_NAME=check-compose docker compose --env-file "$E" "${files[@]}" config --quiet 2>&1)"; then
    echo "✗ check:compose · $combo"; echo "$out" | sed 's/^/    /' | head -5
    bad=$((bad + 1))
  fi
done
[ "$bad" -eq 0 ] || exit 1
[ "$checked" -gt 0 ] || { echo "✗ check:compose — لم تُقرأ تركيبةٌ واحدة: لم يُقَس"; exit 1; }
echo "✓ check:compose · $checked تركيباتٍ يقرؤها compose"
