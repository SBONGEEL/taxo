/** بوابةُ واتساب الذاتية — خادمُ HTTP صغيرٌ **لا تكلّمه إلا الخلفية**.
 *
 * **ولا منفذَ منشور في compose**: لا `ports:` أصلاً، فالخدمةُ لا تُرى إلا من
 * شبكة المشروع الداخلية. والمفتاحُ المشترك (`WA_GATEWAY_KEY`) هو الحارسُ
 * الثاني — لأن «لا منفذ» شرطُ نشرٍ يمكن أن يُنقض بسطرٍ في ملفٍ آخر، والمفتاحُ
 * شرطٌ في الكود لا يُنقض بالنشر. حارسان لا واحد، كقاعدة الأقفال في الخلفية.
 *
 * **وأربعةُ أبوابٍ لا أكثر**، وكلُّ بابٍ منها سؤالٌ واحد:
 *
 * | الباب | السؤال |
 * |---|---|
 * | `POST /send` | أرسِل رمزاً لرقم |
 * | `GET /status` | ما حالُ الجلسة الآن |
 * | `GET /qr` | ما رمزُ الربط الحالي |
 * | `POST /logout` | افصِل وامحُ لأربط رقماً آخر |
 *
 * **ولا بابَ يقبل نصّاً**: `/send` يأخذ الرمزَ ورقمَه، والنصُّ يُصاغ في
 * `session.js`. فوعدُ «نصٌّ واحدٌ ثابتٌ بلا روابط» يحرسه من يملك السلك، لا من
 * يستدعيه — ووعدٌ يحرسه المستدعي يُنقض أوّلَ مسارٍ جديد.
 *
 * **ولا صحّةَ (`/health`) خلف المفتاح**: مراقبةُ الحياة سؤالٌ لا يكشف شيئاً،
 * وحارسٌ عليه يجعل فحصَ compose يحتاج سرّاً.
 */

"use strict";

const http = require("node:http");

const { Session, logger } = require("./session");
const { chooseText } = require("./template");
const { SendQueue } = require("./queue");

const PORT = Number(process.env.WA_PORT || 8080);
const KEY = String(process.env.WA_GATEWAY_KEY || "").trim();

// الجسمُ مسقوف: هذا الباب يقبل رقماً ورمزاً، وأيُّ حجمٍ أكبر خطأٌ أو عبث
const MAX_BODY_BYTES = 4096;

const session = new Session();
const queue = new SendQueue();

function send(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
    "Cache-Control": "no-store",
  });
  res.end(payload);
}

function authorized(req) {
  // **المقارنةُ بطولٍ ثابت لا تُبنى هنا**: المفتاحُ لا يعبر شبكةً عامةً أصلاً
  // (لا منفذ منشور)، وقياسُ الزمن يحتاج مهاجماً داخل الشبكة — ومن بلغها بلغ
  // ما هو أقصر. فالبساطةُ هنا صدقٌ لا كسل
  return KEY !== "" && req.headers["x-gateway-key"] === KEY;
}

async function readBody(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      const error = new Error("الجسم أكبر من المسموح");
      error.tooLarge = true;
      throw error;
    }
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf-8"));
  } catch {
    const error = new Error("جسمٌ غير مقروء");
    error.badJson = true;
    throw error;
  }
}

async function handleSend(req, res) {
  let body;
  try {
    body = await readBody(req);
  } catch (error) {
    return send(res, 400, { error: String(error.message) });
  }

  const to = String(body.to || "").trim();
  const code = String(body.code || "").trim();
  const ttl = Number(body.ttl_minutes || 5);
  if (!/^\+?[0-9]{6,20}$/.test(to) || !/^[0-9]{4,10}$/.test(code)) {
    return send(res, 400, { error: "رقمٌ أو رمزٌ غير صالح" });
  }

  // **الفحصُ ثم السقوطُ إلى النصّ المدمج — ولا سقوطَ صامت.** قالبٌ معطوبٌ يعمل
  // شهراً ولا أحد يعلم هو أسوأُ من قالبٍ يُرفض بصوت، فكلُّ سقوطٍ يُسجَّل
  // بمستوى `warn` باسم القالب وبالشرط الذي خالفه.
  const decision = chooseText(
    typeof body.body === "string" ? body.body : "",
    String(body.purpose || "registration"),
  );
  if (decision.fellBack && !decision.silent) {
    logger.warn(
      {
        purpose: decision.purpose,
        violations: decision.violations,
        at: new Date().toISOString(),
      },
      "قالبٌ مرفوضٌ عند الإرسال — يُستعمل النصُّ المدمج",
    );
  }

  try {
    const reference = await queue.run(() => session.sendCode(to, code, ttl, decision.text));
    return send(res, 200, { reference, provider: "baileys" });
  } catch (error) {
    // **حالُ الجلسة تُعاد مع الخطأ**: الخلفيةُ ترتدّ إلى القناة التالية في
    // الحالتين، لكنّ سجلَّها يجب أن يفرّق بين «الرقم ليس على واتساب» و«جلستُنا
    // ساقطة» — الأولُ يخصّ مستخدماً واحداً، والثاني يوقف التسجيل كلَّه
    // **و«لم يُقرّ الخادم» عطبُ قناةٍ لا عطبُ رقم**: ٥٠٣ فترتدّ الخلفيةُ إلى
    // القناة التالية، بخلاف ٤٢٢ التي تخصّ صاحبَ الرقم وحدَه
    const status = error.notOnWhatsApp ? 422 : 503;
    logger.warn(
      { err: String(error.message || error), to: to.slice(-4) },
      "تعذّر الإرسال",
    );
    return send(res, status, {
      error: String(error.message || error),
      session: session.snapshot().state,
      not_on_whatsapp: Boolean(error.notOnWhatsApp),
    });
  }
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || "/", "http://gateway");
  const route = `${req.method} ${url.pathname}`;

  if (route === "GET /health") {
    return send(res, 200, { ok: true, state: session.snapshot().state });
  }

  if (!authorized(req)) {
    return send(res, 401, { error: "مفتاحُ البوابة مطلوب" });
  }

  if (route === "POST /send") return void handleSend(req, res);

  if (route === "GET /status") {
    return send(res, 200, { ...session.snapshot(), queue_depth: queue.depth });
  }

  if (route === "GET /qr") {
    const qr = session.qr();
    if (!qr) return send(res, 404, { error: "لا رمزَ ربطٍ الآن" });
    return send(res, 200, qr);
  }

  if (route === "POST /logout") {
    return void session
      .logout()
      .then(() => send(res, 200, session.snapshot()))
      .catch((error) => send(res, 500, { error: String(error.message || error) }));
  }

  return send(res, 404, { error: "لا مسار" });
});

if (!KEY) {
  // **الرفضُ عند الإقلاع لا عند أول نداء**: بوابةٌ بلا مفتاحٍ ترفض كلَّ شيء
  // بصمتٍ فتُقرأ «واتساب لا يعمل»، والسببُ سطرٌ ناقصٌ في `.env.local`
  logger.error("WA_GATEWAY_KEY غير مضبوط — البوابةُ لا تعمل بلا مفتاح");
  process.exit(1);
}

server.listen(PORT, "0.0.0.0", () => {
  logger.info({ port: PORT }, "بوابةُ واتساب تستمع");
  void session.start();
});

for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => {
    logger.info({ signal }, "إيقافٌ نظيف");
    server.close(() => process.exit(0));
  });
}
