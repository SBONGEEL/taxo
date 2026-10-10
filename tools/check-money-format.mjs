/** **صياغةُ المال في الواجهة نصّاً بنصّ — الأردنُ وليبيا كما كانا حرفاً، والجزائرُ بلا كسور** (SPEC §٧٣-ج/١٢).
 *
 * **العلّة**: العلامةُ والخاناتُ صارت تُقرأ من `/config` (سجلُّ العملات) بعد أن كانت جداولَ في الشيفرة — **وتبديلُ مصدرٍ يغيّر النصَّ
 * المعروضَ بلا أن يفشل نوعٌ أو بناء**. فهذا الحارسُ يبني وحدةَ الصياغة الحقيقيّة في كلِّ تطبيق (`esbuild`، نسختُه التي يُبنى بها
 * التطبيق)، ويملأ السجلَّ كما تملؤه `/config`، **ويشترط نصوصاً بعينها**: قيمُ الأردن وليبيا أُخذت من الشيفرة **قبل** §٧٣ وقُورنت بها
 * الجديدةُ على ١٥٬٦٤٤ ناتجاً بلا فرق (٢٠٢٦-١٠-١١) — فهنا عيّنتُها ثابتةً، وأيُّ تغيّرٍ فيها يُسقط البناء.
 *
 * **وما لا يقيسه — ويقوله**: شاشةً بعينها ولا مكانَ العلامة في التخطيط، **ولا أن `/config` تصل قبل أوّل رسم** (ذاك شرطُ مُزوِّد
 * الإعدادات: شاشةُ البدء تبقى حتى تصل)؛ ولا سطحاً يطبع المبلغَ بغير هذه الدوال.
 */

import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { argv, exit } from "node:process";
import { createRequire } from "node:module";
import { certify } from "./certify.mjs";

const APP = argv[2];
const ENTRIES = {
  "customer-app": `export { formatMoney, currencyLabel, currencyName, currencyDecimals, zeroAmount, isZeroAmount, registerCurrencies } from "./src/lib/utils.ts";`,
  "driver-app": `export { currencyLabel, currencyName, currencyDecimals, zeroAmount, isZeroAmount, registerCurrencies } from "./src/lib/utils.ts";\nexport { CURRENCY_LABEL, CURRENCY_FULL } from "./src/lib/rideFormat.ts";`,
  "admin-panel": `export { money, currencyLabel, currencyOf, currencyDecimals, zeroAmount, isZeroAmount, registerCurrencies, registerCountryCurrencies } from "./src/lib/format.ts";`,
};
if (!ENTRIES[APP]) {
  console.error("استعمال: node tools/check-money-format.mjs <customer-app|driver-app|admin-panel>");
  exit(2);
}

const ROOT = new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const appDir = join(ROOT, APP);
let esbuild;
try {
  esbuild = createRequire(join(appDir, "package.json"))("esbuild");
} catch {
  console.error(`✗ لم يوجد \`esbuild\` في ${APP} — ثبّت حزمتَه (\`npm ci\`). الحارسُ لا يقيس.`);
  exit(2);
}

const work = mkdtempSync(join(tmpdir(), "money-format-"));
const outfile = join(work, "entry.mjs");
await esbuild.build({
  stdin: { contents: ENTRIES[APP], resolveDir: appDir, loader: "ts" },
  bundle: true,
  platform: "node",
  format: "esm",
  outfile,
  logLevel: "silent",
  alias: { "@": join(appDir, "src") },
  external: ["mapbox-gl", "@capacitor/*"],
});
const m = await import(outfile);
rmSync(work, { recursive: true, force: true });

/** **كما تنشرها `/config`** (`core/currency.py`) — وهي ما يملأ السجلَّ في التشغيل */
const COUNTRIES = [
  { country_code: "JO", currency: "JOD", currency_label: "د.أ", currency_name: "دينار أردني", currency_decimals: 3 },
  { country_code: "LY", currency: "LYD", currency_label: "د.ل", currency_name: "دينار ليبي", currency_decimals: 3 },
  { country_code: "DZ", currency: "DZD", currency_label: "د.ج", currency_name: "دينار جزائري", currency_decimals: 0 },
];

const cases = [];
const expect = (what, got, want) => cases.push({ what, got, want });

// **قبل أن تصل `/config`**: ثلاثُ خاناتٍ كما كانت الصياغةُ قبل §٧٣ — لا خاناتٌ مخترعة
expect("currencyDecimals(قبل الإعداد)", m.currencyDecimals("JOD"), 3);
m.registerCurrencies(COUNTRIES);
m.registerCountryCurrencies?.(COUNTRIES);

expect("zeroAmount(JOD)", m.zeroAmount("JOD"), "0.000");
expect("zeroAmount(DZD)", m.zeroAmount("DZD"), "0");
expect("isZeroAmount(0.000)", m.isZeroAmount("0.000"), true);
expect("isZeroAmount(0.001)", m.isZeroAmount("0.001"), false);
expect("currencyDecimals(DZD)", m.currencyDecimals("DZD"), 0);
expect("currencyLabel(JOD)", m.currencyLabel("JOD"), "د.أ");
expect("currencyLabel(LYD)", m.currencyLabel("LYD"), "د.ل");
expect("currencyLabel(DZD)", m.currencyLabel("DZD"), "د.ج");

if (APP === "customer-app") {
  // **قيمُ الأردن وليبيا من الشيفرة قبل §٧٣** — حرفاً
  expect("formatMoney(1.5,JOD)", m.formatMoney("1.5", "JOD"), "1.500 د.أ");
  expect("formatMoney(1234567.891,JOD)", m.formatMoney("1234567.891", "JOD"), "1,234,567.891 د.أ");
  expect("formatMoney(-2.250,LYD)", m.formatMoney("-2.250", "LYD"), "−2.250 د.ل");
  expect("formatMoney(0,JOD)", m.formatMoney("0", "JOD"), "0.000 د.أ");
  expect("formatMoney(12)", m.formatMoney("12"), "12.000");
  expect("formatMoney(—)", m.formatMoney("", "JOD"), "—");
  expect("currencyName(LYD)", m.currencyName("LYD"), "دينار ليبي");
  // **والجزائريُّ بلا كسور — ولا يُخفى كسرٌ وصل**
  expect("formatMoney(150.000,DZD)", m.formatMoney("150.000", "DZD"), "150 د.ج");
  expect("formatMoney(1234567,DZD)", m.formatMoney("1234567", "DZD"), "1,234,567 د.ج");
  expect("formatMoney(150.500,DZD)", m.formatMoney("150.500", "DZD"), "150.500 د.ج");
}
if (APP === "driver-app") {
  expect("CURRENCY_LABEL.JOD", m.CURRENCY_LABEL.JOD, "د.أ");
  expect("CURRENCY_LABEL.LYD", m.CURRENCY_LABEL.LYD, "د.ل");
  expect("CURRENCY_FULL.JOD", m.CURRENCY_FULL.JOD, "دينار أردني");
  expect("CURRENCY_LABEL.DZD", m.CURRENCY_LABEL.DZD, "د.ج");
  expect("currencyName(DZD)", m.currencyName("DZD"), "دينار جزائري");
}
if (APP === "admin-panel") {
  expect("money(1.500,JOD)", m.money("1.500", "JOD"), "1.500 د.أ");
  expect("money(0.750,LYD)", m.money("0.750", "LYD"), "0.750 د.ل");
  expect("currencyOf(JO)", m.currencyOf("JO"), "JOD");
  expect("currencyOf(LY)", m.currencyOf("LY"), "LYD");
  expect("currencyOf(DZ)", m.currencyOf("DZ"), "DZD");
  expect("money(150,DZD)", m.money("150", "DZD"), "150 د.ج");
}

const failed = cases.filter((c) => c.got !== c.want);
if (failed.length > 0) {
  console.error(`\nصياغةُ المال في ${APP} تغيّرت:\n`);
  for (const c of failed) console.error(`  ✗ ${c.what}: ${JSON.stringify(c.got)} — والمنتظَر ${JSON.stringify(c.want)}`);
  console.error("\n  والعلامةُ والخاناتُ من `/config` (`core/currency.py`) — لا تُكتب في الواجهة ولا تُخمَّن.");
  exit(1);
}
certify("check:money-format", `✓ ${cases.length} نصّاً كما يجب في ${APP} — الأردنُ وليبيا كما كانا حرفاً، والجزائريُّ بلا كسور`);
