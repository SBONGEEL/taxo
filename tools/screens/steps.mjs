#!/usr/bin/env node
/**
 * **خطواتُ اللقطات — واحدةٌ للنظامين** (أمرُ المالك ٢٠٢٦-١١-١٧): `node tools/screens/steps.mjs <app> <outDir> -- <أمرُ اللقطة>`
 *
 * يرسل كلَّ خطوةٍ إلى خادم اللقطات (`server.mjs`)، وينتظر جوابَ المُشغِّل في الصفحة، ثمّ يُشغّل أمرَ اللقطة بالاسم في `$SHOT`:
 *   iPhone:  xcrun simctl io <udid> screenshot "$SHOT"
 *   أندرويد: adb exec-out screencap -p > "$SHOT"
 * **فالشاشاتُ في النظامين بالخطوات نفسِها حرفاً** — والمقارنةُ مقارنةُ تطبيقٍ بتطبيق.
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
async function command(body) {
  const sent = await (await fetch(`${SERVER}/__shot`, { method: "POST", body: JSON.stringify(body) })).json();
  for (let i = 0; i < 60; i++) {
    await wait(500);
    const ack = await (await fetch(`${SERVER}/__shot/ack`)).json();
    if (ack.id === sent.id) return ack;
  }
  return { id: sent.id, ok: false, note: "لا جوابَ من الصفحة خلال ٣٠ ث" };
}

const DEMO = JSON.stringify({ token: "screens", started_at: "2026-11-17T09:41:00Z" });
// **أوّلُ فتحةٍ مقضيّة** — ورقةُ الترحيب وجولةُ التطبيق تغطّيان كلَّ لقطةٍ لو بقيتا (مقيسٌ في أوّل تشغيل)
const SEEN = { "taxo.welcome.seen": "1", "taxo.driver.welcome.seen": "1", "taxo.driver.welcome.intro.seen": "1" };
const signedIn = (theme) => ({ ...SEEN, "taxo.demo": DEMO, "taxo.access_token": "demo", "taxo.driver.access_token": "demo", "taxo.theme": theme, "taxo.lang": "ar", "taxo.shell.open_map": "1" });
const signedOut = (theme) => ({ ...SEEN, "taxo.theme": theme, "taxo.lang": "ar", "taxo.shell.open_map": "1" });

/** **الشاشاتُ بترتيبها** — `label` تحت الصورة في اللوحة، و`do` ما يُفعل قبلها، و`settle` ما يُنتظر لترسم (الخريطةُ أبطأ). */
const RIDER = [
  // **ضغطةٌ ثانيةٌ اختياريّة** — الترحيبُ يُعاد رسمُه بعد فحص المنطقة، فضغطةٌ قبله لا تنقل (مقيسٌ: أندرويد وSE بقيا على «غيرُ متاح» والضغطةُ ✓)
  { name: "login", label: "الدخول", do: [{ kind: "reset", storage: "out" }, { kind: "click", text: "لديّ حساب" }, { kind: "click", text: "لديّ حساب", optional: true }], settle: 4000 },
  { name: "home", label: "الرئيسيّة «إلى أين؟»", do: [{ kind: "reset", storage: "in" }], settle: 9000 },
  { name: "search-empty", label: "البحث قبل الكتابة", do: [{ kind: "click", text: "إلى أين" }, { kind: "click", text: "ابحث عن الوجهة بالاسم" }], settle: 3000 },
  { name: "search-typing", label: "البحث أثناء الكتابة", do: [{ kind: "type", text: "مطار" }], settle: 5000 },
  { name: "order-sheet", label: "ورقةُ الطلب والمسار", do: [{ kind: "click", selector: ".t2-ps-pick" }], settle: 8000 },
  { name: "options", label: "الفئات و«خيارات»", do: [{ kind: "click", text: "خيارات" }], settle: 3000 },
  // **الورقةُ تُغلق بزرّها «تمّ» كما تُغلقها اليد** — `back` غادر الصفحةَ كلَّها على iPhone في الداكن فعادت الرئيسيّة (التشغيل 44060665439)
  { name: "ride-status", label: "الكبتن في الطريق", do: [{ kind: "click", text: "تم", optional: true }, { kind: "click", text: "اطلب" }], settle: 15000 },
  { name: "wallet", label: "المحفظة", do: [{ kind: "nav", path: "/wallet" }], settle: 4000 },
];
const DRIVER = [
  // **ترحيبُ الكبتن يُفتح في كلِّ إقلاعٍ لا في الأوّل وحدَه** (`App.tsx › WelcomeGate`) — فيُتخطّى بعد كلِّ reset
  // **والترحيبُ يظهر عند الخروج في كلِّ جهاز، فـ«تخطَّ» إلزاميّةٌ هنا** — اختياريّةً لم تنتظره في أوّل إقلاعٍ بارد (iPhone، التشغيل 44039966678)
  // **وأوراقُ الأذونات الأولى (توفيرُ الطاقة…) تسبق الرئيسيّة في أندرويد** — «لاحقاً» اختياريّةٌ لأنها لا تظهر في كلِّ جهاز
  { name: "login", label: "الدخول", do: [{ kind: "reset", storage: "out" }, { kind: "click", text: "تخط" }, { kind: "click", text: "دخول" }], settle: 4000 },
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
    ],
    settle: 9000,
  },
  { name: "home-online", label: "متّصل", do: [{ kind: "click", selector: ".t2-hm-go" }], settle: 8000 },
  // **ومهلةُ الطلب ثوانٍ** — انتظارٌ أطولُ تركه ينتهي قبل «قبول» فذهب التطبيقُ إلى الخلفيّة (مقيس)
  { name: "offer", label: "طلبُ رحلة", do: [], settle: 4000 },
  { name: "ride", label: "شاشةُ الرحلة", do: [{ kind: "click", text: "قبول" }], settle: 8000 },
  { name: "earnings", label: "الأرباح", do: [{ kind: "nav", path: "/wallet" }], settle: 4000 },
];
const steps = app === "driver-app" ? DRIVER : RIDER;
const log = [];

async function pass(theme) {
  const rows = [];
  if (process.env.APPEARANCE_CMD) execSync(`${process.env.APPEARANCE_CMD} ${theme}`, { stdio: "inherit" });
  for (const step of steps) {
    const notes = [];
    for (const action of step.do) {
      const body = { ...action };
      if (body.kind === "reset") body.storage = action.storage === "in" ? signedIn(theme) : signedOut(theme);
      // **التطبيقُ إلى المقدّمة قبل كلِّ إعادة** — صفحةٌ في الخلفيّة لا تسأل الخادمَ عن الأمر، فتسقط كلُّ خطوةٍ بعدها (مقيسٌ: أندرويد
      // ذهب إلى الخلفيّة بعد رحلة الفاتح، فكان عمودُ الداكن كلُّه شاشةَ المُطلِق — التشغيل 44039966678)
      if (body.kind === "reset" && process.env.FOREGROUND_CMD) {
        execSync(process.env.FOREGROUND_CMD, { stdio: "inherit", shell: "/bin/bash" });
        await wait(3000);
      }
      const ack = await command(body);
      notes.push(`${action.kind}: ${ack.ok ? "✓" : "✗"} ${ack.note ?? ""}`.trim());
      await wait(body.kind === "reset" ? 2500 : 900);
    }
    await wait(step.settle);
    const file = join(out, `${theme}-${step.name}.png`);
    execSync(shotCmd, { stdio: "inherit", env: { ...process.env, SHOT: file }, shell: "/bin/bash" });
    const reached = notes.every((n) => !n.includes("✗"));
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
  if (process.env.FOREGROUND_CMD && rows.some((r) => r.notes.some((n) => n.includes("لا جوابَ")))) {
    console.log(`↻ ${theme}: الصفحةُ صمتت — يُعاد العمودُ مرّةً`);
    rows = (await pass(theme)).map((r) => ({ ...r, notes: ["↻ أُعيد العمود", ...r.notes] }));
  }
  log.push(...rows);
}
writeFileSync(join(out, "steps.json"), JSON.stringify(log, null, 1));
