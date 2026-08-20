/** **العمودُ الرابع في خطوة الصفر**: ما يُحمَّل من الصفحة = ما بُني.
 *
 * خطوةُ الصفر كانت ثلاثةَ أعمدة — المبنيُّ · ما تخدمه الحاويةُ · ما يصل عبر
 * النفق. **وصفحةُ التحميل تفتح عموداً رابعاً**: ملفٌّ يهبط على هاتفِ إنسانٍ
 * ويبقى فيه شهوراً.
 *
 * **والعطبُ كان قائماً قبل هذا الحارس** (قِيس 2026-08-21):
 * `app.tajora.ly/taxo-rider.apk` يخدم بناءَ **١٤ آب** وآخرُ بناءٍ **١٩ آب** —
 * أربعُ نسخٍ من الملف نفسِه على القرص، والمخدومةُ أقدمُها.
 *
 * **ولا يُقارَن بالنسخة**: قِيس أن الحزمتين تقولان `versionName=1.0`
 * و`versionCode=1`، ونسختان بفارقِ خمسةِ أيامٍ وستةِ ميجابايت تحملان الرقمَ
 * نفسَه. **فالمقارنةُ بالبصمة** — وهي الشيءُ الوحيد الذي لا يكذب.
 */

import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { argv, exit } from "node:process";

const ROOT = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const MANIFEST = join(ROOT, "landing", "downloads", "manifest.json");
const base = argv[2] ?? "";

if (!existsSync(MANIFEST)) {
  console.error("✗ لا بيانَ حزم — شغّل `node tools/apk-manifest.mjs` أولاً.");
  exit(1);
}
const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));
if (!manifest.apps?.length) {
  console.error("✗ بيانٌ بلا حزم — والحارسُ الذي لا يقيس شيئاً يمرّ أخضرَ أبداً.");
  exit(1);
}

console.log(`\n  الحزم — البصمةُ في أربعة مواضع`);
let bad = 0;
for (const app of manifest.apps) {
  // ١) المبنيُّ (مصدرُ البيان)
  const local = join(ROOT, "landing", "downloads", app.file);
  const onDisk = existsSync(local)
    ? createHash("sha256").update(readFileSync(local)).digest("hex")
    : null;
  const mark = onDisk === app.sha256 ? "✓" : "✗";
  if (onDisk !== app.sha256) bad += 1;
  console.log(`  ${mark} ${app.label.padEnd(16)} البيان ${app.sha256.slice(0, 10)} · على القرص ${onDisk?.slice(0, 10) ?? "غائب"}`);

  // ٢) وما يُحمَّل فعلاً من الصفحة — **إن أُعطي عنوانها**
  if (!base) continue;
  const url = `${base.replace(/\/$/, "")}/downloads/${app.file}`;
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const served = createHash("sha256")
      .update(Buffer.from(await response.arrayBuffer()))
      .digest("hex");
    const ok = served === app.sha256;
    if (!ok) bad += 1;
    console.log(`    ${ok ? "✓" : "✗"} ما يُحمَّل من ${new URL(url).host}: ${served.slice(0, 10)}`);
  } catch (error) {
    console.log(`    · لم يُقس (${String(error).slice(0, 40)}) — **ولا يُقرأ سكوتُه ضماناً**`);
  }
}

if (bad > 0) {
  console.error(
    "\n✗ ما يُحمَّل ليس ما بُني — وهذا لا يظهر في أيِّ فحصٍ آخر." +
      "\n  أعد توليدَ البيان ثم انشر:  node tools/apk-manifest.mjs",
  );
  exit(1);
}
console.log("\n✓ البصمةُ واحدةٌ في كل موضعٍ قِيس.");
