#!/usr/bin/env bash
# **فيديوهاتُ إقرارات Google Play لإصدار الكبتن** (أمرُ المالك ٢٠٢٦-١١-١٨ السادس، البند ٤) — سيرُ «فيديوهاتُ Play».
# **بخلاف أفلام «أندرويد»** (الأذوناتُ هناك تُمنح بأمرٍ والواجهةُ بلا خادم): هنا خلفيةٌ حقيقيّةٌ في المشغّل وكبتنُ تجربةٍ داخل،
# **والأذوناتُ تُمنح بالنقر كما يمنحها الإنسان** — فيُرى الإفصاحُ البارزُ قبل نافذة النظام، وهو ما يشترطه Play نصّاً.
#
#   bash scripts/android-emulator-play-demo.sh <الحزمة> <مجلّد الإخراج> <ملف رمز الكبتن>
#
# الفيديوهات: play-1-background-location (الإفصاحُ ⇐ الأذونات ⇐ «ابدأ الاستقبال» ⇐ الإشعارُ المستمرّ ⇐ الفقاعةُ فوق الرئيسيّة
# ⇐ الشاشةُ مطفأة) · play-2-full-screen-intent (طلبٌ والهاتفُ مقفل) · play-3-overlay (الطلبُ فوق تطبيقٍ آخر).
# **كلُّ خطوةٍ سطرٌ في steps.log**، وما سقط «✗» ولا يوقف ما بعده.
set -u
APK="$1"; OUT="$2"; SESSION="$3"
mkdir -p "$OUT"; LOG="$OUT/steps.log"; : > "$LOG"
say() { echo "$*" | tee -a "$LOG"; }
step() { local name="$1"; shift; if "$@" >>"$LOG" 2>&1; then say "✓ $name"; else say "✗ $name"; fi; }

for p in 5174 8001; do adb reverse "tcp:$p" "tcp:$p" >>"$LOG" 2>&1; done
# **بلا `-g`**: الأذوناتُ تُمنح في الفيديو بالنقر لا عند التثبيت
step "تثبيت الكبتن" adb install -r "$APK"
adb shell settings put global hide_error_dialogs 1 >>"$LOG" 2>&1
sleep 45
adb shell am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS >>"$LOG" 2>&1
adb shell input keyevent KEYCODE_WAKEUP; adb shell wm dismiss-keyguard
# عمّان، الدوّارُ السابع — حيث الكبتنُ التجريبيّ
adb emu geo fix 35.8460 31.9560 >>"$LOG" 2>&1

PKG="$(adb shell pm list packages | tr -d '\r' | sed -n 's/^package://p' | grep '^ly.tajora.driver' | head -1)"
say "الحزمة: $PKG"
comp() { adb shell cmd package resolve-activity --brief "$1" | tr -d '\r' | grep -E '^[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+$' | tail -1; }
cdp() {
  local pid sock
  pid="$(adb shell pidof "$PKG" | tr -d '\r')"; sock="webview_devtools_remote_$pid"
  adb forward --remove tcp:9222 >/dev/null 2>&1
  adb forward tcp:9222 "localabstract:$sock" >/dev/null 2>&1 || return 1
  node scripts/cdp-eval.mjs 9222 "$1"
}
cdp_retry() { local i; for i in 1 2 3 4; do cdp "$1" && return 0; sleep 5; done; return 1; }
# **نقرُ زرٍّ في الواجهة بنصِّه** — كما ينقره الكبتن، ويُطبع ما نُقر
click_text() {
  local r
  r="$(cdp_retry "(()=>{const b=[...document.querySelectorAll('button,a,[role=button]')].find(e=>(e.textContent||'').trim().startsWith('$1'));if(!b)return 'none';b.click();return 'ok'})()" 2>>"$LOG")"
  [ "$r" = ok ] && say "  · نُقر «$1»" || { say "  ✗ لا زرَّ «$1»"; return 1; }
}
# **نقرُ عنصرٍ في واجهة النظام** (نافذةُ الإذن، صفحةُ الإعدادات) — من شجرة uiautomator بالنصِّ أو المعرّف
ui_tap() {
  local xy i
  for i in 1 2 3; do
    adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb pull /sdcard/ui.xml /tmp/ui.xml >/dev/null 2>&1
    xy="$(python3 - "$1" <<'PY'
import re, sys, xml.etree.ElementTree as ET
pat = re.compile(sys.argv[1])
try:
    nodes = list(ET.parse("/tmp/ui.xml").iter("node"))
except Exception:
    nodes = []
for n in nodes:
    if any(pat.search(n.get(k, "")) for k in ("text", "content-desc", "resource-id")):
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
        print((x1 + x2) // 2, (y1 + y2) // 2)
        break
PY
)"
    if [ -n "$xy" ]; then adb shell input tap $xy; say "  · نظام: «$1» ($xy)"; return 0; fi
    sleep 2
  done
  say "  ✗ نظام: لا «$1»"; return 1
}
REC=""
rec_start() { REC="$1"; adb shell screenrecord --time-limit 180 --size 720x1600 "/sdcard/$1.mp4" >/dev/null 2>&1 & sleep 1; say "● تسجيل $1"; }
rec_stop() {
  adb shell pkill -INT screenrecord >/dev/null 2>&1; sleep 3
  adb pull "/sdcard/$REC.mp4" "$OUT/$REC.mp4" >>"$LOG" 2>&1 && say "✓ فيديو $REC ($(stat -c%s "$OUT/$REC.mp4") بايت)" || say "✗ فيديو $REC"
}
shot() { adb exec-out screencap -p > "$OUT/$1.png"; }
probe() { adb shell am broadcast -a ly.tajora.driver.test.SHOW_OFFER -p "$PKG" "$@" >>"$LOG" 2>&1; }

# ── الدخول: رمزا الحساب في مخزن الصفحة ثمّ إعادةُ التحميل — بلا كلمة مرورٍ في أيِّ حقل
adb shell am start -W -n "$(comp "$PKG")" >>"$LOG" 2>&1; sleep 30; adb shell am force-stop "$PKG"
adb shell am start -W -n "$(comp "$PKG")" >>"$LOG" 2>&1; sleep 15
step "الدخول" cdp_retry "localStorage.setItem('taxo.driver.access_token','$(sed -n 1p "$SESSION")');localStorage.setItem('taxo.driver.refresh_token','$(sed -n 2p "$SESSION")');location.reload();'ok'"
sleep 25

# ── ١) الموقعُ في الخلفيّة والخدمةُ الأماميّة: من الإفصاح إلى الاستعمال
rec_start play-1-background-location
sleep 3; shot walk-1-location
click_text "اسمح بالموقع"; sleep 3
ui_tap "permission_allow_foreground_only_button|While using the app"; sleep 3
shot walk-2-notifications
click_text "اسمح بالإشعارات"; sleep 3
ui_tap "permission_allow_button|^Allow$"; sleep 3
click_text "ليس الآن"; sleep 3                     # استثناءُ توفير الطاقة — يُترك للكبتن
shot walk-3-overlay
click_text "افتح الإعدادات"; sleep 4               # الرسمُ فوق التطبيقات ⇐ صفحةُ النظام
ui_tap "Allow display over other apps|switch_widget"; sleep 2
adb shell input keyevent KEYCODE_BACK; sleep 4
shot walk-4-background
click_text "افتح الإعدادات واختر"; sleep 4         # الإفصاحُ البارزُ للموقع في الخلفيّة ⇐ صفحةُ النظام
if ! ui_tap "allow_always_radio_button|Allow all the time"; then
  ui_tap "^Permissions$" && sleep 2 && ui_tap "^Location$" && sleep 2 && ui_tap "allow_always_radio_button|Allow all the time"
fi
sleep 2; adb shell input keyevent KEYCODE_BACK; sleep 2
adb shell am start -W -n "$(comp "$PKG")" >>"$LOG" 2>&1; sleep 6
for b in "تخط" "لاحق" "ليس الآن" "إغلاق"; do click_text "$b" >/dev/null 2>&1 && sleep 2; done
adb shell input tap 540 300; sleep 2                # ورقةُ الترحيب تُغلق بلمسةٍ خارجها
shot home-before-online
click_text "ابدأ الاستقبال"; sleep 6
shot home-online
adb shell cmd statusbar expand-notifications; sleep 5
shot shade-online
adb shell cmd statusbar collapse; sleep 2
adb shell input keyevent KEYCODE_HOME; sleep 6       # الفقاعةُ فوق الرئيسيّة
shot bubble-home
adb shell input keyevent KEYCODE_SLEEP; sleep 6; adb shell input keyevent KEYCODE_WAKEUP; sleep 3
adb shell wm dismiss-keyguard; sleep 3
rec_stop
adb shell dumpsys activity services "$PKG" > "$OUT/foreground-service.txt" 2>&1
adb shell dumpsys appops --package "$PKG" > "$OUT/appops.txt" 2>&1
adb shell dumpsys package "$PKG" | grep -E "ACCESS_BACKGROUND_LOCATION|ACCESS_FINE_LOCATION|POST_NOTIFICATIONS" > "$OUT/permissions.txt" 2>&1

# ── ٢) النيّةُ بملء الشاشة: طلبٌ والهاتفُ مقفل
adb shell input keyevent KEYCODE_SLEEP; sleep 2
rec_start play-2-full-screen-intent
probe --es force locked --ei timeout 12; sleep 12
rec_stop
adb shell input keyevent KEYCODE_WAKEUP; adb shell wm dismiss-keyguard; probe --es mode hide; sleep 2

# ── ٣) العرضُ فوق التطبيقات: الطلبُ يظهر فوق تطبيقٍ آخر (الإعدادات)
adb shell am start -a android.settings.SETTINGS >>"$LOG" 2>&1; sleep 4
rec_start play-3-overlay
sleep 2; probe --es force bubble --ei timeout 10; sleep 12
rec_stop
probe --es mode hide

adb logcat -d -s chromium:I Capacitor/Console:I > "$OUT/console.txt" 2>&1 || true
adb logcat -d -b crash > "$OUT/crash.txt" 2>&1 || true
say "انتهى"
