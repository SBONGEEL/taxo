/** `check:fields` — **حقلٌ يحمله العقدُ ولا يملك المشرفُ ضبطَه** (2026-08-31).
 *
 * ## العطبُ الذي بُني له، مقيساً لا مفترَضاً
 *
 * `ServiceTileIn.audience` حقلٌ في العقد منذ اليوم الأول، **واللوحةُ تكتب
 * `audience: "all_riders"` نصّاً** في نداء الإنشاء. فكان كلُّ ما يُنشأ من
 * اللوحة بلاطةَ راكب، **وبلاطةُ الكبتن لا تُبنى من اللوحة أصلاً** — لا
 * بخطأٍ يُرى، بل بحقلٍ محشوٍّ بقيمةٍ واحدة.
 *
 * **ولا حارسَ قائمٌ يراه**: `check:doors` يسأل «أللبابِ زرّ؟» — **والبابُ له
 * زرّ**. `check:config` و`check:published-readers` يسألان عمّا **يُقرأ**، وهذا
 * حقلٌ **يُكتب**. **والبناءُ أخضر، والزرُّ يعمل، والصفُّ يُنشأ** — والناقصُ
 * خيارٌ لم يُعرض قطّ.
 *
 * > **بابٌ بلا زرٍّ يُرى فارغاً؛ وحقلٌ محشوٌّ يُرى عاملاً.** والثاني أخفى.
 *
 * ## ما يمسكه — بحدِّه
 *
 * كلُّ نداءٍ في اللوحة إلى بابٍ **يكتب** (`post`/`put`/`patch`) يُقرأ
 * بمُحلِّل TypeScript، **ويُنظر في حرفيّته الكائنيّة**: كلُّ مفتاحٍ قيمتُه
 * **حرفيّةٌ ثابتة** (نصٌّ أو رقمٌ أو `true/false`) هو حقلٌ **قرّرته الشيفرةُ
 * عن المشرف**.
 *
 * **ولا يُقرأ كلُّ ثابتٍ عطباً** — كثيرٌ منها قرارٌ صحيح: «تُنشأ مخفيّةً
 * دائماً» ثابتٌ مقصود. **فكلُّ ثابتٍ يحمل علّتَه في `DELIBERATE`**، وقائمةٌ
 * بلا أسبابٍ تصير مقبرةً يُلقى فيها كلُّ ما لم يُبنَ.
 *
 * ## وحدُّه مكتوبٌ — يُقرأ قبل أن تُصدَّق خضرتُه
 *
 * **١) لا يمسك ما يُكتب بمفتاحٍ محسوب.** `patch({ [key]: value })` — وهو
 * شكلٌ قائمٌ في شاشة الإعدادات — **لا يراه هذا الحارس**، لأن المفتاحَ ليس
 * في المصدر أصلاً. فخُضرتُه ليست شهادةً بأن كلَّ حقلٍ يُضبط.
 *
 * **٢) ولا يسأل «أهذا الثابتُ صحيح؟»** — يسأل «أهو **مقصود**؟». والفرقُ هو
 * كلُّ ما يستطيع حارسٌ نصّيٌّ قولَه: **الثابتُ المكتوبُ بعلّته قرارٌ،
 * والمكتوبُ بلا علّةٍ سهوٌ**.
 *
 * **٣) وقيمةٌ من مُعامل الدالّة تمرّ**: `country_code: country` ليست ثابتاً.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { certify } from "./certify.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const PANEL = join(ROOT, "admin-panel", "src");

function loadTypeScript() {
  try {
    return createRequire(new URL("../admin-panel/package.json", import.meta.url))(
      "typescript",
    );
  } catch {
    console.error("✗ لم يوجد `typescript` في اللوحة — الحارسُ لا يقيس.");
    process.exit(1);
  }
}
const ts = loadTypeScript();

/** **ثوابتُ مقصودةٌ بعللها** — `دالّة.حقل` ← لمَ قرّرتها الشيفرةُ لا المشرف. */
const DELIBERATE = new Map([
  [
    "createServiceTile.status",
    "تُنشأ مخفيّةً دائماً — **فلا تظهر بلاطةٌ نصفُ مضبوطةٍ لأحد**، والإشعالُ فعلٌ ثانٍ بعد ضبطها.",
  ],
  [
    "createPromoBanner.is_active",
    "تُنشأ مطفأةً للعلّة نفسِها — والنافذةُ والعنوانُ يُضبطان قبل أن يراها أحد.",
  ],
  [
    "createPromoBanner.title",
    "عنوانٌ نائبٌ يُستبدل في المحرِّر الذي يُفتح فوراً — واللافتةُ تُنشأ ثم تُحرَّر، فلا نموذجَ قبل الصفّ.",
  ],
  [
    "createPromoBanner.audience",
    "تابعٌ للعنوان النائب — يُضبط في المحرِّر نفسِه قبل الإشعال.",
  ],
  [
    "createPromoBanner.link_kind",
    "«لا تفتح شيئاً» هو الحالُ الآمن — ولافتةٌ تُولد بمقصدٍ لم يُختر تَعِد بشاشةٍ لم تُقرَّر.",
  ],
]);

const isPanelSource = (name) => /\.tsx?$/.test(name);

function sources(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    return statSync(path).isDirectory()
      ? sources(path)
      : isPanelSource(entry)
        ? [path]
        : [];
  });
}

/** **أبوابُ الكتابة وحدَها** — تُقرأ من `endpoints.ts` لا تُكتب هنا.
 *
 * كلُّ تصديرٍ جسمُه ينادي `api.post` أو `api.put` أو `api.patch` أو `upload`.
 */
function writingDoors() {
  const source = readFileSync(join(PANEL, "api", "endpoints.ts"), "utf-8");
  const names = new Set();
  const re =
    /export\s+(?:const|async function|function)\s+(\w+)[\s\S]*?(?=\nexport\s|\n\/\*\*|$)/g;
  let match;
  while ((match = re.exec(source)) !== null) {
    if (/\bapi\.(post|put|patch)\b|\bupload</.test(match[0])) names.add(match[1]);
  }
  return names;
}

const doors = writingDoors();
const findings = [];
const seen = new Set();

for (const file of sources(PANEL)) {
  if (file.endsWith(join("api", "endpoints.ts"))) continue;
  const text = readFileSync(file, "utf-8");
  const tree = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);

  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
      const door = node.expression.text;
      if (doors.has(door)) {
        for (const argument of node.arguments) {
          if (!ts.isObjectLiteralExpression(argument)) continue;
          for (const property of argument.properties) {
            if (!ts.isPropertyAssignment(property)) continue;
            const key = property.name.getText(tree);
            const value = property.initializer;
            const literal =
              ts.isStringLiteral(value) ||
              ts.isNumericLiteral(value) ||
              value.kind === ts.SyntaxKind.TrueKeyword ||
              value.kind === ts.SyntaxKind.FalseKeyword;
            if (!literal) continue;
            const id = `${door}.${key}`;
            seen.add(id);
            if (DELIBERATE.has(id)) continue;
            const { line } = tree.getLineAndCharacterOfPosition(
              property.getStart(tree),
            );
            findings.push({
              id,
              where: `${relative(ROOT, file).replace(/\\/g, "/")}:${line + 1}`,
              value: value.getText(tree),
            });
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(tree);
}

if (findings.length > 0) {
  console.error(
    `\n✗ ${findings.length} حقلاً تكتبه الشيفرةُ ثابتاً ولا يملك المشرفُ ضبطَه:\n`,
  );
  for (const f of findings) console.error(`   ${f.id} = ${f.value}   (${f.where})`);
  console.error(
    "\n  إمّا أن يصله ضابطٌ في الشاشة، وإمّا أن يُضاف إلى `DELIBERATE` في tools/check-fields.mjs",
  );
  console.error("  **بعلّته نصّاً** — فثابتٌ بعلّةٍ قرار، وبلا علّةٍ سهو.\n");
  process.exit(1);
}

// **والعلّةُ التي زالت تُحذف**: قائمةُ أعذارٍ لا تُنظَّف تصير كذباً
const stale = [...DELIBERATE.keys()].filter((id) => !seen.has(id));
if (stale.length > 0) {
  console.error("\n✗ عللٌ لثوابتَ لم تعد مكتوبةً — تُحذف من `DELIBERATE`:\n");
  for (const id of stale) console.error(`   ${id}`);
  console.error("");
  process.exit(1);
}

certify(
  "check:fields",
  `✓ كلُّ ثابتٍ يُكتب في أبواب الكتابة (${seen.size}) يحمل علّتَه — ` +
    `وأبوابُ الكتابة ${doors.size}`,
);
