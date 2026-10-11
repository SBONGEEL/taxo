#!/usr/bin/env node
/**
 * **العربيّةُ لا تتغيّر بالترجمة** (SPEC §٧٣-هـ المرحلة ٥) — حارسُ التطبيقين.
 *
 *     node tools/check-arabic-frozen.mjs            # يقيس
 *     node tools/check-arabic-frozen.mjs --write    # يكتب الجردَ من الشجرة (بعد تغييرٍ عربيٍّ مقصود)
 *
 * **ما يقيسه**: جردُ كلِّ نصٍّ عربيٍّ في شيفرة التطبيقين — نصُّ JSX كما يُرسم (بقواعد المسافات في JSX)، والحرفيّاتُ النصّيّة، وقوالبُ
 * النصوص بمواضع `{0}` `{1}` — **بلا التعليقات**. والجردُ المحفوظُ في `<app>/src/i18n/ar-inventory.json` كُتب من الشجرة **قبل** أن يُلفّ
 * أيُّ نصٍّ بـ`tr()`؛ **فكلُّ نصٍّ فيه يجب أن يبقى في الشجرة بعدده حرفاً** — ملفوفاً كان أو لا.
 *
 * **ولمَ يكفي هذا**: `tr(نص)` في العربيّة **تعيد النصَّ نفسَه** (`lib/i18n.ts`) — فالمفتاحُ هو ما يُرسم. **فإن بقي كلُّ مفتاحٍ كما كان،
 * بقي كلُّ ما يُرسم كما كان.** وما يُضاف جديداً لا يُسقط الحارس؛ **ما يُحذف أو يُعدَّل يُسقطه** — ومن عدّله بقصدٍ يكتب الجردَ ثانيةً
 * (`--write`) **ويضيف فرنسيّتَه** إلى `<app>/src/i18n/fr.json`.
 *
 * **وما لا يقيسه — مكتوبٌ لا مسكوتٌ عنه**: المسافاتُ حول النصّ الملفوف (حفظتها أداةُ اللفّ بنصوصٍ صريحة `{" "}`، ولا يقيسها هذا)؛ **وجودةُ
 * الفرنسيّة** (يعدّ الناقصَ منها ولا يُسقط عليه — والمراجعةُ البشريّة في `design/I18N-FR-REVIEW.csv`).
 */

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

import { jsxRendered, templateKey } from "./check-arabic-frozen-lib.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APPS = ["customer-app", "driver-app"];
const AR = /[؀-ۿ]/;
const WRITE = process.argv.includes("--write");

// **المُحلِّلُ من أيِّ تطبيقٍ ثُبّتت حزمتُه** — CI يثبّت تطبيقاً واحداً في كلِّ مهمّة (قِيس: مهمّةُ الكبتن سقطت لأن الراكبَ بلا حزم)
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
  console.error("✗ لم يوجد `typescript` في أيٍّ من: customer-app · driver-app · admin-panel — ثبّت حزمةَ تطبيق. الحارسُ لا يقيس.");
  process.exit(1);
}

function sources(app) {
  const out = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== "i18n") walk(full);
      } else if (/\.tsx?$/.test(entry.name) && !/\.d\.ts$|\.test\.tsx?$/.test(entry.name)) {
        if (!full.endsWith(path.join("lib", "i18n.ts"))) out.push(full);
      }
    }
  };
  walk(path.join(ROOT, app, "src"));
  return out.sort();
}

function inventory(app) {
  const counts = new Map();
  const wrapped = new Set();
  let unwrapped = 0;
  const add = (text) => counts.set(text, (counts.get(text) ?? 0) + 1);
  for (const file of sources(app)) {
    const sf = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true,
      file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    const isTrKey = (node) =>
      ts.isCallExpression(node.parent) && node.parent.arguments[0] === node &&
      ts.isIdentifier(node.parent.expression) && /^tr_?$|^i18nTr$/.test(node.parent.expression.text);
    const visit = (node) => {
      if (ts.isJsxText(node)) {
        if (AR.test(node.text)) {
          const core = (node.text.includes("&") ? node.text : jsxRendered(node.text)).trim();
          if (core) {
            add(core);
            unwrapped += 1;
          }
        }
        return;
      }
      if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) && AR.test(node.text)) {
        add(node.text);
        if (isTrKey(node)) wrapped.add(node.text);
        else unwrapped += 1;
        return;
      }
      if (ts.isTemplateExpression(node) && [node.head, ...node.templateSpans.map((s) => s.literal)].some((p) => AR.test(p.text))) {
        add(templateKey(node));
        unwrapped += 1;
        node.templateSpans.forEach((span) => visit(span.expression));
        return;
      }
      ts.forEachChild(node, visit);
    };
    visit(sf);
  }
  return { counts, wrapped, unwrapped };
}

let red = 0;
for (const app of APPS) {
  const file = path.join(ROOT, app, "src/i18n/ar-inventory.json");
  const { counts, wrapped, unwrapped } = inventory(app);
  if (WRITE) {
    const sorted = Object.fromEntries([...counts.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, `${JSON.stringify(sorted, null, 1)}\n`);
    console.log(`✓ ${app}: كُتب الجرد — ${counts.size} نصّاً عربيّاً (${[...counts.values()].reduce((a, b) => a + b, 0)} موضعاً)`);
    continue;
  }
  if (!fs.existsSync(file)) {
    console.error(`✗ ${app}: لا جردَ في ${path.relative(ROOT, file)} — الحارسُ لا يقيس.`);
    red += 1;
    continue;
  }
  const frozen = JSON.parse(fs.readFileSync(file, "utf8"));
  const lost = Object.entries(frozen).filter(([text, n]) => (counts.get(text) ?? 0) < n);
  const frFile = path.join(ROOT, app, "src/i18n/fr.json");
  const fr = fs.existsSync(frFile) ? JSON.parse(fs.readFileSync(frFile, "utf8")) : {};
  const untranslated = [...wrapped].filter((key) => !(key in fr)).length;
  if (lost.length) {
    red += 1;
    console.error(`✗ ${app}: ${lost.length} نصّاً عربيّاً تغيّر أو حُذف عمّا في الجرد — **والعربيّةُ لا تتغيّر بالترجمة**:`);
    for (const [text, n] of lost.slice(0, 20)) console.error(`    «${text}» — كان ${n} والآن ${counts.get(text) ?? 0}`);
    console.error("  إن كان التغييرُ مقصوداً: `node tools/check-arabic-frozen.mjs --write` ثمّ فرنسيّتُه في fr.json.");
    continue;
  }
  console.log(
    `✓ ${app}: العربيّةُ كما في الجرد (${Object.keys(frozen).length} نصّاً) · ملفوفٌ بـtr ${wrapped.size} · غيرُ ملفوف ${unwrapped} موضعاً` +
      ` · بلا فرنسيّة ${untranslated}`,
  );
}
process.exit(red ? 1 : 0);
