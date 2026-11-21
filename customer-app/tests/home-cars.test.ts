/** سياراتُ الرئيسيّة (SPEC §١١١) — السحبةُ تطوي/تبسط ولا تخلط اللمسة، والفئاتُ فئاتُ الدولة وحدَها. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { shownCategories, swipeIntent } from "../src/lib/home-cars-core.ts";

test("سحبةٌ لأسفلَ تطوي، ولأعلى تبسط", () => {
  assert.equal(swipeIntent(60, 4), "fold");
  assert.equal(swipeIntent(-60, 4), "open");
});

test("لمسةٌ أو سحبةٌ قصيرةٌ أو أفقيّةٌ لا تفعل شيئاً — صفُّ الفئات يتمرّر أفقيّاً بلا طيّ", () => {
  assert.equal(swipeIntent(10, 0), null);
  assert.equal(swipeIntent(40, 80), null);
  assert.equal(swipeIntent(0, 0), null);
});

test("الفئاتُ بترتيب الدولة، وخدمةُ النساء لمن عُرضت عليها وحدَها", () => {
  const all = ["economy", "comfort", "women_economy", "vip"] as never[];
  assert.deepEqual(shownCategories(all, false), ["economy", "comfort", "vip"]);
  assert.deepEqual(shownCategories(all, true), ["economy", "comfort", "women_economy", "vip"]);
  assert.deepEqual(shownCategories([], true), []);
});
