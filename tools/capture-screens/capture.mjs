/** لقطاتُ الموقع — **من التطبيقين وهما يعملان، بحسابات البذرة**.
 *
 *     cd tools/capture-screens && npm i && node capture.mjs ../../site/assets-src/screens
 *
 * **ولا واجهةَ تُرسم ولا تُولَّد** (شرطُ المالك): كلُّ ملفٍّ يخرج من هنا
 * **التقاطُ متصفّحٍ لصفحةٍ حيّةٍ على بيئة التطوير**.
 *
 * ## الشروطُ الثلاثة — **وكلُّ واحدٍ منها ثمنُ خطأٍ وقع مقيساً**
 *
 * **١) الحزمةُ المخدومةُ تطابق `dist`** — لا المنفذُ يطابق العُرف.
 * **٢) ولكلِّ لقطةٍ علامةٌ تخصّها** — لا «الشاشةُ غيرُ فارغة».
 * **٣) وزوالُ الدوّارة** — فالترويسةُ تُرسم قبل أن تصل البيانات.
 *
 * **وهي شكلٌ واحدٌ لا ثلاثة**: *العلامةُ القريبةُ تُقرأ العلامةَ نفسَها*.
 * منفذٌ يشبه منفذَنا، وشاشةٌ غيرُ فارغةٍ تُقرأ الشاشةَ المطلوبة، ودوّارةُ
 * تحميلٍ تُحفظ باسم المحتوى. **والعلاجُ في الثلاثة واحدٌ: علامةٌ لا يملكها
 * إلا المطلوب.** وتفصيلُه في `CLAUDE.md` مع كلفته.
 *
 * **والحزمةُ تُقرأ من `dist` لا تُكتب هنا**: رقمٌ يُنسخ في مصدرٍ يبلى عند أوّل
 * بناء، **فيصير الحارسُ يصيح على سليم** — ومن يصيح على سليمٍ يُطفأ.
 */

import { chromium } from "playwright";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
//: **وجذرُ الشجرة يُصرَّح حين يُشغَّل من خارجها**: Chrome مركَّبٌ على ويندوز
//: والشجرةُ في WSL، **فمن شغّله من جزيرةٍ أخرى يقول أين الشجرة** — ولا يُخمَّن.
const ROOT = process.env.TAXO_ROOT ?? join(HERE, "..", "..");
const OUT = process.argv[2] ?? join(HERE, "out");
mkdirSync(OUT, { recursive: true });

//: **المنفذُ من `docker port` لا من العُرف** (`COMMANDS.md`): تطبيقُ الراكب
//: ينشر على `5176`، **و`5173` منفذُ الحاوية من داخلها** — ومن قصده من المضيف
//: أصاب خادماً أجنبيّاً على ويندوز، **والتُقطت منه خمسُ لقطات**.
const APPS = {
  rider: { base: "http://localhost:5176", dist: "customer-app/dist/index.html" },
  driver: { base: "http://localhost:5174", dist: "driver-app/dist/index.html" },
};
const API = "https://dev-api.tajora.ly/api/v1";

//: حساباتُ البذرة — **موثَّقةٌ في `COMMANDS.md` لهذا الغرض بعينه**.
const SEED = {
  rider: { phone: "+962790000021", app: "rider" },
  riderWoman: { phone: "+962790000022", app: "rider" },
  driver: { phone: "+962790000011", app: "driver" },
};
const PASS = "TaxoTest123";
const KEYS = {
  rider: ["taxo.access_token", "taxo.refresh_token"],
  driver: ["taxo.driver.access_token", "taxo.driver.refresh_token"],
};

const log = [];
const saved = [];

//: **توكنٌ واحدٌ لكلِّ رقمٍ يعيش عبر التشغيلات** — والدخولُ محدودٌ لكلِّ هاتف
//: (`COMMANDS.md`)، **وثلاثةُ تشغيلاتٍ تعيد الدخولَ تعود بـ429**. ووقع ثلاثاً:
//: **والمفتاحُ `ratelimit:login:*` لا `login:*`** — كنتُ أمسح نمطاً لا وجودَ
//: له **فأظنّه مُسح**، وهو حارسٌ صامتٌ في الأداة لا في النظام.
const CACHE = join(HERE, ".tokens.json");
let _tokens = new Map();
try {
  _tokens = new Map(Object.entries(JSON.parse(readFileSync(CACHE, "utf8"))));
} catch {
  /* لا ذاكرة بعد — والتشغيلُ الأوّلُ يدخل */
}

/** **وتوكنٌ محفوظٌ ليس توكناً صالحاً** — الشكلُ نفسُه، في الأداة هذه المرّة.
 *
 * **وقع مقيساً ٢٠٢٦-٠٩-٠٥**: الذاكرةُ سلّمت توكناً منتهياً، **فارتدّت كلُّ
 * صفحةٍ إلى شاشة الدخول** — وثمانِ لقطاتٍ من عشرٍ رُفضت. **والشروطُ الثلاثةُ
 * أمسكتها كلَّها** (شاشةُ دخولٍ لا تحمل علامةَ محفظةٍ ولا أرباح)، **فالكلفةُ
 * كانت تشغيلاً ضائعاً لا لقطةً كاذبة** — وهذا بعينه ما بُنيت له.
 *
 * **والعلاجُ: يُسأل البابُ لا الذاكرة.** نداءٌ واحدٌ مصادَقٌ عليه يفصل
 * «محفوظٌ» عن «صالح»، **وهو أرخصُ من تشغيلٍ كامل**. */
async function _alive(app, tokens) {
  const me = app === "driver" ? "/drivers/me" : "/wallet/me";
  const res = await fetch(API + me, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  return res.ok;
}

async function tokensFor(account) {
  const cached = _tokens.get(account.phone);
  if (cached && (await _alive(account.app, cached))) return cached;
  if (cached) log.push(`  … توكنُ ${account.phone} منتهٍ — **يُعاد الدخول**`);
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone: account.phone, password: PASS, app: account.app }),
  });
  if (!res.ok) throw new Error(`login ${account.phone}: HTTP ${res.status}`);
  const body = await res.json();
  if (!body.tokens) throw new Error(`login ${account.phone}: لا توكن`);
  _tokens.set(account.phone, body.tokens);
  writeFileSync(CACHE, JSON.stringify(Object.fromEntries(_tokens)), "utf8");
  return body.tokens;
}

const BUNDLE = /\/assets\/index-[A-Za-z0-9_-]+\.js/;

/** **الشرطُ الأوّل: أهذا تطبيقُنا؟** — يُقاس قبل أن يُلتقط منه شيء. */
async function assertBundle(app) {
  const dist = join(ROOT, APPS[app].dist);
  if (!existsSync(dist)) {
    throw new Error(`${APPS[app].dist} غيرُ مبنيّ — **لا مرجعَ يُقاس عليه**`);
  }
  const want = (readFileSync(dist, "utf8").match(BUNDLE) ?? [])[0];
  if (!want) throw new Error(`${APPS[app].dist} بلا حزمة`);
  const html = await (await fetch(`${APPS[app].base}/`)).text();
  const found = (html.match(BUNDLE) ?? [])[0] ?? "<لا حزمة>";
  if (found !== want) {
    throw new Error(`${APPS[app].base} يخدم ${found} لا ${want} — **ليس تطبيقَنا**`);
  }
  log.push(`  ✓ ${app}: ${APPS[app].base} = ${APPS[app].dist} → ${want.slice(15)}`);
}

async function contextFor(browser, account) {
  const tokens = await tokensFor(account);
  const [a, r] = KEYS[account.app];
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
    locale: "ar",
  });
  await context.addInitScript(
    ([ak, rk, at, rt]) => {
      localStorage.setItem(ak, at);
      localStorage.setItem(rk, rt);
      // **بوّاباتُ أوّل فتحٍ تُغلق** — وإلا صُوِّرت هي بدل الشاشة المطلوبة.
      for (const k of Object.keys(localStorage)) {
        if (/onboard|welcome|intro|notice|seen|tour/i.test(k)) localStorage.setItem(k, "1");
      }
      localStorage.setItem("taxo.onboarded", "1");
      localStorage.setItem("taxo.welcome.seen", "1");
      localStorage.setItem("taxo.brand.notice", "1");
    },
    [a, r, tokens.access_token, tokens.refresh_token],
  );
  return context;
}

/** يلتقط شاشةً — **ولا يحفظ إلا إن تحقّق الشرطان الثاني والثالث**. */
async function shot(page, app, path, name, marker) {
  await page.goto(APPS[app].base + path, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
  let ok = false;
  let busy = true;
  for (let i = 0; i < 20 && !(ok && !busy); i++) {
    const state = await page.evaluate(() => ({
      text: document.body.innerText || "",
      busy: !!document.querySelector("[role=status],[aria-busy=true],.animate-spin"),
    }));
    ok = marker.test(state.text);
    busy = state.busy;
    if (!(ok && !busy)) await page.waitForTimeout(800);
  }
  const text = (await page.evaluate(() => document.body.innerText || "")).trim();

  // **وطولُ النصِّ ليس فيصلاً**: شاشةُ الخريطة ٧٩ حرفاً **وهي مكتملةٌ تماماً**،
  // **فرفضُها بالطول رفضُ سليم** — والحدُّ الأدنى يبقى للفراغ المحض وحدَه.
  if (ok && (busy || text.length < 40)) {
    log.push(`  ✗ ${name}: لم تكتمل (نص ${text.length}${busy ? " · دوّارة" : ""}) — **لا تُحفظ**`);
    return;
  }
  if (!ok) {
    const seen = text.slice(0, 46).replace(/\n/g, " ");
    log.push(`  ✗ ${name}: لم تظهر علامتُها — **لا تُحفظ**  (بدلَها: ${seen}…)`);
    return;
  }
  await page.screenshot({
    path: join(OUT, `${name}.png`),
    clip: { x: 0, y: 0, width: 390, height: Math.min(Math.round((390 * 1198) / 582), 844) },
  });
  saved.push(name);
  log.push(`  ✓ ${name}  (نص ${text.length})`);
}

const RIDER_SHOTS = [
  ["/", "rider-home", /أين تذهب|اطلب|وجهت/],
  ["/wallet", "rider-wallet", /المحفظة|الرصيد|شحن/],
  ["/rides", "rider-rides", /رحلات|لا رحلات/],
];
const DRIVER_SHOTS = [
  ["/", "captain-home", /استقبال|الطلبات|أرباح|متصل/],
  ["/wallet/earnings", "captain-earnings", /أرباح|الدخل|اليوم/],
  ["/subscription", "captain-subscription", /اشتراك/],
  ["/account/vehicle", "captain-documents", /مركبة|مستند|وثائق|رخصة/],
  ["/account/garage", "captain-garage", /كراج|مركبات|المتجر/],
];

//: **Chrome المركَّبُ لا متصفّحٌ يُنزَّل** (`COMMANDS.md`)، وswiftshader لأن
//: الخرائطَ تطلب WebGL ولا بطاقةَ في هذه البيئة.
const browser = await chromium.launch({
  channel: "chrome",
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});

try {
  await assertBundle("rider");
  await assertBundle("driver");
} catch (err) {
  log.push(`  ✗ ${err.message}`);
  console.log(log.join("\n"));
  await browser.close();
  process.exit(1);
}

for (const [account, shots, app] of [
  [SEED.rider, RIDER_SHOTS, "rider"],
  [SEED.riderWoman, [["/", "rider-women", /أين تذهب|اطلب|وجهت/]], "rider"],
  [SEED.driver, DRIVER_SHOTS, "driver"],
]) {
  const context = await contextFor(browser, account);
  const page = await context.newPage();
  for (const [path, name, marker] of shots) {
    try {
      await shot(page, app, path, name, marker);
    } catch (err) {
      log.push(`  ✗ ${name}: ${err.message.slice(0, 60)}`);
    }
  }
  await context.close();
}

await browser.close();
console.log(log.join("\n"));
console.log(`\n  حُفظ ${saved.length}: ${saved.join(" · ")}`);
//: **والسجلُّ بجانب الأداة لا في مجلد الأصول**: ملفٌّ غريبٌ بين اللقطات
//: يُقرأ لاحقاً أصلاً، **وهو عطبُ «مجلَّدٌ صار مخرَجاً» بعينه معكوساً**.
writeFileSync(join(HERE, "_log.txt"), log.join("\n"), "utf8");
