/** أداةُ تعديلٍ لمرّةٍ واحدة (أمرُ المالك ٢٠٢٦-١١-٢٠ الثاني، البند ٣) — `digits(<مبلغ>)` في تطبيق الكبتن ⇐ `formatAmount(<مبلغ>, <عملته>)`.
 *
 * **العملةُ من مدقّق الأنواع لا من التخمين**: يُؤخذ جذرُ عبارة المبلغ (`ride` من `ride.estimated_fare`، `offer.ride` من
 * `offer.ride.current_fare`) ويُسأل: أله حقلٌ اسمُه `currency` نوعُه سلسلة؟ إن كان ⇐ `formatAmount(x, root.currency)`. وإلا يُطبع الموضعُ
 * ويبقى كما هو ليُصلَح بيد. وتُعدَّل مواضعُ نوعُ مبلغها سلسلةٌ (أو null/undefined) وحدَها — الأعدادُ ليست مالاً من الخادم.
 *
 * node tools/codemod-money-digits.mjs [--write]
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const APP = path.join(ROOT, "driver-app");
const ts = createRequire(path.join(APP, "package.json"))("typescript");
const WRITE = process.argv.includes("--write");
const MONEY = /(fare|amount|price|total|net|balance|earn|commission|fee|tip|cost|outstanding|due|sum|bonus|reward|debt|advance|payout|gross|collected)/i;

const configPath = path.join(APP, "tsconfig.app.json");
const cfg = ts.readConfigFile(fs.existsSync(configPath) ? configPath : path.join(APP, "tsconfig.json"), ts.sys.readFile);
const parsed = ts.parseJsonConfigFileContent(cfg.config, ts.sys, APP);
const program = ts.createProgram(parsed.fileNames, parsed.options);
const checker = program.getTypeChecker();

const manual = [];
let changed = 0;
for (const sf of program.getSourceFiles()) {
  const file = sf.fileName;
  if (!file.includes("/driver-app/src/") || file.includes("/node_modules/") || file.endsWith("lib/utils.ts")) continue;
  const edits = [];
  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "digits" && node.arguments.length === 1) {
      const arg = node.arguments[0];
      const text = arg.getText(sf);
      if (MONEY.test(text)) {
        const argType = checker.getTypeAtLocation(arg);
        const parts = argType.isUnion() ? argType.types : [argType];
        const stringy = parts.every((t) => t.flags & (ts.TypeFlags.StringLike | ts.TypeFlags.Null | ts.TypeFlags.Undefined));
        const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
        const where = `${path.relative(ROOT, file)}:${line}  ${text}`;
        if (!stringy) {
          manual.push(`${where}  (ليس سلسلة: ${checker.typeToString(argType)})`);
        } else {
          // الجذرُ: أوّلُ عبارةِ وصولٍ عن يسار آخر حقل — مع ?? نأخذ الطرفَ الأيسر
          let probe = arg;
          while (ts.isBinaryExpression(probe) && probe.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken) probe = probe.left;
          while (ts.isParenthesizedExpression(probe) || ts.isNonNullExpression(probe)) probe = probe.expression;
          let currency = null;
          if (ts.isPropertyAccessExpression(probe)) {
            const root = probe.expression;
            const rootType = checker.getNonNullableType(checker.getTypeAtLocation(root));
            const prop = rootType.getProperty("currency");
            if (prop) {
              const pt = checker.getTypeOfSymbolAtLocation(prop, root);
              if (pt.flags & ts.TypeFlags.StringLike || (pt.isUnion() && pt.types.every((t) => t.flags & (ts.TypeFlags.StringLike | ts.TypeFlags.Null | ts.TypeFlags.Undefined)))) {
                const q = probe.questionDotToken || root.getText(sf).includes("?.") ? "?." : ".";
                currency = `${root.getText(sf)}${q}currency`;
              }
            }
          }
          if (currency) {
            edits.push({ start: node.getStart(sf), end: node.getEnd(), text: `formatAmount(${text}, ${currency})` });
          } else {
            manual.push(`${where}  (لا عملةَ على الجذر)`);
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  if (!edits.length) continue;
  let out = sf.getFullText();
  for (const e of edits.sort((a, b) => b.start - a.start)) out = out.slice(0, e.start) + e.text + out.slice(e.end);
  if (!/\bformatAmount\b/.test(sf.getFullText().replace(/digits\(/g, ""))) {
    // استيرادُ formatAmount من بيته — يُلحق باستيراد utils إن وُجد وإلا سطرٌ جديد
    const m = out.match(/import \{([^}]*)\} from "@\/lib\/utils";/);
    if (m) out = out.replace(m[0], `import {${m[1].replace(/\s*$/, "")}, formatAmount } from "@/lib/utils";`);
    else out = out.replace(/^(import [^\n]*\n)/m, `$1import { formatAmount } from "@/lib/utils";\n`);
  }
  changed += edits.length;
  console.log(`${path.relative(ROOT, file)}: ${edits.length}`);
  if (WRITE) fs.writeFileSync(file, out);
}
console.log(`\nعُدِّل ${changed} موضعاً${WRITE ? "" : " (تجربةٌ بلا كتابة)"}. ويدويّاً ${manual.length}:`);
for (const m of manual) console.log("  " + m);
