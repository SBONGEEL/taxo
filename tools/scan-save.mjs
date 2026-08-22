/** يمسح شاشاتِ اللوحة عن «نجاحٍ يُعلَن قبل أن يقع».
 *
 * والشكلُ: نداءُ **كتابةٍ** (مصدرُه `api/endpoints.ts`) يُطلق بلا `await`
 * ولا `.then` — ثم يُغلَق حوارٌ أو تُعلَن رسالةُ نجاح. **فالإغلاقُ يقع قبل
 * أن يُعرف**، ولو فشل النداءُ لم يرَ أحد.
 */
import { readFileSync, readdirSync } from "node:fs";
import ts from "../admin-panel/node_modules/typescript/lib/typescript.js";

const EP = readFileSync("admin-panel/src/api/endpoints.ts", "utf8");
// أسماءُ الكتابة وحدَها — لا القراءات
const WRITERS = new Set(
  [...EP.matchAll(/export (?:const|(?:async )?function) (\w+)/g)]
    .map((m) => m[1])
    .filter((n) => /^(create|update|patch|delete|remove|record|approve|reject|resolve|grant|revoke|mark|set|upload|attach|activate|suspend|block|unblock|waive|writeOff|pay|cancel|send|save|enable|disable|hide|restore)/.test(n)),
);

const findings = [];
for (const f of readdirSync("admin-panel/src/screens")) {
  if (!f.endsWith(".tsx")) continue;
  const path = `admin-panel/src/screens/${f}`;
  const src = readFileSync(path, "utf8");
  const sf = ts.createSourceFile(path, src, ts.ScriptTarget.Latest, true);
  const walk = (n) => {
    if (ts.isCallExpression(n) && ts.isIdentifier(n.expression) && WRITERS.has(n.expression.text)) {
      // **والانتظارُ قد يقع في مكانٍ آخر** — فلا يُحكم من الأب وحدَه:
      // نداءٌ داخل سهميّةٍ تُمرَّر إلى مُشغِّلٍ ينتظرها (`run(() => save())`)
      // **منتظَرٌ بحقّ**. وأولُ صياغةٍ لم تعُدَّ ذلك فأبلغت عن أربعةٍ سليمة —
      // **وحارسٌ يخترع أغلى من حارسٍ يفوت**.
      let awaited = false;
      for (let p = n.parent; p; p = p.parent) {
        if (ts.isAwaitExpression(p)) { awaited = true; break; }
        if (ts.isPropertyAccessExpression(p) && /^(then|catch|finally)$/.test(p.name.text)) { awaited = true; break; }
        // سهميّةٌ أو دالّةٌ تُعيد الوعدَ إلى من يستدعيها — فالانتظارُ عنده
        if (ts.isArrowFunction(p) || ts.isFunctionExpression(p) || ts.isFunctionDeclaration(p)) { awaited = true; break; }
        if (ts.isReturnStatement(p)) { awaited = true; break; }
        if (ts.isExpressionStatement(p)) break;   // جملةٌ قائمةٌ بذاتها ⇒ إطلاقٌ
      }
      if (!awaited) {
        const { line } = sf.getLineAndCharacterOfPosition(n.getStart());
        findings.push(`${path}:${line + 1}  ${n.expression.text}(…)`);
      }
    }
    ts.forEachChild(n, walk);
  };
  walk(sf);
}
console.log(`كُتّابٌ معروفون: ${WRITERS.size}`);
if (!findings.length) console.log("✓ لا نداءَ كتابةٍ مُطلَقاً بلا انتظار");
else { console.log(`✗ ${findings.length}:`); findings.forEach((x) => console.log("  " + x)); }
