// **بحثُ القوائم الكاملة** (قائمةُ المالك ٢٠٢٦-١١-١٠: «بحثٌ في كلِّ قائمة») — الطيُّ ونصُّ الصفّ.
// usage: node --experimental-strip-types --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { foldSearch, rowText } from "../src/lib/table-search.ts";

test("الهمزاتُ والتاءُ المربوطةُ والتشكيلُ لا تمنع المطابقة", () => {
  assert.equal(foldSearch("أحمد"), foldSearch("احمد"));
  assert.equal(foldSearch("مطارُ معيتيقة"), foldSearch("مطار معيتيقه"));
  assert.equal(foldSearch("مصطفى"), foldSearch("مصطفي"));
});

test("الخاناتُ العربيّة-الهنديّة تطابق اللاتينيّة، وحالةُ الحروف لا تهمّ", () => {
  assert.equal(foldSearch("٠٩١٢٣"), "09123");
  assert.equal(foldSearch("  TAXO   Card "), "taxo card");
});

test("نصُّ الصفّ من قيمه وكائناته المتداخلة، بلا null", () => {
  const row = { id: "a1", name: "سالم", phone: "+218912345678", amount: 7, owner: { city: "طرابلس" }, note: null };
  const text = rowText(row);
  for (const part of ["سالم", "+218912345678", "7", "طرابلس"]) assert.ok(text.includes(part), part);
  assert.ok(!text.includes("null"));
});
