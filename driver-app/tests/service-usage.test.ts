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

// ── خدماتُ الكبتن من «حسابي» (أمرُ المالك ٢٠/١١ البند ٤) — كانت بلاطاتِ اللوحة وحدَها فخلت رئيسيّةُ ليبيا ──────────────
import { allServices, captainServices } from "../src/lib/captain-services.ts";

test("سوقٌ بلا بلاطةٍ في اللوحة (ليبيا) يرى خدماتِ الكبتن — لا رئيسيّةً خالية", () => {
  const shown = homeTiles(allServices(captainServices({ levels: false, advances: false, garage: false }), []), {});
  assert.equal(shown.length, HOME_TILES);
  assert.deepEqual(
    shown.map((t) => t.key),
    ["subscription", "wallet", "earnings", "vehicle", "support", "referral"],
  );
});

test("ما أطفأته اللوحةُ لدولته (السلفة · المستويات · الكراج) لا يُعدّ أصلاً", () => {
  const off = captainServices({ levels: false, advances: false, garage: false }).map((t) => t.key);
  const on = captainServices({ levels: true, advances: true, garage: true }).map((t) => t.key);
  for (const key of ["missions", "advance", "garage"]) {
    assert.ok(!off.includes(key), key);
    assert.ok(on.includes(key), key);
  }
});

test("بلاطةُ اللوحة التي تكرّر مقصداً قائماً لا تظهر مرّتين، والأخرى تُلحق بعد خدمات الكبتن", () => {
  const captain = captainServices({ levels: true, advances: true, garage: true });
  const merged = allServices(captain, [tile("offers"), { ...tile("dup"), destination: "/wallet" }]);
  assert.equal(merged.filter((t) => t.destination === "/wallet").length, 1);
  assert.equal(merged.at(-1)?.id, "offers");
});

test("الأكثرُ استعمالاً يتقدّم بين خدمات الكبتن", () => {
  const all = allServices(captainServices({ levels: true, advances: true, garage: true }), []);
  assert.equal(homeTiles(all, { "captain:garage": 4 })[0].key, "garage");
});
