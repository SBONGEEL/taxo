/** **شاشةُ إقلاع iOS من مصدر أندرويد — لونٌ صامتٌ بلا شعار** (قرارُ المالك ٢٠٢٦-٠٩-٢٩).
 *
 * **ولمَ بلا شعار**: حركةُ رسم TAXO في `index.html` ترسم الشعارَ بعد الإقلاع،
 * **فشعارٌ قبلها يُرسم مرّتين** — وهو ما أُزيل من أندرويد في ٢٠٢٦-٠٨-١٤
 * (`res/drawable/splash_silent.xml`). فالمنصّتان تسلّمان من لونٍ إلى الحركة.
 *
 * **واللونُ يُقرأ من ملفّ أندرويد لا يُنسخ بالعين**:
 * `android/app/src/main/res/values/launch_background.xml` للنهار و`values-night/`
 * لليل — ويُكتبان لونين في `LaunchBackground.colorset` بمظهرَي النظام. **و`check:ios`
 * يقارنهما في كلِّ تشغيل**، فمن غيّر لونَ أندرويد ونسي iOS يسقط هناك.
 *
 *     node tools/ios-assets.mjs            # يكتب اللونَ وشاشةَ الإقلاع للتطبيقين
 */
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
export const IOS_APPS = ["customer-app", "driver-app"];

/** `#rrggbb` من ملفّ موارد أندرويد — **أو وقوفٌ باسم الملفّ**. */
export function androidLaunchColor(app, variant) {
  const file = join(ROOT, app, "android/app/src/main/res", variant, "launch_background.xml");
  const text = readFileSync(file, "utf8");
  // **و«--» داخل تعليق XML يُسقط بناءَ الحزمة** (`mergeResources`، قِيس ٢٠٢٦-١٠-٠٥: كُتب اسمُ رمزٍ مثل `--t2-bg` في تعليق) —
  // وCI لا يبني الحزمة، **فيُمسك هنا** حيث يُقرأ الملفُّ في كلِّ تشغيلٍ لـ`check:ios`
  for (const [, body] of text.matchAll(/<!--([\s\S]*?)-->/g)) {
    if (body.includes("--")) throw new Error(`«--» داخل تعليقٍ في ${file} — XML لا يقبله وgradle يُسقط البناء`);
  }
  const hex = text.match(/<color\s+name="launch_background">\s*#([0-9a-fA-F]{6})\s*<\/color>/)?.[1];
  if (!hex) throw new Error(`لا launch_background بصيغة #rrggbb في ${file}`);
  return `#${hex.toLowerCase()}`;
}

export function colorsetPath(app) {
  return join(ROOT, app, "ios/App/App/Assets.xcassets/LaunchBackground.colorset/Contents.json");
}

/** اللونان من الـcolorset — بالصيغة نفسِها ليُقارَنا. */
export function iosLaunchColors(app) {
  const set = JSON.parse(readFileSync(colorsetPath(app), "utf8"));
  const pick = (dark) => {
    const entry = set.colors.find((c) => Boolean(c.appearances?.length) === dark);
    const { red, green, blue } = entry.color.components;
    return `#${[red, green, blue].map((v) => v.replace(/^0x/i, "").toLowerCase()).join("")}`;
  };
  return { day: pick(false), night: pick(true) };
}

function component(hex, i) {
  return `0x${hex.slice(1 + i * 2, 3 + i * 2).toUpperCase()}`;
}

function colorEntry(hex, dark) {
  return {
    ...(dark ? { appearances: [{ appearance: "luminosity", value: "dark" }] } : {}),
    color: {
      "color-space": "srgb",
      components: {
        alpha: "1.000",
        red: component(hex, 0),
        green: component(hex, 1),
        blue: component(hex, 2),
      },
    },
    idiom: "universal",
  };
}

function srgb(hex, i) {
  return (parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255).toFixed(3);
}

function storyboard(day) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<!-- **لونٌ صامتٌ بلا شعار** — يولّده tools/ios-assets.mjs من مصدر أندرويد، ولا يُحرَّر بيد. -->
<document type="com.apple.InterfaceBuilder3.CocoaTouch.Storyboard.XIB" version="3.0" toolsVersion="17132" targetRuntime="iOS.CocoaTouch" propertyAccessControl="none" useAutolayout="YES" launchScreen="YES" useTraitCollections="YES" useSafeAreas="YES" colorMatched="YES" initialViewController="01J-lp-oVM">
    <device id="retina4_7" orientation="portrait" appearance="light"/>
    <dependencies>
        <deployment identifier="iOS"/>
        <plugIn identifier="com.apple.InterfaceBuilder.IBCocoaTouchPlugin" version="17105"/>
        <capability name="Named colors" minToolsVersion="9.0"/>
        <capability name="documents saved in the Xcode 8 format" minToolsVersion="8.0"/>
    </dependencies>
    <scenes>
        <!--View Controller-->
        <scene sceneID="EHf-IW-A2E">
            <objects>
                <viewController id="01J-lp-oVM" sceneMemberID="viewController">
                    <view key="view" contentMode="scaleToFill" id="snD-IY-ifK">
                        <rect key="frame" x="0.0" y="0.0" width="375" height="667"/>
                        <autoresizingMask key="autoresizingMask" widthSizable="YES" heightSizable="YES"/>
                        <color key="backgroundColor" name="LaunchBackground"/>
                    </view>
                </viewController>
                <placeholder placeholderIdentifier="IBFirstResponder" id="iYj-Kq-Ea1" userLabel="First Responder" sceneMemberID="firstResponder"/>
            </objects>
            <point key="canvasLocation" x="53" y="375"/>
        </scene>
    </scenes>
    <resources>
        <namedColor name="LaunchBackground">
            <color red="${srgb(day, 0)}" green="${srgb(day, 1)}" blue="${srgb(day, 2)}" alpha="1" colorSpace="custom" customColorSpace="sRGB"/>
        </namedColor>
    </resources>
</document>
`;
}

if (process.argv[1]?.endsWith("ios-assets.mjs")) {
  for (const app of IOS_APPS) {
    const day = androidLaunchColor(app, "values");
    const night = androidLaunchColor(app, "values-night");
    mkdirSync(dirname(colorsetPath(app)), { recursive: true });
    writeFileSync(
      colorsetPath(app),
      `${JSON.stringify({ colors: [colorEntry(day, false), colorEntry(night, true)], info: { author: "xcode", version: 1 } }, null, 2)}\n`,
    );
    const base = join(ROOT, app, "ios/App/App");
    writeFileSync(join(base, "Base.lproj/LaunchScreen.storyboard"), storyboard(day));
    // **صورةُ الإقلاع القالبُ تُزال** — لا شيءَ يشير إليها، وبقاؤها يوحي بأنها تُعرض
    const splash = join(base, "Assets.xcassets/Splash.imageset");
    if (existsSync(splash)) rmSync(splash, { recursive: true });
    console.log(`${app}: LaunchBackground  نهار ${day} · ليل ${night}  (من android/res)`);
  }
}
