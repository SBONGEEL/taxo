/** فقاعةُ الراكب (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — تظهر في البحث والرحلة وحدَهما، بالاسم الأوّل، بلا هاتفٍ ولا مبلغ. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { firstName, riderBubbleRide, riderPhase } from "../src/lib/rider-bubble-core.ts";

const ride = (status: string, extra: Record<string, unknown> = {}) => ({
  id: "r1",
  status,
  arrived_at: null,
  driver: { name: "أحمد سالم العلي", vehicle: { make: "Kia", model: "Rio", color: "أبيض", plate_number: "12-3456" } },
  ...extra,
});

test("الأطوار: البحثُ والقبولُ والوصولُ والرحلة — وما عداها لا فقاعة", () => {
  assert.equal(riderPhase("requested"), "searching");
  assert.equal(riderPhase("searching"), "searching");
  assert.equal(riderPhase("accepted"), "assigned");
  assert.equal(riderPhase("arrived"), "arrived");
  assert.equal(riderPhase("in_progress"), "in_progress");
  assert.equal(riderPhase("completed"), null);
  assert.equal(riderBubbleRide(ride("cancelled"), 3, 5), null);
  assert.equal(riderBubbleRide(null, null, null), null);
});

test("الاسمُ الأوّلُ وحدَه، والمركبةُ ولوحتُها، ولا هاتفَ ولا مبلغ", () => {
  assert.equal(firstName("  أحمد سالم "), "أحمد");
  const body = JSON.parse(riderBubbleRide(ride("accepted"), 4, 8)!);
  assert.equal(body.driver, "أحمد");
  assert.equal(body.car, "Kia Rio");
  assert.equal(body.plate, "12-3456");
  assert.equal(body.eta_min, 4);
  assert.equal(body.eta_first, 8);
  const keys = Object.keys(body).join(",");
  assert.ok(!/phone|fare|amount|fee/.test(keys), keys);
});

test("«الإلغاء الآن مجاني» أثناء البحث وحدَه — قبل القبول (القسم 5)", () => {
  assert.equal(JSON.parse(riderBubbleRide(ride("searching", { driver: null }), null, null)!).free_cancel, true);
  assert.equal(JSON.parse(riderBubbleRide(ride("accepted"), 3, 5)!).free_cancel, false);
  assert.equal(JSON.parse(riderBubbleRide(ride("arrived"), null, null)!).free_cancel, false);
});

test("عدّادُ الانتظار من وقت الوصول، ولا وقتَ وصولٍ بعد الوصول", () => {
  const body = JSON.parse(riderBubbleRide(ride("arrived", { arrived_at: "2026-11-20T10:00:00Z" }), 2, 6)!);
  assert.equal(body.arrived_ms, Date.parse("2026-11-20T10:00:00Z"));
  assert.equal(body.eta_min, -1);
});
