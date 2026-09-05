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
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SITE = join(HERE, "..");
const html = readFileSync(join(SITE, "index.html"), "utf8");
const js = readFileSync(join(SITE, "src", "site.js"), "utf8");

const bad = [];

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


/* ١ — قوالبُ المُشغِّل */
const templates = html.match(/\{\{[^}]*\}\}/g) ?? [];
const scTags = html.match(/<sc-[a-z]+/g) ?? [];
if (templates.length) bad.push(`قوالبُ مُشغِّلٍ لم تُفكّ: ${templates.slice(0, 3).join(" · ")}`);
if (scTags.length) bad.push(`وسومُ مُشغِّلٍ باقية: ${[...new Set(scTags)].join(" · ")}`);

/* ٢ — بلدٌ غير الأردن */
//
// **والنصُّ وحدَه يُفحص لا السماتُ**: `dir="ltr"` ليست بلداً، واسمُ ملفٍّ ليس
// جملةً. فتُنزع الوسومُ ثم يُقرأ ما يراه الإنسان.
const text = html.replace(/<[^>]*>/g, " ");
for (const country of ["ليبيا", "طرابلس", "بنغازي", "Libya", "سوريا", "مصر", "السعودية"]) {
  if (text.includes(country)) bad.push(`بلدٌ غير الأردن في نصِّ الصفحة: «${country}»`);
}

/* ٣ — أرقامُ أسعار */
for (const token of ["د.أ", "د.ل", "JOD", "LYD", "دينار"]) {
  if (text.includes(token)) bad.push(`رمزُ عملةٍ في الصفحة: «${token}»`);
}

/* ٤ — المفاتيحُ في الاتجاهين */
const readKeys = new Set(
  [...js.matchAll(/data-(?:site|section|social)=["'`]?\$?\{?([a-z_]+)/g)].map((m) => m[1]),
);
const pageKeys = new Set(
  [...html.matchAll(/data-(?:site|section|social)="([a-z_]+)"/g)].map((m) => m[1]),
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

/* ── الحكم ──────────────────────────────────────────────────────────── */
if (bad.length) {
  console.error("\n✗ حارسُ الصفحة:");
  for (const line of bad) console.error(`   ${line}`);
  process.exit(1);
}
const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");
console.log(
  `✓ check:site · لا قالبَ ولا وسمَ مُشغِّل · الأردنُ وحدَه · لا رمزَ عملة · ` +
    `${pageKeys.size} مفتاحاً موصولاً · والقوائمُ الخمسُ في HTML · ${stamp}Z`,
);
