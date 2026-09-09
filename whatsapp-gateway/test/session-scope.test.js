/** حارسُ النطاق: **لا متغيّرَ يُستعمَل في دالّةٍ ويُعرَّف في أخرى**.
 *
 * ## العلّةُ مقيسةٌ لا مفترضة (٢٠٢٦-٠٩-٠٩)
 *
 * فُصل `checkNumber` عن `sendCode` في 2026-08-31، **فانتقل `const [known]`
 * إلى الأولى وبقي `known.jid` في الثانية** — `ReferenceError: known is not
 * defined` على **كلِّ إرسالٍ حقيقيّ**، على التطوير والإنتاج معاً.
 *
 * **ولم يظهر تسعةَ أيام** لأن الحاويةَ تخدم صورةً أقدمَ من الشجرة: **أوّلُ
 * بناءٍ شحن العطبَ الساكن**. ولا اختبارَ أمسكه لأن الإرسالَ الحقيقيَّ لا
 * يُقاس في مجموعةٍ (رسائلُ إلى هواتفِ ناس).
 *
 * **فالقياسُ ثابتٌ لا تشغيليّ**: تُقرأ الوحدةُ نصّاً، ويُتحقَّق أن كلَّ
 * مُعرِّفٍ محلّيٍّ يُستعمَل داخل الدالّة التي تعلنه.
 *
 * ## وأوّلُ نسخةٍ منه كانت تصيح على سليم
 *
 * `why` معلَنٌ في `checkNumber`، **ومُعامِلُ دالّةِ سهمٍ في `sendCode`** —
 * رابطتان مستقلّتان باسمٍ واحد. فصاح الحارسُ على ما لا عطبَ فيه، **وحارسٌ
 * يخترع عطباً أغلى من واحدٍ يفوته**. فضُيِّق: **يُستثنى كلُّ اسمٍ تُعيد
 * `sendCode` ربطَه** (`const`/`let`/`var`، أو مُعامِلاً).
 *
 *   node --test whatsapp-gateway/test/
 */

"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const SRC = path.join(__dirname, "..", "src", "session.js");
const text = fs.readFileSync(SRC, "utf8");

/** يقصّ جسمَ دالّةٍ بعدِّ الأقواس من سطر إعلانها. */
function bodyOf(source, header) {
  const start = source.indexOf(header);
  assert.notEqual(start, -1, `لم تُوجد الدالّة: ${header}`);
  const open = source.indexOf("{", start);
  let depth = 0;
  for (let j = open; j < source.length; j += 1) {
    if (source[j] === "{") depth += 1;
    else if (source[j] === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(open, j + 1);
    }
  }
  throw new Error(`قوسٌ غيرُ مغلق: ${header}`);
}

/** يُزيل التعليقات كي لا يُقرأ شرحٌ استعمالاً. */
function stripComments(s) {
  return s.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/\/\/[^\n]*/g, " ");
}

/** أتُعيد هذه الدالّةُ ربطَ الاسم؟ إعلاناً أو مُعامِلاً. */
function rebinds(body, name) {
  const n = name.replace(/[$]/g, "\\$&");
  return (
    new RegExp(`\\b(?:const|let|var)\\s+[\\[{]?[^;=]*\\b${n}\\b`).test(body) ||
    new RegExp(`\\(\\s*(?:[\\w$]+\\s*,\\s*)*${n}\\s*(?:,[^)]*)?\\)\\s*=>`).test(body) ||
    new RegExp(`(?:function\\s*[\\w$]*\\s*)?\\([^)]*\\b${n}\\b[^)]*\\)\\s*(?:=>|\\{)`).test(body)
  );
}

const send = stripComments(bodyOf(text, "async sendCode("));
const check = stripComments(bodyOf(text, "async checkNumber("));

test("لا متغيّرَ محلّيٌّ يُستعمَل خارج الدالّة التي تعلنه", () => {
  const declared = [
    ...check.matchAll(/\b(?:const|let)\s+\[?\s*([A-Za-z_$][\w$]*)/g),
  ].map((m) => m[1]);
  assert.ok(
    declared.includes("known"),
    "المرجعُ تغيّر: `known` لم يعد معلَناً في checkNumber",
  );

  const leaked = [];
  for (const name of declared) {
    if (!new RegExp(`\\b${name}\\b`).test(send)) continue;
    if (rebinds(send, name)) continue; // رابطةٌ أخرى باسمٍ واحد — لا عطب
    leaked.push(name);
  }
  assert.deepEqual(
    leaked,
    [],
    `مُعرِّفاتٌ معلَنةٌ في checkNumber ومستعمَلةٌ في sendCode بلا ربطٍ جديد: ` +
      `${leaked.join(" · ")} — وهي \`ReferenceError\` على كلِّ إرسال. ` +
      "تُعاد في جواب checkNumber وتُفكَّك هناك.",
  );
});

test("وجهةُ الإرسال تأتي من جواب checkNumber لا من نطاقٍ آخر", () => {
  assert.match(
    send,
    /const\s*\{[^}]*\bjid\b[^}]*\}\s*=\s*await\s+this\.checkNumber/,
    "sendCode يجب أن يأخذ `jid` من جواب checkNumber",
  );
  assert.doesNotMatch(send, /known\s*\./, "sendCode يقرأ `known` من نطاقٍ ليس له");
});
