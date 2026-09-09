/** **حزمةٌ تُبنى ثمّ يُغيَّر ما تشير إليه = حزمةٌ كاذبة** — تُقاس قبل التثبيت.
 *
 * ## العلّةُ مقيسةٌ لا مفترضة (٢٠٢٦-٠٩-٠٩)
 *
 * بُنيت `ly.tajora.rider.test` وثُبِّتت، ثمّ **غُيِّرت الحاويةُ التي تخدم
 * شاشاتِها** — فصار ما في اليد لا يوصف ما في الجهاز. **والسؤالُ الذي لم يكن
 * لأحدٍ أن يجيبه بلا فتحِ الحزمة**: أيَّ خادمٍ تنادي هذه الحزمةُ بالضبط؟
 *
 * **و`check:apk` يقيس `server.url` وحدَه** — عنوانَ الشاشات. **وهذا يقيس
 * الاثنين**: الشاشاتِ **والـAPI** المخبوزَ في الحزمة الجافاسكربتية، ويقارنهما
 * بـ`channels.json` للقناة المصرَّحة.
 *
 * **ويُشغَّل قبل `adb install` لا بعده**: بعده يكون الجهازُ قد أخذ الكذبة.
 *
 *     node tools/check-apk-target.mjs <ملفّ.apk> <public|test>
 *
 * **وما لا يقيسه يقوله**: لا يقيس أن الخادمَ حيٌّ ولا أن CORS يسمح — تلك
 * أعمدةٌ أخرى. **يقيس أن ما في الحزمة هو ما صُرِّح به، لا أكثر.**
 */

import { readFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";
import { resolve as resolveChannel } from "./channels.mjs";

const ROOT = dirname(fileURLToPath(new URL(".", import.meta.url))).replace(
  /[\\/]tools$/,
  "",
);

// **والتطبيقُ يُصرَّح ولا يُفترض** (صُحّح ٢٠٢٦-٠٩-٠٩): كان الحارسُ يقارن كلَّ
// حزمةٍ بقناة **تطبيق الراكب** مهما كانت — فحزمةُ الكبتن الصحيحةُ تماماً
// أُعلنت «تشير إلى غير ما صُرِّح» بثلاثة فروق، **وهو بلاغٌ كاذبٌ يُطفئ حارساً**.
const APPS = new Set(["customer-app", "driver-app", "admin-panel"]);
const [apkPath, channelName, appName = "customer-app"] = process.argv.slice(2);
if (!apkPath || !channelName) {
  console.error(
    "الاستعمال: node tools/check-apk-target.mjs <ملفّ.apk> <public|test> [customer-app|driver-app|admin-panel]",
  );
  process.exit(2);
}
if (!APPS.has(appName)) {
  console.error(`
✗ تطبيقٌ غيرُ معروف: ${appName} — والمعروفُ: ${[...APPS].join(" · ")}`);
  process.exit(2);
}
if (!existsSync(apkPath)) {
  console.error(`\n✗ لا حزمةَ عند: ${apkPath} — **وصفرٌ مقروءٌ عطبٌ لا سلامة**.`);
  process.exit(2);
}

/** يقرأ مدخلاً من داخل الـAPK بلا فكِّ ضغطٍ إلى القرص. */
function entry(name) {
  try {
    return execFileSync("unzip", ["-p", apkPath, name], {
      maxBuffer: 64 * 1024 * 1024,
      encoding: "utf8",
    });
  } catch {
    return "";
  }
}

/** أسماءُ ما في الحزمة — لنجد حزمةَ الجافاسكربت مهما تغيّرت بصمتُها. */
function names() {
  try {
    return execFileSync("unzip", ["-Z1", apkPath], {
      maxBuffer: 64 * 1024 * 1024,
      encoding: "utf8",
    }).split("\n");
  } catch {
    return [];
  }
}

const want = resolveChannel(channelName, appName);
const apiHost = new URL(want.apiBase).host;
const shellHost = new URL(want.shellUrl).host;

// ── ١) عنوانُ الشاشات، من `capacitor.config.json` داخل الحزمة
const cfgRaw = entry("assets/capacitor.config.json");
if (!cfgRaw.trim()) {
  console.error("\n✗ لم يُقرأ `assets/capacitor.config.json` من الحزمة — **لم يُقس**.");
  process.exit(2);
}
const cfg = JSON.parse(cfgRaw);
const gotShell = cfg?.server?.url ?? "";
const gotAppId = cfg?.appId ?? "";

// ── ٢) عنوانُ الـAPI، من حزمة الجافاسكربت المضمَّنة
const jsNames = names().filter((n) => /^assets\/public\/.*\.js$/.test(n));
let foundApi = null;
const strays = new Set();
// **ويُبحث عن المحلّيِّ في حزمةِ تطبيقنا وحدَها لا في حزم الغير**
// (ضُيِّق ٢٠٢٦-٠٩-٠٩): أوّلُ نسخةٍ صاحت على  في
//  — **ثابتٌ داخليٌّ في حزمة Firebase لا يُنادى**.
// **وحارسٌ يخترع عطباً أغلى من واحدٍ يفوته**: يُطفأ، فيسقط معه ما يمسكه
// حقّاً. **فالحزمةُ التي تحمل عنوانَ الـAPI هي حزمةُ إعدادنا** — والمحلّيُّ
// فيها وحدَها خبرٌ، وما عداها ضجيجُ مكتبات.
const LOCAL = /^(127\.0\.0\.1|localhost|10\.0\.2\.2|0\.0\.0\.0)/;
for (const n of jsNames) {
  const body = entry(n);
  if (!body) continue;
  const hosts = [...body.matchAll(/https?:\/\/([A-Za-z0-9._-]+(?::\d+)?)\/?/g)].map(
    (m) => m[1],
  );
  const isOurs = hosts.includes(apiHost);
  if (isOurs) {
    foundApi = apiHost;
    for (const h of hosts) if (LOCAL.test(h)) strays.add();
  }
}

const problems = [];
if (gotAppId !== want.appId) problems.push(`المعرّف: ${gotAppId} ≠ ${want.appId}`);
if (gotShell !== want.shellUrl) problems.push(`الشاشات: ${gotShell} ≠ ${want.shellUrl}`);
if (!foundApi) problems.push(`الـAPI: لم يُوجد ${apiHost} في أيٍّ من ${jsNames.length} ملفَّ جافاسكربت`);
for (const s of strays) problems.push(`عنوانٌ محلّيٌّ في حزمةِ هاتف: ${s}`);

console.log("");
console.log(`  الحزمة — ما تشير إليه من داخلها  (قناة ${channelName})`);
console.log(`  · المعرّف : ${gotAppId}`);
console.log(`  · الشاشات : ${gotShell}`);
console.log(`  · الـAPI  : ${foundApi ?? "«لم يُوجد»"}   (فُحص ${jsNames.length} ملفّاً)`);

if (problems.length === 0) {
  console.log(`  ✓ ثلاثتُها تطابق \`channels.json\` — تُثبَّت`);
  process.exit(0);
}

console.error("");
console.error("  ✗ **حزمةٌ تشير إلى غير ما صُرِّح — ولا تُثبَّت**");
for (const p of problems) console.error(`      ${p}`);
console.error("");
console.error("  **حزمةٌ تُبنى ثمّ يُغيَّر ما تشير إليه تصير كاذبة**، ولا يظهر");
console.error("  كذبُها في بناءٍ ولا توقيعٍ ولا تثبيت — **يظهر على شاشة الهاتف**.");
process.exit(1);
