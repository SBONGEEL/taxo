#!/usr/bin/env node
/** **`check:service-tiles`** — بلاطاتُ «خدماتك» تتبع مفاتيحَ السوق، **ولا «قريباً» تُكتب نصّاً لا يطفئها شيء** (أمرُ المالك ٢٠٢٦-١٠-١٠، SPEC §٧٢).
 *
 * **العلّةُ مقيسةٌ على الإنتاج**: رأى المالكُ «قريباً» على المطار والطرد والرحلات في رئيسية الكبتن وقد أشعل كلَّ شيءٍ في الأردن —
 * البلاطاتُ صفوفٌ كتبتها اللوحةُ «قريباً» بلا مقصد. **فالحالُ صار يُحسب في الخلفية من المفتاح** (`storefront.tiles_for`، واختبارُه
 * `tests/test_storefront_services.py`)، **وهذا الحارسُ نصفُه الذي يسكن في البناء**:
 *
 * 1. **لكلِّ خدمةٍ في `SERVICE_ROUTES` شاشةٌ في تطبيق كلِّ دورٍ يراها** — `ServiceRouteT2` في التطبيقين ومساره `/services/:service`.
 *    وإلا بلاطةٌ مشتعلةٌ تقع على صفحةٍ مفقودة.
 * 2. **«قريباً» نصّاً في الواجهة في مواضعَ تقرؤها من مفتاحٍ أو من حال البلاطة وحدَها** — كلٌّ بعلّته. ومن كتبها في موضعٍ آخر كتب «قريباً»
 *    لا يطفئها شيء، وهي بعينها ما رآه المالك.
 *
 * **وما لا يقيسه — يُقال**: لا يعرف ما في قاعدة الإنتاج من بلاطات؛ ذاك يحرسه حسابُ الحال في الخلفية واختبارُه، ورحلةُ التجربة بعد الرفع.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { certify } from "./certify.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFileSync(join(ROOT, path), "utf8");
const faults = [];

// ── ١ — الخدماتُ وأدوارُها من الخلفية ──
const py = read("backend/app/services/storefront.py");
const block = py.match(/SERVICE_ROUTES: dict\[str, dict\[UserRole, FeatureKey\]\] = \{([\s\S]*?)\n\}/);
if (!block) {
  console.error("✗ لم يُعثر على `SERVICE_ROUTES` — لا يُقاس بالظنّ");
  process.exit(1);
}
const services = new Map();
for (const m of block[1].matchAll(/"\/services\/(\w+)":\s*\{([^}]*)\}/g)) {
  services.set(m[1], [...m[2].matchAll(/UserRole\.(RIDER|DRIVER)/g)].map((r) => r[1].toLowerCase()));
}
if (services.size === 0) faults.push("`SERVICE_ROUTES` بلا خدمةٍ مقروءة — الحارسُ لا يقرأ شيئاً");

/** مفاتيحُ قاموسٍ في ملفّ TSX — `NAME: Record<string, string> = { key: … }`. */
function keysOf(src, name, file) {
  const m = src.match(new RegExp(`${name}: Record<string, string> = \\{([\\s\\S]*?)\\};`));
  if (!m) {
    faults.push(`${file}: \`${name}\` غيرُ موجود — لا يُقاس بالظنّ`);
    return new Set();
  }
  return new Set([...m[1].matchAll(/^\s*(\w+):/gm)].map((k) => k[1]));
}

const driverSrc = read("driver-app/src/screens/t2/ServiceRouteT2.tsx");
const riderSrc = read("customer-app/src/screens/t2/ServiceRouteT2.tsx");
const has = {
  driver: new Set([
    ...keysOf(driverSrc, "DRIVER_SERVICE_TARGETS", "driver-app"),
    // **ما تفتحه شاشةُ «الطرود»** — قائمةٌ في الملفّ نفسِه (`DRIVER_PARCEL_SERVICES`)، لا اسمٌ يُخمَّن
    ...[...(driverSrc.match(/DRIVER_PARCEL_SERVICES: readonly string\[\] = \[([^\]]*)\]/)?.[1] ?? "").matchAll(/"(\w+)"/g)].map((m) => m[1]),
  ]),
  rider: new Set([
    ...keysOf(riderSrc, "RIDER_SERVICE_TARGETS", "customer-app"),
    ...keysOf(riderSrc, "RIDER_SERVICE_STARTS", "customer-app"),
  ]),
};
for (const [app, folder] of [["driver", "driver-app"], ["rider", "customer-app"]]) {
  if (!read(`${folder}/src/App.tsx`).includes('path="/services/:service"')) {
    faults.push(`${folder}: لا مسارَ \`/services/:service\` في App.tsx — البلاطةُ تقع على «*»`);
  }
  for (const [service, roles] of services) {
    if (roles.includes(app) && !has[app].has(service)) {
      faults.push(`«/services/${service}» يراها ${app === "driver" ? "الكبتن" : "الراكب"} — **ولا شاشةَ لها في ${folder}**`);
    }
  }
}

// ── ٢ — «قريباً» نصّاً، في مواضعَ تقرؤها من مفتاحٍ أو من حال البلاطة وحدَها ──
const ALLOWED = new Map([
  ["driver-app/src/screens/t2/ServicesT2.tsx", "حالُ البلاطة من الخلفية (`status`)، والخلفيةُ تحسبها من المفتاح"],
  ["driver-app/src/components/home/ServiceTiles.tsx", "حالُ البلاطة من الخلفية (`status`)"],
  ["customer-app/src/components/home/ServiceTiles.tsx", "حالُ البلاطة من الخلفية (`status`)"],
  ["driver-app/src/screens/t2/SettingsT2.tsx", "فرعُ «المطار» و«صوتُ الإرشاد» المطفأ — المفتاحُ يُقرأ في الشاشة نفسِها"],
  ["customer-app/src/screens/t2/RiderHomeT2.tsx", "فروعُ البلاطات المطفأة — كلٌّ بمفتاحه في الشاشة نفسِها"],
]);
const strip = (text) => text.replace(/\{\/\*[\s\S]*?\*\/\}|\/\*[\s\S]*?\*\/|(^|[^:])\/\/[^\n]*/g, "$1");
function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, out);
    else if (path.endsWith(".tsx")) out.push(path);
  }
  return out;
}
let scanned = 0;
const found = new Set();
for (const folder of ["driver-app", "customer-app"]) {
  for (const path of walk(join(ROOT, folder, "src"))) {
    scanned += 1;
    const code = strip(readFileSync(path, "utf8"));
    if (/[>"'`]\s*قريباً\s*[<"'`]|—\s*قريباً`/.test(code)) found.add(relative(ROOT, path).replaceAll("\\", "/"));
  }
}
if (scanned === 0) faults.push("صفرُ ملفّاتٍ مقروءة — الحارسُ لا يقرأ شيئاً");
for (const file of found) {
  if (!ALLOWED.has(file)) faults.push(`«قريباً» نصّاً في ${file} — **لا يقرؤها من مفتاحٍ ولا من حال بلاطة**`);
}

if (faults.length) {
  console.error("\n✗ بلاطاتُ الخدمات:\n");
  for (const fault of faults) console.error(`  ${fault}`);
  console.error("\nالحالُ من مفتاح السوق في الخلفية (`storefront.SERVICE_ROUTES`) — لا «قريباً» تُكتب بيدٍ وتبقى بعد الإشعال.");
  process.exit(1);
}
certify(
  "check:service-tiles",
  `${services.size} خدماتٍ لكلٍّ شاشتُه في تطبيق من يراها`,
  `«قريباً» نصّاً في ${found.size} مواضعَ تقرؤها من مفتاحٍ أو حال (${scanned} ملفّاً)`,
);
