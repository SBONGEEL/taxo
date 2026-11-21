#!/usr/bin/env node
// **لا معرّفَ مكرَّرٌ في تخطيطٍ أندرويديّ** (٢٠٢٦-١١-٢١): `lintVital` في بناء الإصدار يُسقط الحزمةَ عليه (أسقط `v2.0.1440`: `tw_car` مرّتين
// في سبعة تخطيطات ودجات)، **وCI الفرع لا يشغّل بناءَ الإصدار** — فالعطبُ يظهر عند الوسم وحدَه. ومعه: `RemoteViews` يلمس الأوّلَ وحدَه بصمت.
import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const dirs = ["customer-app", "driver-app"].map((app) => join(app, "android/app/src/main/res/layout"));
const bad = [];
let files = 0;
for (const dir of dirs) {
  if (!existsSync(dir)) continue;
  for (const name of readdirSync(dir).filter((f) => f.endsWith(".xml"))) {
    files += 1;
    const seen = new Map();
    for (const m of readFileSync(join(dir, name), "utf8").matchAll(/android:id="@\+id\/([A-Za-z0-9_]+)"/g)) {
      seen.set(m[1], (seen.get(m[1]) ?? 0) + 1);
    }
    for (const [id, n] of seen) if (n > 1) bad.push(`${join(dir, name)}: @+id/${id} ×${n}`);
  }
}
if (bad.length) {
  console.error("✗ check:layout-ids · معرّفٌ مكرَّرٌ في تخطيط — يُسقط lintVital بناءَ الإصدار:\n  " + bad.join("\n  "));
  process.exit(1);
}
console.log(`✓ check:layout-ids · ${files} تخطيطاً بلا معرّفٍ مكرَّر`);
