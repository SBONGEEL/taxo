#!/usr/bin/env bash
# **لقطاتُ ما يرسمه iOS** — `bash tools/screens/native-run.sh <app> <udid> <bundle> "<iPhone …>" <outDir>`
#
# يُشغَّل بعد `steps.mjs` على المحاكي نفسِه والتطبيقُ مثبَّتٌ وخادمُ اللقطات يعمل (`ios-run.sh`): يولّد مشروعَ الاختبار (`native/project.yml`)
# ويشغّل `NativeShots` — Dynamic Island، وشاشةُ القفل، واختصاراتُ الأيقونة، وأداتا الشاشة الرئيسيّة، والمكالمة.
# **ولا يُسقط وظيفتَه**: ما لم يُبلغ يُكتب في `native.json` بعلّته، وسجلُّ xcodebuild بجانبه.
set -uo pipefail
app="$1"; udid="$2"; bundle="$3"; device="$4"; out="$5"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
kind=rider; [ "$app" = "driver-app" ] && kind=driver
island=1; case "$device" in *SE*) island=0 ;; esac

command -v xcodegen >/dev/null || HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install xcodegen >/dev/null 2>&1
command -v xcodegen >/dev/null || { echo "✗ لا xcodegen"; echo '[]' > "$out/native.json"; exit 0; }
work="$(mktemp -d)"
cp -R "$here/native/." "$work/"
(cd "$work" && xcodegen generate --quiet) || { echo "✗ لم يُولَّد المشروع"; exit 0; }

xcrun simctl ui "$udid" appearance light || true
start=$(date +%s)
TEST_RUNNER_SHOTS_DIR="$out" TEST_RUNNER_APP_BUNDLE="$bundle" TEST_RUNNER_APP_KIND="$kind" TEST_RUNNER_HAS_ISLAND="$island" \
  xcodebuild test -project "$work/NativeShots.xcodeproj" -scheme NativeShots -destination "id=$udid" \
  -derivedDataPath "$work/dd" -resultBundlePath "$work/NativeShots.xcresult" > "$out/xcodebuild.log" 2>&1
code=$?
echo "· NativeShots: خرج $code بعد $(( $(date +%s) - start )) ث"
grep -E "📸|✗ |· setShortcuts|error:|Test Case|\*\* TEST" "$out/xcodebuild.log" | head -60 || true
# **وإن تعذّرت كتابةُ الملفّات من داخل المحاكي** فالصورُ مرفقاتٌ في النتيجة
if ! ls "$out"/*.png >/dev/null 2>&1; then
  xcrun xcresulttool export attachments --path "$work/NativeShots.xcresult" --output-path "$out/attachments" 2>&1 | tail -3 || true
fi
ls -la "$out"
exit 0
