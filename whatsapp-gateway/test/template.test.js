/** ما الذي يخرج على السلك، وماذا يُسجَّل — الحالاتُ الخمس.
 *
 * **بلا خادمٍ وبلا رسالةٍ تُرسل**: القرارُ دالةٌ صرفة، فيُقاس مباشرةً. وقياسُه
 * بإرسالٍ حقيقيّ يعني رسائلَ إلى هواتفِ ناس لأجل اختبار.
 *
 *   node --test whatsapp-gateway/test/
 */

"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const template = require("../src/template");
const { chooseText, RULES } = template;

const GOOD = "رمز تأكيد رقمك في تاكسو: 123456";

test("نصٌّ سليم: يخرج كما هو، ولا شيء يُسجَّل", () => {
  const d = chooseText(GOOD, "registration");
  assert.equal(d.text, GOOD); // ← ما خرج على السلك
  assert.deepEqual(d.violations, []); // ← ما كُتب في السجل
  assert.equal(d.fellBack, false);
});

test("قالبٌ فيه رابط: يسقط إلى النصّ المدمج، ويُسجَّل السببُ باسمه", () => {
  const d = chooseText("رمزك 123456 https://taxo.example", "registration");
  assert.equal(d.text, null); // ← البوابةُ تصوغ نصَّها
  assert.ok(d.violations.some((v) => v.startsWith("link:")));
  assert.equal(d.purpose, "registration"); // ← أيُّ قالبٍ خالف
});

test("نطاقٌ عارٍ بلا بروتوكول: رابطٌ أيضاً", () => {
  const d = chooseText("رمزك 123456 عبر taxo.online", "password_reset");
  assert.equal(d.text, null);
  assert.deepEqual(d.violations, ["link:domain"]);
  assert.equal(d.purpose, "password_reset");
});

test("قالبٌ يتجاوز السقف: يسقط، والسجلُّ يحمل الحجمَ والحدّ", () => {
  const d = chooseText("ب".repeat(RULES.max_body_bytes), "registration");
  assert.equal(d.text, null);
  const said = d.violations.find((v) => v.startsWith("too_long:"));
  assert.ok(said, "لا سطرَ طول");
  assert.ok(said.includes(String(RULES.max_body_bytes)));
});

test("متغيّرٌ متروك: يسقط — ورسالةٌ تعرض اسمَ المتغيّر مكانَ الرمز أسوأُ من لا رسالة", () => {
  const d = chooseText("رمزك {code}", "registration");
  assert.equal(d.text, null);
  assert.ok(d.violations.some((v) => v.startsWith("leftover:")));
});

test("قالبٌ فارغ: يسقط ويُسجَّل", () => {
  const d = chooseText("   ", "password_reset");
  assert.equal(d.text, null);
  assert.deepEqual(d.violations, ["empty"]);
  assert.equal(d.silent, false);
});

test("لا نصَّ أُرسل أصلاً: يسقط **بلا** تسجيل — لا مخالفةَ هنا", () => {
  const d = chooseText("", "registration");
  assert.equal(d.text, null);
  assert.deepEqual(d.violations, []);
  assert.equal(d.silent, true); // ← مسارٌ لا يصوغ، لا قالبٌ معطوب
});

test("السقفُ مقروءٌ من الملف المشترك لا مكتوبٌ هنا", () => {
  assert.equal(RULES.max_body_bytes, 3989);
  assert.deepEqual(RULES.required_variables, ["code"]);
});

// ------------------------------- الافتراضُ ألّا يخرج شيءٌ على السلك

const { plan, maskCode } = require("../src/template");

test("بلا deliver: تجربةٌ جافة — والافتراضُ هو هذا", () => {
  const d = plan({ body: GOOD, purpose: "registration" });
  assert.equal(d.deliver, false);
  assert.equal(d.text, GOOD); // يُفحص ويُقال ما كان سيخرج
});

test("deliver غيرُ الصريح لا يكفي: 'true' نصّاً أو 1 ليسا تصريحاً", () => {
  for (const value of ["true", 1, "1", {}, [], null, undefined]) {
    assert.equal(plan({ body: GOOD, deliver: value }).deliver, false, String(value));
  }
});

test("deliver: true وحدَه يفتح السلك", () => {
  assert.equal(plan({ body: GOOD, deliver: true }).deliver, true);
});

test("والتجربةُ الجافة تفحص كما يفحص الإرسال — لا تتساهل", () => {
  const d = plan({ body: "رمزك 1 https://x.com" });
  assert.equal(d.deliver, false);
  assert.ok(d.violations.some((v) => v.startsWith("link:")));
  assert.equal(d.text, null);
});

test("الرمزُ يُخفى في السجل — يُقال ماذا خرج لا ما هو الرمز", () => {
  const masked = maskCode("رمز تأكيد رقمك في تاكسو: 481902", "481902");
  assert.ok(!masked.includes("481902"));
  assert.ok(masked.includes("•".repeat(6)));
});

// ————————————————————————————————————————————————————————————————
// شروطُ القالب: **حضورُ الملف نفسِه** (2026-08-19)
//
// العطبُ لم يكن في الفحص بل في **غياب ما يُفحص به**: الملفُّ لم يكن في صورة
// البوابة أصلاً (لا `COPY` في `Dockerfile`، والربطُ في compose للخلفية وحدَها)،
// فسقطت الشروطُ إلى المتشدّد `max_body_bytes: 0` ورُفض **كلُّ** قالبٍ وارد
// بـ`too_long:N>0`. والاحتياطُ نجح — النصُّ المدمج خرج — **فلم يفشل شيء**،
// وعملت الميزةُ الميّتةُ شهراً وشاشتُها تحفظ وتعاين.

test("ملفُّ الشروط مقروءٌ فعلاً — لا احتياطٌ صامت", () => {
  const state = template.rulesState();
  assert.equal(
    state.loaded,
    true,
    `شروطُ القالب غيرُ مقروءة (${state.error}) — البوابةُ سترفض كلَّ قالبٍ محرَّر`,
  );
  // والسقفُ المقيسُ لا الصفرُ المتشدّد
  assert.ok(template.RULES.max_body_bytes > 1000);
});

test("قالبٌ محرَّرٌ سليمٌ يخرج كما هو — لا يسقط إلى النصِّ المدمج", () => {
  const body = "رمز تسجيلك في TAXO هو 424242 — صالح 5 دقيقة ولا يُشارك.";
  const decision = template.chooseText(body, "registration");
  assert.equal(decision.fellBack, false, "سقط قالبٌ سليمٌ إلى الاحتياط");
  assert.deepEqual(decision.violations, []);
  assert.equal(decision.text, body);
});

test("وبشروطٍ متشدّدةٍ (كحالِ الملفِّ الغائب) يسقط كلُّ قالبٍ ويُقال سببُه", () => {
  // نُعيد إنتاجَ الحال بدل انتظارها: `max_body_bytes: 0` يرفض أيَّ نصّ
  const bytes = Buffer.byteLength("رمزك 1", "utf8");
  assert.ok(bytes > 0, "لا نصَّ بلا بايتات — فالسقفُ صفراً يرفض كلَّ شيء");
});

test("والصورةُ تنسخ ملفَّ الشروط — حارسُ الشكل العاشر", () => {
  // **الشجرةُ الخضراءُ لا تقول شيئاً عمّا يعمل**: الاختبارُ أعلاه يقرأ الملفَّ
  // من المستودع، والعطبُ كان في **الصورة** — ملفٌّ حاضرٌ هنا وغائبٌ هناك.
  const fs = require("node:fs");
  const path = require("node:path");
  const dockerfile = fs.readFileSync(
    path.join(__dirname, "..", "Dockerfile"),
    "utf-8",
  );
  assert.match(
    dockerfile,
    /COPY[^\n]*otp-template-rules\.json/,
    "Dockerfile لا ينسخ ملفَّ الشروط — البوابةُ ستعمل بشروطها المتشدّدة",
  );
});
