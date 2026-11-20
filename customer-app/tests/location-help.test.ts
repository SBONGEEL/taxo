/** «لم نتمكن من تحديد موقعك» (SPEC §١٠٩-ج) — السببُ لكلِّ حالة، والنصُّ والزرُّ لكلِّ سبب. */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  actionFor,
  LOCATION_MESSAGE,
  locationCause,
  messageFor,
  WEAK_SIGNAL_MESSAGE,
} from "../src/lib/location-help.ts";

const none = { permission: "unknown", services: "unknown" } as const;

test("GPS مطفأ ⇒ «فتح إعدادات الموقع» — من الغلاف أو من رمز ٢", () => {
  assert.equal(locationCause({ errorCode: null, permission: "on", services: "off" }), "gps_off");
  assert.equal(locationCause({ errorCode: 2, ...none }), "gps_off");
  assert.deepEqual(actionFor("gps_off"), { label: "فتح إعدادات الموقع", key: "location_services" });
  assert.equal(messageFor("gps_off"), LOCATION_MESSAGE);
});

test("الإذنُ مرفوض ⇒ صفحةُ إذن التطبيق — والغلافُ يغلب رمزَ المتصفّح", () => {
  assert.equal(locationCause({ errorCode: 1, ...none }), "permission");
  assert.equal(locationCause({ errorCode: 2, permission: "off", services: "on" }), "permission");
  assert.equal(actionFor("permission")?.key, "location");
});

test("إشارةٌ ضعيفة ⇒ نصُّها وحدَه بلا صفحةِ إعداد", () => {
  assert.equal(locationCause({ errorCode: 3, ...none }), "weak");
  assert.equal(messageFor("weak"), WEAK_SIGNAL_MESSAGE);
  assert.equal(actionFor("weak"), null);
});

test("بلا إشارةٍ لا يُخمَّن سبب — والرسالةُ بنصّ المالك حرفاً", () => {
  assert.equal(locationCause({ errorCode: null, ...none }), "unknown");
  assert.equal(
    LOCATION_MESSAGE,
    "لم نتمكن من تحديد موقعك الحالي. تأكد أن زر الموقع (GPS) مفعّل في هاتفك، ثم اضغط تحديث الموقع",
  );
});
