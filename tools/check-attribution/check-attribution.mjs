/** **نسبةُ الخريطة لا تنفتح وحدَها — مقيسةً في متصفّحٍ بـMapLibre الحقيقيّ** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّة ١-٥).
 *
 *     node tools/check-attribution/check-attribution.mjs      (بعد `npm ci` في customer-app و`npm install` هنا)
 *
 * **ما يُقاس**: خريطةٌ بمقاس كلِّ شاشة — بطاقةُ الرئيسيّة، والخريطةُ بملء الشاشة، وخريطةُ ورقة الطلب، وشاشةُ الرحلة، واللوحة — نهاراً
 * ثمّ ليلاً، **بالمحرّك نفسِه الذي يُشحن** (`customer-app/node_modules/maplibre-gl`) **وبالحارس نفسِه** (`src/lib/map-attribution.ts`
 * مبنيّاً بـesbuild الذي يبني التطبيق). ولكلٍّ: أوّلُ تحميل · تغيّرُ الحجم إلى ملء الشاشة · تبدّلُ المظهر · العودةُ من الخلفيّة —
 * **ويسقط إن كانت النسبةُ مفتوحةً بلا نقرة**. ثمّ: نقرةُ ⓘ تفتحها، والثانيةُ تطويها، وتُطوى وحدَها بعد ثوانٍ.
 *
 * **ومقيسٌ في الاتجاهين** (قاعدةُ كلِّ حارس): خريطةٌ **بلا الحارس** يجب أن تُرى مفتوحةً وحدَها — **وهو العطبُ الذي في لقطة المالك**؛
 * فإن لم يره الفحصُ هناك فهو لا يقيس شيئاً، ويسقط.
 *
 * **وما لا يقيسه**: أنّ كلَّ شاشةٍ تنادي الحارس — ذاك `customer-app/tests/map-attribution.test.ts` (كلُّ `new …Map(` في الثلاثة
 * بـ`attributionControl: false` و`foldedAttribution`). ولا `mapbox-gl` (اللوحةُ والاحتياط): الأصنافُ نفسُها بلاحقةٍ أخرى والحارسُ يقرأ الاثنتين.
 */
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const APP = join(ROOT, "customer-app");
const require = createRequire(join(APP, "package.json"));
const esbuild = require("esbuild");

const helper = esbuild.buildSync({
  entryPoints: [join(APP, "src/lib/map-attribution.ts")],
  bundle: true, write: false, format: "iife", globalName: "TaxoAttr", target: "es2020",
}).outputFiles[0].text;
const engine = readFileSync(require.resolve("maplibre-gl/dist/maplibre-gl.js"), "utf8");
const css = readFileSync(require.resolve("maplibre-gl/dist/maplibre-gl.css"), "utf8");

const SCREENS = [
  { name: "بطاقةُ رئيسيّة الراكب", w: 343, h: 250 },
  { name: "الخريطةُ بملء الشاشة", w: 412, h: 915 },
  { name: "خريطةُ ورقة الطلب", w: 412, h: 420 },
  { name: "شاشةُ الرحلة", w: 412, h: 560 },
  { name: "اللوحة", w: 1100, h: 700 },
];
const CREDIT = '<a href="https://openfreemap.org">OpenFreeMap</a> © OpenMapTiles Data from OpenStreetMap';
const style = (bg) => ({ version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": bg } }] });

const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.setContent(`<!doctype html><html><head><style>${css} body{margin:0} .m{position:relative}</style></head><body></body></html>`);
await page.addScriptTag({ content: engine });
await page.addScriptTag({ content: helper });

const failures = [];
const wait = (ms) => page.waitForTimeout(ms);

async function make(id, w, h, guarded, bg) {
  await page.evaluate(({ id, w, h, guarded, bg, credit }) => {
    const el = document.createElement("div");
    el.id = id; el.className = "m"; el.style.width = `${w}px`; el.style.height = `${h}px`;
    document.body.appendChild(el);
    const map = new maplibregl.Map({ container: el, style: bg, attributionControl: false, center: [13.18, 32.88], zoom: 12 });
    if (guarded) TaxoAttr.foldedAttribution(map, maplibregl.AttributionControl, credit);
    else map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: credit }), "bottom-right");
    window[`map_${id}`] = map;
  }, { id, w, h, guarded, bg: style(bg), credit: CREDIT });
  await page.waitForFunction((id) => window[`map_${id}`].loaded() && document.querySelector(`#${id} .maplibregl-ctrl-attrib`), id, { timeout: 30000 });
}
const isOpen = (id) => page.evaluate((id) => TaxoAttr.attributionOpen(document.querySelector(`#${id} .maplibregl-ctrl-attrib`)), id);
async function expectClosed(id, label, step) {
  await wait(400);
  if (await isOpen(id)) failures.push(`✗ ${label} — مفتوحةٌ بلا نقرة بعد «${step}»`);
}

// ── الاتجاهُ الآخر أوّلاً: بلا الحارس تُرى مفتوحةً وحدَها (العطبُ المقيس) — وإلّا فالفحصُ أعمى
await make("bare", 343, 250, false, "#f4f1ea");
await wait(400);
if (!(await isOpen("bare"))) failures.push("✗ الفحصُ أعمى: خريطةٌ بلا الحارس لم تُرَ مفتوحةً وحدَها — فلا يُصدَّق «مطويّة» على غيرها");
else console.log("✓ بلا الحارس: النسبةُ تنفتح وحدَها (العطبُ المقيس) — فالفحصُ يرى");

let n = 0;
for (const s of SCREENS) {
  for (const [theme, bg, other] of [["نهاراً", "#f4f1ea", "#0e1013"], ["ليلاً", "#0e1013", "#f4f1ea"]]) {
    const id = `s${n++}`;
    const label = `${s.name} ${theme}`;
    await make(id, s.w, s.h, true, bg);
    await expectClosed(id, label, "أوّلُ تحميل");
    await page.evaluate((id) => { const el = document.getElementById(id); el.style.width = "412px"; el.style.height = "915px"; window[`map_${id}`].resize(); }, id);
    await expectClosed(id, label, "ملءُ الشاشة");
    await page.evaluate(({ id, w, h }) => { const el = document.getElementById(id); el.style.width = `${w}px`; el.style.height = `${h}px`; window[`map_${id}`].resize(); }, { id, w: s.w, h: s.h });
    await expectClosed(id, label, "العودةُ إلى المقاس");
    await page.evaluate(({ id, st }) => window[`map_${id}`].setStyle(st), { id, st: style(other) });
    await page.waitForFunction((id) => window[`map_${id}`].isStyleLoaded(), id);
    await expectClosed(id, label, "تبدّلُ المظهر");
    await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
    await expectClosed(id, label, "العودةُ من الخلفيّة");

    // ── النقرةُ وحدَها تفتحها، والثانيةُ تطويها، وتُطوى وحدَها بعد ثوانٍ
    const button = `#${id} .maplibregl-ctrl-attrib-button`;
    await page.click(button);
    await wait(300);
    if (!(await isOpen(id))) failures.push(`✗ ${label} — نقرةُ ⓘ لم تفتحها`);
    await page.click(button);
    await wait(300);
    if (await isOpen(id)) failures.push(`✗ ${label} — النقرةُ الثانيةُ لم تطوِها`);
    await page.click(button);
    await wait(6500);
    if (await isOpen(id)) failures.push(`✗ ${label} — لم تُطوَ وحدَها بعد ستّ ثوانٍ`);
    console.log(`  · ${label}: ${failures.some((f) => f.includes(label)) ? "✗" : "✓"}`);
  }
}

await browser.close();
if (errors.length) failures.push(...errors.map((e) => `✗ خطأٌ في الصفحة: ${e}`));
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log(`✓ النسبةُ مطويّةٌ بلا نقرة على ${SCREENS.length * 2} خريطة (خمسُ شاشاتٍ × نهارٌ وليل)، وتنفتح بـⓘ وحدَه`);
