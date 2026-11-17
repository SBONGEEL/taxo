#!/usr/bin/env bash
# **لقطاتُ أندرويد** — `bash tools/screens/android-run.sh <app> <apk> <dist-screens> <outDir>` داخل محاكي `android-emulator-runner`.
#
# **غلافُ أندرويد نفسُه** (`assembleTrialDebug`) يحمّل واجهتَه من عنوانٍ كما يفعل في الحقيقة — وعنوانُه هنا خادمُ اللقطات
# على 127.0.0.1 (`adb reverse`) يخدم **حزمةَ اللقطات نفسَها** التي في iPhone. فالمقارنةُ تطبيقٌ بتطبيق، بالشاشات نفسِها حرفاً.
set -euo pipefail
app="$1"; apk="$2"; dist="$3"; out="$4"
root="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$out"
pkg="$(case "$app" in customer-app) echo ly.tajora.rider.test.dev;; driver-app) echo ly.tajora.driver.test.dev;; esac)"

node "$root/tools/screens/server.mjs" "$dist" > "$out/server.log" 2>&1 &
server=$!
trap 'kill $server 2>/dev/null || true' EXIT
sleep 1
adb reverse tcp:8787 tcp:8787
adb install -r -g "$apk"
adb emu geo fix 35.9106 31.9539 || true
adb shell settings put system time_12_24 24 || true
adb logcat -c || true
adb shell monkey -p "$pkg" -c android.intent.category.LAUNCHER 1 >/dev/null
sleep 15
APPEARANCE_CMD="bash $root/tools/screens/android-night.sh" \
  node "$root/tools/screens/steps.mjs" "$app" "$out" -- 'adb exec-out screencap -p > "$SHOT"'
# **سجلُّ الأعطال بجانب اللقطات** — تطبيقٌ أُغلق في منتصف الخطوات يُقرأ سببُه لا يُخمَّن (مقيسٌ: أُغلق بعد الدخول في التشغيل الثاني)
adb logcat -d -b crash > "$out/crash.log" 2>/dev/null || true
adb logcat -d -v time > "$out/logcat.log" 2>/dev/null || true
adb shell dumpsys activity activities | grep -E "mResumedActivity|topResumedActivity" > "$out/activity.txt" 2>/dev/null || true
