/** الفقاعةُ الجديدة (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — الهدفُ للعرض، والرحلةُ بلا هاتفٍ ولا اسم. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { bubbleRide, cleanGoal } from "../src/lib/bubble-core.ts";

test("الهدفُ رقمٌ موجبٌ بثلاث منازل، والخانُ العربيّةُ تُقرأ، وما عداه «بلا هدف»", () => {
  assert.equal(cleanGoal("25"), "25");
  assert.equal(cleanGoal(" ٣٠ "), "30");
  assert.equal(cleanGoal("12.500"), "12.500");
  assert.equal(cleanGoal("0"), "");
  assert.equal(cleanGoal("-5"), "");
  assert.equal(cleanGoal("1.2345"), "");
  assert.equal(cleanGoal("abc"), "");
});

const base = {
  id: "r1",
  arrived_at: null,
  pickup: { lat: 31.95, lng: 35.91 },
  dropoff: { lat: 31.99, lng: 35.87 },
};

test("الرحلةُ للفقاعة: الملاحةُ إلى الالتقاط قبل البدء وإلى الوجهة بعده، ولا شيءَ بلا رحلةٍ جارية", () => {
  const going = JSON.parse(bubbleRide({ ...base, status: "accepted" })!);
  assert.deepEqual([going.nav_lat, going.nav_lng], [31.95, 35.91]);
  const riding = JSON.parse(bubbleRide({ ...base, status: "in_progress" })!);
  assert.deepEqual([riding.nav_lat, riding.nav_lng], [31.99, 35.87]);
  assert.equal(bubbleRide({ ...base, status: "completed" }), null);
  assert.equal(bubbleRide(null), null);
});

test("لا رقمَ هاتفٍ ولا اسمَ في ما يصل الفقاعة (SPEC §٦١-ز)", () => {
  const ride = JSON.parse(bubbleRide({ ...base, status: "arrived", arrived_at: "2026-11-20T10:00:00Z" })!);
  assert.deepEqual(Object.keys(ride).sort(), ["arrived_at", "id", "nav_lat", "nav_lng", "rider", "status"]);
  assert.equal(ride.rider, "الراكب");
});
