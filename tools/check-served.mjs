/** **البند ١: عمرُ الحزمة لا هدفُها** — «شجرةٌ خضراء» لا تقول شيئاً عن القطعة
 * التي يشغّلها إنسان.
 *
 * **وهذا أغلى درسٍ في المشروع**: كلّف **ثلاثةَ تحقيقاتٍ منفصلة**، ولم يكن أيٌّ
 * منها عطباً في الكود — ورقةُ تحويلٍ أرسلت مالاً بضغطةٍ واحدة (الإصلاحُ في
 * الشجرة والحزمةُ تسبقه)، وزرُّ عرضِ وثيقةٍ «غيرُ موجود» (اللوحةُ بُنيت بعد
 * `dist` المخدوم)، ورفعٌ «يرسل POST» (الهاتفُ يحمل أقدمَ من الاثنين).
 *
 * **و`check:dist` لا يغني عنه**: ذاك يقيس **الهدف** — أن الحزمةَ تنادي
 * `api.tajora.ly` ولا عنوانَ محلّياً فيها — وهو صحيحٌ تماماً في حزمةٍ عمرُها
 * أسبوع. **والسؤالُ هنا آخر: أهذه هي الحزمةُ التي بُنيت الآن؟**
 *
 * **وثلاثةُ أعمدةٍ لا عمودان**، وهذا مقيسٌ لا احتياط: الحاويةُ المحليةُ قد تخدم
 * حزمةً جديدةً بينما يخدم النفقُ قديمة (خدمتان مختلفتان)، والهاتفُ قد يحمل
 * أقدمَ من الاثنتين (ذاكرةُ عاملِ خدمة). فيُقارَن **المبنيّ** بما **يُخدَم
 * محلياً** وبما **يصل عبر النفق**.
 *
 * **وما لا يفعله**: لا يقيس ما على الهاتف — لا سبيلَ إليه من البناء، ويبقى
 * شرطاً بشرياً (`HANDOFF.md` §٦). **ويقول ذلك في مخرجه** كي لا يُقرأ سكوتُه
 * ضماناً: حارسٌ يوحي بأنه يغطّي ما لا يغطّيه أسوأُ من غيابه.
 *
 * **والغيابُ ليس فشلاً**: من يبني والحاوياتُ مطفأةٌ لا يُمنع — يُقال له إن
 * العمودَ لم يُقس. الفشلُ **للاختلاف** وحدَه، لأن الاختلافَ وحدَه كذبٌ صامت.
 */

import { existsSync, readFileSync } from "node:fs";
import { argv, env, exit } from "node:process";
import { certify } from "./certify.mjs";

/** **العمودُ الثالث يقيس نفقَ هذا الجهاز — `dev-*` لا الأسماءَ العارية.**
 *
 * كانت هنا `app` و`driver` و`admin` عاريةً، وكانت صحيحةً يومَ كانت تشير إلى
 * جهاز المطوّر. **وقُلبت النطاقاتُ 2026-08-26** فصارت العاريةُ تشير إلى
 * **الخادم**، و`dev-*` إلى هذا الجهاز.
 *
 * **فصار الحارسُ يقارن ما بنيتَه قبل ثوانٍ بما يخدمه الخادم** — وهما لا
 * يتساويان إلا صدفةً. وأثرُه أسوأُ من حمرةٍ كاذبة: **لو تصادف التساوي
 * لَأخضرَّ وهو لم يقس نفقَك أصلاً**، وهو «حارسٌ يُشغَّل حيث لا يملك ما يقيسه»
 * بعينه. وقِيس الفرقُ في اليوم نفسِه: `dev-app` تخدم البناءَ الجديد
 * و`app` تخدم `b6f6868` من الخادم.
 */
const APPS = {
  "admin-panel": { port: 5175, host: "dev-admin.tajora.ly" },
  "customer-app": { port: 5176, host: "dev-app.tajora.ly" },
  "driver-app": { port: 5174, host: "dev-driver.tajora.ly" },
};

const app = argv[2];
if (!app || !APPS[app]) {
  console.error(`استعمال: node tools/check-served.mjs <${Object.keys(APPS).join("|")}>`);
  exit(2);
}
// **CI تبني ولا تنشر** — فلا شيءَ تُقارَن به، والإعلانُ صريحٌ لا صامت.
if (env.CI) {
  console.log("");
  console.log(`  ${app} — عمرُ الحزمة **لم يُقس**: بيئةُ CI تبني ولا تنشر،`);
  console.log("  فالمقارنةُ تسأل عن خدمةٍ لم يصلها هذا البناء. محلُّه البوّابةُ الخامسة.");
  console.log("");
  exit(0);
}

const { port, host } = APPS[app];
const root = new URL(`../${app}/`, import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

/** بصمةُ الحزمة كما يذكرها `index.html` — لا اسمُ ملفٍّ على القرص.
 *
 * **والمرجعُ هو `index.html`** لأنه ما يقرؤه المتصفح: مجلدٌ فيه حزمتان
 * (واحدةٌ قديمةٌ لم تُمسح) يخدم التي يذكرها هذا الملف وحدَها.
 */
function stampOf(html) {
  const match = html.match(/assets\/index-[A-Za-z0-9_-]+\.js/);
  return match ? match[0] : null;
}

async function fetchStamp(url) {
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) return { error: `HTTP ${response.status}` };
    return { stamp: stampOf(await response.text()) };
  } catch (error) {
    return { error: String(error?.cause?.code ?? error?.name ?? error).slice(0, 40) };
  }
}

const distPath = `${root}dist/index.html`;
if (!existsSync(distPath)) {
  console.error("✗ لا `dist/index.html` — يُبنى قبل أن يُقاس.");
  exit(1);
}
const built = stampOf(readFileSync(distPath, "utf8"));
if (!built) {
  console.error("✗ `dist/index.html` لا يذكر حزمةً — ناتجُ بناءٍ غيرُ مكتمل.");
  exit(1);
}

const [local, tunnel] = await Promise.all([
  fetchStamp(`http://127.0.0.1:${port}/`),
  env.SKIP_TUNNEL === "1"
    ? Promise.resolve({ skipped: true })
    : fetchStamp(`https://${host}/`),
]);

// ═══ العمودُ الرابع — **أيصلح العنوانُ المخدومُ لجهازٍ غيرِ هذا الحاسوب؟**
//
// **العلّةُ مقيسةٌ ثلاثَ مرّاتٍ في يومٍ واحد** (2026-09-11/12): الحزمةُ
// التجريبيةُ تُحمَّل شاشاتُها من النفق ثمّ تنادي `127.0.0.1:8001` —
// **وهو الهاتفُ نفسُه** — فيردّ كروميوم `ERR_NETWORK_UNREACHABLE`، ويعرض
// التطبيقُ «تعذّر الوصول إلى الخدمة». **وأُصلح في `docker-compose.yml`.**
//
// **وثلاثةُ الأعمدة فوق لا تمسكه**: هي تسأل «أالمخدومُ هو المبنيّ؟»
// **وتُجيب بنعم وهي صادقة** — الحزمةُ المخدومةُ هي بعينها المبنيّة،
// **وعنوانُها لا يصل هاتفاً**. فالسؤالُ الرابعُ مختلفٌ في نوعه لا في درجته.
//
// **ولا يُسأل إلا عمّا يصل هاتفاً**: من يخدم على `127.0.0.1` لمتصفّحِ هذا
// الحاسوب **صائبٌ تماماً** — والحكمُ يقع حين **يُخدَم النفقُ** وهو الطريقُ
// الذي لا يسلكه إلا جهازٌ آخر.
const LOOPBACK = /^https?:\/\/(127\.0\.0\.1|localhost|\[?::1\]?)(:|\/|$)/i;

/** عنوانُ الـAPI كما **يُخدَم** — من الحزمة المخدومة لا من الشجرة. */
async function servedApiBase(url) {
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) return { error: `HTTP ${response.status}` };
    const html = await response.text();
    // **مسارُ التطوير ومسارُ البناء كلاهما**: `vite dev` يخدم `src/main.tsx`
    // و`preview` يخدم `assets/index-*.js` — **والعنوانُ مخبوزٌ في الثاني
    // ومحقونٌ في الأول**، فيُقرأ من الوحدة التي تحمله في الحالين.
    const asset = html.match(/\/(assets\/index-[A-Za-z0-9_-]+\.js|src\/main\.tsx)/);
    if (!asset) return { error: "لا وحدةَ في index.html" };
    const mod = await fetch(new URL(asset[0], url), {
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    if (!mod.ok) return { error: `HTTP ${mod.status}` };
    const text = await mod.text();
    const hit = text.match(/https?:\/\/[A-Za-z0-9.:_-]+(?=["'`])/g) ?? [];
    const api = hit.find((u) => LOOPBACK.test(u)) ?? hit.find((u) => /api/i.test(u));
    return { api: api ?? null };
  } catch (error) {
    return { error: String(error?.cause?.code ?? error?.name ?? error).slice(0, 40) };
  }
}

const reach =
  env.SKIP_TUNNEL === "1" || tunnel.error
    ? { skipped: true }
    : await servedApiBase(`https://${host}/`);

const rows = [
  ["المبنيُّ في dist", built],
  [`ما يخدمه 127.0.0.1:${port}`, local.stamp ?? null, local.error, local.skipped],
  [`ما يصل عبر ${host}`, tunnel.stamp ?? null, tunnel.error, tunnel.skipped],
];

console.log(`\n  ${app} — عمرُ الحزمة في ثلاثة أعمدة`);
for (const [label, stamp, error, skipped] of rows) {
  const shown = stamp ?? (skipped ? "— لم يُقس (SKIP_TUNNEL)" : `— لم يُقس (${error})`);
  const mark = stamp === null ? "·" : stamp === built ? "✓" : "✗";
  console.log(`  ${mark} ${label.padEnd(30)} ${shown}`);
}

const mismatched = rows
  .slice(1)
  .filter(([, stamp]) => stamp !== null && stamp !== built);

if (mismatched.length > 0) {
  console.error(
    [
      "",
      "✗ ما يُخدَم ليس ما بُني — وهذا لا يظهر في أيِّ فحصٍ آخر.",
      ...mismatched.map(([label, stamp]) => `  ${label}: ${stamp}`),
      `  المبنيُّ الآن:      ${built}`,
      "",
      "  أعد تشغيل ما يخدمها:",
      "    docker compose --env-file .env.local \\",
      "      -f docker-compose.yml -f docker-compose.tunnel.yml restart " + app,
    ].join("\n"),
  );
  exit(1);
}

// **العمودُ الرابعُ يُطبع ويحكم** — ولا يُقرأ سكوتُه ضماناً.
if (reach.skipped) {
  console.log(`  · ${"أيصلح للهاتف؟".padEnd(30)} — لم يُقس (النفقُ لم يُقرأ)`);
} else if (reach.error) {
  console.log(`  · ${"أيصلح للهاتف؟".padEnd(30)} — لم يُقس (${reach.error})`);
} else if (reach.api && LOOPBACK.test(reach.api)) {
  console.error(`  ✗ ${"أيصلح للهاتف؟".padEnd(30)} ${reach.api}`);
  console.error(
    [
      "",
      "✗ العنوانُ المخدومُ عبر النفق **عنوانُ هذا الحاسوب** — ولا يصل هاتفاً.",
      "  الهاتفُ يقرأ `127.0.0.1` نفسَه، فيردّ `ERR_NETWORK_UNREACHABLE`",
      "  ويعرض التطبيقُ «تعذّر الوصول إلى الخدمة».",
      "",
      "  والإصلاحُ في `docker-compose.yml`:",
      "    VITE_API_BASE_URL: ${TAXO_DEV_API_BASE:-https://dev-api.tajora.ly}",
    ].join("\n"),
  );
  exit(1);
} else {
  console.log(`  ✓ ${"أيصلح للهاتف؟".padEnd(30)} ${reach.api ?? "لا عنوانَ محلّيٌّ فيه"}`);
}

const unmeasured = rows.slice(1).filter(([, stamp]) => stamp === null);
if (unmeasured.length > 0) {
  console.log(
    "\n  ⚠ عمودٌ لم يُقس — ولا يُقرأ سكوتُه ضماناً. وما على الهاتف لا يقيسه هذا\n" +
      "    الحارسُ أصلاً: يبقى شرطاً بشرياً (`HANDOFF.md` §٦).",
  );
} else {
  certify("check:served", 
    "\n✓ الثلاثةُ متطابقة. **وما على الهاتف خارج هذا القياس** — يبقى شرطاً بشرياً.",
  );
}
