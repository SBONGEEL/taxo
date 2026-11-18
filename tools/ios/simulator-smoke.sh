#!/usr/bin/env bash
# **يُقلع التطبيقُ على محاكي iPhone ويُصوَّر** (أمرُ المالك ٢٠٢٦-١١-١٧) — `ios.yml › smoke`.
#
#     bash tools/ios/simulator-smoke.sh <App.app.zip> "<iPhone …>" <مجلّدُ الصور>
#
# **ما يقيسه، بترتيبه — وكلٌّ يُسقط:**
#   ١) يُثبَّت على محاكٍ جديدٍ بالجهاز المسمّى (iOS الأحدث على العدّاء)؛
#   ٢) يُقلع، **وبعد ٢٠ ثانيةً ما زالت عمليّتُه حيّة** — سقوطٌ عند الإقلاع (إذنٌ بلا نصّ، ملحقٌ يُسقط) يقف هنا؛
#   ٣) **الشاشةُ ليست لوناً واحداً**: صورةُ لونٍ واحدٍ تُضغط إلى بضعة كيلوبايتات — وما رُسم فيه نصٌّ وخطوطٌ أثقلُ بكثير.
#      وهو حدٌّ أدنى مكتوب: يقول «رُسم شيء» لا «رُسم الصحيح» — والصورةُ نفسُها أثرٌ يُفتح ويُقرأ.
#   ٤) **ويُقلع ثانيةً بالفرنسيّة** ويُصوَّر — نصوصُ الأذونات واتّجاهُ الواجهة.
#
# **ولا شبكةَ إلى الإنتاج**: الحزمةُ قناةُ `test` (`dev-api`) — ما يظهر بلا خادمٍ هو حالُ «لا اتصال» الحقيقيّة.
set -euo pipefail

zip="$1"; device="$2"; out="$3"
mkdir -p "$out"
work="$(mktemp -d)"
ditto -x -k "$zip" "$work"
app="$work/App.app"
bundle="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$app/Info.plist")"
slug="$(echo "$device" | tr -cd '[:alnum:]')"

runtime="$(xcrun simctl list runtimes -j | python3 -c 'import json,sys; r=[x for x in json.load(sys.stdin)["runtimes"] if x["isAvailable"] and x["platform"]=="iOS"]; print(sorted(r,key=lambda x:[int(p) for p in x["version"].split(".")])[-1]["identifier"])')"
type="$(xcrun simctl list devicetypes -j | DEVICE="$device" python3 -c 'import json,os,sys; d=[x for x in json.load(sys.stdin)["devicetypes"] if x["name"]==os.environ["DEVICE"]]; print(d[0]["identifier"] if d else "")')"
if [ -z "$type" ]; then
  echo "✗ لا جهازَ «$device» على هذا العدّاء — المتاح:"; xcrun simctl list devicetypes | grep iPhone; exit 1
fi
udid="$(xcrun simctl create "taxo-$slug" "$type" "$runtime")"
echo "── $device · $runtime · $udid · $bundle"
xcrun simctl boot "$udid"
xcrun simctl bootstatus "$udid" -b >/dev/null
# **حالُ الشريط ثابتة** (الوقت والشحن والشبكة) — فالصورُ تُقارَن ولا تحمل ساعةَ العدّاء
xcrun simctl status_bar "$udid" override --time "9:41" --batteryState charged --batteryLevel 100 --cellularBars 4 --wifiBars 3 || true
xcrun simctl install "$udid" "$app"

shoot() {
  local lang="$1" name="$2"
  xcrun simctl terminate "$udid" "$bundle" >/dev/null 2>&1 || true
  xcrun simctl launch "$udid" "$bundle" -AppleLanguages "($lang)" -AppleLocale "$lang" >/dev/null
  sleep 20
  # **القائمةُ تُقرأ كاملةً ثمّ يُبحث فيها** — `launchctl list | grep -q` مع `pipefail` يسقط حين يخرج grep عند أوّل تطابقٍ فيُكسر
  # الأنبوبُ على launchctl (الإشارة ١٣): «لم يبقَ حيّاً» والتطبيقُ حيّ (مقيسٌ في التشغيل 43997796635).
  local alive; alive="$(xcrun simctl spawn "$udid" launchctl list || true)"
  if ! grep -q "UIKitApplication:$bundle" <<<"$alive"; then
    echo "✗ $device · $lang: التطبيقُ لم يبقَ حيّاً بعد ٢٠ ثانية"
    xcrun simctl spawn "$udid" log show --last 2m --predicate "process == \"App\"" --style compact | tail -60 || true
    exit 1
  fi
  # **يُعاد التصويرُ حتى ٤٥ ث قبل الحكم** — أوّلُ إقلاعٍ باردٍ لمحاكٍ جديدٍ رسم شاشةً بيضاء بعد ٢٠ ث (التشغيل 44049095452، SE، 29056 بايت)
  # ثمّ رسم في إعادة الوظيفة نفسِها بلا تغيير. **والحدُّ لم يُخفَّف**: ما لم يُرسم في ٤٥ ث يُسقط كما كان.
  local size=0 tries=0
  while :; do
    xcrun simctl io "$udid" screenshot "$out/$name.png" >/dev/null
    size=$(stat -f%z "$out/$name.png")
    [ "$size" -ge 40000 ] || [ "$tries" -ge 5 ] && break
    tries=$((tries + 1)); sleep 5
  done
  echo "   $lang: $(sips -g pixelWidth -g pixelHeight "$out/$name.png" | awk '/pixel/{printf "%s ", $2}')· ${size} بايت"
  if [ "$size" -lt 40000 ]; then
    echo "✗ $device · $lang: الشاشةُ لونٌ واحدٌ تقريباً (${size} بايت) — لم يُرسم شيء"; exit 1
  fi
}

shoot ar "$slug-ar"
shoot fr "$slug-fr"
echo "✓ $device: يُقلع ويرسم بالعربيّة والفرنسيّة"
xcrun simctl shutdown "$udid" || true
xcrun simctl delete "$udid" || true
