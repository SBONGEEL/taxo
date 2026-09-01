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
import { existsSync, readFileSync } from "node:fs";
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

  // ١-ب) **الزوجُ من داخل الحزمة**: معرّفُها وغلافُها — أمِن قناةٍ واحدة؟
  const appName = APP_OF_KEY[app.key];
  if (!appName) {
    bad += 1;
    console.log(`    ✗ غلافٌ لا يعرفه الجدول: ${app.key} — يُصرَّح في \`channels.json\` أو يُسقط الفحص`);
  } else if (onDisk) {
    const host = shellTarget(local);
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
    const ok = served === app.sha256;
    if (!ok) bad += 1;
    console.log(`    ${ok ? "✓" : "✗"} ما يُحمَّل من ${new URL(url).host}: ${served.slice(0, 10)}`);
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
    console.error("✗ ما يُحمَّل ليس ما بُني — وهذا لا يظهر في أيِّ فحصٍ آخر.");
    console.error("  أعد توليدَ البيان ثم انشر:  node tools/apk-manifest.mjs");
  }
  exit(1);
}
certify("check:apk", "\n✓ البصمةُ واحدةٌ في كل موضعٍ قِيس.");
