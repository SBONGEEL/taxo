/** يطبع رمزَ الربط الحالي في الطرفية — **بابُ الربط لمن لا لوحةَ عنده**.
 *
 * أوّلُ ربطٍ على تركيبٍ جديد يقع قبل أن يفتح أحدٌ اللوحة، ولذلك للربط بابان:
 * هذا، وبطاقةُ الجلسة في صفحة العقود. وكلاهما يقرأ **الرمزَ نفسَه** من
 * `/qr` — لا يولّد أحدُهما رمزاً ثانياً، فرمزان لجلسةٍ واحدة يجعل أحدَهما
 * يفشل بلا سبب ظاهر.
 *
 *   docker compose exec whatsapp-gateway npm run link
 */

"use strict";

const http = require("node:http");
const qrTerminal = require("qrcode-terminal");

const PORT = Number(process.env.WA_PORT || 8080);
const KEY = String(process.env.WA_GATEWAY_KEY || "").trim();

function ask(path) {
  return new Promise((resolve, reject) => {
    const req = http.get(
      { host: "127.0.0.1", port: PORT, path, headers: { "x-gateway-key": KEY } },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          try {
            resolve({ status: res.statusCode, body: JSON.parse(Buffer.concat(chunks).toString()) });
          } catch (error) {
            reject(error);
          }
        });
      },
    );
    req.on("error", reject);
  });
}

(async () => {
  const status = await ask("/status");
  if (status.status !== 200) {
    console.error("تعذّر قراءة الحالة:", status.body);
    process.exit(1);
  }
  console.log("حالُ الجلسة:", status.body.state);
  if (status.body.state === "linked") {
    console.log("مرتبطةٌ بالرقم", status.body.phone, "منذ", status.body.since);
    console.log("ولإعادة الربط برقمٍ آخر: افصِلها أولاً من صفحة العقود.");
    return;
  }

  const qr = await ask("/qr");
  if (qr.status !== 200) {
    console.error("لا رمزَ ربطٍ الآن — انتظر ثوانيَ وأعد المحاولة.", qr.body);
    process.exit(1);
  }
  qrTerminal.generate(qr.body.qr, { small: true });
  console.log(
    "\nامسحه من هاتف الرقم المخصّص: واتساب › الإعدادات › الأجهزة المرتبطة › ربط جهاز.",
  );
  console.log(`الرمزُ يتجدّد كلَّ ${qr.body.ttl_seconds} ثانية — أعد الأمر إن انتهى.`);
})().catch((error) => {
  console.error(String(error?.message || error));
  process.exit(1);
});
