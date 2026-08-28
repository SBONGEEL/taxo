/** **الشكلُ الثالثَ عشر**: قيمةُ مالٍ تحسبها الخلفيةُ ولا تصل أيَّ واجهة.
 *
 * **كلفتُه مقيسةٌ لا مقدَّرة** (2026-08-21): رحلةٌ بمحطتين على تسعيرة الأردن
 * تحمل **1.000 د.أ رسمَ محطات** ورسمَ انتظارٍ بالدقيقة — **كلُّه داخلٌ في
 * `final_fare`، ولا سطرَ له في أيِّ شاشة**: لا عند الراكب، ولا في شاشة الدفع،
 * ولا في «تفصيل السعر» عند الكبتن، ولا في اللوحة. فيدفع الراكبُ رقماً لا
 * يستطيع اشتقاقَه، ويفصل المشرفُ في نزاعٍ بأرقامٍ لا تفسّره.
 *
 * **ولا حارسَ كان يراه**: `check:config` يسأل عن **مرآةٍ** للحقل لا عن
 * **قارئ**، و`check:readers` يمسح `lib/` وحدَها، و`tsc` يرى نوعاً صحيحاً.
 *
 * ---
 *
 * **ومفرداتُ المال تُقرأ من بيتها الواحد** — `backend/tests/money_format.py`.
 * نسختان من قائمةٍ تفترقان أوّلَ إضافة، ثم يحرس أحدُهما ما لا يحرسه الآخر
 * **بلا أن يفشل شيء**؛ وهي القاعدةُ نفسُها التي جعلت `otp-template-rules.json`
 * ملفاً واحداً تقرؤه لغتان.
 *
 * **ولماذا مطابقةُ اسمٍ لا مُحلِّل؟** الشكُّ يُفسَّر لصالح السكوت كما في
 * `check:readers`: حارسٌ يصيح على سليمٍ يُطفأ، فيسقط معه ما يمسكه حقاً — وهو
 * قرارُ المالك بعد أن اخترع `check:contract` عطباً لا وجودَ له.
 *
 * ---
 *
 * **وحدُّه يُقال قبل أن يُصدَّق، فلا يُقرأ أوسعَ مما هو:**
 *
 * **يثبت أن للاسم قارئاً، لا أن القيمةَ تُرسم، ولا في أيِّ شاشة.** **والعطبُ
 * الذي أنشأه لا يمسكه**: `waiting_charge` **كان** يُقرأ — في شاشة الوقوف —
 * واختفى لحظةَ صار مبلغاً يُدفع. **فمن يقرأ اسمَ هذا الحارس ويطمئنّ يكون قد
 * استبدل بالمراجعة اطمئناناً.** وما يمسكه الصنفُ الأوسع: مبلغٌ **لا يصل
 * واجهةً البتّة** — كـ`pending_compensation` في محفظة الكبتن (شُحن كذلك)،
 * و`stops_charge` قبل أن يُبنى سطرُه.
 *
 * **ومحلُّه بناءُ اللوحة وحدَها** كـ`check:doors`: سؤالُه **عابرٌ للتطبيقات**
 * («ألا يقرؤه أحد؟»)، وجوابُه واحدٌ أينما شُغِّل — فتشغيلُه ثلاثاً عملٌ مكرَّر
 * بجوابٍ واحد.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { exit } from "node:process";
import { createRequire } from "node:module";
import { certify } from "./certify.mjs";

/** **مُحلِّلٌ من حزمة تطبيقٍ لا من الجذر** — لا `node_modules` في جذر
 *  المستودع، وهي قاعدةُ `check:money-math` نفسُها. **وغيابُه وقوفٌ لا سلامة.** */
function loadTypeScript() {
  for (const app of APPS) {
    try {
      return createRequire(new URL(`../${app}/package.json`, import.meta.url))(
        "typescript",
      );
    } catch {
      /* جرّبْ التالي */
    }
  }
  console.error("✗ لم يوجد `typescript` في أيٍّ من التطبيقات — الحارسُ لا يقيس.");
  exit(1);
}

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const APPS = ["customer-app", "driver-app", "admin-panel"];
const SCHEMAS = join(ROOT, "backend", "app", "schemas");
const VOCAB = join(ROOT, "backend", "tests", "money_format.py");
const ts = loadTypeScript();

/** استثناءاتٌ تحمل عللَها نصّاً — وقائمةٌ بلا عللٍ تصير قائمةَ أعذار. */
const DELIBERATE = {
  // **مقيسٌ لا مُخمَّن**: شاشةُ التقييم ترسم `presets` أزراراً **ولا حقلَ
  // مبلغٍ حرّاً فيها**، فالسقفُ لا يمكن بلوغُه من الواجهة أصلاً — وهو حارسُ
  // طلبٍ مصنوعٍ بيد. ويومَ يُضاف إدخالٌ حرّ **يصير هذا الاستثناءُ كذباً**،
  // ومن يضيفه يجد سطرَه هنا.
  max_amount:
    "سقفُ البقشيش — والشاشةُ أزرارٌ جاهزةٌ بلا إدخالٍ حرّ، فلا سبيلَ لبلوغه",
  // **والرقمان اللذان يحتاجهما الكبتن معروضان**: `amount_paid` و«وفّرتَ
  // {discount_amount}» في شاشة اشتراكه — وسعرُ القائمة ثالثٌ يُشتقّ منهما،
  // فعرضُه تكرارٌ لا تفصيل.
  list_price:
    "سعرُ القائمة مجمَّدٌ للسجل، و`amount_paid` و`discount_amount` معروضان" +
    " في شاشة الاشتراك — فالثالثُ مشتقٌّ منهما",

  // ── ما كشفه فصلُ الأسطح 2026-08-28 — **مسجَّلٌ بحاله لا بعلّةٍ مخترَعة** ──
  //
  // **هذه لم تكن مُقرَّةً يوماً**: كانت تمرّ لأن `seen` جمعت التطبيقاتِ
  // الثلاثة، **فقارئٌ في سطحٍ يُسكت مرآةً في آخر**. وفصلُ المجموعات أظهرها.
  //
  // **وعرضُها أو حذفُ مرآتها قرارُ منتَجٍ لا يُخمَّن**: `check:config` يوجب
  // المرآةَ لكلِّ حقلٍ **يصل** السطح، فحذفُها يكسره؛ وعرضُها سطرٌ في شاشة.
  // **فتُقيَّد بحالها المقيسة** حتى يقرّرها المالك — والحارسُ يصيح يومَ
  // يصير لأحدها قارئ، فلا يبقى الاستثناءُ بعد زوال علّته.
  paid_amount:
    "مرآةٌ في تطبيقَي الراكب والكبتن بلا قارئٍ فيهما — ويُقرأ في اللوحة" +
    " وحدَها. مقيسٌ 2026-08-28، وينتظر قرارَ المالك: يُعرض أم تُحذف مرآتُه",
  stop_fee:
    "مرآةٌ في تطبيقَي الراكب والكبتن بلا قارئٍ فيهما — وذِكرُه في" +
    " `ConfirmRide.tsx` تعليقٌ لا قراءة. مقيسٌ 2026-08-28، وينتظر قراراً",
  carried_cancellation_fee:
    "مرآةٌ في تطبيق الراكب بلا قارئٍ فيه — ويُقرأ في تطبيق الكبتن." +
    " مقيسٌ 2026-08-28، وينتظر قراراً",
  outstanding:
    "مرآةٌ في تطبيق الكبتن بلا قارئٍ فيه — وذِكرُه في `Collect.tsx` تعليقٌ" +
    " لا قراءة. ويُقرأ في تطبيق الراكب بثلاثة مواضع. مقيسٌ 2026-08-28",
  fare:
    "لا مرآةَ له في أيِّ سطح — `schemas/promo.py`، ولم يكن يظهر قطُّ قبل" +
    " فصل الأسطح لأن الاسمَ شائعٌ في الثلاثة. مقيسٌ 2026-08-28، وينتظر قراراً",
};

// ── مفرداتُ المال من بيتها الواحد ───────────────────────────────────────
function vocabulary() {
  const text = readFileSync(VOCAB, "utf8");
  // **`endsWith("SUFFIXES")` كان خطأً صامتاً**: الاسمُ المُمرَّر
  // `"MONEY_SUFFIXES ="` ينتهي بـ`=` لا بـ`SUFFIXES` — فكان الحارسُ يقرأ
  // **كتلةَ الأسماء مكانَ اللواحق**، فلا يعرف `_fee` لاحقةً ويمرّ أخضرَ على
  // كلِّ رسمٍ ينتهي بها. **ولم يكشفه إلا القياسُ في الاتجاه الثاني** — وشجرةٌ
  // سليمةٌ كانت تُخرجه أخضرَ ٢٧ حقلاً، وهو رقمٌ يُطمئن ولا يعني شيئاً.
  const block = (name) => {
    const at = text.indexOf(name);
    if (at < 0) throw new Error(`لم يوجد ${name} في ${VOCAB}`);
    const list = name.includes("SUFFIXES");
    const open = text.indexOf(list ? "(" : "{", at);
    const close = text.indexOf(list ? ")" : "}", open);
    return [...text.slice(open, close).matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  };
  return {
    suffixes: block("MONEY_SUFFIXES ="),
    names: new Set(block("MONEY_NAMES =")),
    notMoney: new Set(block("NOT_MONEY =")),
  };
}

const { suffixes, names, notMoney } = vocabulary();
const isMoney = (key) =>
  !notMoney.has(key) && (names.has(key) || suffixes.some((s) => key.endsWith(s)));

// ── حقولُ المخططات: `name: type` في ملفات `schemas/` ────────────────────
function schemaFields() {
  const found = new Map(); // اسم → ملفٌّ ظهر فيه
  for (const file of readdirSync(SCHEMAS)) {
    if (!file.endsWith(".py")) continue;
    const text = readFileSync(join(SCHEMAS, file), "utf8");
    for (const m of text.matchAll(/^\s{4}([a-z_][a-z0-9_]*)\s*:/gm)) {
      const key = m[1];
      if (isMoney(key) && !found.has(key)) found.set(key, file);
    }
  }
  return found;
}

// ── ما تقرؤه التطبيقاتُ فعلاً — **خارج مرايا الأنواع وخارج التعليقات** ───
// ذكرُ الاسم في `api/types.ts` **تصريحٌ لا قراءة**، وهي قاعدةُ `check:doors`
// نفسُها: بيانٌ لا يكفي دليلاً على زرّ. **وذكرُه في تعليقٍ أضعفُ من التصريح
// نفسِه** — شرحٌ عن الحقل لا قراءةٌ له.
//
// **وقد خدع هذا الحارسَ مقيساً (2026-08-25)**: `stop_fee` لا أثرَ له في
// `customer-app` خارج `types.ts` إلا **تعليقٌ برأس `ConfirmRide.tsx`**،
// و`outstanding` لا أثرَ له في `driver-app` إلا **تعليقٌ برأس `Collect.tsx`**.
// فكان المسحُ نصّياً أعمى — `matchAll(/[A-Za-z_]\w*/g)` لا يفرّق بين قارئٍ
// وشرحٍ عنه — **وهو درسُ `check:doors` الأول لم يُطبَّق هنا**.
//
// **فالمُحلِّلُ هو الأداة** كما في `check:money-math`: التعليقاتُ ليست عُقَداً
// في الشجرة، فتسقط بلا قائمةٍ استثناءاتٍ تُكتب بيد وتُنسى.
//
// **وتبقى السلاسلُ محسوبةً قراءةً عمداً**: `row["stop_fee"]` قراءةٌ بحقّ،
// والشكُّ يُفسَّر لصالح السكوت كما في رأس هذا الملفّ — حارسٌ يصيح على سليمٍ
// يُطفأ، فيسقط معه ما يمسكه حقاً. **ونصُّ JSX ليس عقدةَ اسمٍ ولا سلسلة**،
// فاسمُ حقلٍ مطبوعٌ للقارئ على الشاشة لا يُحسب قارئاً — وهو الصواب.
function readIdentifiers() {
  /** **مجموعةٌ لكلِّ سطحٍ لا مجموعةٌ واحدةٌ للثلاثة** (قرارُ المالك 2026-08-28).
   *
   * كانت `seen` واحدةً تجمع التطبيقاتِ الثلاثة، **فقارئٌ في سطحٍ يُسكت مرآةً
   * في آخر**: حقلٌ تعلنه `driver-app` في `types.ts` ولا يقرؤه أحدٌ فيها يمرّ
   * أخضرَ لأن `admin-panel` تقرأ اسماً مثلَه. **والحارسُ صادقٌ ودعواه أوسعُ
   * من نطاقه** — وهو الشكلُ الخامسَ عشر بعينه.
   *
   * **وليس الصوابُ أن يُطلب كلُّ حقلٍ في كلِّ سطح**: حقلُ الكبتن لا شأنَ له
   * بتطبيق الراكب. **والمرآةُ هي الدعوى**: سطحٌ يكتب الحقلَ في `types.ts`
   * يقول «أنا أنشره لقارئٍ عندي» — فيُطالَب بقارئٍ **عنده هو**.
   */
  const perApp = new Map(); // تطبيق → { seen, mirrored, files }
  const collectInto = (set) => {
    const walkNode = (node) => {
      if (
        ts.isIdentifier(node) ||
        ts.isStringLiteral(node) ||
        ts.isNoSubstitutionTemplateLiteral(node)
      ) {
        set.add(node.text);
      }
      ts.forEachChild(node, walkNode);
    };
    return walkNode;
  };

  let files = 0;
  for (const app of APPS) {
    const src = join(ROOT, app, "src");
    const seen = new Set();
    const mirrored = new Set();
    let appFiles = 0;
    const walk = (dir) => {
      for (const entry of readdirSync(dir)) {
        const path = join(dir, entry);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.tsx?$/.test(entry)) {
          const kind = entry.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
          const tree = ts.createSourceFile(
            path,
            readFileSync(path, "utf8"),
            ts.ScriptTarget.Latest,
            false,
            kind,
          );
          if (entry.endsWith("types.ts")) {
            // **المرآةُ تُقرأ دعوى لا قراءة** — تُجمع وحدَها
            ts.forEachChild(tree, collectInto(mirrored));
          } else {
            appFiles += 1;
            files += 1;
            ts.forEachChild(tree, collectInto(seen));
          }
        }
      }
    };
    try { walk(src); } catch { /* تطبيقٌ غيرُ موجودٍ في هذه الشجرة */ }
    perApp.set(app, { seen, mirrored, files: appFiles });
  }
  return { perApp, files };
}

const fields = schemaFields();
const { perApp, files } = readIdentifiers();

// **صمتٌ سببُه ألّا شيءَ قِيس ليس صمتَ سلامة** — وقد وقع مقيساً في
// `check:readers` حين لم يطابق فاصلُ المسار على ويندوز فمرّ أخضرَ بلا ملف
if (files === 0 || fields.size === 0) {
  console.error(
    `✗ لم يُقرأ شيء (ملفات=${files}، حقول=${fields.size}) — هذا عطبٌ في الحارس لا سلامةٌ في الشجرة.`,
  );
  exit(1);
}

// **حقلٌ لا يعكسه أيُّ سطحٍ لا يراه أحد** — وهو ما كان يمسكه الحارسُ الأول
const anywhereMirrored = (key) =>
  APPS.some((app) => perApp.get(app)?.mirrored.has(key));

// **تُحسب المخالفاتُ أولاً بلا نظرٍ إلى الاستثناءات** — فيصير «الاستثناءُ
// زالت علّتُه» سؤالاً عن **زوال المخالفة**، لا عن وجود قارئٍ في أيِّ سطح.
// **والفرقُ ليس تجميلاً**: حقلٌ يقرؤه سطحٌ ويُهمله آخرُ **له مخالفةٌ وقارئٌ
// معاً**، فقياسُ «له قارئ» وحدَه يقلّم استثناءً ما تزال علّتُه قائمة.
const violations = new Map(); // مفتاح → { ملف، أسباب }
for (const [key, file] of fields) {
  const why = [];
  if (!anywhereMirrored(key)) {
    why.push("لا مرآةَ في أيِّ سطح");
  } else {
    for (const app of APPS) {
      const box = perApp.get(app);
      if (!box || box.files === 0) continue;
      if (box.mirrored.has(key) && !box.seen.has(key)) {
        why.push(`مرآةٌ في ${app} بلا قارئٍ فيها`);
      }
    }
  }
  if (why.length) violations.set(key, { file, why });
}

const unread = [];
for (const [key, { file, why }] of violations) {
  if (DELIBERATE[key]) continue;
  for (const reason of why) unread.push([key, file, reason]);
}
unread.sort((a, z) => (a[0] + a[2]).localeCompare(z[0] + z[2]));

// **استثناءٌ زالت مخالفتُه يُقلَّم** — لا استثناءٌ صار له قارئٌ في سطحٍ ما
const stale = Object.keys(DELIBERATE)
  .filter((key) => fields.has(key) && !violations.has(key))
  .sort();

if (unread.length || stale.length) {
  if (unread.length) {
    console.error("\n✗ مبالغُ تحسبها الخلفيةُ ولا يقرؤها من أعلنها:\n");
    for (const [key, file, why] of unread) {
      console.error(`   ${key}  (schemas/${file}) — ${why}`);
    }
    console.error(
      "\n  إمّا سطرٌ يعرضه في شاشةٍ، وإمّا سببٌ مكتوبٌ في `DELIBERATE`.",
    );
  }
  if (stale.length) {
    console.error(
      `\n✗ استثناءاتٌ صار لها قارئٌ فتُقلَّم: ${stale.join(" · ")}`,
    );
  }
  exit(1);
}

// **الشهادةُ تقول ما قِيس سطحاً سطحاً** — ورقمٌ واحدٌ للثلاثة يخفي أن
// أحدَها لم يُقَس أصلاً
const perAppNote = APPS.map((app) => {
  const box = perApp.get(app);
  if (!box || box.files === 0) return `${app}: —`;
  return `${app}: ${box.mirrored.size ? [...fields.keys()].filter((k) => box.mirrored.has(k)).length : 0}/${box.files}`;
}).join(" · ");

certify(
  "check:money-visible",
  `✓ كلُّ مبلغٍ معلَنٍ في مرآةِ سطحٍ يقرؤه ذلك السطح — ${fields.size} حقلاً، ` +
    `${files} ملفَّ واجهة (مرايا/ملفات — ${perAppNote}).`,
);
