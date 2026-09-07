/** **قيمةُ سرٍّ من `.env` ظهرت في الشجرة** — تُوقف الإيداع، ولا تُطبع.
 *
 * ## العلّةُ التي يحرسها
 *
 * `.env` **محميٌّ من الشجرة ومكشوفٌ في التشغيل** (قرارُ المالك ٢٠٢٦-٠٩-٠٧):
 * يُقرأ في كلِّ بناء، وتراه كلُّ عمليةٍ في الحاوية، **ويظهر في
 * `docker inspect` وفي أثر الأخطاء**. **فالخطرُ ليس أن يُودَع — الخطّافُ
 * يمنعه ومقيسٌ — بل أن تُنسَخ قيمةٌ منه إلى ملفٍّ عاديّ**: تقريرٌ، أو سجلٌّ،
 * أو تعليقٌ في شيفرة، أو مثالٌ «للتوضيح».
 *
 * **والنسخُ لا يُمنع بقاعدة، بل يُمسك بعد وقوعه** — ولذلك حارسٌ يقرأ القيَمَ
 * الحقيقيةَ ويبحث عنها حرفاً في كلِّ ما هو **متتبَّعٌ في git**.
 *
 * ## وما يمسكه بالضبط
 *
 * **القيمةَ الحرفيةَ نفسَها**، لا شكلَها ولا طولَها. `JWT_SECRET` إن نُسخ إلى
 * `README` أو إلى تعليقٍ أو إلى `design/*.md` **يُمسَك باسمه وموضعه**.
 *
 * ## وما لا يمسكه — يُقال ولا يُقرأ سكوتُه ضماناً
 *
 * · **لا يرى صدفةً حيّةً ولا سجلَّ حاوية**: يقرأ ملفّاتِ الشجرة المتتبَّعة.
 *   **وما يُطبع في طرفيّةٍ لا يمرّ من هنا** — وذاك شرطٌ بشريٌّ يبقى بشريّاً.
 * · **ولا يمسك قيمةً مُرمَّزة**: base64 أو تجزئةٌ من القيمة تمرّ. **والحارسُ
 *   يمسك النسخَ الساذجَ وهو الذي يقع**، لا التمويهَ المقصود.
 * · **ولا يعمل بلا `.env`**: يقول «لم يُقس» ويخرج بصفر — **بيئةُ CI بلا
 *   `.env` ليست بيئةَ تسريب**، **ولا يُقرأ ذلك سلامةً** بل غيابَ قياس.
 *
 * ## وقيَمٌ لا تُحرَس — **بعلّتها، لا بالسكوت**
 *
 * قيمةٌ قصيرةٌ أو شائعةٌ (`true` · `15` · `development`) **تظهر في كلِّ ملفٍّ
 * بلا معنى** — فحارسٌ يصيح عليها يُطفأ، **ويسقط معه ما يمسكه حقاً**.
 * **فالحدُّ الأدنى ١٢ حرفاً، والقيَمُ في `SAFE` مستثناةٌ بأسمائها.**
 */

import { execSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(new URL(".", import.meta.url))).replace(/[\\/]tools$/, "");
const ENV = [join(ROOT, ".env"), join(ROOT, ".env.local")].filter(existsSync);

//: **مفاتيحُ إعدادٍ لا أسرار** — قيَمُها عامّةٌ بطبعها فلا تُحرَس.
const SAFE = new Set([
  "ENVIRONMENT",
  "TELR_USE_MOCK",
  "ACCESS_TOKEN_EXPIRE_MINUTES",
  "REFRESH_TOKEN_EXPIRE_DAYS",
  "CUSTOMER_APP_PORT",
  "POSTGRES_USER",
  "POSTGRES_DB",
  "TAXO_TUNNEL_USER",
  "TAXO_CLOUDFLARED_DIR",
  "FCM_SERVICE_ACCOUNT_PATH",
  "FCM_SERVICE_ACCOUNT_JSON_PATH",
  "DATABASE_URL",
  "REDIS_URL",
  // **اسمُ المشرف ليس سرّاً** — اسمُ إنسانٍ يُعرض على شاشةٍ ويُذكر في أمثلة
  // التوثيق بحقّ. **وحارسٌ يصيح عليه في أربعة ملفّاتِ وثائقَ يُطفأ**،
  // ويسقط معه ما يمسكه حقّاً — وهو ما وقع في أوّل تشغيلٍ لهذا الحارس.
  "BOOTSTRAP_ADMIN_NAME",
  // **ورقمُ الهاتف حسابُ تطويرٍ معروضٌ في `COMMANDS.md` بقصد** — يُدخَل بيدٍ
  // في كلِّ جولة. **والسرُّ كلمتُه لا رقمُه.**
  "BOOTSTRAP_ADMIN_PHONE",
]);

const MIN = 12;
const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");

if (ENV.length === 0) {
  console.log(`✓ check:env-leak · **لم يُقس** — لا \`.env\` في الشجرة · ${stamp}Z`);
  process.exit(0);
}

const secrets = new Map(); // اسم → قيمة
for (const f of ENV) {
  for (const line of readFileSync(f, "utf8").split("\n")) {
    const m = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!m) continue;
    const [, k, raw] = m;
    const v = raw.trim().replace(/^["']|["']$/g, "");
    if (SAFE.has(k) || v.length < MIN) continue;
    secrets.set(k, v);
  }
}

let files;
try {
  files = execSync("git ls-files", { cwd: ROOT, encoding: "utf8", maxBuffer: 64 << 20 })
    .split("\n")
    .filter(Boolean);
} catch {
  console.error("\n✗ check:env-leak · تعذّر `git ls-files` — **يُوقَف ولا يُقرأ سلامة**\n");
  process.exit(1);
}

const hits = [];
let scanned = 0;
for (const rel of files) {
  const p = join(ROOT, rel);
  let text;
  try {
    const buf = readFileSync(p);
    if (buf.includes(0)) continue; // ثنائيّ
    text = buf.toString("utf8");
  } catch {
    continue;
  }
  scanned += 1;
  for (const [k, v] of secrets) {
    const i = text.indexOf(v);
    if (i < 0) continue;
    const line = text.slice(0, i).split("\n").length;
    // **يُسمّى المفتاحُ والموضعُ — ولا تُطبع القيمة أبداً**
    hits.push(`${rel}:${line} — قيمةُ \`${k}\``);
  }
}

if (hits.length) {
  console.error(`\n✗ check:env-leak · **قيمةُ سرٍّ من \`.env\` في ملفٍّ متتبَّع** (${hits.length}):`);
  for (const h of hits) console.error(`    ${h}`);
  console.error(
    "\n  **ولا تُطبع القيمة** — يُفتح الموضعُ ويُنزع.\n" +
      "  **والنزعُ وحدَه لا يكفي**: القيمةُ صارت في تاريخ git إن أُودعت — **فتُدوَّر**.\n",
  );
  process.exit(1);
}

console.log(
  `✓ check:env-leak · لا قيمةَ سرٍّ في الشجرة — ${secrets.size} سرّاً محروساً، ` +
    `${scanned} ملفّاً مقروءاً، والحدُّ ${MIN} حرفاً · ${stamp}Z`,
);
