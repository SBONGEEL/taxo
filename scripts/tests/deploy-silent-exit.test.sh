#!/usr/bin/env bash
# **لا موتَ صامتاً للمشغّل** — `scripts/deploy-guard.sh` (رفعُ ٢٠٢٦-١١-١٦ مات بعد «الصحّة عبر النفق» بلا سطر).
#
# يُقاس **السلوكُ لا الشكل** في أربع، ولا يُطرق الخادمُ ولا الشبكةُ الخارجيّة:
#  ١) إسنادٌ من أنبوبٍ ساقطٍ تحت `set -euo pipefail` — **الشكلُ الذي قتل الرفع** — يُطبع بسطره وأمره، لا يمرّ صامتاً.
#  ٢) `die` يقول ما سقط **مرّةً واحدة** — لا يتكرّر بصيغة «خرج بلا رسالة».
#  ٣) `edge_get` على عنوانٍ لا يجيب **لا يُسقط المشغّل**، ويعيد فراغاً فيبلغ `die`.
#  ٤) والبوّابةُ ٦ في `deploy.sh` بلا `$(curl` عارٍ — كلُّ جلبٍ من الحافّة يمرّ بـ`edge_get` أو يحمل `|| true`.
#
# **ويُقاس في الاتجاه الآخر**: بلا الحارس (الحالةُ ٠) يموت الشكلُ نفسُه **بلا أيِّ سطر** — وهو ما يجعل ١ اختباراً لا وصفاً.
set -uo pipefail
cd "$(dirname "$0")/../.."

GUARD="$PWD/scripts/deploy-guard.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok()  { printf '  ✓ %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  ✗ %s\n     %s\n' "$1" "${2:0:200}"; fail=$((fail+1)); }

printf '\n  المشغّلُ لا يموت صامتاً\n\n'

# ٠) الاتجاهُ الآخر — بلا الحارس: الشكلُ يقتل بلا سطر
cat > "$TMP/bare.sh" <<'EOF'
set -euo pipefail
echo "قبل"
_len="$(false | wc -c | tr -d ' ')"
echo "بعد — لا يُبلغ"
EOF
out="$(bash "$TMP/bare.sh" 2>&1)"; code=$?
if [ "$code" -ne 0 ] && [ "$out" = "قبل" ]; then ok "بلا الحارس يموت الشكلُ صامتاً (رمز $code) — العطبُ مُعاد إنتاجُه"
else bad "لم يُعَد إنتاجُ الموت الصامت" "code=$code out=$out"; fi

# ١) بالحارس: الموتُ نفسُه يُسمّى بسطره وأمره
cat > "$TMP/guarded.sh" <<EOF
set -euo pipefail
. "$GUARD"
die() { deploy_died; printf '\n✗ %s\n' "\$*" >&2; exit 1; }
echo "قبل"
_len="\$(false | wc -c | tr -d ' ')"
echo "بعد — لا يُبلغ"
EOF
out="$(bash "$TMP/guarded.sh" 2>&1)"; code=$?
if [ "$code" -ne 0 ] && printf '%s' "$out" | grep -q "المشغّلُ خرج بلا رسالة" && printf '%s' "$out" | grep -q "السطر 5"; then
  ok "بالحارس يُطبع الموتُ برمزه وسطره (5)"
else bad "الموتُ لم يُسمَّ" "code=$code out=$out"; fi

# ١-ب) وفي دالّةٍ أيضاً (`set -E`) — فخُّ ERR يرث الدوال
cat > "$TMP/infn.sh" <<EOF
set -euo pipefail
. "$GUARD"
check() { local x; x="\$(grep -o nope /dev/null | head -1)"; echo "\$x"; }
check
EOF
out="$(bash "$TMP/infn.sh" 2>&1)"; code=$?
if [ "$code" -ne 0 ] && printf '%s' "$out" | grep -q "المشغّلُ خرج بلا رسالة"; then ok "وداخلَ دالّةٍ يُسمّى كذلك"
else bad "داخل دالّةٍ مات صامتاً" "code=$code out=$out"; fi

# ٢) die يقول مرّةً واحدة
cat > "$TMP/died.sh" <<EOF
set -euo pipefail
. "$GUARD"
die() { deploy_died; printf '\n✗ %s\n' "\$*" >&2; exit 1; }
die "الحافّةُ لا تجيب"
EOF
out="$(bash "$TMP/died.sh" 2>&1)"; code=$?
if [ "$code" -eq 1 ] && printf '%s' "$out" | grep -q "الحافّةُ لا تجيب" && ! printf '%s' "$out" | grep -q "خرج بلا رسالة"; then
  ok "die يقول ما سقط مرّةً واحدة"
else bad "die تكرّر أو ضاع" "code=$code out=$out"; fi

# ٢-ب) والخروجُ الناجحُ لا يطبع شيئاً
cat > "$TMP/fine.sh" <<EOF
set -euo pipefail
. "$GUARD"
x="\$(echo ok | { grep -o nope || true; })"
echo "تمّ"
EOF
out="$(bash "$TMP/fine.sh" 2>&1)"; code=$?
if [ "$code" -eq 0 ] && [ "$out" = "تمّ" ]; then ok "الخروجُ الناجحُ صامتٌ بحقّ"
else bad "الناجحُ طبع شيئاً" "code=$code out=$out"; fi

# ٣) edge_get على منفذٍ مغلق — لا يُسقط، ويعيد فراغاً فيبلغ die بنصّه
cat > "$TMP/edge.sh" <<EOF
set -euo pipefail
. "$GUARD"
die() { deploy_died; printf '\n✗ %s\n' "\$*" >&2; exit 1; }
EDGE_RETRY_SLEEP=0 EDGE_TIMEOUT=2
_len="\$(edge_get "http://127.0.0.1:9/privacy" | wc -c | tr -d ' ')"
[ "\${_len:-0}" -gt 4000 ] || die "الحافّةُ تردّ \${_len:-0} بايت"
EOF
out="$(EDGE_RETRY_SLEEP=0 bash "$TMP/edge.sh" 2>&1)"; code=$?
if [ "$code" -eq 1 ] && printf '%s' "$out" | grep -q "الحافّةُ تردّ 0 بايت"; then ok "edge_get لا يُسقط المشغّل — die يقول «تردّ 0 بايت»"
else bad "edge_get أسقط المشغّلَ أو ابتلع die" "code=$code out=$out"; fi

# ٤) البوّابةُ ٦: لا `$(curl` عارٍ بلا `|| true`
gate6="$(awk '/══ ٦\) التحقّق/{f=1} f' scripts/deploy.sh)"
naked="$(printf '%s\n' "$gate6" | grep -n '\$(curl' | grep -v '|| true' || true)"
if [ -n "$gate6" ] && [ -z "$naked" ]; then ok "البوّابةُ ٦ بلا \$(curl عارٍ"
else bad "في البوّابة ٦ جلبٌ عارٍ" "${naked:-لم تُوجد البوّابة ٦}"; fi
grep -q 'deploy-guard.sh' scripts/deploy.sh && grep -q '^die() { deploy_died;' scripts/deploy.sh \
  && ok "deploy.sh يستورد الحارس، وdie يعلّم أنه قال" \
  || bad "deploy.sh لا يستورد الحارس أو die لا يعلّم" ""

printf '\n  ✓ %s · ✗ %s\n\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
