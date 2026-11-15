// **ورقةُ الطلب الجديدة — ما يُعرض لا ما يُحسب** (SPEC §١٠٢). usage: npm run test:unit
import { test } from "node:test";
import assert from "node:assert/strict";
import { activeChips, compactAmount, oneLine } from "../src/lib/order-sheet.ts";

test("السعرُ بلا فلوسٍ حين خاناتُه أصفار، وكما هو حين ليست", () => {
  assert.equal(compactAmount("12.000"), "12");
  assert.equal(compactAmount("12.500"), "12.500");
  assert.equal(compactAmount("1,250.000"), "1,250");
  assert.equal(compactAmount("850"), "850");
  assert.equal(compactAmount("0.250"), "0.250");
});

test("سطرُ العنوان بلا فاصلتين متتاليتين ولا فاصلةٍ في طرفيه", () => {
  assert.equal(oneLine("شارع الرينبو،، جبل عمّان"), "شارع الرينبو، جبل عمّان");
  assert.equal(oneLine("، سيتي مول ، ، الجبيهة ,"), "سيتي مول، الجبيهة");
  assert.equal(oneLine(null), "");
});

test("الرقاقاتُ بترتيبٍ ثابت، والمطفأُ لا رقاقةَ له", () => {
  assert.deepEqual(activeChips({ bargain: false, share: false, forOther: false, scheduling: false }), []);
  assert.deepEqual(activeChips({ bargain: true, share: false, forOther: true, scheduling: true }), ["bargain", "forOther", "schedule"]);
});
