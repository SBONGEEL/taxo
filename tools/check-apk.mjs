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
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { argv, exit } from "node:process";

const ROOT = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const MANIFEST = join(ROOT, "landing", "downloads", "manifest.json");
const base = argv[2] ?? "";

/** الهدفُ المعلَنُ لكلِّ غلاف. **يُصرَّح ولا يُخمَّن**: غلافٌ بلا هدفٍ مكتوبٍ هنا
 *  يُسقط الفحص، فلا يمرّ تطبيقٌ ثالثٌ بالسكوت. */
const SHELL_TARGET = {
  rider: "app.tajora.ly",
  driver: "driver.tajora.ly",
};

/** يقرأ `server.url` **من داخل ملفِّ الحزمة**، لا من الشجرة. */
function shellTarget(path) {
  try {
    const json = execFileSync(
      "python",
      ["-c",
       "import zipfile,sys,json;z=zipfile.ZipFile(sys.argv[1]);" +
       "n=[x for x in z.namelist() if x.endswith('capacitor.config.json')];" +
       "print(json.loads(z.read(n[0])).get('server',{}).get('url','') if n else '')",
       path],
      { encoding: "utf8" },
    ).trim();
    return json ? new URL(json).host : null;
  } catch {
    return null;
  }
}

if (!existsSync(MANIFEST)) {
  console.error("✗ لا بيانَ حزم — شغّل `node tools/apk-manifest.mjs` أولاً.");
  exit(1);
}
const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));
if (!manifest.apps?.length) {
  console.error("✗ بيانٌ بلا حزم — والحارسُ الذي لا يقيس شيئاً يمرّ أخضرَ أبداً.");
  exit(1);
}

console.log(`\n  الحزم — البصمةُ والهدف`);
let bad = 0;
let wrongTarget = 0;
for (const app of manifest.apps) {
  // ١) المبنيُّ (مصدرُ البيان)
  const local = join(ROOT, "landing", "downloads", app.file);
  const onDisk = existsSync(local)
    ? createHash("sha256").update(readFileSync(local)).digest("hex")
    : null;
  const mark = onDisk === app.sha256 ? "✓" : "✗";
  if (onDisk !== app.sha256) bad += 1;
  console.log(`  ${mark} ${app.label.padEnd(16)} البيان ${app.sha256.slice(0, 10)} · على القرص ${onDisk?.slice(0, 10) ?? "غائب"}`);

  // ١-ب) **وإلى أين تشير** — يُقرأ من داخل الملف لا من الشجرة
  const want = SHELL_TARGET[app.key];
  if (!want) {
    bad += 1;
    console.log(`    ✗ غلافٌ بلا هدفٍ مُصرَّحٍ في \`SHELL_TARGET\`: ${app.key}`);
  } else if (onDisk) {
    const got = shellTarget(local);
    if (got === want) console.log(`    ✓ يشير إلى ${got}`);
    else {
      bad += 1;
      wrongTarget += 1;
      console.log(`    ✗ يشير إلى ${got ?? "(تعذّرت القراءة)"} والمُصرَّحُ ${want}`);
    }
  }

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
  // **يُسمّى العطبُ بعينه**: حارسٌ يخطئ في تسمية ما وجده يعلّم إصلاحاً خاطئاً
  if (wrongTarget) {
    console.error("");
    console.error("✗ حزمةٌ تشير إلى غير هدفها المُصرَّح — ومن يحمّلها يفتح");
    console.error("  تطبيقاً يخاطب خادماً غيرَ الذي يظنّه.");
    console.error("  يُعدَّل `capacitor.config.ts` ثم يُعاد بناءُ الغلاف، ثم:");
    console.error("    node tools/apk-manifest.mjs");
  }
  if (bad > wrongTarget) {
    console.error("");
    console.error("✗ ما يُحمَّل ليس ما بُني — وهذا لا يظهر في أيِّ فحصٍ آخر.");
    console.error("  أعد توليدَ البيان ثم انشر:  node tools/apk-manifest.mjs");
  }
  exit(1);
}
console.log("\n✓ البصمةُ واحدةٌ في كل موضعٍ قِيس.");
