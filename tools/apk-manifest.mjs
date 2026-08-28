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
 *
 * ---
 *
 * **⚠ شرطُ البناء: JDK 21 — لا 17 ولا 24** (قرارُ المالك 2026-08-22: «سجّل
 * شرطَ البناء حيث يُقرأ»). `gradlew assembleRelease` يسقط على غيره، **ولا
 * يُكتشف إلا عند الفشل** — ورسالتُه تتكلّم عن توافُقِ فئاتٍ لا عن نسخةِ جافا،
 * فيذهب قارئُها إلى الاعتماديات.
 *
 * **وموضعُه هنا لا في وثيقةٍ جانبية**: هذا الملفُّ هو ما يُقرأ حين تُبنى
 * الحزمة، **وشرطٌ يُكتب حيث لا يُقرأ ليس شرطاً** — وهي قاعدةُ «المكتوبُ لا
 * يُطبَّق، والحارسُ يُطبَّق» في أضعف صورها: توثيقٌ في موضعه.
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

/** **والمسارُ مسارُ نكهةٍ لا مسارُ نوعِ بناء** (صُحّح 2026-08-28): منذ صارت
 * القنواتُ نكهتين (`channels.json`) لم يعد `apk/release/app-release.apk`
 * موجوداً أصلاً — **والوسمُ كان سيبني أربعاً موقَّعةً ثم لا يجد ما ينشره**.
 * **والصفحةُ العامّةُ تحمل العامّةَ وحدَها**: التجريبيّةُ تخاطب جهازَ مطوّرٍ،
 * ونشرُها في صفحةِ تحميلٍ عامّةٍ يعطي الناسَ تطبيقاً يتوقّف حين يُطفأ حاسوب.
 */
/** الحزمتان ومصدرُ كلٍّ — **مخرجُ البناء لا نسخةُ `public/`**.
 *
 * **و`public/` هي المصدرُ الثاني الذي أنشأ العطب**: نسخةٌ قديمةٌ تُنسخ إلى
 * `dist` مع كل بناءٍ فتُخدَم إلى الأبد. فالمصدرُ هنا **مخرجُ Gradle** وحدَه.
 */
const APPS = [
  { key: "rider", label: "تطبيق الراكب", src: "customer-app/android/app/build/outputs/apk/public/release/app-public-release.apk", name: "taxo-rider.apk" },
  { key: "driver", label: "تطبيق الكبتن", src: "driver-app/android/app/build/outputs/apk/public/release/app-public-release.apk", name: "taxo-driver.apk" },
];

function badging(file) {
  // **قراءةُ المجلد بـ`readdirSync` لا بـ`cmd /c dir`**: الثانيةُ تكسر على
  // مسارٍ فيه مسافة (`AppData\Local`) وتطبع سطرَ خطأٍ لا يُقرأ. قِيس 2026-08-21
  // **جذورٌ ثلاثةٌ لا واحد**: متغيّرا SDK أولاً (وهما ما يضبطه عاملُ
  // GitHub)، ثم مسارُ ويندوز، ثم مسارُ دبيان. **وكان الأولان غائبَين**
  // فخرج البيانُ من CI بلا `versionCode` — و**الحارسُ الذي يمنع بناءً برقمٍ
  // قديمٍ يقرأ ذلك الحقلَ نفسَه**، فسكت حيث صار أهمَّ ما يكون.
  const roots = [
    env.ANDROID_SDK_ROOT && join(env.ANDROID_SDK_ROOT, "build-tools"),
    env.ANDROID_HOME && join(env.ANDROID_HOME, "build-tools"),
    env.LOCALAPPDATA && join(env.LOCALAPPDATA, "Android", "Sdk", "build-tools"),
    "/usr/lib/android-sdk/build-tools",
  ].filter(Boolean);
  const base = roots.find((dir) => existsSync(dir));
  if (!base) return {};
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
    // **وشرطُ البناء يُقال هنا لأن هنا يُقرأ** (2026-08-22): `gradlew` يطلب
    // **Java 21**، ورسالتُه عند غيابها (`languageVersion=21 … No locally
    // installed toolchains match`) صحيحةٌ ولا تقول **أين تُوجد** — وعلى هذا
    // الجهاز المثبَّتُ ١٧ و**النسخةُ ٢١ داخل Android Studio**. فبناءُ الحزم
    // كان موقوفاً على شيءٍ لا يُكتشف إلا عند الفشل، وهو ما وقع 2026-08-22.
    console.error("");
    console.error("  ومقيسٌ على هذا الجهاز — والبناءُ يحتاج Java 21 لا 17:");
    console.error('    export ANDROID_SDK_ROOT="$LOCALAPPDATA/Android/Sdk"');
    console.error('    export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"');
    console.error(`    ( cd ${app.src.split("/android/")[0]}/android && ./gradlew assembleDebug )`);
    console.error("  ويسبقه `npx cap sync android` وإلا حملت الحزمةُ حزمةَ ويبٍ قديمة.");
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

// **بناءٌ جديدٌ بـ`versionCode` قديمٍ لا يعرفه أندرويد** (2026-08-21).
//
// `versionCode` هو ما يقارن به النظامُ نسختين. فحزمةٌ **تغيّرت بصمتُها ولم
// يتغيّر رقمُها** تُقرأ عند أندرويد **النسخةَ نفسَها**: لا تحديثَ يُعرض،
// و«التثبيت» فوقها قد يُرفض أو يمرّ بلا أثرٍ ظاهر — **ومن يحمّل يظنّ أنه
// حدّث وهو لم يفعل**.
//
// **والبيانُ السابقُ هو الذاكرة**: لا عمودَ ولا ملفَّ حالةٍ ثانٍ. فإن وُجد
// بيانٌ قديم، تُقارَن به كلُّ حزمة.
//
// **وكلاهما `1` اليوم** — وهو مقبولٌ ما دامتا لم تُنشرا بعد؛ والحارسُ يبدأ
// عملَه من أول نشرةٍ ثانية.
const previous = existsSync(join(OUT, "manifest.json"))
  ? JSON.parse(readFileSync(join(OUT, "manifest.json"), "utf8"))
  : null;
const stale = [];
const unread = [];
for (const app of entries) {
  const before = previous?.apps?.find((a) => a.key === app.key);
  if (!before || before.sha256 === app.sha256) continue;
  // **ولا يُقرأ غيابُ الرقم سلامة** (قاعدةُ الحارس الخامسة): بلا `aapt2`
  // يخرج `version_code` فارغاً، و`Number(undefined)` هو `NaN` — وكلُّ مقارنةٍ
  // به تُرجع `false`، **فيمرّ الحارسُ صامتاً حيث بُني ليصيح**.
  if (app.version_code == null || before.version_code == null) {
    unread.push(app.label);
    continue;
  }
  const wasCode = Number(before.version_code);
  const nowCode = Number(app.version_code);
  if (nowCode <= wasCode) {
    stale.push(
      `${app.label}: البصمةُ تغيّرت (${before.sha256.slice(0, 8)} ← ` +
        `${app.sha256.slice(0, 8)}) و\`versionCode\` ما زال ${nowCode}`,
    );
  }
}
if (unread.length > 0) {
  console.error("");
  console.error("✗ تغيّرت البصمةُ ولم يُقرأ `versionCode` — **لم تُقس القاعدة**:");
  for (const label of unread) console.error(`  ${label}`);
  console.error("");
  console.error("  `aapt2` غيرُ موجود، فلا يُعرف أزاد الرقمُ أم لا.");
  console.error("  **وسكوتُ حارسٍ لم يقرأ شيئاً ليس سلامة** — ثبّت أدوات");
  console.error("  البناء، أو صرّح `ANDROID_SDK_ROOT`.");
  exit(1);
}

if (stale.length > 0) {
  console.error("");
  console.error("✗ بناءٌ جديدٌ برقمٍ قديم — وأندرويدُ لا يفرّق بينهما:");
  for (const line of stale) console.error(`  ${line}`);
  console.error("");
  console.error("  ارفع `versionCode` في `android/app/build.gradle` قبل النشر.");
  console.error("  ومن يحمّل برقمٍ لم يتغيّر يظنّ أنه حدّث وهو لم يفعل.");
  exit(1);
}

/** **الإيداعُ الذي بُنيت منه الحزمة — يُنشر معها** (شرطُ المالك 2026-08-21).
 *
 * **فمن حمّل يعرف ما حمّل، ونحن نعرف من أيِّ شجرة.** وبغيره تكون البصمةُ
 * هويةً بلا نسب: تفرّق حزمتين ولا تقول من أين جاءت أيٌّ منهما — فشكوى «هذه
 * تفعل كذا» لا يمكن ردُّها إلى سطر.
 *
 * **ويُقرأ من البيئة قبل `git`**: في CI الإيداعُ معلومٌ يقيناً
 * (`GITHUB_SHA`)، وعلى جهازٍ يُشتقّ. **والشجرةُ المتّسخةُ تُقال**: حزمةٌ
 * بُنيت من شجرةٍ فيها تعديلٌ غيرُ مودَع **لا تُنسب إلى إيداعٍ بحقّ**.
 */
function provenance() {
  const sha = env.GITHUB_SHA || run(["git", "rev-parse", "HEAD"]);
  // **`2>/dev/null` عبر `stdio`**: بلا وسمٍ يطبع git سطرَ خطأٍ يُقرأ عطباً
  // وليس عطباً — والغيابُ هنا الحالُ الطبيعيةُ على جهازٍ بين إصدارين
  const tag = env.GITHUB_REF_NAME || run(["git", "describe", "--tags", "--exact-match"], true);
  const dirty = env.GITHUB_SHA ? false : run(["git", "status", "--porcelain"]) !== "";
  return { commit: sha || null, tag: tag || null, dirty };
}

function run(cmd, quiet = false) {
  try {
    return execFileSync(cmd[0], cmd.slice(1), {
      cwd: ROOT,
      encoding: "utf8",
      stdio: quiet ? ["ignore", "pipe", "ignore"] : undefined,
    }).trim();
  } catch {
    return "";
  }
}

// **`generated_at` ليس هويةَ الحزمة**: يقول متى وُلِّد البيان، والهويةُ
// `sha256` و`built_at`. وخلطُهما يجعل إعادةَ توليدٍ تبدو بناءً جديداً
const manifest = {
  generated_at: new Date().toISOString(),
  ...provenance(),
  apps: entries,
};
writeFileSync(join(OUT, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n", "utf8");

console.log(`✓ بيانُ الحزم — ${entries.length} حزمة · إيداع ${(manifest.commit ?? "?").slice(0, 8)}${manifest.dirty ? " (شجرةٌ متّسخة)" : ""}${manifest.tag ? " · " + manifest.tag : ""}`);
for (const e of entries) {
  console.log(`  ${e.label.padEnd(16)} ${(e.size_bytes / 1048576).toFixed(1)} م.ب  ${e.sha256.slice(0, 12)}  ${e.built_at.slice(0, 16).replace("T", " ")}  ${e.version_name ?? "?"}`);
}
