/** `check:contract` — **نداءٌ لا يقابله مسارٌ في الخلفية يُوقف البناء**.
 *
 * **ولا شيءَ في المشروع كان يقارن ما يرسله التطبيقُ بما تقبله الخلفية.** فرفعُ
 * الوثائق ظلّ يرسل `POST` إلى مسارٍ يقبل `PUT` وحدَه — **٤٠٥ في كل مرة** — ومرّ
 * على المرحلة ١٣ وستةِ سيناريوهاتٍ وجولاتِ هاتفٍ متعددة. والسببُ أن كلَّ حارسٍ
 * قائمٍ يفحص **طرفاً واحداً**: `tsc` يفحص الأنواع، و`check:enums` التعدادات،
 * و`check:config` الحمولات، و`check:doors` الأبواب بلا أزرار. **ولا واحدَ منها
 * يفحص السلك بين الطرفين.**
 *
 * ويقابل **الفعلَ والمسارَ معاً**: مسارٌ صحيحٌ بفعلٍ خاطئ هو بعينه ما وقع، وحارسٌ
 * يفحص المسارَ وحدَه كان سيمرّ عليه.
 *
 * **وحدُّه مُعلَنٌ لا مخفيّ**: يقرأ النداءاتِ المكتوبةَ حرفياً (قوالبَ نصٍّ أو
 * سلاسل). ونداءٌ مسارُه مبنيٌّ من متغيّرٍ كاملٍ لا يراه — ويُعلَن عددُها في
 * المخرَج بدل أن يُصمت عنها، فالحارسُ الذي يُخفي ما فاته يُقرأ أوسعَ مما هو.
 */

import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { certify } from "./certify.mjs";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const ROUTERS = join(ROOT, "backend", "app", "routers");

const APPS = {
  "customer-app": "customer-app",
  "driver-app": "driver-app",
  "admin-panel": "admin-panel",
};

/** نداءاتٌ لا تُقابَل — ومعها علّتُها نصّاً. */
const EXEMPT = new Map([
  // مسارٌ خارجيٌّ لا يخصّ خلفيتَنا
  ["GET https://api.mapbox.com", "مزوّدٌ خارجيّ"],
  // **عنوانٌ يُسلَّم إلى كودٍ أصليٍّ لا يُنادى من TypeScript** (2026-08-21):
  // `lib/online-service.ts` يمرّر عنوانَ البثِّ إلى الخدمة الأمامية، **وهي
  // التي ترسل `POST`** حين يخنق النظامُ مؤقتاتِ الـWebView. فالفعلُ يقع في
  // Java ولا يراه هذا الحارسُ الذي يقرأ الشجرةَ الأمامية وحدَها — **والمسارُ
  // نفسُه مقابَلٌ فعلاً** من `reportLocationOverRest` بفعله الصحيح.
  //
  // **ولا يُوسَّع هذا الاستثناءُ إلى «كلِّ ما يُمرَّر نصّاً»**: هو لعنوانٍ
  // واحدٍ بعينه، ومن أضاف ثانياً يكتب علّتَه هنا كما كُتبت هذه.
  ["GET /drivers/me/location", "عنوانٌ يُسلَّم للخدمة الأمامية، والإرسالُ منها بـPOST"],
]);

function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");
}

/** كلُّ مساراتِ الخلفية: [{verb, path}] مع البادئة. */
function backendRoutes() {
  const found = [];
  for (const name of readdirSync(ROUTERS)) {
    if (!name.endsWith(".py")) continue;
    const src = readFileSync(join(ROUTERS, name), "utf-8");
    const prefix =
      src.match(/APIRouter\([\s\S]*?prefix\s*=\s*"([^"]*)"/)?.[1] ?? "";
    const re = /@router\.(get|post|put|patch|delete)\(\s*"([^"]*)"/g;
    let m;
    while ((m = re.exec(src)) !== null) {
      found.push({
        verb: m[1].toUpperCase(),
        path: (prefix + m[2]) || "/",
        file: name,
      });
    }
  }
  return found;
}

/** يحوّل مسارَ الخلفية إلى نمطٍ يقبل قوالبَ الواجهة. */
function routePattern(path) {
  const parts = path
    .split("/")
    .filter(Boolean)
    .map((seg) =>
      seg.startsWith("{")
        ? "[^/]+"
        : seg.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
    );
  return new RegExp("^/" + parts.join("/") + "$");
}

/** نداءاتُ تطبيقٍ واحد: [{verb, path, file, line}]. */
function appCalls(dir) {
  const calls = [];
  const walk = (d) => {
    for (const entry of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, entry.name);
      if (entry.isDirectory()) {
        walk(p);
        continue;
      }
      if (!/\.tsx?$/.test(entry.name)) continue;
      const src = stripComments(readFileSync(p, "utf-8"));
      const rel = p.slice(ROOT.length).replace(/\\/g, "/");

      // `api.get<T>("/x")` · `api.post("/x", …)` · `api.del(...)`
      const api =
        /\bapi\.(get|post|put|patch|del)\s*(?:<[^>]*>)?\s*\(\s*([`"'])([^`"']*)\2/g;
      let m;
      while ((m = api.exec(src)) !== null) {
        const verb = m[1] === "del" ? "DELETE" : m[1].toUpperCase();
        calls.push({ verb, raw: m[3], file: rel, line: lineOf(src, m.index) });
      }

      // رفعُ الملفات — عميلٌ خاصٌّ خارج `api.*` (تقدّمُ الرفع يحتاج XHR)
      const up = /\bupload\s*(?:<[^>]*>)?\s*\(\s*([`"'])([^`"']*)\1/g;
      while ((m = up.exec(src)) !== null) {
        calls.push({
          verb: uploadVerb(dir),
          raw: m[2],
          file: rel,
          line: lineOf(src, m.index),
          note: "رفع",
        });
      }

      // عنوانٌ يُبنى بيدٍ: `${API_URL}/x`
      const direct = /\$\{API_URL\}([^`"']*)/g;
      while ((m = direct.exec(src)) !== null) {
        calls.push({
          verb: nearestVerb(src, m.index),
          raw: m[1],
          file: rel,
          line: lineOf(src, m.index),
          note: "عنوانٌ مبنيّ",
          outsideLayer: !/\/api\/(endpoints|client)\.ts$/.test(rel),
        });
      }
    }
  };
  walk(join(ROOT, dir, "src"));
  return calls;
}

/** الفعلُ الذي يفتح به عميلُ الرفع — **يُقرأ من `client.ts` نفسِه**.
 *
 * **وكذبت أولُ نسخةٍ هنا**: كانت تقرأ الملفَّ الذي يُنادى فيه `upload(...)`
 * (`endpoints.ts`) لا الذي يفتح المقبس، فلا تجد `request.open` فتفترض `POST`
 * — وأبلغت عن عطبٍ لا وجودَ له في مسارٍ يرسل `PUT` منذ شهر. **حارسٌ يخترع
 * عطباً يُفقد الثقةَ بما يجده حقاً.**
 */
function uploadVerb(appDir) {
  for (const rel of ["src/api/client.ts", "src/api/upload.ts"]) {
    try {
      const src = readFileSync(join(ROOT, appDir, rel), "utf-8");
      const m = src.match(/request\.open\(\s*["']([A-Z]+)["']/);
      if (m) return m[1];
    } catch {
      // الملفُّ غيرُ موجودٍ في هذا التطبيق — يُجرَّب التالي
    }
  }
  return "POST";
}

/** أقربُ `method:` أو `fetch(` قبل الموضع — أو `GET` وهو افتراضُ `fetch`. */
const HTTP_VERBS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]);

function nearestVerb(src, index) {
  // **ولا يُلتقط أيُّ `method:` مجاور**: أولُ نسخةٍ قرأت `method: "cash"` من
  // حمولةِ شحنٍ إداريٍّ قريبةٍ فأعلنت فعلاً اسمُه `CASH`. فالمقبولُ ما كان
  // فعلاً حقيقياً، وما عداه يُقرأ `GET` — وهو افتراضُ `fetch` نفسِه
  const before = src.slice(Math.max(0, index - 300), index + 300);
  for (const m of before.matchAll(/method\s*:\s*["']([A-Za-z]+)["']/g)) {
    const verb = m[1].toUpperCase();
    if (HTTP_VERBS.has(verb)) return verb;
  }
  return "GET";
}

function lineOf(src, index) {
  return src.slice(0, index).split("\n").length;
}

/** قالبُ نصٍّ إلى مسارٍ قابلٍ للمطابقة: `${x}` تصير جزءاً واحداً. */
function normalize(raw) {
  // **وسلسلةُ الاستعلام ليست مساراً**: `/wallet/me?wallet=rider` مسارُه
  // `/wallet/me`. أولُ نسخةٍ عدّتها جزءاً فأبلغت عن أربعةَ عشرَ نداءً سليماً
  return raw.replace(/\$\{[^}]*\}/g, "§").split("?")[0].split("#")[0];
}

const routes = backendRoutes();
const patterns = routes.map((r) => ({ ...r, re: routePattern(r.path) }));

let broken = [];
const jumpers = [];
let unresolved = 0;
let checked = 0;

const target = process.argv.includes("--app")
  ? process.argv[process.argv.indexOf("--app") + 1]
  : null;

for (const [name, dir] of Object.entries(APPS)) {
  if (target && target !== name) continue;
  for (const call of appCalls(dir)) {
    if (call.outsideLayer) jumpers.push({ ...call, app: name });
    const path = normalize(call.raw);
    if (!path.startsWith("/")) {
      // عنوانٌ خارجيٌّ أو جزءٌ لا يُحكم عليه
      if (!path.startsWith("§")) unresolved += 1;
      continue;
    }
    checked += 1;
    const probe = path.replace(/§/g, "x");
    const samePath = patterns.filter((r) => r.re.test(probe));
    if (samePath.length === 0) {
      broken.push({ ...call, app: name, why: "لا مسارَ يطابقه" });
      continue;
    }
    if (!samePath.some((r) => r.verb === call.verb)) {
      broken.push({
        ...call,
        app: name,
        why: `الفعلُ ${call.verb} — والخلفيةُ تقبل ${[
          ...new Set(samePath.map((r) => r.verb)),
        ].join("/")}`,
      });
    }
  }
}

broken = broken.filter((b) => !EXEMPT.has(`${b.verb} ${b.raw}`));

if (broken.length > 0) {
  console.error(`\n✗ ${broken.length} نداءً لا يقابله مسارٌ في الخلفية:\n`);
  for (const b of broken) {
    console.error(`   [${b.app}] ${b.verb} ${b.raw}`);
    console.error(`      ${b.file}:${b.line} — ${b.why}`);
  }
  console.error("");
  process.exit(1);
}

// **وطبقةُ الأبواب شرطٌ ثانٍ غيرُ صحّة المسار** (2026-08-23): مسارٌ يُبنى في
// شاشةٍ **صحيحاً** يمرّ من الفحص أعلاه — **ويقفز فوق الطبقة**. فيبقى حيّاً بعد
// أن يتغيّر في الخلفية، ولا يراه من يقرأ `endpoints.ts` ليعرف ما يطرقه التطبيق.
//
// **والحارسُ يحرس البابَ ولا يرى من قفز السور** — وقِيست ثلاثةُ قافزين
// 2026-08-23: صورةُ بلاغٍ في شاشة، وتنزيلُ نسخةٍ في مكوّن، **وعنوانُ بثِّ
// الموقع في الخدمة الأمامية** — وهذا أخطرُها: الشاشةُ تُفتح فيُرى عطبُها،
// **والخدمةُ تعمل والشاشةُ مقفلة** فيُقرأ صمتُها «لا طلبات اليوم».
if (jumpers.length > 0) {
  console.error(`\n✗ ${jumpers.length} عنواناً يُبنى خارج طبقة الأبواب:\n`);
  for (const j of jumpers) console.error(`   ${j.file}:${j.line} — \${API_URL}${j.raw}`);
  console.error("\n  يُعلَن في `api/endpoints.ts` ويُستدعى من هناك — ولو لم يمرّ بـ`api.*`.");
  process.exit(1);
}

certify("check:contract", 
  `✓ كل نداءات الواجهة (${checked}) تقابل فعلاً ومساراً في الخلفية` +
    (unresolved ? ` · وتعذّر الحكمُ على ${unresolved} (عنوانٌ من متغيّر)` : ""),
);
