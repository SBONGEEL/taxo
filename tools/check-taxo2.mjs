/** `check:taxo2` — **نظامُ تصميم TAXO 2.0 منسوخٌ في كلِّ تطبيق، فيُقاس بايتاً** (SPEC §61-ج).
 *
 * `src/taxo2/` في تطبيقي الراكب والكبتن **ملفّاتٌ واحدةٌ نسختين لا استيراد** — بعلّة بوّابة التحديث نفسِها: كلُّ تطبيقٍ
 * شجرةٌ تُبنى وحدَها، **واستيرادُ مكوّنٍ من خارج الشجرة يجرّ بناءً ثانياً إلى داخل الأول**.
 *
 * **والنسخُ بلا حارسٍ تفترق أوّلَ تعديل — والافتراقُ هنا لا يُسقط شيئاً**: البناءُ أخضر، **والتطبيقان يرسمان «الجمر» بلونين**
 * أو «الشارة» بمقاسين — وهو عينُ ما وُجد نظامُ التصميم ليمنعه: هويةٌ واحدةٌ تُرى بوجهين.
 *
 * **فيقيس أمرين**: أن **مجموعةَ الملفّات واحدة** (ملفٌّ في نسخةٍ دون الأخرى افتراق)، وأن **كلَّ ملفٍّ متطابق** بعد تطبيع
 * نهايات الأسطر (`driver-app` محفوظٌ بـCRLF أحياناً، **وفرقُ نهايةِ سطرٍ ليس افتراقاً في الشكل**).
 *
 * **وحدُّه مكتوب**: يقيس **التطابق** لا **الصحّة** — من عدّل النسختين بالخطأ نفسِه يمرّ؛ وما يضمنه أن **الافتراقَ لا يمرّ صامتاً**.
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { certify } from "./certify.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const APPS = ["customer-app", "driver-app"];
const REL = join("src", "taxo2");

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...walk(path));
    else out.push(path);
  }
  return out;
}

const copies = [];
for (const app of APPS) {
  const dir = join(ROOT, app, REL);
  if (!existsSync(dir)) {
    console.error(`\n✗ نسخةٌ مفقودة: ${app}/${REL.replace(/\\/g, "/")}`);
    console.error("  **والغيابُ ليس تطابقاً**: تطبيقٌ بلا نظام التصميم يرسم الهويةَ من عنده.");
    process.exit(1);
  }
  const files = new Map();
  for (const path of walk(dir)) {
    const rel = relative(dir, path).replace(/\\/g, "/");
    const text = readFileSync(path, "utf8").replace(/\r\n/g, "\n");
    files.set(rel, createHash("sha256").update(text).digest("hex"));
  }
  copies.push({ app, files });
}

const [a, b] = copies;
const names = new Set([...a.files.keys(), ...b.files.keys()]);
const problems = [];
for (const name of [...names].sort()) {
  const da = a.files.get(name);
  const db = b.files.get(name);
  if (!da) problems.push(`  ${name} — في ${b.app} وحدَه`);
  else if (!db) problems.push(`  ${name} — في ${a.app} وحدَه`);
  else if (da !== db) problems.push(`  ${name} — افترق (${da.slice(0, 10)}… ≠ ${db.slice(0, 10)}…)`);
}

if (problems.length) {
  console.error("\n✗ نسختا نظام التصميم افترقتا — والافتراقُ لا يُسقط بناءً:");
  for (const line of problems) console.error(line);
  console.error("");
  console.error("  انسخ الملفَّ الصحيحَ على الآخر في الإيداع نفسِه. **وهويةٌ تُرى بوجهين**");
  console.error("  **هي ما وُجد نظامُ التصميم ليمنعه.**");
  process.exit(1);
}

const all = createHash("sha256")
  .update([...a.files.entries()].sort().map(([k, v]) => `${k}:${v}`).join("\n"))
  .digest("hex");
certify("check:taxo2", `✓ نظامُ التصميم متطابقٌ في التطبيقين — ${a.files.size} ملفّات (${all.slice(0, 12)})`);
