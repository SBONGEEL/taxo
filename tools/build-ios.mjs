/** يبني تطبيقاً لـiOS بقناةٍ — **بابٌ واحدٌ كـ`build-channel.mjs`**.
 *
 *     TAXO_CHANNEL=public node tools/build-ios.mjs customer-app
 *     TAXO_CHANNEL=test   node tools/build-ios.mjs driver-app --sync-only
 *
 * **أربعُ خطواتٍ بترتيبها، وكلٌّ يقف عليه ما بعده:**
 *
 * 1. `build-channel.mjs` — `dist` بعنوان القناة وحرّاسِ البناء كلِّهم.
 * 2. `cap sync ios` — **المنصّةُ مسمّاةٌ في الأمر**، فلا `server.url`
 *    (`tools/channels.mjs::isIosCommand`). وعلى macOS تُشغَّل CocoaPods هنا.
 * 3. `check-ios --synced` — لا غلاف · المعرّفُ = القناة · المرفقُ = المبنيّ.
 * 4. `xcodebuild` للمحاكي **بلا توقيع** — والمعرّفُ والاسمُ **يُمرَّران هنا
 *    من الجدول** لا من مشروع Xcode. ثمّ `check-ios --built` من داخل `App.app`.
 *
 * **ولا افتراضَ للقناة**: غيابُ `TAXO_CHANNEL` يوقف قبل الخطوة الأولى، كما
 * يوقف `cap sync android`.
 *
 * **و`--sync-only` لغير macOS**: الخطواتُ الثلاثُ الأولى وحدَها، **ويقال
 * «لم يُجمَّع»** — فلا يُقرأ خروجُه بصفرٍ تجميعاً. وبلا العلَم على غير macOS
 * **يقف** بعد الثالثة، لأن بناءً لم يقع لا يُعلَن.
 */
import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { fromEnv } from "./channels.mjs";

const app = process.argv[2];
const syncOnly = process.argv.includes("--sync-only");
// **`--dist-ready`**: الشاشاتُ بُنيت في وظيفة Linux ونزلت أثراً (`ios.yml`) — فلا يُعاد بناؤها على عدّاء macOS
// الأثمن. **والحارسُ بعد المزامنة يقارن المرفقَ بـ`dist` نفسِه**، فأثرٌ لقناةٍ أخرى يسقط هناك لا يمرّ.
const distReady = process.argv.includes("--dist-ready");
const derivedArg = process.argv.find((a) => a.startsWith("--derived="))?.slice("--derived=".length);
if (!["customer-app", "driver-app"].includes(app ?? "")) {
  console.error(
    "الاستعمال: TAXO_CHANNEL=<public|test> node tools/build-ios.mjs <customer-app|driver-app> [--sync-only]",
  );
  process.exit(2);
}

let ch;
try {
  ch = fromEnv(app);
} catch (error) {
  console.error(`✗ ${error.message}`);
  process.exit(1);
}

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const APP_DIR = join(ROOT, app);
const env = { ...process.env, TAXO_CHANNEL: ch.channel };

function step(title, command, args, cwd = ROOT) {
  console.log(`\n── ${title}`);
  const result = spawnSync(command, args, { cwd, stdio: "inherit", env });
  if (result.status !== 0) {
    console.error(`✗ ${title} — خرج ${result.status ?? result.signal}`);
    process.exit(result.status || 1);
  }
}

if (distReady) console.log("\n── الشاشاتُ مبنيّةٌ سلفاً (--dist-ready) — يقيسها الحارسُ بعد المزامنة");
else step("الشاشاتُ بعنوان القناة", "node", ["tools/build-channel.mjs", app]);
step("المزامنة — iOS مسمّاةً", "npx", ["cap", "sync", "ios"], APP_DIR);
step("لا غلافَ في المزامَن", "node", ["tools/check-ios.mjs", "--synced", app]);

if (process.platform !== "darwin") {
  if (syncOnly) {
    console.log(`\n⚠ لم يُجمَّع — ${ch.appId}: المزامنةُ وحدَها (لا xcodebuild خارج macOS).`);
    process.exit(0);
  }
  console.error("\n✗ لم يُجمَّع — xcodebuild على macOS وحدَه. (`--sync-only` للمزامنة وحدَها.)");
  process.exit(3);
}

// **المشروعُ يُكمَل قبل التجميع** — نصوصُ الأذونات بالفرنسيّة وامتدادُ الأدوات (`tools/ios/configure-xcode.rb`)
step("إكمالُ مشروع Xcode", "ruby", ["tools/ios/configure-xcode.rb", app]);

const derived = derivedArg ?? join(APP_DIR, "ios", "DerivedData");

// **`--release`: أرشيفٌ موقَّعٌ يُرفع إلى TestFlight** (يومَ حساب Apple — `ios-release.yml`). **التوقيعُ يديره Xcode بمفتاح
// App Store Connect API** (`-allowProvisioningUpdates`): لا شهادةَ ولا ملفَّ تزويدٍ يُحفظ في المستودع أو يُنقل بيد —
// المفتاحُ في أسرار GitHub المشفّرة وحدَها، يُكتب إلى ملفٍّ مؤقّتٍ في الوظيفة ويُمحى معها.
if (process.argv.includes("--release")) {
  const need = ["ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_KEY_PATH", "APPLE_TEAM_ID", "TAXO_BUILD_NUMBER"];
  const missing = need.filter((k) => !process.env[k]);
  if (missing.length) {
    console.error(`
✗ لا رفعَ — ينقص: ${missing.join(" · ")} (تُنشأ يومَ حساب Apple: design/IOS-APP-STORE.md §١)`);
    process.exit(4);
  }
  const auth = [
    "-allowProvisioningUpdates",
    "-authenticationKeyPath", process.env.ASC_KEY_PATH,
    "-authenticationKeyID", process.env.ASC_KEY_ID,
    "-authenticationKeyIssuerID", process.env.ASC_ISSUER_ID,
  ];
  const archive = join(APP_DIR, "ios", "build", "App.xcarchive");
  step("الأرشيفُ الموقَّع", "xcodebuild", [
    "-workspace", "ios/App/App.xcworkspace", "-scheme", "App", "-configuration", "Release",
    "-destination", "generic/platform=iOS", "-archivePath", archive, "-quiet", ...auth,
    `DEVELOPMENT_TEAM=${process.env.APPLE_TEAM_ID}`, "CODE_SIGN_STYLE=Automatic",
    `TAXO_APP_ID=${ch.appId}`, `TAXO_APP_NAME=${ch.appName}`,
    `CURRENT_PROJECT_VERSION=${process.env.TAXO_BUILD_NUMBER}`,
    "archive",
  ], APP_DIR);
  const options = join(APP_DIR, "ios", "build", "ExportOptions.plist");
  writeFileSync(options, `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>method</key><string>app-store-connect</string>
<key>destination</key><string>upload</string>
<key>teamID</key><string>${process.env.APPLE_TEAM_ID}</string>
<key>signingStyle</key><string>automatic</string>
<key>manageAppVersionAndBuildNumber</key><false/>
</dict></plist>
`);
  step("الرفعُ إلى TestFlight", "xcodebuild", [
    "-exportArchive", "-archivePath", archive, "-exportOptionsPlist", options,
    "-exportPath", join(APP_DIR, "ios", "build", "export"), ...auth,
  ], APP_DIR);
  console.log(`
✓ ${ch.channel} · ${app} · ${ch.appId} — رُفع البناءُ ${process.env.TAXO_BUILD_NUMBER} إلى TestFlight.`);
  process.exit(0);
}

step("التجميعُ للمحاكي بلا توقيع", "xcodebuild", [
  "-workspace", "ios/App/App.xcworkspace",
  "-scheme", "App",
  "-configuration", "Debug",
  "-sdk", "iphonesimulator",
  "-destination", "generic/platform=iOS Simulator",
  "-derivedDataPath", derived,
  // **التحذيراتُ والأخطاءُ وحدَها** — عشراتُ آلاف السطور تدفن السطرَ الذي يُقرأ
  "-quiet",
  "CODE_SIGNING_ALLOWED=NO",
  // **من الجدول لا من المشروع** — والمشروعُ يحمل المتغيّرَ لا القيمة
  `TAXO_APP_ID=${ch.appId}`,
  `TAXO_APP_NAME=${ch.appName}`,
  "build",
], APP_DIR);

const product = join(derived, "Build", "Products", "Debug-iphonesimulator", "App.app");
step("المبنيُّ مقروءاً من داخله", "node", ["tools/check-ios.mjs", "--built", app, product]);
console.log(`\n✓ ${ch.channel} · ${app} · ${ch.appId} — يُجمَّع على iOS.`);
