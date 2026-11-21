/** رئيسيّةُ الراكب الجديدة (SPEC §١١١، أمرُ المالك ٢١/١١ الثاني) — شرائحُ حقيقيّةٌ وحدَها، والدوّارُ يعرف بطاقتَه، والشبكةُ بلا فراغ. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { carouselIndex, quickChips, shownCategories, spansLast } from "../src/lib/home-cars-core.ts";

const labels = { home: "المنزل", work: "العمل", airport: "المطار" };
const home = { id: "place:1", name: "بيتي", lat: 31.95, lng: 35.91 };
const work = { id: "place:2", name: "المكتب", lat: 31.97, lng: 35.86 };
const airport = { id: "airport:a", name: "مطار الملكة علياء الدولي", lat: 31.72, lng: 35.99 };

test("الفئاتُ بترتيب الدولة، وخدمةُ النساء لمن عُرضت عليها وحدَها", () => {
  const all = ["economy", "comfort", "women_economy", "vip"] as never[];
  assert.deepEqual(shownCategories(all, false), ["economy", "comfort", "vip"]);
  assert.deepEqual(shownCategories(all, true), ["economy", "comfort", "women_economy", "vip"]);
  assert.deepEqual(shownCategories([], true), []);
});

test("الشرائحُ أماكنُ حقيقيّةٌ وحدَها — بلا مكانٍ محفوظٍ ولا مطارٍ ولا رحلةٍ لا شريحة", () => {
  assert.deepEqual(quickChips({ home: null, work: null, airport: null, last: null, labels }), []);
  const chips = quickChips({ home, work, airport, last: null, labels });
  assert.deepEqual(chips.map((chip) => chip.kind), ["home", "work", "airport"]);
  assert.equal(chips[2].place.name, "مطار الملكة علياء الدولي");
});

test("الوجهةُ الأخيرةُ باسمها، ولا تُكرَّر إن كانت منزلَه", () => {
  const last = { id: "recent:x", name: "سيتي مول", lat: 31.98, lng: 35.83 };
  assert.deepEqual(quickChips({ home, work: null, airport: null, last, labels }).map((chip) => chip.label), ["المنزل", "سيتي مول"]);
  const backHome = { id: "recent:y", name: "شارع الجامعة", lat: 31.9501, lng: 35.9101 };
  assert.deepEqual(quickChips({ home, work: null, airport: null, last: backHome, labels }).map((chip) => chip.kind), ["home"]);
});

test("الدوّارُ يعرف بطاقتَه في الواجهة من اليمين (scrollLeft سالب) ومن اليسار، ولا يخرج عن العدد", () => {
  assert.equal(carouselIndex(0, 300, 3), 0);
  assert.equal(carouselIndex(-310, 300, 3), 1);
  assert.equal(carouselIndex(590, 300, 3), 2);
  assert.equal(carouselIndex(-5000, 300, 3), 2);
  assert.equal(carouselIndex(-100, 0, 3), 0);
  assert.equal(carouselIndex(0, 300, 0), 0);
});

test("الشبكةُ بلا خانةٍ فارغة: الفردُ يمدّ آخرَه على العمودين", () => {
  assert.equal(spansLast(5), true);
  assert.equal(spansLast(4), false);
  assert.equal(spansLast(1), true);
  assert.equal(spansLast(0), false);
});
