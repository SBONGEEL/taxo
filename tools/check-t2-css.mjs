// check:t2-css — **محدِّدٌ واحدٌ بقيمتين لخاصّيةٍ واحدة في ورقة أنماطٍ واحدة** (قِيس ٢٠٢٦-١٠-٠٤).
//
// **العلّة**: بطاقةُ المسار في ورقة الطلب (R06) سُمّيت `.t2-route`، وهو اسمُ سطر المسار في «رحلاتي» (R12) في الملفّ نفسِه —
// فطغت `grid-template-columns: 14px 1fr auto` على `10px 1fr`، وصارت وجهةُ كلِّ رحلةٍ حرفاً واحداً نهاراً. **ولم يمسكه شيء**:
// tsc لا يقرأ CSS، والحرّاسُ تقرأ الشيفرة، **ووجدته لقطةٌ متجاورةٌ بالتصميم بعد إيداعين**.
//
// **وما يُمسك هو التعارضُ لا التكرار**: قاعدةٌ ثانيةٌ للمحدِّد نفسِه **تضيف** خاصّيةً (`.t2-home-near { z-index: 2 }`) تقسيمٌ
// مقصود، **وقاعدةٌ تعيد خاصّيةً بقيمةٍ أخرى** هي ما قلب R12 — اسمان لشيئين أو تعديلٌ نُسي أصلُه. والسياقُ جزءٌ من المفتاح:
// القاعدةُ داخل `@media` تُقارَن بأخواتها في الكتلة نفسِها لا بالقاعدة العليا (ذاك تجاوزٌ مقصود).
//
// **والقاعدةُ المجمَّعةُ أساسٌ مشترَكٌ يُتجاوَز** (`.t2-store-buy, .t2-store-garage {…}` ثمّ `.t2-store-garage { background: none }`):
// تجميعُ المحدِّدات يقول «شكلٌ واحدٌ ثمّ يفترقان» — نمطٌ مقصودٌ وجده أوّلُ تشغيلٍ مرّتين. **فالتعارضُ يُقاس بين القواعد التي يقف فيها
// المحدِّدُ وحدَه** — وهو بعينه شكلُ R12: قاعدتان قائمتان باسمٍ واحدٍ لشيئين.
//
// **وحدُّه مكتوبٌ فيه**: يقرأ الملفَّ الواحد — **ولا يمسك اسمين متصادمين في ملفّين** يُحمَّلان معاً (ترتيبُ تحميلهما يحسم)،
// ولا تعارضاً بين محدِّدين مختلفين يصيبان العنصرَ نفسَه (`.a .b` و`.b`)، **ولا قاعدةً مجمَّعةً تعارض أختَها المجمَّعة**. **وصفرُ ملفٍّ
// مقروءٍ سقوط.**

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
// **ولوحةُ الإدارة ثالثتُها** (§٦٢/١٦): إطارُها وعُدّتُها وشاشاتُها في `src/t2/`، ونسختُها من نظام التصميم في `src/taxo2/`
const APPS = ["customer-app", "driver-app", "admin-panel"];
// عائلةُ TAXO 2.0 — حيث تُكتب الشاشاتُ الجديدةُ بأيدٍ كثيرة
const DIRS = ["src/screens/t2", "src/taxo2", "src/components/welcome", "src/t2"];

function cssFiles() {
  const out = [];
  for (const app of APPS) {
    for (const dir of DIRS) {
      const base = join(ROOT, app, dir);
      let names = [];
      try {
        names = readdirSync(base);
      } catch {
        continue;
      }
      for (const name of names) {
        const path = join(base, name);
        if (name.endsWith(".css") && statSync(path).isFile()) out.push(path);
      }
    }
  }
  return out;
}

/** قواعدُ الملفّ بسياقها: `{ context, selectors[], decls: [{prop, value}], line }` — يُنزع التعليقُ أوّلاً بمكانه سطرياً. */
function rules(text) {
  const clean = text.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
  const found = [];
  const stack = []; // سياقاتُ الكتل المفتوحة: نصُّ المقدّمة
  let start = 0;
  for (let i = 0; i < clean.length; i += 1) {
    const ch = clean[i];
    if (ch === "{") {
      const prelude = clean.slice(start, i).trim();
      const line = clean.slice(0, i).split("\n").length;
      stack.push({ prelude, bodyStart: i + 1, line });
      start = i + 1;
    } else if (ch === "}") {
      const open = stack.pop();
      if (!open) {
        start = i + 1;
        continue;
      }
      const body = clean.slice(open.bodyStart, i);
      // قاعدةُ أنماطٍ لا كتلةُ @ ولا إطارُ @keyframes (من/إلى/نِسَب)
      const isAt = open.prelude.startsWith("@");
      const inKeyframes = stack.some((frame) => /^@(-\w+-)?keyframes/.test(frame.prelude));
      if (!isAt && !inKeyframes && !body.includes("{")) {
        const decls = body
          .split(";")
          .map((part) => part.trim())
          .filter(Boolean)
          .map((part) => {
            const colon = part.indexOf(":");
            return colon < 0 ? null : { prop: part.slice(0, colon).trim(), value: part.slice(colon + 1).trim().replace(/\s+/g, " ") };
          })
          .filter(Boolean);
        found.push({
          context: stack.map((frame) => frame.prelude.replace(/\s+/g, " ")).join(" » "),
          selectors: open.prelude.split(",").map((s) => s.trim().replace(/\s+/g, " ")).filter(Boolean),
          decls,
          line: open.line,
        });
      }
      start = i + 1;
    } else if (ch === ";" && stack.length === 0) {
      start = i + 1; // `@import …;` وأمثالُه في الأعلى
    }
  }
  return found;
}

const files = cssFiles();
const failures = [];
let selectorsSeen = 0;
let repeated = 0;

for (const file of files) {
  const seen = new Map(); // "سياق␟محدِّد" → Map(خاصّية → [{value, line}])
  const counts = new Map();
  for (const rule of rules(readFileSync(file, "utf8"))) {
    for (const selector of rule.selectors) {
      const key = `${rule.context}␟${selector}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
      if (!seen.has(key)) seen.set(key, new Map());
      // **المجمَّعةُ أساسٌ مشترَك** — تُعدّ في التكرار ولا تدخل المقارنة
      if (rule.selectors.length > 1) continue;
      const props = seen.get(key);
      for (const { prop, value } of rule.decls) {
        if (!props.has(prop)) props.set(prop, []);
        props.get(prop).push({ value, line: rule.line });
      }
    }
  }
  selectorsSeen += seen.size;
  for (const [key, n] of counts) if (n > 1) repeated += 1;
  for (const [key, props] of seen) {
    const [context, selector] = key.split("␟");
    for (const [prop, entries] of props) {
      const values = [...new Set(entries.map((entry) => entry.value))];
      if (values.length > 1) {
        failures.push(
          `${relative(ROOT, file)}: ${context ? `${context} » ` : ""}${selector} { ${prop} } — ` +
            entries.map((entry) => `«${entry.value}» (سطر ${entry.line})`).join(" ثمّ "),
        );
      }
    }
  }
}

if (files.length === 0) {
  console.error("✗ check:t2-css · صفرُ ملفٍّ مقروء — الحارسُ لا يقرأ شيئاً");
  process.exit(1);
}
if (failures.length > 0) {
  console.error(`✗ check:t2-css · محدِّدٌ بقيمتين لخاصّيةٍ واحدة في ملفٍّ واحد (${failures.length}):`);
  for (const line of failures) console.error(`  ${line}`);
  console.error("  — اسمان لشيئين مختلفين، أو تعديلٌ نُسي أصلُه. سمِّ الثانيَ باسمه، أو ادمج القاعدتين.");
  process.exit(1);
}
console.log(
  `✓ check:t2-css · لا محدِّدَ بقيمتين لخاصّيةٍ واحدة — ${files.length} ملفّاً، ${selectorsSeen} محدِّداً، ` +
    `${repeated} مكرَّراً يضيف ولا يعارض · ${new Date().toISOString().slice(0, 16)}Z`,
);
