/** **مكالمةُ الرحلة عند نظام أندرويد** (SPEC §١٠٣ B/27) — ما يُقال للنظام من طورٍ إلى طور، مرّةً لكلِّ مكالمة. */
import { test } from "node:test";
import assert from "node:assert/strict";

import { bridgeStep } from "../src/lib/native-call-core.ts";

test("الصادرةُ تُعلَن عند «يرنّ» لا قبله", () => {
  assert.equal(bridgeStep(false, null, "preparing", true), null);
  assert.equal(bridgeStep(false, "consent", "dialing", true)?.kind, "outgoing");
});

test("الواردةُ تُعلَن عند الرنين", () => {
  assert.equal(bridgeStep(false, null, "incoming", false)?.kind, "incoming");
});

test("جاريةٌ مرّةً واحدة", () => {
  assert.equal(bridgeStep(true, "joining", "talking", true)?.kind, "active");
  assert.equal(bridgeStep(true, "talking", "talking", true), null);
});

test("الانتهاءُ بسببه", () => {
  assert.deepEqual(bridgeStep(true, "dialing", "unanswered", true), { kind: "end", reason: "missed" });
  assert.deepEqual(bridgeStep(true, "talking", "broken", true), { kind: "end", reason: "error" });
  assert.deepEqual(bridgeStep(true, "talking", "hungup", true), { kind: "end", reason: "local" });
  assert.deepEqual(bridgeStep(true, "talking", null, true), { kind: "end", reason: "local" });
});

test("لا شيءَ لمكالمةٍ لم تُعلَن", () => {
  assert.equal(bridgeStep(false, "talking", "hungup", true), null);
});
