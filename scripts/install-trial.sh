#!/usr/bin/env bash
# تثبيتُ حزمةٍ تجريبيةٍ على جهازٍ موصول — **ولا يُعلَن النجاحُ إلا بقراءةٍ بعده**.
#
# **العلّةُ مقيسةٌ لا مُقدَّرة** (٢٠٢٦-٠٩-١١): قيل «بُنيت الحزمة» وقيل «لا
# ناتج» وقيل «ثُبِّتت» — **وثلاثتُها لم تُقرأ من الجهاز**. والحقيقةُ أن
# `app-trial-debug.apk` كان موجوداً منذ ٢٢:١٠ (`versionCode=524`)، **والمثبَّتُ
# على الهاتف `412` منذ ٢٠٢٦-٠٨-٣٠** — واستمرّ الوهمُ جولتين.
#
# **والقاعدةُ التي يطبّقها هذا الملفّ**: `adb install` يخرج بصفرٍ في حالاتٍ لا
# يتغيّر فيها المثبَّت، **وخروجُه بصفرٍ ليس دليلَ تثبيت**. فالدليلُ الوحيدُ
# **قراءةُ `versionCode` من الجهاز بعده ومطابقتُها بما في الحزمة**.
#
#     bash scripts/install-trial.sh <مسار .apk>
#
# **ولا ينزع شيئاً**: إن اختلف التوقيعُ يقف ويسمّي، **والنزعُ قرارُ المالك**.

set -uo pipefail

APK="${1:-}"
[ -n "$APK" ] && [ -f "$APK" ] || {
  printf '✗ الاستعمال: bash scripts/install-trial.sh <مسار .apk>\n' >&2
  exit 2
}

# **ويُختار العميلُ الذي **يرى جهازاً** لا أوّلُ ما في المسار** (قِيس
# 2026-09-11): `adb` داخل WSL موجودٌ ويعمل، **ولا يرى USB البتّة** — فيقول
# «no devices» بينما الجهازُ موصولٌ ويراه عميلُ ويندوز. **فوجودُ الأداة ليس
# صلاحيتَها**، وهو الفرقُ الذي أسقط قياساً كاملاً.
sees_device() {
  "$1" devices 2>/dev/null | tr -d '\r' | grep -qE '^[A-Za-z0-9.:_-]+[[:space:]]+device$'
}
adb_bin() {
  local found=""
  for c in "/mnt/c/Users/$USER/AppData/Local/Android/Sdk/platform-tools/adb.exe" \
           adb "$HOME/Android/Sdk/platform-tools/adb"; do
    if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then
      [ -z "$found" ] && found="$c"
      sees_device "$c" && { printf '%s' "$c"; return 0; }
    fi
  done
  [ -n "$found" ] && { printf '%s' "$found"; return 0; }
  return 1
}
ADB="$(adb_bin)" || { printf '✗ لا `adb` في المسار.\n' >&2; exit 2; }

aapt_bin() { ls "$HOME"/Android/Sdk/build-tools/*/aapt2 2>/dev/null | tail -1; }
AAPT="$(aapt_bin)"

# ── ١) ما في الحزمة — **يُقرأ من داخلها لا من اسمها** ────────────────────
if [ -z "$AAPT" ]; then
  printf '✗ لا `aapt2` — ولا يُثبَّت ما لا يُقرأ اسمُه ورقمُه.\n' >&2
  exit 2
fi
BADGE="$("$AAPT" dump badging "$APK" 2>/dev/null | head -1)"
# **ويُقرآن مثبَّتَين في أوّل السطر لا بمطابقةٍ جشعة** (عطبٌ قِيس في أوّل
# تشغيل): `.*name='` تلتقط **آخرَ** `name=` في السطر —
# `compileSdkVersionCodename='16'` — فقرأ البابُ اسمَ الحزمة «16».
PKG="$(printf '%s' "$BADGE" | sed -n "s/^package: name='\([^']*\)'.*/\1/p")"
WANT="$(printf '%s' "$BADGE" | sed -n "s/^package:[^ ]* name='[^']*' versionCode='\([^']*\)'.*/\1/p")"
[ -n "$PKG" ] && [ -n "$WANT" ] || { printf '✗ تعذّرت قراءةُ الحزمة.\n' >&2; exit 1; }

# **ولا تُثبَّت حزمةٌ عامّةٌ من هذا الباب** — التجريبيُّ وحدَه، بقرارِ المالك.
case "$PKG" in
  *.test) ;;
  *) printf '✗ «%s» ليست حزمةً تجريبية — هذا البابُ للتجريبيِّ وحدَه.\n' "$PKG" >&2; exit 1 ;;
esac

read_installed() {
  "$ADB" shell "dumpsys package $PKG | grep -m1 versionCode" 2>/dev/null \
    | tr -d '\r' | sed -n 's/.*versionCode=\([0-9]*\).*/\1/p'
}

BEFORE="$(read_installed)"
printf '  الحزمة      %s\n' "$PKG"
printf '  في الملفّ    %s\n' "$WANT"
printf '  على الجهاز  %s\n' "${BEFORE:-غيرُ مثبَّتة}"

# ── ٢) التثبيت — **ولا نزعَ مهما كان السبب** ─────────────────────────────
OUT="$("$ADB" install -r "$APK" 2>&1)"
printf '%s\n' "$OUT" | tail -2

case "$OUT" in
  *INSTALL_FAILED_UPDATE_INCOMPATIBLE*)
    printf '\n✗ التوقيعان يختلفان — والمثبَّتُ لم يتغيّر.\n' >&2
    printf '  **ولا يُنزع شيءٌ من هذا الباب**: النزعُ يمحو بيانات التطبيق،\n' >&2
    printf '  وهو قرارُ المالك لا قرارُ سكربت.\n' >&2
    ;;
esac

# ── ٣) الدليلُ قراءةٌ بعده — **لا خروجُ `adb` بصفر** ──────────────────────
AFTER="$(read_installed)"
printf '\n  بعد التثبيت %s\n' "${AFTER:-غيرُ مثبَّتة}"

if [ "$AFTER" = "$WANT" ]; then
  printf '✓ مثبَّتٌ ومقروءٌ من الجهاز: %s = %s\n' "$PKG" "$AFTER"
  exit 0
fi

printf '✗ **لم يتغيّر المثبَّت**: على الجهاز %s والمطلوبُ %s.\n' \
  "${AFTER:-غيرُ مثبَّتة}" "$WANT" >&2
printf '  ولا يُقرأ خروجُ `adb` نجاحاً — الدليلُ هذه القراءةُ وحدَها.\n' >&2
exit 1
