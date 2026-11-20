/** صورةُ الملفّ (SPEC §١٠٩-هـ) — القصُّ لا يُظهر حافّةً فارغة، والحرفُ ولونُه ثابتان لصاحبهما. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { clampCrop, initialOf, INITIAL_CROP, letterColour, MAX_ZOOM, sourceRect } from "../src/lib/photo-crop.ts";

test("البدايةُ: مربّعُ الوسط من صورةٍ أفقيّة", () => {
  const rect = sourceRect(1200, 800, INITIAL_CROP);
  assert.equal(Math.round(rect.size), 800);
  assert.equal(Math.round(rect.sx), 200);
  assert.equal(Math.round(rect.sy), 0);
});

test("الإزاحةُ لا تُخرج المربّعَ عن الصورة", () => {
  const crop = clampCrop({ zoom: 1, x: 5, y: 5 }, 1200, 800);
  assert.equal(crop.y, 0);
  const rect = sourceRect(1200, 800, crop);
  assert.ok(rect.sx >= -0.001 && rect.sx + rect.size <= 1200.001);
});

test("التكبيرُ محصورٌ بين ١ والأقصى، ويضيّق المربّعَ المأخوذ", () => {
  assert.equal(clampCrop({ zoom: 0.2, x: 0, y: 0 }, 500, 500).zoom, 1);
  assert.equal(clampCrop({ zoom: 99, x: 0, y: 0 }, 500, 500).zoom, MAX_ZOOM);
  assert.equal(Math.round(sourceRect(1000, 1000, { zoom: 2, x: 0, y: 0 }).size), 500);
});

test("الحرفُ ولونُه من الاسم وحدَه", () => {
  assert.equal(initialOf("  محمد"), "م");
  assert.equal(initialOf(""), "؟");
  assert.equal(letterColour("محمد"), letterColour("محمد"));
  assert.match(letterColour("سارة"), /^#[0-9A-F]{6}$/);
});
