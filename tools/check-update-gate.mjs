/** `check:update-gate` — **بوّابةُ التحديث منسوخةٌ ثلاثاً، فتُقاس بايتاً**
 *  (البند ٨، §43).
 *
 * `src/lib/update-gate.tsx` موجودٌ في التطبيقات الثلاثة **نسخاً لا استيراداً**،
 * بعلّةٍ مكتوبةٍ في رأسه: ثلاثُ شجراتٍ مستقلّةٍ لكلٍّ حزمتُها وبناؤها،
 * **واستيرادُ مكوّنٍ من خارج الشجرة يجرّ بناءً ثانياً إلى داخل الأول**.
 *
 * **ونسخٌ بلا حارسٍ يفترق أوّلَ تعديل — والافتراقُ هنا لا يُسقط شيئاً**:
 * البناءُ أخضر، والتطبيقاتُ تُقلع، **وتطبيقٌ واحدٌ يتوقّف عن سؤال الخلفية**
 * فيبقى مستعمِلوه على حزمةٍ لم تعد مدعومة **بلا أن يقول شيءٌ شيئاً**. وهو
 * أخبثُ من عطبٍ يظهر: لا شاشةَ خطأٍ ولا سطرَ سجلّ، **فقط ناسٌ عالقون على
 * نسخةٍ قديمة**.
 *
 * **وهو أخو `check:storefront-card` بحرفه** — والفرقُ أن ذاك يبصم بعد نزع
 * التعليقات، **وهذا يقارن الملفَّ كما هو**: بوّابةُ قفلٍ تعليقاتُها جزءٌ من
 * عقدها (لماذا لا تعمل في متصفّح، ولماذا لا تقفل عند سقوط الشبكة)، **ونسخةٌ
 * فقدت تعليقَها تفقد سببَ ألّا تُغيَّر**.
 *
 * **وحدُّه مكتوب**: يقيس **التطابق** لا **الصحّة**. من عدّل الثلاثةَ معاً
 * بالخطأ نفسِه يمرّ — وما يضمنه أن **الافتراقَ لا يمرّ صامتاً**.
 */

import { readFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { certify } from "./certify.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const APPS = ["customer-app", "driver-app", "admin-panel"];
// **والأنماطُ معها** (2026-10-12): نافذةُ الإلزاميِّ صارت بهوية TAXO 2.0 في ملفِّ أنماطٍ بجانبها، **وأنماطٌ تفترق نافذةٌ تفترق**
// وإن تطابق المكوّن — فيُبصم الملفّان معاً
const RELS = [join("src", "lib", "update-gate.tsx"), join("src", "lib", "update-gate.css")];

const seen = [];
for (const app of APPS) {
  const hash = createHash("sha256");
  for (const rel of RELS) {
    const path = join(ROOT, app, rel);
    if (!existsSync(path)) {
      console.error(`\n✗ نسخةٌ مفقودة: ${app}/${rel.replace(/\\/g, "/")}`);
      console.error("  **والغيابُ ليس تطابقاً**: تطبيقٌ بلا بوّابةٍ لا يسأل");
      console.error("  الخلفيةَ أبداً، ويبقى مستعمِلوه على حزمةٍ غير مدعومة.");
      process.exit(1);
    }
    // **الأسطرُ تُطبَّع قبل البصم**: `driver-app` محفوظٌ بـCRLF في هذه الشجرة،
    // **وفرقُ نهايةِ سطرٍ ليس افتراقاً في السلوك** — وحارسٌ يصيح عليه يُطفأ.
    hash.update(readFileSync(path, "utf8").replace(/\r\n/g, "\n"));
    hash.update("\0");
  }
  seen.push({ app, digest: hash.digest("hex") });
}

const unique = new Set(seen.map((one) => one.digest));
if (unique.size !== 1) {
  console.error("\n✗ نسخُ بوّابة التحديث افترقت — والافتراقُ لا يُسقط بناءً:");
  for (const one of seen) {
    console.error(`  ${one.app.padEnd(14)} ${one.digest.slice(0, 16)}…`);
  }
  console.error("");
  console.error("  انسخ الملفَّ الصحيحَ على الاثنين الآخرين، أو صحّح الثلاثة");
  console.error("  معاً. **وتطبيقٌ لا يسأل الخلفيةَ يترك ناسَه على نسخةٍ**");
  console.error("  **قديمةٍ بلا أن يقول شيءٌ شيئاً.**");
  process.exit(1);
}

certify(
  "check:update-gate",
  `✓ بوّابةُ التحديث متطابقةٌ في التطبيقات الثلاثة (${[...unique][0].slice(0, 12)})`,
);
