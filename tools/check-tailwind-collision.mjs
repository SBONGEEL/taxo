#!/usr/bin/env node
// check:tailwind-collision — **مُعدِّلُ صنفٍ في نظام TAXO 2.0 اسمُه صنفُ Tailwind** (عطبٌ مقيسٌ ٢٠٢٦-١١-٢٢).
//
// **الواقعة**: `<span className="t2-auth-country fixed">` — أرادت «دولةٌ ثابتةٌ لا تُختار»، وفي التطبيقات الثلاثة `@tailwind utilities`
// محمَّلٌ فصار `.fixed { position: fixed }`: **العلمُ و«+218» خرجا من حقل الهاتف وطفوا فوق «عنوان الاستلام» يتحرّكان مع التمرير**،
// وخانةُ البادئة داخل الحقل فارغة (هاتفُ المالك، «أحضر غرضي»، حسابٌ ليبيّ، ليلاً). **والمُحدِّدُ `.t2-auth-country.fixed` في CSS صحيحٌ
// وحدَه** — فلا مُحلِّلَ CSS ولا TypeScript يرى العطب؛ يقع بين ملفّين.
//
// **فالسؤالُ واحد**: أفي أوراق أنماط `taxo2` مُحدِّدٌ مركّبٌ `.t2-…​.<كلمة>` و`<كلمة>` صنفُ Tailwind قائم؟ — فكلُّ عنصرٍ يحمل المعدِّلَ
// يحمل الأداةَ معه. **ولا يمسّ الاستعمالَ المقصود** لأدوات Tailwind في JSX (`absolute inset-x-0` في الشريط السفليّ): ذاك صنفٌ يُكتب
// لأدائه، وهذا معدِّلٌ يُكتب لغيره فيؤدّيه بالصدفة.
//
// **وما لا يمسكه، مكتوباً**: معدِّلٌ يُضاف بلا قاعدةٍ في CSS (`className="t2-x hidden"` قصداً أو سهواً) — لا مُحدِّدَ يُقرأ؛ ولا الأدواتُ
// ذاتُ البادئة (`md:fixed`) لأن المعدِّلات هنا كلماتٌ عارية.
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..");
const APPS = ["customer-app", "driver-app", "admin-panel"];

// **أدواتُ Tailwind الكاملةُ بكلمةٍ واحدة** — ما يكتب سلوكاً بلا قيمة؛ والخطرُ الأوّلُ الموضعُ والظهور
const UTILITIES = new Set([
  "fixed", "absolute", "relative", "sticky", "static",
  "hidden", "invisible", "visible", "collapse", "block", "inline", "inline-block", "flex", "inline-flex", "grid", "inline-grid",
  "contents", "table", "flow-root", "list-item",
  "truncate", "italic", "underline", "overline", "uppercase", "lowercase", "capitalize", "grow", "shrink", "isolate",
  "container", "border", "rounded", "shadow", "ring", "outline", "transform", "transition", "filter", "blur", "invert", "grayscale",
  "sr-only", "not-sr-only", "antialiased", "ordinal", "rtl", "ltr",
]);

function cssFiles(dir) {
  const out = [];
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...cssFiles(full));
    else if (entry.name.endsWith(".css")) out.push(full);
  }
  return out;
}

const hits = [];
let scanned = 0;
for (const app of APPS) {
  for (const file of cssFiles(path.join(ROOT, app, "src"))) {
    const text = fs.readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
    if (!text.includes(".t2")) continue;
    scanned += 1;
    const lines = text.split("\n");
    lines.forEach((line, index) => {
      // مُحدِّدٌ مركّب: صنفُ t2- يليه مباشرةً `.كلمة` (بلا فراغٍ بينهما) — المعدِّلُ على العنصر نفسِه
      for (const match of line.matchAll(/\.(t2[\w-]*)((?:\.[\w-]+)+)/g)) {
        for (const mod of match[2].split(".").filter(Boolean)) {
          if (UTILITIES.has(mod)) hits.push(`${path.relative(ROOT, file).replace(/\\/g, "/")}:${index + 1}  .${match[1]}.${mod}`);
        }
      }
    });
  }
}

if (hits.length) {
  console.error("✗ check:tailwind-collision · معدِّلٌ في TAXO 2.0 اسمُه أداةُ Tailwind — فيحمل العنصرُ سلوكَها معه:");
  for (const hit of hits) console.error(`  ${hit}`);
  console.error("  سمِّ المعدِّلَ اسماً لا يكون أداةً (`is-static` لا `fixed`)، في CSS وفي JSX معاً.");
  process.exit(1);
}
console.log(`✓ check:tailwind-collision · لا معدِّلَ t2 باسم أداة Tailwind (${scanned} ورقةَ أنماط في ${APPS.length} تطبيقات) · ${new Date().toISOString().slice(0, 16)}Z`);
