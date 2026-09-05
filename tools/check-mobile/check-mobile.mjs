/** **حارسُ الهاتف** — يفتح مسارات اللوحة على أربعة مقاسات **ويقيس بالعناصر**.
 *
 *     cd tools/capture-screens && node ../check-mobile/check-mobile.mjs
 *
 * **ولمَ بالعناصر لا بالنظر** (شرطُ المالك ٢٠٢٦-٠٩-٠٥): «رأيتُه بعيني على
 * جهازي» **وصفٌ لا قياس** — لا يقول أيَّ عنصرٍ ولا كم بكسلاً، **ولا يُعرف
 * بعد الإصلاح أزال أم بقي**. وأربعةُ أسئلةٍ لها جوابٌ رقميّ:
 *
 * **١) `scrollWidth > clientWidth`** — الصفحةُ تمرّ أفقياً، والعربيةُ RTL
 *     فالفائضُ يخرج **يساراً** ولا يُرى بالتمرير المعتاد.
 * **٢) عنصرٌ خارج إطار الشاشة** — `rect.left < 0` أو `rect.right > innerWidth`
 *     بأكثرَ من بكسل. **وهو ما يجعل زرَّين لا يُضغطان أصلاً.**
 * **٣) مساحةُ لمسٍ دون ٤٤** — لكلِّ `button`/`a`/`input` مرئيّ.
 * **٤) تقاطعُ عنصرين تفاعليّين** — مستطيلان يتداخلان بأكثر من ٤ بكسل.
 * **٥) محتوىً تحت شريطٍ ثابت** — آخرُ ما في الصفحة يقع تحت `fixed`/`sticky`.
 * **٦) ولوحةُ المفاتيح** — تُحاكى بقصِّ الارتفاع ٣٠٠px بعد تركيز حقلٍ،
 *     **فما يقفز عند فتحها يقفز هنا**. والمتصفّحُ الآليُّ لا يفتح لوحةً
 *     حقيقية، **وأثرُها على التخطيط هو القصُّ بعينه**.
 *
 * ## وقياسُه في الاتجاهين شرطٌ قبل تصديقه
 *
 * **يُشغَّل على الشجرة السليمة فيصمت، وعلى عطبٍ مزروعٍ فيصيح** —
 * `--negate` يحقن نمطاً يعيد العطبَ المقيس (زرٌّ `34px` وترويسةٌ لا تلتفّ)
 * **ويسقط الحارسُ إن لم يصح**. فبابٌ يصمت دائماً ليس باباً.
 */

import { chromium } from "playwright";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = process.env.TAXO_ROOT ?? join(HERE, "..", "..");
const BASE = process.env.ADMIN_BASE ?? "http://localhost:5175";
const API = process.env.TAXO_API ?? "https://dev-api.tajora.ly/api/v1";
const NEGATE = process.argv.includes("--negate");

//: **و`panel` لا `admin`**: `ClientApp` ثلاثةٌ — راكبٌ وكبتنٌ ولوحة، **والدورُ
//: شيءٌ والتطبيقُ الطالبُ شيءٌ آخر**. وقيمةٌ خارجَها تعود بـ422 لا برفضِ دخول.
const ADMIN = { phone: "+962790000000", password: "TaxoTest123", app: "panel" };
const KEYS = ["taxo.admin.access_token", "taxo.admin.refresh_token"];

//: **الأربعةُ التي سمّاها المالك** — و`DPR` لا يغيّر تخطيطَ CSS، **لكنه يغيّر
//: ما يقرّره المتصفّحُ من نقرٍ ولمس**، فيُثبَّت عند ٣ ومعه `hasTouch`.
const SIZES = [
  { w: 360, h: 640 },
  { w: 390, h: 844 },
  { w: 412, h: 915 },
  { w: 360, h: 800 },
];

//: **مساراتُ الهاتف** — ما يفتحه مشرفٌ من جيبه، لا كلُّ شاشةٍ في اللوحة.
const ROUTES = [
  "/overview",
  "/rides",
  "/drivers",
  "/finance",
  "/payments",
  "/disputes",
  "/m/payments",
  "/users",
  "/settings",
  "/site",
];

const TOUCH = "button, a[href], input, select, textarea, [role=button], [role=radio], [role=switch]";

//: **نمطُ العطب المزروع** — يعيد ما قِيس بالضبط: ترويسةٌ لا تلتفّ وأزرارٌ ٣٤.
const POISON = `
  header > div:first-child { flex-wrap: nowrap !important; }
  header button[aria-label="تبديل المظهر"],
  header button[aria-label="خروج"] { width: 34px !important; height: 34px !important; min-width: 34px !important; }
`;

async function login() {
  const cache = join(HERE, ".admin-token.json");
  const probe = async (t) =>
    (await fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${t.access_token}` } })).ok;
  if (existsSync(cache)) {
    try {
      const t = JSON.parse(readFileSync(cache, "utf8"));
      if (await probe(t)) return t;
    } catch {
      /* ذاكرةٌ تالفة — يُعاد الدخول */
    }
  }
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ADMIN),
  });
  if (!res.ok) throw new Error(`دخولُ المشرف: HTTP ${res.status}`);
  const body = await res.json();
  if (!body.tokens) throw new Error("دخولُ المشرف: لا توكن");
  writeFileSync(cache, JSON.stringify(body.tokens), "utf8");
  return body.tokens;
}

/** **الحزمةُ المخدومةُ تطابق `dist`** — الشرطُ الأوّل، كما في حارس الالتقاط. */
async function assertBundle() {
  const dist = join(ROOT, "admin-panel/dist/index.html");
  if (!existsSync(dist)) throw new Error("admin-panel/dist غيرُ مبنيّ — **لا مرجع**");
  const re = /\/assets\/index-[A-Za-z0-9_-]+\.js/;
  const want = (readFileSync(dist, "utf8").match(re) ?? [])[0];
  const found = ((await (await fetch(`${BASE}/`)).text()).match(re) ?? [])[0] ?? "<لا حزمة>";
  if (found !== want) throw new Error(`${BASE} يخدم ${found} لا ${want} — **ليست لوحتَنا**`);
  return want;
}

/** القياسُ كلُّه داخل الصفحة — **رقمٌ لكلِّ دعوى**. */
const MEASURE = (touchSel) => {
  const de = document.documentElement;
  const W = window.innerWidth;
  const out = { overflow: null, offscreen: [], small: [], overlap: [], underBar: [], inTable: 0 };

  if (de.scrollWidth > de.clientWidth + 1) {
    out.overflow = { scrollWidth: de.scrollWidth, clientWidth: de.clientWidth };
  }

  const name = (el) => {
    const id = el.getAttribute("aria-label") || el.textContent?.trim().slice(0, 24) || "";
    return `${el.tagName.toLowerCase()}${el.className ? "." + String(el.className).split(/\s+/)[0] : ""}${id ? ` «${id}»` : ""}`;
  };
  // **وحاويةٌ تمرّ أفقياً ليست عطباً، هي العلاج**: جدولٌ عريضٌ داخل
  // `overflow-x:auto` **يُمرَّر داخل صندوقه ولا يدفع الصفحة**. وأوّلُ تشغيلٍ
  // بلا هذا الاستثناء بلّغ عن أربعة عناوينَ في مصفوفة الصلاحيات **وهي
  // سليمةٌ بالبنية** — **وحارسٌ يخترع عطباً أغلى من واحدٍ يفوته**، لأنه
  // يُطفأ فيسقط معه ما يمسكه حقاً.
  const scrolled = (el) => {
    for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) {
      const ox = getComputedStyle(n).overflowX;
      if (ox === "auto" || ox === "scroll") return n;
    }
    return null;
  };

  const seen = (el) => {
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden" || Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  // ── ١) أيُّ عنصرٍ يخرج عن إطار العرض ─────────────────────────────────
  for (const el of document.querySelectorAll("body *")) {
    if (!seen(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width > W + 1) continue; // أوسعُ من الشاشة: يُبلَّغ عنه بالفائض لا هنا
    const over = Math.max(0, -r.left, r.right - W);
    if (over > 1 && el.children.length === 0 && !scrolled(el)) {
      out.offscreen.push({ el: name(el), over: Math.round(over), left: Math.round(r.left) });
    }
  }

  // ── ٢) مساحاتُ اللمس ─────────────────────────────────────────────────
  const touch = [...document.querySelectorAll(touchSel)].filter(seen);
  for (const el of touch) {
    const r = el.getBoundingClientRect();
    if (r.width >= 44 && r.height >= 44) continue;
    // **خليةُ جدولٍ ليست زرَّ قشرة**: مصفوفةُ صلاحياتٍ ٥٢rem فيها عشراتُ
    // الخلايا، **ورفعُ كلِّ خليةٍ إلى ٤٤ إعادةُ تصميمٍ لا إصلاحُ تخطيط**.
    // **فتُعدّ وتُقال ولا تُسقط** — والرقمُ يبقى مرئياً كي لا يصير الصمتُ
    // عُرفاً، **والحدُّ مكتوبٌ في الحارس لا مسكوتٌ عنه**.
    if (scrolled(el)) {
      out.inTable++;
      continue;
    }
    out.small.push({ el: name(el), w: Math.round(r.width), h: Math.round(r.height) });
  }

  // ── ٣) تقاطعُ اثنين تفاعليّين ────────────────────────────────────────
  for (let i = 0; i < touch.length; i++) {
    for (let j = i + 1; j < touch.length; j++) {
      if (touch[i].contains(touch[j]) || touch[j].contains(touch[i])) continue;
      const a = touch[i].getBoundingClientRect();
      const b = touch[j].getBoundingClientRect();
      const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ox > 4 && oy > 4) {
        out.overlap.push({ a: name(touch[i]), b: name(touch[j]), x: Math.round(ox), y: Math.round(oy) });
      }
    }
  }

  // ── ٤) محتوىً تحت شريطٍ ثابتٍ في الأسفل ──────────────────────────────
  const bars = [...document.querySelectorAll("body *")].filter((el) => {
    const s = getComputedStyle(el);
    return (s.position === "fixed" || s.position === "sticky") && seen(el);
  });
  const bottomBars = bars.filter((el) => el.getBoundingClientRect().bottom > innerHeight - 8);
  if (bottomBars.length) {
    const top = Math.min(...bottomBars.map((el) => el.getBoundingClientRect().top));
    window.scrollTo(0, de.scrollHeight);
    for (const el of touch) {
      const r = el.getBoundingClientRect();
      if (r.top < top && r.bottom > top + 4 && !bottomBars.some((b) => b.contains(el))) {
        out.underBar.push({ el: name(el), bottom: Math.round(r.bottom), bar: Math.round(top) });
      }
    }
    window.scrollTo(0, 0);
  }

  return out;
};

const browser = await chromium.launch({
  channel: "chrome",
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});

const lines = [];
let findings = 0;
try {
  const bundle = await assertBundle();
  lines.push(`  ✓ ${BASE} = admin-panel/dist → ${bundle.slice(15)}${NEGATE ? "   ⚠ عطبٌ مزروع" : ""}`);
  const tokens = await login();

  for (const size of SIZES) {
    const context = await browser.newContext({
      viewport: { width: size.w, height: size.h },
      deviceScaleFactor: 3,
      isMobile: true,
      hasTouch: true,
      locale: "ar",
    });
    await context.addInitScript(
      ([ak, rk, at, rt]) => {
        localStorage.setItem(ak, at);
        localStorage.setItem(rk, rt);
      },
      [KEYS[0], KEYS[1], tokens.access_token, tokens.refresh_token],
    );
    const page = await context.newPage();
    for (const route of ROUTES) {
      await page.goto(BASE + route, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(1400);
      if (NEGATE) await page.addStyleTag({ content: POISON });
      let r;
      try {
        r = await page.evaluate(MEASURE, TOUCH);
      } catch (err) {
        lines.push(`  ✗ ${size.w}×${size.h} ${route}: ${err.message.slice(0, 70)}`);
        findings++;
        continue;
      }
      const bad0 = [];
      const bad = bad0;
      if (r.overflow) bad.push(`تمريرٌ أفقيّ ${r.overflow.scrollWidth}>${r.overflow.clientWidth}`);
      for (const x of r.offscreen.slice(0, 4)) bad.push(`خارجَ الإطار ${x.over}px: ${x.el}`);
      for (const x of r.small.slice(0, 4)) bad.push(`لمسٌ ${x.w}×${x.h}: ${x.el}`);
      for (const x of r.overlap.slice(0, 3)) bad.push(`تقاطعٌ ${x.x}×${x.y}: ${x.a} ∩ ${x.b}`);
      for (const x of r.underBar.slice(0, 3)) bad.push(`تحت شريطٍ ثابت: ${x.el}`);
      const extra =
        r.offscreen.length + r.small.length + r.overlap.length + r.underBar.length - bad.length + (r.overflow ? 1 : 0);
      // ── ولوحةُ المفاتيح: يُركَّز حقلٌ ثمّ يُقصّ الارتفاع ────────────
      const hasField = await page.$("input:not([type=hidden]), textarea");
      if (hasField) {
        await hasField.focus().catch(() => undefined);
        await page.setViewportSize({ width: size.w, height: Math.max(320, size.h - 300) });
        await page.waitForTimeout(400);
        const k = await page.evaluate(MEASURE, TOUCH);
        await page.setViewportSize({ width: size.w, height: size.h });
        await page.waitForTimeout(300);
        if (k.overflow) {
          bad0.push(`لوحةُ المفاتيح: تمريرٌ أفقيّ ${k.overflow.scrollWidth}>${k.overflow.clientWidth}`);
        }
        for (const x of k.underBar.slice(0, 2)) {
          bad0.push(`لوحةُ المفاتيح: تحت شريطٍ ثابت — ${x.el}`);
        }
      }

      const note = r.inTable ? `   (و${r.inTable} خليةَ جدولٍ يُمرَّر دون ٤٤ — تُعدّ ولا تُسقط)` : "";
      if (bad.length) {
        findings += bad.length;
        lines.push(`  ✗ ${size.w}×${size.h} ${route}${note}`);
        for (const b of bad) lines.push(`      · ${b}`);
        if (extra > 0) lines.push(`      · (و${extra} غيرُها)`);
      } else {
        lines.push(`  ✓ ${size.w}×${size.h} ${route}${note}`);
      }
    }
    await context.close();
  }
} catch (err) {
  lines.push(`  ✗ ${err.message}`);
  findings++;
}
await browser.close();

console.log(lines.join("\n"));
writeFileSync(join(HERE, "_last.txt"), lines.join("\n"), "utf8");

if (NEGATE) {
  //: **البابُ يُقاس في الاتجاه الآخر**: عطبٌ مزروعٌ ولم يصح الحارسُ = الحارسُ
  //: أعمى، **وخُضرتُه على الشجرة السليمة لا تعني شيئاً**.
  if (findings === 0) {
    console.log("\n  ✗ **عطبٌ مزروعٌ ولم يُمسك — الحارسُ أعمى، ولا تُصدَّق خُضرتُه**");
    process.exit(1);
  }
  console.log(`\n  ✓ العطبُ المزروعُ أُمسك في ${findings} موضعاً — **الحارسُ يرى**`);
  process.exit(0);
}

console.log(`\n  ${findings === 0 ? "✓ لا عطبَ على المقاسات الأربعة" : `✗ ${findings} بلاغاً`}`);
process.exit(findings === 0 ? 0 : 1);
