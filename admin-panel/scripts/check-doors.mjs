/** `check:doors` — **بابٌ إداريٌّ بلا زرّ يُوقف البناء** (قرارُ المالك 2026-08-19).
 *
 * هذا الشكلُ تكرّر في المشروع مراراً: مفتاحٌ سابعٌ بلا زرّ، شارةُ كبتنٍ بلا زرّ
 * منح، ردُّ دفعةٍ مبنيٌّ ومختبَرٌ في ثلاثة ملفاتٍ ولا صفَّ في اللوحة يُضغط عليه.
 * **والقاعدةُ المكتوبةُ لم تكفِ** — وهو بعينه ما قيل عن `check:flags` قبل بنائه.
 *
 * فالحارسُ يقابل **كلَّ مسارٍ إداريٍّ في الخلفية** بما تناديه اللوحةُ فعلاً،
 * ويرفض ما لا يجد له نداءً إلا أن يكون **غياباً مُصرَّحاً بعلّته** في
 * `DELIBERATE` أدناه.
 *
 * وثلاثةُ تفاصيل تجعله حارساً لا مزعجاً:
 *
 * - **التعليقاتُ تُحذف قبل المطابقة**: أولُ نسخةٍ عدَّت ذكرَ المسار في تعليقٍ
 *   نداءً موجوداً، فأخفت `POST /drivers/me/online`. حارسٌ يكذب في اتجاهٍ واحدٍ
 *   يُطمأنّ إليه.
 * - **المعاملاتُ تُقارَن بنمط**: `/admin/wallets/{user_id}/topups` في الخلفية
 *   هو `` `/admin/wallets/${id}/topups` `` في الواجهة.
 * - **والغيابُ المصرَّحُ يحمل سببَه نصّاً** — لا مجرّدَ استثناء: قائمةٌ بلا
 *   أسبابٍ تصير مقبرةً يُلقى فيها كلُّ ما لم يُبنَ.
 */

import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { certify } from "../../tools/certify.mjs";

const ROOT = new URL("../..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const ROUTERS = join(ROOT, "backend", "app", "routers");
const PANEL = join(ROOT, "admin-panel", "src");

/** أبوابٌ لا زرَّ لها **بقرارٍ مكتوب** — ومعها علّتُها ومَن قرّرها. */
const DELIBERATE = new Map([
  [
    "POST /admin/withdrawals/{request_id}/payout",
    "مؤجَّلٌ حتى يثبت مزوّدُ الصرف على اعتماداتٍ حقيقية (SPEC §18.2-أ). والصرفُ اليدويُّ يعمل، وزرٌّ يُخرج المالَ عبر واجهةٍ لم تُجرَّب أخطرُ من غيابه.",
  ],
  [
    "GET /admin/drivers/{driver_id}/badges",
    "شاراتُ البند ٥٣ — الكتالوجُ والمنحُ قائمان بلا درج (SPEC §18.2).",
  ],
  [
    "POST /admin/drivers/{driver_id}/badges",
    "شاراتُ البند ٥٣ — لا يُبنى نصفُها: زرٌّ يمنح بلا سجلِّ تدقيقٍ أسوأُ من غيابه.",
  ],
  [
    "POST /admin/drivers/{driver_id}/badges/{badge_id}/revoke",
    "شاراتُ البند ٥٣ — تابعٌ لبابِ المنح.",
  ],
  [
    "POST /admin/campaigns/test-push",
    "دفعةٌ تجريبيةٌ قبل حملة — مسجَّلٌ في SPEC §18.2 ولم يُقرَّر بناؤه بعد.",
  ],
]);

function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/^\s*\/\/.*$/gm, " ");
}

/** **التصريحُ ليس زرّاً** — وهذا ما فاتَ النسخةَ الأولى.
 *
 * `api/endpoints.ts` يصرّح بالمسار، والشاشةُ هي التي تناديه. فلو اكتُفي بوجود
 * المسار في المصدر لَمرَّ كلُّ ما صُرِّح به ولم يُستعمل — وهو بعينه عطبُ البند ٧
 * في جولة الجهاز: `GET /drivers/nearby` مصرَّحٌ به في `endpoints.ts` **ولا
 * ينادِيه أحد**، فبقيت خريطةُ الراكب فارغة.
 *
 * فالفحصُ شقّان: المسارُ في `endpoints.ts`، **واسمُ دالّته يُستعمل خارجَه**.
 */
function panelSources() {
  const endpoints = stripComments(
    readFileSync(join(PANEL, "api", "endpoints.ts"), "utf-8"),
  );
  let screens = "";
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (/\.tsx?$/.test(entry.name) && entry.name !== "endpoints.ts")
        screens += stripComments(readFileSync(path, "utf-8"));
    }
  };
  walk(PANEL);
  return { endpoints, screens };
}

/** اسمُ الدالّة المصرَّحة التي يقع المسارُ في جسمها — أو `null`. */
function declaredName(endpoints, pattern) {
  const re = new RegExp(
    String.raw`export\s+(?:const|async function|function)\s+(\w+)[\s\S]*?(?=\nexport\s|\n/\*\*|$)`,
    "g",
  );
  let m;
  while ((m = re.exec(endpoints)) !== null) {
    if (pattern.test(m[0])) return m[1];
  }
  return null;
}

function adminRoutes() {
  const found = [];
  for (const name of readdirSync(ROUTERS)) {
    if (!name.endsWith(".py")) continue;
    const src = readFileSync(join(ROUTERS, name), "utf-8");
    const prefix = src.match(/APIRouter\([\s\S]*?prefix\s*=\s*"([^"]*)"/)?.[1] ?? "";
    const re = /@router\.(get|post|put|patch|delete)\(\s*"([^"]*)"/g;
    let m;
    while ((m = re.exec(src)) !== null) {
      const path = (prefix + m[2]) || "/";
      if (!path.startsWith("/admin")) continue;
      found.push({ verb: m[1].toUpperCase(), path, file: name });
    }
  }
  return found;
}

function patternFor(path) {
  const parts = path
    .split("/")
    .filter(Boolean)
    .map((seg) =>
      seg.startsWith("{")
        ? "[^\"'`/]+"
        : seg.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
    );
  return new RegExp("/" + parts.join("/"));
}

const { endpoints, screens } = panelSources();
const routes = adminRoutes();
const orphans = [];
const staleExemptions = [];

for (const route of routes) {
  const key = `${route.verb} ${route.path}`;
  const pattern = patternFor(route.path);
  const name = declaredName(endpoints, pattern);
  // زرٌّ حقيقيّ = مصرَّحٌ به **واسمُه يُستعمل في شاشةٍ أو مكوّن**
  // **أو يُبنى العنوانُ في الشاشة مباشرةً** — كتنزيل النسخة الاحتياطية، حيث
  // يُبنى الرابطُ بيدٍ ويُسلَّم للمتصفح. بابٌ مطروقٌ بغير دالّةٍ مصرَّحة، وحارسٌ
  // لا يراه يصيح على ما يعمل — وحارسٌ يصيح على العامل يُعطَّل
  const wired =
    (name !== null &&
      new RegExp(String.raw`\b` + name + String.raw`\b`).test(screens)) ||
    pattern.test(screens);
  if (wired && DELIBERATE.has(key)) staleExemptions.push(key);
  if (!wired && !DELIBERATE.has(key))
    orphans.push({ ...route, key, why: name === null ? "لا تصريح" : `مصرَّحٌ (${name}) ولا نداء` });
}

if (orphans.length > 0) {
  console.error(
    `\n✗ ${orphans.length} باباً إدارياً بلا زرٍّ في اللوحة، وبلا علّةٍ مكتوبة:\n`,
  );
  for (const o of orphans)
    console.error(`   ${o.key}   (${o.file}) — ${o.why}`);
  console.error(
    "\n  إمّا أن يصله زرٌّ، وإمّا أن يُضاف إلى `DELIBERATE` في scripts/check-doors.mjs",
  );
  console.error("  **بعلّته نصّاً** — وأن يُسجَّل في SPEC.md §18.2.\n");
  process.exit(1);
}

// **والاستثناءُ الذي بُني له زرٌّ يُحذف**: قائمةُ أعذارٍ لا تُنظَّف تصير كذباً
if (staleExemptions.length > 0) {
  console.error("\n✗ استثناءاتٌ صار لها زرٌّ — تُحذف من `DELIBERATE`:\n");
  for (const key of staleExemptions) console.error(`   ${key}`);
  console.error("");
  process.exit(1);
}

certify("check:doors", 
  `✓ كل المسارات الإدارية (${routes.length}) لها زرٌّ أو علّةٌ مكتوبة (${DELIBERATE.size})`,
);
