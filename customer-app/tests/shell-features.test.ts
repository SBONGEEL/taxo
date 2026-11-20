/** **ميزاتُ A وB وC لغلاف 1367 فما فوق على أندرويد** (أمرُ المالك ١٨/١١ السادس، البند ٦) — `shell-features-core.ts`. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { BUBBLE_SHELL_KEYS, BUBBLE_SHELL_MIN_ANDROID, NEW_SHELL_KEYS, NEW_SHELL_MIN_ANDROID, shellAllowsFor } from "../src/lib/shell-features-core.ts";

test("الغلافُ القديمُ على أندرويد لا يقرأ مفتاحاً جديداً مشتعلاً — والجديدُ يقرؤه", () => {
  assert.equal(NEW_SHELL_MIN_ANDROID, 1367);
  assert.equal(shellAllowsFor("pickup_wait_timer", "android", 1118), false);
  assert.equal(shellAllowsFor("pickup_wait_timer", "android", 1366), false);
  assert.equal(shellAllowsFor("pickup_wait_timer", "android", 1367), true);
  assert.equal(shellAllowsFor("sms_autofill", "android", 2000), true);
});

test("مفاتيحُ الفقاعتين لا تُقرأ في غلاف المراحل الثلاث — حدُّها غلافُها", () => {
  assert.ok(BUBBLE_SHELL_MIN_ANDROID > NEW_SHELL_MIN_ANDROID);
  assert.equal(shellAllowsFor("bubble_radial_menu", "android", 1367), false);
  assert.equal(shellAllowsFor("rider_bubble", "android", BUBBLE_SHELL_MIN_ANDROID - 1), false);
  assert.equal(shellAllowsFor("rider_bubble", "android", BUBBLE_SHELL_MIN_ANDROID), true);
  assert.equal(shellAllowsFor("quick_replies", "android", null), false);
  assert.equal(shellAllowsFor("quick_replies", "web", null), true);
  for (const key of BUBBLE_SHELL_KEYS) assert.ok(!NEW_SHELL_KEYS.has(key), `${key} في القائمتين`);
});

test("رقمٌ لم يُعرف بعد على أندرويد يُقرأ مطفأً — لا يُفترض جديداً", () => {
  assert.equal(shellAllowsFor("status_bubble", "android", null), false);
});

test("iOS والمتصفّحُ وكلُّ مفتاحٍ خارج القائمة كما كانوا", () => {
  assert.equal(shellAllowsFor("pickup_wait_timer", "ios", 5), true);
  assert.equal(shellAllowsFor("pickup_wait_timer", "web", null), true);
  assert.equal(shellAllowsFor("voice_order_enabled", "android", 994), true);
  assert.equal(shellAllowsFor("open_map", "android", null), true);
});

test("نسختا التطبيقين متطابقتان بايتاً", () => {
  const here = readFileSync(new URL("../src/lib/shell-features-core.ts", import.meta.url));
  const there = readFileSync(new URL("../../driver-app/src/lib/shell-features-core.ts", import.meta.url));
  assert.ok(here.equals(there), "shell-features-core.ts افترق بين التطبيقين");
});
