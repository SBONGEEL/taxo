/** **البند ٥: مبلغٌ يُمرَّر بعلامته المحلولة مرتين، فيُطبع عارياً.**
 *
 * **الشكل**: `money(value, currency)` يحلّ العلامةَ بنفسه
 * (`currencyLabel(currency)`). فمن ناداه بعلامةٍ محلولةٍ سلفاً —
 * `money(row.amount, currencyLabel(row.currency))` — يمرّر «د.أ» إلى دالةٍ
 * تبحث عن «د.أ» في جدولِ رموزِ العملات، فلا تجده. وفي اللوحة الافتراضُ
 * `?? ""`، **فيُطبع الرقمُ بلا عملة**: «٠٫٧٥٠ » بمسافةٍ زائدة.
 *
 * **ولا شيءَ آخرَ يراه**: الأنواعُ صحيحةٌ تماماً (`Currency | string`)،
 * والدالّةُ تُنادى بوسيطين كما يجب، والناتجُ نصٌّ سليمُ الشكل. **ولا تفرّق
 * العينُ في لقطةِ شاشة** بين «د.أ» وغيابها في ذلك الحجم — ولذلك يُقرأ من
 * DOM لا من صورة.
 *
 * **وقد شُحن مرتين**: عمودان في `components/Advances.tsx` منذ البند ١٥، ثم
 * نُسخا إلى جدولِ رسوم الإلغاء. **وظهر ثالثةً في ٢٠٢٦-٠٨-٢٠** في تعليلِ درسٍ
 * قبل أن يُبنى حارسُه — وهو ما قدّمه على غيره.
 *
 * **وما لا يُبلَّغ عنه عمداً**: `money(value)` بلا عملةٍ أصلاً. أحياناً
 * تُكتب العملةُ في رأس العمود مرةً واحدة، فالتبليغُ عنه يصيح على كودٍ سليم —
 * **وحارسٌ يصيح على السليم يُطفأ**، فيسقط معه ما يمسكه حقاً.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { argv, exit } from "node:process";
import { createRequire } from "node:module";

// **من `node_modules` التطبيق لا من الجذر** — كما يفعل `check-slot`: الجذرُ لا
// `node_modules` له، والمُحلِّلُ نسخةُ التطبيق نفسِها التي يُبنى بها
const require = createRequire(new URL("../admin-panel/package.json", import.meta.url));
const ts = require("typescript");

/** مُنسِّقاتُ المال في التطبيقات الثلاثة — كلُّها تحلّ العلامةَ بنفسها. */
const FORMATTERS = new Set(["money", "formatMoney"]);
/** ما يعيد **علامةً محلولة** — تمريرُه إلى ما فوق هو العطب. */
const RESOLVERS = new Set(["currencyLabel", "CURRENCY_LABEL"]);

const APPS = argv.slice(2);
if (APPS.length === 0) {
  console.error("استعمال: node tools/check-money.mjs <app> [app…]");
  exit(2);
}

/** جذرُ المستودع من موضع هذا الملف — **لا من مجلد العمل**.
 *
 * قِيس أثناء الإدراج في البناء: `npm run` يجعل مجلدَ العمل مجلدَ التطبيق،
 * فمسارٌ نسبيٌّ يصير `driver-app/driver-app/src` ويسقط بـENOENT. و`check:served`
 * سلم لأنه يشتقّ من `import.meta.url` منذ كُتب.
 */
const ROOT = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    if (entry === "node_modules" || entry === "dist") return [];
    const path = join(dir, entry);
    return statSync(path).isDirectory()
      ? walk(path)
      : /\.tsx?$/.test(entry)
        ? [path]
        : [];
  });
}

/** أهذا التعبيرُ علامةٌ محلولة؟ — نداءٌ لمُحلِّل، أو قراءةٌ من جدوله. */
function resolvesALabel(node) {
  if (ts.isCallExpression(node) && ts.isIdentifier(node.expression))
    return RESOLVERS.has(node.expression.text);
  // `CURRENCY_LABEL[x]` — الشكلُ نفسُه بلا دالّة
  if (ts.isElementAccessExpression(node) && ts.isIdentifier(node.expression))
    return RESOLVERS.has(node.expression.text);
  return false;
}

const findings = [];
/** **كم ملفاً قُرئ** — وصفرٌ عطبٌ لا سلامة (قاعدةُ المِسبار ٥). */
let scanned = 0;
for (const app of APPS) {
  const root = `${ROOT}${app}/src`;
  for (const file of walk(root)) {
    scanned += 1;
    const source = ts.createSourceFile(
      file,
      readFileSync(file, "utf8"),
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    const visit = (node) => {
      if (
        ts.isCallExpression(node) &&
        ts.isIdentifier(node.expression) &&
        FORMATTERS.has(node.expression.text)
      ) {
        for (const arg of node.arguments) {
          if (resolvesALabel(arg)) {
            const { line } = source.getLineAndCharacterOfPosition(arg.getStart());
            findings.push({
              file,
              line: line + 1,
              call: node.expression.text,
              text: arg.getText().slice(0, 60),
            });
          }
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
}

if (findings.length > 0) {
  console.error("\nمبلغٌ يُمرَّر بعلامةٍ محلولةٍ سلفاً — فتُحلَّل مرةً ثانيةً ويُطبع عارياً:\n");
  for (const f of findings)
    console.error(`  ${f.file}:${f.line}  ${f.call}(…, ${f.text})`);
  console.error(
    [
      "",
      "  مرِّر **رمزَ العملة** كما وصل من الخلفية، لا علامتَه المعروضة:",
      "    ✗ money(row.amount, currencyLabel(row.currency))",
      "    ✓ money(row.amount, row.currency)",
      "",
      "  والمُنسِّقُ يحلّ العلامةَ بنفسه — وتمريرُها محلولةً يجعله يبحث عن «د.أ»",
      "  في جدولِ الرموز فلا يجده، فيُطبع الرقمُ بلا عملة.",
    ].join("\n"),
  );
  exit(1);
}
if (scanned === 0) {
  console.error("");
  console.error("✗ لم يُقرأ ملفٌ واحد — وحارسٌ لا يقرأ شيئاً يمرّ أخضرَ أبداً.");
  exit(1);
}
console.log(
  `✓ كل مبلغٍ يُمرَّر برمز عملته لا بعلامتها — قُرئ ${scanned} ملفاً (${APPS.join("، ")})`,
);
