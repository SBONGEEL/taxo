/** **وظيفتان تشغّلان المجموعةَ نفسَها بمهلتين مختلفتين** — تُوقف الإيداع.
 *
 * ## العلّةُ مقيسةٌ مرّتين لا مفترضة
 *
 * `backend` و`batch-suite` في `ci.yml` **خطواتُهما متطابقةٌ سطراً سطراً**:
 * بيئةُ التشغيل · بناءُ صورة الخلفية · القاعدةُ وRedis · المجموعةُ الكاملة.
 * **فهما عملٌ واحدٌ في موضعين**، ومهلتاهما وصفٌ لِما يحتمله ذلك العمل.
 *
 * **ورُفع أحدُهما وتُرك الآخر**: ٢٠٢٦-٠٩-٠٥ صار `batch-suite` عند ٤٠،
 * و`backend` بقي على ٣٠. **وفي اليوم التالي قُتلت `backend` عند ٣٠د ١٥ث**
 * (التشغيل ‎34027019141) **بينما مرّ أخواها في ١٩د ٤٥ث و١٩د ٠٨ث على الشيفرة
 * نفسِها** — **صفرُ اختبارٍ ساقط، ورفعٌ أُوقف بلا عطب**.
 *
 * **ومهلةٌ تقتل مجموعةً خضراءَ تُقرأ حمرةً** — وهي أخبثُ من حمرةٍ حقيقية،
 * لأن السجلَّ لا يسمّي عطباً يُصلَح.
 *
 * ## ما يمسكه
 *
 * **افتراقَ المهلتين** — لا صغرَهما. **الرقمُ قرارُ المالك، والتساوي قاعدة.**
 *
 * ## وما لا يمسكه — يُقال ولا يُقرأ سكوتُه ضماناً
 *
 * · **لا يحكم أنّ الرقم كافٍ**: أربعون قد تضيق غداً كما ضاقت ثلاثون.
 *   **يقيس التطابقَ لا الكفاية.**
 * · **ولا يقارن الخطوات**: لو افترق العملُ بين الوظيفتين لَبقي صامتاً —
 *   وحينها يصير التساوي هو الخطأ. **والتطابقُ اليومَ قِيس بالعين لا بالأداة.**
 * · **ولا يمسّ `frontends` ولا `docs` ولا `packages`**: أعمالٌ أخرى بأحمالٍ
 *   أخرى، **وإلزامُها برقمٍ واحدٍ يخترع قاعدةً لا علّةَ لها**.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

//: **الجذرُ من `fileURLToPath` لا من `pathname`** — الثاني يكسر على مسارٍ
//: شبكيّ، **وحارسٌ يقرأ صفرَ ملفٍّ يخرج أخضرَ وهو أعمى**.
const ROOT = dirname(fileURLToPath(new URL(".", import.meta.url))).replace(/[\\/]tools$/, "");
const FILE = join(ROOT, ".github", "workflows", "ci.yml");

//: **الوظيفتان اللتان تشغّلان المجموعةَ الكاملة** — بأسمائهما في `ci.yml`.
const TWINS = ["backend", "batch-suite"];

const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
const die = (msg) => {
  console.error(`\n✗ check:ci-timeouts · ${msg}\n`);
  process.exit(1);
};

let text;
try {
  text = readFileSync(FILE, "utf8");
} catch {
  die(`تعذّرت قراءة ${FILE} — **وغيابُ المقروء يوقف ولا يُقرأ سلامة**`);
}

//: يقرأ `timeout-minutes` لوظيفةٍ باسمها: من سطر `  <job>:` حتى الوظيفة
//: التالية على المستوى نفسِه (سطرٌ يبدأ بمسافتين ثمّ اسمٌ ثمّ نقطتان).
function timeoutOf(job) {
  const lines = text.split("\n");
  const head = lines.findIndex((l) => l === `  ${job}:`);
  if (head < 0) return { found: false };
  for (let i = head + 1; i < lines.length; i += 1) {
    if (/^ {2}[A-Za-z][\w-]*:/.test(lines[i])) break; // الوظيفةُ التالية
    const m = lines[i].match(/^ {4}timeout-minutes:\s*(\d+)\s*$/);
    if (m) return { found: true, minutes: Number(m[1]), line: i + 1 };
  }
  return { found: true, minutes: null };
}

const read = TWINS.map((job) => ({ job, ...timeoutOf(job) }));

for (const r of read) {
  if (!r.found) die(`لا وظيفةَ اسمُها \`${r.job}\` في \`ci.yml\` — **اسمٌ بلي**`);
  if (r.minutes === null)
    die(`\`${r.job}\` بلا \`timeout-minutes\` — **وغيابُ الحدِّ ليس حدّاً واسعاً، بل ساعةُ GitHub الافتراضية (٣٦٠)**`);
}

const [a, b] = read;
if (a.minutes !== b.minutes)
  die(
    `المهلتان تفترقان: \`${a.job}\`=${a.minutes} و\`${b.job}\`=${b.minutes}` +
      ` (السطران ${a.line} و${b.line})\n` +
      "  **والوظيفتان تشغّلان المجموعةَ نفسَها بخطواتٍ متطابقة** — فرقمان" +
      " لعملٍ واحدٍ نسختان تفترقان لا معايرتان.\n" +
      "  **وقع مقيساً ٢٠٢٦-٠٩-٠٦**: ٣٠ قتلت مجموعةً خضراءَ عند ٣٠د ١٥ث" +
      " ومرّ أخواها في ١٩د. **حرّكهما معاً.**"
  );

console.log(
  `✓ check:ci-timeouts · المجموعتان بمهلةٍ واحدة (${a.minutes} دقيقة) — ${TWINS.join(" · ")} · ${stamp}Z`
);
