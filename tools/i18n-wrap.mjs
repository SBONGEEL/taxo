#!/usr/bin/env node
/**
 * **يلفّ النصوصَ العربيّة في `tr()`** (SPEC §٧٣-هـ المرحلة ٥) — لتطبيقَي الراكب والكبتن.
 *
 *     node tools/i18n-wrap.mjs customer-app            # كلُّ الشجرة
 *     node tools/i18n-wrap.mjs driver-app src/x.tsx    # ملفّاتٌ بعينها
 *
 * **لا يضيف سطراً ولا يحذف سطراً** — فالحرّاسُ التي تعرف الاستثناءَ بـ`ملف:سطر` تبقى صادقة: الاستيرادُ يُلحق بسطر آخر استيراد، ونصُّ
 * JSX الممتدُّ سطوراً يُستبدل وتُبقى أسطرُه فراغاً لا يرسمه JSX.
 *
 * **وما يُلفّ**: نصُّ JSX (بما يرسمه — والمسافاتُ حوله تُحفظ بنصوصٍ صريحة `{" "}`)، والحرفيّاتُ النصّيّة، وقيمُ الخصائص المرئيّة
 * (`placeholder` · `aria-label` · `title` · `label`…)، وقوالبُ النصوص ⇐ `tr("… {0} …", { 0: قيمة })`.
 * **وما لا يُلفّ — لأن لفَّه يغيّر سلوكاً لا نصّاً**: ما يُقارَن (`===` · `case`) أو يُبحث به (`includes` · `startsWith`…)، والأنواعُ
 * وأسماءُ الخصائص و`as const`، وقيمُ `value`/`key`/`id`، وما في `console`. **فتبقى تلك عربيّةً في الفرنسيّة** — ويعدّها الحارسُ «غيرَ
 * ملفوفة».
 */

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

import { jsxRendered } from "./check-arabic-frozen-lib.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [app, ...only] = process.argv.slice(2);
// **واللوحةُ بملفّاتٍ بعينها وحدَها**: نسخُ نظام التصميم وبوّابةِ التحديث بايتاً (`check:taxo2` · `check:update-gate`) — و`tr` فيها عربيّةٌ أبداً
if (!(["customer-app", "driver-app"].includes(app) || (app === "admin-panel" && only.length))) {
  console.error("استعمال: node tools/i18n-wrap.mjs <customer-app|driver-app> [ملفّات…] — أو admin-panel <ملفّات منسوخة…>");
  process.exit(2);
}
const require = createRequire(path.join(ROOT, app, "package.json"));
const ts = require("typescript");
const AR = /[؀-ۿ]/;
const TR_NAMES = new Set(["tr", "i18nTr"]);
const SKIP_ATTRS = new Set([
  "key", "id", "name", "value", "defaultValue", "htmlFor", "className", "type", "role", "href", "src", "to", "lang", "dir",
  "inputMode", "autoComplete", "rel", "target", "method", "action", "pattern", "accept", "form", "icon", "tone", "variant",
]);
const DATA_METHODS = new Set([
  "includes", "startsWith", "endsWith", "indexOf", "lastIndexOf", "match", "matchAll", "replace", "replaceAll", "split",
  "search", "localeCompare", "test", "has", "get", "set", "delete",
]);
const EQUALITY = new Set([
  ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken,
]);
const newlines = (text) => (text.match(/\n/g) ?? []).length;

function sources() {
  if (only.length) return only.map((f) => path.resolve(ROOT, app, f));
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

function inTypeOrConst(node) {
  for (let p = node.parent; p && !ts.isSourceFile(p); p = p.parent) {
    if (ts.isTypeNode(p) && !ts.isExpressionWithTypeArguments(p)) return true;
    if (ts.isAsExpression(p) && ts.isTypeReferenceNode(p.type) && p.type.typeName.getText() === "const") return true;
    if (ts.isBlock(p) || ts.isSourceFile(p)) break;
  }
  return false;
}

function skipLiteral(node) {
  const parent = node.parent;
  if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent) || ts.isExternalModuleReference(parent)) return true;
  if ((ts.isPropertyAssignment(parent) || ts.isPropertySignature(parent) || ts.isPropertyDeclaration(parent) ||
    ts.isMethodDeclaration(parent) || ts.isEnumMember(parent) || ts.isGetAccessorDeclaration(parent)) && parent.name === node) return true;
  if (ts.isComputedPropertyName(parent) || ts.isCaseClause(parent) || ts.isLiteralTypeNode(parent)) return true;
  if (ts.isTaggedTemplateExpression(parent)) return true;
  if (ts.isBinaryExpression(parent) && EQUALITY.has(parent.operatorToken.kind)) return true;
  if (ts.isElementAccessExpression(parent) && parent.argumentExpression === node) return true;
  if (ts.isCallExpression(parent) || ts.isNewExpression(parent)) {
    const callee = parent.expression;
    if (ts.isIdentifier(callee) && (TR_NAMES.has(callee.text) || callee.text === "RegExp")) return true;
    if (ts.isPropertyAccessExpression(callee)) {
      if (ts.isIdentifier(callee.expression) && callee.expression.text === "console") return true;
      if (DATA_METHODS.has(callee.name.text)) return true;
    }
  }
  return inTypeOrConst(node);
}

function wrapFile(file) {
  const source = fs.readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  let fn = "tr";
  let declared = false;
  const scan = (node) => {
    if (ts.isIdentifier(node) && node.text === "tr" && !(ts.isPropertyAccessExpression(node.parent) && node.parent.name === node)) {
      const imported = ts.isImportSpecifier(node.parent) && node.parent.parent.parent.parent.moduleSpecifier.text === "@/lib/i18n";
      if (!imported) declared = true;
    }
    ts.forEachChild(node, scan);
  };
  scan(sf);
  if (declared) fn = "i18nTr";
  const call = (key, extra = "") => `${fn}(${JSON.stringify(key)}${extra})`;

  /** يجمع تعديلاتِ عقدةٍ في `edits` — والقالبُ يجمع تعديلاتِ ما بداخله ويطويها في تعديلٍ واحد */
  function collect(node, edits) {
    if (ts.isJsxText(node)) {
      const raw = node.text;
      if (!AR.test(raw) || raw.includes("&")) return;
      const rendered = jsxRendered(raw);
      const core = rendered.trim();
      if (!core || !AR.test(core)) return;
      const lead = rendered.slice(0, rendered.length - rendered.trimStart().length);
      const trail = rendered.slice(rendered.trimEnd().length);
      const rawLead = raw.match(/^\s*/)[0];
      const rawTrail = raw.match(/\s*$/)[0];
      const keepLead = rawLead.includes("\n") ? rawLead : "";
      const keepTrail = rawTrail.includes("\n") ? rawTrail : "";
      const inner = newlines(raw) - newlines(keepLead) - newlines(keepTrail);
      const text = keepLead + (lead ? `{${JSON.stringify(lead)}}` : "") + `{${call(core)}}` +
        (trail ? `{${JSON.stringify(trail)}}` : "") + "\n".repeat(inner) + keepTrail;
      edits.push({ start: node.pos, end: node.end, text });
      return;
    }
    if (ts.isStringLiteral(node) && AR.test(node.text)) {
      if (ts.isJsxAttribute(node.parent)) {
        const name = node.parent.name.getText(sf);
        if (SKIP_ATTRS.has(name) || name.startsWith("data-") || /&\w+;|&#/.test(node.text)) return;
        edits.push({ start: node.getStart(sf), end: node.end, text: `{${call(node.text)}}` });
        return;
      }
      if (skipLiteral(node)) return;
      edits.push({ start: node.getStart(sf), end: node.end, text: call(node.text, "\n".repeat(newlines(node.getText(sf)))) });
      return;
    }
    if (ts.isNoSubstitutionTemplateLiteral(node) && AR.test(node.text)) {
      if (skipLiteral(node)) return;
      edits.push({ start: node.getStart(sf), end: node.end, text: call(node.text, "\n".repeat(newlines(node.getText(sf)))) });
      return;
    }
    if (ts.isTemplateExpression(node)) {
      const parts = [node.head, ...node.templateSpans.map((s) => s.literal)];
      if (parts.some((p) => AR.test(p.text)) && !parts.some((p) => /[{}]/.test(p.text)) && !skipLiteral(node)) {
        const exprs = node.templateSpans.map((span) => {
          const inner = [];
          collect(span.expression, inner);
          return apply(span.expression.getStart(sf), span.expression.end, inner);
        });
        const key = node.head.text + node.templateSpans.map((s, i) => `{${i}}${s.literal.text}`).join("");
        const vars = exprs.map((e, i) => `${i}: ${e}`).join(", ");
        const extra = newlines(node.getText(sf)) - exprs.reduce((n, e) => n + newlines(e), 0);
        edits.push({ start: node.getStart(sf), end: node.end, text: `${fn}(${JSON.stringify(key)}, { ${vars} }${"\n".repeat(Math.max(0, extra))})` });
        return;
      }
    }
    ts.forEachChild(node, (child) => collect(child, edits));
  }

  function apply(start, end, edits) {
    let text = source.slice(start, end);
    for (const edit of [...edits].sort((a, b) => b.start - a.start)) {
      text = text.slice(0, edit.start - start) + edit.text + text.slice(edit.end - start);
    }
    return text;
  }

  const edits = [];
  collect(sf, edits);
  if (!edits.length) return 0;
  let out = apply(0, source.length, edits);
  const hasImport = sf.statements.some((s) => ts.isImportDeclaration(s) && s.moduleSpecifier.text === "@/lib/i18n");
  if (!hasImport) {
    const statement = fn === "tr" ? 'import { tr } from "@/lib/i18n";' : 'import { tr as i18nTr } from "@/lib/i18n";';
    const imports = sf.statements.filter(ts.isImportDeclaration);
    if (imports.length) {
      // **على سطر آخر استيراد** — والتعديلاتُ كلُّها بعده، فموضعُه في النصّ الجديد هو موضعُه في القديم
      const at = imports[imports.length - 1].end;
      out = out.slice(0, at) + ` ${statement}` + out.slice(at);
    } else {
      out = `${out.replace(/\n?$/, "\n")}${statement}\n`;
    }
  }
  if (newlines(out) !== newlines(source) && !(newlines(out) === newlines(source) + 1 && !sf.statements.some(ts.isImportDeclaration))) {
    throw new Error(`عددُ الأسطر تغيّر في ${file}: ${newlines(source)} ⇐ ${newlines(out)}`);
  }
  fs.writeFileSync(file, out);
  return edits.length;
}

let total = 0;
let files = 0;
for (const file of sources()) {
  const n = wrapFile(file);
  if (n) {
    total += n;
    files += 1;
  }
}
console.log(`✓ ${app}: لُفّ ${total} نصّاً في ${files} ملفّاً`);
