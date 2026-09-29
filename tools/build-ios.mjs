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
import { join } from "node:path";
import { fromEnv } from "./channels.mjs";

const app = process.argv[2];
const syncOnly = process.argv.includes("--sync-only");
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

step("الشاشاتُ بعنوان القناة", "node", ["tools/build-channel.mjs", app]);
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

const derived = join(APP_DIR, "ios", "DerivedData");
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
