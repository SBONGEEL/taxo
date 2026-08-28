/** يرفض بناءً يخالف هدفَه — بوّابةٌ قبل `vite build` وأخرى بعده.
 *
 * **القاعدةُ كانت مكتوبةً ووقعت مرتين**، وهذا ما يوقفها: `dist` هنا ليس ناتجَ
 * تحقّقٍ بل **ما تخدمه الحاويةُ للهاتف عبر النفق**. فبناءٌ بلا
 * `VITE_API_BASE_URL` يكتب فوقه نسخةً تنادي `http://localhost:8001` — عنوانٌ
 * لا وجودَ له داخل الهاتف — فيقف التطبيقُ على شاشة الإقلاع يقول «الشبكة
 * ضعيفة» بينما الشبكةُ سليمةٌ والخلفيةُ تردّ ٢٠٠ من داخل الـWebView نفسِه.
 *
 * **وما يجعل هذا الفخَّ صامتاً**: البناءُ ينجح، وtsc يمرّ،
 * و`check:scale`/`check:enums`/`check:config` كلُّها خضراء — لأن الخطأ ليس في
 * الكود بل في **متغيّرٍ لم يُمرَّر**، ولا يظهر إلا على جهازٍ آخر.
 *
 * **وهو بوّابتان لا واحدة**، وترتيبُهما هو الفرقُ بين تحذيرٍ وحماية:
 *
 * - `--intent` **قبل** البناء: يمنع كتابةَ `dist` أصلاً. وبغيره يقع الضررُ ثم
 *   يُقال لك إنه وقع — والحاويةُ تخدم النسخةَ الخاطئة بينما تقرأ الرسالة.
 * - `--dist` **بعده**: يقيس الناتجَ نفسَه، فيمسك ما لا يعرفه المتغيّر — ملفاً
 *   قديماً بقي في المجلد، أو متغيّراً مُرِّر ولم يلتقطه البناء.
 *
 * والحالتان:
 *
 * - **هدفٌ بعيدٌ مُصرَّحٌ به**: يجب أن يظهر في `dist`، **وألّا يظهر معه العنوانُ
 *   الاحتياطيّ** — ظهورُه يعني ملفاً من بناءٍ سابق ما زال يُخدَم.
 * - **بلا تصريح**: بناءٌ محليٌّ، **مرفوضٌ افتراضاً** لأنه يكتب فوق ما يخدمه
 *   الجهاز. ومن أراده يقولها: `DEV_BUILD=1`. فالافتراضُ آمن، والقصدُ يُعلَن،
 *   ولا يقع الخطأ بالسكوت. وللتحقّق من الأنواع وحدَها: `npm run lint`.
 */

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { certify } from "../../tools/certify.mjs";

const DIST = new URL("../dist/", import.meta.url).pathname.replace(
  /^\/([A-Za-z]:)/,
  "$1",
);
const FALLBACK = /https?:\/\/(localhost|127\.0\.0\.1):\d+/g;

const mode = process.argv[2] === "--intent" ? "intent" : "dist";
const target = (process.env.VITE_API_BASE_URL ?? "").trim();
const isRemote = target !== "" && !/localhost|127\.0\.0\.1/.test(target);

function refuseUndeclared() {
  console.error(
    [
      "✗ بناءٌ بلا هدف — و`dist` هنا هو ما تخدمه الحاويةُ للهاتف.",
      "  للنفق:   VITE_API_BASE_URL=https://api.tajora.ly npm run build",
      "  محلياً:  DEV_BUILD=1 npm run build",
      "  وللفحص وحدَه بلا بناء: npm run lint",
    ].join("\n"),
  );
  process.exit(1);
}

/** **رفضٌ يسمّي علّتَه هو** — لا الرسالةَ العامّة.
 *
 * **ووقع مقيساً 2026-08-29**: بُنيت الثلاثةُ بـ`DEV_BUILD=1` وحدَها، فمرّت
 * البوّابةُ **والحزمةُ لا تقلع**: `client.ts` يرمي عند تحميل الوحدة، فتخدم
 * حاويةُ التطوير حزمةً تُظهر «تعذّر الوصول» ولا تصل شاشةُ دخولٍ أصلاً.
 * **وأولُ قياسٍ بالمتصفّح بعدها أعطى خُضرةً كاذبة** — «الزرُّ غائب» وكانت
 * الشاشةُ كلُّها غائبة.
 *
 * **ورسالةٌ عامّةٌ هنا تُرسل القارئَ إلى الطريق الخطأ**: من يقرأ «بناءٌ بلا
 * هدف» وقد كتب `DEV_BUILD=1` بيده يظنّ الحارسَ لم يرَ إذنَه.
 */
function refuseEmptyLocal() {
  console.error(
    [
      "✗ `DEV_BUILD=1` بلا `VITE_API_BASE_URL` — **إذنٌ بلا عنوان**.",
      "  والحزمةُ تُبنى ولا تقلع: العنوانُ يُقرأ عند تحميل الوحدة، وغيابُه",
      "  يرمي قبل أن تُرسم شاشة — فتخدم الحاويةُ حزمةً تقول «تعذّر الوصول».",
      "  محلياً:  DEV_BUILD=1 VITE_API_BASE_URL=http://localhost:8001 npm run build",
    ].join("\n"),
  );
  process.exit(1);
}

function declared() {
  if (isRemote) {
    console.log(`✓ الهدف مُصرَّحٌ به: ${target}`);
    return true;
  }
  if (process.env.DEV_BUILD === "1") {
    // **الإذنُ ليس عنواناً** (صُحّح 2026-08-29): كان `DEV_BUILD=1` وحدَه يمرّ
    // **ولو كان `VITE_API_BASE_URL` فارغاً** — وهي عائلةُ الاحتياط الصامت
    // نفسُها التي نُزعت من `POSTGRES_PASSWORD:?`: قيمةٌ تقرّر إلى أين تذهب
    // البيانات لا تُترك للسكوت.
    if (target === "") refuseEmptyLocal();
    console.log(`✓ بناءٌ محليٌّ مُصرَّحٌ به (DEV_BUILD=1): ${target}`);
    return true;
  }
  return false;
}

// البوّابةُ الأولى — قبل أن يُكتب شيء
if (mode === "intent") {
  if (!declared()) refuseUndeclared();
  process.exit(0);
}

function bundles(dir) {
  const found = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...bundles(path));
    else if (/\.(js|html)$/.test(entry.name)) found.push(path);
  }
  return found;
}

if (!existsSync(DIST)) {
  console.error("✗ لا مجلد dist — شغّل البناء أولاً");
  process.exit(1);
}

const files = bundles(DIST);
const offenders = [];
for (const file of files) {
  const hits = [...new Set(readFileSync(file, "utf8").match(FALLBACK) ?? [])];
  if (hits.length) offenders.push([file.slice(DIST.length), hits.join("، ")]);
}

if (!isRemote) {
  if (!declared()) refuseUndeclared();
  process.exit(0);
}

if (!files.some((file) => readFileSync(file, "utf8").includes(target))) {
  console.error(`✗ الهدف ${target} لا يظهر في dist — البناءُ لم يلتقط المتغيّر`);
  process.exit(1);
}
if (offenders.length) {
  console.error(`✗ الهدف ${target} ومع ذلك بقي عنوانٌ محليٌّ في dist:`);
  for (const [file, hits] of offenders) console.error(`  ${file} → ${hits}`);
  console.error("  احذف dist وأعد البناء — ملفٌّ قديمٌ ما زال يُخدَم من الحاوية.");
  process.exit(1);
}

certify("check:dist-target", `✓ dist يوافق هدفَه (${target}) ولا عنوانَ محليّاً فيه`);
