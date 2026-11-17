#!/usr/bin/env bash
# فيديو إشعار الكبتن الغنيّ (SPEC §١٠٣ A/12) على محاكي CI — حزمةُ تجربة الراكب ومسبارُها RideNoticeProbe (في src/trial وحدَه).
# **ما يُرسم هو `RideNotice` نفسُه**: المسبارُ يمرّر بياناتٍ ثابتةً كالتي يرسلها الخادمُ للمجموعة الخامسة، والصورةُ من رابطٍ عامٍّ لوجهٍ رماديٍّ عامّ.
set -u
APK_DIR="$1"; OUT="$2"; mkdir -p "$OUT"
LOG="$OUT/steps.log"; : > "$LOG"
say() { echo "$*" | tee -a "$LOG"; }
step() { local name="$1"; shift; if "$@" >>"$LOG" 2>&1; then say "✓ $name"; else say "✗ $name"; fi; }

APK="$(ls "$APK_DIR"/*.apk | head -1)"
step "تثبيتُ $APK" adb install -r -g "$APK"
PKG="$(adb shell pm list packages | tr -d '\r' | sed -n 's/^package://p' | grep '^ly\.tajora\.rider' | head -1)"
say "الحزمة: $PKG"
adb shell pm grant "$PKG" android.permission.POST_NOTIFICATIONS >>"$LOG" 2>&1 || true

adb shell input keyevent KEYCODE_WAKEUP; adb shell wm dismiss-keyguard
# القنواتُ تُنشأ عند أوّل فتح (TaxoChannels.ensure) — ومعها شاهدُ المجموعة الخامسة taxo.ride.live
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >>"$LOG" 2>&1
sleep 8; adb shell input keyevent KEYCODE_HOME; sleep 2
adb shell dumpsys notification --noredact > "$OUT/notification-channels.txt" 2>&1
if grep -q "mId='taxo.ride.live'" "$OUT/notification-channels.txt"; then say "✓ قناةُ taxo.ride.live (شاهدُ المجموعة الخامسة)"; else say "✗ قناةُ taxo.ride.live غائبة"; fi

adb shell screenrecord --time-limit 16 --size 720x1600 /sdcard/05-rich-notification.mp4 >/dev/null 2>&1 &
REC=$!
sleep 1
adb shell am broadcast -a ly.tajora.rider.test.SHOW_RIDE_NOTICE -p "$PKG" \
  --es photo_url "https://github.githubassets.com/images/gravatars/gravatar-user-420.png" >>"$LOG" 2>&1
sleep 3
adb shell cmd statusbar expand-notifications; sleep 3
# **لقطةٌ ثابتةٌ مع الفيديو** — قِيس في الجولة الثانية: الإشعارُ رُسم (dumpsys) والتسجيلُ فاته
adb shell screencap -p /sdcard/05-rich-notification.png
adb pull /sdcard/05-rich-notification.png "$OUT/05-rich-notification.png" >>"$LOG" 2>&1 && say "✓ لقطة 05-rich-notification" || say "✗ لقطة 05-rich-notification"
sleep 6
adb shell cmd statusbar collapse
wait "$REC" 2>/dev/null; sleep 1
adb pull /sdcard/05-rich-notification.mp4 "$OUT/05-rich-notification.mp4" >>"$LOG" 2>&1 && say "✓ فيديو 05-rich-notification" || say "✗ فيديو 05-rich-notification"
adb shell dumpsys notification --noredact > "$OUT/notification-after.txt" 2>&1
grep -nE "pkg=$PKG|actions=|android.title=|android.subText=|largeIcon" "$OUT/notification-after.txt" | head -20 >> "$LOG"
adb logcat -d -t 1500 > "$OUT/logcat.txt" 2>&1
grep -nE "FATAL|AndroidRuntime" "$OUT/logcat.txt" | head -20 >> "$LOG" || true
say "انتهى"
