#!/usr/bin/env node
/** **`check:native-calls` — وعدُ إضافةٍ أصليّةٍ لا يطفو بلا ماسك** (بلاغُ الإصدار 496، 2026-10-11).
 *
 * ## ما وقع
 *
 * غلافُ أندرويد للراكب **بُني قبل أن تدخله إضافةُ الإشعارات** (`437ea22`، قبل `51236e4`)، **والشاشاتُ تُحمَّل من الخادم** فهي أحدثُ منه.
 * و`RideComms.tsx` كان ينادي `PushNotifications.addListener(…)` بـ`void … .then(…)` **بلا `.catch`** — فرُفض الوعدُ عند كلِّ إقلاعٍ
 * («plugin is not implemented on android») ووصل تقاريرَ الأعطال: ستّةُ أحداثٍ من أربعة أجهزة. **ولا أثرَ يُرى، والضجيجُ يُغرق الحقيقيّ.**
 *
 * ## ما يمسكه
 *
 * **نداءٌ لإضافةٍ أصليّة** — مستوردةٍ من `@capacitor/*` (عدا `core`) أو `@aparajita/*`، أو مسجَّلةٍ بـ`registerPlugin` — **يطفو وعدُه**:
 * لا يُنتظر (`await`) ولا يُعاد ولا يُمرَّر، بل يُرمى (`void`، أو سطرٌ وحدَه، أو يُحفظ في متغيّر) — **وليس في سلسلته `.catch(` ولا
 * `.then(نجاح، فشل)`**. فهذا الشكلُ بعينه: **إن غابت الإضافةُ من الغلاف صار رفضاً بلا ماسك**.
 *
 * ## وما لا يمسكه — يُقال ولا يُسكت عنه
 *
 * - **النداءُ المنتظَر أو المعاد**: رفضُه لمن ناداه، **وهو مسؤوليّةُ النداء لا الإضافة** — ومسكُه هنا يصيح على سليمٍ كثير
 *   (`try`/`catch` عند المنادي)، **وحارسٌ يصيح على السليم يُطفأ**.
 * - **وعدُ دالّةٍ لنا تنادي إضافةً** (`listenToPush` مثلاً): لا يُتتبَّع عبر الدوالّ. **فالدوالُّ التي تنادي إضافةً غيرَ مضمونةٍ تسأل
 *   `Capacitor.isPluginAvailable` أولاً** (كما في `lib/push.ts` للتطبيقين)، **ومناديها يُمسك** — وهذا شرطٌ بشريّ.
 *
 *     node tools/check-native-calls.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

import { certify } from "./certify.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APPS = ["customer-app", "driver-app"];
// **و`--root <دليل>` يقيس شجرةً أخرى** — به يُقاس الحارسُ في الاتجاهين على الشجرة قبل العلاج (والمُحلِّلُ من هنا)
const at = process.argv.indexOf("--root");
const SRC = at > 0 ? path.resolve(process.argv[at + 1]) : ROOT;
const PLUGIN_MODULE = /^@capacitor\/(?!core$)|^@aparajita\//;

// **المُحلِّلُ من أيِّ تطبيقٍ ثُبّتت حزمتُه** — CI يثبّت تطبيقاً واحداً في كلِّ مهمّة (درسُ `check-arabic-frozen`)
let ts;
for (const app of ["customer-app", "driver-app", "admin-panel"]) {
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

function sources(app) {
  const out = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.tsx?$/.test(entry.name) && !/\.d\.ts$/.test(entry.name)) out.push(full);
    }
  };
  walk(path.join(SRC, app, "src"));
  return out.sort();
}

/** أسماءُ الإضافات في الملفّ: ما استُورد من وحداتها، وما سُجّل بـ`registerPlugin`. */
function pluginNames(file) {
  const names = new Set();
  const visit = (node) => {
    if (ts.isImportDeclaration(node) && PLUGIN_MODULE.test(node.moduleSpecifier.text)) {
      const bindings = node.importClause?.namedBindings;
      if (bindings && ts.isNamedImports(bindings)) {
        for (const el of bindings.elements) if (!el.isTypeOnly) names.add(el.name.text);
      }
    }
    if (ts.isVariableDeclaration(node) && node.initializer && ts.isCallExpression(node.initializer)) {
      const callee = node.initializer.expression;
      if (ts.isIdentifier(callee) && callee.text === "registerPlugin" && ts.isIdentifier(node.name)) names.add(node.name.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  return names;
}

const unwrap = (node) => {
  let n = node;
  while (n.parent && (ts.isParenthesizedExpression(n.parent) || ts.isAsExpression(n.parent) || ts.isNonNullExpression(n.parent))) n = n.parent;
  return n;
};

/** من نداء الإضافة إلى رأس سلسلته (`.then(…).catch(…)`) — وهل في السلسلة ماسك؟ */
function chain(call) {
  let node = unwrap(call);
  let caught = false;
  for (;;) {
    const access = node.parent;
    if (!access || !ts.isPropertyAccessExpression(access) || access.expression !== node) break;
    const next = access.parent;
    if (!next || !ts.isCallExpression(next) || next.expression !== access) break;
    const name = access.name.text;
    if (name === "catch" || (name === "then" && next.arguments.length >= 2)) caught = true;
    node = unwrap(next);
  }
  return { top: node, caught };
}

/** أيطفو الوعد؟ — يُرمى ولا يُنتظر ولا يُعاد ولا يُمرَّر. */
function floats(top) {
  const parent = top.parent;
  if (!parent) return false;
  if (ts.isVoidExpression(parent) || ts.isExpressionStatement(parent)) return true;
  if (ts.isVariableDeclaration(parent) && parent.initializer === top) return true;
  if (ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.EqualsToken && parent.right === top) return true;
  return false;
}

const found = [];
let calls = 0;
let files = 0;
for (const app of APPS) {
  for (const full of sources(app)) {
    const text = fs.readFileSync(full, "utf8");
    const file = ts.createSourceFile(full, text, ts.ScriptTarget.Latest, true, full.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    const plugins = pluginNames(file);
    if (plugins.size === 0) continue;
    files += 1;
    const visit = (node) => {
      if (
        ts.isCallExpression(node) &&
        ts.isPropertyAccessExpression(node.expression) &&
        ts.isIdentifier(node.expression.expression) &&
        plugins.has(node.expression.expression.text)
      ) {
        calls += 1;
        const { top, caught } = chain(node);
        if (!caught && floats(top)) {
          const { line } = file.getLineAndCharacterOfPosition(node.getStart(file));
          found.push(`${path.relative(SRC, full)}:${line + 1}  ${node.expression.getText(file)}(…)`);
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(file);
  }
}

if (found.length) {
  console.error(`✗ check:native-calls — ${found.length} نداءً لإضافةٍ أصليّةٍ يطفو وعدُه بلا ماسك:\n`);
  for (const line of found) console.error(`    ${line}`);
  console.error(
    "\n  **غلافٌ أقدمُ بلا الإضافة يرفض الوعدَ فيصل تقاريرَ الأعطال** (بلاغُ 496). أضف `.catch(() => undefined)` في السلسلة،\n" +
      "  واسأل `Capacitor.isPluginAvailable(…)` قبل ما يُعلَّق عليها إن لم تكن في كلِّ غلاف.",
  );
  process.exit(1);
}
certify("check:native-calls", `${calls} نداءً لإضافةٍ أصليّة في ${files} ملفّاً`, "لا وعدَ يطفو بلا ماسك");
