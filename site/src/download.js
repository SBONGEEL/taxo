/** منطقُ صفحة التحميل `/download` — **بابٌ واحدٌ للحزمتين** (SPEC §٦٨-ج/٦).
 *
 * ## والصفحةُ تعمل بلا JavaScript
 *
 * **الزرّان رابطان مباشران مخبوزان** (`/downloads/taxo-rider.apk`) يعملان كما
 * هما، والقيمُ «—» حتى يُقرأ البيان. **ولا قوسَ قالبٍ يصل الزائر**: كان قسمُ
 * التحميل في الرئيسية يُبقي `{version}` حرفيّاً لمن لم يصله البيان.
 *
 * ## وما يُقرأ — من بابين لا ثالث لهما
 *
 * · **بيانُ الحزم** (`/downloads/manifest.json`) — يكتبه `tools/apk-manifest.mjs`
 *   من الملفّ نفسِه: البصمةُ والحجمُ والتاريخُ والإصدار. **ولا رقمَ يُكتب بيد.**
 * · **البابُ العامّ** (`GET /public/site`) — وضعُ التوزيع ورابطا Google Play.
 *
 * ## ورابطُ الملفّ يحمل بصمتَه
 *
 * `?v=` بأوّل اثني عشر حرفاً من البصمة: **اسمُ الملفّ ثابتٌ ومحتواه يتغيّر**،
 * فمتصفّحٌ حفظه يعيده من ذاكرته — **فيثبّت إنسانٌ بناءً قديماً وهو يظنّه
 * الجديد**. والبصمةُ في العنوان تجعل كلَّ بناءٍ عنواناً لم يُطلب قبله.
 *
 * ## ووضعا التوزيع (§٥٢٫٥، وما زاده §٦٨)
 *
 * · `apk`: زرُّ الملفّ **ومعه رابطُ Google Play ثانياً** — التطبيقان في اختبارٍ
 *   مغلقٍ هناك، **والسطرُ يقول ذلك** فلا يُفتح رابطٌ لا يُظهر شيئاً بلا تفسير.
 * · `play`: كالرئيسية بحرفها — الشارةُ الرسميةُ مكانَ الزرّ، **وما يخصّ الملفَّ
 *   يذهب**، ويبقى سطرُ «من ثبّت من هنا يحذف أوّلاً» (قرارُ المالك ٢٠٢٦-٠٩-٠٧).
 * · `play` **و`apk_page_enabled` مشتعل** (مفتاحُ اللوحة «أتِح صفحة APK غير
 *   المفهرسة في وضع المتجر»): **تبقى الحزمةُ كما في `apk`** — الزرُّ والبصمةُ
 *   والخطوات — ورابطُ المتجر ثانياً، **بلا سطر «اختبارٌ مغلق»**: في `play`
 *   خرج التطبيقان إلى المتجر. **ومطفأً** (الافتراضُ في الخلفية) فكالسطر قبله.
 */

import { playBadge, readDoor, trademark } from "./door.js";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

//: **الخاناتُ التي تُملأ من البيان** — و`check:site` يقرأ هذه القائمةَ نفسَها
//: ويطابقها بخانات `download.html` في الاتجاهين: خانةٌ لا تُملأ تبقى «—»
//: إلى الأبد، **ومفتاحٌ بلا خانةٍ يُحسب ولا يراه أحد**.
const FIELDS = ["version_name", "version_code", "built_at", "size", "sha256"];

//: اسمُ كلِّ تطبيقٍ كما يُعرض — والمفتاحُ مفتاحُ البيان (`apps[].key`)
const NAMES = { rider: "TAXO", driver: "TAXO كبتن" };

const SHA = /^[0-9a-f]{64}$/;
// **اسمُ ملفٍّ لا مسار**: ما يُبنى منه رابطٌ لا يحمل `/` ولا `..`
const FILE = /^[a-z0-9][a-z0-9._-]*\.apk$/i;
// **ورابطُ المتجر يبدأ بـ`https://play.google.com/`** — يفحصه المخطَّطُ أيضاً
const STORE = /^https:\/\/play\.google\.com\//;

const mb = (n) => (n / 1048576).toFixed(1);
// **أرقامٌ لاتينيةٌ بالوسم لا بالافتراض** (`nu-latn`): متصفّحٌ عربيُّ اللغة
// يكتب التاريخَ بالأرقام الهندية بغيره.
function day(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("ar-u-nu-latn", { year: "numeric", month: "long", day: "numeric" });
}

/** يُعلن للقارئ الصوتيّ ما تغيّر — **والزرُّ يقوله بنصِّه أيضاً**. */
function say(text) {
  const live = $("[data-live]");
  if (live) live.textContent = text;
}

/* ═══════════════════ البيان — ثلاثُ حالاتٍ لا اثنتان ═══════════════════ */
//
// **غيابُ البيان ليس تعذُّرَ قراءته**: ٤٠٤ يعني أن لا ملفَّ نُشر — فالزرُّ
// يُخفى ولا يشير إلى لا شيء. **وتعذُّرُ القراءة** (شبكةٌ أو خطأُ خادم) لا يقول
// شيئاً عن الملفّ — فيبقى الرابطُ المخبوزُ كما هو، **ويُقال إن البيانَ لم يُقرأ**.

async function readManifest() {
  try {
    const res = await fetch("/downloads/manifest.json", { cache: "no-store" });
    if (res.status === 404) return { apps: [] };
    if (!res.ok) return null;
    const manifest = await res.json();
    return Array.isArray(manifest?.apps) ? manifest : null;
  } catch {
    return null;
  }
}

/* ═══════════════════ النسخ — الحافظةُ ثمّ التحديد ═══════════════════════ */
//
// **`navigator.clipboard` يشترط أصلاً آمناً وإذناً** — وقد يُرفض في متصفّحٍ
// داخل تطبيق. فإن فشل حُدِّد النصُّ كلُّه وجُرّب الأمرُ القديم، **وإن فشل هو
// أيضاً بقيت البصمةُ محدَّدةً والزرُّ يقول ذلك** — لا نجاحَ يُعلَن لم يقع.

const timers = new WeakMap();

function select(node) {
  const range = document.createRange();
  range.selectNodeContents(node);
  const picked = window.getSelection();
  picked.removeAllRanges();
  picked.addRange(range);
}

async function copy(button, code, name) {
  const text = code.textContent.trim();
  if (!SHA.test(text)) return;
  let done = false;
  try {
    await navigator.clipboard.writeText(text);
    done = true;
  } catch { /* لا حافظةَ هنا — يُحدَّد النصّ */ }
  if (!done) {
    select(code);
    try {
      done = document.execCommand("copy");
    } catch {
      done = false;
    }
  }
  const label = $("[data-copy-text]", button);
  if (label) {
    label.textContent = done ? "نُسخت" : "حُدِّدت";
    clearTimeout(timers.get(button));
    timers.set(button, setTimeout(() => { label.textContent = "نسخ"; }, 2400));
  }
  say(done ? `نُسخت بصمةُ ${name} كاملةً.` : `حُدِّدت بصمةُ ${name} — انسخها من قائمة الهاتف.`);
}

/* ═══════════════════ البطاقة ═══════════════════════════════════════════ */

function fill(card, app) {
  const key = card.dataset.app;
  const get = $("[data-get]", card);
  if (get) {
    get.href = `/downloads/${app.file}?v=${app.sha256.slice(0, 12)}`;
    get.setAttribute("download", app.file);
  }

  const values = {
    version_name: app.version_name,
    version_code: app.version_code,
    built_at: day(app.built_at),
    size: Number.isFinite(app.size_bytes) ? mb(app.size_bytes) : null,
    sha256: app.sha256,
  };
  for (const name of FIELDS) {
    const el = $(`[data-field="${name}"]`, card);
    const value = values[name];
    // **وما لم يُقرأ يبقى «—»** — `version_code` يغيب إن بُني البيانُ بلا
    // `aapt2`، **ورقمٌ مخترعٌ مكانه أسوأُ من شَرطة**.
    if (!el || value === undefined || value === null || value === "") continue;
    if (name === "size") {
      // **الرقمُ بـUnbounded والوحدةُ بخطّ النصّ** (قِيس بلقطة): نقطةُ «م.ب»
      // من Unbounded ثقيلةٌ بين حرفين عربيّين
      const num = document.createElement("span");
      num.className = "num";
      num.textContent = String(value);
      el.replaceChildren(num, " م.ب");
    } else {
      el.textContent = String(value);
    }
  }

  const button = $("[data-copy]", card);
  const code = $('[data-field="sha256"]', card);
  if (button && code) {
    button.hidden = false;
    button.addEventListener("click", () => copy(button, code, NAMES[key] ?? key));
  }
}

/** تطبيقٌ ليس في البيان — **لا زرَّ يشير إلى لا شيء، ويُقال ذلك**. */
function unpublished(card) {
  $("[data-get]", card)?.remove();
  $$("[data-apk-only]", card).forEach((el) => el.remove());
  const note = $("[data-missing]", card);
  if (note) note.hidden = false;
}

/** سطرُ النسب — **من أيِّ إيداعٍ بُنيت الحزمتان** (شرطُ المالك ٢٠٢٦-٠٨-٢١).
 *
 * `apk-manifest.mjs` ينشر الإيداعَ مع الحزمة «فمن حمّل يعرف ما حمّل». **ولا
 * يُعرض من شجرةٍ متّسخة**: حزمةٌ بُنيت فوق تعديلٍ غيرِ مودَعٍ لا تُنسب إلى
 * إيداعٍ بحقّ، **وسطرٌ يدّعي ذلك أسوأُ من غيابه**.
 */
function provenance(manifest) {
  const line = $("[data-build]");
  const commit = String(manifest.commit ?? "");
  if (!line || manifest.dirty || !/^[0-9a-f]{7,40}$/.test(commit)) return;
  const code = (text) => {
    const el = document.createElement("code");
    el.dir = "ltr";
    el.textContent = text;
    return el;
  };
  line.append("بُنيت الحزمتان من الإيداع ", code(commit.slice(0, 12)));
  const tag = String(manifest.tag ?? "");
  if (/^[A-Za-z0-9._-]{1,64}$/.test(tag)) line.append(" · الوسم ", code(tag));
  line.hidden = false;
}

/* ═══════════ Google Play — ثانياً ما بقيت الحزمة، ووحدَه حين تذهب ═══════════ */

function offBadge() {
  const span = document.createElement("span");
  span.className = "badge-off";
  span.setAttribute("aria-disabled", "true");
  span.textContent = "قريباً على Google Play";
  return span;
}

/** رابطُ المتجر — **شارةٌ مكانَ الزرّ** إن لم تبقَ الحزمة، **ورابطٌ نصّيٌّ تحته**
 * إن بقيت. و`isPlay` يقول أيَّ الوضعين، و`badges` أيَّ الشكلين. */
function store(site, isPlay, badges) {
  const urls = { rider: site?.play_url_rider, driver: site?.play_url_driver };
  let shown = false;
  let logo = false;
  for (const card of $$("[data-app]")) {
    const key = card.dataset.app;
    const url = STORE.test(urls[key] ?? "") ? urls[key] : "";
    if (badges) {
      // **لا زرَّ بلا رابطٍ أبداً** — الفارغُ شارةٌ معطَّلةٌ بنصِّها (§٥٢٫٥)
      $("[data-get]", card)?.replaceWith(
        url ? playBadge(url, `${NAMES[key] ?? key} على Google Play`) : offBadge(),
      );
      if (url) shown = logo = true;
      continue;
    }
    const slot = $("[data-play]", card);
    const link = $("[data-play-link]", card);
    if (url && slot && link) {
      link.href = url;
      slot.hidden = false;
      shown = true;
    }
  }
  // **«والشعار» حين تُرسم الشارةُ وحدَها** — الرابطُ النصّيُّ اسمٌ بلا شعار
  if (shown) trademark($("[data-trademark]"), logo);
  // **«اختبارٌ مغلق» يخصّ وضعَ الحزمة**: في `play` خرج التطبيقان إلى المتجر
  if (shown && !isPlay) $("[data-play-note]")?.removeAttribute("hidden");
}

/* ═══════════════════ الإقلاع ═══════════════════════════════════════════ */

(async function boot() {
  const [site, manifest] = await Promise.all([readDoor(), readManifest()]);
  const isPlay = site?.distribution_mode === "play";
  // **الحزمةُ تبقى في `play` إن أتاحها المالك** (`apk_page_enabled`، §٥٢٫٥) —
  // **و`true` حرفاً**: بابٌ أجاب بغير منطقيٍّ لا يُبقي ما أطفأه المالك.
  const apkPage = !isPlay || site?.apk_page_enabled === true;

  // **بريدُ الدعم من الباب** — والمخبوزُ احتياطٌ لا مصدر
  const support = $("[data-support]");
  if (support && site?.support_email) {
    support.textContent = site.support_email;
    support.href = `mailto:${site.support_email}`;
  }

  if (!apkPage) {
    $$("[data-apk-only]").forEach((el) => el.remove());
  } else if (!manifest) {
    // **لم يُقرأ البيان** — الرابطُ المخبوزُ باقٍ والقيمُ «—»، **ويُقال ذلك**
    $("[data-status]")?.removeAttribute("hidden");
  } else {
    for (const card of $$("[data-app]")) {
      const app = manifest.apps.find((row) => row?.key === card.dataset.app);
      if (!app) unpublished(card);
      // **بيانٌ بقيمٍ لا تُشبه ما يكتبه `apk-manifest.mjs` لا يُبنى منه رابط**:
      // يبقى المخبوزُ كما هو، فهو أصدقُ من رابطٍ مركَّبٍ من قيمةٍ غريبة.
      else if (FILE.test(String(app.file ?? "")) && SHA.test(String(app.sha256 ?? ""))) fill(card, app);
    }
    provenance(manifest);
  }

  store(site, isPlay, !apkPage);
})();
