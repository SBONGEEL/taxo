/** **جسرُ iOS** (`lib/native-ios.ts`) — المنطقُ الخالص: متى تُعلن المكالمةُ للنظام، وما يُرسم من الرحلة على شاشة القفل. بلا هاتف. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { nativeCallStep, rideActivity } from "../src/lib/native-ios-logic.ts";

const tr = (text: string) => text;

const call = (stage: string, callId: string | null = "c1", outgoing = true) => ({ stage, callId, outgoing, muted: false });

test("الصادرةُ تُعلن حين يظهر معرّفُها، والواردةُ لا تُعلن والتطبيقُ ظاهر", () => {
  assert.equal(nativeCallStep(null, call("dialing")), "start");
  assert.equal(nativeCallStep(call("preparing", null), call("dialing")), "start");
  assert.equal(nativeCallStep(null, call("incoming", "c2", false)), null);
});

test("الاتّصالُ يُعلن مرّةً عند «talking» لا مع كلِّ تحديث", () => {
  assert.equal(nativeCallStep(call("dialing"), call("talking")), "connected");
  assert.equal(nativeCallStep(call("talking"), call("talking")), null);
});

test("النهايةُ تُعلن لمكالمةٍ كانت حيّة — ولا تُعلن لما لم يبدأ", () => {
  assert.equal(nativeCallStep(call("talking"), call("hungup")), "end");
  assert.equal(nativeCallStep(call("talking"), null), "end");
  assert.equal(nativeCallStep(call("hungup"), null), null);
  assert.equal(nativeCallStep(null, null), null);
  assert.equal(nativeCallStep(call("preparing", null), null), null);
});

const driver = { name: "سامي", vehicle: { make: "Toyota", model: "Corolla", color: "أبيض", plate_number: "12-34567" } };

test("الراكب: لا نشاطَ بلا كبتن، والحالُ تُرسم بخطوتها ولوحتها", () => {
  assert.equal(rideActivity({ id: "r", status: "searching" }, "rider", tr), null);
  const accepted = rideActivity({ id: "r", status: "accepted", driver }, "rider", tr);
  assert.equal(accepted?.step, 1);
  assert.equal(accepted?.plate, "12-34567");
  assert.match(accepted?.detail ?? "", /سامي · Toyota · Corolla · أبيض/);
  assert.equal(rideActivity({ id: "r", status: "arrived", driver }, "rider", tr)?.step, 2);
  assert.equal(rideActivity({ id: "r", status: "at_stop", driver }, "rider", tr)?.step, 3);
});

test("المنتهيةُ والملغاةُ لا تُرسم — فينتهي النشاط", () => {
  for (const status of ["completed", "cancelled_by_rider", "cancelled_by_driver", "no_driver_found"]) {
    assert.equal(rideActivity({ id: "r", status, driver }, "rider", tr), null);
    assert.equal(rideActivity({ id: "r", status }, "driver", tr), null);
  }
});

test("الكبتن: العنوانُ من الرحلة لا من كبتنٍ لا يحمله", () => {
  const going = rideActivity({ id: "r", status: "accepted", pickup_address: "الدوار السابع" }, "driver", tr);
  assert.deepEqual(going, { title: "في الطريق إلى الراكب", detail: "الدوار السابع", plate: "", step: 1 });
  assert.equal(rideActivity({ id: "r", status: "in_progress", dropoff_address: "المطار" }, "driver", tr)?.detail, "المطار");
});
