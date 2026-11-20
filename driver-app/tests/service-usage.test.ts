/** خدماتُ الرئيسيّة (SPEC §١٠٩-د) — الأكثرُ استعمالاً أوّلاً، والمطفأُ لا يظهر، والستُّ وحدَها. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { byUsage, HOME_TILES, homeTiles } from "../src/lib/service-usage.ts";

const tile = (id: string, status: "active" | "soon" = "active") => ({
  id,
  key: id,
  title: id,
  subtitle: null,
  icon: "car",
  status,
  destination: status === "active" ? `/x/${id}` : null,
  is_new: false,
});

test("الأكثرُ استعمالاً أوّلاً، والتعادلُ بترتيب اللوحة", () => {
  const tiles = [tile("a"), tile("b"), tile("c")];
  assert.deepEqual(byUsage(tiles, { c: 3, b: 3 }).map((t) => t.id), ["b", "c", "a"]);
  assert.deepEqual(byUsage(tiles, {}).map((t) => t.id), ["a", "b", "c"]);
});

test("ما أُطفئ لدولة الكبتن («قريباً») لا يظهر في الرئيسيّة", () => {
  const tiles = [tile("a"), tile("off", "soon"), tile("b")];
  assert.deepEqual(homeTiles(tiles, { off: 9 }).map((t) => t.id), ["a", "b"]);
});

test("ستُّ بلاطاتٍ وحدَها — والباقي في «كل الخدمات»", () => {
  const tiles = Array.from({ length: 9 }, (_, i) => tile(`t${i}`));
  const shown = homeTiles(tiles, { t8: 5, t7: 2 });
  assert.equal(shown.length, HOME_TILES);
  assert.deepEqual(shown.slice(0, 3).map((t) => t.id), ["t8", "t7", "t0"]);
});
