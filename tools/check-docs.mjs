#!/usr/bin/env node
// حارسُ الملفّات الخمسة — «نقلٌ لا تحرير»، وستُّ مقايسَ بالاتجاهين.
//
// الشكلُ الذي وُجد له: `CLAUDE.md` بلغ ٣٨٦ ألفَ حرف، فصار حملُه في كلِّ جلسةٍ
// أكبرَ ممّا يُحتمل. فنُقل ٨٩٪ منه إلى أربعة ملفّاتٍ **مربوطةٍ بشروطٍ صريحة**،
// لا «مراجعَ اختيارية». وخطرُ ذلك واحد: **منقولٌ لا طريقَ إليه** — وهو «بابٌ
// بلا زرّ» في ثوب توثيق، ولا يفشل به شيءٌ أبداً.
//
// ولا يُصدَّق حارسٌ حتى يُقاس في الاتجاهين: يمسك عطباً **مصنوعاً**، ويصمت على
// شجرةٍ **سليمة**. وصمتُه يحتاج إثباتاً كما يحتاجه صياحُه — **فيُعلن كم عنواناً
// قرأ، وصفرٌ مقروءٌ يُقرأ عطباً لا سلامة**.
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

// حروفُ `CLAUDE.md` قبل النقل، مقيسةً لا مقدَّرة. وهو الرقمُ الذي تُطابَق به
// الملفّاتُ الخمسة: `sum(5) − المكتوبُ الجديد` يجب أن يساويَه بالحرف.
const ORIGIN = 386023;
const ORIGIN_LINES = 5422;

// **وما حُذف من الأصل بعد النقل يُعلَن هنا بعلّته، ولا يُطرح صامتاً.**
// النقلُ نفسُه لم يحذف حرفاً؛ وما بعده قد يحذف بقرارٍ صريح — **فيُكتب**، كي
// يُقرأ في الفرق ويُسأل عنه. وطرحُ العددِ من الأصل بلا سطرٍ يقول لماذا هو
// «تعديلُ الحارس ليمرّ» — وهو الطريقُ الذي تُفرَّغ به المطلقاتُ بلا أن يقرّر
// أحدٌ إفراغَها.
const REMOVED = [
  {
    chars: 148,
    lines: 5,
    what: "«### وفي بداية كلِّ جلسة» — نصُّه السابق: «تُقرأ الثلاثة قبل أيِّ شيء»",
    why:
      "قرارُ المالك 2026-08-25: استبدالٌ لا إضافة. قِيس النصُّ السابق في اليوم " +
      "نفسِه فسقط — وكيلٌ فتح HANDOFF.md ٥٣٩ سطراً من ١٠١٢ وقال إنها «لم تغيّر " +
      "الجوابَ بحرف»، ولم يفتح SPEC.md البتّة. وتركُه إلى جانب الشروط الأربعة " +
      "يترك بابين يقولان أمرين.",
  },
];
const REMOVED_CHARS = REMOVED.reduce((n, r) => n + r.chars, 0);
const REMOVED_LINES = REMOVED.reduce((n, r) => n + r.lines, 0);
const EXPECT_CHARS = ORIGIN - REMOVED_CHARS;
const EXPECT_LINES = ORIGIN_LINES - REMOVED_LINES;

// والعددُ وحدَه لا يكفي: **تبادلُ نصَّين متساويَي الطول بين ملفّين يمرّ منه**.
// فهذه بصمةُ الأسطر مرتَّبةً — تُثبت أن **مجموعةَ الأسطر هي هي**، لا أن
// مجموعَها هو هو. والاثنان معاً هما «لا حرفَ تغيّر».
//
// **وهي تُعاد كتابتُها كلَّما تغيّر `REMOVED`** — ولا تُشتقّ من شيء. فحارستُها
// أن تغييرَها يظهر في الفرق سطراً واحداً بجانب علّةٍ مكتوبة؛ **ومن غيّرها بلا
// إضافةِ سببٍ في `REMOVED` فقد كتب العلّةَ في لا مكان**.
const ORIGIN_DIGEST = "0af01cbf160ba7f2b68dda39eef70d431a4bf690bad338c8989f05dd1051a9aa";

// سقفُ `CLAUDE.md` — بهامشٍ لا عند حافّة. وتضييقُه يدفع إلى نقل قواعدَ عاملة،
// وذاك خسارةٌ لا ربح (قرارُ المالك 2026-08-25).
const CEILING = 60000;

const MAIN = "CLAUDE.md";
const MOVED = ["ARCHITECTURE.md", "PATTERNS.md", "GUARDS.md", "STATE.md"];
const ALL = [MAIN, ...MOVED];

// النصُّ المكتوبُ حديثاً — لا المنقول — محصورٌ بين هاتين العلامتين. وهو الوحيدُ
// الذي يُطرح من المجموع، فيُقاس النقلُ وحدَه.
const MARK_O = "<!--جديد-->";
const MARK_C = "<!--/جديد-->";
const NEW_RE = new RegExp(`${MARK_O}[\\s\\S]*?${MARK_C}\\n*`, "g");

const ARROW = " → `";

const read = (f) => readFileSync(join(ROOT, f), "utf8");
const fail = [];
const say = (s) => process.stdout.write(s + "\n");

// ── العناوينُ المنقولة: `##`..`####`، وما كان منها داخل اقتباس (`> ###`) ──
const headingOf = (line) => {
  const m = /^(?:>\s*)?#{2,4}\s+(.*\S)\s*$/.exec(line);
  return m ? m[1] : null;
};

// **عناوينُ الملفّات صنفان، والقاعدتان تُفرّقان بينهما** (قرارُ المالك 2026-08-25):
//
//   `headings`  — **المنقول**: ما خارج علامتَي «جديد». عليه القاعدةُ الأولى،
//                 فكلُّ منقولٍ يجب أن يذكره الفهرس.
//   `authored`  — **المكتوبُ جديداً**: ما داخلَهما. **يُبلَغ بالفهرس ولا
//                 يُلزَم به** — إلزامُه يجعل كلَّ عنوانِ خبرٍ يومِيٍّ سطرَ فهرس،
//                 والفهرسُ الذي يطول بكلِّ يومٍ يصير قائمةً يُمرّ عليها.
//
// **والعلّةُ مقيسةٌ لا محتاطة**: كُتب «الشكلُ السادسَ عشر» في `PATTERNS.md`
// داخل العلامتين، **فلم يكن يُبلَغ إليه بفهرسٍ البتّة** — وسطرُ فهرسٍ يشير
// إليه كان يسقط «موضعٌ بلا شكل» لأن العنوانَ يُطرح قبل الجمع. **وذاك يُفرِّغ
// النقلَ من معناه**: نُقل ليُبلَغ إلى ما نُقل، فصار الجديدُ وحدَه بلا طريق.
//
// **والقياسُ السادسُ نفسُه كان يجب أن يمسكه فلم يمسكه** — لأنه يسأل عن
// **المنقول** لا عن **المكتوب**؛ وهو «حارسٌ صادقٌ في نطاقه، وسؤالُه أضيقُ
// ممّا يُقرأ منه».
const headings = new Map(); // منقول → Set(text)
const authoredHeadings = new Map(); // مكتوبٌ جديداً → Set(text)
let headingCount = 0;
let authoredHeadingCount = 0;
const collectHeadings = (s) => {
  const set = new Set();
  for (const line of s.split("\n")) {
    const h = headingOf(line);
    if (h) set.add(h);
  }
  return set;
};
for (const f of MOVED) {
  const text = read(f);
  const moved = collectHeadings(text.replace(NEW_RE, ""));
  const fresh = new Set([...collectHeadings(text)].filter((h) => !moved.has(h)));
  headings.set(f, moved);
  authoredHeadings.set(f, fresh);
  headingCount += moved.size;
  authoredHeadingCount += fresh.size;
}

// ── سطورُ الفهرس في CLAUDE.md ──
const mainText = read(MAIN);
const indexRows = [];
for (const line of mainText.split("\n")) {
  if (!line.startsWith("- ") || !line.endsWith("`")) continue;
  const i = line.lastIndexOf(ARROW);
  if (i < 0) continue;
  indexRows.push({
    text: line.slice(2, i),
    file: line.slice(i + ARROW.length, -1),
  });
}

// ١ — لا شكلَ بلا موضع: كلُّ عنوانٍ منقولٍ يذكره الفهرس.
const indexed = new Map(MOVED.map((f) => [f, new Set()]));
for (const r of indexRows) if (indexed.has(r.file)) indexed.get(r.file).add(r.text);
for (const f of MOVED)
  for (const h of headings.get(f))
    if (!indexed.get(f).has(h)) fail.push(`شكلٌ بلا موضع: «${h}» في ${f} لا يذكره الفهرس`);

// ٢ — لا موضعَ بلا شكل: كلُّ سطرِ فهرسٍ يشير إلى ملفٍّ وعنوانٍ موجودَين حرفياً.
//     **والعنوانُ يُطلب في الصنفين** — منقولاً كان أو مكتوباً جديداً: السؤالُ
//     «أثمّة عنوانٌ بهذا النصّ؟» لا «أهو منقول؟». وسطرٌ يشير إلى ما لا وجودَ
//     له يبقى ساقطاً كما كان.
for (const r of indexRows) {
  if (!headings.has(r.file)) fail.push(`موضعٌ بلا ملفّ: سطرُ فهرسٍ يشير إلى «${r.file}»`);
  else if (!headings.get(r.file).has(r.text) && !authoredHeadings.get(r.file).has(r.text))
    fail.push(`موضعٌ بلا شكل: «${r.text}» ليس عنواناً في ${r.file}`);
}

// ٣ — الرقمان، ثمّ البصمة.
let sum = 0;
let authored = 0;
const sizes = {};
let movedText = "";
for (const f of ALL) {
  const t = read(f);
  sizes[f] = t.length;
  sum += t.length;
  for (const m of t.matchAll(NEW_RE)) authored += m[0].length;
  movedText += t.replace(NEW_RE, ""); // وصلٌ بلا فاصلٍ: كلُّ قطعةٍ تنتهي بسطرٍ جديد
}
const movedChars = sum - authored;
if (movedChars !== EXPECT_CHARS)
  fail.push(`الرقمان لا يتطابقان: المنقولُ ${movedChars} والمنتظَرُ ${EXPECT_CHARS} (الأصلُ ${ORIGIN} ناقصَ ${REMOVED_CHARS} معلَنةً) — فرقٌ ${movedChars - EXPECT_CHARS}`);

const movedLines = movedText.split("\n");
const digest = createHash("sha256").update(movedLines.slice().sort().join("\n"), "utf8").digest("hex");
if (movedLines.length !== EXPECT_LINES)
  fail.push(`أسطرُ المنقول ${movedLines.length} والمنتظَرُ ${EXPECT_LINES}`);
if (digest !== ORIGIN_DIGEST)
  fail.push(`بصمةُ الأسطر تخالف الأصل — سطرٌ تغيّر أو انتقل نصُّه: ${digest.slice(0, 16)}…`);

// ٤ — سقفُ CLAUDE.md.
if (sizes[MAIN] > CEILING)
  fail.push(`CLAUDE.md ${sizes[MAIN]} حرفاً — فوق السقف ${CEILING}`);

// ٥ — صمتُ الحارس يحتاج إثباتاً: صفرٌ مقروءٌ عطبٌ لا سلامة.
if (headingCount === 0) fail.push("صفرُ عناوينَ مقروءة — الحارسُ لا يقرأ شيئاً");
if (indexRows.length === 0) fail.push("صفرُ سطورِ فهرسٍ مقروءة — الحارسُ لا يقرأ شيئاً");

// ٦ — لا منقولَ بلا طريقٍ إليه: لكلِّ ملفٍّ **شرطٌ** يوجب فتحه، مكتوبٌ في
//     CLAUDE.md بصيغة «قبل أن … | `FILE` |». والفهرسُ وحدَه لا يكفي لملفٍّ
//     أكثرُه نثرٌ بلا عناوين — ولا الشرطُ وحدَه يكفي لعنوانٍ بعينه.
for (const f of MOVED) {
  const row = mainText
    .split("\n")
    .find((l) => l.startsWith("| **قبل أن") && l.includes(`\`${f}\``));
  if (!row) fail.push(`منقولٌ بلا طريق: ${f} لا شرطَ يوجب فتحه في CLAUDE.md`);
}

// ── التقرير ──
say("");
say(`  الأصلُ قبل النقل   ${ORIGIN.toLocaleString("en")}`);
say(`  مجموعُ الخمسة      ${sum.toLocaleString("en")}`);
say(`  المكتوبُ الجديد    ${authored.toLocaleString("en")}`);
say(`  المحذوفُ معلَناً    ${REMOVED_CHARS.toLocaleString("en")}  (${REMOVED.length} بنداً بعلّته)`);
say(`  المنقول            ${movedChars.toLocaleString("en")}  ${movedChars === EXPECT_CHARS ? "= الأصل ناقصَ المعلَن ✓" : "✗"}`);
say(`  بصمةُ الأسطر       ${digest.slice(0, 16)}…  ${digest === ORIGIN_DIGEST ? "= الأصل ✓" : "✗"}`);
say("");
for (const f of ALL)
  say(`  ${f.padEnd(18)} ${String(sizes[f].toLocaleString("en")).padStart(9)}${f === MAIN ? `   (السقف ${CEILING.toLocaleString("en")})` : ""}`);
say("");
say(
  `  قُرئ: ${headingCount} عنواناً منقولاً · ${authoredHeadingCount} مكتوباً جديداً` +
    ` · ${indexRows.length} سطرَ فهرس · ${MOVED.length} شروطٍ`,
);

if (fail.length) {
  say("");
  for (const m of fail) say(`  ✗ ${m}`);
  say("");
  say(`  ✗ ${fail.length} عطباً.`);
  process.exit(1);
}
say("");
say("  ✓ لا شكلَ بلا موضع، ولا موضعَ بلا شكل، ولا منقولَ بلا طريق — ولا حرفَ تغيّر.");
