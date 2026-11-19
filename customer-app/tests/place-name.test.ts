/** **اسمُ المكان مختصراً بذكاء** (أمرُ المالك ٢٠٢٦-١١-١٩) — ما رآه على هاتفه: «طرابلس» وحدَها للانطلاق، و«طرابلس، شعبية طرابلس، لـ…» للوجهة. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { isGenericPlace, shortPlace, usefulParts } from "../src/lib/place-name.ts";

test("المختصرُ يحذف البلدَ والشعبيّةَ والمكرَّر ويُبقي ما يدلّ أوّلاً", () => {
  assert.equal(shortPlace("طرابلس، شعبية طرابلس، ليبيا"), "طرابلس");
  assert.equal(shortPlace("شارع الشط، تاجوراء، طرابلس، شعبية طرابلس، ليبيا"), "شارع الشط، تاجوراء");
  assert.equal(shortPlace("تاجوراء، قرب مصحة ابن النفيس"), "تاجوراء، قرب مصحة ابن النفيس");
  assert.equal(shortPlace("شارع الرينبو 9, جبل عمّان, عمّان, محافظة العاصمة, الأردن"), "شارع الرينبو 9، جبل عمّان");
});

test("ولا يُخترع جزءٌ ولا يُفرَّغ السطر", () => {
  assert.equal(shortPlace(null), null);
  assert.equal(shortPlace("ليبيا"), "ليبيا");
  assert.deepEqual(usefulParts("باب الزوار، ولاية الجزائر، الجزائر"), ["باب الزوار"]);
});

test("المدينةُ وحدَها لا تدلّ — والمعلمُ أو الشارعُ وحدَه يدلّ", () => {
  assert.ok(isGenericPlace("طرابلس"));
  assert.ok(isGenericPlace("طرابلس، شعبية طرابلس، ليبيا"));
  assert.ok(isGenericPlace(null));
  assert.ok(!isGenericPlace("قرب مصحة ابن النفيس"));
  assert.ok(!isGenericPlace("شارع الشط"));
  assert.ok(!isGenericPlace("تاجوراء، قرب مصحة ابن النفيس"));
});
