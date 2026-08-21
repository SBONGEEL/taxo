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
import { join, sep } from "node:path";
import { exit } from "node:process";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const APPS = ["customer-app", "driver-app", "admin-panel"];
const SCHEMAS = join(ROOT, "backend", "app", "schemas");
const VOCAB = join(ROOT, "backend", "tests", "money_format.py");

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

// ── ما تقرؤه التطبيقاتُ فعلاً — **خارج مرايا الأنواع** ──────────────────
// ذكرُ الاسم في `api/types.ts` **تصريحٌ لا قراءة**، وهي قاعدةُ `check:doors`
// نفسُها: بيانٌ لا يكفي دليلاً على زرّ.
function readIdentifiers() {
  const seen = new Set();
  let files = 0;
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) walk(path);
      else if (/\.tsx?$/.test(entry) && !entry.endsWith("types.ts")) {
        files += 1;
        for (const m of readFileSync(path, "utf8").matchAll(/[A-Za-z_][A-Za-z0-9_]*/g))
          seen.add(m[0]);
      }
    }
  };
  for (const app of APPS) {
    const src = join(ROOT, app, "src");
    try { walk(src); } catch { /* تطبيقٌ غيرُ موجودٍ في هذه الشجرة */ }
  }
  return { seen, files };
}

const fields = schemaFields();
const { seen, files } = readIdentifiers();

// **صمتٌ سببُه ألّا شيءَ قِيس ليس صمتَ سلامة** — وقد وقع مقيساً في
// `check:readers` حين لم يطابق فاصلُ المسار على ويندوز فمرّ أخضرَ بلا ملف
if (files === 0 || fields.size === 0) {
  console.error(
    `✗ لم يُقرأ شيء (ملفات=${files}، حقول=${fields.size}) — هذا عطبٌ في الحارس لا سلامةٌ في الشجرة.`,
  );
  exit(1);
}

const unread = [...fields]
  .filter(([key]) => !DELIBERATE[key] && !seen.has(key))
  .sort();
const stale = Object.keys(DELIBERATE).filter((key) => seen.has(key)).sort();

if (unread.length || stale.length) {
  if (unread.length) {
    console.error("\n✗ مبالغُ تحسبها الخلفيةُ ولا يقرؤها تطبيقٌ واحد:\n");
    for (const [key, file] of unread) console.error(`   ${key}  (schemas/${file})`);
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

console.log(
  `✓ كلُّ مبلغٍ في المخططات (${fields.size}) يقرؤه تطبيقٌ — قُرئ ${files} ملفَّ واجهة.`,
);
