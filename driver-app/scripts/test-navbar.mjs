#!/usr/bin/env node
/** **شريطُ الكبتن بعد رحلةٍ منتهية، وعودةُ الدفع بلا شاشةٍ وراءها** (SPEC §٧٦-س، بلاغُ المالك ٢٠٢٦-١٠-١٦) — يسقط على السلوك القديم.
 *
 *     node scripts/test-navbar.mjs
 *
 * **العطبُ في الراكب ونمطُه هنا**: حدثُ `ride_completed` يضع الرحلةَ المكتملةَ في السياق (`lib/ride.tsx`)، و`NavBar` كان يُخفي الشريطَ
 * **لأيِّ رحلةٍ** (`ride !== null`) — فيغيب بعد التحصيل والتقييم. **ورحلةٌ جاريةٌ وحدَها تُخفيه** (`isActive`). وعودةُ الاشتراك والشحن
 * (`PayReturnT2`) تمضي بـ`replace` فلا تبقى وراءها يعود إليها زرُّ الرجوع.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");

test("the bar is hidden by an active ride, not by a finished one", () => {
  const app = readFileSync(join(SRC, "App.tsx"), "utf8");
  assert.doesNotMatch(app, /const covered = ride !== null \|\|/, "NavBar يُخفي الشريطَ لرحلةٍ انتهت");
  assert.match(app, /const covered = isActive\(ride\) \|\|/);
});

test("the payment return leaves no screen behind", () => {
  const ret = readFileSync(join(SRC, "screens", "t2", "PayReturnT2.tsx"), "utf8");
  assert.doesNotMatch(ret, /navigate\([^)]*"\/wallet"\)\}/, "عودةُ الدفع تدفع المحفظةَ فوقها");
  assert.match(ret, /\{ replace: true \}/);
});
