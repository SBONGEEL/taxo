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

const { chooseText, RULES } = require("../src/template");

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
