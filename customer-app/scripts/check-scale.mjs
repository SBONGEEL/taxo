/** حارسٌ ضد الصنف الذي يسقط صامتاً.
 *
 * سلّمُ `DESIGN.md` يمنع **القيمة الخاطئة**: `p-4` لا وجود له فلا يُقرَّب أحدٌ
 * 16px إلى الافتراضي. لكنه لا يمنع **القيمة الناقصة**: صنفٌ خارج السلّم
 * (`size-33` وليس 33 في `spacing`) لا يرفضه Tailwind — يتجاهله بصمت، فيخرج
 * العنصر بلا مقاسٍ أصلاً ولا يقول أحدٌ شيئاً. وهذا وقع فعلاً في أول جلسةٍ
 * بنت الرئيسية: أربعةُ أصنافٍ سقطت وبُني المشروع أخضرَ.
 *
 * فيقرأ هذا السكربت السلالم من `tailwind.config.js` نفسه — لا نسخةً ثانية
 * تفترق عنه — ويمسح المصدر بحثاً عن كل صنفٍ رقميٍّ لا يقابله مفتاح.
 *
 * يعمل ضمن `npm run build` قبل `tsc`، فلا يمر بناءٌ بصنفٍ ساقط.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const config = (await import(pathToFileURL(join(process.cwd(), "tailwind.config.js")))).default;
const theme = config.theme;

// بادئةٌ ← السلّم الذي تقرأ منه. الافتراضاتُ مستبدَلةٌ بالكامل، فأي مفتاح
// خارج هذه الجداول لا يُولَّد له شيء.
const SCALES = {
  spacing: theme.spacing,
  fontSize: theme.fontSize,
  borderRadius: theme.borderRadius,
};

const PREFIXES = [
  // [البادئة، السلّم]
  ["text", "fontSize"],
  ["rounded", "borderRadius"],
  ...["p", "px", "py", "pt", "pb", "ps", "pe", "m", "mx", "my", "mt", "mb", "ms", "me",
      "gap", "gap-x", "gap-y", "w", "h", "size", "top", "bottom", "start", "end",
      "inset", "inset-x", "inset-y", "space-x", "space-y"].map((p) => [p, "spacing"]),
];

// أسماءٌ لا تأتي من السلالم: قيمٌ خاصة بـTailwind أو مفاتيحُ `extend`
const ALLOWED = new Set([
  "auto", "full", "none", "px", "screen", "min", "max", "fit", "0", "reverse",
  "device", "drawer", "side", "side-sm", "status", "nav", "header", "toast",
]);

function sources(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    return statSync(path).isDirectory()
      ? sources(path)
      : /\.tsx?$/.test(path)
        ? [path]
        : [];
  });
}

const problems = [];
for (const file of sources(join(process.cwd(), "src"))) {
  const text = readFileSync(file, "utf8");
  for (const [prefix, scale] of PREFIXES) {
    // يتجاهل القيم الاعتباطية `p-[12px]` — تلك صريحةٌ ومقصودة
    const pattern = new RegExp(`\\b-?${prefix}-([0-9]+(?:\\.[0-9]+)?)\\b(?!\\[)`, "g");
    for (const match of text.matchAll(pattern)) {
      const key = match[1];
      if (ALLOWED.has(key)) continue;
      if (SCALES[scale][key] === undefined) {
        problems.push(`${file}: ${prefix}-${key} — ليس في سلّم ${scale}`);
      }
    }
  }
}

// سلّمُ `cn` في `lib/utils.ts` نسخةٌ ثانيةٌ من مقاسات الخط، ووجودُها ضرورة:
// `tailwind-merge` لا يعرف سلّمنا فيخلط المقاسَ باللون ويُسقط أحدهما وقت
// التشغيل — والبناءُ يبقى أخضر. فما دامت نسخةً، تُقارَن هنا بالأصل.
const utils = readFileSync(join(process.cwd(), "src", "lib", "utils.ts"), "utf8");
const declared = utils.match(/const FONT_SIZES = \[([\s\S]*?)\];/);
if (declared === null) {
  problems.push("src/lib/utils.ts: لم أجد `FONT_SIZES` — لا يمكن التحقق من سلّم الدمج");
} else {
  const listed = [...declared[1].matchAll(/"([0-9.]+)"/g)].map((m) => m[1]);
  const expected = Object.keys(theme.fontSize);
  const missing = expected.filter((key) => !listed.includes(key));
  const extra = listed.filter((key) => !expected.includes(key));
  for (const key of missing) {
    problems.push(`src/lib/utils.ts: text-${key} ناقصٌ من FONT_SIZES — سيُقرأ لوناً`);
  }
  for (const key of extra) {
    problems.push(`src/lib/utils.ts: text-${key} في FONT_SIZES وليس في السلّم`);
  }
}

if (problems.length > 0) {
  console.error("أصنافٌ خارج سلّم DESIGN.md — ستسقط بصمت:\n");
  for (const problem of [...new Set(problems)]) console.error("  " + problem);
  console.error(
    "\nأضف القيمة إلى `design/DESIGN.md` §6 ثم انسخها إلى tailwind.config.js،" +
      " أو استعمل مقاساً من السلّم.",
  );
  process.exit(1);
}
console.log("✓ كل الأصناف الرقمية داخل سلّم DESIGN.md");
