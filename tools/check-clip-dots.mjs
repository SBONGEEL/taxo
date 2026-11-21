// check:clip-dots — **نقطتا الياء تحت السطر، والقصُّ يأكلهما** (قِيس ٢٠٢٦-١١-٢١، أمرُ المالك الثاني ذلك اليوم).
//
// **العلّة**: رأى المالكُ على هاتفه «اقتصادى» في بطاقة الفئة — والنصُّ في الشيفرة وفي `/config` «اقتصادي» حرفاً. **الحرفُ سليمٌ والرسمُ
// مقصوص**: نقطتا الياء الأخيرة تنزلان تحت خطّ السطر، و`overflow: hidden` (مع `text-overflow: ellipsis` أو `-webkit-line-clamp`) يقصّ عند
// حافّة صندوق السطر — **فبارتفاع سطرٍ دون ١٫٤ بخطّ Readex Pro تُقصّ النقطتان وتُقرأ الياءُ ألفاً مقصورة**. قِيس بالمتصفّح: ١٫٢ و١٫٣
// و`normal` تقصّ، و١٫٤ فما فوق سليمة (`design/OWNER-2026-11-21-HOME-REDESIGN.md`).
//
// **والوراثةُ هشّة**: أكثرُ القواعد القاصّة ترث ١٫٥ من `preflight` — **وأبٌ واحدٌ بسطرٍ ضيّقٍ يكسرها** (بطاقةُ الرئيسيّة كتبت ١٫٣). فالقاعدةُ:
// **كلُّ قاعدةٍ تقصّ نصّاً تكتب ارتفاعَ سطرها بنفسها، ١٫٤ فما فوق** (أو بكسلاتٍ لا تقلّ عن ١٫٤ من حجم خطّها في القاعدة نفسِها). **و`truncate`
// من Tailwind** تُضبط مرّةً في `index.css` كلِّ تطبيق (`.truncate { line-height: … }`)، ويُقاس وجودُها هنا.
//
// **وحدُّه مكتوبٌ فيه**: يقرأ ملفّات CSS **ولا يقرأ الأنماطَ المضمَّنة في TSX**، ولا يقيس ما يرسمه المتصفّحُ فعلاً (خطٌّ آخرُ بنزولٍ أعمق
// يحتاج أكثر)، ولا يرى قصّاً بـ`overflow: hidden` وحدَه على صندوقٍ بارتفاعٍ ثابت. **وصفرُ ملفٍّ مقروءٍ سقوط.**

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const APPS = ["customer-app", "driver-app", "admin-panel"];
const MIN = 1.4;

function walk(dir, out) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (name === "node_modules") continue;
    if (statSync(path).isDirectory()) walk(path, out);
    else if (name.endsWith(".css")) out.push(path);
  }
  return out;
}

function lineHeightOk(body) {
  const lh = /(?:^|;|\s)line-height:\s*([^;]+)/.exec(body);
  if (!lh) return { ok: false, why: "بلا line-height صريح (يرث)" };
  const value = lh[1].trim().replace(/\s*!important$/, "");
  if (/^[\d.]+$/.test(value)) return Number(value) >= MIN ? { ok: true } : { ok: false, why: `line-height: ${value} (< ${MIN})` };
  const px = /^([\d.]+)px$/.exec(value);
  if (px) {
    const size = /font-size:\s*([\d.]+)px/.exec(body);
    if (!size) return { ok: false, why: `line-height: ${value} بلا font-size بالبكسل في القاعدة نفسِها` };
    return Number(px[1]) >= MIN * Number(size[1]) ? { ok: true } : { ok: false, why: `line-height: ${value} لخطّ ${size[1]}px (< ${MIN}×)` };
  }
  if (/^var\(/.test(value) || /^calc\(/.test(value)) return { ok: false, why: `line-height: ${value} — لا يُقاس، اكتب رقماً` };
  return { ok: false, why: `line-height: ${value}` };
}

const failures = [];
let files = 0;
let clipping = 0;
for (const app of APPS) {
  for (const file of walk(join(ROOT, app, "src"), [])) {
    files += 1;
    const text = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
    for (const match of text.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const selector = match[1].trim().split("\n").pop().trim();
      const body = match[2];
      const clips = (/text-overflow:\s*ellipsis/.test(body) || /line-clamp:\s*\d/.test(body));
      if (!clips) continue;
      clipping += 1;
      const verdict = lineHeightOk(body);
      if (!verdict.ok) failures.push(`${relative(ROOT, file)} — ${selector}: ${verdict.why}`);
    }
  }
  // **`truncate` من Tailwind** — قاعدتُها في `index.css` التطبيق
  const index = readFileSync(join(ROOT, app, "src", "index.css"), "utf8");
  const rule = /\.truncate[^{]*\{([^}]*)\}/.exec(index);
  const verdict = rule ? lineHeightOk(rule[1]) : { ok: false, why: "لا قاعدةَ `.truncate` في index.css" };
  if (!verdict.ok) failures.push(`${app}/src/index.css — .truncate: ${verdict.why}`);
}

if (files === 0) {
  console.error("check:clip-dots ✗ — صفرُ ملفٍّ مقروء");
  process.exit(1);
}
if (failures.length) {
  console.error(`check:clip-dots ✗ — ${failures.length} قاعدةً تقصّ نقطتي الياء (السطرُ دون ${MIN}):`);
  for (const line of failures) console.error("  " + line);
  process.exit(1);
}
console.log(`check:clip-dots ✓ — ${clipping} قاعدةً قاصّةً في ${files} ملفّاً، كلُّها بسطرٍ ${MIN} فما فوق، و\`.truncate\` مضبوطةٌ في التطبيقات الثلاثة`);
