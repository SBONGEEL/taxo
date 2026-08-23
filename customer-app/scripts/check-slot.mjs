/** يرفض `asChild` بأكثرَ من ابنٍ واحد — الحارسُ الرابع في العائلة.
 *
 * **العطبُ الذي وُجد لأجله** (تجربةُ المرحلة ١٣، 2026-08-15): `Button` بـ
 * `asChild` يرسم `<Slot>` ويمرّر إليه ابنَين — سطرَ التحميل و`children`.
 * و`Slot` يستعمل `React.Children.only`، **و`{null}` يُعدّ ابناً**. فيرمي
 * Radix استثناءً، ولا حدودَ خطأٍ فوقه، ⇒ **شاشةٌ بيضاء: صفرُ نصٍّ وعنصران**.
 * ووقع على **شاشتين ماليّتين**: الدفعُ بكليك وشحنُ المحفظة — فلا الراكبُ يدفع
 * ولا يشحن، بلا رسالةٍ ولا سطرٍ في السجل.
 *
 * **وما جعله يمرّ**: النوعُ صحيحٌ تماماً، فلا `tsc` يراه ولا حارسٌ آخر —
 * الكسرُ في زمن التشغيل داخل مكتبةٍ خارجية. وهو الشكلُ الرابع لعائلة «ما لا
 * يراه البناء»: صنفٌ يحذفه tailwind-merge، ومفتاحٌ غائبٌ عن المقياس، وقيمةٌ
 * ناقصةٌ من مصفوفةٍ لا اتحاد، **وابنٌ زائدٌ في `Slot`**.
 *
 * **والفحصُ بمحلّل TypeScript لا بتعبيرٍ نمطيّ**: JSX متداخلٌ وشرطيّ، وتعبيرٌ
 * نمطيٌّ يقرأ `>` الأولى نهايةً للوسم يُنتج حارساً يكذب في الاتجاهين — يمرّ على
 * عطبٍ ويوقف بناءً سليماً، وكلاهما يُفقد الثقةَ به فيُعطَّل بعد أسبوع.
 *
 * **وقاعدتُه**: عنصرٌ يحمل `asChild` (أو `<Slot>` مباشرةً) يجب أن يكون له
 * **ابنٌ واحدٌ بالضبط**، وألّا يكون ذلك الابنُ تعبيراً شرطياً قد يؤول إلى
 * `null` — فـ`Children.only(null)` يرمي كما يرمي الاثنان.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import { certify } from "../../tools/certify.mjs";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const SRC = new URL("../src/", import.meta.url).pathname.replace(
  /^\/([A-Za-z]:)/,
  "$1",
);

function files(dir) {
  const found = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) found.push(...files(path));
    else if (/\.tsx$/.test(entry)) found.push(path);
  }
  return found;
}

/** الأبناءُ المعتدُّ بهم: النصُّ الفارغُ بين الأسطر ليس ابناً عند React. */
function meaningfulChildren(node) {
  return (node.children ?? []).filter((child) => {
    if (ts.isJsxText(child)) return child.text.trim().length > 0;
    if (ts.isJsxExpression(child) && child.expression === undefined) return false;
    return true;
  });
}

function tagName(node) {
  const opening = node.openingElement ?? node;
  return opening.tagName?.getText?.(node.getSourceFile()) ?? "?";
}

/** هل يحمل العنصرُ `asChild` فعّالاً؟ `asChild={false}` لا يُنشئ `Slot`. */
function hasAsChild(opening, source) {
  for (const attribute of opening.attributes.properties) {
    if (!ts.isJsxAttribute(attribute)) continue;
    if (attribute.name.getText(source) !== "asChild") continue;
    if (attribute.initializer === undefined) return true; // asChild وحدها
    if (ts.isJsxExpression(attribute.initializer)) {
      const text = attribute.initializer.expression?.getText(source) ?? "";
      return text.trim() !== "false";
    }
    return true;
  }
  return false;
}

const problems = [];

for (const file of files(SRC)) {
  const source = ts.createSourceFile(
    file,
    readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );

  const visit = (node) => {
    const selfClosing = ts.isJsxSelfClosingElement(node);
    const element = ts.isJsxElement(node);
    if (selfClosing || element) {
      const opening = selfClosing ? node : node.openingElement;
      const name = opening.tagName.getText(source);
      const slotted = hasAsChild(opening, source) || name === "Slot";
      if (slotted) {
        const line =
          source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
        const children = selfClosing ? [] : meaningfulChildren(node);
        if (children.length !== 1) {
          problems.push(
            `${file.slice(SRC.length)}:${line} — <${name} asChild> له ${children.length} أبناء، والمطلوب ابنٌ واحد`,
          );
        } else {
          const only = children[0];
          if (ts.isJsxExpression(only) && only.expression) {
            const kind = only.expression.kind;
            const risky =
              kind === ts.SyntaxKind.ConditionalExpression ||
              (ts.isBinaryExpression(only.expression) &&
                only.expression.operatorToken.kind ===
                  ts.SyntaxKind.AmpersandAmpersandToken);
            if (risky) {
              problems.push(
                `${file.slice(SRC.length)}:${line} — <${name} asChild> ابنُه تعبيرٌ شرطيٌّ قد يؤول إلى null`,
              );
            }
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  };

  visit(source);
}

if (problems.length > 0) {
  console.error("✗ `asChild` يقبل ابناً واحداً بالضبط — و`{null}` يُعدّ ابناً:");
  for (const problem of problems) console.error(`  ${problem}`);
  console.error(
    "  والاستثناءُ غيرُ الملتقَط من `Slot` يُبيّض الشاشةَ بلا رسالةٍ ولا سجل.",
  );
  process.exit(1);
}

certify("check:slot", "✓ كلُّ `asChild` بابنٍ واحدٍ صريح");
