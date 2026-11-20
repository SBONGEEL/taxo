/** «تعديل الوجهة» — متى يُرسم الزرّ (SPEC §١٠٩-أ): المفتاحُ مطفأً لا زرّ، ولكلِّ طورٍ مفتاحُه، ولا زرَّ لما لا يُعدَّل بنوعه. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { canChangeDestination, destinationPhase } from "../src/lib/destination-change.ts";

const ride = (status: string, editable = true) => ({ status, destination_editable: editable }) as never;

test("مطفأان ⇒ لا زرَّ في أيِّ طور", () => {
  for (const status of ["searching", "accepted", "arrived", "in_progress"]) {
    assert.equal(canChangeDestination(ride(status), { searching: false, inRide: false }), false);
  }
});

test("لكلِّ طورٍ مفتاحُه — البحثُ لا يفتح ما بعد القبول", () => {
  const onlySearching = { searching: true, inRide: false };
  assert.equal(canChangeDestination(ride("searching"), onlySearching), true);
  assert.equal(canChangeDestination(ride("requested"), onlySearching), true);
  assert.equal(canChangeDestination(ride("accepted"), onlySearching), false);
  const onlyRide = { searching: false, inRide: true };
  assert.equal(canChangeDestination(ride("searching"), onlyRide), false);
  assert.equal(canChangeDestination(ride("in_progress"), onlyRide), true);
});

test("لا زرَّ لما لا يُعدَّل بنوعه، ولا عند المحطة ولا بعد الانتهاء", () => {
  const both = { searching: true, inRide: true };
  assert.equal(canChangeDestination(ride("in_progress", false), both), false);
  assert.equal(canChangeDestination(ride("at_stop"), both), false);
  assert.equal(canChangeDestination(ride("completed"), both), false);
  assert.equal(destinationPhase("cancelled"), null);
});
