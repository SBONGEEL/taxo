/** **أرقامُ الخريطة لاتينيّة** (أمرُ المالك ٢٠٢٦-١١-١٨ الثاني) — نطاقُ الخطّ العربيّ وحدَه من ملفّات التطبيق، وكلُّ ما عداه كما كان. */
import { test } from "node:test";
import assert from "node:assert/strict";

import { buildOpenStyle, OPEN_GLYPHS_URL, openTransformRequest } from "../src/lib/open-map-style.ts";

const glyph = (stack: string, range: string) =>
  OPEN_GLYPHS_URL.replace("{fontstack}", encodeURIComponent(stack)).replace("{range}", range);

test("the arabic range comes from the app, with its font", () => {
  assert.equal(openTransformRequest(glyph("Noto Sans Regular", "1536-1791"), "Glyphs").url, "/map-glyphs/Noto%20Sans%20Regular/1536-1791.pbf");
  assert.equal(openTransformRequest(glyph("Noto Sans Bold", "1536-1791"), "Glyphs").url, "/map-glyphs/Noto%20Sans%20Bold/1536-1791.pbf");
});

test("every other range, tile and request is left as it was", () => {
  for (const url of [glyph("Noto Sans Regular", "0-255"), glyph("Noto Sans Regular", "65024-65279")]) {
    assert.equal(openTransformRequest(url, "Glyphs").url, url);
  }
  const tile = "https://tiles.openfreemap.org/planet/20251112_001001_pt/14/9000/6500.pbf";
  assert.equal(openTransformRequest(tile, "Tile").url, tile);
  assert.equal(openTransformRequest("https://example.org/fonts/x/1536-1791.pbf", "Glyphs").url, "https://example.org/fonts/x/1536-1791.pbf");
});

test("labels fall back from arabic to local to english, so no place is nameless", () => {
  const colors = Object.fromEntries(
    ["land", "water", "park", "building", "road", "roadMajor", "roadCasing", "label", "labelHalo", "poi"].map((k) => [k, "#000000"]),
  );
  const style = buildOpenStyle(colors as never, true) as { layers: Array<{ layout?: { "text-field"?: unknown } }> };
  const names = style.layers.map((layer) => JSON.stringify(layer.layout?.["text-field"] ?? null)).filter((t) => t.includes("name"));
  assert.ok(names.length > 0);
  for (const field of names) {
    assert.ok(field.indexOf("name:ar") < field.indexOf('"name"') && field.indexOf('"name"') < field.indexOf("name:en"), field);
  }
});
