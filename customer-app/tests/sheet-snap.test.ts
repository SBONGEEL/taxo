// **ورقةُ الطلب بارتفاعين** (SPEC §١٠٥/١) — السحبُ يقرّر باتّجاهه، وما دون العتبة لا يبدّل. usage: npm run test:unit
import { test } from "node:test";
import assert from "node:assert/strict";
import { SNAP_PX, snapAfterDrag } from "../src/lib/sheet-snap.ts";

test("السحبُ للأعلى يملأ الشاشة، وللأسفل يعيد النصف", () => {
  assert.equal(snapAfterDrag("half", SNAP_PX + 40), "full");
  assert.equal(snapAfterDrag("full", -(SNAP_PX + 40)), "half");
});

test("وسحبٌ في الاتّجاه نفسِه لا يغيّر شيئاً", () => {
  assert.equal(snapAfterDrag("full", 200), "full");
  assert.equal(snapAfterDrag("half", -200), "half");
});

test("وما دون العتبة ارتجافُ إصبعٍ لا سحب", () => {
  assert.equal(snapAfterDrag("half", SNAP_PX - 1), "half");
  assert.equal(snapAfterDrag("full", -(SNAP_PX - 1)), "full");
});
