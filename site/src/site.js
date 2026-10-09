/** منطقُ صفحة `taxo.tajora.ly` — **بهويّة TAXO 2.0، مطابقاً للوحات W01–W09** (SPEC §٦٩).
 *
 * ## والصفحةُ تُقرأ كاملةً بلا JavaScript (§٥٢٫٧)
 *
 * **كلُّ قسمٍ مبنيٌّ في HTML وقتَ البناء** — فهذا الملفُّ يضيف الحركةَ ويحدّث القيم، **ولا يرسم قسماً**. ومن أطفأ JavaScript يقرأ
 * الصفحةَ كلَّها بقيمها المخبوزة؛ والطريقُ وحدَه لا يُرسم له، **وهو زينةٌ لا محتوى**.
 *
 * ## وما يُحدَّث من الباب العام
 *
 * `GET /api/site` يعطي النصوصَ والروابطَ والمفاتيح، و`/api/landing` اسمَ العرض. **والقيمُ المخبوزةُ احتياطٌ لا مصدر**: لا يجيب
 * البابُ ⇒ تبقى المخبوزة، **ولا وميضَ ولا فراغ**. «الفشلُ صامتٌ… وما لا يصل لا يُرسم».
 *
 * ## ولا نسبةَ عمولةٍ هنا ولا في الباب (§٦٩-ب)
 *
 * **كان هذا الملفُّ يكتب النسبةَ في ثلاثة مواضعَ ويعدّ إليها عدّاداً** — والنسبةُ نُزعت من الباب نفسِه لا من الرسم وحدَه، فلا
 * يقرؤها شيءٌ هنا ولا يجدها لو قرأ. و`check:site` يمنع عودتَها بالاسم.
 */

import { isStoreUrl, playBadge, readDoor, trademark } from "./door.js";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const desktopMq = window.matchMedia("(min-width: 1024px)");

/* ═══════════════════ القيمُ من الباب ═══════════════════════════════════ */

function setText(sel, value) {
  if (value === undefined || value === null || value === "") return;
  for (const el of $$(sel)) {
    if (el.textContent.trim() !== String(value)) el.textContent = value;
  }
}

/** يخفي ما أعلنته اللوحةُ مخفيّاً — **ولا يرسم مكاناً محجوزاً** (والطريقُ يُعاد بناؤه بلا محطّته). */
function applyHidden(list, attr) {
  (list || []).forEach((key) => {
    $$(`[${attr}="${key}"]`).forEach((el) => el.remove());
  });
}

/** يبدّل بطاقةً إلى «قريباً» — **مطفأٌ يُرسم بشارة، ومخفيٌّ لا يُرسم** (§٥٢٫٤). يُقرأ ولا يُنقر. */
function markSoon(card) {
  if (!card || card.classList.contains("is-soon")) return;
  card.classList.add("is-soon");
  card.setAttribute("aria-disabled", "true");
  const h = $("h3", card);
  if (h && !$(".badge-soon", h)) {
    const badge = document.createElement("span");
    badge.className = "badge-soon";
    badge.textContent = "قريباً";
    h.appendChild(badge);
  }
}

/* ═══════════════════ قسمُ التحميل (W08) — يقود إلى `/download` ═══════════ */
//
// **بابٌ واحدٌ للحزمتين** (SPEC §٦٨-ج/٦): البيانُ والإصدارُ والبصمةُ في صفحة التحميل وحدَها، **والزرّان هنا يقودان إليها كما
// خُبزا** — رابطٌ يعمل بلا JavaScript. **وشارةُ المتجر الرسمية تحت الزرّ** برابطٍ من اللوحة؛ فارغُه يُسقط الشارة.
//
// **ووضعُ `play`** (§٥٢٫٥): الشارةُ الرسميةُ **مكانَ الزرّ** (٢٠٠)، وما يخصّ الحزمةَ يذهب، **ولا زرَّ بلا رابطٍ أبداً** — الفارغُ
// شارةٌ معطَّلةٌ بنصِّها. **وسطرُ العلامة التجارية يتبع ما رُسم**: بالشعار حين تُرسم شارةٌ رسمية، وباسمه وحدَه حين تبقى
// المعطَّلةُ وحدَها، ولا سطرَ حين لا يُذكر المتجرُ أصلاً.

function offBadge() {
  const span = document.createElement("span");
  span.className = "badge-off";
  span.setAttribute("aria-disabled", "true");
  span.textContent = "قريباً على Google Play";
  return span;
}

function download(site) {
  const isPlay = site.distribution_mode === "play";
  const urls = { rider: site.play_url_rider, driver: site.play_url_driver };
  const labels = { rider: "تطبيق الراكب على Google Play", driver: "تطبيق الكبتن على Google Play" };
  let badges = 0;
  for (const card of $$("[data-dl-card]")) {
    const key = card.dataset.dlCard; // rider | driver
    const url = isStoreUrl(urls[key]) ? urls[key] : "";
    const badge = $("[data-play-badge]", card);
    if (isPlay) {
      badge?.remove();
      $("[data-dl-cta]", card)?.replaceWith(url ? playBadge(url, labels[key], 200) : offBadge());
    } else if (badge) {
      if (url) badge.href = url;
      else badge.remove();
    }
    if (url) badges += 1;
  }
  if (isPlay) $$("[data-apk-only]").forEach((el) => el.remove());

  const line = $("[data-trademark]");
  if (badges) trademark(line, true);
  else if (isPlay) trademark(line, false);
  else if (line) line.hidden = true;
}

/* ═══════════════════ سطرُ العرض — بلا رقم ═════════════════════════════ */
//
// **اسمُ العرض كما كتبه المشرف** («أول أسبوع مجاناً»)، **ولا سطرَ بلا عرض**: عرضٌ أُطفئ أو نفد يختفي سطرُه من نفسه. والبابُ لا
// يُخرج سعراً أصلاً (§٥٢٫٣).

async function offer() {
  const slots = $$("[data-offer]");
  if (!slots.length) return;
  try {
    const res = await fetch("/api/landing?country_code=JO", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    const name = typeof data?.offer?.name === "string" ? data.offer.name.trim() : "";
    if (!name) return; // **لا سطر** — وهو المطلوب
    for (const slot of slots) {
      const text = $("[data-offer-text]", slot);
      if (text) text.textContent = name;
      slot.removeAttribute("hidden");
    }
    route?.build();
  } catch { /* صامت */ }
}

/* ═══════════════════ الكشفُ عند الظهور ═════════════════════════════════ */
//
// **450ms بارتفاع ١٦، وبين الإخوة ٧٠** (حتى ثمانية). والإخفاءُ قبله بصنف `js` في الرأس — **فلا شيءَ يختفي قبل أن يعمل هذا**،
// والرأسُ يرفع الصنفَ وحدَه إن لم يقلع هذا خلال ثانيتين ونصف.

function reveal() {
  const items = $$("[data-reveal]");
  if (reduced || !("IntersectionObserver" in window)) {
    items.forEach((el) => el.classList.add("is-in"));
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      for (const en of entries) {
        if (!en.isIntersecting) continue;
        const el = en.target;
        io.unobserve(el);
        const sibs = [...(el.parentElement?.children ?? [])].filter((n) => n.hasAttribute("data-reveal"));
        el.style.transitionDelay = `${Math.min(Math.max(0, sibs.indexOf(el)), 8) * 70}ms`;
        el.classList.add("is-in");
      }
    },
    { rootMargin: "0px 0px -12% 0px", threshold: 0.15 },
  );
  items.forEach((el) => io.observe(el));
}

/* ═══════════════════ W02 — الطريقُ والسيارة ═════════════════════════════ */
//
// **الهندسةُ من مواضع الأقسام وقتَ التشغيل** (مواصفة المصمّم §٦)، وتُعاد مع كلِّ تغيّرٍ في الحجم — فقسمٌ أخفته اللوحةُ يأخذ
// محطّتَه معه، **ولا فراغَ محجوزٌ في الطريق**.
//
//   · **الهاتف**: حارةٌ واحدةٌ على بُعد ١٤ من الحافّة اليمنى، ودبوسٌ عند عين كلِّ قسم، ثمّ منعطفٌ إلى الوسط فوق «حمّل TAXO».
//   · **الحاسوب**: حارتان في الهامشين — يمينٌ ثمّ يسارٌ بالتناوب — **والعبورُ منحنى S داخل حشوة الـ٢٤٠ بين قسمين**، فلا يقطع
//     محتوى. والأخيرُ إلى الوسط.
//   · **السيارة**: عند `scrollY + 0.58 × ارتفاع الشاشة`، **وتبدأ واقفةً تحت دائرة الانطلاق** ثمّ تلحق الموضعَ خلال أوّل تمرير؛
//     مقدّمتُها مع اتّجاه السير، والمقطوعُ يُرسم خلفها، والدبابيسُ تضيء حين تتجاوزها.
//   · **في مدى الخدمة النسائية** يصير المرسومُ والسيارةُ والدبابيسُ برقوقاً (تدرّجٌ بحدّين قاطعين).
//   · **الوصول** مرّةً لكلِّ زيارة: نبضتان، ثمّ يتكوّن الـX مكانَ مربّع الوجهة.
//   · **«تقليل الحركة»**: الطريقُ مرسومٌ كاملاً، والدبابيسُ مضاءة، والسيارةُ واقفةٌ فوق الوجهة، والـX متكوّن — **ولا شيءَ يتحرّك**.

const SVG = "http://www.w3.org/2000/svg";

class Route {
  constructor(root) {
    this.root = root;
    this.svg = $("#taxo-route", root);
    this.track = $("#taxo-track", root);
    this.drawn = $("#taxo-drawn", root);
    this.pins = $("#taxo-pins", root);
    this.start = $("#taxo-start", root);
    this.end = $("#taxo-end", root);
    this.car = $("#taxo-car", root);
    this.carScale = $(".car-scale", this.car);
    this.grad = $("#taxo-grad", root);
    this.arrived = false;
    if (!this.svg || !this.drawn) return;

    this.build();
    this.ro = new ResizeObserver(() => this.schedule());
    this.ro.observe(root);
    window.addEventListener("resize", () => this.schedule(), { passive: true });
    document.fonts?.ready?.then(() => this.build());
    window.addEventListener("load", () => this.build(), { once: true });
    if (!reduced) {
      window.addEventListener("scroll", () => this.tick(), { passive: true });
    }
  }

  schedule() {
    if (this._b) return;
    this._b = requestAnimationFrame(() => {
      this._b = 0;
      this.build();
    });
  }

  tick() {
    if (this._r) return;
    this._r = requestAnimationFrame(() => {
      this._r = 0;
      this.update();
    });
  }

  /** موضعُ عنصرٍ في إحداثيات الجذر — **من `offsetTop` لا من `getBoundingClientRect`**.
   *
   * **قِيس ٢٠٢٦-١٠-٠٩**: الدبوسُ رُسم أسفلَ عين قسمه بستّة عشرَ بكسلاً — العينُ كانت في حركة الكشف (`translateY(16px)`)
   * لحظةَ القياس، **والمستطيلُ يقيس ما يُرسم لا ما تخطّط له الصفحة**. والإزاحةُ لا تمسّ `offsetTop`. */
  box(el) {
    let top = 0;
    for (let n = el; n && n !== this.root; n = n.offsetParent) top += n.offsetTop;
    return { top, height: el.offsetHeight, cy: top + el.offsetHeight / 2 };
  }

  build() {
    const root = this.root;
    const W = root.clientWidth;
    const H = root.scrollHeight;
    const desktop = desktopMq.matches;
    const rootTop = root.getBoundingClientRect().top + window.scrollY;
    const sections = $$("[data-route]", root).map((el) => {
      const b = this.box(el);
      return { el, key: el.dataset.route, lane: el.dataset.lane || "right", top: b.top, bottom: b.top + b.height };
    });
    const hero = sections.find((s) => s.key === "hero");
    const startEl = hero && $("[data-pin]", hero.el);
    if (!hero || !startEl || sections.length < 2) return;

    // **الحارتان في نصف الهامش**: ٦٠ من كلِّ حافّةٍ على 1440 (الهامشُ ١٢٠)
    const margin = Math.max(48, (W - 1200) / 2);
    const inset = desktop ? margin / 2 : 14;
    const laneX = (s) => {
      if (!desktop) return W - inset;
      if (s.lane === "center") return W / 2;
      return s.lane === "left" ? inset : W - inset;
    };
    const band = 120;
    const startY = this.box(startEl).cy;
    const last = sections[sections.length - 1];
    const destEl = $("[data-dest]", last.el);
    // **الوجهةُ فوق «حمّل TAXO»** (هاتف ١٠٤ من رأس القسم، حاسوب ١٥٠) — ومن العنوان نفسِه، فتتبعه أينما انزاح
    let destY = destEl ? this.box(destEl).top - (desktop ? 50 : 36) : last.bottom - (desktop ? band : 72);
    let destX = destEl ? W / 2 : laneX(last);

    let d;
    const fx = (n) => n.toFixed(1);
    if (desktop) {
      let prev = hero;
      d = `M${fx(laneX(hero))} ${fx(startY)}`;
      for (const s of sections.slice(1)) {
        const x1 = laneX(prev);
        const x2 = destEl && s === last ? W / 2 : laneX(s);
        const B = s.top;
        d += ` L${fx(x1)} ${fx(B - band)} C${fx(x1)} ${fx(B)} ${fx(x2)} ${fx(B)} ${fx(x2)} ${fx(B + band)}`;
        prev = s;
      }
      if (!destEl) destX = laneX(last);
      d += ` L${fx(destX)} ${fx(destY)}`;
    } else {
      const x = W - inset;
      if (destEl) {
        // **ذيلٌ عموديٌّ فوق الـX** (٦٦) — فتقف السيارةُ عند `endY` قائمةً فوقه كما في W02، لا مائلةً على المنحنى.
        // ونقاطُ التحكّم تُبقي الصادَ متزايداً على المنحنى كلِّه، و`lenAt` يبحث بالتنصيف فيشترطه.
        d =
          `M${fx(x)} ${fx(startY)} L${fx(x)} ${fx(destY - 150)} ` +
          `C${fx(x)} ${fx(destY - 96)} ${fx(W / 2)} ${fx(destY - 120)} ${fx(W / 2)} ${fx(destY - 66)} ` +
          `L${fx(W / 2)} ${fx(destY)}`;
      } else {
        destX = x;
        d = `M${fx(x)} ${fx(startY)} L${fx(x)} ${fx(destY)}`;
      }
    }

    this.svg.setAttribute("width", String(W));
    this.svg.setAttribute("height", String(H));
    this.svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    this.track.setAttribute("d", d);
    this.drawn.setAttribute("d", d);
    this.len = this.drawn.getTotalLength();
    this.drawn.style.strokeDasharray = `${this.len} ${this.len}`;
    this.drawn.style.strokeWidth = desktop ? "3" : "2.5";

    // **برقوقٌ في مدى الخدمة النسائية** — تدرّجٌ بإحداثيات الصفحة وحدّين قاطعين
    const women = sections.find((s) => s.key === "women");
    this.grad.setAttribute("y2", String(H));
    const stops = Object.fromEntries($$("stop[data-w]", this.grad).map((s) => [s.dataset.w, s]));
    const a = women ? women.top / H : 1;
    const b = women ? women.bottom / H : 1;
    stops.a.setAttribute("offset", String(a));
    stops.b.setAttribute("offset", String(a));
    stops.c.setAttribute("offset", String(b));
    stops.d.setAttribute("offset", String(b));
    this.women = women ? [women.top, women.bottom] : null;

    // دائرةُ الانطلاق
    this.start.setAttribute("cx", fx(desktop ? laneX(hero) : W - inset));
    this.start.setAttribute("cy", fx(startY));
    this.start.setAttribute("r", desktop ? "11" : "8");
    this.start.style.strokeWidth = desktop ? "5" : "3.5";

    // الدبابيس — عند عين كلِّ قسم، على حارته
    const pins = [];
    this.pins.replaceChildren();
    for (const s of sections.slice(1)) {
      const anchor = $("[data-pin]", s.el);
      if (!anchor) continue;
      const y = this.box(anchor).cy;
      const c = document.createElementNS(SVG, "circle");
      c.setAttribute("class", `route-pin${s.key === "women" ? " is-women" : ""}`);
      c.setAttribute("cx", fx(desktop ? laneX(s) : W - inset));
      c.setAttribute("cy", fx(y));
      c.setAttribute("r", desktop ? "8" : "6");
      this.pins.appendChild(c);
      pins.push({ el: c, y });
    }
    this.pinList = pins;

    // الوجهة — مربّعٌ ٢٢ على الهاتف و٢٦ على الحاسوب، والـX بقضيبين ٣٨ و٥٢ (المقاسُ على الأب، والحركةُ على الأبناء)
    this.end.setAttribute("transform", `translate(${fx(destX)} ${fx(destY)})`);
    $(".end-scale", this.end).setAttribute("transform", desktop ? "scale(1.2)" : "");
    this.destY = destY;

    // السيارة: ٢٠×٣٨ على الحاسوب و١٤×٢٦ على الهاتف — **تقف تحت دائرة الانطلاق** وفوق الوجهة
    this.carScale.setAttribute("transform", desktop ? "scale(1.43)" : "");
    this.parkY = startY + (desktop ? 55 : 38);
    this.endY = destY - (desktop ? 50 : 44);
    this.lenAt = (y) => {
      let lo = 0;
      let hi = this.len;
      for (let i = 0; i < 24; i++) {
        const m = (lo + hi) / 2;
        if (this.drawn.getPointAtLength(m).y < y) lo = m;
        else hi = m;
      }
      return lo;
    };
    this.rootTop = rootTop;
    this.update();
  }

  placeCar(L) {
    const p = this.drawn.getPointAtLength(L);
    const q = this.drawn.getPointAtLength(Math.min(this.len, L + 3));
    const back = this.drawn.getPointAtLength(Math.max(0, L - 3));
    const [dx, dy] = q.x === p.x && q.y === p.y ? [p.x - back.x, p.y - back.y] : [q.x - p.x, q.y - p.y];
    // **المقدّمةُ مع اتّجاه السير**: الزاويةُ المماسّة + ٩٠° (مقدّمةُ الرسم نحو الأعلى)
    const ang = (Math.atan2(dy, dx) * 180) / Math.PI + 90;
    this.car.setAttribute("transform", `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)}) rotate(${ang.toFixed(1)})`);
    this.car.classList.toggle("is-women", !!this.women && p.y >= this.women[0] && p.y <= this.women[1]);
    return p;
  }

  update() {
    if (!this.len) return;
    if (reduced) {
      // **لا شيءَ يتحرّك**: المرسومُ كاملاً، والسيارةُ واقفةٌ فوق الوجهة، والـX متكوّن
      this.drawn.style.strokeDashoffset = "0";
      this.placeCar(this.lenAt(this.endY));
      this.pinList.forEach((pt) => pt.el.classList.add("is-lit"));
      this.svg.classList.add("is-formed");
      return;
    }
    const sy = window.scrollY;
    const vh = window.innerHeight;
    // **تبدأ واقفةً ثمّ تلحق ٥٨٪ من الشاشة** خلال أوّل ٥٨٪ من التمرير — منحدرٌ رتيبٌ لا قفزة
    const parkDoc = this.rootTop + this.parkY;
    const want = sy + 0.58 * vh;
    const lag = Math.max(0, 0.58 * vh - parkDoc);
    const ramp = Math.max(1, 0.58 * vh);
    const ty = Math.max(this.parkY, Math.min(this.endY, want - lag * Math.max(0, 1 - sy / ramp) - this.rootTop));
    const L = this.lenAt(ty);
    const p = this.placeCar(L);
    const atEnd = ty >= this.endY - 1;
    // **واقفةً لا مرسومَ خلفها** — في أعلى الصفحة يظهر المسارُ الباهتُ وحده كما في W01، لا خطٌّ من دائرة الانطلاق إليها
    const parked = ty <= this.parkY + 0.5;
    this.drawn.style.strokeDashoffset = atEnd ? "0" : parked ? String(this.len) : String(this.len - L);
    this.pinList.forEach((pt) => pt.el.classList.toggle("is-lit", pt.y <= p.y + 4));
    if (atEnd && !this.arrived) {
      this.arrived = true;
      this.svg.classList.add("is-arrived");
    }
  }
}

/* ═══════════════════ الواجهةُ على الحاسوب — الهاتفُ يرتفع أبطأ من الصفحة ═══ */

function parallax() {
  const phone = $("[data-parallax]");
  if (!phone || reduced) return;
  let raf = 0;
  const run = () => {
    raf = 0;
    const sy = window.scrollY;
    phone.style.translate = desktopMq.matches && sy < window.innerHeight * 1.5 ? `0 ${(-0.07 * sy).toFixed(1)}px` : "";
  };
  window.addEventListener("scroll", () => { if (!raf) raf = requestAnimationFrame(run); }, { passive: true });
  run();
}

/* ═══════════════════ الإقلاع ═══════════════════════════════════════════ */

let route = null;

(async function boot() {
  window.__taxoMotion = true;
  reveal();
  parallax();
  const root = $("#taxo-root");
  if (root) route = new Route(root);

  const site = await readDoor();
  if (site) {
    setText("[data-site='hero_title']", site.hero_title);
    setText("[data-site='hero_subtitle']", site.hero_subtitle);
    setText("[data-site='hero_note']", site.hero_note);
    setText("[data-site='support_email']", site.support_email);
    setText("[data-site='privacy_email']", site.privacy_email);

    const support = $("a[data-site-href='support_email']");
    if (support && site.support_email) support.href = `mailto:${site.support_email}`;
    const privacy = $("a[data-site-href='privacy_email']");
    if (privacy && site.privacy_email) privacy.href = `mailto:${site.privacy_email}`;

    // **الشريطُ الإعلانيّ** — ثلاثةُ حقول: مفتاحٌ ونصٌّ ورابط. ومطفأٌ لا يُرسم.
    const bar = $("[data-announce]");
    if (bar) {
      if (site.announce_enabled && site.announce_text) {
        $("[data-announce-text]", bar).textContent = site.announce_text;
        const link = $("[data-announce-link]", bar);
        if (site.announce_url) link.href = site.announce_url;
        else {
          link.removeAttribute("href");
          $("[data-announce-arrow]", bar)?.remove();
        }
        bar.removeAttribute("hidden");
      } else bar.remove();
    }

    // **رابطٌ لما له رابطٌ فقط** — ولا رابطَ معطَّلٌ محجوز، ولا عنوانُ «تابعنا» فوق لا شيء.
    let social = 0;
    for (const net of ["facebook", "instagram", "tiktok", "x", "whatsapp"]) {
      const el = $(`[data-social="${net}"]`);
      if (!el) continue;
      const url = site[`social_${net}`];
      if (url) {
        el.href = url;
        el.removeAttribute("hidden");
        if (net !== "whatsapp") social += 1;
      } else el.remove();
    }
    if (social) $("[data-social-group]")?.removeAttribute("hidden");
    else $("[data-social-group]")?.remove();

    // **السياساتُ خلف مفتاحها** (§٥٢٫٦) — ولا تُعرض على مستخدمٍ قبل المراجعة. وحذفُ الحساب ليس خلفه.
    if (!site.policies_public) $$("[data-policy-link]").forEach((el) => el.remove());

    applyHidden(site.hidden_sections, "data-section");
    applyHidden(site.hidden_cards, "data-card");

    // **خدمةٌ مطفأةٌ في الأردن تُرسم «قريباً»** — ولا تختفي بلا أثر. والمخفيّةُ أُزيلت أعلاه.
    $$("[data-feature]").forEach((el) => {
      if (site.features && site.features[el.dataset.feature] === false) markSoon(el);
    });
    // **قسمٌ بلا بطاقةٍ لا يُرسم عنوانُه فوق فراغ**
    const services = $("[data-services]");
    if (services && !services.children.length) $$('[data-section="services"]').forEach((el) => el.remove());

    download(site);
    route?.build();
  }

  await offer();
})();
