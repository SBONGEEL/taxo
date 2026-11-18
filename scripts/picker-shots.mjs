// **صورُ منتقي الدول بحالاته الأربع** (أمرُ المالك ٢٠٢٦-١١-١٨ الثالث، البند ٣) — في سير «إثباتُ الخريطة المفتوحة».
//   node scripts/picker-shots.mjs <عنوان التطبيق> <مجلّد الإخراج> <click|look>
// **`look` للإنتاج**: يفتح الورقةَ ويصوّرها ولا ينقر دولةً — النقرةُ على دولةٍ غيرِ نشطةٍ تُعدّ محاولةَ تسجيلٍ في قاعدة الإنتاج.
// **`click` لقاعدة CI وحدَها**: ينقر «ظاهرة» (مصر) و«قريباً» (السعوديّة) و«متوقفة» (تونس) ويصوّر رسالةَ كلٍّ منها.
import { chromium } from "playwright";

const [base, out, mode] = process.argv.slice(2);
const browser = await chromium.launch();
const log = [];
for (const scheme of ["light", "dark"]) {
  const page = await browser.newPage({ viewport: { width: 412, height: 915 }, colorScheme: scheme, locale: "ar" });
  // **«load» لا «networkidle»**: الصفحةُ تُبقي اتصالاً حيّاً فلا تهدأ الشبكةُ أبداً (قِيس: مهلةُ ٣٠ث على الإنتاج)
  await page.goto(`${base}/register`, { waitUntil: "load" });
  // **شاشةُ البداية «المس الشاشة للتخطي» تغطّي الصفحة** (قِيس في 44289821374: صورتا الإنتاج شعارٌ وحده) — تُلمس وتُنتظر
  await page.waitForTimeout(2500);
  await page.mouse.click(206, 450);
  await page.waitForTimeout(2500);
  const trigger = page.locator(".t2-auth-country").first();
  // **وصفحةُ الترحيب قبل الحقل** («أهلاً وسهلاً» ثمّ «حساب جديد») — تُعبر إن ظهرت
  if (!(await trigger.waitFor({ state: "visible", timeout: 8000 }).then(() => true, () => false))) {
    await page.getByRole("button", { name: /جديد/ }).first().click({ timeout: 15000 });
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${out}/picker-${mode}-${scheme}-before.png` });
  // **الزرُّ موجودٌ في الشجرة ولا يصير «ظاهراً» لـPlaywright** (قِيس في 44283491864: «waiting for element to be visible» عشرين ثانية)
  // — فيُنقر بالسكربت، والورقةُ تُنتظر بعده
  await trigger.evaluate((el) => el.click());
  await page.locator(".t2-country-sheet").waitFor();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${out}/picker-${mode}-${scheme}.png` });
  const rows = await page.locator(".t2-country-list button").evaluateAll((els) =>
    els.map((el) => ({
      name: el.querySelector(".t2-country-name")?.textContent,
      soon: el.classList.contains("soon"),
      badge: el.querySelector(".t2-country-soon")?.textContent ?? null,
      gray: getComputedStyle(el.querySelector("img,svg,span") ?? el).filter,
    })),
  );
  log.push({ scheme, rows });
  if (mode === "click") {
    for (const [file, name] of [["visible", "مصر"], ["soon", "السعودية"], ["stopped", "تونس"]]) {
      const row = page.locator(".t2-country-list button", { hasText: name }).first();
      if ((await row.count()) === 0) {
        log.push({ scheme, missing: name });
        continue;
      }
      await row.evaluate((el) => el.click()); // **والصفُّ كالزرّ: موجودٌ ولا يصير «ظاهراً» لـPlaywright** (قِيس في 44289821374)
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${out}/picker-${file}-${scheme}.png` });
      log.push({ scheme, tapped: name, notice: await page.locator(".t2-country-notice").textContent().catch(() => null) });
    }
    log.push({ scheme, hiddenShown: (await page.locator(".t2-country-list button", { hasText: "الكويت" }).count()) > 0 });
  }
  await page.close();
}
await browser.close();
console.log(JSON.stringify(log, null, 1));
