#!/usr/bin/env bash
# **لقطاتُ iPhone** — `bash tools/screens/ios-run.sh <app> <App.app.zip> <dist-screens> "<iPhone …>" <outDir>`
#
# يأخذ **المبنيَّ نفسَه** للمحاكي (قناةُ test من وظيفة `build`) ويبدّل شاشاتِه بحزمة اللقطات (`prepare-dist.mjs`) —
# فالشيفرةُ الأصليّةُ (Swift والملحقات والإعداد) هي التي جُمِّعت، والشاشاتُ هي شاشاتُ الشجرة نفسِها بعنوانٍ محلّيّ.
# **ويُفتح للمبنيّ هذا وحدَه** الاتّصالُ بـ127.0.0.1 بلا TLS (ATS) — وهو لا يُشحن ولا يُوقَّع.
set -euo pipefail
app="$1"; zip="$2"; dist="$3"; device="$4"; out="$5"
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../.." && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"
ditto -x -k "$zip" "$work"
bundle_app="$work/App.app"
rm -rf "$bundle_app/public"; cp -R "$dist" "$bundle_app/public"
plist="$bundle_app/Info.plist"
/usr/libexec/PlistBuddy -c "Delete :NSAppTransportSecurity" "$plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :NSAppTransportSecurity dict" -c "Add :NSAppTransportSecurity:NSAllowsArbitraryLoads bool true" \
  -c "Add :NSAppTransportSecurity:NSAllowsLocalNetworking bool true" "$plist"
bundle="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$plist")"

runtime="$(xcrun simctl list runtimes -j | python3 -c 'import json,sys; r=[x for x in json.load(sys.stdin)["runtimes"] if x["isAvailable"] and x["platform"]=="iOS"]; print(sorted(r,key=lambda x:[int(p) for p in x["version"].split(".")])[-1]["identifier"])')"
type="$(xcrun simctl list devicetypes -j | DEVICE="$device" python3 -c 'import json,os,sys; d=[x for x in json.load(sys.stdin)["devicetypes"] if x["name"]==os.environ["DEVICE"]]; print(d[0]["identifier"] if d else "")')"
[ -n "$type" ] || { echo "✗ لا جهازَ «$device»"; xcrun simctl list devicetypes | grep iPhone; exit 1; }
udid="$(xcrun simctl create "shots" "$type" "$runtime")"
xcrun simctl boot "$udid"; xcrun simctl bootstatus "$udid" -b >/dev/null
xcrun simctl status_bar "$udid" override --time "9:41" --batteryState charged --batteryLevel 100 --cellularBars 4 --wifiBars 3 || true
xcrun simctl location "$udid" set 31.9539,35.9106 || true   # عمّان — مدينةُ العرض
xcrun simctl install "$udid" "$bundle_app"
for p in location-always location photos camera microphone; do xcrun simctl privacy "$udid" grant "$p" "$bundle" 2>/dev/null || true; done
# إذنُ الإشعارات يُجاب «مرفوضاً» في الصفحة نفسِها (`harness.js › quietPush`) — `simctl` لا يمنحه، وapplesimutils لم يُثبَّت على العدّاء

node "$root/tools/screens/server.mjs" "" > "$out/server.log" 2>&1 &
server=$!
trap 'kill $server 2>/dev/null || true' EXIT
sleep 1
xcrun simctl launch "$udid" "$bundle" -AppleLanguages "(ar)" -AppleLocale "ar_JO" >/dev/null
sleep 12
LOCATION_CMD="xcrun simctl location $udid set 31.9539,35.9106 || true" \
APPEARANCE_CMD="xcrun simctl ui $udid appearance" \
  node "$root/tools/screens/steps.mjs" "$app" "$out" -- xcrun simctl io "$udid" screenshot '"$SHOT"'
# **قياسُ ملحق العربيّة على الخريطة** (أمرُ المالك ٢٠٢٦-١١-١٨): صفحةُ القياس في WebView التطبيق نفسِه، أسماءٌ طويلةٌ وشوارعُ وعربيّةٌ بأرقام
node -e 'fetch("http://127.0.0.1:8787/__shot",{method:"POST",body:JSON.stringify({kind:"reset",storage:{},path:"/__rtl/index.html"})}).then(r=>r.json()).then(c=>console.log("· rtl:",c.id))' || true
sleep 28
mkdir -p "$out/rtl"; xcrun simctl io "$udid" screenshot "$out/rtl/rtl-$(basename "$out").png" || true
grep '^NOTE' "$out/server.log" | tail -2 > "$out/rtl/rtl-notes.txt" || true
cat "$out/rtl/rtl-notes.txt" || true
sleep 15   # الصفحةُ تعود إلى التطبيق بعد ٤٠ ث
# **ثمّ ما يرسمه iOS نفسُه** (أمرُ المالك ٢٠٢٦-١١-١٨): Dynamic Island والقفلُ والاختصاراتُ والأدواتُ والمكالمة — بالتطبيق والخادم نفسَيهما
bash "$root/tools/screens/native-run.sh" "$app" "$udid" "$bundle" "$device" "$out/native" || true
# **أثرُ خروج التطبيق يُحفظ** — مقيسٌ: الكبتنُ صار في الخلفيّة بعد ورقة الموقع بلا سطرٍ يقول لماذا (التشغيل 44026434831)
xcrun simctl spawn "$udid" log show --last 30m --style compact   --predicate 'process == "App" OR (process == "SpringBoard" AND eventMessage CONTAINS[c] "'"$bundle"'") OR eventMessage CONTAINS[c] "terminat"'   > "$out/ios-app.log" 2>&1 || true
crashes="$HOME/Library/Logs/DiagnosticReports"
find "$crashes" -name "App*.ips" -newer "$out/server.log" -exec cp {} "$out/" \; 2>/dev/null || true
ls "$out"/*.ips >/dev/null 2>&1 && echo "✗ تقريرُ انهيارٍ لـApp في $out" || echo "— لا تقريرَ انهيارٍ لـApp"
xcrun simctl shutdown "$udid" || true
