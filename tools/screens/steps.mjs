#!/usr/bin/env node
/**
 * **خطواتُ اللقطات — واحدةٌ للنظامين** (أمرُ المالك ٢٠٢٦-١١-١٧): `node tools/screens/steps.mjs <app> <outDir> -- <أمرُ اللقطة>`
 *
 * يرسل كلَّ خطوةٍ إلى خادم اللقطات (`server.mjs`)، وينتظر جوابَ المُشغِّل في الصفحة، ثمّ يُشغّل أمرَ اللقطة بالاسم في `$SHOT`:
 *   iPhone:  xcrun simctl io <udid> screenshot "$SHOT"
 *   أندرويد: adb exec-out screencap -p > "$SHOT"
 * **فالشاشاتُ في النظامين بالخطوات نفسِها حرفاً** — والمقارنةُ مقارنةُ تطبيقٍ بتطبيق.
 *
 * **و«بلغ» يعني أن علامةً من الشاشة المقصودة تُرى داخل الشاشة** (`expect` — أمرُ المالك ٢٠٢٦-١١-١٨)، لا أن الضغطةَ نجحت:
 * في التشغيل 44140812843 نجحت كلُّ الضغطات وكانت ثلاثةُ صفوفٍ صوراً خاطئة (الدخولُ بقي على «غيرُ متاح»، وورقةُ الطلب تحت حافّة SE،
 * والكبتنُ «بانتظار إشارة الموقع»). **وكلُّ عمودٍ فيه صفٌّ بلا علامته يُعاد مرّةً**، وما بقي بلا علامةٍ يُكتب أحمرَ بما يُرى بدلَها.
 *
 * **ولا خطوةَ تسقط بصمت**: خطوةٌ لم يجد مُشغِّلُها زرَّها تُصوَّر كما هي **وتُكتب في `steps.json` بعلّتها** — فلوحةُ المقارنة تقول
 * «لم يُبلغ» تحت الشاشة لا صورةً خاطئةً بتسميةٍ صحيحة.
 */
import { execSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [app, out] = process.argv.slice(2);
const shotCmd = process.argv.slice(process.argv.indexOf("--") + 1).join(" ");
const SERVER = "http://127.0.0.1:8787";
mkdirSync(out, { recursive: true });

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
// **قطعُ اتّصالٍ عابرٌ بالخادم المحلّيّ لا يُسقط العمود** — `ECONNRESET` واحدٌ أسقط عمودَ Pro Max كلَّه وفيه صفوفٌ سليمة (44208851709)
async function getJson(url, init) {
  for (let attempt = 1; ; attempt++) {
    try {
      return await (await fetch(url, init)).json();
    } catch (error) {
      if (attempt >= 5) throw error;
      console.log(`  ↻ ${url} — ${error.cause?.code ?? error.message} (محاولة ${attempt})`);
      await wait(1000 * attempt);
    }
  }
}

async function command(body) {
  const sent = await getJson(`${SERVER}/__shot`, { method: "POST", body: JSON.stringify(body) });
  for (let i = 0; i < 60; i++) {
    await wait(500);
    const ack = await getJson(`${SERVER}/__shot/ack`);
    if (ack.id === sent.id) return ack;
  }
  return { id: sent.id, ok: false, note: "لا جوابَ من الصفحة خلال ٣٠ ث" };
}

const DEMO = JSON.stringify({ token: "screens", started_at: "2026-11-17T09:41:00Z" });
// **أوّلُ فتحةٍ مقضيّة** — ورقةُ الترحيب وجولةُ التطبيق تغطّيان كلَّ لقطةٍ لو بقيتا (مقيسٌ في أوّل تشغيل)
const SEEN = { "taxo.welcome.seen": "1", "taxo.driver.welcome.seen": "1", "taxo.driver.welcome.intro.seen": "1" };
const signedIn = (theme) => ({ ...SEEN, "taxo.demo": DEMO, "taxo.access_token": "demo", "taxo.driver.access_token": "demo", "taxo.theme": theme, "taxo.lang": "ar", "taxo.shell.open_map": "1" });
const signedOut = (theme) => ({ ...SEEN, "taxo.theme": theme, "taxo.lang": "ar", "taxo.shell.open_map": "1" });

/** **الشاشاتُ بترتيبها** — `label` تحت الصورة في اللوحة، و`do` ما يُفعل قبلها، و`settle` ما يُنتظر لترسم (الخريطةُ أبطأ)،
 *  و`expect` علاماتُ الشاشة المقصودة: **يكفي واحدةٌ منها داخل الشاشة**، وتُنتظر حتى ١٢ ث بعد `settle`. */
const t = (text) => ({ text });
const sel = (selector) => ({ selector });
const RIDER = [
  // **إلى شاشة الدخول بمسارها لا بزرِّ الترحيب** — الترحيبُ يتبدّل بفحص المنطقة («غيرُ متاحٍ في منطقتك»)، والضغطتان ✓ بقيتا عليه
  // (أندرويد وPro Max، التشغيل 44140812843). والمسارُ هو ما يفتحه الزرّان كلاهما (`Welcome.tsx › go("/login")`).
  { name: "login", label: "الدخول", do: [{ kind: "reset", storage: "out" }, { kind: "nav", path: "/login" }, { kind: "click", text: "لديّ حساب", optional: true }], settle: 4000, expect: [sel("#password"), t("أهلاً من جديد")] },
  // ↑ **ورقةُ الترحيب قد تبقى فوق `/login`** («TAXO غيرُ متاحٍ في منطقتك بعد» وزرُّها «لديّ حساب — دخول») — والعلامةُ قُرئت ✓ من خانةٍ تحتها
  //   (لوحاتُ 44255793642)؛ فيُضغط زرُّها إن ظهر، والعلامةُ صارت تُشترط فوقَ غيرها
  { name: "home", label: "الرئيسيّة «إلى أين؟»", do: [{ kind: "reset", storage: "in" }], settle: 9000, expect: [t("إلى أين")] },
  { name: "search-empty", label: "البحث قبل الكتابة", do: [{ kind: "click", text: "إلى أين" }, { kind: "click", text: "ابحث عن الوجهة بالاسم" }], settle: 3000, expect: [sel(".t2-ps input")] },
  { name: "search-typing", label: "البحث أثناء الكتابة", do: [{ kind: "type", text: "مطار" }], settle: 5000, expect: [sel(".t2-ps-pick")] },
  { name: "order-sheet", label: "ورقةُ الطلب والمسار", do: [{ kind: "click", selector: ".t2-ps-pick" }], settle: 8000, expect: [t("اطلب"), t("اختر الفئة")] },
  { name: "options", label: "الفئات و«خيارات»", do: [{ kind: "click", text: "خيارات" }], settle: 3000, expect: [sel(".t2-v2-options-title")] },
  // **الورقةُ تُغلق بزرّها «تمّ» كما تُغلقها اليد** — `back` غادر الصفحةَ كلَّها على iPhone في الداكن فعادت الرئيسيّة (التشغيل 44060665439)
  { name: "ride-status", label: "حالةُ الرحلة — الكبتن قادمٌ أو وصل", do: [{ kind: "click", text: "تم", optional: true }, { kind: "click", text: "اطلب" }], settle: 2000, expect: [t("الكبتن في الطريق إليك"), t("الكبتن ينتظرك")], expectWithin: 25000, movesOn: true },
  // ↑ **يُصوَّر حين تظهر العلامة لا بعد مهلةٍ ثابتة** — رحلةُ العرض تمضي بمؤقّتاتها، فبعد ١٥ ث ثابتةٍ صُوِّرت «في الطريق إلى المطار» على Pro Max
  //   والعلامةُ ✓ قبلها بلحظة (أمسكها فحصُ ما بعد اللقطة · 44238489964)
  { name: "wallet", label: "المحفظة", do: [{ kind: "nav", path: "/wallet" }], settle: 4000, expect: [sel(".t2-balance")] },
];
const DRIVER = [
  // **ترحيبُ الكبتن يُفتح في كلِّ إقلاعٍ لا في الأوّل وحدَه** (`App.tsx › WelcomeGate`) — فيُتخطّى بعد كلِّ reset
  // **والترحيبُ يظهر عند الخروج في كلِّ جهاز، فـ«تخطَّ» إلزاميّةٌ هنا** — اختياريّةً لم تنتظره في أوّل إقلاعٍ بارد (iPhone، التشغيل 44039966678)
  // **وأوراقُ الأذونات الأولى (توفيرُ الطاقة…) تسبق الرئيسيّة في أندرويد** — «لاحقاً» اختياريّةٌ لأنها لا تظهر في كلِّ جهاز
  { name: "login", label: "الدخول", do: [{ kind: "reset", storage: "out" }, { kind: "click", text: "تخط" }, { kind: "click", text: "دخول", optional: true }], settle: 4000, expect: [sel("#password")] },
  // ↑ **«دخول» اختياريّ** — بعد «تخطَّ» قد تكون شاشةُ الدخول نفسُها، وزرُّها «دخول» معطَّلٌ حتى تُملأ الخانات؛ فكان يُنقر بلا أثر،
  //   وصار الضغطُ ينتظر الزرَّ المعطَّل فسقط الصفُّ والعلامةُ ✓ (44245895915). العلامةُ `#password` هي الحَكَم
  {
    name: "home-offline",
    label: "الرئيسيّة — غيرُ متّصل",
    do: [
      { kind: "reset", storage: "in" },
      { kind: "click", text: "تخط", optional: true },
      { kind: "click", text: "لاحق", optional: true },
      { kind: "click", text: "لاحق", optional: true },
      { kind: "click", text: "لاحق", optional: true },
      // **وعلى iPhone ورقتا الأذونات الأوليان («١ / ٢»: الإشعارات ثمّ الموقع) بزرِّ «ليس الآن»** — مقيسٌ في التشغيل 44014121180
      { kind: "click", text: "ليس الآن", optional: true },
      // ثمّ ورقةُ الموقع «٢ / ٢» بزرِّ «لاحقاً» — **و«لاحق» بلا تنوينٍ تطابق الرسمين** (لاحقاً · لاحقًا)
      { kind: "click", text: "لاحق", optional: true },
      { kind: "click", text: "ليس الآن", optional: true },
      // **وزرُّ الاتصال قد يكون تحت بطاقة «لا تصلك طلبات الآن»** — على iPhone SE كان تحت الشريط والصورةُ بلا زرّ (44199806732)
      { kind: "show", selector: ".t2-hm-go" },
    ],
    settle: 9000,
    expect: [sel(".t2-hm-go.off")],
  },
  // **«متّصل» بموقعٍ لا «بانتظار إشارة الموقع»** — Pro Max صُوِّر بلا موقعٍ والضغطةُ ✓ (التشغيل 44140812843)؛ والموقعُ يُعاد ضبطُه قبل كلِّ
  // إعادة (`LOCATION_CMD`). **واللقطةُ بلا طلب**: العرضُ يرسل طلبَه بعد ٥ ث من الاتصال (`demo/engine.ts › scheduleOffer(5000)`)، فصُوِّرت ورقةُ
  // الطلب في صفِّ «متّصل» مرّتين (44195002007 · 44199806732) ولو صُوِّر بعد ثانيةٍ ونصف. **فيُرفض الطلبُ الأوّل كما يرفضه الكبتن** — والتالي
  // بعد ٦ ث (`decline → scheduleOffer(6000)`) — ثمّ يُصوَّر «متّصل — بانتظار الطلبات» في تلك الفسحة. وهو وضعُ العرض وحدَه: لا خادمَ ولا راكب.
  { name: "home-online", label: "متّصل", do: [{ kind: "click", selector: ".t2-hm-go" }, { kind: "click", text: "رفض", after: 300 }, { kind: "show", selector: ".t2-hm-go", after: 200 }], settle: 300,
    again: [{ kind: "click", text: "رفض", after: 300 }, { kind: "show", selector: ".t2-hm-go", after: 200 }], expect: [t("متصل — بانتظار الطلبات")], expectWithin: 4000 },
  // **ومهلةُ الطلب ثوانٍ** — انتظارٌ أطولُ تركه ينتهي قبل «قبول» فذهب التطبيقُ إلى الخلفيّة (مقيس)
  { name: "offer", label: "طلبُ رحلة", do: [], settle: 4000, expect: [t("قبول")] },
  { name: "ride", label: "شاشةُ الرحلة", do: [{ kind: "click", text: "قبول" }], settle: 8000, expect: [t("في الطريق إلى الراكب"), t("وصلتُ إلى الراكب")] },
  { name: "earnings", label: "الأرباح", do: [{ kind: "nav", path: "/wallet" }], settle: 4000, expect: [sel(".t2-wal-title")] },
];
const steps = app === "driver-app" ? DRIVER : RIDER;
const log = [];

async function pass(theme) {
  const rows = [];
  if (process.env.APPEARANCE_CMD) execSync(`${process.env.APPEARANCE_CMD} ${theme}`, { stdio: "inherit" });
  for (const step of steps) {
    const notes = [];
    for (const action of step.do) {
      // **«location» يُنفَّذ هنا لا في الصفحة** (أمرُ `LOCATION_CMD` على المحاكي). ولا يحتاجه «متّصل»: العرضُ يزيّف الموقعَ في الصفحة،
      // و«بانتظار إشارة الموقع» الذي بقي هناك كان عطباً في التطبيق — المقبسُ لا يراقب الموقعَ في العرض (أُصلح في `lib/socket.ts`)
      if (action.kind === "location") {
        if (process.env.LOCATION_CMD) execSync(process.env.LOCATION_CMD, { stdio: "inherit", shell: "/bin/bash" });
        notes.push("location: ✓");
        await wait(600);
        continue;
      }
      const body = { ...action };
      if (body.kind === "reset") body.storage = action.storage === "in" ? signedIn(theme) : signedOut(theme);
      // **التطبيقُ إلى المقدّمة قبل كلِّ إعادة** — صفحةٌ في الخلفيّة لا تسأل الخادمَ عن الأمر، فتسقط كلُّ خطوةٍ بعدها (مقيسٌ: أندرويد
      // ذهب إلى الخلفيّة بعد رحلة الفاتح، فكان عمودُ الداكن كلُّه شاشةَ المُطلِق — التشغيل 44039966678)
      if (body.kind === "reset" && process.env.FOREGROUND_CMD) {
        execSync(process.env.FOREGROUND_CMD, { stdio: "inherit", shell: "/bin/bash" });
        await wait(3000);
      }
      // **والموقعُ يُضبط من جديد قبل كلِّ إعادة** — ضبطُه مرّةً قبل الإقلاع لم يصل الكبتنَ على Pro Max («بانتظار إشارة الموقع»)
      if (body.kind === "reset" && process.env.LOCATION_CMD) execSync(process.env.LOCATION_CMD, { stdio: "inherit", shell: "/bin/bash" });
      let ack = await command(body);
      // **أمرٌ بلا جوابٍ يُعاد مرّةً** — الصفحةُ قد تكون في منتصف تحميلٍ من عمودٍ سابق فيضيع أمرُها: «reset» بلا جوابٍ خلال ٣٠ ث والعلامةُ بعده ✓
      // (الراكب على أندرويد · 44245895915). وجوابٌ بـ✗ من الصفحة نفسِها لا يُعاد — ذاك حكمٌ لا ضياع
      if (!ack.ok && (ack.note ?? "").startsWith("لا جوابَ")) ack = await command(body);
      notes.push(`${action.kind}: ${ack.ok ? "✓" : "✗"} ${ack.note ?? ""}`.trim());
      await wait(action.after ?? (body.kind === "reset" ? 2500 : 900));
    }
    await wait(step.settle);
    const file = join(out, `${theme}-${step.name}.png`);
    // **«again»: فرصٌ أخرى للحال نفسِها** — «متّصل» نافذتُه ٦ ث بين رفض الطلب ووصول التالي، ولقطةُ iPhone تأكل منها فوصل الطلبُ
    // في أثنائها (Pro Max الداكن · 44245895915). فإن سقطت العلامةُ قبل اللقطة أو بعدها تُعاد أفعالُ `again` (رفضُ الطلب الجديد) ثمّ اللقطة
    const tries = 1 + (step.again ? step.againTimes ?? 2 : 0);
    for (let attempt = 1; attempt <= tries; attempt++) {
      const before = notes.length;
      if (attempt > 1) {
        for (const action of step.again) {
          const ack = await command({ ...action });
          notes.push(`↻ ${attempt}: ${action.kind}: ${ack.ok ? "✓" : "✗"} ${ack.note ?? ""}`.trim());
          await wait(action.after ?? 900);
        }
      }
      if (step.expect) {
        const seenAck = await command({ kind: "expect", any: step.expect, timeout: step.expectWithin ?? 12000 });
        notes.push(`expect: ${seenAck.ok ? "✓" : "✗"} ${seenAck.note ?? ""}`.trim());
      }
      execSync(shotCmd, { stdio: "inherit", env: { ...process.env, SHOT: file }, shell: "/bin/bash" });
      // **والعلامةُ بعد اللقطة أيضاً** — صُوِّر «متّصل» وعليه بطاقةُ الطلب التالي والعلامةُ ✓ قبلها بثانية (Pro Max · 44232290580):
      // الشاشةُ تتغيّر بين العلامة واللقطة. فلا يُقرأ الصفُّ «بلغ» إلا إن ثبتت العلامةُ على جانبي اللقطة
      if (step.expect) {
        const after = await command({ kind: "expect", any: step.expect, timeout: 600 });
        // **حالٌ تمضي وحدَها** (`movesOn`) — رحلةُ العرض تنتقل بمؤقّتاتها ولا تُعاد، فتغيّرُها بعد اللقطة خبرٌ لا سقوط؛ والحَكَمُ علامةُ ما قبل
        // اللقطة، **والصورةُ تُفحص بالعين قبل الإرسال** (صُوِّرت «الكبتن في الطريق إليك» صحيحةً وسقط الصفُّ بفحص ما بعدها · 44255793642)
        if (!after.ok) notes.push(`بعد اللقطة: ${step.movesOn ? "مضت الحالُ (خبر)" : "✗ تغيّرت الشاشة"} — ${after.note ?? ""}`.trim());
      }
      const failed = notes.slice(before).some((n) => n.includes("✗"));
      if (!failed || attempt === tries) break;
      // **المحاولةُ السابقة تبقى في الملاحظات** لكن لا تُحسب على الصفّ إن نجحت التالية — تُعلَّم «سابقة»
      for (let i = before; i < notes.length; i++) notes[i] = notes[i].replace(/✗/g, "✗(سابقة)");
    }
    const reached = notes.every((n) => !n.replace(/✗\(سابقة\)/g, "").includes("✗"));
    rows.push({ theme, name: step.name, label: step.label, file: `${theme}-${step.name}.png`, reached, notes });
    console.log(`${reached ? "✓" : "✗"} ${theme} · ${step.label} — ${notes.join(" · ")}`);
  }
  return rows;
}

for (const theme of ["light", "dark"]) {
  let rows = await pass(theme);
  // **عمودٌ صمتت فيه الصفحةُ يُعاد مرّةً واحدة** — على محاكٍ باردٍ أُعيد تشغيلُ خدمات Google بعد الإقلاع بدقيقة، فقتل النظامُ التطبيقَ
  // لأنه يعتمد على مزوّد خطوطها («depends on provider … FontsProvider in dying proc») — التشغيل 44060665439، عمودُ الكبتن الفاتح.
  // **عطبُ بيئةٍ لا تطبيق**: فيُعاد العمودُ من أوّله ويُكتب أنه أُعيد؛ وإن صمت ثانيةً بقي أحمرَ كما هو.
  // **وعمودٌ سقط أكثرُه يُعاد كذلك** — iPhone 17 Pro Max رسم صفحةً بيضاءَ للعمود الفاتح كلِّه والخادمُ يُجاب (التشغيل 44140812843)،
  // والداكنُ بعده سليم: إقلاعٌ باردٌ كالذي رُئي في `simulator-smoke.sh`.
  // **وصارت كلُّ علامةٍ غائبةٍ تعيد العمود** (أمرُ المالك ٢٠٢٦-١١-١٨) — مرّةً واحدةً لا حلقة، وما بقي أحمرَ يبقى أحمر.
  const missed = rows.filter((r) => !r.reached).map((r) => r.name);
  if (missed.length) {
    console.log(`↻ ${theme}: بلا علامة — ${missed.join("، ")} — يُعاد العمودُ مرّةً`);
    rows = (await pass(theme)).map((r) => ({ ...r, notes: ["↻ أُعيد العمود", ...r.notes] }));
  }
  log.push(...rows);
}
writeFileSync(join(out, "steps.json"), JSON.stringify(log, null, 1));
