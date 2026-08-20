/** **البند ٤: حقلٌ يُحسب ولا يقرؤه أحد.**
 *
 * **وقع مقيساً في 2026-08-20**: `lib/shrink.ts` يعيد `before` و`after`
 * و`changed` منذ بُني، **ويرميها المُنادِيان كلاهما** — فلا شاشةَ تعرض شيئاً،
 * **وتوثيقُ الحقل نفسِه يَعِد بعرضه** («يُعرض للكبتن فيرى ما وقع»).
 *
 * **وما يجعله صامتاً أن الميزةَ تعمل**: الملفُّ يصغر فعلاً ويُرفع فعلاً، ولا
 * `tsc` ولا حارسٌ من العشرة يرى حقلاً محسوباً لا يقرؤه أحد. وهو «بابٌ بلا زرّ»
 * في ثوبِ حقل.
 *
 * **ونطاقُه `src/lib/` وحدَه، وهذا تضييقٌ مقصود.** `api/types.ts` مرايا
 * الخلفية — حقلٌ لا يُقرأ فيها **صحيحٌ** (التطبيقُ يضيّق ما ينشره الخادم)،
 * ويحرسه `check:config` من الجهة الأخرى. و`components/` خصائصُ مكوّناتٍ يقرؤها
 * JSX بأشكالٍ يصعب تتبّعُها. **أمّا `lib/` فمنطقٌ خالص: ما يُحسب فيه ولا يُقرأ
 * خارجه عملٌ لا ثمرةَ له.**
 *
 * **ولا يبلّغ عمّا يُقرأ بأيِّ شكل**: `x.field` أو `{ field }` أو `["field"]`
 * أو مفتاحٌ في نوعٍ آخر — **والشكُّ يُفسَّر لصالح السكوت**، لأن حارساً يصيح على
 * سليمٍ يُطفأ فيسقط معه ما يمسكه حقاً (قرارُ المالك 2026-08-20).
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, sep } from "node:path";
import { argv, exit } from "node:process";
import { createRequire } from "node:module";

const require = createRequire(new URL("../admin-panel/package.json", import.meta.url));
const ts = require("typescript");

const APPS = argv.slice(2);
if (APPS.length === 0) {
  console.error("استعمال: node tools/check-readers.mjs <app> [app…]");
  exit(2);
}

/** أسماءٌ لا يُبلَّغ عنها: شائعةٌ جداً فقراءتُها في مكانٍ ما شبهُ مؤكدة. */
const COMMON = new Set(["id", "name", "type", "value", "label", "key"]);

/** ما يُسلَّم **جملةً** إلى مكتبةٍ خارجية — قارئُه خارج شجرتنا فلا نراه.
 *
 * **والاستثناءُ يحمل علّتَه نصّاً** كما في `UI_UNIONS` و`DELIBERATE`: قائمةٌ
 * يُضاف إليها بلا سببٍ تصير قائمةَ أعذار، ثم لا يُقلَّم منها شيء.
 */
const PASSED_WHOLE = {
  FirebaseWebConfig:
    "يُسلَّم كما هو إلى `initializeApp` — Firebase يقرأ حقولَه، لا نحن",
};

/** **فاصلُ المسار يختلف بين ويندوز ولينكس** — وتعبيرٌ يفترض `/` وحدَه يجعل
 *  الحارسَ يمرّ على **لا شيء** على ويندوز فيصمت صمتَ السليم. وقد وقع مقيساً
 *  أثناء بنائه: صمت على العطب الذي بُني له، لا لأن العطب غاب بل لأنه لم يقرأ
 *  ملفاً واحداً. **وصمتٌ سببُه ألّا شيءَ قِيس ليس صمتَ سلامة.**
 */
function isLib(file) {
  return file.split(sep).includes("lib");
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

const findings = [];
/** **كم ملفَّ `lib/` قُرئ** — وصفرٌ عطبٌ لا سلامة (قاعدةُ المِسبار ٥). */
let scannedLib = 0;
for (const app of APPS) {
  const files = walk(`${ROOT}${app}/src`);
  const parsed = new Map(
    files.map((f) => [
      f,
      ts.createSourceFile(f, readFileSync(f, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX),
    ]),
  );

  /** كلُّ ما **يُقرأ فعلاً** في التطبيق — من الشجرة لا من النصّ.
   *
   * **والنصُّ هو ما أعمى النسخةَ الأولى**: `before` و`after` كلماتٌ شائعة،
   * فأيُّ ورودٍ لها في أيِّ ملفٍّ كان يُحسب قراءةً — فمرّ الحارسُ على العطب
   * الذي بُني له. والشجرةُ تفرّق بين `x.before` (قراءة) و`before:` في كائنٍ
   * يُنشأ (كتابة) و«before» في نصٍّ (لا شيء).
   */
  const readNames = new Set();
  for (const [file, source] of parsed) {
    const collect = (node) => {
      // `x.field`
      if (ts.isPropertyAccessExpression(node)) readNames.add(node.name.getText());
      // `x["field"]`
      if (ts.isElementAccessExpression(node) && node.argumentExpression &&
          ts.isStringLiteral(node.argumentExpression))
        readNames.add(node.argumentExpression.text);
      // `const { field } = …` — تفكيكٌ، وهو قراءةٌ كاملة
      if (ts.isObjectBindingPattern(node))
        for (const element of node.elements)
          readNames.add((element.propertyName ?? element.name).getText());
      ts.forEachChild(node, collect);
    };
    // **وتُجمع من كل الملفات بما فيها `lib/`** — وهذا صُحِّح أثناء البناء:
    // استثناءُ ملفِّ التعريف يبدو صواباً («لا يشهد لنفسه») وهو خطأ، لأن
    // المُنسِّقَ الذي يقرأ الحقولَ يعيش مع تعريفها بحكم «بيتٌ واحد» — فاستثناؤه
    // يبلّغ عن حقولٍ لها قارئٌ صحيح. **والسؤالُ هو: أيقرؤها أحدٌ أصلاً؟**
    collect(source);
  }

  for (const [file, source] of parsed) {
    if (isLib(file)) {
      scannedLib += 1;
    const visit = (node) => {
      if (
        ts.isInterfaceDeclaration(node) &&
        node.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword) &&
        !(node.name.getText() in PASSED_WHOLE)
      ) {
        const fields = node.members
          .filter((m) => ts.isPropertySignature(m) && m.name)
          .map((m) => ({ node: m, name: m.name.getText() }))
          .filter((f) => !COMMON.has(f.name));
        const unread = fields.filter((f) => !readNames.has(f.name));

        // **يُبلَّغ عن المنسيِّ لا عن المُمرَّر جملةً** — والفرقُ هو كلُّ الفرق:
        // كائنٌ **لا يُقرأ منه شيء** يُسلَّم كما هو إلى مكتبة (`initializeApp`
        // يبتلع `FirebaseWebConfig` كلَّه)، وقارئُه موجودٌ خارج شجرتِنا.
        // وكائنٌ **تُقرأ بعضُ حقوله ويُهمل بعضُها** هو الشكلُ الحقيقيّ: مُنادٍ
        // أخذ ما يريد ونسي الباقي — وهو عطبُ `ShrinkResult` بحرفه (`file`
        // يُقرأ، و`before`/`after`/`changed` تُرمى).
        //
        // **والتضييقُ مقصودٌ لا كسل**: حارسٌ يصيح على سليمٍ يُطفأ، فيسقط معه
        // ما يمسكه حقاً (قرارُ المالك 2026-08-20).
        if (unread.length > 0 && unread.length < fields.length) {
          for (const f of unread) {
            const { line } = source.getLineAndCharacterOfPosition(f.node.getStart());
            findings.push({ file, line: line + 1, iface: node.name.getText(), field: f.name });
          }
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
    }
  }
}

if (findings.length > 0) {
  if (findings.length > 0) {
    console.error("");
    console.error("حقولٌ تُحسب في `lib/` ولا يقرؤها أحد:");
    console.error("");
    for (const f of findings)
      console.error(`  ${f.file}:${f.line}  ${f.iface}.${f.field}`);
  }
  console.error("");
  console.error("  إمّا أن تُقرأ — شاشةٌ تعرضها أو منطقٌ يقرّر بها — وإمّا أن تُحذف.");
  console.error("  **وحقلٌ يَعِد توثيقُه بعرضه ولا يُعرض هو الأسوأ**: الميزةُ تعمل،");
  console.error("  ولا شيءَ يفشل، والغائبُ هو الخبرُ وحدَه.");
  exit(1);
}
if (scannedLib === 0) {
  console.error("");
  console.error("✗ لم يُقرأ ملفُّ `lib/` واحد — وحارسٌ لا يقرأ شيئاً يمرّ أخضرَ أبداً.");
  console.error("  (وقع مقيساً 2026-08-20: فحصُ المسار افترض `/` فاصلاً فلم يطابق ويندوز.)");
  exit(1);
}
console.log(
  `✓ كل حقلٍ مُصدَّرٍ في \`lib/\` له قارئ — قُرئ ${scannedLib} ملفَّ \`lib/\` (${APPS.join("، ")})`,
);
