/** منطقُ صفحة `taxo.tajora.ly` — **الحركةُ منقولةٌ من التصميم، والبياناتُ موصولة**.
 *
 * ## والصفحةُ تُقرأ كاملةً بلا JavaScript
 *
 * **القوائمُ الخمسُ مبنيّةٌ في HTML وقتَ البناء** لا وقتَ التشغيل — فهذا الملفُّ
 * يضيف الحركةَ ويحدّث القيم، **ولا يرسم قسماً**. ومن أطفأ JavaScript يقرأ
 * الصفحةَ كلَّها بقيمها المخبوزة.
 *
 * ## وما يُحدَّث من الباب العام
 *
 * `GET /public/site` يعطي النصوصَ والروابطَ والمفاتيح. **والقيمُ المخبوزةُ
 * احتياطٌ لا مصدر**: لا يجيب البابُ ⇒ تبقى المخبوزة، **ولا وميضَ ولا فراغ**.
 * وهي قاعدةُ `app.js` القائمة بحرفها: «الفشلُ صامتٌ… وما لا يصل لا يُرسم».
 *
 * ## ولا مفتاحَ ثانٍ لمفهومٍ قائم
 *
 * **مصدرُ قسم التحميل هو المبنيُّ سلفاً**: `distribution_mode` من الإعدادات
 * (وكان `source` في `landing/config.js`، **نُقل ولم يُخترع ثانياً**)، وبيانُ
 * الحزمة من `downloads/manifest.json` الذي يكتبه CI. **والتصميمُ يُلبَس فوقهما.**
 */

const DOOR = "/api/site";
const BAKED = "/site.json";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ═══════════════════ الشاشةُ الأولى — تُتخطّى بأيِّ لمسة ═══════════════ */

(function splash() {
  const el = $('[data-screen-label="splash"]');
  if (!el) return;
  let gone = false;
  const skip = () => {
    if (gone) return;
    gone = true;
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 320);
  };
  ["pointerdown", "keydown"].forEach((e) => window.addEventListener(e, skip, { once: true }));
  window.addEventListener("wheel", skip, { passive: true, once: true });
  window.addEventListener("touchstart", skip, { passive: true, once: true });
  setTimeout(skip, reduced ? 0 : 750);
})();

/* ═══════════════════ التحويم — أصنافٌ مولَّدةٌ وقتَ البناء ═══════════════ */
//
// **التصميمُ يكتب `style-hover` على العنصر**، وهي خاصّيةُ مُشغِّلِ DC لا CSS.
// فحُوِّلت إلى قواعدَ حقيقيةٍ في الورقة، **ويحملها العنصرُ في `data-hov`**.

/* ═══════════════════ ما يُقرأ من الأبواب ═══════════════════════════════ */

async function readDoor() {
  // **المخبوزُ أوّلاً فلا وميض**، ثمّ الحيُّ يصحّحه إن اختلف.
  try {
    const res = await fetch(DOOR, { cache: "no-store" });
    if (res.ok) return await res.json();
  } catch { /* الفشلُ صامت */ }
  try {
    const res = await fetch(BAKED, { cache: "no-store" });
    if (res.ok) return await res.json();
  } catch { /* والمخبوزُ قد يغيب في التطوير */ }
  return null;
}

function setText(sel, value) {
  if (value === undefined || value === null || value === "") return;
  const el = $(sel);
  if (el && el.textContent.trim() !== String(value)) el.textContent = value;
}

/** يخفي ما أعلنته اللوحةُ مخفيّاً — **ولا يرسم مكاناً محجوزاً**. */
function applyHidden(list, attr) {
  (list || []).forEach((key) => {
    $$(`[${attr}="${key}"]`).forEach((el) => el.remove());
  });
}

/** يبدّل بطاقةً إلى «قريباً» — **مطفأٌ يُرسم بشارة، ومخفيٌّ لا يُرسم**. */
function markSoon(el) {
  if (!el || el.dataset.soon === "1") return;
  el.dataset.soon = "1";
  el.style.background = "#faf9f6";
  el.style.borderStyle = "dashed";
  const h = el.querySelector("h3");
  if (h && !h.querySelector("[data-soon-badge]")) {
    const badge = document.createElement("span");
    badge.dataset.soonBadge = "1";
    badge.textContent = "قريباً";
    badge.style.cssText =
      "margin-inline-start:8px;font-size:11px;font-weight:700;color:#9a6b00;" +
      "background:#ffffff;border:1px solid #ddd8cf;border-radius:8px;padding:2px 8px";
    h.appendChild(badge);
  }
}

/* ═══════════════════ قسمُ التحميل — الحالتان ═══════════════════════════ */

const mb = (n) => (n / 1048576).toFixed(1);
const day = (iso) =>
  new Date(iso).toLocaleDateString("ar-u-nu-latn", {
    year: "numeric", month: "long", day: "numeric",
  });

/** شارةُ Google Play الرسمية — **من ملفّ Google كما هو**.
 *
 * **ولا زرَّ مرسومٌ يحاكيها** (شرطُ المالك): الشارةُ ملفٌّ رسميٌّ بمساحته
 * الآمنة، **ورسمُ بديلٍ يشبهها مخالفةُ علامةٍ تجارية**.
 */
function playBadge(href, label) {
  const a = document.createElement("a");
  a.href = href;
  a.rel = "noopener";
  a.setAttribute("aria-label", label);
  a.style.cssText = "display:inline-block;margin-top:auto;min-height:44px";
  const img = document.createElement("img");
  img.src = "/assets/google-play-badge.png";
  img.alt = label;
  img.width = 180;
  img.height = 53;
  img.loading = "lazy";
  img.style.cssText = "display:block;width:180px;height:auto";
  a.appendChild(img);
  return a;
}

function disabledBadge(text) {
  const span = document.createElement("span");
  span.setAttribute("aria-disabled", "true");
  span.textContent = text;
  span.style.cssText =
    "display:inline-flex;align-items:center;justify-content:center;min-height:52px;" +
    "margin-top:auto;padding:0 20px;border-radius:14px;background:#0d1014;color:#8b949e;" +
    "border:1px dashed #2a313a;font-size:15px;font-weight:500;cursor:not-allowed";
  return span;
}

async function download(site) {
  const mode = site?.distribution_mode ?? "apk";
  const cards = $$("[data-dl-card]");
  const isPlay = mode === "play";

  // **خطواتُ التثبيت وسطرُ الإزالة يخصّان APK وحدَه** — ويذهبان مع المتجر.
  if (isPlay) {
    $$("[data-apk-only]").forEach((el) => el.remove());
    $("[data-trademark]")?.removeAttribute("hidden");
  }

  let manifest = null;
  if (!isPlay) {
    try {
      const res = await fetch("/downloads/manifest.json", { cache: "no-store" });
      if (res.ok) manifest = await res.json();
    } catch { /* صامت */ }
  }

  for (const card of cards) {
    const key = card.dataset.dlCard; // rider | driver
    const meta = card.querySelector("[data-dl-meta]");
    const cta = card.querySelector("[data-dl-cta]");
    if (!cta) continue;

    if (isPlay) {
      const url = key === "rider" ? site?.play_url_rider : site?.play_url_driver;
      meta?.remove();
      const label = key === "rider" ? "تطبيق الراكب على Google Play" : "تطبيق الكبتن على Google Play";
      // **لا زرَّ بلا رابطٍ أبداً** — الفارغُ شارةٌ معطَّلةٌ بنصِّها.
      cta.replaceWith(url ? playBadge(url, label) : disabledBadge("قريباً على Google Play"));
      continue;
    }

    const app = manifest?.apps?.find((a) => a.key === key);
    if (!app) {
      // **زرٌّ بلا ملفٍّ يُخفى ولا يشير إلى لا شيء** — قاعدةُ `app.js` القائمة.
      cta.remove();
      meta?.remove();
      continue;
    }
    cta.href = `/downloads/${app.file}`;
    cta.setAttribute("download", app.file);
    if (meta) {
      const rows = meta.querySelectorAll("[data-dl-value]");
      const values = [
        app.version_name ?? "1.0",
        app.sha256.slice(0, 8),
        day(app.built_at),
        `${mb(app.size_bytes)} م.ب`,
      ];
      rows.forEach((el, i) => { if (values[i]) el.textContent = values[i]; });
    }
  }

  // **iOS: شارةٌ معطَّلةٌ حتى يُملأ الرابط** — ولا زرَّ يفتح لا شيء.
  const ios = $("[data-ios-cta]");
  if (ios && site?.ios_url) {
    const a = document.createElement("a");
    a.href = site.ios_url;
    a.rel = "noopener";
    a.textContent = "نزّل من App Store";
    a.style.cssText = "display:inline-flex;align-items:center;min-height:44px;color:#e6edf3";
    ios.replaceWith(a);
  }
}

/* ═══════════════════ سطرُ العرض — بلا رقم ═════════════════════════════ */
//
// **قرارُ المالك ٢٠٢٦-٠٩-٠٥**: «اعرضه بلا رقم — الشهر الأول مجاناً فقط».
// والبابُ نفسُه لم يعد يُخرج سعراً، **فالمنعُ في الطرفين لا في الرسم وحدَه**.

async function offer() {
  const slot = $("[data-offer]");
  if (!slot) return;
  try {
    const res = await fetch("/api/landing?country_code=JO", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    if (!data?.offer) return; // **لا سطر** — وهو المطلوب
    slot.textContent = data.offer.name;
    slot.removeAttribute("hidden");
  } catch { /* صامت */ }
}

/* ═══════════════════ الحركة — منقولةٌ من التصميم ═══════════════════════ */

class Motion {
  constructor() {
    this.root = $("#taxo-root");
    this.svg = $("#taxo-route");
    this.track = $("#taxo-track");
    this.drawn = $("#taxo-drawn");
    this.car = $("#taxo-car");
    this.body = $("#taxo-car-body");
    this.progress = $("#taxo-progress");
    this.women = $("#taxo-women");
    this.womenBadge = $("#taxo-women-badge");
    this.womenPhone = $("#taxo-women-phone");
    this.womenDots = $$("#taxo-women-list span");
    this.ctaBar = $("#taxo-cta-bar");
    this.download = $("#download");
    this.phones = $$("[data-phone]");
    this.story = $("#taxo-story");
    this.storyFill = $("#taxo-story-fill");
    this.storyCar = $("#taxo-story-car");
    this.storyLine = $("#taxo-story-line");
    if (!this.root) return;

    this.build();
    this.ro = new ResizeObserver(() => this.build());
    this.ro.observe(this.root);
    this._onScroll = () => {
      if (!this._raf) this._raf = requestAnimationFrame(() => { this._raf = 0; this.update(); });
    };
    window.addEventListener("scroll", this._onScroll, { passive: true });
    // **إعادتان بعد استقرار الخطوط والصور** — من التصميم، وتبقيان.
    setTimeout(() => this.build(), 900);
    setTimeout(() => this.build(), 2200);

    if (!reduced) { this.setupReveal(); this.setupTilt(); }
    this.setupStory();
    this.setupAccordions();
    this.startSlides();
  }

  setupReveal() {
    const items = $$("[data-reveal]", this.root);
    items.forEach((el) => {
      el.style.opacity = "0";
      el.style.transform = "translateY(16px)";
      el.style.transition = "opacity .45s ease-out, transform .45s ease-out";
    });
    // **طولُ المسار يُقرأ عند ظهور الأيقونة لا عند الإقلاع** (قِيس ٢٠٢٦-٠٩-٠٥).
    //
    // `getTotalLength()` **يفرض تخطيطاً** لكلِّ مسار، وفي الصفحة عشراتُ
    // المسارات — فقراءتُها جميعاً في الإقلاع تُثقِل الخيطَ الرئيس، **وهو
    // `TBT` في قياس Lighthouse**.
    //
    // **ولا يتغيّر شكلُ الحركة بحرف**: الطولُ يُكتب **قبل أن تُطلق** الرسمةُ
    // مباشرةً، فالنتيجةُ المرئيةُ هي هي — **وما تغيّر متى يُحسب لا كم**.
    // **ولا يُستعمل ثابتُ ٩٠ الاحتياطيّ**: مسارٌ أطولُ منه يبدو مرسوماً نصفَه.
    const prime = (node) => {
      node.querySelectorAll("[data-draw] path, [data-draw] circle, [data-draw] rect")
        .forEach((p) => {
          if (p.dataset.primed) return;
          p.dataset.primed = "1";
          const L = p.getTotalLength ? p.getTotalLength() : 90;
          p.style.strokeDasharray = L;
          p.style.strokeDashoffset = L;
          p.style.transition = "stroke-dashoffset .7s ease-out";
        });
    };
    this._prime = prime;
    const waves = $$("[data-wave]", this.root);

    this.io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        const el = en.target;
        this.io.unobserve(el);
        if (el.hasAttribute("data-reveal")) {
          const sibs = [...(el.parentElement ? el.parentElement.children : [])]
            .filter((n) => n.hasAttribute && n.hasAttribute("data-reveal"));
          const i = Math.max(0, sibs.indexOf(el));
          setTimeout(() => {
            el.style.opacity = "1";
            el.style.transform = "translateY(0)";
          }, Math.min(i, 8) * 70);
          // **يُقاس الطولُ الآن ثمّ تُطلق الرسمة** — إطارٌ واحدٌ بينهما كي
          // يلتقط المتصفّحُ قيمةَ البداية، **وبغيره تقفز الرسمةُ بلا حركة**.
          this._prime(el);
          requestAnimationFrame(() => {
            el.querySelectorAll("[data-draw] path, [data-draw] circle, [data-draw] rect")
              .forEach((p, j) => setTimeout(() => { p.style.strokeDashoffset = "0"; }, 180 + j * 110));
          });
        }
        if (el.hasAttribute("data-wave")) el.style.animation = "txWave .9s ease-out 1";
        if (el.id === "taxo-commission") this.countCommission();
      });
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.15 });

    items.forEach((el) => this.io.observe(el));
    waves.forEach((el) => this.io.observe(el));
    const com = $("#taxo-commission");
    if (com) this.io.observe(com);
  }

  /** العدّادُ يهبط إلى **النسبة الفعّالة** لا إلى صفرٍ مفترض.
   *
   * **والفرقُ ليس تجميلاً**: الصفحةُ تَعِد بما تقوله القاعدة، **ورقمٌ مكتوبٌ
   * في صفحةٍ يخالف إعدادَ العمولة يَعِد بما لا يقع**.
   */
  countCommission() {
    const el = $("#taxo-commission");
    if (!el || el.dataset.done) return;
    el.dataset.done = "1";
    const target = Number(el.dataset.target ?? "0");
    const from = 25;
    if (reduced) { el.textContent = String(target); return; }
    const t0 = performance.now(), dur = 900;
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      el.textContent = String(Math.round(from - (from - target) * e));
      if (k < 1) requestAnimationFrame(step);
      else { el.textContent = String(target); el.style.animation = "txGlowOnce 1.1s ease-out 1"; }
    };
    el.textContent = String(from);
    requestAnimationFrame(step);
  }

  setupTilt() {
    $$("[data-tilt]", this.root).forEach((el) => {
      el.addEventListener("pointermove", (ev) => {
        const r = el.getBoundingClientRect();
        const rx = ((ev.clientY - r.top) / r.height - 0.5) * -4;
        const ry = ((ev.clientX - r.left) / r.width - 0.5) * 4;
        el.style.transform = `perspective(700px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`;
      });
      el.addEventListener("pointerleave", () => { el.style.transform = "translateY(0)"; });
    });
  }

  setupStory() {
    if (!this.story || !this.storyLine) return;
    this._onStory = () => {
      const max = this.story.scrollWidth - this.story.clientWidth;
      const k = max > 4 ? Math.min(1, Math.abs(this.story.scrollLeft) / max) : 0;
      const w = this.storyLine.clientWidth;
      this.storyFill.style.width = k * w + "px";
      this.storyCar.style.translate = -k * (w - 20) + "px 0";
    };
    this.story.addEventListener("scroll", this._onStory, { passive: true });
    this._onStory();
  }

  setupAccordions() {
    $$("[data-acc]", this.root).forEach((d) => {
      const body = d.querySelector("[data-acc-body]");
      const bar = d.querySelector("[data-acc-bar]");
      const sum = d.querySelector("summary");
      if (!body || !sum) return;
      body.style.height = "0px";
      body.style.transition = reduced ? "none" : "height .34s ease-out";
      sum.addEventListener("click", (ev) => {
        ev.preventDefault();
        const open = d.hasAttribute("open");
        if (open) {
          body.style.height = body.scrollHeight + "px";
          requestAnimationFrame(() => { body.style.height = "0px"; });
          if (bar) bar.style.opacity = "1";
          setTimeout(() => d.removeAttribute("open"), reduced ? 0 : 340);
        } else {
          d.setAttribute("open", "");
          body.style.height = "0px";
          requestAnimationFrame(() => { body.style.height = body.scrollHeight + "px"; });
          if (bar) bar.style.opacity = "0";
        }
      });
    });
  }

  startSlides() {
    this.slides = $$("[data-slide]", this.root);
    if (this.slides.length < 2 || reduced) return;
    let i = 0;
    this._slides = setInterval(() => {
      this.slides[i].style.opacity = "0";
      i = (i + 1) % this.slides.length;
      this.slides[i].style.opacity = "1";
    }, 3000);
  }

  build() {
    const root = this.root;
    if (!root || !this.drawn) return;
    const rr = root.getBoundingClientRect();
    const ox = rr.left, oy = rr.top;
    const pts = $$("[data-pin]", root).map((el) => {
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2 - ox, y: r.top + r.height / 2 - oy, el, color: el.dataset.color || "#e6edf3" };
    });
    if (pts.length < 2) return;
    let d = `M${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i];
      const ym = (a.y + b.y) / 2;
      d += ` C${a.x} ${ym} ${b.x} ${ym} ${b.x} ${b.y}`;
    }
    this.svg.setAttribute("width", root.clientWidth);
    this.svg.setAttribute("height", root.scrollHeight);
    this.track.setAttribute("d", d);
    this.drawn.setAttribute("d", d);
    this.len = this.drawn.getTotalLength();
    this.pts = pts;
    this.drawn.style.strokeDasharray = this.len;
    const s = root.clientWidth >= 1024 ? 1.25 : 0.9;
    this.body.setAttribute("transform", `scale(${s})`);
    this.update();
  }

  update() {
    if (!this.len) return;
    const sy = window.scrollY, vh = window.innerHeight;
    const rootTop = this.root.getBoundingClientRect().top + sy;
    const docH = Math.max(1, document.documentElement.scrollHeight - vh);
    this.progress.style.transform = `scaleX(${Math.min(1, sy / docH)})`;
    const y0 = this.pts[0].y, y1 = this.pts[this.pts.length - 1].y;
    let ty = sy + vh * 0.58 - rootTop;
    ty = Math.max(y0, Math.min(y1, ty));

    if (reduced) {
      this.drawn.style.strokeDashoffset = 0;
      const p0 = this.pts[0];
      this.car.setAttribute("transform", `translate(${p0.x} ${p0.y})`);
      this.pts.forEach((pt) => this.light(pt, true));
    } else {
      let lo = 0, hi = this.len;
      for (let i = 0; i < 24; i++) {
        const m = (lo + hi) / 2;
        if (this.drawn.getPointAtLength(m).y < ty) lo = m; else hi = m;
      }
      const L = lo;
      const p = this.drawn.getPointAtLength(L);
      const q = this.drawn.getPointAtLength(Math.min(this.len, L + 3));
      const ang = (Math.atan2(q.y - p.y, q.x - p.x) * 180) / Math.PI - 90;
      this.car.setAttribute("transform", `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)}) rotate(${ang.toFixed(1)})`);
      this.drawn.style.strokeDashoffset = this.len - L;
      this.pts.forEach((pt) => this.light(pt, pt.y <= p.y + 4));
      this.phones.forEach((ph, i) => { ph.style.translate = `0 ${(-sy * (i ? 0.12 : 0.07)).toFixed(1)}px`; });
    }

    if (this.women) {
      const wr = this.women.getBoundingClientRect();
      const t = Math.max(0, Math.min(1, 1 - Math.abs(wr.top + wr.height / 2 - vh / 2) / (vh * 0.8)));
      const k = Math.round(t * 100) / 100;
      if (k !== this._wk) {
        this._wk = k;
        this.women.style.background = `color-mix(in oklab, #14181d ${k * 100}%, #f2f0eb)`;
        const dark = k > 0.5;
        this.women.style.color = dark ? "#e6edf3" : "#171b20";
        if (this.womenBadge) {
          this.womenBadge.style.color = dark ? "#ff6fae" : "#d81b73";
          this.womenBadge.style.background = dark ? "#2a1a22" : "#fdeaf2";
          this.womenBadge.style.borderColor = dark ? "#4d2b39" : "#f2b7d1";
        }
        this.womenDots.forEach((s) => { s.style.background = dark ? "#ff6fae" : "#d81b73"; });
        if (this.womenPhone) {
          this.womenPhone.style.boxShadow = dark
            ? "0 0 0 7px #4d2b39,0 0 0 9px #ff6fae,0 24px 54px rgba(255,111,174,.22)"
            : "0 0 0 7px #24262a,0 0 0 9px #3a3d42,0 24px 54px rgba(23,27,32,.24)";
        }
      }
    }

    if (this.ctaBar && this.download) {
      const past = sy > vh * 0.85;
      const atDl = this.download.getBoundingClientRect().top < vh * 0.9;
      const show = past && !atDl;
      if (show !== this._cta) {
        this._cta = show;
        this.ctaBar.style.transform = show ? "translateY(0)" : "translateY(120%)";
      }
    }
  }

  light(pt, on) {
    if (pt.lit === on) return;
    pt.lit = on;
    if (pt.el.dataset.pin === "hero") return;
    const c = pt.color;
    const off = pt.el.dataset.pin === "women" || pt.el.dataset.pin === "dest" ? "transparent" : "#f2f0eb";
    pt.el.style.background = on ? c : off;
    pt.el.style.boxShadow = on ? `0 0 0 6px ${c}33, 0 0 22px ${c}99` : "none";
    const inner = pt.el.firstElementChild;
    if (inner) inner.style.background = on ? (pt.el.dataset.pin === "dest" ? "#0d1014" : "#f2f0eb") : c;
  }
}

/* ═══════════════════ الإقلاع ═══════════════════════════════════════════ */

(async function boot() {
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

    // **الشريطُ الإعلانيّ** — ثلاثةُ حقولٍ: نصٌّ ورابطٌ ومفتاح.
    const bar = $("[data-announce]");
    if (bar) {
      if (site.announce_enabled && site.announce_text) {
        $("[data-announce-text]", bar).textContent = site.announce_text;
        const link = $("a", bar);
        if (link) {
          if (site.announce_url) link.href = site.announce_url;
          else link.removeAttribute("href");
        }
        bar.removeAttribute("hidden");
      } else bar.remove();
    }

    // **أيقونةٌ لما له رابطٌ فقط** — ولا أيقونةَ معطَّلةٌ محجوزة.
    for (const net of ["facebook", "instagram", "tiktok", "x", "whatsapp"]) {
      const el = $(`[data-social="${net}"]`);
      if (!el) continue;
      const url = site[`social_${net}`];
      if (url) { el.href = url; el.removeAttribute("hidden"); } else el.remove();
    }

    // **السياساتُ خلف مفتاحها** — ولا تُعرض على مستخدمٍ قبل المراجعة.
    if (!site.policies_public) $$("[data-policy-link]").forEach((el) => el.remove());

    applyHidden(site.hidden_sections, "data-section");
    applyHidden(site.hidden_cards, "data-card");

    // **بطاقةٌ لمفتاحٍ مطفأٍ تُرسم «قريباً»** — ولا تختفي بلا أثر.
    $$("[data-feature]").forEach((el) => {
      const key = el.dataset.feature;
      if (site.features && site.features[key] === false) markSoon(el);
    });

    // **العمولةُ من الباب** — والعدّادُ يهبط إليها لا إلى رقمٍ مكتوب.
    const com = $("#taxo-commission");
    if (com && site.commission_percent !== undefined) {
      const pct = Math.round(Number(site.commission_percent));
      com.dataset.target = String(pct);
      if (!com.dataset.done) com.textContent = String(pct);
    }

    // **الأسئلةُ من اللوحة حين تُكتب** — والمخبوزةُ حتى ذلك.
    if (Array.isArray(site.faq) && site.faq.length) {
      const host = $("[data-faq]");
      if (host) {
        const tpl = host.firstElementChild;
        if (tpl) {
          const items = [...site.faq].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
          const built = items.map((row) => {
            const node = tpl.cloneNode(true);
            const q = node.querySelector("summary span, summary");
            const a = node.querySelector("[data-acc-body] p, [data-acc-body]");
            if (q) q.textContent = row.q ?? "";
            if (a) a.textContent = row.a ?? "";
            return node;
          });
          if (built.length) { host.replaceChildren(...built); }
        }
      }
    }
  }

  await download(site);
  await offer();

  // **جُرّب تأجيلُ الحركة إلى `requestIdleCallback` فساءت النتيجة** (قِيس
  // ٢٠٢٦-٠٩-٠٥): `TBT` ٦٥٠ → ١٤٠٠ و`Speed Index` ٢٫٥ → ٦٫٢ — **الخمولُ يقع
  // داخل نافذة القياس فيصير مهمّةً واحدةً طويلةً بدل مهامَّ موزّعة**.
  // **فأُعيدت كما رسمها التصميم**، والفكرةُ تُقيَّد مسقَطةً لا تُعاد.
  new Motion();
})();
