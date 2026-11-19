/** **نقطةُ الانطلاق = الموقعُ الحاليّ، بتأكيدٍ لطيف** (أمرُ المالك ٢٠٢٦-١١-١٩، البند ٧) — المنطقُ الخالص في `src/lib/pickup-confirm.ts`.
 *  وما يخصّ الشاشة (السطرُ في الورقة وحدَها، لا نافذة، «تغيير» يحدّث السعرَ والمسار) يُقرأ من الشيفرة في الاختبار الأخير. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  SNAP_MAX_M,
  WEAK_ACCURACY_M,
  metersBetween,
  movedEnough,
  pickupLine,
  placeName,
  refreshOnResume,
  snapToRoad,
} from "../src/lib/pickup-confirm.ts";

const tr = (text: string, values: Record<string, string> = {}) => text.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
const AMMAN = { lat: 31.9539, lng: 35.9106 };
const north = (point: { lat: number; lng: number }, meters: number) => ({ lat: point.lat + meters / 111_195, lng: point.lng });

test("الانطلاقُ من GPS يُقال «موقعك الحالي» باسمه العربيّ ويُبرَز مرّة", () => {
  const line = pickupLine({ source: "gps", accuracy_m: 12, address: "شارع الرينبو، جبل عمّان" }, tr);
  assert.equal(line.kind, "current");
  assert.equal(line.text, "الانطلاق من موقعك الحالي: شارع الرينبو، جبل عمّان");
  assert.ok(line.pulse);
  assert.ok(!line.adjust);
});

test("لا إحداثيّاتٍ في السطر أبداً — بلا اسمٍ يُقال «موقعك الحالي» وحدَه", () => {
  assert.equal(placeName("31.9539, 35.9106"), null);
  assert.equal(placeName("  "), null);
  assert.equal(pickupLine({ source: "gps", accuracy_m: 5, address: "31.9539,35.9106" }, tr).text, "الانطلاق من موقعك الحالي");
  assert.equal(pickupLine({ source: "gps", accuracy_m: 5, address: null }, tr).text, "الانطلاق من موقعك الحالي");
});

test("دقّةٌ أضعفُ من 50 م: «موقعك تقريبي» ويُدعى إلى ضبط الدبّوس — في السطر نفسِه", () => {
  const weak = pickupLine({ source: "gps", accuracy_m: WEAK_ACCURACY_M + 1, address: "دوّار الداخليّة" }, tr);
  assert.equal(weak.kind, "approx");
  assert.equal(weak.text, "موقعك تقريبي، تأكد من نقطة الانطلاق");
  assert.ok(weak.adjust && weak.pulse);
  assert.equal(pickupLine({ source: "gps", accuracy_m: WEAK_ACCURACY_M, address: "x" }, tr).kind, "current");
  assert.equal(pickupLine({ source: "gps", accuracy_m: null, address: "x" }, tr).kind, "current");
});

test("ما اختاره الراكبُ بيده لا يُنبَّه عليه ولا يُقال «موقعك الحالي»", () => {
  const manual = pickupLine({ source: "manual", accuracy_m: 400, address: "مستشفى الأردن" }, tr);
  assert.equal(manual.kind, "manual");
  assert.equal(manual.text, "الانطلاق من: مستشفى الأردن");
  assert.ok(!manual.pulse && !manual.adjust);
});

test("العودةُ من الخلفيّة تحدّث GPS وحدَه، ولا شيءَ وسطَ رحلة، ولا لارتعاشٍ صغير", () => {
  assert.ok(refreshOnResume("gps", false));
  assert.ok(!refreshOnResume("manual", false), "ما غيّره الراكبُ بيده لا يُمسّ");
  assert.ok(!refreshOnResume("gps", true));
  assert.ok(movedEnough(null, AMMAN));
  assert.ok(!movedEnough(AMMAN, north(AMMAN, 10)));
  assert.ok(movedEnough(AMMAN, north(AMMAN, 40)));
});

test("الدبّوسُ يُلصق بأوّل نقطةٍ في المسار (الطريق) — ضمن الحدّ، ولـGPS وحدَه", () => {
  const road = north(AMMAN, 20);
  const route = [[road.lng, road.lat], [35.92, 31.96]];
  const snapped = snapToRoad("gps", AMMAN, route);
  assert.ok(snapped && Math.abs(metersBetween(snapped, road)) < 0.01);
  assert.equal(snapToRoad("manual", AMMAN, route), null, "دبّوسُ الراكب لا يُنقل");
  assert.equal(snapToRoad("gps", road, route), null, "على الطريق أصلاً — لا حلقة");
  const far = north(AMMAN, SNAP_MAX_M + 30);
  assert.equal(snapToRoad("gps", AMMAN, [[far.lng, far.lat], [35.92, 31.96]]), null, "أبعدُ من الحدّ مكانٌ آخر");
  assert.equal(snapToRoad("gps", AMMAN, null), null);
});

test("الشاشة: السطرُ في ورقة الطلب وحدَها، بلا نافذة، و«تغيير» يعيد التسعير — والإذنُ المرفوضُ له زرُّ إعداد", () => {
  const sheet = readFileSync(new URL("../src/screens/t2/ConfirmRideT2.tsx", import.meta.url), "utf8");
  const home = readFileSync(new URL("../src/screens/Home.tsx", import.meta.url), "utf8");
  const riderHome = readFileSync(new URL("../src/screens/t2/RiderHomeT2.tsx", import.meta.url), "utf8");
  // السطرُ يُرسم داخل الورقة (لا في الرئيسيّة) — والورقةُ لا تُبنى إلا بوجهة (`target`)
  assert.match(sheet, /t2-pickup-confirm/);
  assert.doesNotMatch(riderHome, /t2-pickup-confirm/);
  assert.match(home, /pickup && target\s*\n?\s*\?/);
  // لا نافذةَ ولا حوارَ للتأكيد
  const block = sheet.slice(sheet.indexOf("t2-pickup-confirm") - 400, sheet.indexOf("t2-pickup-confirm") + 1200);
  assert.doesNotMatch(block, /Modal|SheetModalT2|window\.confirm|role="dialog"|alert\(/);
  // «تغيير» يفتح منتقي الانطلاق، والتقديرُ يُعاد لأيِّ نقطة انطلاقٍ جديدة (`pickup` في اعتماديّات التسعير)
  assert.match(home, /pickupConfirm:/);
  assert.match(sheet, /\[pickup, dropoff, stops, key\]/);
  // الإذنُ المرفوض: رسالةٌ وزرٌّ يفتح إعدادَ الموقع، والاختيارُ على الخريطة في الأثناء
  assert.match(riderHome, /locationOff/);
  assert.match(home, /openPermission\("location"\)/);
});

test("العنوانُ بلا فاصلةٍ فارغة في احتياط Mapbox (geocode.ts)", () => {
  const source = readFileSync(new URL("../src/lib/geocode.ts", import.meta.url), "utf8");
  assert.match(source, /export function tidyAddress/);
  // لا `full_address` يُعرض خاماً
  assert.doesNotMatch(source, /\?\? properties\?\.full_address \?\?/);
  assert.doesNotMatch(source, /return first\?\.full_address \?\?/);
});

test("ضبطُ الانطلاق بالدبّوس يبدأ من الانطلاق لا من حيث وقفت الخريطة", () => {
  const home = readFileSync(new URL("../src/screens/Home.tsx", import.meta.url), "utf8");
  assert.match(home, /function adjustPickup\(\) \{\s*if \(pickup\) map\.current\?\.flyTo\(pickup/);
  // لا بابَ من الورقة أو البحث يفتح دبّوسَ الانطلاق مباشرةً
  assert.doesNotMatch(home, /onChange: \(\) => \([^)]*setPhase\("pick-pickup"\)/);
  assert.doesNotMatch(home, /openSearch\("pickup"\) : setPhase\("pick-pickup"\)/);
});

test("الطلبُ يحمل اسمَ الانطلاق الآليّ لا فراغاً", () => {
  const home = readFileSync(new URL("../src/screens/Home.tsx", import.meta.url), "utf8");
  assert.equal((home.match(/pickup_address: pickupAddress \?\? pickupLine,/g) ?? []).length, 2);
  assert.doesNotMatch(home, /pickup_address: pickupAddress,/);
});

test("بلا انطلاقٍ معروفٍ تُختار الوجهةُ ثمّ الانطلاقُ بالدبّوس — لا «موقعي الحالي» عن موقعٍ مرفوض", () => {
  const home = readFileSync(new URL("../src/screens/Home.tsx", import.meta.url), "utf8");
  assert.equal((home.match(/setPhase\(pickup \? "confirm" : "pick-pickup"\);/g) ?? []).length >= 3, true);
  assert.match(home, /locationState === "denied" \? tr\("حدّد نقطة الانطلاق"\)/);
});
