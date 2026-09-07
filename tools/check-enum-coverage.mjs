/** **اتحادٌ يغطّي تعدادَه، وخريطةُ أسماءٍ تغطّي اتحادَها** — أو يقف الإيداع.
 *
 * ## العلّةُ مقيسةٌ على شاشةٍ يقرؤها إنسان (2026-09-07)
 *
 * `WalletTransactionType` في الخلفية **ثمانيةَ عشرَ عضواً**، وفي لوحة الإدارة
 * **عشرة**. **والثمانيةُ الناقصةُ تُرسم بمفتاحها الإنجليزيّ** في درج الملفّ:
 * `tip_payment` · `cancellation_fee` · `advance` … بين «شحن» و«تسوية».
 *
 * **وقِيس المدى**: **٢٣ صفّاً من ١١٥ — ٢٠٪ من دفترٍ يراه المشرف**.
 *
 * ## و`check:enums` كان أخضرَ بحقّ — **وهذا هو الدرس**
 *
 * ذاك يسأل **«أثمّة قيمةٌ مخترعة؟»**: أعضاءُ الاتحاد كلُّهم في الخلفية، فمرّ.
 * **ولا يسأل «أينقص عضو؟»** — وهو حدٌّ **مكتوبٌ في `GUARDS.md` منذ
 * 2026-08-23**، **وثمنُه لم يُقَس حتى اليوم**.
 *
 * **وسؤالان لحارسٍ واحدٍ لا يجيب أحدُهما عن الآخر**: الزائدُ يكسر الشيفرة
 * فيُمسَك بالمُترجِم أحياناً، **والناقصُ لا يكسر شيئاً** — يرسم مفتاحاً
 * إنجليزياً في شاشةٍ عربية **ولا يشكو أحد**.
 *
 * ## ما يفعله
 *
 * ١) يقرأ كلَّ `class X(StrEnum)` في الخلفية بأعضائه.
 * ٢) ويقرأ كلَّ `type X = "a" | "b"` في التطبيقات الثلاثة.
 * ٣) **والمطابقةُ بالاسم**: `WalletTransactionType` هنا هي هي هناك.
 * ٤) فيشترط **تعدادُ الخلفية ⊆ اتحادُ الواجهة**.
 * ٥) ثمّ يقرأ كلَّ `Record<X, string>` ويشترط **الاتحادُ ⊆ مفاتيحُ الخريطة**.
 *
 * ## وما لا يمسكه — يُقال ولا يُقرأ سكوتُه ضماناً
 *
 * · **لا يقرأ نصَّ الاسم**: «شحن» أو «xyz» سواءٌ عنده. **يمسك الغياب لا
 *   الرداءة** — وتسميةُ ما يفهمه المشرفُ شرطٌ بشريّ.
 * · **ولا يعرف أيَّ اتحادٍ يُعرض فعلاً**: اتحادٌ لا يُرسم لإنسانٍ يُحسب معه،
 *   **والثمنُ عضوٌ يُترجَم بلا حاجة** لا عطبٌ مسكوت.
 * · **ولا يطابق ما اختلف اسمُه**: اتحادٌ اسمُه غيرُ اسم تعداده **لا يُرى
 *   أصلاً** — والمطابقةُ بالاسم شرطٌ لا اكتشاف.
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(new URL(".", import.meta.url))).replace(/[\\/]tools$/, "");
const BACKEND = join(ROOT, "backend", "app");
const APPS = ["admin-panel", "customer-app", "driver-app"];
const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");

/** اتحاداتٌ تغطّي تعدادَها **جزئياً بحقّ** — كلٌّ بعلّته. */
const PARTIAL = new Map([
  // مثال: ["PaymentMethod@customer-app", "الراكبُ لا يرى قنواتِ الكبتن"],
]);

const stripComments = (t) =>
  t.replace(/\/\*[\s\S]*?\*\//g, " ").replace(new RegExp("//[^\n]*", "g"), " ");

function walk(dir, test, out = []) {
  if (!existsSync(dir)) return out;
  for (const e of readdirSync(dir)) {
    if (e === "node_modules" || e === "__pycache__" || e === "dist" || e === "android") continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, test, out);
    else if (test(p)) out.push(p);
  }
  return out;
}

// ── ١) تعداداتُ الخلفية: الاسمُ → الأعضاء ─────────────────────────────────
const backend = new Map();
for (const f of walk(BACKEND, (p) => p.endsWith(".py"))) {
  const text = readFileSync(f, "utf8");
  for (const m of text.matchAll(/^class\s+(\w+)\((?:str,\s*)?(?:StrEnum|Enum)\):([\s\S]*?)(?=^class |\Z)/gm)) {
    const [, name, body] = m;
    const vals = [...body.matchAll(/^\s{4}[A-Z_0-9]+\s*=\s*"([^"]+)"/gm)].map((x) => x[1]);
    if (vals.length) backend.set(name, new Set(vals));
  }
}

// ── ٢) اتحاداتُ الواجهة وخرائطُ أسمائها ───────────────────────────────────
const missingMembers = [];
const missingLabels = [];
let unionsChecked = 0;
let mapsChecked = 0;

for (const app of APPS) {
  const src = join(ROOT, app, "src");
  const unions = new Map(); // اسم → أعضاء
  const files = walk(src, (p) => /\.tsx?$/.test(p));

  for (const f of files) {
    const text = stripComments(readFileSync(f, "utf8"));
    for (const m of text.matchAll(/type\s+(\w+)\s*=\s*((?:\s*\|?\s*"[^"]+")+)\s*;/g)) {
      const [, name, body] = m;
      const members = [...body.matchAll(/"([^"]+)"/g)].map((x) => x[1]);
      if (members.length < 2) continue;
      unions.set(name, { members: new Set(members), file: f });
    }
  }

  for (const [name, { members, file }] of unions) {
    const be = backend.get(name);
    if (!be) continue; // لا تعدادَ بهذا الاسم — خارج نطاق هذا الحارس
    if (PARTIAL.has(`${name}@${app}`)) continue;
    unionsChecked += 1;
    const gone = [...be].filter((v) => !members.has(v));
    if (gone.length)
      missingMembers.push(
        `${file.replace(ROOT + "/", "")}: ${name} — ينقصه ${gone.length}: ${gone.join(", ")}`,
      );
  }

  // ── خرائطُ الأسماء: `Record<UnionName, string>` ───────────────────────
  for (const f of files) {
    const text = stripComments(readFileSync(f, "utf8"));
    for (const m of text.matchAll(
      /(\w+)\s*:\s*Record<\s*(\w+)\s*,\s*string\s*>\s*=\s*\{([\s\S]*?)^\};/gm,
    )) {
      const [, mapName, unionName, body] = m;
      const u = unions.get(unionName);
      if (!u) continue;
      mapsChecked += 1;
      // **والمفتاحُ قد يكون كبيرَ الحروف** (`JOD` · `JO`) — ونمطٌ يقرأ
      // الصغيرةَ وحدَها **يتّهم خريطةً كاملة**. وقع في أوّل تشغيل: أربعةُ
      // بلاغاتٍ كاذبةٍ من تسعة، **والحارسُ الذي يخترع عطباً أغلى من واحدٍ
      // يفوته** — قاعدةٌ مكتوبةٌ في هذا المستودع منذ 2026-08-20.
      const keys = new Set(
        [...body.matchAll(/^\s{2}"?([A-Za-z_][A-Za-z_0-9]*)"?\s*:/gm)].map((x) => x[1]),
      );
      const gone = [...u.members].filter((v) => !keys.has(v));
      if (gone.length)
        missingLabels.push(
          `${f.replace(ROOT + "/", "")}: ${mapName}<${unionName}> — ينقصه ${gone.length}: ${gone.join(", ")}`,
        );
    }
  }
}

if (unionsChecked === 0) {
  console.error("\n✗ check:enum-coverage · **صفرُ اتحادٍ مقروء** — وصفرٌ مقروءٌ عطبٌ لا سلامة\n");
  process.exit(1);
}

if (missingMembers.length || missingLabels.length) {
  console.error("\n✗ check:enum-coverage · **عضوٌ في الخلفية لا يعرفه ما يُرسم للإنسان**\n");
  for (const p of missingMembers) console.error(`    ${p}`);
  for (const p of missingLabels) console.error(`    ${p}`);
  console.error(
    "\n  **والعضوُ الناقصُ لا يكسر شيئاً** — يُرسم مفتاحُه الإنجليزيُّ في شاشةٍ\n" +
      "  عربيةٍ ولا يشكو أحد. أضِف العضوَ واسمَه، أو صرّح جزئيّتَه في `PARTIAL`\n" +
      "  بعلّتها.\n",
  );
  process.exit(1);
}

console.log(
  `✓ check:enum-coverage · كلُّ اتحادٍ يغطّي تعدادَه وكلُّ خريطةٍ تغطّي اتحادَها — ` +
    `${unionsChecked} اتحاداً و${mapsChecked} خريطةً · ${backend.size} تعداداً في الخلفية · ${stamp}Z`,
);
