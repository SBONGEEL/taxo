/** حارسٌ ضد الاتحاد المكتوب في الواجهة بدل نسخه من الخلفية.
 *
 * وقع هذا مرتين: `awaiting_confirmation` في `PaymentStatus` — حالٌ لا وجود لها
 * في `app/models/enums.py` — فبنت عليها ثلاث شاشات، ولم يستطع كبتنٌ تأكيد
 * دفعة كاش؛ و`mixed` في `PaymentMethod` — قناةٌ لا يرسلها المزود قط، والدفعُ
 * المختلط **صفّان** لا قناة. والبناءُ أخضر في الحالتين: السلسلة عضوٌ صحيح في
 * اتحادٍ أعلنه التطبيق نفسه، فلا TypeScript يعترض ولا الاختبارات ترى واجهة.
 *
 * فيقرأ هذا السكربت أعضاء كل `StrEnum` في الخلفية، ثم كل اتحادِ سلاسلَ في
 * `src`، ويرفض ما خلط قيمةً من تعدادٍ بقيمةٍ لا وجود لها فيه — وتلك بالضبط
 * بصمةُ الاتحاد المنسوخ ثم المزيد عليه.
 *
 * يعمل ضمن `npm run build` قبل `tsc`.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const BACKEND = join(process.cwd(), "..", "backend", "app");
const SRC = join(process.cwd(), "src");

/** اتحاداتُ واجهةٍ خالصة تشترك في أسماءٍ مع تعدادات الخلفية بالمصادفة.
 *  كلُّ إعفاءٍ هنا يذكر لماذا هو اتحادُ عرضٍ لا مرآةُ عقد. */
const UI_UNIONS = new Set([
  // حالُ الاشتراك الأربع تُشتق في `Subscription.tsx::stateOf` من
  // `is_active` و`days_remaining` و`coverage_until` — لا عمودَ لها
  "State",
]);

/** يمحو تعليقات `/* *\/` و`//` ويترك ما عداها بطوله.
 *
 * لا يفهم السلاسل، فـ`"// ليس تعليقاً"` داخل نصٍّ يُمحى خطأً — وهو مقبولٌ هنا:
 * الضررُ الوحيد أن يفحص الحارس اتحاداً بعضوٍ ناقص، لا أن يتخطّى اتحاداً.
 * والخطأُ في هذا الاتجاه هو الاتجاه الصحيح للخطأ في حارس.
 */
function stripComments(text) {
  const block = /\/\*[\s\S]*?\*\//g;
  const line = new RegExp("//[^\n]*", "g");
  return text.replace(block, " ").replace(line, " ");
}

function walk(dir, test) {
  return readdirSync(dir).flatMap((entry) => {
    if (entry === "__pycache__" || entry === "node_modules") return [];
    const path = join(dir, entry);
    return statSync(path).isDirectory()
      ? walk(path, test)
      : test(path)
        ? [path]
        : [];
  });
}

// ------------------------------------------------------------- الخلفية
const enumValues = new Set();
for (const file of walk(BACKEND, (p) => p.endsWith(".py"))) {
  const text = readFileSync(file, "utf8");
  for (const member of text.matchAll(/^\s{4}[A-Z_0-9]+\s*=\s*"([^"]+)"/gm)) {
    enumValues.add(member[1]);
  }
  // أسماءُ الأحداث المبثوثة عقدٌ كذلك وإن لم تكن تعداداً في كل موضع
  for (const event of text.matchAll(/"type":\s*"([a-z_]+)"/g)) {
    enumValues.add(event[1]);
  }
}

// ------------------------------------------------------------- الواجهة
const problems = [];
for (const file of walk(SRC, (p) => /\.tsx?$/.test(p))) {
  // **التعليقات تُحذف قبل المطابقة.** النمطُ أدناه يقبل سلاسلَ وأنابيبَ فقط،
  // فتعليقٌ بين أعضاء الاتحاد يجعله لا يطابق — فيمر الاتحادُ **بلا فحص**
  // والبناءُ أخضر. وقع هذا فعلاً في `AuditAction` بلوحة الإدارة: شرحُ
  // `read` كُتب بين العضوين فتوقّف الحارس عن رؤية الاتحاد كله، ولا شيء
  // يقول ذلك. حارسٌ يُتخطّى بصمتٍ أسوأ من حارسٍ غائب — الغائبُ يُعرف.
  const text = stripComments(readFileSync(file, "utf8"));
  for (const match of text.matchAll(
    /type\s+(\w+)\s*=\s*((?:\s*\|?\s*"[^"]+")+)\s*;/g,
  )) {
    const [, name, body] = match;
    if (UI_UNIONS.has(name)) continue;
    const members = [...body.matchAll(/"([^"]+)"/g)].map((m) => m[1]);
    if (members.length < 2) continue;
    const known = members.filter((value) => enumValues.has(value));
    const strays = members.filter((value) => !enumValues.has(value));
    // اتحادٌ **بعضُه** من الخلفية وبعضُه لا: منسوخٌ ثم زِيد عليه
    if (known.length > 0 && strays.length > 0) {
      problems.push(
        `${file.replace(process.cwd(), ".")}: ${name} — ${strays.join(", ")}`,
      );
    }
  }
}

if (problems.length > 0) {
  console.error("اتحاداتٌ فيها قيمٌ لا يعرفها أيُّ تعدادٍ في الخلفية:\n");
  for (const problem of [...new Set(problems)]) console.error("  " + problem);
  console.error(
    "\nانسخ القيم من `backend/app/models/enums.py` كما هي." +
      " وإن كان اتحادَ عرضٍ لا مرآةَ عقد، أضف اسمه إلى `UI_UNIONS` بسببه.",
  );
  process.exit(1);
}
console.log("✓ كل اتحادات السلاسل تطابق تعدادات الخلفية");
