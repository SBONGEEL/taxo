/** **بابٌ بلا زرّ — في وجهه الثاني**: مسارٌ مسمّىً في `api/endpoints.ts` لا
 * يستعمله أحد.
 *
 * `check:doors` يسأل السؤالَ من جهة الخلفية: «مسارٌ إداريٌّ بلا مُنادٍ». وهذا
 * يسأله **من جهة العميل**: دالّةٌ مُصدَّرةٌ تُعلن باباً **ولا زرَّ يطرقه**.
 * والشكلُ واحدٌ والثمنُ واحد — وقد كلّف هذا المشروعَ مرّتين مقيستين:
 * `/drivers/nearby` مُصرَّحاً ولا ينادِيه أحدٌ **فبقيت خريطةُ الراكب فارغةً
 * أسابيع**، ومسارا الحضور البديلان اللذان يقول تعليقُهما نفسُه إنهما «مبنيّان
 * ومختبَران ولا ينادِيهما أحد».
 *
 * **والتصريحُ ليس استعمالاً** — وهي قاعدةُ `check:doors` بعينها: وجودُ الاسم
 * في `endpoints.ts` يقول إن أحداً كتبه، لا إن أحداً يطرقه.
 *
 * **وكلُّ استثناءٍ يحمل علّتَه نصّاً، واستثناءٌ صار له مستعملٌ يفشل البناء** —
 * فقائمةُ أعذارٍ لا تُنظَّف تصير كذباً.
 */

import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { argv, exit } from "node:process";
import { certify } from "./certify.mjs";

const app = argv[2];
if (!app) {
  console.error("الاستعمال: node tools/check-client-doors.mjs <customer-app|driver-app>");
  exit(2);
}

// **الجذرُ يُشتقّ من موضع الملفّ لا من مجلد التشغيل**: `npm run build` يشتغل
// **داخل مجلد التطبيق**، فمسارٌ نسبيٌّ يتضاعف (`driver-app/driver-app/…`).
// وهو الفخُّ الذي أسقط أوّلَ تشغيلٍ لهذا الحارس في البناء.
const ROOT = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
process.chdir(ROOT);

/** ما لا يُعدّ باباً بلا زرّ — **والعلّةُ نصٌّ يُقرأ لا مجرّدُ وجودٍ في قائمة**. */
const DELIBERATE = {
  CLIENT_APP:
    "ليس مساراً بل ثابتٌ يُرسَل ترويسةً — يُقرأ داخل `endpoints.ts` نفسِه (`app_scope`).",
  getAuthMethod:
    "بابٌ ثانٍ لِما ينشره `GET /config` — والتطبيقان يقرآن القناةَ من " +
    "`countries[].verification`، فهذا احتياطٌ لا واجهةَ له. **يُحذف أو يُوصَل**، " +
    "وبقاؤه مصرَّحاً بلا قرارٍ هو ما يجعله بنداً في `HANDOFF` لا استثناءً دائماً.",
  simulateMockCard:
    "بابُ محاكي البطاقة — يُطرق يدوياً في قياسٍ لا من شاشة، ووصلُه بزرٍّ " +
    "يضع في تطبيقِ راكبٍ زرّاً يُنهي دفعةً بلا مال.",
};

const src = readFileSync(`${app}/src/api/endpoints.ts`, "utf8");
const exported = [
  ...src.matchAll(/^export (?:const|(?:async )?function) ([A-Za-z0-9_]+)/gm),
].map((m) => m[1]);

if (exported.length === 0) {
  console.error(`✗ لم يُقرأ مسارٌ واحدٌ من ${app}/src/api/endpoints.ts — **صفرٌ مقروءٌ عطبٌ لا سلامة**.`);
  exit(1);
}

/** يُقرأ الاستعمالُ من الشجرة كلِّها **عدا ملفِّ التصريح** — فالتصريحُ ليس استعمالاً. */
function used(name) {
  try {
    const out = execFileSync(
      "git",
      ["grep", "-l", "-w", name, "--", `${app}/src`, `:!${app}/src/api/endpoints.ts`],
      { encoding: "utf8" },
    );
    return out.trim().length > 0;
  } catch {
    return false; // `git grep` يخرج ١ حين لا يجد
  }
}

const orphans = [];
const staleExemptions = [];
for (const name of exported) {
  const hasUser = used(name);
  if (!hasUser && !(name in DELIBERATE)) orphans.push(name);
  if (hasUser && name in DELIBERATE) staleExemptions.push(name);
}

console.log(`  قُرئ ${exported.length} مساراً مُصدَّراً في ${app}`);

let bad = 0;
if (orphans.length) {
  bad = 1;
  console.error(`\n✗ ${orphans.length} باباً بلا زرّ — مُصرَّحٌ ولا يطرقه أحد:`);
  for (const n of orphans) console.error(`    ${n}`);
  console.error("\n  يُوصَل بزرّ، أو يُحذف، أو يُدرَج في `DELIBERATE` **بعلّته نصّاً**.");
}
if (staleExemptions.length) {
  bad = 1;
  console.error(`\n✗ ${staleExemptions.length} استثناءً صار له مستعملٌ — يُنظَّف:`);
  for (const n of staleExemptions) console.error(`    ${n}`);
  console.error("\n  **قائمةُ أعذارٍ لا تُنظَّف تصير كذباً** — ويُقرأ سكوتُها ضماناً.");
}
if (bad) exit(1);

certify("check:client-doors", `✓ كلُّ مسارٍ مُصرَّحٍ له زرٌّ — و${Object.keys(DELIBERATE).length} استثناءاتٍ بعللها`);
