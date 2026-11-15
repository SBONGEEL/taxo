// **«وجهتي» تُعرض بقيمتها المخزّنة أو «غيرُ مضبوطة»** — لا صفرٌ مخترَع (`?? 0` القديم).
// usage: node --experimental-strip-types --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { destinationStatus } from "../src/lib/destination-status.ts";

test("لا صفَّ للدولة ⇐ «غيرُ مضبوطة» لا «مطفأة»", () => {
  assert.deepEqual(destinationStatus(null), { label: "غيرُ مضبوطة — يعمل افتراضُ الخلفيّة", tone: "warn" });
  assert.deepEqual(destinationStatus(undefined), { label: "غيرُ مضبوطة — يعمل افتراضُ الخلفيّة", tone: "warn" });
});

test("القيمةُ المخزّنةُ تُعرض كما هي", () => {
  assert.equal(destinationStatus(2).label, "مفعّلة — 2 في اليوم");
  assert.equal(destinationStatus(7).label, "مفعّلة — 7 في اليوم");
  assert.equal(destinationStatus(2).tone, "ok");
});

test("الصفرُ المخزّنُ مطفأةٌ حقّاً — ويُقال إنه صفر", () => {
  assert.deepEqual(destinationStatus(0), { label: "مطفأة (0)", tone: "muted" });
});
