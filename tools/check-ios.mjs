/** **حارسُ iOS** — الشاشاتُ داخل الحزمة، والمعرّفُ من الجدول لا من Xcode.
 *
 * ## القرارُ الذي يحرسه (قرارُ المالك 2026-09-29)
 *
 * **على iOS تُجمَّع شاشاتُ الراكب والكبتن داخل الحزمة** — `dist` مرفقٌ
 * يخاطب `apiBase` مباشرةً، **لا غلافٌ يفتح عنواناً بعيداً**. وأندرويد يبقى
 * غلافاً كما هو.
 *
 * **والخطرُ مقيسٌ لا مفترض** (2026-09-29): `npx cap sync` **بلا منصّةٍ**
 * يكتب `server.url` في `ios/App/App/capacitor.config.json` — لأن المنصّةَ
 * تُستنتج من نصِّ الأمر (`tools/channels.mjs::isIosCommand`)، والأمرُ العاري
 * لا يسمّيها. **فحزمةٌ كهذه تُجمَّع خضراءَ وتفتح نطاقاً** — وهو بعينه ما
 * قُرِّر ألّا يكون.
 *
 * ## ثلاثةُ أوضاع
 *
 *     node tools/check-ios.mjs                     # ساكن — في scripts/guards.sh
 *     TAXO_CHANNEL=… node tools/check-ios.mjs --synced <app>
 *     TAXO_CHANNEL=… node tools/check-ios.mjs --built  <app> <App.app>
 *
 * - **الساكن**: المعرّفُ والاسمُ في مشروع Xcode **متغيّران يُمرَّران عند
 *   البناء** (`$(TAXO_APP_ID)` · `$(TAXO_APP_NAME)`) لا قيمةٌ مخبوزة — ومن فتح
 *   Xcode فكتب `ly.tajora.rider` في الحقل يسقط هنا. وما تولّده المزامنةُ
 *   (`capacitor.config.json` · `public/`) **مُتجاهَلٌ في git**.
 * - **بعد المزامنة**: لا `server.url` · المعرّفُ = القناة · `public/index.html`
 *   = `dist/index.html` بايتاً · **وعنوانُ القناة في الحزمة وعنوانُ غيرها
 *   غائب**.
 * - **بعد البناء**: الأسئلةُ نفسُها **من داخل `App.app`** — `Info.plist`
 *   المبنيّ لا المصدر، كما يقرأ `check-apk.mjs` الحزمةَ لا الشجرة.
 *
 * ## وما لا يقيسه — يُقال
 *
 * **لا يقيس أن التطبيقَ يعمل.** يقيس أن الحزمةَ **تحمل** شاشاتِها وتخاطب
 * هدفَها — لا أن CORS يقبلها، ولا أن ملحقاً يعمل، ولا أن شاشةً تُرسم.
 * **خُضرتُه «تُجمَّع على iOS كما قُرِّر» لا أكثر.**
 */

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { argv, exit } from "node:process";
import { CHANNEL_NAMES, fromEnv, resolve } from "./channels.mjs";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const APPS = ["customer-app", "driver-app"];

const problems = [];
const fail = (line) => problems.push(line);

function finish(label) {
  if (problems.length) {
    console.error(`✗ check:ios (${label}) — ${problems.length}:`);
    for (const p of problems) console.error(`  · ${p}`);
    exit(1);
  }
  console.log(`✓ check:ios (${label})`);
  exit(0);
}

/** القناةُ من البيئة — **أو وقوفٌ باسمها**، كـ`cap sync` لأندرويد. */
function channelOf(app) {
  if (!APPS.includes(app)) {
    console.error(`✗ تطبيقٌ بلا iOS: «${app ?? ""}» — والمعروفُ: ${APPS.join(" · ")}.`);
    exit(2);
  }
  try {
    return fromEnv(app);
  } catch (error) {
    console.error(`✗ ${error.message}`);
    exit(1);
  }
}

/** سؤالُ الإعداد المضمَّن — **يُسأل في الموضعين بالكلمات نفسِها**. */
function checkConfig(where, raw, ch) {
  let config;
  try {
    config = JSON.parse(raw);
  } catch {
    fail(`${where}: ليس JSON`);
    return;
  }
  if (config.server?.url) {
    fail(
      `${where}: server.url = ${config.server.url} — **iOS بلا غلاف**. ` +
        "أُعيدت المزامنةُ بلا منصّة؟ المزامنةُ من `tools/build-ios.mjs` وحدَه.",
    );
  }
  if (config.appId !== ch.appId) {
    fail(`${where}: appId = ${config.appId} والقناةُ «${ch.channel}» تقول ${ch.appId}`);
  }
}

/** الشاشاتُ المرفقة = المبنيّة — **وتخاطب هدفَ قناتها لا غيرَه**. */
function checkScreens(where, publicDir, app, ch) {
  const built = join(ROOT, app, "dist", "index.html");
  const shipped = join(publicDir, "index.html");
  if (!existsSync(shipped)) {
    fail(`${where}: لا index.html — حزمةٌ بلا شاشات`);
    return;
  }
  if (!existsSync(built)) {
    fail(`${app}/dist/index.html غائب — لا مبنيَّ يُقارَن به`);
  } else if (!readFileSync(built).equals(readFileSync(shipped))) {
    fail(`${where}/index.html ≠ ${app}/dist/index.html — المرفقُ غيرُ المبنيّ`);
  }

  const assets = join(publicDir, "assets");
  const js = existsSync(assets)
    ? readdirSync(assets)
        .filter((f) => f.endsWith(".js"))
        .map((f) => readFileSync(join(assets, f), "utf8"))
        .join("\n")
    : "";
  if (!js.includes(ch.apiBase)) {
    fail(`${where}: عنوانُ القناة ${ch.apiBase} غائبٌ عن الحزمة`);
  }
  for (const other of CHANNEL_NAMES.filter((c) => c !== ch.channel)) {
    const { apiBase } = resolve(other, app);
    if (apiBase !== ch.apiBase && js.includes(apiBase)) {
      fail(`${where}: عنوانُ قناةٍ أخرى (${other}: ${apiBase}) في الحزمة`);
    }
  }
}

const mode = argv[2] ?? "--static";

if (mode === "--static") {
  for (const app of APPS) {
    const ios = join(ROOT, app, "ios");
    if (!existsSync(ios)) {
      fail(`${app}/ios غائب`);
      continue;
    }
    const pbx = readFileSync(join(ios, "App", "App.xcodeproj", "project.pbxproj"), "utf8");
    const ids = [...pbx.matchAll(/PRODUCT_BUNDLE_IDENTIFIER = ([^;]+);/g)].map((m) => m[1]);
    if (ids.length === 0) fail(`${app}: لا PRODUCT_BUNDLE_IDENTIFIER في المشروع`);
    for (const id of ids) {
      if (id !== '"$(TAXO_APP_ID)"') {
        fail(`${app}: PRODUCT_BUNDLE_IDENTIFIER = ${id} — **يُمرَّر عند البناء** لا يُخبز`);
      }
    }
    const plist = readFileSync(join(ios, "App", "App", "Info.plist"), "utf8");
    const name = plist.match(/<key>CFBundleDisplayName<\/key>\s*<string>([^<]*)<\/string>/);
    if (name?.[1] !== "$(TAXO_APP_NAME)") {
      fail(`${app}: CFBundleDisplayName = ${name?.[1] ?? "(غائب)"} — **يُمرَّر عند البناء**`);
    }
    const ignored = readFileSync(join(ios, ".gitignore"), "utf8").split("\n").map((l) => l.trim());
    for (const generated of ["App/App/capacitor.config.json", "App/App/public"]) {
      if (!ignored.includes(generated)) {
        fail(`${app}/ios/.gitignore لا يذكر ${generated} — ناتجُ مزامنةٍ يُودَع بقناته`);
      }
    }
  }
  finish("ساكن");
}

if (mode === "--synced") {
  const app = argv[3];
  const ch = channelOf(app);
  const dir = join(ROOT, app, "ios", "App", "App");
  const file = join(dir, "capacitor.config.json");
  if (!existsSync(file)) fail(`${app}: لم يُزامَن — ${file} غائب`);
  else checkConfig(`${app}/ios/App/App/capacitor.config.json`, readFileSync(file, "utf8"), ch);
  checkScreens(`${app}/ios/App/App/public`, join(dir, "public"), app, ch);
  finish(`${ch.channel} · ${app} · بعد المزامنة`);
}

if (mode === "--built") {
  const app = argv[3];
  const product = argv[4];
  const ch = channelOf(app);
  if (!product || !existsSync(product)) {
    console.error(`✗ لا منتَجَ يُقاس: «${product ?? ""}»`);
    exit(1);
  }
  // **`plutil` من macOS** — و`Info.plist` المبنيُّ ثنائيٌّ غالباً. **وغيابُ
  // أداةِ القياس يوقف ولا يُقرأ سلامة.**
  let info;
  try {
    info = JSON.parse(
      execFileSync("plutil", ["-convert", "json", "-o", "-", join(product, "Info.plist")], {
        encoding: "utf8",
      }),
    );
  } catch (error) {
    console.error(`✗ لم يُقَس Info.plist — ${error.message.split("\n")[0]}`);
    exit(1);
  }
  if (info.CFBundleIdentifier !== ch.appId) {
    fail(`App.app: CFBundleIdentifier = ${info.CFBundleIdentifier || "(فارغ)"} والقناةُ تقول ${ch.appId}`);
  }
  if (info.CFBundleDisplayName !== ch.appName) {
    fail(`App.app: CFBundleDisplayName = ${info.CFBundleDisplayName || "(فارغ)"} والقناةُ تقول ${ch.appName}`);
  }
  const file = join(product, "capacitor.config.json");
  if (!existsSync(file)) fail("App.app: لا capacitor.config.json");
  else checkConfig("App.app/capacitor.config.json", readFileSync(file, "utf8"), ch);
  checkScreens("App.app/public", join(product, "public"), app, ch);
  console.log(`  ${info.CFBundleIdentifier} · ${info.CFBundleDisplayName} · ${ch.apiBase}`);
  finish(`${ch.channel} · ${app} · المبنيّ`);
}

console.error(`✗ وضعٌ غيرُ معروف: ${mode} — --static | --synced <app> | --built <app> <App.app>`);
exit(2);
