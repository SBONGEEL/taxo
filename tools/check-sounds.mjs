// check:sounds — **كلُّ صوتٍ في التطبيقات ملفٌّ من العائلة التي اختارها المالك، ولا مذبذبَ في أيِّ موضع** (§٦٢/١٢، ٢٠٢٦-١٠-٠٥).
//
// **العلّة**: رفض المالكُ النغماتِ المركّبةَ برمجياً واختار ملفّاتٍ من مكتبةٍ مرخَّصة (§٦١-ك) — **فوُصلت العشرةُ وبقيت خمسُ
// نغماتٍ مركّبةٍ** «حتى يقرّر»: التوقيعُ عند أوّل لمسةٍ بعد الدخول، وانقضاءُ الطلب، ووصولُ الكبتن، وتذكيرُ الاشتراك، وتأكيدُ
// الطلب عند الراكب. **فكان أوّلُ ما يُسمع في كلِّ جلسةٍ نغمةً قديمة**، وقال المالكُ بعد جولته: «الأصواتُ ما زالت القديمة».
// **ولم يمسكه شيء**: الجدولان (`FILES` و`CUES`) كانا مقصودَين، **والمسارُ الثاني بقي حيّاً بلا أحدٍ يسأل عنه.**
//
// **فيُقاس شيئان:**
//   ١) **لا مذبذبَ في شيفرة التطبيقات** — لا `createOscillator` ولا `OscillatorNode`: صوتٌ يُركَّب في الشيفرة هو القديمُ بعينه،
//      **أيّاً كان اسمُه** — فالفحصُ على النداء لا على اسم الجدول.
//   ٢) **كلُّ ملفٍّ في `FILES` موجودٌ في `public/` تطبيقِه** — والنوعُ `Record<Cue, string>` يُلزم كلَّ صوتٍ بملفٍّ عند البناء.
//
// **وحدُّه مكتوبٌ فيه**: لا يسمع — **لا يعرف أنّ الملفَّ من العائلة** (ذاك في `design/TAXO-SOUNDS.md` ببصماته)، ولا يقيس أصواتَ
// الإشعار الأصليّة في أندرويد (`res/raw` وقنواتُها — تُقاس على الهاتف). **وصفرُ ملفٍّ مقروءٍ سقوط.**

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const APPS = ["customer-app", "driver-app", "admin-panel"];
const SOUNDED = ["customer-app", "driver-app"];
const OSCILLATOR = /\bcreateOscillator\s*\(|\bOscillatorNode\b/;

function sources(dir) {
  const out = [];
  let names = [];
  try {
    names = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of names) {
    if (name === "node_modules" || name === "dist") continue;
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...sources(path));
    else if (/\.(ts|tsx|js|jsx|mjs)$/.test(name)) out.push(path);
  }
  return out;
}

const failures = [];
let scanned = 0;
for (const app of APPS) {
  for (const path of sources(join(ROOT, app, "src"))) {
    scanned += 1;
    readFileSync(path, "utf8")
      .split("\n")
      .forEach((line, index) => {
        if (OSCILLATOR.test(line)) failures.push(`${relative(ROOT, path)}:${index + 1} — نغمةٌ مركّبة: ${line.trim().slice(0, 90)}`);
      });
  }
}

let files = 0;
for (const app of SOUNDED) {
  const module = join(ROOT, app, "src", "lib", "sound.ts");
  if (!existsSync(module)) {
    failures.push(`${app}: لا \`src/lib/sound.ts\` — أين تُعزف الأصوات؟`);
    continue;
  }
  const text = readFileSync(module, "utf8");
  const table = text.match(/const FILES: Record<Cue, string> = \{([\s\S]*?)\n\};/);
  if (!table) {
    failures.push(`${app}: \`FILES\` ليس \`Record<Cue, string>\` كاملاً — صوتٌ بلا ملفٍّ يُبنى بلا شكوى`);
    continue;
  }
  for (const [, file] of table[1].matchAll(/"(sounds\/[^"]+)"/g)) {
    files += 1;
    if (!existsSync(join(ROOT, app, "public", file))) failures.push(`${app}: \`${file}\` في \`FILES\` وليس في \`public/\``);
  }
}

if (scanned === 0 || files === 0) failures.push(`لم يُقرأ شيء (${scanned} ملفّ شيفرة · ${files} صوت) — صفرٌ مقروءٌ سقوطٌ لا سلامة`);

if (failures.length) {
  console.error(`✗ check:sounds — ${failures.length}`);
  for (const line of failures) console.error(`  ${line}`);
  process.exit(1);
}
console.log(`✓ check:sounds — لا مذبذبَ في ${scanned} ملفّاً، و${files} صوتاً في جدولي التطبيقين كلُّها ملفّاتٌ موجودة.`);
