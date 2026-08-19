/** فحصُ نصِّ الرسالة قبل السلك — **الحارسُ انتقل ولم يُحذف**.
 *
 * كان `/send` لا يقبل نصّاً، والبوابةُ تصوغه؛ فوعدُ «بلا روابط» يحرسه من يملك
 * السلك. ومنذ قوالبِ اللوحة (قرارُ المالك 2026-08-19) يصل النصُّ مصاغاً — لكنّ
 * **الوعدَ المقصودَ لم يكن «البوابةُ تصوغ» بل «لا يخرج على السلك ما يخالف
 * الشروط»**، وهو باقٍ هنا بالفحص بدل الصياغة. ومن قرأ هذا لاحقاً فلا يقرأه
 * تنازلاً.
 *
 * **والشروطُ من ملفٍ واحدٍ تقرؤه الخلفيةُ أيضاً** (`otp-template-rules.json`):
 * نسختان تفترقان أوّلَ تعديل، فيقبل المشرفُ في اللوحة نصّاً ترفضه البوابةُ
 * صامتةً — وذلك بعينه قالبٌ معطوبٌ يعمل شهراً ولا أحد يعلم.
 *
 * **والقرارُ دالةٌ صرفة** (`chooseText`): «ما الذي يخرج على السلك، وماذا يُسجَّل»
 * سؤالٌ واحد، وجوابُه يُختبر بلا خادمٍ ولا رسالةٍ تُرسل.
 */

"use strict";

const fs = require("node:fs");
const path = require("node:path");

const RULES_PATH = path.join(__dirname, "..", "otp-template-rules.json");

let RULES;
/** سببُ سقوط الشروط إلى المتشدّد — `null` يعني أنها قُرئت. */
let RULES_ERROR = null;
try {
  RULES = JSON.parse(fs.readFileSync(RULES_PATH, "utf-8"));
} catch (error) {
  // الشروطُ غائبةٌ أو تالفة: تُشدَّد لا تُرخَّى — فيسقط كلُّ نصٍّ وارد إلى
  // نصِّ البوابة المدمج، وهو أسلمُ من قبولِ ما لا نعرف أنه يوافق.
  //
  // **والسببُ يُحفظ ويُنشر** (2026-08-19): هذا الاحتياطُ عمل شهراً وحده —
  // الملفُّ لم يكن في الصورة أصلاً، فرُفض **كلُّ** قالبٍ بـ`too_long:…>0` ولم
  // يخرج قالبٌ محرَّرٌ قط. **واحتياطٌ ناجحٌ بلا أثرٍ مرئيٍّ يُعمي**: لا شيء
  // يفشل، والشاشةُ تحفظ وتعاين، والميزةُ لا تعمل
  RULES_ERROR = String(error && error.message ? error.message : error);
  RULES = {
    max_body_bytes: 0,
    required_variables: ["code"],
    optional_variables: [],
    forbidden_patterns: [],
  };
}

/** حالُ الشروط كما تُنشر — تقرؤها اللوحةُ فيرى الإنسانُ ما يراه السلك. */
function rulesState() {
  return { loaded: RULES_ERROR === null, error: RULES_ERROR, path: RULES_PATH };
}

/** يعيد أسماءَ الشروط المخالَفة — فارغاً يعني نصّاً يصلح للسلك. */
function violations(text) {
  const out = [];
  if (typeof text !== "string" || text.trim() === "") {
    out.push("empty");
    return out;
  }
  const bytes = Buffer.byteLength(text, "utf8");
  if (bytes > RULES.max_body_bytes) {
    out.push(`too_long:${bytes}>${RULES.max_body_bytes}`);
  }

  // **لا متغيّرَ متروك**: متغيّرٌ وصل غيرَ مستبدَلٍ يعني رمزاً لم يُكتب، فتخرج
  // رسالةٌ تعرض اسمَ المتغيّر مكانَ الرمز — وهي أسوأُ من لا رسالة
  const leftover = text.match(/\{[^{}]*\}/g);
  if (leftover) out.push(`leftover:${leftover.join(",")}`);

  for (const rule of RULES.forbidden_patterns || []) {
    const re = new RegExp(rule.pattern, rule.flags || "");
    if (re.test(text)) out.push(`${rule.kind || "link"}:${rule.name}`);
  }
  return out;
}

/**
 * ما الذي يخرج على السلك؟
 *
 * `text` غير `null` يعني نصّاً مقترحاً اجتاز الفحص. و`null` يعني السقوطَ إلى
 * نصِّ البوابة المدمج — و`violations` عندئذٍ غيرُ فارغة، وهي ما يُسجَّل.
 *
 * **ولا سقوطَ صامت**: من لم يُسجَّل سقوطُه لا يعرف أحدٌ أن قالبَه معطّل.
 */
function chooseText(proposed, purpose) {
  if (typeof proposed !== "string" || proposed === "") {
    // لم يُرسل نصٌّ أصلاً — مسارٌ قديمٌ أو مزوّدٌ لا يصوغ، ولا مخالفةَ هنا
    return { text: null, violations: [], purpose, fellBack: true, silent: true };
  }
  const bad = violations(proposed);
  if (bad.length === 0) {
    return { text: proposed, violations: [], purpose, fellBack: false, silent: false };
  }
  return { text: null, violations: bad, purpose, fellBack: true, silent: false };
}


/** يُخفي الرمزَ في نصٍّ يُسجَّل — السجلُّ يقول ماذا خرج، لا ما هو الرمز. */
function maskCode(text, code) {
  if (typeof text !== "string" || !code) return text;
  return text.split(code).join("•".repeat(String(code).length));
}

/**
 * خطةُ الطلب: أيخرج شيءٌ على السلك أصلاً، وبأيِّ نصّ؟
 *
 * **والافتراضُ ألّا يخرج** (قرارُ المالك 2026-08-19). كان `/send` يرسل بمجرّد
 * أن يُنادى، فقياسُ سقفِ الجسم — وهو قياسٌ لا علاقةَ له بالإرسال — أخرج أربعَ
 * رسائلَ حقيقيةً إلى هاتفِ إنسان. والعطبُ ليس في من نسي، بل في بابٍ **بابُه
 * الافتراضيُّ الإرسال**: من يستكشفه يرسل، ومن يختبره يرسل، ومن يخطئ يرسل.
 *
 * فالآن: `deliver: true` صراحةً وإلا فهو **تجربةٌ جافة** — تُفحص وتُجاب بما
 * كان سيخرج، ولا يُمسّ السلك. والباب لا يُقفل بالتذكّر بل بانقلاب الافتراض.
 */
function plan(payload) {
  const decision = chooseText(
    typeof payload.body === "string" ? payload.body : "",
    String(payload.purpose || "registration"),
  );
  return { ...decision, deliver: payload.deliver === true };
}

module.exports = {
  rulesState,
  violations,
  chooseText,
  plan,
  maskCode,
  RULES,
  RULES_PATH,
};
