#!/usr/bin/env bash
# فيديوهاتُ المرحلة A على محاكي CI (سيرُ «أندرويد»، وظيفةُ emulator) — حزمةُ تجربة الكبتن وملحقُها OfferProbe.
# يُشغَّل داخل android-emulator-runner: adb متّصلٌ بمحاكٍ واحد. **كلُّ خطوةٍ تكتب سطراً في films/steps.log**،
# **وما سقط يُكتب «✗» ولا يوقف ما بعده** — فالفيديوهاتُ الباقيةُ تُصوَّر ويُقرأ السجلُّ كاملاً.
set -u
APK_DIR="$1"; OUT="$2"; mkdir -p "$OUT"
LOG="$OUT/steps.log"; : > "$LOG"
say() { echo "$*" | tee -a "$LOG"; }
step() { local name="$1"; shift; if "$@" >>"$LOG" 2>&1; then say "✓ $name"; else say "✗ $name"; fi; }

APK="$(ls "$APK_DIR"/*.apk | head -1)"
step "تثبيتُ $APK" adb install -r -g "$APK"
PKG="$(adb shell pm list packages | tr -d '\r' | sed -n 's/^package://p' | grep '^ly\.tajora\.driver' | head -1)"
say "الحزمة: $PKG"
adb root >/dev/null 2>&1; sleep 3

# الأذوناتُ كما يمنحها الكبتنُ من مركز الأذونات
for p in android.permission.POST_NOTIFICATIONS android.permission.ACCESS_FINE_LOCATION android.permission.ACCESS_COARSE_LOCATION android.permission.ACCESS_BACKGROUND_LOCATION; do
  adb shell pm grant "$PKG" "$p" >>"$LOG" 2>&1 || true
done
step "الظهورُ فوق التطبيقات" adb shell appops set "$PKG" SYSTEM_ALERT_WINDOW allow
step "تنبيهاتُ ملء الشاشة" adb shell appops set "$PKG" USE_FULL_SCREEN_INTENT allow

# المفاتيحُ كما يكتبها الويبُ بـLauncher.setPrefs — هنا بيدٍ لأن الواجهةَ لا خادمَ لها في CI
PREFS='<?xml version="1.0" encoding="utf-8" standalone="yes" ?><map><boolean name="online" value="true" /><boolean name="status_bubble" value="true" /><boolean name="native_location" value="true" /><boolean name="tile" value="true" /></map>'
adb shell "mkdir -p /data/data/$PKG/shared_prefs && echo '$PREFS' > /data/data/$PKG/shared_prefs/taxo_launcher.xml && chmod 660 /data/data/$PKG/shared_prefs/taxo_launcher.xml" >>"$LOG" 2>&1
OWNER="$(adb shell stat -c %U /data/data/$PKG | tr -d '\r')"
adb shell chown "$OWNER:$OWNER" "/data/data/$PKG/shared_prefs/taxo_launcher.xml" >>"$LOG" 2>&1

rec() { # rec <name> <seconds>  — يبدأ التسجيلَ في الخلفية
  adb shell screenrecord --time-limit "$2" --size 720x1600 "/sdcard/$1.mp4" >/dev/null 2>&1 &
  REC_PID=$!
}
pull() { wait "$REC_PID" 2>/dev/null; sleep 1; adb pull "/sdcard/$1.mp4" "$OUT/$1.mp4" >>"$LOG" 2>&1 && say "✓ فيديو $1" || say "✗ فيديو $1"; }
probe() { adb shell am broadcast -a ly.tajora.driver.test.SHOW_OFFER -p "$PKG" "$@" >>"$LOG" 2>&1; }

adb shell input keyevent KEYCODE_WAKEUP; adb shell wm dismiss-keyguard
# ١) فقاعةُ الحال: التطبيقُ ثمّ «الرئيسيّة» فتظهر، ثمّ طلبٌ فتنبض وتظهر فقاعةُ الطلب
rec 01-status-bubble 22
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >>"$LOG" 2>&1
sleep 6; adb shell input keyevent KEYCODE_HOME; sleep 5
probe --es force bubble --ei timeout 8; sleep 9
pull 01-status-bubble

# ٢) الطلبُ فوق شاشة القفل بملء الشاشة — والصوتُ من قناته (لا يُسجَّل الصوتُ في screenrecord)
adb shell input keyevent KEYCODE_SLEEP; sleep 2
probe --es force locked --ei timeout 10; sleep 1
rec 02-lockscreen-offer 12; sleep 1
adb shell input keyevent KEYCODE_WAKEUP
pull 02-lockscreen-offer
adb shell dumpsys notification --noredact > "$OUT/notification-channels.txt" 2>&1
grep -nE "taxo\.offer\.v2[^ ]*|mSound=|sound=" "$OUT/notification-channels.txt" | head -40 >> "$LOG"
probe --es mode hide

# ٣) الخدمةُ الأماميّةُ والموقعُ والشاشةُ مطفأة — يُقاس من dumpsys لا من الصورة (الشاشةُ سوداء).
# **والتطبيقُ يُغلق قبلها** (قِيس في أوّل تشغيل): الويبُ بلا خادمٍ ولا دخولٍ هنا يقول «غيرُ متّصل» فيوقف الخدمةَ بعد ثوانٍ —
# وهو سلوكُه الصحيح؛ فتُشغَّل الخدمةُ وحدَها في عمليّةٍ بلا نشاط، كما تعيش والكبتنُ في تطبيقٍ آخر
adb shell am force-stop "$PKG"
adb shell wm dismiss-keyguard
step "بدءُ الخدمة الأماميّة" adb shell am start-foreground-service -n "$PKG/ly.tajora.driver.OnlineService" --el interval_ms 10000
adb shell input keyevent KEYCODE_SLEEP
for i in 1 2 3 4 5 6; do adb emu geo fix 35.9$i 31.9$i >/dev/null 2>&1; sleep 5; done
adb shell dumpsys location > "$OUT/location-screen-off.txt" 2>&1
grep -nE "$PKG|interval|Request\[" "$OUT/location-screen-off.txt" | head -30 >> "$LOG"
adb shell dumpsys activity services "$PKG" > "$OUT/foreground-service.txt" 2>&1
grep -nE "OnlineService|isForeground" "$OUT/foreground-service.txt" | head -6 >> "$LOG"
adb shell input keyevent KEYCODE_WAKEUP; adb shell input keyevent KEYCODE_MENU
rec 03-online-notification 10
adb shell cmd statusbar expand-notifications; sleep 6; adb shell cmd statusbar collapse
pull 03-online-notification

# ٤) بلاطةُ «متصل» في الإعدادات السريعة
step "إضافةُ البلاطة" adb shell cmd statusbar add-tile "$PKG/ly.tajora.driver.OnlineTileService"
rec 04-quick-tile 14
# البلاطةُ أُضيفت أوّلاً (QSTileHost)، **والصفحةُ الأولى تُعرض بالسحب** — ثمّ نقرةٌ عليها تفتح التطبيقَ بفعل «اتصل»
adb shell cmd statusbar expand-settings; sleep 3
adb shell input swipe 200 400 900 400 300; sleep 3
adb shell cmd statusbar click-tile "$PKG/ly.tajora.driver.OnlineTileService" >>"$LOG" 2>&1; sleep 5
adb shell cmd statusbar collapse
pull 04-quick-tile

# ٥) حرارةُ الطلب في الفقاعة (SPEC §١٠٣ C/29) — `bubble_demand` كما يكتبه الويبُ من جواب الطلب؛ تُكتب والتطبيقُ مغلق
#    (التفضيلاتُ تُقرأ عند الإقلاع)، ثمّ «الرئيسيّة» فتظهر الفقاعةُ ممتلئةً بالجمر
adb shell am force-stop "$PKG"
HOT="${PREFS/<\/map>/<boolean name=\"bubble_demand\" value=\"true\" /><\/map>}"
adb shell "echo '$HOT' > /data/data/$PKG/shared_prefs/taxo_launcher.xml" >>"$LOG" 2>&1
adb shell chown "$OWNER:$OWNER" "/data/data/$PKG/shared_prefs/taxo_launcher.xml" >>"$LOG" 2>&1
rec 05-bubble-heat 16
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >>"$LOG" 2>&1
sleep 6; adb shell input keyevent KEYCODE_HOME; sleep 7
pull 05-bubble-heat
adb shell uiautomator dump /sdcard/heat.xml >>"$LOG" 2>&1 && adb shell cat /sdcard/heat.xml | grep -o 'منطقة طلب عالٍ[^"]*' | head -1 | sed 's/^/وصفُ الفقاعة: /' >> "$LOG"

# ٦) تعطّلُ أندرويد الأصليّ (SPEC §١٠٣ C/41) — `am crash` يُسقط العمليّةَ بتعطّلٍ حقيقيّ، ثمّ يُقرأ ما حفظه الماسك:
#    **الاسمُ والإطاراتُ، ولا نصَّ رسالة** — والإقلاعُ التالي يأخذه الويبُ إن اشتعل المفتاح
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >>"$LOG" 2>&1; sleep 5
adb shell am crash "$PKG" >>"$LOG" 2>&1; sleep 3
adb shell cat "/data/data/$PKG/shared_prefs/taxo_native_crash.xml" > "$OUT/native-crash.xml" 2>&1
if grep -q 'name="name"' "$OUT/native-crash.xml"; then say "✓ حُفظ التعطّلُ الأصليّ: $(grep -o 'name="name">[^<]*' "$OUT/native-crash.xml" | head -1)"; else say "✗ لم يُحفظ التعطّلُ الأصليّ"; fi

# ٧) «TAXO بيب بيب» في كلِّ حال (SPEC §١١٥، أمرُ المالك ٢٦/١١) — **يُقاس من سجلّ `TaxoOfferTone` ومن dumpsys لا من الصورة**
#    (المحاكي بلا صوت). الطلبُ بمسبار `push` كما يصل من FCM بياناتٍ وحدَها، **من خيطٍ عامل**؛ وكلُّ حالٍ سطرُ ✓ أو ✗.
adb shell am force-stop "$PKG"
adb shell "echo '$PREFS' > /data/data/$PKG/shared_prefs/taxo_launcher.xml" >>"$LOG" 2>&1
adb shell chown "$OWNER:$OWNER" "/data/data/$PKG/shared_prefs/taxo_launcher.xml" >>"$LOG" 2>&1
adb shell input keyevent KEYCODE_WAKEUP; adb shell wm dismiss-keyguard
tonelog() { adb logcat -d -s TaxoOfferTone:I 2>/dev/null | tr -d '\r'; }
playing() { adb logcat -c; probe --es mode playing; sleep 1; tonelog | grep -q "probe playing=true"; }
expect() { # expect <الحال> <نمطُ السجلّ>
  if tonelog | grep -qE "$2"; then say "✓ بيب: $1 — $(tonelog | grep -E "$2" | tail -1 | sed 's/.*TaxoOfferTone: //')"; else say "✗ بيب: $1 (لا «$2» في السجلّ)"; tonelog | tail -5 >> "$LOG"; fi
}
ring() { adb logcat -c; probe --es mode push --es ride_id "$1" --ei timeout "${2:-12}"; sleep 3; }

# أ) الواجهة
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >>"$LOG" 2>&1; sleep 7
ring beep-front 12; expect "الواجهة" "start usage=alarm"
# ب) الرفضُ أو القبولُ يوقفها فوراً (`hide` — ما تناديه الأزرارُ الثلاثة)
adb logcat -c; probe --es mode hide; sleep 1; expect "الرفضُ يوقفها" "stop playing=true"
playing && say "✗ بيب: ما زالت تعزف بعد الرفض" || say "✓ بيب: صامتةٌ بعد الرفض"
# ج) الخلفية — وتتكرّر بعد طول الملفّ (6.4 ث)، وتسكت عند الانقضاء
adb shell input keyevent KEYCODE_HOME; sleep 4
ring beep-back 12; expect "الخلفية" "start usage=alarm"
sleep 6; playing && say "✓ بيب: تتكرّر بعد ٩ ثوانٍ" || say "✗ بيب: سكتت قبل الانقضاء"
sleep 5; adb logcat -c; sleep 1; playing && say "✗ بيب: تعزف بعد الانقضاء" || say "✓ بيب: سكتت عند الانقضاء"
# د) التطبيقُ مغلق — العمليّةُ ميتة (`am kill` كسحبه من الحديثة، لا «إيقاف إجباريّ» يمنع FCM نفسَه)
adb shell am kill "$PKG"; sleep 2
[ -z "$(adb shell pidof "$PKG" | tr -d '\r')" ] && say "✓ العمليّةُ ميتة قبل الطلب" || say "· العمليّةُ ما زالت حيّة"
ring beep-closed 10; expect "التطبيقُ مغلق" "start usage=alarm"
adb logcat -c; probe --es mode hide; sleep 1
# هـ) الشاشةُ مقفلة — ملءُ الشاشة بصوت قناة `taxo.offer.v3` مكرَّراً (FLAG_INSISTENT)
adb shell input keyevent KEYCODE_SLEEP; sleep 2
ring beep-locked 10
adb shell dumpsys notification --noredact > "$OUT/beep-locked-notification.txt" 2>&1
if grep -q "channel=taxo.offer.v3\b\|taxo.offer.v3 " "$OUT/beep-locked-notification.txt"; then say "✓ بيب: الشاشةُ مقفلة — إشعارُ ملء الشاشة على taxo.offer.v3"; else say "✗ بيب: الشاشةُ مقفلة — لا إشعارَ على taxo.offer.v3"; fi
grep -m3 -E "fullscreenIntent|flags=0x|mSound|sound=" "$OUT/beep-locked-notification.txt" >> "$LOG" || true
adb shell dumpsys audio > "$OUT/beep-locked-audio.txt" 2>&1
grep -iE "usage=USAGE_ALARM" "$OUT/beep-locked-audio.txt" | head -3 >> "$LOG" || true
adb logcat -c; probe --es mode hide; sleep 1
adb shell input keyevent KEYCODE_WAKEUP; adb shell wm dismiss-keyguard; sleep 2
# و) الوضعُ الصامت — «حتى في الصامت» مشتعلٌ افتراضاً ⇐ مجرى المنبّه يرنّ
# **من داخل التطبيق** (`ringer`): `cmd audio set-ringer-mode` لا يغيّر الوضعَ على المحاكي — قِيس 2026-11-26، والمنبّهُ يرنّ في كلِّ وضعٍ فستر ذلك
adb logcat -c; probe --es mode ringer --es to vibrate; sleep 1
tonelog | grep -q "probe ringer=1" && say "✓ الهاتفُ على الاهتزاز" || say "✗ لم يصر الهاتفُ على الاهتزاز ($(tonelog | grep 'probe ringer' | tail -1 | sed 's/.*TaxoOfferTone: //'))"
adb shell input keyevent KEYCODE_HOME; sleep 2
ring beep-silent 10; expect "الوضعُ الصامت" "start usage=alarm"
adb logcat -c; probe --es mode hide; sleep 1
# ز) وأطفأه الكبتن ⇐ يهتزّ ولا يصيح في الصامت
probe --es mode silent_ring --ez on false; sleep 1
ring beep-silent-off 10; expect "الصامتُ والإعدادُ مطفأ" "start vibrate-only"
adb logcat -c; probe --es mode hide; sleep 1
probe --es mode silent_ring --ez on true
probe --es mode ringer --es to normal; sleep 1
# ح) غيرُ متّصل ⇐ لا رنينَ أبداً
# **من داخل العمليّة** (`online`): `force-stop` لكتابة الملفّ يجعل الحزمةَ «موقوفة» فلا يبلغها البثُّ أصلاً — قِيس 2026-11-26
probe --es mode online --ez on false; sleep 1
ring beep-offline 10; expect "غيرُ متّصل لا يرنّ" "push skipped: offline"
tonelog | grep -q "start usage" && say "✗ بيب: رنّ وهو غيرُ متّصل" || true
probe --es mode online --ez on true

adb logcat -d -t 2000 > "$OUT/logcat.txt" 2>&1
grep -nE "FATAL|AndroidRuntime" "$OUT/logcat.txt" | head -20 >> "$LOG" || true
say "انتهى — $(ls "$OUT"/*.mp4 2>/dev/null | wc -l) فيديو"
