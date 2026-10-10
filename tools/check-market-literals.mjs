/** **سوقٌ ثالثٌ يُرسم بعملة سوقٍ آخر ولا يفشل شيء** (SPEC §٧٣-ج/١٢).
 *
 * **الشكل**: شرطٌ بدولتين في واجهة — `country === "JO" ? "JOD" : "LYD"` — صحيحٌ ما دام في المنصّة سوقان، **ويكذب بصمتٍ يومَ
 * يُضاف ثالث**: قِيس على الشجرة قبل الجزائر فوُجد في **اثني عشر موضعاً** في الثلاث (اللوحةُ تعرض الجزائرَ «د.ل»، والتطبيقان
 * يعرضان للجزائريّ «د.أ»، واختيارُ اللوحة المحفوظُ يقبل `JO|LY` فيضيع اختيارُ الجزائر عند كلِّ تحديث). **ولا شيءَ آخرَ يراه**:
 * الأنواعُ صحيحة، والفرعُ الثاني فرعٌ صالح، والشاشةُ تُرسم كاملة.
 *
 * **وما يمسكه** (بمُحلِّل TypeScript لا بالنصّ، فلا تصيح التعليقاتُ ولا الأنواع):
 * 1. **مقارنةٌ برمز دولةٍ أو عملة** — `===` · `!==` · `==` · `!=` وأحدُ طرفيها `"JO"` · `"LY"` · `"DZ"` · `"JOD"` · `"LYD"` · `"DZD"`.
 *    **والعملةُ وعلامتُها وخاناتُها من `/config`** (`currency` · `currency_label` · `currency_decimals`) لا من شرط.
 * 2. **`"0.000"` نصّاً في شيفرة** — صفرٌ بخانات عملةٍ واحدة؛ والصفرُ بعملته `zeroAmount(currency)` وفحصُه `isZeroAmount(…)`.
 *
 * **وما لا يمسكه — مكتوبٌ لا مسكوتٌ عنه**: `?? "JO"` احتياطاً لدولة الحساب (مسموحٌ بنصِّ §24.3: دولةُ صاحب الحساب لا قائمةُ أسواق) ·
 * جدولاً مفتاحُه `Record<CountryCode, …>` (المترجمُ يُجبر اكتمالَه بنفسه حين يتّسع التعداد) · **ورمزاً يُقارن به عبر متغيّر**
 * (`const JO = "JO"; x === JO`) — شكلٌ لم يُقَس في الشجرة.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { argv, exit } from "node:process";
import { createRequire } from "node:module";
import { certify } from "./certify.mjs";

const APPS = argv.slice(2);
if (APPS.length === 0) {
  console.error("استعمال: node tools/check-market-literals.mjs <app> [app…]");
  exit(2);
}

/** **`typescript` من التطبيق المفحوص أوّلاً** — كما في `check-money.mjs` ولعلّته نفسِها (استنساخُ CI يثبّت حزمةً واحدة). */
function loadTypeScript(apps) {
  const tried = [];
  for (const app of apps) {
    try {
      return createRequire(new URL(`../${app}/package.json`, import.meta.url))("typescript");
    } catch {
      tried.push(app);
    }
  }
  console.error(`✗ لم يوجد \`typescript\` في أيٍّ من: ${tried.join(" · ")} — الحارسُ لا يقيس.`);
  exit(2);
}
const ts = loadTypeScript([...new Set([...APPS, "admin-panel", "customer-app", "driver-app"])]);

const ROOT = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const MARKET_CODES = new Set(["JO", "LY", "DZ", "JOD", "LYD", "DZD"]);
const EQUALITY = new Set([
  ts.SyntaxKind.EqualsEqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsToken,
]);

function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    if (entry === "node_modules" || entry === "dist") return [];
    const path = join(dir, entry);
    return statSync(path).isDirectory() ? walk(path) : /\.tsx?$/.test(entry) ? [path] : [];
  });
}

const isText = (node) => ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node);

const findings = [];
let scanned = 0;
for (const app of APPS) {
  for (const file of walk(`${ROOT}${app}/src`)) {
    scanned += 1;
    const source = ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const report = (node, why) => {
      const { line } = source.getLineAndCharacterOfPosition(node.getStart());
      findings.push(`  ${file.replace(ROOT, "")}:${line + 1}  ${why}  ${node.getText().slice(0, 70)}`);
    };
    const visit = (node) => {
      if (ts.isBinaryExpression(node) && EQUALITY.has(node.operatorToken.kind)) {
        for (const side of [node.left, node.right]) {
          if (isText(side) && MARKET_CODES.has(side.text)) {
            report(node, "مقارنةٌ برمز سوق ←");
            break;
          }
        }
      }
      if (isText(node) && node.text === "0.000") report(node, "صفرٌ بخانات عملةٍ واحدة ←");
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
}

if (findings.length > 0) {
  console.error("\nشرطٌ بسوقٍ أو صفرٌ بخاناتٍ ثابتة في الواجهة — يصدق بسوقين ويكذب بالثالث:\n");
  for (const line of findings) console.error(line);
  console.error(
    [
      "",
      "  العملةُ وعلامتُها وخاناتُها من `/config` لا من شرط:",
      "    ✗ currencyLabel(country === \"JO\" ? \"JOD\" : \"LYD\")",
      "    ✓ currencyLabel(currencyOf(country))          // اللوحة",
      "    ✓ useCountryConfig(user?.country_code)?.currency  // التطبيقان",
      "  والصفرُ بعملته:  zeroAmount(currency) · isZeroAmount(amount)",
    ].join("\n"),
  );
  exit(1);
}
if (scanned === 0) {
  console.error("\n✗ لم يُقرأ ملفٌ واحد — وحارسٌ لا يقرأ شيئاً يمرّ أخضرَ أبداً.");
  exit(1);
}
certify(
  "check:market-literals",
  `✓ لا شرطَ بسوقٍ ولا صفرَ بخاناتٍ ثابتة — قُرئ ${scanned} ملفاً (${APPS.join("، ")})`,
);
