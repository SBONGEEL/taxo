#!/usr/bin/env bash
# إقامةُ بيئة التطوير بعد كلِّ إعادة تشغيل — **ويقرأ بعده لا يعِد قبله**.
#
# **العلّةُ مقيسةٌ في يومٍ واحد** (٢٠٢٦-٠٩-١١/١٢): سقطت الحزمةُ التجريبيةُ على
# الهاتف ثلاثَ مرّاتٍ بثلاثة وجوه، **ولم يكن السببُ ثلاثةً**:
#
#   1. `taxo-tunnel` خرج `(255)` منذ ٤١ ساعة   — عارضٌ يُقام بأمرٍ واحد
#   2. حاويتا الواجهة `Restarting (127)`       — `sh: npm: not found` بعد
#      إقلاع Docker Desktop، والصورةُ سليمةٌ تماماً
#   3. `VITE_API_BASE_URL: http://127.0.0.1:8001` — **دائمٌ ومكتوب**، وهو
#      الهاتفُ نفسُه، فيردّ كروميوم `ERR_NETWORK_UNREACHABLE`
#
# **والثالثُ أُصلح في `docker-compose.yml`**، والأوّلان يُقامان من هنا.
#
# **ولا يُعلَن نجاحٌ بلا قراءة**: `docker compose up -d` يخرج بصفرٍ وحاويةٌ
# تدخل دورةَ سقوطٍ بعده بثوانٍ — **وخروجُه بصفرٍ ليس دليلَ حياة**. فالدليلُ
# **جوابُ النطاقات نفسِها**.
#
#     bash scripts/dev-up.sh
#
# **ولا يمسّ ما يعمل**: `up -d` يُقيم الناقصَ ولا يُعيد القائم.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

ENV_FILE="${TAXO_ENV_FILE:-.env.local}"
[ -f "$ENV_FILE" ] || { printf '✗ لا ملفَّ بيئة «%s».\n' "$ENV_FILE" >&2; exit 2; }

printf '→ إقامةُ ما سقط…\n'
docker compose --env-file "$ENV_FILE" up -d >/dev/null 2>&1

# ── الحاويات: **حالُها بعد ثوانٍ لا لحظةَ الأمر** ─────────────────────────
# **ودورةُ السقوط تحتاج مهلةً لتظهر**: `Restarting` لا تُقرأ في الثانية الأولى.
sleep 12

printf '\n  الحاويات\n'
bad=0
while read -r name status; do
  case "$status" in
    Up*) printf '    ✓ %-22s %s\n' "$name" "$status" ;;
    *)   printf '    ✗ %-22s %s\n' "$name" "$status"; bad=$((bad + 1)) ;;
  esac
done < <(docker compose --env-file "$ENV_FILE" ps --format '{{.Name}} {{.Status}}' 2>/dev/null)

# ── النطاقات: **الدليلُ الحقيقيُّ** ───────────────────────────────────────
# **ويُسأل النفقُ لا المنفذُ المحلّيّ**: منفذٌ يجيب على هذا الحاسوب لا يقول
# شيئاً عمّا يصل الهاتفَ — وهو الفرقُ الذي أخفى العطبَ ثلاث مرّات.
printf '\n  النطاقات — جوابُها لا سجلُّها\n'
for u in https://dev-api.tajora.ly/health \
         https://dev-app.tajora.ly/ \
         https://dev-driver.tajora.ly/ \
         https://dev-admin.tajora.ly/; do
  code="$(curl -sS -m 25 -o /dev/null -w '%{http_code}' "$u" 2>/dev/null)"
  case "$code" in
    200) printf '    ✓ %-34s %s\n' "$u" "$code" ;;
    530) printf '    ✗ %-34s %s — **النفقُ غيرُ متّصل**\n' "$u" "$code"; bad=$((bad + 1)) ;;
    502) printf '    ✗ %-34s %s — النفقُ حيٌّ وما خلفه ساقط\n' "$u" "$code"; bad=$((bad + 1)) ;;
    *)   printf '    ✗ %-34s %s\n' "$u" "${code:-لا جواب}"; bad=$((bad + 1)) ;;
  esac
done

# ── وما يُخدَم للهاتف — **السطرُ الذي أخفى العطبَ ثلاثاً** ────────────────
served="$(docker inspect taxo-customer-app \
  --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
  | sed -n 's/^VITE_API_BASE_URL=//p' | head -1)"
printf '\n  ما يُخدَم للهاتف   %s\n' "${served:-لم يُقرأ}"
case "$served" in
  http://127.0.0.1*|http://localhost*)
    printf '    ✗ **عنوانٌ لا يصل هاتفاً** — هو الهاتفُ نفسُه.\n' >&2
    bad=$((bad + 1))
    ;;
esac

if [ "$bad" -gt 0 ]; then
  printf '\n✗ %d موضعاً ساقطاً — **ولا يُقرأ خروجُ `up -d` حياةً**.\n' "$bad" >&2
  exit 1
fi
printf '\n✓ بيئةُ التطوير حيّةٌ ومقروءةٌ من نطاقاتها.\n'
