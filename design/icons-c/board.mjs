/** **لوحةُ النمط C وتسجيلُها** — القديمُ (Material Symbols الحيُّ اليوم) مقابلَ الجديد، فاتحاً وداكناً، وعلامةُ الخريطة تدور مع الطريق.
 *
 *     node design/icons-c/board.mjs <مجلّدُ الإخراج>      (من ويندوز؛ Playwright من حزمة video-studio)
 *
 * لا يمسّ تطبيقاً ولا قاعدة، و`icons_v2` لا يُمسّ.
 */
import { createRequire } from "module";
import { pathToFileURL, fileURLToPath } from "url";
import fs from "fs";
import path from "path";

const require = createRequire("C:/Users/loly3/.claude/skills/video-studio/package.json");
const { chromium } = require("playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const S = await import(pathToFileURL(path.join(HERE, "set.mjs")).href + "?t=" + Date.now());
const OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });

const FONT = `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cairo:wght@600;800&display=swap">`;
const all = [...Object.keys(S.VEHICLES).map((k) => [k, S.VEHICLES[k]]), ...Object.keys(S.GLYPHS).map((k) => [k, S.GLYPHS[k]])];

function cell(name, parts, dark) {
  const old = `<span class="ms" style="color:${dark ? "#e8e6e3" : "#1f2433"}">${name}</span>`;
  return `<div class="pair"><div class="old">${old}</div><div class="arrow">←</div><div class="new">${S.renderC(parts, { dark, size: 64 })}</div></div>`;
}

function boardHtml() {
  const rows = all.map(([n, parts]) => `<div class="row"><div class="lbl">${S.LABELS[n] ?? n}</div><div class="half light">${cell(n, parts, false)}</div><div class="half dark">${cell(n, parts, true)}</div></div>`);
  const mid = Math.ceil(rows.length / 2);
  return `<!doctype html><html dir="rtl"><head><meta charset="utf-8">${FONT}<style>
  body{margin:0;background:#f4f1ec;font-family:Cairo,sans-serif;color:#1f2433}
  h1{margin:28px 32px 4px;font-size:34px;font-weight:800} p.sub{margin:0 32px 18px;font-size:17px;color:#555}
  .cols{display:flex;gap:24px;padding:0 24px 28px}.col{flex:1}
  .head,.row{display:grid;grid-template-columns:120px 1fr 1fr;align-items:center}
  .head div{font-weight:800;font-size:15px;padding:6px 10px;text-align:center}
  .row{border-top:1px solid #e2ddd5}.lbl{font-weight:600;font-size:16px;padding:0 8px}
  .half{padding:8px 0;display:flex;justify-content:center}.light{background:#fff}.dark{background:#171a1f}
  .pair{display:flex;align-items:center;gap:14px}.arrow{font-size:18px;color:#999}
  .ms{font-family:'Material Symbols Rounded';font-size:40px;line-height:1;width:64px;height:64px;display:flex;align-items:center;justify-content:center;direction:ltr}
  </style></head><body>
  <h1>أيقوناتُ TAXO — النمط C بأشكالٍ جديدة</h1>
  <p class="sub">يميناً القديمُ الحيُّ اليوم، ويساراً الجديد · فاتحٌ وداكن · ${all.length} رسماً أصيلاً · <b>icons_v2 مطفأ</b> حتى توافق</p>
  <div class="cols">${[rows.slice(0, mid), rows.slice(mid)].map((rs) => `<div class="col"><div class="head"><div></div><div>فاتح: قديم ← جديد</div><div>داكن: قديم ← جديد</div></div>${rs.join("")}</div>`).join("")}</div>
  </body></html>`;
}

/** صفحةُ التسجيل: الطريقُ المنحني والسيّارةُ تدور معه (بالقوس الأقصر)، والمركباتُ والأيقوناتُ تتحرّك — فاتحٌ وداكنٌ جنباً إلى جنب */
function motionHtml() {
  const marker = (dark) => S.renderC(S.MARKER, { dark, size: 46 });
  const strip = (dark) => ["local_taxi", "directions_car", "electric_car", "airport_shuttle", "directions_bus", "woman"]
    .map((n, i) => `<div class="veh" style="animation-delay:${i * 0.18}s">${S.renderC(S.VEHICLES[n], { dark, size: 70 })}<span>${S.LABELS[n]}</span></div>`).join("");
  const icons = (dark) => [["location_on", "drop"], ["notifications", "ring"], ["account_balance_wallet", "pop"], ["search", "pop"], ["home", "pop"], ["star", "spin"]]
    .map(([n, a], i) => `<div class="ic ${a}" style="animation-delay:${i * 0.25}s">${S.renderC(S.GLYPHS[n], { dark, size: 54 })}</div>`).join("");
  const panel = (dark) => `<div class="panel ${dark ? "dk" : "lt"}"><div class="ttl">${dark ? "داكن" : "فاتح"}</div>
    <svg class="map" viewBox="0 0 400 300"><rect width="400" height="300" fill="${dark ? "#1d2127" : "#eef0f2"}"/>
      <path d="M0 60H400M0 170H400M90 0V300M300 0V300" stroke="${dark ? "#2a2f37" : "#ffffff"}" stroke-width="14"/>
      <path id="road${+dark}" d="M30 260 C 90 250 110 190 160 170 S 250 190 270 120 S 330 40 380 50" fill="none" stroke="${dark ? "#3a4048" : "#cfd5dc"}" stroke-width="20" stroke-linecap="round"/>
      <path d="M30 260 C 90 250 110 190 160 170 S 250 190 270 120 S 330 40 380 50" fill="none" stroke="${S.ORANGE}" stroke-width="5" stroke-linecap="round" stroke-dasharray="1 0"/>
      <g class="mk" id="mk${+dark}">${marker(dark)}</g></svg>
    <div class="strip">${strip(dark)}</div><div class="icons">${icons(dark)}</div></div>`;
  return `<!doctype html><html dir="rtl"><head><meta charset="utf-8"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cairo:wght@600;800&display=swap"><style>
  body{margin:0;width:1280px;height:720px;display:flex;font-family:Cairo,sans-serif;background:#0e1013}
  .panel{flex:1;padding:18px 22px;display:flex;flex-direction:column;gap:10px}.lt{background:#f6f4f0;color:#1f2433}.dk{background:#171a1f;color:#eee}
  .ttl{font-weight:800;font-size:22px}.map{width:100%;height:330px;border-radius:18px}
  .strip{display:flex;justify-content:space-between}.veh{display:flex;flex-direction:column;align-items:center;font-size:13px;animation:drive 2.4s cubic-bezier(.3,1.3,.5,1) infinite}
  .icons{display:flex;justify-content:space-around}.ic{display:flex}
  @keyframes drive{0%{transform:translateX(18px);opacity:.0}25%{transform:translateX(0);opacity:1}80%{transform:translateX(0);opacity:1}100%{transform:translateX(-10px);opacity:.0}}
  .drop{animation:drop 1.8s cubic-bezier(.4,0,.2,1) infinite}@keyframes drop{0%{transform:translateY(-26px);opacity:0}35%{transform:translateY(0);opacity:1}48%{transform:translateY(-5px)}60%,100%{transform:translateY(0)}}
  .ring{transform-origin:50% 15%;animation:ring 1.8s ease-in-out infinite}@keyframes ring{0%,60%,100%{transform:rotate(0)}10%{transform:rotate(14deg)}20%{transform:rotate(-12deg)}30%{transform:rotate(8deg)}40%{transform:rotate(-5deg)}}
  .pop{animation:pop 2s ease-in-out infinite}@keyframes pop{0%,70%,100%{transform:scale(1)}80%{transform:scale(1.14)}}
  .spin{animation:spin 2.4s ease-in-out infinite}@keyframes spin{0%,60%{transform:rotate(0)}100%{transform:rotate(144deg)}}
  </style></head><body>${panel(false)}${panel(true)}
  <script>
  const smooth=${S.smoothBearing.toString()};
  for (const id of [0,1]) {
    const road=document.getElementById('road'+id), mk=document.getElementById('mk'+id), L=road.getTotalLength();
    let s=0, bearing=60;
    function frame(){ s=(s+1.6)%L; const p=road.getPointAtLength(s), q=road.getPointAtLength(Math.min(L,s+6));
      const target=(Math.atan2(q.x-p.x,-(q.y-p.y))*180/Math.PI+360)%360; bearing=smooth(bearing,target,0.15);
      mk.setAttribute('transform','translate('+(p.x-23)+' '+(p.y-23)+') rotate('+bearing+' 23 23)'); requestAnimationFrame(frame); }
    frame();
  }
  </script></body></html>`;
}

const browser = await chromium.launch();
try {
  fs.writeFileSync(path.join(OUT, "board.html"), boardHtml());
  const page = await browser.newPage({ viewport: { width: 1500, height: 900 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(path.join(OUT, "board.html")).href);
  await page.waitForTimeout(2500);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(OUT, "icons-board-C.png"), fullPage: true });
  await page.close();

  fs.writeFileSync(path.join(OUT, "motion.html"), motionHtml());
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: OUT, size: { width: 1280, height: 720 } } });
  const mp = await ctx.newPage();
  await mp.goto(pathToFileURL(path.join(OUT, "motion.html")).href);
  await mp.waitForTimeout(12000);
  const vid = await mp.video().path();
  await ctx.close();
  fs.renameSync(vid, path.join(OUT, "icons-motion-C.webm"));
  console.log("OK", OUT);
} finally {
  await browser.close();
}
