/** لونُ سيارة الكبتن (SPEC §١١١) — يُقرأ من نصِّه الحرّ، ولا يُخمَّن ما لا يُعرف، ولا يُطلى ما ليس أبيضَ الهيكل. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { paintFor } from "../src/lib/car-paint.ts";

test("الألوانُ الشائعةُ بالعربيّة بتشكيلها وبلا تشكيل", () => {
  assert.equal(paintFor("economy", "أسود"), "#2b2e33");
  assert.equal(paintFor("economy", "فضّي"), "#b9bec6");
  assert.equal(paintFor("suv", "أحمر"), "#b8262b");
  assert.equal(paintFor("comfort", "ازرق"), "#2f5fae");
});

test("الفرنسيّةُ والإنجليزيّة", () => {
  assert.equal(paintFor("economy", "Noir"), "#2b2e33");
  assert.equal(paintFor("economy", "Gris métallisé"), "#7d838c");
  assert.equal(paintFor("van", "blue"), "#2f5fae");
});

test("الأبيضُ وما لا يُعرف: السيارةُ كما رُسمت — لا لونَ مخترع", () => {
  assert.equal(paintFor("economy", "أبيض"), null);
  assert.equal(paintFor("economy", "لون خاص"), null);
  assert.equal(paintFor("economy", ""), null);
  assert.equal(paintFor("economy", null), null);
});

test("«المميّزة» السوداء وسيارةُ النساء بلونيهما — لا طلاء", () => {
  assert.equal(paintFor("vip", "أحمر"), null);
  assert.equal(paintFor("women", "أزرق"), null);
});

test("الأطولُ أوّلاً: كحليٌّ لا أزرق، وخمريٌّ لا أحمر", () => {
  assert.equal(paintFor("economy", "كحلي"), "#22355e");
  assert.equal(paintFor("economy", "خمري"), "#6e1f2a");
});
