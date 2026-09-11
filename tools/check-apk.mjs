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
import { allPairs } from "./channels.mjs";
import { reportTable } from "./check-hosts.mjs";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { argv, env, exit } from "node:process";
import { certify } from "./certify.mjs";

const ROOT = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const MANIFEST = join(ROOT, "landing", "downloads", "manifest.json");
const base = argv[2] ?? "";

/** الأزواجُ الأربعةُ (قناة × تطبيق) — **من `channels.json` لا من هنا**.
 *
 * **ولمَ الزوجُ لا الهدفُ وحدَه** (أربعُ نسخ، 2026-08-26): صار للتطبيق الواحد
 * نسختان تتعايشان — عامّةٌ تخاطب الخادم وتجريبيّةٌ تخاطب جهاز المطوّر.
 * **فهدفٌ صحيحٌ وحدَه لا يكفي**: حزمةٌ معرّفُها `…rider` وغلافُها
 * `dev-app.tajora.ly` **متّسقةُ الطرفين منفردَين ومكسورةُ الزوج** — تُثبَّت
 * مكانَ العامّة وتخاطب حاسوباً في بيت.
 *
 * **فالسؤالُ: أهذان الطرفان من قناةٍ واحدة؟** — ويُقرأ الطرفان من **داخل
 * الحزمة** لا من الشجرة: `applicationId` من بيانها، و`server.url` من
 * `capacitor.config.json` المضمَّن.
 */
const PAIRS = allPairs();

/** مفتاحُ البيان (`rider`/`driver`) → اسمُ التطبيق في الجدول. */
const APP_OF_KEY = { rider: "customer-app", driver: "driver-app", admin: "admin-panel" };

const READER =
  "import zipfile,sys,json;z=zipfile.ZipFile(sys.argv[1]);" +
  "n=[x for x in z.namelist() if x.endswith('capacitor.config.json')];" +
  "print(json.loads(z.read(n[0])).get('server',{}).get('url','') if n else '')";

/** **أيُّ مُفسِّرٍ بايثون موجودٌ هنا** — أو `null`، وهو خبرٌ لا اتّهام.
 *
 * **العلّةُ مقيسةٌ 2026-09-07**: كان يُنادى `python` وحدَه، **وليس في هذه
 * البيئة إلا `python3`** — فكانت كلُّ قراءةٍ ترتدّ فارغةً، **وتُقرأ في
 * الشقّ الثاني «زوجٌ غيرُ متّسق»**: حزمتان هدفُهما صحيحٌ حرفاً
 * (`app.tajora.ly` و`driver.tajora.ly` مقروءتان بـ`unzip -p`) **اتُّهمتا
 * بأنهما تخاطبان غيرَ هدفهما**، وسقط الحارسُ أحمرَ يوقف رفعاً.
 *
 * **وهو «حارسٌ يخترع عطباً»**، وثمنُه أغلى من واحدٍ يفوت: من رآه أحمرَ
 * مرّتين أطفأه، فسقط معه ما يمسكه حقاً.
 */
let cachedPython;
function python() {
  if (cachedPython !== undefined) return cachedPython;
  for (const candidate of ["python3", "python"]) {
    try {
      execFileSync(candidate, ["-c", "0"], { stdio: "ignore" });
      cachedPython = candidate;
      return cachedPython;
    } catch {
      /* التالي */
    }
  }
  cachedPython = null;
  return cachedPython;
}

/** يقرأ `server.url` **من داخل ملفِّ الحزمة**، لا من الشجرة.
 *
 * **ويُفرَّق «لا أداة» عن «لا هدف»**: الأولى `undefined` — **لم يُقس**،
 * والثانيةُ `null` — قُرئت الحزمةُ ولا عنوانَ فيها. **وخلطُهما هو العطبُ
 * نفسُه** الذي جعل الحارسَ يتّهم حزمةً سليمة.
 */
function shellTarget(path) {
  const runner = python();
  if (runner === null) return undefined;
  try {
    const json = execFileSync(runner, ["-c", READER, path], {
      encoding: "utf8",
    }).trim();
    return json ? new URL(json).host : null;
  } catch {
    return null;
  }
}

// ═══ ٠) **أللنطاق سجلٌّ أصلاً؟** — يُسأل قبل البيان لا بعده (2026-09-04)
//
// **وقبل البيان بقصد**: هذا الفحصُ يقرأ `channels.json` وحدَه، **فيقع حتى
// حين لا حزمةَ مبنيّة** — وغلافُ المشرف **لا يدخل البيان أصلاً** (`private`)،
// فلو وُضع تحته لَما نظر إلى النطاق الذي كُسر فعلاً.
//
// **والعطبُ الذي أنشأه**: `panel.tajora.ly` و`dev-panel.tajora.ly` بلا سجلِّ
// DNS، **والزوجُ متّسقٌ مع الجدول تماماً** — فالحارسُ كان أخضرَ والحزمةُ
// تفتح صفحةً غيرَ موجودة.
console.log(`\n  نطاقاتُ الجدول — أللاسمِ سجلّ؟`);
const deadHosts = await reportTable("  ");
if (deadHosts > 0) exit(1);

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
//: **ما لم يُقَس يُعدّ ولا يُخلط بما سقط** — ويُطبع في السطر الأخير، فلا
//: تُقرأ خضرةٌ ناقصةٌ خضرةً تامّة.
let unmeasured = 0;

// ═══ ٠-ج) **مرجعُ الحافّة هو بيانُ الحافّة** (قِيس 2026-09-11) ═══
//
// **العطبُ الذي أوجبه**: كان ما تخدمه الصفحةُ يُقارَن ببيانِ **هذا الجهاز**.
// و`landing/downloads` مُهمَلٌ في git، **فنسخةُ المطوّر تبلى وحدَها**: قِيس
// بيانٌ محلّيٌّ من `v0.2.0` (2026-08-28، رمز 392) بينما تخدم الصفحةُ
// `v0.2.4` (2026-09-10، رمز 514) — **فصاح الحارسُ «ما يُحمَّل ليس ما بُني»
// على إنتاجٍ سليم**، والصفحةُ مطابقةٌ لبيانها بايتاً (7,641,837 و7,864,877).
//
// **وأخطرُ من الحمرة الكاذبة ما تحتها**: لو تصادف تطابقُ النسختين لَأخضرَّ
// **بلا أن يقرأ بيانَ الصفحة أصلاً** — وهو «حارسٌ يُشغَّل حيث لا يملك ما
// يقيسه» بعينه، وخضرتُه صدفةٌ لا قياس.
//
// **فالسؤالان يفترقان ولا يُخلطان**: «أالصفحةُ متّسقةٌ مع نفسِها؟» مرجعُه
// **بيانُها**، و«أهذا الجهازُ هو من نشرها؟» يُجاب **بمقارنة الإيداعين**.
let edgeManifest = null;
/** أإيداعُ بيانِ الصفحة هو إيداعُ البيان المحلّيّ؟ — `null` يعني لم يُقس. */
let edgeSame = null;
if (base) {
  const manifestUrl = `${base.replace(/\/$/, "")}/downloads/manifest.json`;
  try {
    const response = await fetch(manifestUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    edgeManifest = await response.json();
    edgeSame = String(edgeManifest.commit ?? "") === String(manifest.commit ?? "");
  } catch (error) {
    console.log(
      `  · بيانُ الصفحة **لم يُقرأ** (${String(error).slice(0, 40)}) — ولا يُقرأ سكوتُه ضماناً`,
    );
  }
}

/** بصمةُ ملفٍّ كما يُصرِّح بها **بيانُ الصفحة** — لا البيانُ المحلّيّ. */
const edgeShaOf = (file) =>
  (edgeManifest?.apps ?? []).find((row) => row.file === file)?.sha256 ?? null;

// ═══ ٠-ب) **بيتُ الحزم الخاصّة — يُفحص ولا يُترك** (قرارُ المالك ٢٠٢٦-٠٩-٠٥)
//
// **العلّةُ**: هذا الفحصُ كان يمسح `landing/downloads` وحدَه، **فحزمةٌ خاصّةٌ
// في مجلَّدٍ آخر تنجو بلا فحصٍ البتّة**. ولمّا اختار المالكُ «رابطاً غيرَ
// مدرَج» صار لها مجلَّدٌ ثانٍ — **وبيتٌ لا يفحصه أحدٌ يصير ثغرةً بمرور
// الوقت**، وهو حارسٌ يُلتفّ عليه بمجلَّد.
//
// **ولكلِّ صنفٍ بيتُه**: الخاصّةُ في `private/` وحدَها، والعامّةُ في
// `downloads/` وحدَها — **ويُقاس الاتجاهان**، فلا تُرضى القاعدةُ بالنقل.
{
  const priv = join(ROOT, "landing", "private");
  const files = existsSync(priv)
    ? readdirSync(priv).filter((f) => f.endsWith(".apk"))
    : [];
  console.log(`\n  بيتُ الخاصّة \`landing/private\` — ${files.length} حزمة`);
  for (const file of files) {
    const full = join(priv, file);
    const host = shellTarget(full);
    if (!host) {
      // **«لا أداةَ» ليست «هدفٌ خاطئ»**: قراءةُ الهدف تحتاج أداةَ SDK،
      // **وغيابُها لا يُقرأ عطباً ولا سلامة**. وCI يملكها فيُقاس هناك.
      console.log(`    · ${file} — **لم يُقس** (تعذّرت قراءةُ الهدف من الحزمة)`);
      continue;
    }
    const pair = PAIRS.find((x) => new URL(x.shellUrl).host === host);
    if (!pair) {
      bad += 1;
      console.log(`    ✗ ${file}: غلافُه ${host} لا يعرفه الجدول`);
      continue;
    }
    if (!pair.private) {
      bad += 1;
      console.log(
        `    ✗ **حزمةٌ عامّةٌ في بيت الخاصّة**: ${file} (${pair.appId}) —` +
          " العامّةُ تُدرَج في `downloads` لا تُخبَّأ هنا",
      );
      continue;
    }
    if (pair.channel !== "public") {
      bad += 1;
      console.log(`    ✗ **حزمةُ قناةِ «${pair.channel}» في \`landing/private\`** — التجريبيةُ لا تُنشر`);
      continue;
    }
    console.log(`    ✓ ${file} — ${pair.appId} ← ${host} (خاصّةٌ في بيتها)`);
  }
}
for (const app of manifest.apps) {
  // ١) المبنيُّ (مصدرُ البيان)
  const local = join(ROOT, "landing", "downloads", app.file);
  const onDisk = existsSync(local)
    ? createHash("sha256").update(readFileSync(local)).digest("hex")
    : null;
  const mark = onDisk === app.sha256 ? "✓" : "✗";
  if (onDisk !== app.sha256) bad += 1;
  console.log(`  ${mark} ${app.label.padEnd(16)} البيان ${app.sha256.slice(0, 10)} · على القرص ${onDisk?.slice(0, 10) ?? "غائب"}`);

  // ١-ب) **الزوجُ من داخل الحزمة**: معرّفُها وغلافُها — أمِن قناةٍ واحدة؟
  const appName = APP_OF_KEY[app.key];
  if (!appName) {
    bad += 1;
    console.log(`    ✗ غلافٌ لا يعرفه الجدول: ${app.key} — يُصرَّح في \`channels.json\` أو يُسقط الفحص`);
  } else if (onDisk) {
    const host = shellTarget(local);
    // **ولا يُتَّهم ما لم يُقرأ** (2026-09-07): غيابُ المُفسِّر يعيد
    // `undefined`، **وهو «لم يُقس» لا «هدفٌ خاطئ»** — والفرقُ أن الأولَ
    // يُصلَح بأداةٍ تُثبَّت، والثاني يُقرأ حزمةً تخاطب خادماً غيرَ الذي
    // يظنّه من يحمّلها. **وخلطُهما أسقط رفعاً على حزمتين هدفُهما صحيح.**
    if (host === undefined) {
      unmeasured += 1;
      console.log(
        `    · ${app.file} — **لم يُقس**: لا مُفسِّرَ بايثون هنا (جُرِّب python3 ثم python)`,
      );
      continue;
    }
    // **المعرّفُ من بيان الحزمة لا من اسم الملفّ** — واسمُ الملفِّ يكتبه من يبني
    const appId = app.package ?? null;
    const match = PAIRS.find(
      (x) => x.app === appName && x.appId === appId && new URL(x.shellUrl).host === host,
    );
    if (match) {
      console.log(`    ✓ زوجٌ متّسق — قناة ${match.channel}: ${appId} ← ${host}`);
      // **٢-ب) ولا حزمةٌ خاصّةٌ على الصفحة العامّة** (قرارُ المالك 2026-09-01).
      //
      // **وهي غيرُ فحص القناة تحتَها**: غلافُ المشرف حزمةُ قناةٍ **عامّة**
      // متّسقةُ الزوج تماماً — **فالفحصُ الذي تحته يمرّ عليها أخضرَ**.
      // والذي يمنعها شرطٌ آخر: **أنها ليست لأحد**.
      //
      // **وتطبيقُ مشرفٍ على صفحة تحميلٍ عامّة ليس عطباً في شاشة**: هو بابُ
      // اللوحة يُعرض على كلِّ من يزور الصفحة — ومن نزّله عرف أنه موجودٌ
      // وأين يسكن، **وذاك نصفُ الطريق إلى محاولة الدخول**.
      if (match.private) {
        bad += 1;
        wrongTarget += 1;
        console.log(`    ✗ **حزمةٌ خاصّةٌ في \`landing/downloads\`**: ${appId} — تطبيقُ المشرف يُثبَّت باليد ولا يُنشر`);
      }
      if (match.channel !== "public") {
        // **٣) ولا حزمةَ تجريبيةٌ على الصفحة العامّة** — وهذا هو الموضع:
        // البيانُ يُبنى ممّا في `landing/downloads`، فوجودُها هنا يعني أنها
        // **تُعرض للناس**. وتثبيتُ نسخةٍ تخاطب حاسوبَ مطوّرٍ على هاتفِ راكبٍ
        // ليس عطباً في شاشة — هو رحلةٌ لا تصل.
        bad += 1;
        wrongTarget += 1;
        console.log(`    ✗ **حزمةُ قناةِ «${match.channel}» في \`landing/downloads\`** — الصفحةُ للعامّ وحدَه`);
      }
    } else {
      bad += 1;
      wrongTarget += 1;
      const known = PAIRS.filter((x) => x.app === appName)
        .map((x) => `${x.channel}: ${x.appId} ← ${new URL(x.shellUrl).host}`)
        .join("  |  ");
      console.log(`    ✗ زوجٌ غيرُ متّسق: ${appId ?? "(بلا معرّف)"} ← ${host ?? "(تعذّرت القراءة)"}`);
      console.log(`      والمعروفُ: ${known}`);
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
    const host = new URL(url).host;
    const want = edgeShaOf(app.file);
    if (want === null) {
      //: **لا مرجعَ فلا حكم** — ويُعدّ في «لم يُقس» لا في «سقط».
      unmeasured += 1;
      console.log(
        `    · ما يُحمَّل من ${host}: ${served.slice(0, 10)} — **لم يُقس**: لا بيانَ للصفحة يُقارَن به`,
      );
    } else if (served !== want) {
      //: **العطبُ الحقيقيّ**: الصفحةُ تخالف بيانَها — بايتاتٌ لا ينسبها أحد.
      bad += 1;
      console.log(
        `    ✗ ما تخدمه ${host} يخالف بيانَ الصفحة نفسِه: ${served.slice(0, 10)} ≠ ${want.slice(0, 10)}`,
      );
    } else if (edgeSame) {
      console.log(
        `    ✓ ما يُحمَّل من ${host}: ${served.slice(0, 10)} — **= بيانُ الصفحة = المبنيُّ هنا**`,
      );
    } else {
      //: **خبرٌ لا سقوط**: الصفحةُ سليمةٌ ونشرَها إيداعٌ غيرُ إيداع هذا الجهاز.
      console.log(
        `    ✓ ما يُحمَّل من ${host}: ${served.slice(0, 10)} — **= بيانُ الصفحة**، ` +
          `ونشرَها إيداعٌ غيرُ إيداعِ هذا الجهاز`,
      );
    }
  } catch (error) {
    console.log(`    · لم يُقس (${String(error).slice(0, 40)}) — **ولا يُقرأ سكوتُه ضماناً**`);
  }
}

// ═══ ٣) والعمودُ السادس مقيسٌ لا مكتوب (شرطُ المالك 2026-08-21) ═══
//
// **ثلاثةٌ تُقارَن لا اثنان**: ما تخدمه صفحةُ التنزيل = ما بناه CI = وسمُه.
// وبغير الثالث تبقى الصفحةُ متّسقةً مع نفسِها **وقد بُنيت على جهاز أحد** —
// وهو بالضبط ما نقضته البوّابةُ الرابعة حين قالت «الخادمُ يسحب نفسَ ما
// خضّره CI».
//
// **وما لا يُقاس يُعلَن**: بلا رمزٍ أو بلا وسمٍ **يقال «لم يُقس»**، ولا
// يُقرأ السكوتُ سلامة — وهي القاعدةُ الخامسة في فهرس الحرّاس.
if (base) {
  const url = `${base.replace(/\/$/, "")}/downloads/manifest.json`;
  console.log("");
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const served = await response.json();
    const commit = served.commit ? String(served.commit).slice(0, 8) : null;
    console.log(`  نسبُ ما تخدمه الصفحة: إيداع ${commit ?? "—"} · وسم ${served.tag ?? "—"}`);
    //: **ولا يُقرأ اختلافُ الإيداعين عطباً** — هذا الجهازُ ليس بالضرورة
    //: ناشرَ الصفحة، و`landing/downloads` مُهمَلٌ فيبلى وحدَه.
    if (edgeSame === false) {
      const mine = manifest.commit ? String(manifest.commit).slice(0, 8) : "—";
      console.log(
        `    · وبيانُ هذا الجهاز إيداعُه ${mine} · وسم ${manifest.tag ?? "—"} — ` +
          `**نسختان لشيءٍ واحد، والحكمُ لبيان الصفحة**`,
      );
    }
    if (served.dirty) {
      bad += 1;
      console.log("    ✗ بُنيت من **شجرةٍ متّسخة** — لا تُنسب إلى إيداعٍ بحقّ");
    }

    const token = env.GITHUB_TAXO_TOKEN;
    if (!token || !served.tag) {
      console.log(
        `    · «= ما بناه CI» **لم يُقس** (${!token ? "لا رمز" : "لا وسم"}) — ولا يُقرأ سكوتُه ضماناً`,
      );
    } else {
      const repo = env.TAXO_GITHUB_REPO ?? "SBONGEEL/taxo";
      const release = await fetch(
        `https://api.github.com/repos/${repo}/releases/tags/${served.tag}`,
        { headers: { authorization: `Bearer ${token}`, accept: "application/vnd.github+json" } },
      );
      if (!release.ok) {
        bad += 1;
        console.log(`    ✗ لا إصدارَ بالوسم ${served.tag} — فما تخدمه الصفحةُ لم يبنِه CI`);
      } else {
        const body = await release.json();
        const assets = new Map((body.assets ?? []).map((a) => [a.name, a]));
        for (const app of manifest.apps) {
          const asset = assets.get(app.file);
          if (!asset) {
            bad += 1;
            console.log(`    ✗ ${app.label}: لا أثرَ لها في إصدار ${served.tag}`);
            continue;
          }
          // **الحجمُ وكيلٌ ضعيفٌ والبصمةُ هي الحكم** — و`digest` تصل من
          // GitHub حين يوفّرها، وإلا يُقال إن المقارنةَ بالحجم وحدَه
          const digest = String(asset.digest ?? "").replace(/^sha256:/, "");
          const pageSha = served.apps?.find((a) => a.key === app.key)?.sha256;
          if (digest && pageSha) {
            const ok = digest === pageSha;
            if (!ok) bad += 1;
            console.log(`    ${ok ? "✓" : "✗"} ${app.label}: أثرُ الإصدار ${digest.slice(0, 10)}`);
          } else {
            console.log(
              `    · ${app.label}: بصمةُ الأثر غيرُ منشورة — **قِيس الحجمُ وحدَه** ` +
                `(${asset.size === app.size_bytes ? "متطابق" : "مختلف"})`,
            );
            if (asset.size !== app.size_bytes) bad += 1;
          }
        }
      }
    }
  } catch (error) {
    console.log(`  · نسبُ الصفحة **لم يُقس** (${String(error).slice(0, 40)})`);
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
    console.error("✗ ما تخدمه الصفحةُ يخالف بيانَها — وهذا لا يظهر في أيِّ فحصٍ آخر.");
    console.error("  أعد توليدَ البيان ثم انشر:  node tools/apk-manifest.mjs");
  }
  exit(1);
}
certify("check:apk", "\n✓ البصمةُ واحدةٌ في كل موضعٍ قِيس.");
