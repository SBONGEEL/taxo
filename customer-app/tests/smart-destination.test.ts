/** **اقتراحُ الوجهة الذكيّ** (SPEC §١٠٣ C/35) — الحسابُ الخالص: التكرارُ في نافذة الساعة، والتفافُ منتصف الليل، ولا اقتراحَ لمكانٍ هو فيه. */
import { test } from "node:test";
import assert from "node:assert/strict";

import { appendVisit, MAX_VISITS, suggestDestination } from "../src/lib/smart-destination-core.ts";

const at = (day: number, hour: number, minute: number) => new Date(2026, 10, day, hour, minute).getTime();
const work = { lat: 31.9539, lng: 35.9106, address: "العمل" };
const gym = { lat: 31.97, lng: 35.88, address: "النادي" };
const history = [
  { ...work, at: at(10, 8, 0) },
  { ...work, lat: 31.9541, at: at(11, 8, 20) },
  { ...gym, at: at(11, 18, 0) },
  { ...gym, at: at(12, 18, 30) },
  { ...gym, at: at(13, 19, 0) },
];

test("الوجهةُ المتكرّرةُ في ساعة الآن تُقترح", () => {
  assert.equal(suggestDestination(history, at(18, 8, 10), null)?.address, "العمل");
  assert.equal(suggestDestination(history, at(18, 18, 40), null)?.count, 3);
});

test("لا اقتراحَ بلا نمط", () => {
  assert.equal(suggestDestination(history, at(18, 13, 0), null), null);
  assert.equal(suggestDestination([history[0]], at(18, 8, 0), null), null);
});

test("لا تُقترح وجهةٌ هو عندها", () => {
  assert.equal(suggestDestination(history, at(18, 8, 10), { lat: 31.954, lng: 35.9107 }), null);
});

test("منتصفُ الليل يلتفّ", () => {
  const night = [{ ...work, at: at(10, 23, 40) }, { ...work, at: at(11, 23, 50) }];
  assert.equal(suggestDestination(night, at(18, 0, 20), null)?.address, "العمل");
});

test("السجلُّ بسقفه", () => {
  let visits: ReturnType<typeof appendVisit> = [];
  for (let i = 0; i < 80; i++) visits = appendVisit(visits, { ...work, at: at(1, 1, i % 59) });
  assert.equal(visits.length, MAX_VISITS);
});
