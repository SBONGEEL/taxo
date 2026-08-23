/** يقارن **مفاتيحَ السوق في بيئةٍ حيّة** بما تشحنه الشجرةُ فعلاً، ويسمّي المختلف.
 *
 * **علّتُه واقعةٌ لا احتمال** (2026-08-21): الأردنُ على الإنتاج كان ينشر
 * `verification: firebase` بينما `otp_verification_enabled` مشتعل — **تحققٌ
 * مطلوبٌ ومستحيل**، فلا أحدَ يسجّل. أُصلح على جهاز التطوير في 2026-08-19، **ولم
 * يُنقل**، ولم يكشفه شيءٌ حتى قُرئ بالصدفة بعد شهر.
 *
 * **ولا يراه أيُّ حارسٍ قائم**: حرّاسُنا يقرؤون **الشجرة**، والفرقُ هنا **صفٌّ في
 * قاعدةِ بيئةٍ تعمل**. وهو **الشكلُ العاشر في لباسٍ ثالث**: شجرةٌ خضراءُ لا تقول
 * شيئاً عمّا يجري في بيئة.
 *
 * ### والمرجعُ ليس جهازَ التطوير، وهذا مقيسٌ لا مذهب
 *
 * أولُ صياغةٍ قارنت التطويرَ بالإنتاج مباشرةً فأخرجت **ثلاثةَ عشرَ سطراً، اثنا عشرَ
 * منها ضجيج**: قاعدةُ التطوير **تُبدَّل عمداً** في كل جولةٍ بصرية، وقاعدةُ هذا
 * المشروع مكتوبةٌ منذ 10-ج: **«`FEATURE_DEFAULTS` هي جوابُ ما يُشحن، لا
 * `SELECT * FROM feature_flags`»**. وحارسٌ يصيح على سليمٍ يُطفأ، فيسقط معه ما
 * يمسكه حقاً.
 *
 * فالمرجعُ **ما تشحنه `scripts/seed.py`**، ويُقرأ **من الوحدة نفسِها** لا بتحليلِ
 * نصّها — فلا يفترق المرجعُ عمّا يُشحن.
 *
 * ### وقاعدةٌ لا تحتاج بيئةً ثانيةً أصلاً
 *
 * **سوقٌ يشترط التحقق ولا ينشر قناةً تعمل = عطبٌ في نفسه.** لا يحتاج مقارنةً بشيء:
 * `firebase` يردّ `billing-not-enabled` (رُفض Blaze)، و`none` تعني لا قناة. وهذه
 * وحدَها كانت تكفي لكشفِ ما كُشف بالصدفة.
 *
 * الاستعمال: `bash scripts/check-markets.sh https://stg-api.tajora.ly`
 */

import { readFileSync } from "node:fs";
import { argv, exit } from "node:process";
import { certify } from "./certify.mjs";

/** اختلافاتٌ **مقصودةٌ بقرار**، ولكلٍّ نصُّ سببه — لا قائمةَ أعذارٍ صامتة.
 *  ويُقاس طولُ السبب: عذرٌ بلا سبب يسقط الفحصَ أيضاً. */
const DELIBERATE = {
  // **حالتان يُستثنيان: قناةُ سوقٍ (`code/verification`) أو مفتاحٌ (`code/key`).**
  "JO/verification":
    "قرارُ المالك 2026-08-21: الأردنُ على الإنتاج بلا قناةٍ عاملةٍ **عن قصد**، " +
    "و`whatsapp_otp_enabled` يبقى مطفأً حتى تصل **الشريحةُ الأردنية**. رقمُ " +
    "الإرسال هناك بريطانيٌّ عارٍ، ورسالةُ تحققٍ من رقمٍ أجنبيٍّ مجهولٍ مشكَّلةٌ " +
    "كالاحتيال — وهي التي تُبلَّغ فيُحظر الرقم. فالتسجيلُ هناك مغلقٌ بعلمٍ لا " +
    "بسهو (حسابان، ولا كبتنَ واحد). **ويوم تصل الشريحة يُحذف هذا السطرُ أولاً**، " +
    "فيصير الفحصُ هو ما يذكّر بإشعال المفتاح.",
};

/** قنواتٌ لا تُعدّ قناةً عاملةً، ولكلٍّ سببُ سقوطه — لا قائمةَ أسماء. */
const DEAD_CHANNELS = {
  firebase: "يردّ `auth/billing-not-enabled` — رُفضت خطةُ Blaze",
  none: "لا قناةَ أصلاً",
};

const [base, defaultsPath] = [argv[2], argv[3]];
if (!base || !defaultsPath) {
  console.error("الاستعمال عبر `scripts/check-markets.sh` — لا يُنادى مباشرةً");
  exit(2);
}

const shipped = JSON.parse(readFileSync(defaultsPath, "utf8"));
const url = `${base.replace(/\/$/, "")}/api/v1/config`;
const response = await fetch(url, { cache: "no-store" });
if (!response.ok) {
  console.error(`✗ ${url} ردّ ${response.status}`);
  exit(1);
}
const body = await response.json();

const live = new Map();
for (const country of body.countries ?? []) {
  live.set(country.country_code, {
    verification: country.verification ?? null,
    features: country.features ?? {},
  });
}

// **يُعلَن كم قُرئ** — صفرٌ مقروءٌ يُقرأ عطباً لا سلامة (قاعدةُ المِسبار ٥)
console.log(
  `  قُرئ: ${live.size} سوقاً ظاهراً من ${base} · ${Object.keys(shipped).length} سوقاً في المشحون`,
);
// **يُقاس بوصفه بيئةً منشورة.** وجهازُ التطوير يُبدَّل عمداً في كلِّ جولةٍ بصرية،
// فظهورُه مختلفاً هنا **صوابٌ لا ضجيج** — وقراءةُ حمرتِه حكماً على الشحن خطأٌ
// يقود إلى إطفاء الفحص.
console.log("  (يُقاس بوصفه بيئةً منشورة — جهازُ التطوير يُبدَّل عمداً فيفترق بحقّ)");
if (live.size === 0 || Object.keys(shipped).length === 0) {
  console.error("✗ جانبٌ لم يعطِ سوقاً واحداً — لا يُقرأ هذا سلامةً");
  exit(1);
}

const problems = [];
const excused = [];

// ١) القاعدةُ القائمةُ بنفسها: تحققٌ مشترطٌ بقناةٍ ميتة
for (const [code, market] of live) {
  if (!market.features.otp_verification_enabled) continue;
  const dead = DEAD_CHANNELS[market.verification ?? "none"];
  if (!dead) continue;
  const line =
    `${code}: التحققُ **مشترطٌ** والقناةُ المنشورة «${market.verification}» — ${dead}. ` +
    `فلا أحدَ يسجّل في هذا السوق.`;
  const reason = DELIBERATE[`${code}/verification`];
  if (reason && reason.trim().length > 20) excused.push([line, reason]);
  else problems.push(line);
}

// ٢) ما يفترق عمّا تشحنه الشجرة
for (const [code, expected] of Object.entries(shipped)) {
  const market = live.get(code);
  if (!market) {
    // سوقٌ مخفيٌّ لا ينشره `/config` — يُقاس بما شُحن لا يُتجاوَز
    if (expected.country_visible) {
      problems.push(`${code}: يُشحن ظاهراً ولا ينشره ${base}`);
    }
    continue;
  }
  for (const [key, want] of Object.entries(expected)) {
    const got = market.features[key] ?? false;
    if (got === want) continue;
    const reason = DELIBERATE[`${code}/${key}`];
    const line = `${code}/${key} — يُشحن ${want ? "مشتعلاً" : "مطفأً"} · و${base} ${got ? "مشتعل" : "مطفأ"}`;
    if (reason && reason.trim().length > 20) excused.push([line, reason]);
    else problems.push(line);
  }
}

// **عذرٌ باقٍ بعد زوال سببه كذبةٌ تُقرأ حارساً**
for (const key of Object.keys(DELIBERATE)) {
  const [code, feature] = key.split("/");
  const market = live.get(code);
  if (!market) continue;
  if (feature === "verification") {
    // **عذرُ قناةٍ يبيد حين تصير القناةُ حيّة** — لا حين تتفق البيئتان
    if (!DEAD_CHANNELS[market.verification ?? "none"]) {
      problems.push(`${key}: عذرٌ بائدٌ — القناةُ «${market.verification}» تعمل، فاحذفه`);
    }
    continue;
  }
  if (!shipped[code]) continue;
  if ((market.features[feature] ?? false) === shipped[code][feature]) {
    problems.push(`${key}: عذرٌ بائدٌ — لم يعد مختلفاً، فاحذفه`);
  }
}

if (excused.length) {
  console.log("\n  اختلافاتٌ مُعلَنةٌ بقرار:");
  for (const [line, reason] of excused) console.log(`  ○ ${line}\n    ${reason}`);
}
if (problems.length) {
  console.error("\n✗ ما لا قرارَ خلفه:");
  for (const line of problems) console.error(`  ${line}`);
  console.error("\n  إمّا يُنقل الصفُّ، أو يُكتب سببُه في `DELIBERATE`.");
  exit(1);
}
certify("check:markets", "\n✓ السوقُ الحيُّ يوافق ما يُشحن، أو يفترق بقرارٍ مكتوب.");
