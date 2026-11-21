/** ودجاتُ الراكب (أمرُ المالك ٢١/١١) — «المطار» أقربُ مطارٍ حقيقيٍّ أو المحفوظ، ولا مطارَ يُخترع؛ ومسارُ الودجة مُخفَّف. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { km, nearestAirport, thinRoute } from "../src/lib/widget-core.ts";

// إحداثيّاتٌ تقريبيّةٌ لمطارين ومدينتين — لاختبار المسافة لا لعرضها
const AMMAN = { lat: 31.95, lng: 35.91 };
const AQABA_CITY = { lat: 29.53, lng: 35.0 };
const AIRPORTS = [
  { id: "a1", name: "مطار الملكة علياء", lat: 31.72, lng: 35.99 },
  { id: "a2", name: "مطار الملك حسين", lat: 29.61, lng: 35.02 },
];

test("المسافة: صفرٌ للنقطة نفسِها، وعمّان–العقبة نحو ٢٦٠ كم", () => {
  assert.equal(km(AMMAN, AMMAN), 0);
  const d = km(AMMAN, AQABA_CITY);
  assert.ok(d > 240 && d < 290, String(d));
});

test("الأقربُ إلى مكان الراكب من مطارات السوق", () => {
  assert.equal(nearestAirport(AIRPORTS, AMMAN, [])?.id, "airport:a1");
  assert.equal(nearestAirport(AIRPORTS, AQABA_CITY, [])?.name, "مطار الملك حسين");
});

test("لا مطارَ ضمن ١٠٠ كم ⇐ null (يُخفى الزرّ) — ولا قائمةَ أو لا موقع ⇐ null", () => {
  assert.equal(nearestAirport(AIRPORTS, { lat: 30.8, lng: 36.9 }, []), null);
  assert.equal(nearestAirport([], AMMAN, []), null);
  assert.equal(nearestAirport(null, AMMAN, []), null);
  assert.equal(nearestAirport(AIRPORTS, null, []), null);
});

test("المكانُ المحفوظُ للمطار يغلب — باسمه أو بقربه من مطارٍ حقيقيّ", () => {
  const named = [{ id: "p1", label: "المطار", lat: 31.7, lng: 35.98 }];
  assert.deepEqual(nearestAirport(AIRPORTS, AQABA_CITY, named), { id: "place:p1", name: "المطار", lat: 31.7, lng: 35.98 });
  const near = [{ id: "p2", label: "صالة المغادرة", lat: 31.725, lng: 35.995 }];
  assert.equal(nearestAirport(AIRPORTS, AQABA_CITY, near)?.id, "place:p2");
  const far = [{ id: "p3", label: "البيت", lat: 31.95, lng: 35.91 }];
  assert.equal(nearestAirport(AIRPORTS, AMMAN, far)?.id, "airport:a1");
});

test("المسار: الأولى والأخيرة دائماً، وسقفُ النقاط، وأقلُّ من نقطتين ⇐ null", () => {
  const long = Array.from({ length: 1000 }, (_, i) => [35.9 + i * 1e-4, 31.9 + i * 1e-4]);
  const thin = thinRoute(long, 120)!;
  assert.ok(thin.length <= 120, String(thin.length));
  assert.deepEqual(thin[0], [35.9, 31.9]);
  assert.deepEqual(thin[thin.length - 1], [Math.round((35.9 + 999e-4) * 1e5) / 1e5, Math.round((31.9 + 999e-4) * 1e5) / 1e5]);
  assert.equal(thinRoute([[35.9, 31.9]]), null);
  assert.equal(thinRoute(null), null);
  assert.equal(thinRoute([[35.9, 31.9], [Number.NaN, 1], [35.91, 31.91]])!.length, 2);
});
