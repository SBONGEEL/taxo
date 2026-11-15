// **قائمةُ البحث عن الأماكن — ما يُحسب للعرض** (SPEC §١٠٤). usage: npm run test:unit
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  categoryIcon,
  distanceLabel,
  foldText,
  forgetRecent,
  hiddenRecents,
  highlightRange,
  latestOnly,
  pointKey,
  recentPicks,
  rememberPick,
  type KeyValueStore,
} from "../src/lib/place-search.ts";

const cut = (name: string, query: string) => {
  const range = highlightRange(name, query);
  return range ? name.slice(range[0], range[1]) : null;
};

test("الطيُّ العربيّ: الهمزاتُ والتاءُ المربوطةُ والألفُ المقصورةُ والحركاتُ والمسافات", () => {
  assert.equal(foldText("أَحْمَد"), "احمد");
  assert.equal(foldText("إربد"), "اربد");
  assert.equal(foldText("آخر"), "اخر");
  assert.equal(foldText("الداخلية"), foldText("الداخليه"));
  assert.equal(foldText("مستشفى"), foldText("مستشفي"));
  assert.equal(foldText("  دوار   الداخلية "), "دوار الداخليه");
  assert.equal(foldText("Algér"), "alger");
  assert.equal(foldText("City Mall"), "city mall");
});

test("التظليلُ يقع على الأصل لا على المطويّ", () => {
  assert.equal(cut("دوار الداخلية", "الداخليه"), "الداخلية");
  assert.equal(cut("دوّار الداخليّة", "دوار الداخلية"), "دوّار الداخليّة");
  assert.equal(cut("مستشفى الأردن", "مستشفي الاردن"), "مستشفى الأردن");
  assert.equal(cut("سيتي مول", "سيتى"), "سيتي");
  assert.equal(cut("City Mall", "city"), "City");
  assert.equal(cut("Bab Ezzouar", "EZZ"), "Ezz");
});

test("بلا «ال» إن لم تُوجد بها", () => {
  assert.equal(cut("مكة مول", "المكة مول"), "مكة مول");
  assert.equal(cut("دوار الداخلية", "داخلية"), "داخلية");
});

test("ما لا يُوجد لا يُظلَّل، والحرفُ الواحدُ لا يُظلَّل", () => {
  assert.equal(highlightRange("سيتي مول", "تاج"), null);
  assert.equal(highlightRange("سيتي مول", "س"), null);
});

test("المسافةُ بالأرقام اللاتينيّة وبوحدتها", () => {
  assert.equal(distanceLabel(850), "850 م");
  assert.equal(distanceLabel(4), "10 م");
  assert.equal(distanceLabel(3240), "3.2 كم");
  assert.equal(distanceLabel(152_400), "152 كم");
  assert.equal(distanceLabel(null), null);
  assert.equal(distanceLabel(undefined), null);
  assert.equal(distanceLabel(-1), null);
  assert.ok(!/[٠-٩]/.test(distanceLabel(3240) ?? ""));
});

test("لكلِّ صنفٍ أيقونة، والمجهولُ أيقونةٌ عامّة", () => {
  assert.equal(categoryIcon("airport"), "flight_takeoff");
  assert.equal(categoryIcon("roundabout"), "roundabout_right");
  assert.equal(categoryIcon("saved"), "star");
  assert.equal(categoryIcon("شيء جديد"), "location_on");
  assert.equal(categoryIcon(null), "location_on");
});

test("جوابٌ أقدمُ يصل بعد أحدثَ منه يُرمى", () => {
  const order = latestOnly();
  const first = order.next(); // «با»
  const second = order.next(); // «باب»
  assert.equal(order.isCurrent(second), true);
  assert.equal(order.isCurrent(first), false, "جوابُ «با» المتأخّرُ لا يغطّي جوابَ «باب»");
});

function memory(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return { data, getItem: (key) => data.get(key) ?? null, setItem: (key, value) => void data.set(key, value) };
}

const CITY_MALL = { name: "سيتي مول", address: "أم السماق، عمان", lat: 31.9785, lng: 35.8337 };
const TAJ = { name: "تاج مول", address: "عبدون، عمان", lat: 31.9437, lng: 35.8888 };

test("آخرُ ما اختير أوّلاً، والمكرَّرُ يصعد ولا يتكرّر", () => {
  const store = memory();
  rememberPick(store, "u1", CITY_MALL);
  rememberPick(store, "u1", TAJ);
  rememberPick(store, "u1", { ...CITY_MALL, lat: CITY_MALL.lat + 0.0001 });
  assert.deepEqual(recentPicks(store, "u1").map((pick) => pick.name), ["سيتي مول", "تاج مول"]);
});

test("لكلِّ مستخدمٍ قائمتُه — حسابٌ آخرُ على الهاتف نفسِه لا يرى شيئاً", () => {
  const store = memory();
  rememberPick(store, "u1", CITY_MALL);
  assert.deepEqual(recentPicks(store, "u2"), []);
  assert.deepEqual(recentPicks(store, null), []);
  rememberPick(store, null, TAJ);
  assert.equal(store.data.size, 2, "بلا مستخدمٍ لا يُكتب شيء");
});

test("الإخفاءُ يُسقط الصفَّ عند صاحبه وحدَه، واختيارُه من جديدٍ يعيده", () => {
  const store = memory();
  rememberPick(store, "u1", CITY_MALL);
  forgetRecent(store, "u1", CITY_MALL);
  assert.deepEqual(recentPicks(store, "u1"), []);
  assert.deepEqual(hiddenRecents(store, "u1"), [pointKey(CITY_MALL)]);
  assert.deepEqual(hiddenRecents(store, "u2"), []);
  rememberPick(store, "u1", CITY_MALL);
  assert.deepEqual(hiddenRecents(store, "u1"), []);
});

test("تخزينٌ تالفٌ أو غائبٌ لا يُسقط القائمة", () => {
  const store = memory();
  store.data.set("taxo:search:picks:u1", "{not json");
  assert.deepEqual(recentPicks(store, "u1"), []);
  assert.deepEqual(recentPicks(null, "u1"), []);
  rememberPick(null, "u1", CITY_MALL);
  const broken: KeyValueStore = {
    getItem: () => null,
    setItem: () => {
      throw new Error("QuotaExceeded");
    },
  };
  rememberPick(broken, "u1", CITY_MALL);
});

test("نسخةُ الكبتن من المكتبة هي هي بايتاً — «وجهتي» تطابق وتُظلّل وتحفظ كالراكب", async () => {
  const { readFile } = await import("node:fs/promises");
  const here = new URL("../src/lib/place-search.ts", import.meta.url);
  const there = new URL("../../driver-app/src/lib/place-search.ts", import.meta.url);
  assert.equal(await readFile(there, "utf8"), await readFile(here, "utf8"));
});
