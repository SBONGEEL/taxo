// **يقيّم تعبيراً في صفحة WebView عبر بروتوكول أدوات المطوّر** — لإثبات الخريطة على المحاكي (`android-emulator-open-map.sh`).
//   node scripts/cdp-eval.mjs <منفذ> <تعبير>
// يطبع القيمةَ ويخرج بصفر، أو يطبع الاستثناءَ ويخرج بواحد. **WebSocket عامٌّ في Node 22** فلا حزمةَ تُثبَّت.
const [port, expression] = process.argv.slice(2);
const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const page = targets.find((t) => t.type === "page") ?? targets[0];
if (!page) {
  console.error("لا صفحةَ في الغلاف");
  process.exit(1);
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
const timer = setTimeout(() => {
  console.error("انتهت المهلة");
  process.exit(1);
}, 15000);
ws.onopen = () =>
  ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression, returnByValue: true } }));
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id !== 1) return;
  clearTimeout(timer);
  const result = msg.result ?? {};
  if (result.exceptionDetails) {
    console.error(result.exceptionDetails.text ?? "استثناء");
    process.exit(1);
  }
  console.log(result.result?.value ?? "");
  ws.close();
  process.exit(0);
};
