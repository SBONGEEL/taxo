/** حارسُ صفحة `taxo.tajora.ly` — **يمنع ما وقع فعلاً، لا ما يُخشى**.
 *
 * خمسةُ أسئلةٍ يجيبها بالقياس على المصدر:
 *
 * ١. **أبقي قالبٌ من مُشغِّل التصميم؟** — `{{ }}` أو `<sc-*>` تصل الزائرَ
 *    نصّاً حرفيّاً. **ووقع**: التحويلُ الأوّل ترك أربعين قالباً.
 * ٢. **أذُكر بلدٌ غير الأردن؟** — شرطُ المالك ٢. **والصفحةُ القائمةُ كانت تقول
 *    «في الأردن وليبيا»**، فهذا يمنع العودة.
 * ٣. **أخرج رقمُ سعر؟** — شرطُ المالك ٣. **ولا يكفي أن الباب لا يُخرجه**:
 *    من كتبه في HTML نشره.
 * ٤. **أكلُّ مفتاحٍ يقرؤه `site.js` موجودٌ في الصفحة؟** — ومقيسٌ في الاتجاهين:
 *    مفتاحٌ يُقرأ ولا يوجد **يترك قيمةً لا تُحدَّث**، وموضعٌ في الصفحة لا يقرؤه
 *    أحدٌ **يبقى مخبوزاً إلى الأبد**. **وهو «بابٌ بلا زرّ» بوجهيه.**
 * ٥. **أتُقرأ القوائمُ الخمسُ بلا JavaScript؟** — بُنيت في HTML وقتَ البناء،
 *    **وحارسٌ يمنع أن تعود إلى الرسم في المتصفّح**.
 *
 * **وصفحةُ التحميل `/download`** (SPEC §٦٨-ج/٦، أُضيفت ٢٠٢٦-١٠-٠٩) تُحرس بالطريقة
 * نفسِها وأبعد — من ٦ إلى ١٢ أدناه: خاناتُها في الاتجاهين، ورابطُها المخبوزُ هو
 * الملفُّ الذي يُنشر فعلاً، وما تقرؤه موجودٌ في بابه، ورموزُها رموزُ العائلة،
 * وخطوطُها لها مصدر، **والرئيسيةُ تقود إليها ولا تحمل نسخةً ثانية**، **وكلُّ
 * صفحةٍ تحمّل فعلاً ما يحكم عليه هذا الحارسُ باسمها**.
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { FONTS } from "./fonts.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const SITE = join(HERE, "..");
const ROOT = join(SITE, "..");
const html = readFileSync(join(SITE, "index.html"), "utf8");
const js = readFileSync(join(SITE, "src", "site.js"), "utf8");
const dlHtml = readFileSync(join(SITE, "download.html"), "utf8");
const dlJs = readFileSync(join(SITE, "src", "download.js"), "utf8");
const dlCss = readFileSync(join(SITE, "src", "download.css"), "utf8");
//: **ما يحكم عليه الحارسُ لكلِّ صفحة** — الملفّاتُ الثلاثةُ المقروءةُ أعلاه
//: نفسُها، **ويُطابَق بوسوم الصفحة في ١٢**: حارسٌ يقرأ ملفّاً كفّت صفحتُه عن
//: تحميله **يشهد لما لا يُخدَم**.
const OWN = {
  "index.html": { scripts: ["site.js"], sheets: [] },
  "download.html": { scripts: ["download.js"], sheets: ["download.css"] },
};
//: **كلُّ صفحةٍ في الجذر** — لا قائمةٌ تُكتب هنا فتنسى صفحةً تُضاف غداً
const PAGES = readdirSync(SITE).filter((f) => f.endsWith(".html")).sort();

const bad = [];

/** الشيفرةُ بلا تعليقاتها — **شرحُ القاعدة ليس خرقاً لها**.
 *
 * **و`//` يُعدّ تعليقاً حين يسبقه فراغٌ أو بدايةُ سطر**: `https://` في نصٍّ
 * يسبقه `:` فيبقى، و`\/\/` في تعبيرٍ نمطيٍّ يسبقه `\` فيبقى. */
const code = (src) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|\s)\/\/.*$/gm, "$1");
/** ما يراه الإنسانُ من الصفحة — بلا تعليقٍ ولا نمطٍ ولا سكربتٍ ولا وسم. */
const visible = (src) =>
  src
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<(style|script)\b[\s\S]*?<\/\1>/g, " ")
    .replace(/<[^>]*>/g, " ");

/* ٠ — قيمُ `doc_type` تُقرأ من التعداد لا تُكتب باليد
 *
 * **وقع مقيساً على الإنتاج ٢٠٢٦-٠٩-٠٥**: `terms.html` كان يرسل
 * `terms_of_service` **والتعدادُ `terms_of_use`** — فالباب يردّ ٤٢٢،
 * **و`catch` في الصفحة يبتلعه صامتاً**، فتبقى الصفحةُ تقول «لم تُنشر بعد»
 * **والوثيقةُ منشورة**.
 *
 * **وما ستره أن الميزةَ كانت مطفأة**: `policies_public=false` يجعل الصفحتين
 * تقولان الشيءَ نفسَه، **فالخاطئةُ تبدو كالصحيحة** — ولم يظهر الفرقُ إلا
 * لحظةَ الإشعال. **وعطبٌ يستتر خلف مفتاحٍ مطفأ يعيش حتى يُشعَل.**
 *
 * **والمرجعُ `models/enums.py` نفسُه** — لا قائمةٌ ثانيةٌ تُكتب هنا وتفترق. */
{
  const enums = readFileSync(join(SITE, "..", "backend", "app", "models", "enums.py"), "utf8");
  const block = enums.slice(enums.indexOf("class PolicyDocType"), enums.indexOf("class PolicyApp"));
  const allowed = new Set([...block.matchAll(/=\s*"([a-z_]+)"/g)].map((m) => m[1]));
  if (allowed.size === 0) bad.push("تعذّر قراءةُ `PolicyDocType` من الخلفية — **لا يُقاس بالظنّ**");

  for (const file of ["privacy.html", "terms.html"]) {
    const page = readFileSync(join(SITE, file), "utf8");
    for (const m of page.matchAll(/data-doc="([^"]*)"/g)) {
      if (!allowed.has(m[1])) {
        bad.push(`${file}: data-doc="${m[1]}" ليست في PolicyDocType (${[...allowed].join(" · ")})`);
      }
    }
  }
}


/* ١ — قوالبُ المُشغِّل — **في كلِّ صفحةٍ لا في الرئيسية وحدَها** */
//
// **وقوسٌ مفردٌ قالبٌ أيضاً** (قِيس ٢٠٢٦-١٠-٠٩): قسمُ التحميل كان يحمل
// `{version}` و`{build}` و`{date}` و`{size}` نصّاً مخبوزاً **يراه كلُّ من لم
// يصله البيان** — وهذا السؤالُ كان يبحث عن `{{` وحدَه فمرّت أربعتُها.
// **ويُقرأ النصُّ المرئيُّ وحدَه**: `{display:…}` في ورقة نمطٍ ليس قالباً.
for (const file of PAGES) {
  const src = file === "index.html" ? html : readFileSync(join(SITE, file), "utf8");
  const templates = src.match(/\{\{[^}]*\}\}/g) ?? [];
  const scTags = src.match(/<sc-[a-z]+/g) ?? [];
  const singles = visible(src).match(/\{[A-Za-z_][A-Za-z0-9_]*\}/g) ?? [];
  if (templates.length) bad.push(`${file}: قوالبُ مُشغِّلٍ لم تُفكّ: ${templates.slice(0, 3).join(" · ")}`);
  if (scTags.length) bad.push(`${file}: وسومُ مُشغِّلٍ باقية: ${[...new Set(scTags)].join(" · ")}`);
  if (singles.length) bad.push(`${file}: قوسُ قالبٍ يصل الزائرَ حرفيّاً: ${[...new Set(singles)].join(" · ")}`);
}

/* ٢ — بلدٌ غير الأردن */
//
// **والنصُّ وحدَه يُفحص لا السماتُ**: `dir="ltr"` ليست بلداً، واسمُ ملفٍّ ليس
// جملةً. فتُنزع الوسومُ ثم يُقرأ ما يراه الإنسان.
// **وصفحةُ التحميل معها** — صفحةٌ عامّةٌ ثانيةٌ بالشرطين نفسَيهما.
const text = html.replace(/<[^>]*>/g, " ") + " " + visible(dlHtml);
for (const country of ["ليبيا", "طرابلس", "بنغازي", "Libya", "سوريا", "مصر", "السعودية"]) {
  if (text.includes(country)) bad.push(`بلدٌ غير الأردن في نصِّ الصفحة: «${country}»`);
}

/* ٣ — أرقامُ أسعار */
for (const token of ["د.أ", "د.ل", "JOD", "LYD", "دينار"]) {
  if (text.includes(token)) bad.push(`رمزُ عملةٍ في الصفحة: «${token}»`);
}

/* ٤ — المفاتيحُ في الاتجاهين */
const readKeys = new Set(
  // **والرقمُ من الاسم**: `[a-z_]+` يبتر `driver_keeps_per_100` إلى
  // `driver_keeps_per_` **ثمّ يشكو أن لا موضعَ له** — بلاغٌ كاذبٌ سببه
  // النمطُ لا الصفحة. **وحارسٌ يبتر ما يقرأ يتّهم السليم.**
  [...js.matchAll(/data-(?:site|section|social)=["'`]?\$?\{?([a-z0-9_]+)/g)].map((m) => m[1]),
);
const pageKeys = new Set(
  // **والرقمُ من الاسم هنا أيضاً** — الطرفان يُقرآن بنمطٍ واحد، وإلا
  // قرأ أحدُهما مفتاحاً كاملاً والآخرُ مبتوراً **فاختلفا على السليم**.
  [...html.matchAll(/data-(?:site|section|social)="([a-z0-9_]+)"/g)].map((m) => m[1]),
);
// **ما يقرؤه السكربتُ بقائمةٍ ثابتة** — تُقرأ من مصفوفته لا تُخمَّن
for (const m of js.matchAll(/for \(const net of \[([^\]]+)\]\)/g)) {
  for (const net of m[1].match(/"([a-z]+)"/g) ?? []) readKeys.add(net.replaceAll('"', ""));
}
// **و`net` اسمُ متغيّرِ القالب لا مفتاحاً** — بلاغٌ كاذبٌ وقع في أوّل
// تشغيل، **ويُستثنى بالاسم لا بتوسيع النمط**: تخفيفُ النمط يُسقط مفاتيحَ
// حقيقيةً معه. والمفاتيحُ التي تُبنى بالتركيب تُفحص في حلقة `social` أدناه.
const TEMPLATE_VARS = new Set(["net"]);
const missing = [...readKeys].filter(
  (k) => !pageKeys.has(k) && !/^social_/.test(k) && !TEMPLATE_VARS.has(k),
);
if (missing.length) bad.push(`مفاتيحُ يقرؤها site.js ولا موضعَ لها: ${missing.join(" · ")}`);

/* ٥ — القوائمُ الخمسُ مبنيّةٌ في HTML */
const lists = {
  "بطاقات الراكب": /طلب رحلة على الخريطة/,
  "بطاقات الكبتن": /عمولة 0% بالاشتراك|اشتراك يومي/,
  "الأمان": /مراجعة المستندات قبل الاعتماد/,
  "قريباً": /توصيل الطلبات والطرود/,
  "الأسئلة": /هل التطبيق مجاني للراكب؟/,
};
for (const [name, re] of Object.entries(lists)) {
  if (!re.test(html)) bad.push(`قائمةٌ ليست في HTML (تسقط بلا JavaScript): ${name}`);
}

/* ٦ — كلُّ صفحةٍ في الجذر تدخل البناء
 *
 * **صفحةٌ لا تدخل `rollupOptions.input` لا تُبنى**، فرابطُها يقود إلى ٤٠٤ —
 * وتعليقُ `vite.config.js` يقول ذلك منذ صفحة الحذف. **وهنا يُطبَّق.** */
{
  const config = readFileSync(join(SITE, "vite.config.js"), "utf8");
  const inputs = new Set([...config.matchAll(/resolve\(__dirname,\s*"([a-z0-9-]+\.html)"\)/g)].map((m) => m[1]));
  for (const file of PAGES) {
    if (!inputs.has(file)) bad.push(`${file} في الجذر وليست في مدخلات vite.config.js — **لا تُبنى، ورابطُها ٤٠٤**`);
  }
}

/* ٧ — صفحةُ التحميل: خاناتُها في الاتجاهين، ورابطُها المخبوزُ هو الملفُّ المنشور
 *
 * **وجهٌ أوّل**: كلُّ `data-*` في الصفحة يقرؤه `download.js`، وكلُّ ما يقرؤه
 * موجودٌ فيها — خانةٌ لا يملؤها أحدٌ تبقى «—» إلى الأبد، ومفتاحٌ بلا خانةٍ
 * يُحسب ولا يُرى. **وجهٌ ثانٍ**: `FIELDS` في كلِّ بطاقةٍ مرّةً، **ومخبوزُها
 * «—» لا قوسٌ ولا رقم** (ما لم يُقرأ لا يُدّعى). **وجهٌ ثالث**: الرابطُ
 * المخبوزُ — وهو كلُّ ما يملكه من أطفأ JavaScript — **اسمُ الملفّ الذي يكتبه
 * `tools/apk-manifest.mjs` لذلك التطبيق حرفاً**، فلا يقود إلى ٤٠٤ إن تغيّر الاسمُ
 * هناك. */
const dlCode = code(dlJs);
const apkTool = readFileSync(join(ROOT, "tools", "apk-manifest.mjs"), "utf8");
{
  const pageAttrs = new Set([...dlHtml.matchAll(/\sdata-([a-z][a-z0-9-]*)/g)].map((m) => m[1]));
  const jsAttrs = new Set([
    ...[...dlCode.matchAll(/data-([a-z][a-z0-9-]*)/g)].map((m) => m[1]),
    // `card.dataset.app` يقرأ `data-app` — **والاسمُ يُحوَّل لا يُخمَّن**
    ...[...dlCode.matchAll(/dataset\.([a-zA-Z]+)/g)].map((m) =>
      m[1].replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`),
    ),
  ]);
  const deadSlots = [...pageAttrs].filter((a) => !jsAttrs.has(a));
  const ghostKeys = [...jsAttrs].filter((a) => !pageAttrs.has(a));
  if (deadSlots.length) bad.push(`download.html: خاناتٌ لا يقرؤها download.js: ${deadSlots.map((a) => `data-${a}`).join(" · ")}`);
  if (ghostKeys.length) bad.push(`download.js يقرأ ما لا موضعَ له في الصفحة: ${ghostKeys.map((a) => `data-${a}`).join(" · ")}`);

  const fields = (/const FIELDS = \[([^\]]+)\]/.exec(dlCode)?.[1].match(/"([a-z0-9_]+)"/g) ?? [])
    .map((s) => s.replaceAll('"', ""));
  const names = new Set([...(/const NAMES = \{([^}]*)\}/.exec(dlCode)?.[1] ?? "").matchAll(/([a-z]+)\s*:/g)].map((m) => m[1]));
  // **أسماءُ الملفّات من مصدرها** — `APPS` في أداة البيان، لا قائمةٌ ثانيةٌ هنا
  const published = new Map(
    [...apkTool.matchAll(/key:\s*"([a-z]+)"[^}]*?name:\s*"([^"]+)"/g)].map((m) => [m[1], m[2]]),
  );
  if (fields.length === 0) bad.push("تعذّر قراءةُ `FIELDS` من download.js — **لا يُقاس بالظنّ**");
  if (published.size === 0) bad.push("تعذّر قراءةُ `APPS` من tools/apk-manifest.mjs — **لا يُقاس بالظنّ**");

  const cards = [...dlHtml.matchAll(/<article\b[^>]*\bdata-app="([a-z]+)"[^>]*>([\s\S]*?)<\/article>/g)];
  if (cards.length === 0) bad.push("download.html بلا بطاقة `data-app` — **صفحةُ تحميلٍ بلا تطبيق**");
  for (const [, key, body] of cards) {
    if (!published.has(key)) bad.push(`download.html: بطاقةُ «${key}» لا تطبيقَ لها في APPS (tools/apk-manifest.mjs)`);
    if (!names.has(key)) bad.push(`download.html: بطاقةُ «${key}» بلا اسمٍ في NAMES (download.js)`);
    const get = /<a\b[^>]*\bdata-get\b[^>]*>/.exec(body)?.[0] ?? "";
    const href = /\shref="([^"]+)"/.exec(get)?.[1];
    const want = published.has(key) ? `/downloads/${published.get(key)}` : null;
    if (!get) bad.push(`download.html: بطاقةُ «${key}» بلا زرّ \`data-get\``);
    else if (want && href !== want) {
      bad.push(`download.html: رابطُ «${key}» المخبوز ${href ?? "—"} والملفُّ المنشور ${want} — **من أطفأ JavaScript يصل إلى ٤٠٤**`);
    }
    for (const field of fields) {
      const slots = [...body.matchAll(new RegExp(`data-field="${field}"[^>]*>([^<]*)<`, "g"))];
      if (slots.length !== 1) bad.push(`download.html: «${key}» فيها ${slots.length} خانةً لـ${field} — والمطلوبُ واحدة`);
      for (const [, baked] of slots) {
        if (baked.trim() !== "—") bad.push(`download.html: «${key}/${field}» مخبوزةٌ «${baked.trim()}» — **وما لم يُقرأ يُكتب «—»**`);
      }
    }
    for (const [, field] of body.matchAll(/data-field="([a-z0-9_]+)"/g)) {
      if (!fields.includes(field)) bad.push(`download.html: خانةُ ${field} في «${key}» ليست في FIELDS — لا تُملأ أبداً`);
    }
  }
}

/* ٨ — بابٌ واحد: الرئيسيةُ تقود إلى `/download` ولا تحمل نسخةً ثانية
 *
 * **وقع مقيساً قبل هذه الصفحة**: القسمُ في الرئيسية كان يقرأ البيانَ ويعرض
 * ثمانيةَ أحرفٍ من البصمة تحت «البناء» — **نسخةٌ ثانيةٌ من الحقيقة نفسِها**،
 * تفترق عن الأولى أوّلَ تعديلٍ في إحداهما. */
{
  if (!/href="\/download(?:#[a-z-]+)?"/.test(html)) bad.push("index.html لا يقود إلى /download — **صفحةُ تحميلٍ لا بابَ إليها**");
  if (/href="\/downloads\//.test(html)) bad.push("index.html يربط ملفّاً في /downloads/ مباشرةً — **البابُ واحدٌ: /download**");
  if (/data-dl-(?:meta|value)/.test(html)) bad.push("index.html يحمل خاناتِ البيان (`data-dl-meta`) — **نسخةٌ ثانيةٌ من الإصدار والبصمة**");
  if (/manifest\.json|\/downloads\//.test(code(js))) bad.push("site.js يقرأ بيانَ الحزم — **تقرؤه صفحةُ التحميل وحدَها**");
}

/* ٩ — ما تقرؤه الصفحتان موجودٌ في بابه
 *
 * **مفتاحٌ يُقرأ من بابٍ لا يُخرجه يبقى `undefined` صامتاً** — فتُرسم القيمةُ
 * المخبوزةُ إلى الأبد ولا يشكو شيء. فيُطابَق:
 *   · `site.<مفتاح>` في السكربتين بقائمة السماح `PUBLIC_FIELDS` في الخلفية
 *     (وما يضيفه `public_payload` بعدها: `payload["…"]`)؛
 *   · و`app.<حقل>` و`manifest.<حقل>` في `download.js` بما يكتبه `apk-manifest.mjs`. */
{
  const sitePy = readFileSync(join(ROOT, "backend", "app", "services", "site.py"), "utf8");
  const door = new Set(
    [...(/^PUBLIC_FIELDS\b[^=\n]*=\s*\(([\s\S]*?)^\)/m.exec(sitePy)?.[1] ?? "").matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]),
  );
  for (const m of sitePy.matchAll(/payload\["([a-z0-9_]+)"\]\s*=/g)) door.add(m[1]);
  if (door.size === 0) bad.push("تعذّر قراءةُ `PUBLIC_FIELDS` من backend/app/services/site.py — **لا يُقاس بالظنّ**");
  for (const [file, src] of [["site.js", js], ["download.js", dlJs]]) {
    // **والاسمُ كاملاً بحروفه الكبيرة** — `[a-z]` وحدَها تبتر `versionCode` إلى
    // `version` فيُسمّى في البلاغ مفتاحٌ لم يُكتب (قِيس بالنقض ٢٠٢٦-١٠-٠٩)
    for (const [, key] of code(src).matchAll(/(?<![\w.$-])site\??\.([A-Za-z0-9_]+)/g)) {
      if (door.size && !door.has(key)) bad.push(`${file} يقرأ site.${key} — **والبابُ العامُّ لا يُخرجه** (PUBLIC_FIELDS)`);
    }
  }

  const tool = code(apkTool);
  const writes = (key) => new RegExp(`(?:\\b${key}\\s*:|[{,]\\s*${key}\\s*[,}])`).test(tool);
  const reads = new Set([
    ...[...dlCode.matchAll(/(?<![\w.$])app\??\.([A-Za-z0-9_]+)/g)].map((m) => m[1]),
    ...[...dlCode.matchAll(/(?<![\w.$/-])manifest\??\.([A-Za-z0-9_]+)/g)].map((m) => m[1]),
  ]);
  for (const key of reads) {
    if (!writes(key)) bad.push(`download.js يقرأ «${key}» من البيان — **و apk-manifest.mjs لا يكتبه**`);
  }
}

/* ١٠ — رموزُ صفحة التحميل هي رموزُ العائلة، بقيمها وفي المظهرين
 *
 * **الموقعُ لا يستورد من تطبيق** (كلُّ شجرةٍ تُبنى وحدَها)، فالرموزُ تُنقل —
 * **والمنقولُ يبلى حين تُعدَّل العائلةُ تحته**. فيُطابَق كلُّ `--t2-*` في
 * `download.css` بقيمته في `customer-app/src/taxo2/tokens.css`:
 *   · الفاتحُ بكتلة `.t2`، والداكنُ بكتلة `html.dark .t2…`؛
 *   · **وقيمةٌ داكنةٌ لم ترسمها العائلةُ مخترعة**؛
 *   · **ورمزٌ تعيده العائلةُ في الداكن ولا يُعاد هنا يُرسم فاتحاً على الإسفلت**؛
 *   · **ولا لونَ خارج الرموز — سداسيّاً ولا دالّةً** (`rgb()` · `rgba()` · `hsl()`…)،
 *     ولا `var()` لرمزٍ لم يُعرَّف.
 *
 * **والدالّةُ أُضيفت بعد أن مرّ منها اثنان** (قِيس ٢٠٢٦-١٠-٠٩): ظلّا البطاقة
 * كانا `rgba(20, 22, 26, …)` خارج الرموز، **والسؤالُ يبحث عن `#` وحدَه** —
 * فلونٌ بلا رمزٍ مرّ لأنه كُتب بصيغةٍ ثانية. */
{
  const stripCss = (src) => src.replace(/\/\*[\s\S]*?\*\//g, "");
  const tokens = (block) =>
    new Map([...(block ?? "").matchAll(/--(t2-[a-z0-9-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2]]));
  const norm = (v) => String(v).trim().replace(/\s+/g, " ").toLowerCase();

  const family = stripCss(readFileSync(join(ROOT, "customer-app", "src", "taxo2", "tokens.css"), "utf8"));
  const famLight = tokens(/(?:^|\n)\.t2\s*\{([^}]*)\}/.exec(family)?.[1]);
  const famDark = tokens(/html\.dark \.t2:not\(\.t2-day\),\s*\.t2\.t2-night\s*\{([^}]*)\}/.exec(family)?.[1]);
  if (famLight.size === 0 || famDark.size === 0) {
    bad.push("تعذّر قراءةُ رموز العائلة من customer-app/src/taxo2/tokens.css — **لا يُقاس بالظنّ**");
  }

  const css = stripCss(dlCss);
  const LIGHT = /(?:^|\n):root\s*\{([^}]*)\}/;
  const DARK = /@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([^}]*)\}\s*\}/;
  const light = tokens(LIGHT.exec(css)?.[1]);
  const dark = tokens(DARK.exec(css)?.[1]);
  if (light.size === 0) bad.push("download.css بلا رموزٍ في `:root` — **لا يُقاس بالظنّ**");
  if (dark.size === 0) bad.push("download.css بلا مظهرٍ داكن (`prefers-color-scheme: dark`)");

  if (famLight.size && famDark.size) {
    for (const [k, v] of light) {
      if (!famLight.has(k)) bad.push(`download.css: --${k} ليس رمزاً في العائلة`);
      else if (norm(v) !== norm(famLight.get(k))) bad.push(`download.css: --${k} = ${v.trim()} — وفي العائلة ${famLight.get(k).trim()}`);
    }
    for (const [k, v] of dark) {
      if (!famDark.has(k)) bad.push(`download.css: --${k} داكنٌ لم ترسمه العائلة — قيمةٌ مخترعة`);
      else if (norm(v) !== norm(famDark.get(k))) bad.push(`download.css: --${k} داكناً = ${v.trim()} — وفي العائلة ${famDark.get(k).trim()}`);
    }
    for (const k of light.keys()) {
      if (famDark.has(k) && !dark.has(k)) bad.push(`download.css: --${k} تعيده العائلةُ في الداكن ولا يُعاد هنا — **يُرسم فاتحاً على الإسفلت**`);
    }
  }

  const used = new Set([...css.matchAll(/var\(--(t2-[a-z0-9-]+)/g)].map((m) => m[1]));
  const undefinedTokens = [...used].filter((k) => !light.has(k));
  if (undefinedTokens.length) bad.push(`download.css يستعمل رموزاً لم تُعرَّف: ${undefinedTokens.map((k) => `--${k}`).join(" · ")}`);
  const outside = css.replace(DARK, "").replace(LIGHT, "");
  const raw = outside.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [];
  if (raw.length) bad.push(`download.css: لونٌ خارج الرموز: ${[...new Set(raw)].join(" · ")}`);
  // **والدالّةُ بحرفها لا باسم الخاصّية**: `color-mix(in srgb, var(--t2-…) …)`
  // لونٌ من رمز، و`srgb` فيه ليس `rgb(` — فالاسمُ يُقرأ بلا حرفٍ قبله وقوسُه بعده.
  const fnColors = outside.match(/(?<![\w-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\([^)]*\)/gi) ?? [];
  if (fnColors.length) bad.push(`download.css: لونٌ بدالّةٍ خارج الرموز: ${[...new Set(fnColors)].join(" · ")}`);
}

/* ١١ — الخطوطُ والأرقام
 *
 * **خطٌّ تطلبه صفحةٌ ولا يُولَّد** طلبٌ يردّ ٤٠٤ في كلِّ فتحة، **والصفحةُ
 * تُرسم بخطٍّ احتياطيٍّ فلا يشكو شيء**. فكلُّ `/fonts/<الاسم>.woff2` في صفحةٍ
 * أو ورقةِ نمطٍ في `FONTS` (`scripts/fonts.mjs`) **ولمصدره ملفٌّ في
 * `assets-src/fonts/`** — وكلُّ ما في `FONTS` تطلبه صفحة.
 *
 * **والأرقامُ لاتينيةٌ في النصّ المرئيّ والسكربتين** (قاعدةُ المشروع)، **وكلُّ
 * تنسيقٍ بلغةٍ يحمل `nu-latn`**: متصفّحٌ عربيُّ اللغة يكتب بالهندية بغيره. */
{
  const srcDir = join(SITE, "src");
  const sheets = readdirSync(srcDir).filter((f) => f.endsWith(".css"));
  const wanted = new Set();
  for (const file of PAGES) {
    for (const m of readFileSync(join(SITE, file), "utf8").matchAll(/\/fonts\/([A-Za-z0-9-]+)\.woff2/g)) wanted.add(m[1]);
  }
  for (const file of sheets) {
    for (const m of readFileSync(join(srcDir, file), "utf8").matchAll(/\/fonts\/([A-Za-z0-9-]+)\.woff2/g)) wanted.add(m[1]);
  }
  const fontSrc = join(SITE, "assets-src", "fonts");
  for (const name of wanted) {
    if (!FONTS.includes(name)) {
      bad.push(`خطٌّ تطلبه صفحةٌ وليس في FONTS (scripts/fonts.mjs): ${name}`);
    } else if (!existsSync(join(fontSrc, `${name}.ttf`)) && !existsSync(join(fontSrc, `${name}.woff2`))) {
      bad.push(`خطٌّ بلا مصدر: site/assets-src/fonts/${name}.ttf (أو .woff2) — **يُطلب ولا يُولَّد**`);
    }
  }
  for (const name of FONTS) {
    if (!wanted.has(name)) bad.push(`خطٌّ في FONTS لا تطلبه صفحة: ${name} — **حمولةٌ لا يراها أحد**`);
  }

  const INDIC = /[٠-٩۰-۹]/;
  for (const file of PAGES) {
    const src = file === "index.html" ? html : readFileSync(join(SITE, file), "utf8");
    if (INDIC.test(visible(src))) bad.push(`${file}: رقمٌ غيرُ لاتينيٍّ في نصٍّ مرئيّ`);
  }
  for (const [file, src] of [["site.js", js], ["download.js", dlJs]]) {
    const body = code(src);
    if (INDIC.test(body)) bad.push(`${file}: رقمٌ غيرُ لاتينيٍّ في نصٍّ يُرسم`);
    for (const m of body.matchAll(/\.toLocale(?:Date|Time)?String\(([^)]*)\)|Intl\.(?:NumberFormat|DateTimeFormat)\(([^)]*)\)/g)) {
      if (!/nu-latn/.test(m[1] ?? m[2] ?? "")) bad.push(`${file}: تنسيقٌ بلا \`nu-latn\` — ${m[0].slice(0, 60)}`);
    }
  }
}

/* ١٢ — كلُّ صفحةٍ تحمّل ما يُحكم عليه باسمها، وكلُّ ما تطلبه موجود
 *
 * **الحارسُ يقرأ `site.js` و`download.js` و`download.css` بأسمائها** ويحكم عليها
 * — فإن كفّت صفحتُها عن تحميلها (وسمٌ حُذف، اسمٌ تغيّر في أحد الطرفين) **بقي
 * يحكم على ملفٍّ لا يُخدَم، وخضرتُه شهادةٌ لما لا يراه أحد**. فيُطابَق:
 *   · ما في `OWN` موسومٌ في صفحته بوسمه — `<script type="module" src>` و`<link
 *     rel="stylesheet" href>`؛ **و`type="module"` شرطٌ**: Vite لا يبني سكربتاً
 *     بغيره، فيبقى `/src/…` في الناتج **ويردّ ٤٠٤ بعد النشر**؛
 *   · وكلُّ `/src/…` تطلبه صفحةٌ ملفٌّ موجود؛
 *   · وكلُّ استيرادٍ نسبيٍّ في السكربتات (`./door.js`) ملفٌّ موجود.
 * **والتعليقُ لا يُحسب وسماً**: `<!-- <script …> -->` لا يحمّل شيئاً. */
{
  const attr = (tag, name) => new RegExp(`\\s${name}\\s*=\\s*["']([^"']+)["']`, "i").exec(tag)?.[1];
  for (const file of PAGES) {
    const src = readFileSync(join(SITE, file), "utf8").replace(/<!--[\s\S]*?-->/g, " ");
    const scripts = new Set();
    const sheets = new Set();
    for (const tag of src.match(/<script\b[^>]*>/gi) ?? []) {
      const ref = attr(tag, "src");
      if (!ref) continue;
      if (attr(tag, "type") !== "module") bad.push(`${file}: <script src="${ref}"> بلا type="module" — **لا يبنيه Vite، فيردّ ٤٠٤ بعد النشر**`);
      else scripts.add(ref);
    }
    for (const tag of src.match(/<link\b[^>]*>/gi) ?? []) {
      const ref = attr(tag, "href");
      if (ref && /^stylesheet$/i.test(attr(tag, "rel") ?? "")) sheets.add(ref);
    }
    for (const ref of [...scripts, ...sheets]) {
      if (ref.startsWith("/src/") && !existsSync(join(SITE, ref.slice(1)))) {
        bad.push(`${file} يطلب ${ref} — **ولا ملفَّ بهذا الاسم**`);
      }
    }
    const own = OWN[file];
    if (!own) continue;
    for (const name of own.scripts) {
      if (!scripts.has(`/src/${name}`)) bad.push(`${file} لا يحمّل /src/${name} (\`<script type="module">\`) — **والحارسُ يحكم عليه كأنه يُخدَم**`);
    }
    for (const name of own.sheets) {
      if (!sheets.has(`/src/${name}`)) bad.push(`${file} لا يحمّل /src/${name} (\`<link rel="stylesheet">\`) — **والحارسُ يحكم عليه كأنه يُخدَم**`);
    }
  }
  for (const file of Object.keys(OWN)) {
    if (!PAGES.includes(file)) bad.push(`OWN يسمّي ${file} — **ولا صفحةَ بهذا الاسم في الجذر**`);
  }

  const srcDir = join(SITE, "src");
  for (const file of readdirSync(srcDir).filter((f) => f.endsWith(".js"))) {
    const body = code(readFileSync(join(srcDir, file), "utf8"));
    for (const [, rel] of body.matchAll(/(?:\bfrom|\bimport)\s*["'](\.\/[^"']+)["']/g)) {
      if (!existsSync(join(srcDir, rel))) bad.push(`src/${file} يستورد ${rel} — **ولا ملفَّ بهذا الاسم**`);
    }
  }
}

/* ── الحكم ──────────────────────────────────────────────────────────── */
if (bad.length) {
  console.error("\n✗ حارسُ الصفحة:");
  for (const line of bad) console.error(`   ${line}`);
  process.exit(1);
}
const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
console.log(
  `✓ check:site · ${PAGES.length} صفحةً بلا قالبٍ ولا وسمِ مُشغِّل وكلُّها في البناء · الأردنُ وحدَه · لا رمزَ عملة · ` +
    `${pageKeys.size} مفتاحاً موصولاً · والقوائمُ الخمسُ في HTML · ` +
    `/download: خاناتُها وروابطُها وأبوابُها ورموزُها مطابقة · ${FONTS.length} خطوطٍ لها مصدر · ` +
    `وسومُ ${Object.keys(OWN).length} صفحاتٍ تحمّل ما يُحكم عليه · ${stamp}Z`,
);
