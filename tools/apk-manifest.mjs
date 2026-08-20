/** بيانُ الحزمتين — **يُولَّد من الملفّ نفسِه، ولا يُكتب بيد**.
 *
 * **والعلّةُ مقيسة (2026-08-21)**: كلتا الحزمتين تقولان `versionName=1.0`
 * و`versionCode=1` — **فرقمُ النسخة وحدَه لا يفرّق بناءً عن بناء**. ونسختان
 * على هذا الجهاز بالرقم نفسِه وبفارقِ خمسةِ أيامٍ وستةِ ميجابايت.
 *
 * **فالهويةُ بصمةٌ وتاريخٌ وحجم**، والرقمُ زينةٌ بجانبها. ومن يشتكي نقول له
 * «أيُّ بصمةٍ عندك» لا «أيُّ نسخة».
 *
 * **وهذا هو الشكلُ العاشر في موضعه الطبيعيّ**: صفحةٌ تعرض زرَّ تحميلٍ لا تعرف
 * ما خلفه. وقد كان قائماً فعلاً قبل هذا الملف — `app.tajora.ly/taxo-rider.apk`
 * يخدم بناءَ ١٤ آب وآخرُ بناءٍ ١٩ آب.
 */

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { argv, env, exit } from "node:process";
import process from "node:process";

const ROOT = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const OUT = join(ROOT, "landing", "downloads");

/** الحزمتان ومصدرُ كلٍّ — **مخرجُ البناء لا نسخةُ `public/`**.
 *
 * **و`public/` هي المصدرُ الثاني الذي أنشأ العطب**: نسخةٌ قديمةٌ تُنسخ إلى
 * `dist` مع كل بناءٍ فتُخدَم إلى الأبد. فالمصدرُ هنا **مخرجُ Gradle** وحدَه.
 */
const APPS = [
  { key: "rider", label: "تطبيق الراكب", src: "customer-app/android/app/build/outputs/apk/debug/app-debug.apk", name: "taxo-rider.apk" },
  { key: "driver", label: "تطبيق الكبتن", src: "driver-app/android/app/build/outputs/apk/debug/app-debug.apk", name: "taxo-driver.apk" },
];

function badging(file) {
  // **قراءةُ المجلد بـ`readdirSync` لا بـ`cmd /c dir`**: الثانيةُ تكسر على
  // مسارٍ فيه مسافة (`AppData\Local`) وتطبع سطرَ خطأٍ لا يُقرأ. قِيس 2026-08-21
  const base = env.LOCALAPPDATA
    ? join(env.LOCALAPPDATA, "Android", "Sdk", "build-tools")
    : "/usr/lib/android-sdk/build-tools";
  if (!existsSync(base)) return {};
  try {
    const dirs = readdirSync(base).sort();
    for (const dir of dirs.reverse()) {
      const aapt = join(base, dir, process.platform === "win32" ? "aapt2.exe" : "aapt2");
      if (!existsSync(aapt)) continue;
      const out = execFileSync(aapt, ["dump", "badging", file], { encoding: "utf8" });
      const NL = String.fromCharCode(10);
      const line = out.split(NL).find((l) => l.startsWith("package:")) ?? "";
      return {
        package: /name='([^']+)'/.exec(line)?.[1],
        version_name: /versionName='([^']+)'/.exec(line)?.[1],
        version_code: /versionCode='([^']+)'/.exec(line)?.[1],
      };
    }
    return {};
  } catch {
    // **غيابُ الأداة ليس فشلاً**: البصمةُ والتاريخُ هما الهوية، والرقمُ زينة
    return {};
  }
}

mkdirSync(OUT, { recursive: true });
const entries = [];
for (const app of APPS) {
  const src = join(ROOT, app.src);
  if (!existsSync(src)) {
    console.error(`✗ لا مخرجَ بناءٍ لـ${app.label}: ${app.src}`);
    console.error("  ابنِ الحزمةَ أولاً — ولا تُنشر صفحةٌ بزرٍّ يشير إلى لا شيء.");
    exit(1);
  }
  const bytes = readFileSync(src);
  const stat = statSync(src);
  copyFileSync(src, join(OUT, app.name));
  entries.push({
    key: app.key,
    label: app.label,
    file: app.name,
    size_bytes: stat.size,
    sha256: createHash("sha256").update(bytes).digest("hex"),
    built_at: stat.mtime.toISOString(),
    ...badging(src),
  });
}

// **`generated_at` ليس هويةَ الحزمة**: يقول متى وُلِّد البيان، والهويةُ
// `sha256` و`built_at`. وخلطُهما يجعل إعادةَ توليدٍ تبدو بناءً جديداً
const manifest = { generated_at: new Date().toISOString(), apps: entries };
writeFileSync(join(OUT, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n", "utf8");

console.log(`✓ بيانُ الحزم — ${entries.length} حزمة`);
for (const e of entries) {
  console.log(`  ${e.label.padEnd(16)} ${(e.size_bytes / 1048576).toFixed(1)} م.ب  ${e.sha256.slice(0, 12)}  ${e.built_at.slice(0, 16).replace("T", " ")}  ${e.version_name ?? "?"}`);
}
