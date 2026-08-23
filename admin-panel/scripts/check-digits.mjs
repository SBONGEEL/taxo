/** حارسُ الخانات: **لا رقمَ عربيٌّ-هنديٌّ في نصٍّ يُعرض** (قرارُ المالك 2026-08-19).
 *
 * قُلبت صيغةُ العرض إلى اللاتينية في كل شاشةٍ وكل رقم، والمصفى الوحيد هو
 * `lib/utils.ts::digits`. وهذا الحارسُ يمنع عودةَ الخانات العربية من بابين
 * لا يراهما `tsc`:
 *
 * ١. **نصٌّ مكتوبٌ في الشيفرة** («الخطوة ١ من ٣»، «٢٤ ساعة») — نوعُه `string`
 *    صحيحٌ تماماً، ولا شيءَ في البناء يفرّق بين خانةٍ وخانة.
 * ٢. **لغةٌ غيرُ مثبَّتة** (`toLocaleDateString("ar-EG")`) — تُخرج خاناتٍ
 *    عربيةً من نفسِها بلا حرفٍ واحدٍ عربيٍّ في الشيفرة، فلا يجدها بحثٌ عن نصّ.
 *
 * **ويفحص بالشجرة لا بالنصّ**: يُحلَّل الملفُّ بمحلِّل TypeScript نفسِه، فتُقرأ
 * السلاسلُ ونصوصُ JSX وحدَها — والتعليقاتُ العربيةُ في هذا المشروع مليئةٌ
 * بالأرقام (§وقواعدُ مرقَّمة)، فحارسٌ يقرؤها يصرخ في كل ملفٍ ثم يُطفأ.
 *
 * **والاستثناءاتُ بأسمائها لا بنمط**: ملفاتُ التحويل نفسُها تحمل الخاناتِ
 * العربيةَ لأنها **آلةُ القلب** لا نصٌّ يُعرض — واستثناءٌ بنمطٍ عامٍّ كان
 * سيبتلع شاشةً يوماً.
 */

import { readFileSync } from "node:fs";
import { readdirSync } from "node:fs";
import { join, relative } from "node:path";
import process from "node:process";

import ts from "typescript";
import { certify } from "../../tools/certify.mjs";

const ROOT = process.cwd();
const ARABIC_INDIC = /[٠-٩۰-۹]/;

/** ملفاتٌ **هي** آلةُ التحويل: جداولُ الخانات وتعابيرُها النمطية. */
const MACHINERY = new Set([
  "src/lib/utils.ts", // digits / toLatinDigits — مداهما مكتوبٌ فيهما
  "src/lib/phone.ts", // ARABIC_DIGITS لتطبيع ما يكتبه المستخدم
]);

/** لغاتُ عرضٍ تُخرج خاناتٍ عربيةً-هندية — ممنوعةٌ ولو بلا حرفٍ عربيٍّ ظاهر. */
const ARABIC_NUMERAL_LOCALES = /^ar(-[A-Za-z]{2})?$|^ar-EG/;

const failures = [];

function scan(file) {
  const rel = relative(ROOT, file).replace(/\\/g, "/");
  if (MACHINERY.has(rel)) return;

  const source = ts.createSourceFile(
    file,
    readFileSync(file, "utf-8"),
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );

  const at = (node) =>
    source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;

  const walk = (node) => {
    // ١) خانةٌ عربيةٌ داخل سلسلةٍ أو نصِّ JSX
    if (
      ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateHead(node) ||
      ts.isTemplateMiddle(node) ||
      ts.isTemplateTail(node) ||
      ts.isJsxText(node)
    ) {
      const text = node.text ?? "";
      if (ARABIC_INDIC.test(text)) {
        failures.push(
          `${rel}:${at(node)}  خانةٌ عربية-هندية في نصٍّ يُعرض: ${text
            .trim()
            .slice(0, 60)}`,
        );
      }
    }

    // ٢) لغةُ عرضٍ غيرُ مثبَّتة — تُخرج الخاناتِ العربيةَ من نفسِها
    if (ts.isCallExpression(node)) {
      const name = node.expression.getText(source);
      const isFormatter =
        /toLocale(Date|Time)?String$/.test(name) ||
        /Intl\.(DateTime|Number)Format$/.test(name);
      if (isFormatter) {
        const first = node.arguments[0];
        if (first && ts.isStringLiteral(first) && ARABIC_NUMERAL_LOCALES.test(first.text)) {
          failures.push(
            `${rel}:${at(node)}  لغةٌ تُخرج خاناتٍ عربية: "${first.text}" — استعمل DISPLAY_LOCALE`,
          );
        }
      }
    }

    ts.forEachChild(node, walk);
  };

  walk(source);
}

/** مسحٌ بالمكتبة القياسية — الحارسُ نسخةٌ واحدةٌ في ثلاثة تطبيقاتٍ بلا تبعية. */
function walkDir(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walkDir(full);
    else if (/\.tsx?$/.test(entry.name)) scan(full);
  }
}

walkDir(join(ROOT, "src"));

if (failures.length > 0) {
  console.error("✗ أرقامٌ عربية-هندية في نصوصٍ تُعرض:\n");
  for (const line of failures) console.error("  " + line);
  console.error(
    `\n  المصفى الوحيد هو lib/utils.ts::digits، ولغةُ العرض DISPLAY_LOCALE.`,
  );
  process.exit(1);
}

certify("check:digits", "✓ كل الأرقام المعروضة لاتينية");
