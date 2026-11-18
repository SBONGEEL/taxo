#!/usr/bin/env bash
# **إثباتُ الخريطة المفتوحة داخل غلاف أندرويد** (أمرُ المالك ٢٠٢٦-١١-١٨ الثالث، البند ١) — سيرُ «إثباتُ الخريطة المفتوحة».
# يُشغَّل داخل android-emulator-runner: الغلافان من وسم v2.0.1118 (الشيفرةُ الأصليّةُ التي يحملها الناس)، والواجهتان من الرأس
# تُخدَمان من المشغّل على 5173/5174، والخلفيةُ على 8001 — **كلُّها عبر `adb reverse`**، فلا يخرج المحاكي إلى أيِّ خادمٍ لنا.
# **والحسابان حسابا تجربةٍ في قاعدة CI** (لا حسابَ إنتاجٍ يدخل CI)، ورمزاهما في ملفّين لا يُطبعان.
#
#   bash scripts/android-emulator-open-map.sh <مجلّد الحزم> <مجلّد الإخراج> <ملف رمز الراكب> <ملف رمز الكبتن>
#
# **كلُّ خطوةٍ سطرٌ في steps.log**، وما سقط «✗» ولا يوقف ما بعده. **والحكمُ من الصفحة لا من الصورة**: يُسأل DOM أيُّ محرّكٍ رسم
# (`.maplibregl-map` = المفتوحة، `.mapboxgl-map` = Mapbox) وتُكتب الإجابةُ في engine-<اللقطة>.txt.
set -u
APK_DIR="$1"; OUT="$2"; RIDER_SESSION="$3"; DRIVER_SESSION="$4"
mkdir -p "$OUT"; LOG="$OUT/steps.log"; : > "$LOG"
say() { echo "$*" | tee -a "$LOG"; }
step() { local name="$1"; shift; if "$@" >>"$LOG" 2>&1; then say "✓ $name"; else say "✗ $name"; fi; }

# **تاجوراء قرب الطريق الدائريّ الثاني** — والإحداثيّاتُ (خطُّ الطول ثمّ العرض) كما يطلبها `geo fix`
TAJOURA_LON=13.3420; TAJOURA_LAT=32.8790

for p in 5173 5174 8001; do adb reverse "tcp:$p" "tcp:$p" >>"$LOG" 2>&1; done
for apk in "$APK_DIR"/*.apk; do step "تثبيت $(basename "$apk")" adb install -r -g "$apk"; done
adb shell input keyevent KEYCODE_WAKEUP; adb shell wm dismiss-keyguard
adb emu geo fix "$TAJOURA_LON" "$TAJOURA_LAT" >>"$LOG" 2>&1

pkg_of() { adb shell pm list packages | tr -d '\r' | sed -n 's/^package://p' | grep "^$1" | head -1; }

cdp() { # cdp <pkg> <js> — يقيّم تعبيراً في صفحة الغلاف ويطبع قيمتَه
  local pid sock
  pid="$(adb shell pidof "$1" | tr -d '\r')"
  sock="webview_devtools_remote_$pid"
  adb forward --remove tcp:9222 >/dev/null 2>&1
  adb forward tcp:9222 "localabstract:$sock" >/dev/null 2>&1 || return 1
  node scripts/cdp-eval.mjs 9222 "$2"
}

shot() { # shot <pkg> <name>
  local engine
  engine="$(cdp "$1" "document.querySelector('.maplibregl-map')?'maplibre':(document.querySelector('.mapboxgl-map')?'mapbox':'none')" 2>>"$LOG")"
  echo "$engine" > "$OUT/engine-$2.txt"
  adb exec-out screencap -p > "$OUT/$2.png" && say "✓ لقطة $2 — المحرّك: ${engine:-؟}" || say "✗ لقطة $2"
}

run_app() { # run_app <prefix> <pkg-prefix> <tokens-file> <access-key> <refresh-key>
  local tag="$1" pkg access refresh
  pkg="$(pkg_of "$2")"; say "الحزمة ($tag): $pkg"
  [ -n "$pkg" ] || { say "✗ لا حزمةَ لـ$tag"; return; }
  for perm in android.permission.ACCESS_FINE_LOCATION android.permission.ACCESS_COARSE_LOCATION android.permission.POST_NOTIFICATIONS; do
    adb shell pm grant "$pkg" "$perm" >>"$LOG" 2>&1 || true
  done
  access="$(sed -n 1p "$3")"; refresh="$(sed -n 2p "$3")"
  for mode in no yes; do
    local theme; [ "$mode" = no ] && theme=day || theme=night
    adb shell cmd uimode night "$mode" >>"$LOG" 2>&1
    adb shell am force-stop "$pkg"
    adb shell monkey -p "$pkg" -c android.intent.category.LAUNCHER 1 >>"$LOG" 2>&1
    sleep 12
    # **الدخولُ برمزَي الحساب في مخزن الصفحة ثمّ إعادةُ التحميل** — كما يكتبهما الدخولُ نفسُه، بلا كتابة كلمة مرورٍ في أيِّ حقل
    step "دخولُ $tag ($theme)" cdp "$pkg" "localStorage.setItem('$4','$access');localStorage.setItem('$5','$refresh');location.reload();'ok'"
    sleep 25
    adb emu geo fix "$TAJOURA_LON" "$TAJOURA_LAT" >>"$LOG" 2>&1
    sleep 10
    shot "$pkg" "$tag-$theme-home"
    # **قربُ تاجوراء بتكبيرٍ يُظهر المباني والأماكن** — نقرتان مزدوجتان وسطَ الخريطة
    adb shell input tap 540 1000; sleep 0.2; adb shell input tap 540 1000; sleep 3
    adb shell input tap 540 1000; sleep 0.2; adb shell input tap 540 1000; sleep 8
    shot "$pkg" "$tag-$theme-zoom"
  done
  adb shell cmd uimode night no >>"$LOG" 2>&1
}

run_app rider ly.tajora.rider "$RIDER_SESSION" taxo.access_token taxo.refresh_token
run_app driver ly.tajora.driver "$DRIVER_SESSION" taxo.driver.access_token taxo.driver.refresh_token
adb logcat -d -s chromium:I Capacitor/Console:I > "$OUT/console.txt" 2>&1 || true
say "انتهى"
