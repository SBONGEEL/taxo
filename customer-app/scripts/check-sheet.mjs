/** يرفض ورقةً سفليةً بلا سقفِ ارتفاعٍ أو بلا منطقةِ تمرير.
 *
 * **العطبُ الذي وُجد لأجله** (مقيسٌ على S21 وNote 20، 2026-08-23): `Sheet`
 * كانت بلا `max-height` وبلا `overflow` — **ومثبَّتةً من الأسفل** داخل صندوقٍ
 * `overflow-hidden`. فكلُّ زيادةٍ في المحتوى تخرج من **الأعلى** ويقصّها
 * الصندوق: ورقةُ التأكيد ٩١٥ بكسلاً في شاشة ٨٠٠ ⇐ **٢٠٧ مقصوصة** تحمل نقطةَ
 * الانطلاق والوجهةَ ومحرّرَ المحطات. **ولا سبيلَ إلى بلوغها بأيِّ حركة** —
 * فهي غيرُ موجودةٍ للمستخدم لا مُزاحةٌ عن نظره.
 *
 * **وعند إطارٍ ٥٢٠ يُقصّ المبلغُ نفسُه** — و٤٦٢ رقمٌ مقيسٌ في هذا المشروع
 * حين تُفتح لوحةُ المفاتيح (مسجَّلٌ في `Sheet.tsx`). أي أن «لا يختفي سطرُ
 * مالٍ أبداً» كان منقوضاً في حالةٍ قِيست سلفاً، لا في حالةٍ متخيَّلة.
 *
 * **وما جعله يمرّ**: لا صنفَ خاطئٌ ولا نوعٌ خاطئ — `tsc` أخضر، و`check:scale`
 * أخضر (كلُّ الأصناف في السلّم)، والبناءُ أخضر. العطبُ في **غياب** صنفٍ لا في
 * وجود صنفٍ خطأ، وهو ما لا يراه حارسٌ يقرأ ما هو مكتوب. وهي عائلةُ «ما لا
 * يراه البناء» نفسُها: `.scr` صنفٌ بلا تعريف، ومفتاحٌ غائبٌ عن السلّم.
 *
 * **وقاعدتُه**: كلُّ جذرِ ورقةٍ — عنصرٌ يجمع في `className` علامةَ ورقةٍ
 * (`rounded-t-24` أو `rounded-22`) مع `bg-surface` — يجب أن يحمل **سقفاً**
 * (`max-h-`) وأن يضمّ في شجرته **منطقةَ تمرير** (`scr` أو `overflow-y-auto`).
 * فالسقفُ وحدَه يقصّ، والتمريرُ وحدَه ينمو بلا حدّ.
 *
 * **والفحصُ بمحلّل TypeScript لا بتعبيرٍ نمطيّ**: الأصنافُ تُبنى بـ`cn(...)`
 * على أسطرٍ وشروط، وتعبيرٌ نمطيٌّ يقرأها سطراً سطراً يخترع عطباً على شجرةٍ
 * سليمة — وحارسٌ يخترع أغلى من حارسٍ يفوته (قاعدةُ المشروع، 2026-08-20).
 *
 * **وصمتُه يحتاج إثباتاً كما يحتاجه صياحُه**: يطبع كم ملفاً قرأ وكم ورقةً
 * فحص، **وصفرُ أوراقٍ يُقرأ عطباً لا سلامة** — فمسحٌ لا يجد شيئاً ليقيسه
 * حارسٌ لا يقرأ شيئاً، يُحسب في العدد ويُطمئن.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const SRC = new URL("../src/", import.meta.url).pathname.replace(
  /^\/([A-Za-z]:)/,
  "$1",
);

/** علامةُ جذرِ ورقة — من `DESIGN.md` §1.3: الملتصقةُ `24` والعائمةُ `22`. */
const SHEET_RADIUS = ["rounded-t-24", "rounded-22"];
const SHEET_SURFACE = "bg-surface";
const CAP = /\bmax-h-/;
const SCROLLER = /\bscr\b|\boverflow-y-auto\b/;

function files(dir) {
  const found = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) found.push(...files(path));
    else if (/\.tsx$/.test(entry)) found.push(path);
  }
  return found;
}

/** كلُّ نصٍّ حرفيٍّ داخل قيمة `className` — بما فيه ما بُني بـ`cn(...)`.
 *
 *  **ويُجمع من الشجرة لا من السطر**: `cn("a", cond ? "b" : "c")` قيمتُه
 *  الفعليةُ أحدُ الفرعين، والسقفُ في أيِّهما يكفي — فالضمُّ هو القراءةُ
 *  الصحيحة، وقراءةُ الفرع الأول وحدَه تخترع عطباً على شجرةٍ سليمة. */
function classText(attributeValue, source) {
  if (!attributeValue) return "";
  const parts = [];
  const walk = (node) => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      parts.push(node.text);
    } else if (ts.isTemplateExpression(node)) {
      parts.push(node.head.text);
      for (const span of node.templateSpans) parts.push(span.literal.text);
    }
    ts.forEachChild(node, walk);
  };
  walk(attributeValue);
  return parts.join(" ");
}

function attribute(opening, name, source) {
  for (const property of opening.attributes.properties) {
    if (!ts.isJsxAttribute(property)) continue;
    if (property.name.getText(source) !== name) continue;
    return property.initializer;
  }
  return undefined;
}

/** هل في شجرة هذا العنصر منطقةُ تمرير؟ — تُقرأ من الأبناء لا من الجذر. */
function hasScroller(node, source) {
  let found = false;
  const walk = (child) => {
    if (found) return;
    if (ts.isJsxSelfClosingElement(child) || ts.isJsxElement(child)) {
      const opening = ts.isJsxElement(child) ? child.openingElement : child;
      const text = classText(attribute(opening, "className", source), source);
      if (SCROLLER.test(text)) {
        found = true;
        return;
      }
    }
    ts.forEachChild(child, walk);
  };
  ts.forEachChild(node, walk);
  return found;
}

const problems = [];
let scanned = 0;
let sheets = 0;

for (const file of files(SRC)) {
  scanned += 1;
  const source = ts.createSourceFile(
    file,
    readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );

  const visit = (node) => {
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const opening = ts.isJsxElement(node) ? node.openingElement : node;
      const text = classText(attribute(opening, "className", source), source);
      const isSheetRoot =
        SHEET_RADIUS.some((radius) => text.includes(radius)) &&
        text.includes(SHEET_SURFACE);
      if (isSheetRoot) {
        sheets += 1;
        const line =
          source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
        const where = `${file.slice(SRC.length)}:${line}`;
        if (!CAP.test(text)) {
          problems.push(`${where} — جذرُ ورقةٍ بلا سقف (\`max-h-\`): ينمو صعوداً ويُقصّ من أعلى`);
        }
        if (!hasScroller(node, source)) {
          problems.push(`${where} — جذرُ ورقةٍ بلا منطقةِ تمرير (\`scr\`): ما زاد عن السقف يُقصّ`);
        }
      }
    }
    ts.forEachChild(node, visit);
  };

  visit(source);
}

// **إثباتُ الصمت** — صفرُ أوراقٍ يعني مسحاً أعمى لا شجرةً سليمة
if (sheets === 0) {
  console.error(
    "✗ لم يُعثر على جذرِ ورقةٍ واحد — المسحُ أعمى، لا الشجرةُ سليمة.",
  );
  console.error(
    `  قُرئ ${scanned} ملفَّ tsx. راجعْ علاماتِ الجذر: ${SHEET_RADIUS.join(" أو ")} مع ${SHEET_SURFACE}.`,
  );
  process.exit(1);
}

if (problems.length > 0) {
  console.error("✗ ورقةٌ سفليةٌ بلا سقفٍ أو بلا تمرير — تُقصّ من أعلى بلا رجعة:");
  for (const problem of problems) console.error(`  ${problem}`);
  console.error(
    "  والمقصوصُ لا يُبلَغ بأيِّ حركة: قِيس ٢٠٧ بكسلاً ذهبت بالوجهةِ ونقطةِ الانطلاق،",
  );
  console.error("  وعند إطارٍ ٥٢٠ يذهب المبلغُ نفسُه (`components/ui/Sheet.tsx`).");
  process.exit(1);
}

console.log(`✓ ${sheets} ورقةً بسقفٍ وتمرير (قُرئ ${scanned} ملفّاً)`);
