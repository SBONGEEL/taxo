/** حارسٌ ضد «مفتاحٌ بلا زرٍّ يشعله» — العطبُ الذي تكرر ستَّ مرات في هذا المشروع.
 *
 * الحكايةُ نفسها كلَّ مرة: تُضاف قيمةٌ إلى `FeatureKey` في الخلفية، ويُبنى ما
 * تحرسه، ويُبذَر صفُّها مطفأً — **ولا يُضاف زرُّها في اللوحة**. فتشحن الميزةُ
 * كاملةً ولا سبيلَ لإشعالها إلا نداءٌ يدويٌّ على المنفذ. وقع ذلك في
 * `women_service_enabled` و`promo_codes_enabled` وغيرِهما، والقاعدةُ مكتوبةٌ في
 * `CLAUDE.md` منذ حينها — **والقاعدةُ المكتوبة لم تكفِ** (قرارُ المالك
 * 2026-08-13: «الحارس يكفي»).
 *
 * **وفحصان لا فحصٌ واحد**، لأن العطبَ يتسلّل من بابين:
 *
 * 1. **الاتحادُ ناقص** — `FeatureKey` في `api/types.ts` يفقد قيمةً موجودةً في
 *    الخلفية. و`tsc` **لا يرى النقص**: اتحادٌ أصغر صحيحٌ في نفسه، والزيادةُ
 *    وحدَها تُكسر. وحين ينقص الاتحادُ لا يمكن كتابةُ الزرِّ أصلاً.
 * 2. **القائمةُ ناقصة** — `FLAGS` في `screens/Settings.tsx` هي ما يُرسم فعلاً،
 *    وهي `FeatureKey[]`. **ومصفوفةٌ ناقصةُ عضوٍ ليست خطأً في TypeScript** — وهذه
 *    بعينُها «قيمةٌ غائبةٌ عن مصفوفةٍ لا عن اتحاد» التي تصفها `CLAUDE.md` بأنها
 *    ما لا يراه `tsc` ولا `check:enums`. أما `FLAG_LABEL` فهو
 *    `Record<FeatureKey, …>` فيحرسه المصرّفُ بنفسه — فلا يُفحص هنا مرتين.
 *
 * يعمل ضمن `npm run build` قبل `tsc`.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { certify } from "../../tools/certify.mjs";

const BACKEND_ENUMS = join(
  process.cwd(),
  "..",
  "backend",
  "app",
  "models",
  "enums.py",
);
const TYPES = join(process.cwd(), "src", "api", "types.ts");
const SETTINGS = join(process.cwd(), "src", "screens", "Settings.tsx");

/** أعضاءُ صنفِ تعدادٍ في الخلفية بقيمها النصّية. */
function backendMembers(source, className) {
  const start = source.indexOf(`class ${className}(StrEnum):`);
  if (start === -1) throw new Error(`لا تعداد ${className} في الخلفية`);
  const rest = source.slice(start + 1);
  const end = rest.search(/^class /m);
  const block = end === -1 ? rest : rest.slice(0, end);
  return [...block.matchAll(/^\s{4}[A-Z_0-9]+\s*=\s*"([^"]+)"/gm)].map(
    (m) => m[1],
  );
}

/** أعضاءُ اتحادِ سلاسلَ في الواجهة — والتعليقاتُ بينها لا تكسر المطابقة. */
function unionMembers(source, typeName) {
  const match = source.match(
    new RegExp(`export type ${typeName}\\s*=([\\s\\S]*?);`, "m"),
  );
  if (!match) throw new Error(`لا اتحاد ${typeName} في ${TYPES}`);
  return [...match[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
}

/** أعضاءُ مصفوفةٍ معلَنةٍ باسمها — وهي ما يُرسم فعلاً في الشاشة. */
function arrayMembers(source, declaration) {
  const match = source.match(
    new RegExp(`${declaration}\\s*=\\s*\\[([\\s\\S]*?)\\];`, "m"),
  );
  if (!match) throw new Error(`لا مصفوفة ${declaration} في ${SETTINGS}`);
  return [...match[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
}

const enums = readFileSync(BACKEND_ENUMS, "utf8");
const expected = backendMembers(enums, "FeatureKey");
const declared = unionMembers(readFileSync(TYPES, "utf8"), "FeatureKey");
const drawn = arrayMembers(
  readFileSync(SETTINGS, "utf8"),
  "const FLAGS: FeatureKey\\[\\]",
);

const problems = [];

const missingFromUnion = expected.filter((key) => !declared.includes(key));
if (missingFromUnion.length > 0) {
  problems.push(
    `اتحادُ \`FeatureKey\` في src/api/types.ts ينقصه: ${missingFromUnion.join(", ")}`,
  );
}

// **والزائدُ خطأٌ أيضاً**: مفتاحٌ في اللوحة لا تعرفه الخلفيةُ يرسم زرّاً يكتب
// صفّاً لا يقرؤه أحد — وهو يُقرأ «الميزةُ مشتعلة» وهي غيرُ موجودة
const strays = declared.filter((key) => !expected.includes(key));
if (strays.length > 0) {
  problems.push(
    `اتحادُ \`FeatureKey\` يحمل ما لا تعرفه الخلفية: ${strays.join(", ")}`,
  );
}

const missingFromScreen = expected.filter((key) => !drawn.includes(key));
if (missingFromScreen.length > 0) {
  problems.push(
    `مصفوفةُ \`FLAGS\` في src/screens/Settings.tsx ينقصها: ` +
      `${missingFromScreen.join(", ")} — مفتاحٌ بلا زرٍّ يشعله`,
  );
}

if (problems.length > 0) {
  console.error("مفاتيحُ ميزاتٍ لا يملك المشرفُ إشعالها من اللوحة:\n");
  for (const problem of problems) console.error("  " + problem);
  console.error(
    "\nإضافةُ `FeatureKey` عملٌ من ثلاث قطعٍ في نفس التغيير لا متابعةٌ لاحقة:" +
      "\n  ١. القيمة في `backend/app/models/enums.py`" +
      "\n  ٢. الاتحاد في `admin-panel/src/api/types.ts`" +
      "\n  ٣. الوصفُ في `FLAG_LABEL` والمفتاحُ في `FLAGS` بـ`screens/Settings.tsx`" +
      "\nومع ذلك: بذرُ الصفِّ مطفأً في `backend/scripts/seed.py`.",
  );
  process.exit(1);
}

certify("check:flags", 
  `✓ كل مفاتيح الميزات (${expected.length}) لها زرٌّ في شاشة الإعدادات`,
);
