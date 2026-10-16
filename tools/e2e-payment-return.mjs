#!/usr/bin/env node
/** **الدفعُ ثمّ العودة — في متصفّحٍ على وضع الضيف** (SPEC §٧٦-س، بلاغُ المالك ٢٠٢٦-١٠-١٦).
 *
 *     chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<مؤقّت> &
 *     node tools/e2e-payment-return.mjs https://app.tajora.ly [cash|wallet]
 *
 * رحلةُ ضيفٍ كاملة (كبتنٌ محاكى) ← «الانتقال إلى الدفع» ← الدفع ← **رجوع** ← يُقاس: **لا نافذةَ «الانتقال إلى الدفع»** و**شريطُ التنقّل ظاهر**
 * و**الرجوعُ من الرئيسية لا يعيد شاشةَ الدفع**. **وسقط على الإنتاج قبل الإصلاح** (عودةُ النافذة وغيابُ الشريط) — وهو ما يثبت أنه يقيس.
 *
 * **ولا يمسّ شيئاً حقيقيّاً**: وضعُ الضيف كلُّه في المتصفّح، والخادمُ لا يرى منه إلا بدءَ جلسةِ ضيف. **ولا يدخل CI** (يحتاج متصفّحاً) — ويُشغَّل
 * بعد كلِّ رفعٍ يمسّ الدفع، ويُكتب ناتجُه في التقرير.
 */

const [base = "https://app.tajora.ly", method = "wallet"] = process.argv.slice(2);
const PORT = Number(process.env.CDP_PORT ?? 9333);

const pages = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
const page = pages.find((p) => p.type === "page") ?? (await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json());
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0;
const waiting = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && waiting.has(msg.id)) {
    waiting.get(msg.id)(msg);
    waiting.delete(msg.id);
  }
};
await new Promise((r) => (ws.onopen = r));
const call = (m, params = {}) => new Promise((resolve) => { const n = ++id; waiting.set(n, resolve); ws.send(JSON.stringify({ id: n, method: m, params })); });
const ev = async (expression) => (await call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.result?.value;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const click = async (text) => {
  const r = await ev(`(() => { const want = ${JSON.stringify(text)}; const all = [...document.querySelectorAll('button,a,[role=button]')].filter(e => e.offsetParent && (e.innerText||'').includes(want)); all.sort((a,b) => (a.innerText||'').length - (b.innerText||'').length); if (!all[0]) return false; all[0].click(); return true; })()`);
  if (!r) throw new Error(`لا زرَّ «${text}»`);
};
const until = async (test, label, ms = 90_000) => {
  for (let t = 0; t < ms; t += 1000) {
    if (await ev(test)) return;
    await sleep(1000);
  }
  throw new Error(`لم يظهر: ${label}`);
};
const has = (text) => `document.body.innerText.includes(${JSON.stringify(text)})`;
const navVisible = "(() => { const n = document.querySelector('.t2-tabs'); return !!(n && n.offsetParent !== null); })()";

await call("Page.enable");
await call("Emulation.setDeviceMetricsOverride", { width: 412, height: 915, deviceScaleFactor: 2, mobile: true });
await call("Page.addScriptToEvaluateOnNewDocument", { source: "Object.defineProperty(navigator,'languages',{get:()=>['ar']});" });
await call("Page.navigate", { url: base });
await sleep(3000);
await ev("localStorage.clear(); sessionStorage.clear()");
if (process.env.SEED_DEMO) {
  // **خادمُ تطويرٍ بلا بابِ الضيف** — يُزرع العرضُ في المتصفّح كما يزرعه الزرّ (`demo/mode.ts`) ثمّ يُقلع
  await ev("localStorage.setItem('taxo.demo', JSON.stringify({token:'local', started_at:new Date().toISOString()})); localStorage.setItem('taxo.access_token','demo'); localStorage.setItem('taxo.refresh_token','demo')");
  await call("Page.navigate", { url: base });
} else {
  await call("Page.navigate", { url: base });
  await until("!!document.querySelector('[data-guest-start]')", "زرُّ الضيف");
  await ev("document.querySelector('[data-guest-start]').click()");
}
await until(has("إلى أين؟"), "الرئيسيةُ في العرض");
await click("إلى أين؟");
await sleep(2000);
await ev("(() => { const i = document.querySelector('input'); i.focus(); })()");
await call("Input.insertText", { text: "rainbow" });
await sleep(3000);
await click("شارع الرينبو");
await until(has("اطلب"), "ورقةُ الطلب");
if (method === "cash") {
  await click("المحفظة");
  await sleep(1500);
  await click("كاش");
  await sleep(1500);
}
await click("اطلب");
await until(has("الانتقال إلى الدفع"), "خاتمةُ الرحلة", 120_000);
const homeIdx = await ev("history.state && history.state.idx");
await click("الانتقال إلى الدفع");
await until(`location.pathname.endsWith('/pay')`, "شاشةُ الدفع");
await sleep(2500);
if (process.env.TRACE) console.log("pay buttons:", await ev("[...document.querySelectorAll('button')].filter(b=>b.offsetParent).map(b=>(b.innerText||'').replace(/\s+/g,' ').trim()).join(' | ')"));
const payLabel = method === "cash" ? "سأدفع كاشاً" : "ادفع من المحفظة";
await click(payLabel).catch(async () => click("ادفع"));
await until(has("اكتمل دفع") + " || " + has("بانتظار") + " || " + has("قيّم رحلتك"), "دفعٌ تمّ");

if (process.env.TRACE) console.log("paid idx", await ev("JSON.stringify(history.state)"), await ev("location.pathname"));
// **الرجوع** — سهمُ الرأس (في العربيّة «arrow_forward»)
await click("arrow_forward");
await sleep(4000);
if (process.env.TRACE) console.log("after back idx", await ev("JSON.stringify(history.state)"), await ev("location.pathname"));
const failures = [];
if (await ev(`location.pathname !== '/'`)) failures.push(`الرجوعُ لم يبلغ الرئيسية: ${await ev("location.pathname")}`);
if (await ev(has("الانتقال إلى الدفع"))) failures.push("عادت نافذةُ «الانتقال إلى الدفع» بعد الدفع");
if (!(await ev(navVisible))) failures.push("شريطُ التنقّل غائبٌ في الرئيسية بعد الدفع");
// **والرئيسيةُ في موضعها قبل الدفع** — لا مدخلٌ فوقها: دفعُ «/» فوق شاشة الدفع يُبقي الدفعَ وراءها يعيده زرُّ الرجوع
const nowIdx = await ev("history.state && history.state.idx");
if (nowIdx !== homeIdx) failures.push(`الرئيسيةُ فوق شاشة الدفع في التاريخ (الموضع ${nowIdx} لا ${homeIdx}) — يعيدها زرُّ الرجوع`);

ws.close();
if (failures.length) {
  console.log(`✗ ${method}: ` + failures.join(" · "));
  process.exit(1);
}
console.log(`✓ ${method}: الرئيسيةُ بعد الدفع بلا نافذةٍ والشريطُ ظاهر، والرجوعُ لا يعيد الدفع`);
