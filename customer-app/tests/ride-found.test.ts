/** **«تم العثور على كبتن»** — متى يُقال ومتى لا (أمرُ المالك ٢٠٢٦-١١-١٩). */
import assert from "node:assert/strict";
import { test } from "node:test";

import { foundNow } from "../src/lib/ride-found.ts";

test("من البحث إلى القبول للرحلة نفسِها ⇐ يُقال", () => {
  assert.equal(foundNow({ id: "r1", status: "searching" }, { id: "r1", status: "accepted" }), true);
  assert.equal(foundNow({ id: "r1", status: "requested" }, { id: "r1", status: "accepted" }), true);
});

test("رحلةٌ فُتحت مقبولةً، أو تبدّلت بأخرى، أو انتقلت إلى غير القبول ⇐ لا يُقال", () => {
  assert.equal(foundNow(null, { id: "r1", status: "accepted" }), false);
  assert.equal(foundNow({ id: "r0", status: "searching" }, { id: "r1", status: "accepted" }), false);
  assert.equal(foundNow({ id: "r1", status: "searching" }, { id: "r1", status: "cancelled" }), false);
  assert.equal(foundNow({ id: "r1", status: "accepted" }, { id: "r1", status: "arrived" }), false);
  assert.equal(foundNow({ id: "r1", status: "searching" }, null), false);
});
