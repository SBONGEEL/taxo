/** **مركزُ الأذونات** (SPEC §١٠٣/٢٨) — المنطقُ الخالص: الترتيب، والأساسيّةُ المطفأة، والبصمة. بلا هاتف. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { ESSENTIAL, PERMISSION_META, SENSITIVE, essentialsOff, ordered, reportKey } from "../src/lib/permissions-center.ts";

const rows = [
  { key: "microphone", state: "off" },
  { key: "autostart", state: "unknown" },
  { key: "overlay", state: "off" },
  { key: "notifications", state: "on" },
  { key: "location_background", state: "off" },
  { key: "location", state: "off" },
] as const;

test("الأساسيّةُ أوّلاً بترتيبها ثمّ الباقي", () => {
  assert.deepEqual(
    ordered([...rows], "driver").map((r) => r.key),
    ["location", "location_background", "notifications", "overlay", "autostart", "microphone"],
  );
  assert.deepEqual(ordered([...rows], "rider").slice(0, 2).map((r) => r.key), ["location", "notifications"]);
});

test("المطفأُ الأساسيّ وحدَه — و«لا يُعرف» لا يُعدّ مطفأً", () => {
  assert.deepEqual(essentialsOff([...rows], "driver"), ["location", "location_background", "overlay"]);
  assert.deepEqual(essentialsOff([...rows], "rider"), ["location"]);
  assert.ok(!essentialsOff([...rows], "driver").includes("autostart" as never));
});

test("البصمةُ لا تتأثّر بالترتيب، وكلُّها مشتعلةٌ بصمةٌ فارغة", () => {
  assert.equal(reportKey(["overlay", "battery"]), reportKey(["battery", "overlay"]));
  assert.equal(reportKey([]), "");
});

test("كلُّ أساسيٍّ له سببٌ مكتوبٌ للتطبيق الذي يطلبه، وكلُّ حسّاسٍ له خطوات", () => {
  for (const app of ["driver", "rider"] as const) {
    for (const key of ESSENTIAL[app]) assert.ok(PERMISSION_META[key].why[app].length > 10, `${app}:${key}`);
  }
  for (const key of SENSITIVE) assert.ok(PERMISSION_META[key].steps.length >= 2, key);
});
