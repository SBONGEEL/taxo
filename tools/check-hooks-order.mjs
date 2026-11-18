#!/usr/bin/env node
/** **`check:hooks-order` — لا هوكَ بعد `return` مبكّر** (عطبٌ مقيسٌ ٢٠٢٦-١١-١٨).
 *
 * ## ما وقع
 *
 * هوكاتُ §١٠٣ في رئيسيّة الكبتن (`useHaptics` · `useNativeFlags` · `useDeviceSignals` · `useKeepAwake` · `useEffect` · `useDriverLauncher`)
 * أُضيفت **تحت** `if (settling) return <CollectT2Screen …/>`. فكلُّ إنهاءِ رحلةٍ يرسم الشاشةَ بهوكاتٍ أقلّ، **وReact يرمي «Rendered fewer
 * hooks than expected»** — فتسقط الرئيسيّةُ لحظةَ التحصيل. **ولم يره `tsc` ولا حارسٌ ولا فيلمُ محاكٍ**: لا فيلمَ يُنهي رحلة. وكان
 * `useTheme()` هناك قبلها بأشهر ولم يظهر — `useContext` لا يحجز خانةً — **فالشكلُ صحيحٌ بالصدفة سَتَر الخاطئَ بالبنية**.
 *
 * ## ما يمسكه
 *
 * في كلِّ دالّةٍ اسمُها مكوّنٌ (حرفٌ كبير) أو هوكٌ (`useX`): **جملةٌ في أعلى جسمها تحوي `return` ثمّ جملةٌ بعدها تنادي `useX(`**
 * (خارج دالّةٍ متداخلة) — ويُسمّى السطران.
 *
 * ## وما لا يمسكه — يُقال
 *
 * - **الهوكُ داخل شرطٍ أو حلقة** بلا `return` قبله (`if (x) useY()`) — شكلٌ آخر، لم يقع.
 * - **`return` داخل `try`/`switch` يُعدّ** كأيِّ جملة — قد يصيح على سليمٍ نادر، ويُرى بالسطر.
 *
 *     node tools/check-hooks-order.mjs [--root <دليل>]
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

import { certify } from "./certify.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APPS = ["customer-app", "driver-app", "admin-panel"];
// **و`--root <دليل>` يقيس شجرةً أخرى** — به يُقاس الحارسُ في الاتجاهين على الشجرة قبل العلاج
const at = process.argv.indexOf("--root");
const SRC = at > 0 ? path.resolve(process.argv[at + 1]) : ROOT;

// **المُحلِّلُ من أيِّ تطبيقٍ ثُبّتت حزمتُه** — CI يثبّت تطبيقاً واحداً في كلِّ مهمّة (درسُ `check-arabic-frozen`)
let ts;
for (const app of APPS) {
  try {
    ts = createRequire(path.join(ROOT, app, "package.json"))("typescript");
    break;
  } catch {
    // التالي
  }
}
if (!ts) {
  console.error("✗ لم يوجد `typescript` في أيٍّ من التطبيقات — ثبّت حزمةَ تطبيق. **الحارسُ لا يقيس، والغيابُ لا يُقرأ سلامة.**");
  process.exit(1);
}

function sources(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) sources(full, out);
    else if (/\.tsx?$/.test(entry.name) && !/\.d\.ts$/.test(entry.name)) out.push(full);
  }
  return out;
}

/** أفي الجملة `return` لها هي (لا لدالّةٍ داخلها)؟ */
function returns(node) {
  let found = false;
  const visit = (n) => {
    if (found || ts.isFunctionLike(n) || ts.isClassLike(n)) return;
    if (ts.isReturnStatement(n)) found = true;
    else ts.forEachChild(n, visit);
  };
  visit(node);
  return found;
}

/** نداءاتُ `useX(` في الجملة — خارج الدوالّ المتداخلة. */
function hooks(node) {
  const names = [];
  const visit = (n) => {
    if (ts.isFunctionLike(n)) return;
    if (ts.isCallExpression(n)) {
      const callee = n.expression;
      const name = ts.isIdentifier(callee) ? callee.text : ts.isPropertyAccessExpression(callee) ? callee.name.text : "";
      if (/^use[A-Z0-9]/.test(name)) names.push(name);
    }
    ts.forEachChild(n, visit);
  };
  visit(node);
  return names;
}

const found = [];
let files = 0;
let bodies = 0;
for (const app of APPS) {
  for (const file of sources(path.join(SRC, app, "src"))) {
    files += 1;
    const text = fs.readFileSync(file, "utf8");
    const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    const line = (n) => sf.getLineAndCharacterOfPosition(n.getStart()).line + 1;
    const visit = (n) => {
      let name = null;
      let body = null;
      if (ts.isFunctionDeclaration(n) && n.name) [name, body] = [n.name.text, n.body];
      else if (
        ts.isVariableDeclaration(n) &&
        ts.isIdentifier(n.name) &&
        n.initializer &&
        (ts.isArrowFunction(n.initializer) || ts.isFunctionExpression(n.initializer))
      )
        [name, body] = [n.name.text, n.initializer.body];
      if (name && /^([A-Z]|use[A-Z0-9])/.test(name) && body && ts.isBlock(body)) {
        bodies += 1;
        let returnAt = null;
        for (const statement of body.statements) {
          if (returnAt !== null) {
            for (const hook of hooks(statement))
              found.push(`${path.relative(SRC, file)}:${line(statement)}: ${name} — ${hook}() بعد return في السطر ${returnAt}`);
          } else if (!ts.isReturnStatement(statement) && returns(statement)) returnAt = line(statement);
        }
      }
      ts.forEachChild(n, visit);
    };
    visit(sf);
  }
}

if (found.length) {
  console.error(`✗ check:hooks-order · ${found.length} هوكاً بعد return مبكّر — عددُ الهوكات يتغيّر بين رسمين فيرمي React:`);
  for (const entry of found) console.error(`  ${entry}`);
  console.error("  **العلاج**: انقل الهوكَ (وما يحتاجه) فوق أوّلِ return — لا تطفئ الحارس.");
  process.exit(1);
}
certify("check:hooks-order", `${bodies} مكوّناً وهوكاً في ${files} ملفّاً`, "لا هوكَ بعد return مبكّر");
