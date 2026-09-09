/** **نسبةُ عمولةٍ مكتوبةٌ رقماً في نصٍّ يراه إنسان** — تُوقف البناءَ وتُسمّي موضعها.
 *
 * ## العلّةُ مقيسةٌ لا مفترضة (٢٠٢٦-٠٩-٠٦)
 *
 * عرضت الصفحةُ **ثلاثةَ أرقامٍ متناقضةٍ في شاشةٍ واحدة**: عدّادٌ حيٌّ يقول
 * «٢» (من `commission_settings`)، وسطرٌ تحته يقول «صفر عمولة»، وبطاقةُ شبكةٍ
 * تقول «عمولة 0% بالاشتراك» — **نصوصٌ ثابتةٌ بليت كلٌّ في وقته**.
 *
 * **وأخطرُ من التناقض أن الوعدَ انفصل عن الشيفرة**: البطاقتان قالتا «الأجرة
 * له **كاملة**»، **وهي صادقةٌ فقط والنسبةُ صفر** — ولمّا أُشعلت العمولةُ
 * بـ`1.50` صار النصُّ يَعِد بما لا يقع، **ولا شيءَ يصيح**.
 *
 * ## ما يمسكه
 *
 * **رقمٌ ملتصقٌ بعلامة نسبةٍ داخل نصٍّ عربيٍّ معروض**، أو **وعدٌ مطلقٌ**
 * («صفر عمولة» · «بلا عمولة» · «الأجرة كاملة») بلا شرطٍ يقيّده.
 *
 * ## وما لا يمسكه — **يُقال ولا يُقرأ سكوتُه ضماناً**
 *
 * · **الأرقامَ المحسوبة**: `${digits(commission)}٪` تمرّ — **الحارسُ يمسك
 *   الوعودَ لا الأوصاف** (قرارُ المالك). فقيمةٌ تُقرأ من بيانات ثمّ تُنسَّق
 *   ليست نسبةً مخبوزة.
 * · **ولا يقرأ قواعدَ CSS**: `50%` في تدرّجٍ أو `keyframes` ليست عمولة،
 *   **وحارسٌ يصيح عليها يُطفأ** فيسقط معه ما يمسكه حقاً.
 * · **ولا يقرأ التعليقات**: تعليقٌ يشرح لماذا مُنع الرقمُ ليس رقماً معروضاً.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

//: **الجذرُ من `fileURLToPath` لا من `pathname`**: الثاني يترك `%20`
//: ويكسر على مسارٍ شبكيّ — **وأوّلُ تشغيلٍ قرأ صفرَ ملفٍّ وخرج أخضر**.
const ROOT = dirname(fileURLToPath(new URL(".", import.meta.url))).replace(/[\\/]tools$/, "");

//: **مواضعُ النصِّ المعروض وحدَها** — لا الخلفيةُ ولا الاختباراتُ ولا الوثائق
//:
//: **⚠ و`landing/` خارجها بقصد، وحدُّ ذلك يُكتب**: هو **مخرَجُ بناء `site`**
//: والجذرُ الذي يخدمه نجينكس فعلاً (قرارُ المالك ٢٠٢٦-٠٩-٠٥: «يبنيه
//: الخادمُ… ولا يُودَع مخرَجُ بناءٍ في الشجرة»). **فمسحُه يعني اتّهامَ نسخةٍ
//: قديمةٍ بعطبٍ صُحّح في مصدرها**، والحارسُ يحرس المصدر.
//:
//: **لكنّ خُضرتَه لا تقول شيئاً عمّا يُعرض على الناس** — الشكلُ العاشر
//: بحرفه. **ومقيسٌ ٢٠٢٦-٠٩-٠٦**: المصدرُ أخضر، و`taxo.tajora.ly` يَعِد
//: **سبعَ مرّاتٍ** بصفر عمولةٍ والعمولةُ ٢٪. **وما يسدّ هذه الفجوةَ الرفعُ
//: لا الحارس** — البوّابةُ الخامسةُ تقرأ الصفحةَ من متصفّح.
const ROOTS = ["site", "customer-app/src", "driver-app/src", "admin-panel/src"];
const SKIP = new Set(["node_modules", "dist", "build", "public", "assets-src", "android", "ios"]);
const EXTS = new Set([".html", ".tsx", ".ts", ".js", ".jsx"]);

//: **استثناءاتٌ مصرَّحةٌ بعللها** — ولا استثناءَ بلا سبب
const DELIBERATE = [
  {
    file: "driver-app/src/screens/Collect.tsx",
    text: '"0٪ حالياً"',
    why:
      "**وصفُ حالٍ محسوبةٍ لا وعدٌ مخبوز** (قرارُ المالك ٢٠٢٦-٠٩-٠٦): يُعرض " +
      "**حين تكون القيمةُ صفراً فعلاً** (`commission === 0`)، والقيمةُ من " +
      "الخلفية. **والحارسُ يمسك الوعودَ لا الأوصاف.**",
  },
  {
    file: "driver-app/src/screens/RideDetails.tsx",
    text: '"0٪ حالياً"',
    why: "نفسُ علّة `Collect.tsx` — قيمةٌ محسوبةٌ تُوصَف، لا نسبةٌ تُوعَد بها.",
  },
  {
    file: "site/index.html",
    text: "والسوق يبدأ من",
    why:
      "**رقمٌ عن السوق لا عنّا** (نصُّ المالك ٢٠٢٦-٠٩-٠٦: «ومعها والسوق " +
      "يبدأ من ٢٥٪»). **والقاعدةُ تحرس نسبتَنا** — أن تتبع الإعدادات فلا " +
      "تبلى. **وحدُّ السوق ليس في إعداداتنا أصلاً** فلا مصدرَ يُقرأ منه، " +
      "**ولا يتغيّر بتبديل المالك نسبتَه**. وهو **بلا تسمية منافسٍ وبلا حدٍّ " +
      "أعلى** كما اشترط.",
  },
];

const ARABIC = /[؀-ۿ]/;
const PCT = /(?<![0-9.])\d{1,3}(?:[.,]\d+)?\s*[%٪]/;
const ABSOLUTE = /(صفر|بلا|بدون)\s*عمول|الأجرة\s*(له|لك)\s*كاملة|عمولة\s*[٠0]\s*[%٪]/;
const CONDITION = /ما دام|ما دامت|سارياً|ساريةً|حالياً|بالنسبة المعلنة/;

const CSS_HINT =
  /keyframes|transform|translate|gradient|box-shadow|inset|opacity|scale\(|calc\(|stdDeviation|animation|border-radius|flex:|line-height|font-size|width:|height:|top:|left:|right:|bottom:|background:/;

function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    if (SKIP.has(name) || name.startsWith(".")) continue;
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (EXTS.has(name.slice(name.lastIndexOf(".")))) out.push(full);
  }
  return out;
}

/** نصٌّ يراه إنسان: يُنزع التعليقُ والنمطُ والوسم. */
function visible(file, line) {
  let s = line.trim();
  if (!s) return "";
  // تعليقاتُ الشيفرة — ليست نصّاً معروضاً
  // **وتعليقُ JSX منها**: `{/* … */}` شرحٌ للقارئ لا نصٌّ يُرسم،
  // **وحارسٌ يصيح على تعليقٍ يشرح القاعدةَ نفسَها يُطفأ**.
  if (/^(\/\/|\/\*|\*|#|<!--|\{\/\*)/.test(s)) return "";
  if (file.endsWith(".html")) {
    if (CSS_HINT.test(s) && !ARABIC.test(s.replace(/<[^>]*>/g, " "))) return "";
    s = s.replace(/style="[^"]*"/g, " ").replace(/<[^>]*>/g, " ");
  } else {
    if (CSS_HINT.test(s) && !ARABIC.test(s)) return "";
  }
  return s;
}

const bad = [];
let scanned = 0;
for (const rootDir of ROOTS) {
  for (const file of walk(join(ROOT, rootDir))) {
    const rel = relative(ROOT, file).replace(/\\/g, "/");
    const text = readFileSync(file, "utf8");
    scanned += 1;
    const lines = text.split("\n");
    // **وتعليقُ الكتلة أسطرٌ لا سطر** (ثغرةٌ مقيسةٌ ٢٠٢٦-٠٩-٠٩): `visible`
    // تُسقط السطرَ الذي **يبدأ** بعلامة تعليق، وسطورُ الكتلة التاليةُ تبدأ
    // بنصٍّ عاديّ — **فشرحٌ يشرح هذه القاعدةَ نفسَها اتُّهم بها**. فتُتتبَّع
    // الكتلةُ من `/*` إلى `*/` ويُسقَط ما بينهما.
    let inBlock = false;
    lines.forEach((raw, i) => {
      const opens = raw.lastIndexOf("/*");
      const closes = raw.lastIndexOf("*/");
      const wasInBlock = inBlock;
      if (inBlock) {
        if (closes !== -1) inBlock = false;
      } else if (opens !== -1 && (closes === -1 || closes < opens)) {
        inBlock = true;
      }
      if (wasInBlock) return;
      const s = visible(rel, raw);
      if (!s || !ARABIC.test(s)) return;
      const exempt = DELIBERATE.find((d) => rel === d.file && raw.includes(d.text));
      if (exempt) return;

      // **والجملةُ تُقرأ بجوارها لا وحدَها**: موضوعُها قد يسبقها بسطر
      // (`title: "البقشيش"` فوق `hint`)، **وشرطُها قد يلحقها** («صفر عمولة
      // ما ⏎ دام اشتراكك سارياً»). **وسطرٌ يُقرأ معزولاً يبتر أحدَهما**
      // فيتّهم نصّاً صادقاً — وحارسٌ يتّهم السليمَ يُطفأ.
      const around = [lines[i - 2], lines[i - 1], raw, lines[i + 1]]
        .filter(Boolean)
        .join(" ");

      // **والبقشيشُ خارجَ هذا الباب أصلاً**: «بلا عمولةٍ عليه» **حقيقةٌ
      // بنيويةٌ لا وعدٌ يتبع نسبة** (`types.ts`: «الدخلُ الوحيد بلا عمولةٍ
      // عليه») — **تبقى صادقةً ولو صارت النسبةُ ٥٪**.
      if (/بقشيش|\btips?\b/i.test(around)) return;

      const near = /عمول|اشتراك|المشترِك|أجرة/.test(s);
      if (PCT.test(s) && near) {
        bad.push([rel, i + 1, "نسبةٌ مكتوبةٌ رقماً", s.slice(0, 130)]);
      } else if (ABSOLUTE.test(s)) {
        // **الشرطُ يُقرأ في الجملة نفسِها لا في جوارها** (كشفه النقضُ
        // ٢٠٢٦-٠٩-٠٦): «صفر عمولة للكبتن.» فوق سطرٍ فيه «ما دام اشتراكه
        // سارياً» **مرّ** — لأن الشرطَ وُجد في النافذة لا في الجملة.
        // **ونافذةٌ سخيّةٌ تُعبِر كلَّ وعدٍ مطلقٍ بجواره سطرٌ مقيَّد.**
        //
        // **ويُوصَل بما بعده فقط إن لم ينتهِ**: الجملةُ المقسومةُ باللفّ
        // تبقى واحدةً، والمنتهيةُ بنقطةٍ جملةٌ قائمةٌ بذاتها.
        const ended = /[.؟!]\s*$/.test(s);
        const joined = ended ? s : s + " " + (lines[i + 1] ?? "");
        const sentence =
          joined
            .split(/(?<=[.؟!])\s+/)
            .find((part) => ABSOLUTE.test(part)) ?? joined;
        if (!CONDITION.test(sentence)) {
          bad.push([rel, i + 1, "وعدٌ مطلقٌ بلا شرط", s.slice(0, 130)]);
        }
      }
    });
  }
}

// **صفرٌ مقروءٌ عطبٌ لا سلامة**: حارسٌ لم يفتح ملفّاً **لا يشهد بشيء**،
// وخُضرتُه أخطرُ من حمرته لأنها تُقرأ ضماناً. **ووقع في أوّل تشغيل.**
if (scanned === 0) {
  console.error(
    `\n✗ لم يُقرأ ملفٌّ واحد من ${ROOTS.join(" · ")} — **صفرٌ مقروءٌ عطبٌ لا سلامة**.` +
      `\n  الجذرُ المقروء: ${ROOT}\n`,
  );
  process.exit(1);
}

const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
if (bad.length) {
  console.error("\n✗ **نسبةُ عمولةٍ مكتوبةٌ في نصٍّ يراه إنسان** — والنسبةُ تُقرأ من");
  console.error("  `commission_settings` وحدَها، فتبديلُها من اللوحة يتبعه كلُّ شيء.\n");
  for (const [rel, ln, why, s] of bad) {
    console.error(`    ${rel}:${ln}`);
    console.error(`      [${why}] ${s}`);
  }
  console.error(
    "\n  يُوصَل بالباب (`data-site` أو قيمةٌ من الخلفية)، أو يُقيَّد بشرطٍ" +
      "\n  («ما دام اشتراكك سارياً»)، أو يُدرَج في `DELIBERATE` **بعلّته نصّاً**.\n",
  );
  process.exit(1);
}
console.log(
  `✓ check:commission-text · لا نسبةَ مكتوبةً ولا وعدَ مطلق — ` +
    // **والعددُ يتغيّر فالصيغةُ لا تُثنّى**: «استثناءان» كُتب حين كانا
    // اثنين، فصار يقول «3 استثناءان» — **نصٌّ يكذب على رقمه**.
    `قُرئ ${scanned} ملفّاً، واستثناءاتٌ مصرَّحةٌ ${DELIBERATE.length} · ${stamp}Z`,
);
