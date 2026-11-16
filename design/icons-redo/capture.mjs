/** **لوحةُ الاتّجاهات الأربعة وتسجيلاتُها — على شاشات الراكب الحقيقيّة** (أمرُ المالك ٢٠٢٦-١١-١٦).
 *
 *     node design/icons-redo/capture.mjs <مجلّدُ الإخراج>      (من ويندوز؛ Playwright من حزمة video-studio)
 *
 * يفتح تطبيقَ الراكب المحلّيَّ (`127.0.0.1:5173`، الخلفيّةُ `8001`) بحساب البذرة، **ويحقن أيقوناتِ الاتّجاه مكانَ أيقوناتِ الشاشة بأسمائها**
 * — فالورقةُ والشريطُ والبحثُ هي هي حرفاً، والأيقونةُ وحدَها تتغيّر. **لا شيءَ يُكتب في التطبيق ولا في القاعدة**، و`icons_v2` لا يُمسّ.
 * والشاشاتُ الثلاث: الرئيسيّة (الجرس والشريط السفليّ)، و«إلى أين؟» (البحث والدبّوس)، **وورقةُ الطلب** (الفئتان والمحفظة).
 */
import { createRequire } from "module";
import { pathToFileURL, fileURLToPath } from "url";
import fs from "fs";
import path from "path";

const require = createRequire("C:/Users/loly3/.claude/skills/video-studio/package.json");
const { chromium } = require("playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const S = await import(pathToFileURL(path.join(HERE, "styles.mjs")).href + "?t=" + Date.now());

const OUT = process.argv[2];
const ONLY = process.argv[3]; // "board" | "video" | undefined
fs.mkdirSync(OUT, { recursive: true });
const APP = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8001/api/v1";

const r = await fetch(API + "/auth/login", {
  method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ phone: "+962790000021", password: "TaxoTest123", app: "rider" }),
});
const tok = (await r.json()).tokens;
if (!tok) throw new Error("لا توكن للراكب");

/** خريطةُ (اسمُ Material ⇐ SVG) لكلِّ أسلوبٍ ومظهر — تُحسب هنا وتُحقن نصّاً */
function svgMap(style, dark) {
  const m = {};
  for (const [mat, n] of Object.entries(S.APP_NAME)) m[mat] = S.render(style, n, { dark, cut: dark ? "#171a1f" : "#ffffff" });
  return m;
}

/** الحاقن — يستبدل كلَّ `.t2-icon` باسمٍ معروف، ويبقى يراقب لأن الشاشةَ تتبدّل */
const INJECT = ([map, css]) => {
  const st = document.createElement("style");
  st.textContent = css + `.ixw{display:inline-flex;width:1.25em;height:1.25em;vertical-align:middle}.ixw svg{width:100%;height:100%;overflow:visible}`;
  const addStyle = () => { if (!st.isConnected) (document.head || document.documentElement).appendChild(st); };
  let n = 0;
  const swap = () => {
    if (document.documentElement) addStyle();
    for (const el of document.querySelectorAll("span.t2-icon:not([data-ix])")) {
      const name = el.textContent.trim();
      if (!map[name]) continue;
      el.setAttribute("data-ix", "1");
      const u = "u" + ++n + "_";
      el.innerHTML = `<span class="ixw">${map[name].replace(/i[ABCD]\d+_/g, u)}</span>`;
      el.style.fontSize = getComputedStyle(el).fontSize;
      el.style.color = "inherit";
    }
  };
  new MutationObserver(swap).observe(document, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", swap);
};

async function openApp(browser, { style, dark, video }) {
  const ctx = await browser.newContext({
    viewport: { width: 412, height: 860 }, deviceScaleFactor: video ? 1 : 2, locale: "ar",
    colorScheme: dark ? "dark" : "light",
    geolocation: { latitude: 31.9539, longitude: 35.9106 }, permissions: ["geolocation"],
    ...(video ? { recordVideo: { dir: video, size: { width: 412, height: 860 } } } : {}),
  });
  await ctx.addInitScript(([at, rt]) => {
    localStorage.setItem("taxo.access_token", at); localStorage.setItem("taxo.refresh_token", rt);
    localStorage.setItem("taxo.onboarded", "1"); localStorage.setItem("taxo.welcome.seen", "1"); localStorage.setItem("taxo.brand.notice", "1");
  }, [tok.access_token, tok.refresh_token]);
  if (style) await ctx.addInitScript(INJECT, [svgMap(style, dark), S.MOTION_CSS]);
  const page = await ctx.newPage();
  return { ctx, page };
}

/** الشاشاتُ الثلاث بعلاماتها — **علامةٌ لا يملكها إلا المطلوب** (درسُ `capture-screens`) */
async function walk(page, shoot, pause = 1200) {
  await page.goto(APP + "/", { waitUntil: "domcontentloaded" });
  await page.getByText("إلى أين؟").first().waitFor({ timeout: 20000 });
  await page.waitForTimeout(2500);
  await shoot("home");
  await page.getByText("رحلة", { exact: true }).first().click();
  await page.getByText("حدّدها على الخريطة بالدبوس").waitFor({ timeout: 10000 });
  await page.waitForTimeout(pause);
  await shoot("search");
  await page.getByText("شارع العبدلية").first().click();
  await page.getByText("اختر الفئة").waitFor({ timeout: 20000 });
  // **الأسعارُ علامةُ الورقة المكتملة** — لقطةٌ قبلها ورقةٌ نصفُ محمّلة (وقع في أوّل تشغيل)
  await page.getByText("2.500").first().waitFor({ timeout: 20000 });
  await page.waitForTimeout(pause + 800);
  await shoot("sheet");
}

const browser = await chromium.launch();
const shots = {};

if (ONLY !== "video") {
  for (const style of ["A", "B", "C", "D"]) {
    for (const dark of [false, true]) {
      const { ctx, page } = await openApp(browser, { style, dark });
      await walk(page, async (k) => {
        const f = path.join(OUT, `${style}-${dark ? "dark" : "light"}-${k}.png`);
        await page.screenshot({ path: f });
        // **التحقّق**: الأيقوناتُ حُقنت فعلاً — وإلا فاللقطةُ لقطةُ الأيقونات القديمة باسم الجديدة
        const injected = await page.locator("[data-ix]").count();
        if (injected < 2) throw new Error(`${style}/${dark}/${k}: لم يُحقن إلا ${injected}`);
        (shots[style] ??= {})[`${dark ? "dark" : "light"}-${k}`] = f;
      });
      await ctx.close();
    }
  }
  fs.writeFileSync(path.join(OUT, "shots.json"), JSON.stringify(shots, null, 1));
  await buildBoard();
}

if (ONLY !== "board") {
  for (const style of ["A", "B", "C", "D"]) await record(style);
}
await browser.close();

/* ── اللوحةُ الواحدة: أربعةُ أعمدةٍ موسومة، في كلٍّ الثماني بالفاتح والداكن، ثمّ الشاشاتُ الثلاث بالفاتح والداكن */
async function buildBoard() {
  const img = (f) => "data:image/png;base64," + fs.readFileSync(f).toString("base64");
  const grid = (style, dark) =>
    `<div class="grid ${dark ? "dk" : "lt"}">${S.SAMPLE.map((n) =>
      `<div class="cell"><div class="ic">${S.render(style, n, { dark, size: 56, cls: S.MOTION[style].icon === n ? "ix-anim" : "" })}</div><div class="lb">${S.SAMPLE_LABEL[n]}</div></div>`).join("")}</div>`;
  const cols = ["A", "B", "C", "D"].map((k) => `
    <section class="col">
      <header><span class="tag">${k}</span><div><h2>${S.STYLES[k].name}</h2><p>${S.STYLES[k].hint}</p></div></header>
      ${grid(k, false)}${grid(k, true)}
      <div class="zooms">${["light", "dark"].map((m) => `<div class="zoom" style="background-image:url(${img(shots[k][m + "-sheet"])});background-position:0 76%"></div><div class="zoom bar" style="background-image:url(${img(shots[k][m + "-home"])});background-position:0 99%"></div>`).join("")}</div>
      <div class="shots">${["sheet", "search", "home"].map((s) => `<img src="${img(shots[k]["light-" + s])}">`).join("")}</div>
      <div class="shots">${["sheet", "search", "home"].map((s) => `<img src="${img(shots[k]["dark-" + s])}">`).join("")}</div>
      <footer>الحركة: ${S.MOTION[k].label}</footer>
    </section>`).join("");
  const html = `<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><style>
    body{margin:0;background:#e9e5dc;font-family:"Segoe UI","Noto Sans Arabic",sans-serif;color:#15171c}
    h1{margin:0;padding:28px 36px 6px;font-size:34px} .sub{padding:0 36px 20px;color:#555;font-size:18px}
    .wrap{display:grid;grid-template-columns:repeat(4,1fr);gap:22px;padding:0 28px 30px}
    .col{background:#fff;border-radius:24px;padding:18px;box-shadow:0 2px 10px #0001}
    header{display:flex;gap:14px;align-items:center;margin-bottom:12px}
    .tag{font-size:44px;font-weight:800;color:#fff;background:#f05a28;width:64px;height:64px;border-radius:18px;display:grid;place-items:center}
    h2{margin:0;font-size:24px} header p{margin:4px 0 0;color:#666;font-size:15px}
    .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;border-radius:16px;padding:12px;margin-bottom:10px}
    .lt{background:#f4f1ea}.dk{background:#0e1013;color:#eee}
    .cell{text-align:center}.ic{height:58px;display:grid;place-items:center}.lb{font-size:13px;margin-top:2px}
    .shots{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:8px}
    .shots img{width:100%;border-radius:12px;border:1px solid #0002}
    .zooms{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px}
    .zoom{height:190px;border-radius:12px;background-size:100% auto;background-repeat:no-repeat;border:1px solid #0002}
    .zoom.bar{height:76px;grid-column:span 1}
    footer{color:#666;font-size:14px;margin-top:4px}
  </style></head><body>
  <h1>TAXO — أربعةُ اتّجاهاتٍ للأيقونات</h1>
  <div class="sub">الثماني بالفاتح والداكن، ثمّ على الشاشات الحقيقيّة: ورقةُ الطلب · «إلى أين؟» · الرئيسيّة والشريطُ السفليّ — النهار فوق، والليل تحت. والأيقوناتُ مطفأةٌ على الإنتاج حتى الاختيار.</div>
  <div class="wrap">${cols}</div></body></html>`;
  const f = path.join(OUT, "board.html");
  fs.writeFileSync(f, html);
  const page = await browser.newPage({ viewport: { width: 2600, height: 1000 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(f).href);
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, "icons-board-ABCD.png"), fullPage: true });
  await page.close();
}

/* ── التسجيلُ لكلِّ اتّجاه: الأيقونةُ المتحرّكةُ كبيرةً بالمظهرين، ثمّ الجولةُ على الشاشات الثلاث نهاراً ثمّ ليلاً */
async function record(style) {
  const vdir = path.join(OUT, "vid-" + style);
  fs.rmSync(vdir, { recursive: true, force: true });
  const parts = [];
  for (const dark of [false, true]) {
    const { ctx, page } = await openApp(browser, { style, dark, video: vdir });
    const m = S.MOTION[style];
    const bg = dark ? "#0e1013" : "#f4f1ea";
    await page.setContent(`<!doctype html><html dir="rtl"><head><meta charset="utf-8"><style>${S.MOTION_CSS}
      body{margin:0;height:100vh;display:grid;place-items:center;background:${bg};color:${dark ? "#eee" : "#15171c"};font-family:"Segoe UI",sans-serif;text-align:center}
      .big{width:220px;height:220px}.big svg{width:100%;height:100%;overflow:visible}.row{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin:30px auto 0;max-width:360px}
      .row svg{width:38px;height:38px}.t{font-size:30px;font-weight:800}.s{font-size:18px;opacity:.7;margin-top:6px}</style></head><body><div>
      <div class="t">${style} — ${S.STYLES[style].name}</div><div class="s">${m.label} · ${dark ? "الوضعُ الداكن" : "الوضعُ الفاتح"}</div>
      <div class="big" style="margin:40px auto 0">${S.render(style, m.icon, { dark, cls: "ix-anim" })}</div>
      <div class="row">${S.SAMPLE.map((n) => S.render(style, n, { dark, cls: n === m.icon ? "ix-anim" : "" })).join("")}</div></div></body></html>`);
    await page.waitForTimeout(3800);
    await walk(page, async () => { await page.waitForTimeout(1600); }, 600);
    const v = page.video();
    await ctx.close();
    parts.push(await v.path());
  }
  fs.writeFileSync(path.join(vdir, "parts.txt"), parts.map((p) => `file '${p.replace(/\\/g, "/")}'`).join("\n"));
}
