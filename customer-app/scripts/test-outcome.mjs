#!/usr/bin/env node
/** **خاتمةُ الرحلة بعد الدفع — اختبارٌ يسقط على السلوك القديم** (SPEC §٧٦-س، بلاغُ المالك ٢٠٢٦-١٠-١٦).
 *
 *     node --experimental-strip-types scripts/test-outcome.mjs
 *
 * **شقّان**: قراراتُ `src/lib/outcome.ts` (النافذةُ تُفتح لما يقول الخادمُ إنه مستحقّ وحدَه · ما طُوي يُذكر خارج الرئيسية · الشريطُ لا يُخفى لرحلةٍ
 * انتهت · العودةُ رجوعٌ لا دفعٌ فوق الدفع) — **وقراءةُ الشيفرة التي كانت العطب**: `NavBar` كان يُخفي الشريطَ لأيِّ رحلة (`ride !== null`)،
 * و«طُويت» كانت `useState` داخل الرئيسية تُنسى بفكّها، ورأسُ شاشة الدفع كان `navigate("/")` دفعاً فوقها. **وكلُّ واحدٍ منها يُسقط هذا الاختبار.**
 *
 * **وما لا يقيسه — مكتوبٌ**: لا يرسم شاشة. **والرسمُ مقيسٌ بـ`tools/e2e-payment-return.mjs`** في متصفّحٍ على وضع الضيف (رحلةٌ ثمّ دفعٌ ثمّ رجوع).
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");
const outcome = await import(join(SRC, "lib", "outcome.ts"));
const ACTIVE = ["requested", "searching", "accepted", "arrived", "in_progress", "at_stop"];

function memory() {
  const map = new Map();
  return { getItem: (k) => (map.has(k) ? map.get(k) : null), setItem: (k, v) => map.set(k, String(v)) };
}

test("the payment prompt opens only for what the server says is due", () => {
  assert.equal(outcome.outcomeDecision("completed", false, { settlement: "due" }), "show");
  // **دُفعت** — لا تعود النافذة
  assert.equal(outcome.outcomeDecision("completed", false, { settlement: "settled" }), "forget");
  // **دفعةٌ تنتظر تأكيد الكبتن** — لا تُفتح دفعةٌ ثانية
  assert.equal(outcome.outcomeDecision("completed", false, { settlement: "awaiting" }), "forget");
  assert.equal(outcome.outcomeDecision("completed", false, { settlement: "disputed" }), "forget");
  // لم يُسأل بعد ⇒ لا ومضة · وتعذّر السؤال ⇒ تُعرض (لا يُخفى دفعٌ بانقطاع شبكة)
  assert.equal(outcome.outcomeDecision("completed", false, undefined), "wait");
  assert.equal(outcome.outcomeDecision("completed", false, null), "show");
  // ما طُوي لا يعود — ولو قال الخادمُ «مستحقّ» (الراكبُ قال «لاحقاً»)
  assert.equal(outcome.outcomeDecision("completed", true, { settlement: "due" }), "forget");
  assert.equal(outcome.outcomeDecision("no_driver_found", false, undefined), "show");
});

test("a closed outcome is remembered outside the home screen", () => {
  const box = memory();
  assert.equal(outcome.isOutcomeClosed("r1", box), false);
  outcome.rememberClosedOutcome("r1", box);
  // **«فكُّ الرئيسية وتركيبُها»** — قراءةٌ جديدةٌ من المخزن نفسِه
  assert.equal(outcome.isOutcomeClosed("r1", box), true);
  assert.equal(outcome.isOutcomeClosed("r2", box), false);
  for (let k = 0; k < 80; k += 1) outcome.rememberClosedOutcome(`x${k}`, box);
  assert.ok(outcome.closedOutcomes(box).length <= 50);
});

test("the bottom bar is hidden only for an active ride or an open sheet", () => {
  // **العطبُ بعينه**: رحلةٌ اكتملت وطُويت خاتمتُها — الشريطُ ظاهر
  assert.equal(outcome.navBarHidden("completed", false, ACTIVE), false);
  assert.equal(outcome.navBarHidden("cancelled_by_driver", false, ACTIVE), false);
  assert.equal(outcome.navBarHidden(null, false, ACTIVE), false);
  assert.equal(outcome.navBarHidden("in_progress", false, ACTIVE), true);
  assert.equal(outcome.navBarHidden(null, true, ACTIVE), true);
});

test("returning home after paying goes back, not forward over the payment screen", () => {
  assert.equal(outcome.stepsBackToHome(5, 2), -3);
  assert.equal(outcome.stepsBackToHome(2, null), null);
  assert.equal(outcome.stepsBackToHome(null, 2), null);
  assert.equal(outcome.stepsBackToHome(2, 5), null);
});

test("the code that was the defect is gone", () => {
  const app = readFileSync(join(SRC, "App.tsx"), "utf8");
  const home = readFileSync(join(SRC, "screens", "Home.tsx"), "utf8");
  const pay = readFileSync(join(SRC, "screens", "Payment.tsx"), "utf8");
  assert.doesNotMatch(app, /if \(ride !== null\) return null;/, "NavBar يُخفي الشريطَ لأيِّ رحلةٍ معروضة");
  assert.match(app, /navBarHidden\(/, "NavBar لا يقرأ قرارَ الشريط من lib/outcome");
  assert.doesNotMatch(home, /const \[dismissed, setDismissed\] = useState/, "«طُويت» حالٌ داخل الرئيسية تُنسى بفكّها");
  assert.match(home, /outcomeDecision\(/, "الرئيسيةُ لا تسأل عن حال الدفع قبل النافذة");
  assert.doesNotMatch(pay, /onBack=\{\(\) => navigate\("\/"\)\}/, "رأسُ الدفع يدفع الرئيسيةَ فوق شاشة الدفع");
});
