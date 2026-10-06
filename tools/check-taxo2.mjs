/** `check:taxo2` — **نظامُ تصميم TAXO 2.0 منسوخٌ في كلِّ تطبيق، فيُقاس بايتاً** (SPEC §61-ج).
 *
 * `src/taxo2/` في تطبيقي الراكب والكبتن **ولوحةِ الإدارة** (§٦٢/١٦ — «نظامُ تصميمٍ واحد») **ملفّاتٌ واحدةٌ ثلاثَ نسخٍ لا استيراد** —
 * بعلّة بوّابة التحديث نفسِها: كلُّ تطبيقٍ شجرةٌ تُبنى وحدَها، **واستيرادُ مكوّنٍ من خارج الشجرة يجرّ بناءً ثانياً إلى داخل الأول**.
 *
 * **والنسخُ بلا حارسٍ تفترق أوّلَ تعديل — والافتراقُ هنا لا يُسقط شيئاً**: البناءُ أخضر، **والتطبيقان يرسمان «الجمر» بلونين**
 * أو «الشارة» بمقاسين — وهو عينُ ما وُجد نظامُ التصميم ليمنعه: هويةٌ واحدةٌ تُرى بوجهين.
 *
 * **فيقيس أمرين**: أن **مجموعةَ الملفّات واحدة** (ملفٌّ في نسخةٍ دون الأخرى افتراق)، وأن **كلَّ ملفٍّ متطابق** بعد تطبيع
 * نهايات الأسطر (`driver-app` محفوظٌ بـCRLF أحياناً، **وفرقُ نهايةِ سطرٍ ليس افتراقاً في الشكل**).
 *
 * **وثالثاً للوحة** (أُضيف حين صارت النسخةُ الثالثة): **كلُّ أيقونةٍ تسمّيها شيفرتُها في مقتطَع خطّها** (`icon_names=` في
 * `admin-panel/index.html`) **ومقتطَعُها مرتَّبٌ أبجدياً بلا تكرار** — وإلا رُسم اسمُ الأيقونة نصّاً، أو ردّ المُقدِّمُ الطلبَ كلَّه.
 * ويقرأ الأسماءَ **بمُحلِّل TypeScript لا بالنصّ**: `<Icon name=…>` بفروعه، و`icon="…"`/`icon: "…"`، ومتغيّراتُ `…icon` وجداولُ `…_ICON`، ونصُّ
 * عنصرٍ صنفُه `t2-icon`. **وحدُّه مكتوب**: اسمٌ يُبنى من متغيّرٍ لا يُرى (`name={x}` بلا حرفيٍّ يصل إليه) — وصفرُ اسمٍ مقروءٍ سقوط.
 *
 * **وحدُّه مكتوب**: يقيس **التطابق** لا **الصحّة** — من عدّل النسخَ بالخطأ نفسِه يمرّ؛ وما يضمنه أن **الافتراقَ لا يمرّ صامتاً**.
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { certify } from "./certify.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
/** **النسخُ كلُّها** — والأولى مرجعُ المقارنة. */
const APPS = ["customer-app", "driver-app", "admin-panel"];
/** **جسرُ أيقونات المتجر** يُرسم في التطبيقين — فمقتطَعُهما يحمل مقابلاتِه (واللوحةُ إن نادته، أدناه). */
const BRIDGE_APPS = ["customer-app", "driver-app"];
const REL = join("src", "taxo2");

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...walk(path));
    else out.push(path);
  }
  return out;
}

const copies = [];
for (const app of APPS) {
  const dir = join(ROOT, app, REL);
  if (!existsSync(dir)) {
    console.error(`\n✗ نسخةٌ مفقودة: ${app}/${REL.replace(/\\/g, "/")}`);
    console.error("  **والغيابُ ليس تطابقاً**: تطبيقٌ بلا نظام التصميم يرسم الهويةَ من عنده.");
    process.exit(1);
  }
  const files = new Map();
  for (const path of walk(dir)) {
    const rel = relative(dir, path).replace(/\\/g, "/");
    const text = readFileSync(path, "utf8").replace(/\r\n/g, "\n");
    files.set(rel, createHash("sha256").update(text).digest("hex"));
  }
  copies.push({ app, files });
}

const [a] = copies;
const problems = [];
for (const b of copies.slice(1)) {
  const names = new Set([...a.files.keys(), ...b.files.keys()]);
  for (const name of [...names].sort()) {
    const da = a.files.get(name);
    const db = b.files.get(name);
    if (!da) problems.push(`  ${name} — في ${b.app} وليس في ${a.app}`);
    else if (!db) problems.push(`  ${name} — في ${a.app} وليس في ${b.app}`);
    else if (da !== db) problems.push(`  ${name} — افترق بين ${a.app} و${b.app} (${da.slice(0, 10)}… ≠ ${db.slice(0, 10)}…)`);
  }
}

if (problems.length) {
  console.error("\n✗ نسخُ نظام التصميم افترقت — والافتراقُ لا يُسقط بناءً:");
  for (const line of problems) console.error(line);
  console.error("");
  console.error("  انسخ الملفَّ الصحيحَ على الأخرى في الإيداع نفسِه. **وهويةٌ تُرى بوجهين**");
  console.error("  **هي ما وُجد نظامُ التصميم ليمنعه.**");
  process.exit(1);
}

// ── والجسرُ بين أيقونات اللوحة ورموز الهوية (`serviceIcon.ts`) ─────────────────────────────────────────
//
// **جهتان تُقاسان لأن كلتيهما تسقط صامتة**: اسمٌ في القائمة المقرَّرة بلا مقابل يُرسم `grid_view` بدل ما اختاره
// المشرف — **وهو «بديلٌ يعمل ويخفي العطب» الذي أنشأ القائمةَ المقرَّرة أصلاً** — ومقابلٌ ليس في مقتطَع الخطّ
// **يُرسم اسمُه نصّاً** («local_taxi» مكتوبةً في البلاطة). والخطُّ يُقتطَع بالأسماء في `index.html` لكلِّ تطبيق.
const allowedSrc = readFileSync(join(ROOT, "backend", "app", "services", "storefront.py"), "utf8");
const tuple = allowedSrc.match(/SERVICE_ICONS:\s*tuple\[str, \.\.\.\]\s*=\s*\(([\s\S]*?)\n\)/)?.[1];
const allowed = tuple ? [...tuple.matchAll(/"([a-z0-9-]+)"/g)].map((m) => m[1]) : [];
const bridgeSrc = readFileSync(join(ROOT, "customer-app", REL, "serviceIcon.ts"), "utf8");
const bridge = new Map(
  [...bridgeSrc.matchAll(/^\s*"?([a-z0-9-]+)"?:\s*"([a-z0-9_]+)",/gm)].map((m) => [m[1], m[2]]),
);
const iconProblems = [];
// **صمتُ القارئ عطبٌ لا سلامة**: صفرٌ مقروءٌ من أيٍّ من الجهتين يوقف
if (allowed.length === 0) iconProblems.push("  لم تُقرأ `SERVICE_ICONS` من `storefront.py` — تغيّر شكلُها؟");
if (bridge.size === 0) iconProblems.push("  لم يُقرأ الجسرُ من `serviceIcon.ts` — تغيّر شكلُه؟");
for (const name of allowed) if (!bridge.has(name)) iconProblems.push(`  «${name}» في القائمة المقرَّرة بلا مقابلٍ في الجسر`);
for (const name of bridge.keys()) if (!allowed.includes(name)) iconProblems.push(`  «${name}» في الجسر وليس في القائمة المقرَّرة — مقابلٌ لما لا يُختار`);

function subsetOf(app) {
  const html = readFileSync(join(ROOT, app, "index.html"), "utf8");
  const raw = html.match(/icon_names=([a-z0-9_,]+)/)?.[1] ?? "";
  return raw.split(",").filter(Boolean);
}

for (const app of BRIDGE_APPS) {
  const subset = new Set(subsetOf(app));
  if (subset.size === 0) iconProblems.push(`  لم يُقرأ مقتطَعُ الخطّ من ${app}/index.html`);
  for (const glyph of new Set(bridge.values()))
    if (!subset.has(glyph)) iconProblems.push(`  «${glyph}» ليس في مقتطَع خطِّ ${app} — يُرسم اسمُه نصّاً`);
}

// ── ولوحةُ الإدارة: كلُّ اسمٍ تسمّيه شيفرتُها في مقتطَعها، والمقتطَعُ مرتَّبٌ بلا تكرار ──────────────────────
const ADMIN = "admin-panel";
const ts = createRequire(join(ROOT, ADMIN, "package.json"))("typescript");
const used = new Map(); // الاسم ← أوّلُ موضعٍ سُمّي فيه
let usesBridge = false;

function note(name, where) {
  if (/^[a-z][a-z0-9_]*$/.test(name) && !used.has(name)) used.set(name, where);
}
/** **الحرفيّاتُ التي قد تصير اسماً لا كلُّ حرفيّ**: فرعا الشرط لا شرطُه (`kind === "date" ? …`)، وقيمُ الجدول لا مفاتيحُه، والجدولُ
 *  لا ما يُفهرَس به (`{…}[tone]`)، وطرفا `??`/`||` وطرفُ `&&` الأيمن — ولا تُنزل في نداء. */
function literals(node, where) {
  if (!node) return;
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return note(node.text, where);
  if (ts.isConditionalExpression(node)) {
    literals(node.whenTrue, where);
    literals(node.whenFalse, where);
    return;
  }
  if (ts.isBinaryExpression(node)) {
    const op = node.operatorToken.kind;
    if (op === ts.SyntaxKind.QuestionQuestionToken || op === ts.SyntaxKind.BarBarToken) literals(node.left, where);
    if (op === ts.SyntaxKind.QuestionQuestionToken || op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.AmpersandAmpersandToken)
      literals(node.right, where);
    return;
  }
  if (ts.isElementAccessExpression(node)) return literals(node.expression, where);
  if (ts.isPropertyAssignment(node)) return literals(node.initializer, where);
  if (ts.isCallExpression(node)) return;
  ts.forEachChild(node, (child) => literals(child, where));
}
function scan(file) {
  const text = readFileSync(file, "utf8");
  const rel = relative(join(ROOT, ADMIN), file).replace(/\\/g, "/");
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const inCopy = rel.startsWith("src/taxo2/");
  // **جداولُ `icon:` في ملفٍّ يرسم بأيقونات الهوية وحدَه**: `Storefront.tsx` يحمل `icon: "package"` — **اسمُ lucide** يُرسل
  // إلى الخلفية ويُختار من قائمتها المقرَّرة، لا أيقونةٌ تُرسم هنا
  const drawsT2 = inCopy || /from "@\/taxo2"/.test(text);
  if (!inCopy && /\b(serviceIcon|SERVICE_ICON)\b/.test(text)) usesBridge = true;
  const visit = (node) => {
    const line = source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
    const where = `${rel}:${line}`;
    // <Icon name="…"> و<Icon name={شرط ? "أ" : "ب"}>
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(source) === "Icon") {
      for (const prop of node.attributes.properties) {
        if (ts.isJsxAttribute(prop) && prop.name.getText(source) === "name") literals(prop.initializer, where);
      }
    }
    // icon="…" على أيِّ عنصر (`ProfileSection` · `ActionCard`)
    if (ts.isJsxAttribute(node) && node.name.getText(source) === "icon") literals(node.initializer, where);
    // { icon: "…" } في الجداول (`GROUPS`)
    if (drawsT2 && ts.isPropertyAssignment(node) && node.name.getText(source) === "icon") literals(node.initializer, where);
    // متغيّراتُ `…icon` وجداولُ `…_ICON` (`themeIcon` · `KIND_ICON`) — **إلا جسرَ المتجر في النسخة**: يُقاس أعلاه، ويُطلب هنا إن نادته اللوحة
    if (ts.isVariableDeclaration(node) && /icon$/i.test(node.name.getText(source)) && !(inCopy && rel.endsWith("serviceIcon.ts"))) {
      literals(node.initializer, where);
    }
    // نصُّ عنصرٍ صنفُه `t2-icon` (`DateField`)
    if (ts.isJsxElement(node)) {
      const cls = node.openingElement.attributes.properties.find(
        (prop) => ts.isJsxAttribute(prop) && prop.name.getText(source) === "className",
      );
      const value = cls?.initializer && ts.isStringLiteral(cls.initializer) ? cls.initializer.text : "";
      if (/\bt2-icon\b/.test(value)) for (const child of node.children) literals(child, where);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
}
for (const file of walk(join(ROOT, ADMIN, "src"))) if (/\.tsx?$/.test(file)) scan(file);
if (usesBridge) for (const glyph of bridge.values()) note(glyph, "src/taxo2/serviceIcon.ts (تناديه اللوحة)");

const adminSubset = subsetOf(ADMIN);
const adminSet = new Set(adminSubset);
if (used.size === 0) iconProblems.push("  لم يُقرأ اسمُ أيقونةٍ واحدٌ من شيفرة اللوحة — تغيّر شكلُ النداء؟");
if (adminSubset.length === 0) iconProblems.push(`  لم يُقرأ مقتطَعُ الخطّ من ${ADMIN}/index.html`);
for (const [name, where] of used)
  if (!adminSet.has(name)) iconProblems.push(`  «${name}» (${where}) ليس في مقتطَع خطِّ ${ADMIN} — يُرسم اسمُه نصّاً`);
const sorted = [...adminSubset].sort();
if (adminSubset.join(",") !== sorted.join(",")) iconProblems.push(`  مقتطَعُ ${ADMIN} غيرُ مرتَّبٍ أبجدياً — والمُقدِّمُ يشترط الترتيب`);
if (adminSet.size !== adminSubset.length) iconProblems.push(`  في مقتطَع ${ADMIN} اسمٌ مكرَّر`);

if (iconProblems.length) {
  console.error("\n✗ الأيقونات (جسرُ المتجر · مقتطَعُ اللوحة):");
  for (const line of iconProblems) console.error(line);
  process.exit(1);
}

const all = createHash("sha256")
  .update([...a.files.entries()].sort().map(([k, v]) => `${k}:${v}`).join("\n"))
  .digest("hex");
certify(
  "check:taxo2",
  `✓ نظامُ التصميم متطابقٌ في ${copies.length} نسخ (${copies.map((c) => c.app).join(" · ")}) — ${a.files.size} ملفّات (${all.slice(0, 12)})`,
  `جسرُ الأيقونات يغطّي ${allowed.length} اسماً في خطَّي التطبيقين`,
  `واللوحةُ تسمّي ${used.size} أيقونةً كلُّها في مقتطَعها المرتَّب (${adminSubset.length})`,
);
