/** حقلٌ تنشره الخلفيةُ وله مرآةٌ **ولا قارئَ له في أيِّ سطح**.
 *
 * **الشرطُ ثلاثيّ** (قرارُ المالك 2026-08-23)، وكلُّه لازم:
 *   ١. تنشره الخلفيةُ في مخطَّطٍ مُعلَن،
 *   ٢. وله مرآةٌ في `api/types.ts` لأحد التطبيقات،
 *   ٣. **ولا يقرؤه سطرٌ في أيِّ من الثلاثة** خارج ملفِّ المرايا نفسِه.
 *
 * **العطبُ الذي وُجد له، مرّتين**: `RideStop.address` تنشره الخلفيةُ ولها
 * مرآةٌ في تطبيق الكبتن **ولا يقرؤها سطرٌ فيه** — فكان يقود إلى محطةٍ لا
 * يعرف أين هي؛ و`waited_minutes` لا قارئَ لها في أيِّ سطح.
 *
 * **ولا يراه حارسٌ قائم**: `tsc` يرى نوعاً صحيحاً، و`check:config` يسأل عن
 * **مرآة** لا عن **قارئ**، و`check:readers` يمسح `lib/` وحدَها.
 *
 * **وضيّقٌ عمداً — والصيغةُ العامّة قِيست فسقطت**: «كلُّ حقلِ مرآةٍ له قارئ»
 * تُبلّغ عن **٢١٤ حقلاً** على شجرةٍ سليمة (٧٤ + ٧٤ + ٦٦)، فتسقط في اختبار
 * «يصمت على السليم» — **وحارسٌ يصيح على مئتين يُطفأ في أسبوع**، فيسقط معه ما
 * يمسكه حقاً. فالقائمةُ **مُعلَنةٌ نوعاً نوعاً**، ويبدأها `RideStop` وحدَه.
 *
 * **والفجوةُ المقصودةُ تُكتب بعلّتها** كما يفعل `check:doors` — وقائمةُ أعذارٍ
 * لا تُنظَّف تصير كذباً، فالمُدرَجُ الذي صار له قارئٌ **يُبلَّغ عنه** أيضاً.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { certify } from "./certify.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

/** الأنواعُ المشمولة — **مُعلَنةٌ لا مستنتَجة**. توسيعُها قرارٌ يُكتب هنا. */
const WATCHED = ["RideStopOut"];

/** الأسطحُ الثلاثة: مجلَّدُ التطبيق ← اسمُ مرآته. */
const APPS = ["customer-app", "driver-app", "admin-panel"];

/** `التطبيق:النوع.الحقل` ← علّةُ غيابِ القارئ. **والمفتاحُ بالسطح لا
 *  بالنوع**: حقلٌ مقروءٌ في الكبتن وغيرُ مقروءٍ في الراكب **فجوةٌ في واحدٍ
 *  لا في الاثنين**، ومفتاحٌ عامٌّ يُسكت الحارسَ عن السطح الذي يحتاجه. */
const DELIBERATE = {
  // **وهذه الفجوةُ الوحيدةُ اليوم، وهي مقصودةٌ بقرارٍ مكتوب**: عدّادُ
  // الانتظار عند الراكب **يُرسم محلياً من `arrived_at`** — عرضُ الوقت حسابُ
  // وقت، والمبلغُ وحدَه يأتي محسوباً (§14 و`StopProgress.tsx`). **فالحقلُ
  // يخدم من يقرأ الـAPI لا شاشةَ الراكب.** وهو مقروءٌ في الكبتن واللوحة.
  "customer-app:RideStopOut.waited_minutes":
    "العدّادُ يُرسم محلياً بالثواني من `arrived_at` — وقراءةُ رقم الخلفية " +
    "**تُجمّده بين استطلاعين**، وهو عطبُ عدّاد الكبتن المُصلَح في دفعة الستّة " +
    "(طُبع `waited_minutes` فتجمّد عند «٠ دقيقة»). فالغيابُ هنا **شرطٌ لا فجوة**.",
};

function files(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === "dist") continue;
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) files(path, out);
    else if (/\.tsx?$/.test(entry)) out.push(path);
  }
  return out;
}

/** حقولُ النوع كما تنشرها الخلفية — تُقرأ من مخطَّطات Pydantic. */
function publishedFields(typeName) {
  const source = readFileSync(join(ROOT, "backend/app/schemas/ride.py"), "utf8");
  const start = source.indexOf(`class ${typeName}(`);
  if (start < 0) return null;
  const rest = source.slice(start);
  const end = rest.indexOf("\nclass ", 1);
  const body = end < 0 ? rest : rest.slice(0, end);
  const fields = [];
  for (const line of body.split("\n")) {
    const match = /^\s{4}(\w+)\s*:/.exec(line);
    if (match) fields.push(match[1]);
  }
  return fields;
}

const problems = [];
const stale = [];
let checked = 0;

for (const typeName of WATCHED) {
  const fields = publishedFields(typeName);
  if (fields === null || fields.length === 0) {
    console.error(`✗ لم يُقرأ النوعُ ${typeName} من مخطَّطات الخلفية — المسحُ أعمى.`);
    process.exit(1);
  }

  // مرآتُه في كلِّ تطبيق + قرّاؤه فيه
  for (const app of APPS) {
    const mirrorPath = join(ROOT, app, "src/api/types.ts");
    let mirror;
    try {
      mirror = readFileSync(mirrorPath, "utf8");
    } catch {
      continue;
    }
    const sources = files(join(ROOT, app, "src"))
      .filter((path) => path !== mirrorPath)
      .map((path) => readFileSync(path, "utf8"))
      .join("\n");

    for (const field of fields) {
      // **الشرطُ ٢**: له مرآةٌ في هذا التطبيق — وإلا فليس من شأنه
      if (!new RegExp(`^\\s{2}${field}\\??:`, "m").test(mirror)) continue;
      checked += 1;
      const key = `${app}:${typeName}.${field}`;
      // **الشرطُ ٣**: أيقرؤه سطرٌ خارج ملفِّ المرايا؟
      const read = new RegExp(`[.\\[\`'"]${field}\\b`).test(sources);
      if (read) {
        if (DELIBERATE[key]) stale.push(`${key} — مُدرَجٌ في الفجوات وله قارئٌ في ${app}`);
        continue;
      }
      if (DELIBERATE[key]) continue;
      problems.push(`${key} — منشورٌ وله مرآةٌ في ${app}، ولا يقرؤه سطرٌ فيه`);
    }
  }
}

// **إثباتُ الصمت**: صفرُ حقولٍ مفحوصةٍ يعني مسحاً أعمى لا شجرةً سليمة
if (checked === 0) {
  console.error("✗ لم يُفحص حقلٌ واحد — المسحُ أعمى، لا الشجرةُ سليمة.");
  process.exit(1);
}

if (stale.length > 0) {
  console.error("✗ فجواتٌ مكتوبةٌ صار لها قرّاء — تُنظَّف وإلا صارت أعذاراً:");
  for (const line of stale) console.error(`  ${line}`);
  process.exit(1);
}

if (problems.length > 0) {
  console.error("✗ حقلٌ تنشره الخلفيةُ وله مرآةٌ ولا يقرؤه أحد:");
  for (const line of problems) console.error(`  ${line}`);
  console.error(
    "  اقرأه في الشاشة التي تحتاجه، أو اكتب علّةَ غيابه في `DELIBERATE`.",
  );
  process.exit(1);
}

certify("check:published-readers", 
  `✓ كلُّ حقلٍ منشورٍ له مرآةٌ له قارئ (فُحص ${checked}، وفجواتٌ مكتوبةٌ ${Object.keys(DELIBERATE).length})`,
);
