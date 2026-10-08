// e2e-call — **مكالمةٌ حقيقيّةٌ بين طرفين في متصفّحَين بلا رأس** (SPEC §٦٦-د/٨: «تُجرَّب المكالمةُ طرفاً لطرفٍ في متصفّحين بلا رأس
// بميكروفونٍ مصطنع على مكدّس التطوير، ولا تُقاس على S21 حتى تُبنى حزمتُها»).
//
// **ما يقيسه** — بتطبيقَي الراكب والكبتن المبنيَّين نفسَيهما (`vite preview`) على خلفية التطوير، لا بمحاكاة:
//   ١) الراكبُ يتّصل، والكبتنُ يرى شاشةَ الوارد ويردّ ⇒ `iceConnectionState` يبلغ `connected`/`completed` في الطرفين، والمدّةُ تعدّ،
//      و«إنهاء» عند الراكب يُغلقها عند الكبتن — وسجلُّها في القاعدة `completed` بمدّة.
//   ٢) الكبتنُ يتّصل والراكبُ يردّ ثمّ **الكبتنُ** يُنهي ⇒ تُغلق عند الراكب.
//   ١-ب) **المتصَلُ به فاته العرض** (مقبسُه لم يحمله — تُسقَط إشاراتُه حتى «ردّ») ⇒ يُعاد العرضُ بعد «ردّ» فتتّصل.
//   ١-ج) **«إنهاء» والميكروفونُ يُسأل** ⇒ لا مكالمةَ تُكتب عند الخادم ولا رنينَ عند الطرف الآخر.
//   ١-د) **رفعُ التسجيل لا يسبق الإنهاء** — «مسجَّلة» تُقال لمتصفّح الراكب وحدَه (ردُّ البدء يُعدَّل في الطريق)، **والخادمُ لا
//        يُشعَل فيه التسجيل** فيردّ الرفعَ ولا يحفظ شيئاً؛ والمقيسُ ترتيبُ الطلبين.
//   ٣) لا يُردّ ⇒ «لم يُجب» عند المتصل بعد مهلة الرنين، وسجلُّها `no_answer`.
//   ٣-ب) **«أعد المحاولة» بشروط «اتصال»**: مقبسُ المتصل يسقط ⇒ لا تُرسم، ويعود ⇒ تعود.
//   ٤) المحادثة: رسالةٌ تصل بشارتها، و«قُرئت» بعد الفتح، **ورقمُ هاتفٍ يُردّ بنصّ الخادم**.
//   ٤-ب) **الورقةُ مفتوحةٌ والتطبيقُ في الخلفية** ⇒ لا «قُرئت» حتى يعود إليها.
//
// **وبياناتُه بياناتُه** (قاعدةُ التطوير وحدَها، `taxo-rd-db` — ولا إنتاجَ أبداً):
//   - مفتاحا المحادثة والمكالمة لسوق الأردن **يُشعَلان للتجربة ثمّ يُعادان كما كانا** (صفٌّ يُحذف أو قيمةٌ تُعاد). **والإشعالُ
//     مباشرةً في القاعدة لا من بابه** — بابُه يشترط نشرَ سطر الخصوصية، **ونشرُ سياسةٍ على مكدّسٍ مشترَكٍ أثرٌ لا يُعاد**. **والتسجيلُ
//     لا يُمسّ** (`service_settings.call_recording_enabled` يبقى مطفأً).
//   - رحلةٌ حقيقيّةٌ بباب الطلب والقبول بين حسابَي التطوير (`COMMANDS.md`)، **ويلغيها الكبتنُ في آخرها** — وإلغاءُ الكبتن بلا رسمٍ على
//     أحد (`rides.cancel_ride`)، فلا مالَ يتحرّك.
//   - **ولا يبدأ إن كانت لأيٍّ منهما رحلةٌ جارية** — لا يُمسّ حالٌ لم يصنعه.
//
// **التشغيل** (ويندوز — Playwright ومتصفّحاتُه هناك؛ والتطبيقان مبنيّان بـ`DEV_BUILD=1 VITE_API_BASE_URL=http://127.0.0.1:8001`
// ويُخدَمان بـ`vite preview` على 5173 و5174 — منفذا `cors_origins`):
//
//     set TAXO_PLAYWRIGHT=D:\prj\TAXO\.claude\skills\video-studio\node_modules\playwright
//     set TAXO_DEV_PASSWORD=…                     (كلمةُ حسابات التطوير — `COMMANDS.md`)
//     set TAXO_E2E_SHOTS=<مجلّدُ اللقطات>          (اختياريّ)
//     node tools/e2e-call.mjs
//
// **ويخرج بـ١ عند أوّل ما يسقط**، ويطبع جدولاً بما قيس وما لم يُقس — **ولا يُقرأ سكوتُه نجاحاً**.

import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.TAXO_PLAYWRIGHT || "playwright");

const API = process.env.TAXO_API || "http://127.0.0.1:8001/api/v1";
const RIDER_URL = process.env.TAXO_RIDER_URL || "http://127.0.0.1:5173";
const DRIVER_URL = process.env.TAXO_DRIVER_URL || "http://127.0.0.1:5174";
const SHOTS = process.env.TAXO_E2E_SHOTS || null;
// كلمةُ حسابات التطوير (`COMMANDS.md`) **من البيئة لا من الشيفرة** — ماسحُ الرفع يقرأ الحرفيّةَ سرّاً، وهو محقٌّ في الشكل
const PASSWORD = process.env.TAXO_DEV_PASSWORD;
if (!PASSWORD) {
  console.error("✗ TAXO_DEV_PASSWORD غيرُ مضبوط — كلمةُ حسابات التطوير في COMMANDS.md");
  process.exit(1);
}
const RIDER_PHONE = "+962790000021"; // عمر الراكب
const DRIVER_PHONE = "+962790000011"; // زيد السائق
const COUNTRY = "JO";
const FLAGS = ["trip_chat_enabled", "ride_calls_enabled"];
// نقطتا آخر رحلةٍ مقيسةٍ على المكدّس نفسِه — عمّان
const PICKUP = { lat: 31.959, lng: 35.91 };
const DROPOFF = { lat: 31.89662, lng: 35.896878 };

const results = [];
function record(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "✓" : "✗"} ${name}${detail ? ` — ${detail}` : ""}`);
}
function must(name, ok, detail = "") {
  record(name, ok, detail);
  if (!ok) throw new Error(`سقط: ${name}${detail ? ` — ${detail}` : ""}`);
}
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ─────────────────────────────── الخلفية والقاعدة

async function call(method, path, token, body) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { raw: text };
  }
  return { status: response.status, json };
}

/** **جلسةٌ محفوظةٌ تُعاد ما دامت صالحة** (`TAXO_E2E_TOKENS`) — الدخولُ محدودٌ لكلِّ هاتف، **وتشغيلٌ يتكرّر لا يستنفده**. */
const SAVED = process.env.TAXO_E2E_TOKENS || null;
function saved() {
  try {
    return SAVED ? JSON.parse(readFileSync(SAVED, "utf8")) : {};
  } catch {
    return {};
  }
}

async function login(phone, app) {
  const kept = saved()[app];
  if (kept?.access_token && (await call("GET", "/auth/me", kept.access_token)).status === 200) {
    record(`دخول ${app}`, true, "جلسةٌ محفوظة");
    return kept;
  }
  const { status, json } = await call("POST", "/auth/login", null, { phone, password: PASSWORD, country_code: COUNTRY, app });
  // **الجلسةُ في `tokens`** (`LoginResponse`) — ومحاولةٌ واحدةٌ لكلِّ رقم: الدخولُ محدودٌ لكلِّ هاتف (`COMMANDS.md`)
  must(`دخول ${app}`, status === 200 && Boolean(json?.tokens?.access_token), `HTTP ${status}${status === 200 ? "" : ` ${json?.code ?? ""}`}`);
  if (SAVED) writeFileSync(SAVED, JSON.stringify({ ...saved(), [app]: json.tokens }));
  return json.tokens;
}

/** **قاعدةُ التطوير وحدَها** — حاويتُها بالاسم، والأمرُ يُطبع قبل أن يُنفَّذ. */
function sql(statement) {
  return execFileSync("docker", ["exec", "-i", "taxo-rd-db", "psql", "-U", "taxo", "-d", "taxo", "-At", "-F", "|", "-c", statement], {
    encoding: "utf8",
  }).trim();
}

// ─────────────────────────────── المتصفّح

/** يسجّل كلَّ `RTCPeerConnection` يُنشئه التطبيق — **فيُقرأ `iceConnectionState` من الصفحة نفسِها** لا من شاشتها. */
const RECORD_PEERS = () => {
  const Original = window.RTCPeerConnection;
  if (!Original || window.__taxoPeers) return;
  window.__taxoPeers = [];
  const Wrapped = function (...args) {
    const peer = new Original(...args);
    window.__taxoPeers.push(peer);
    return peer;
  };
  Wrapped.prototype = Original.prototype;
  Object.setPrototypeOf(Wrapped, Original);
  window.RTCPeerConnection = Wrapped;
};

/** **ميكروفونٌ يتأخّر عند الطلب** — `getUserMedia` تنتظر `__taxoMicDelayMs` قبل أن تجيب: سؤالُ الإذن مفتوحٌ على الشاشة. */
const DELAY_MIC = () => {
  const media = navigator.mediaDevices;
  if (!media || window.__taxoMicDelayMs !== undefined) return;
  window.__taxoMicDelayMs = 0;
  const original = media.getUserMedia.bind(media);
  media.getUserMedia = async (constraints) => {
    const delay = window.__taxoMicDelayMs;
    if (delay > 0) await new Promise((resolve) => setTimeout(resolve, delay));
    return original(constraints);
  };
};

/** **كم مسجِّلاً بُني وما سجّل** — يُطبع مع سطر الرفع، فرفعٌ غائبٌ يُقرأ سببُه (لم يُبنَ مسجِّل؟ بُني ولم يسجّل شيئاً؟). */
const COUNT_RECORDERS = () => {
  const Original = window.MediaRecorder;
  if (!Original || window.__taxoRecorders) return;
  window.__taxoRecorders = [];
  window.MediaRecorder = class extends Original {
    constructor(...args) {
      super(...args);
      const entry = { state: "new", chunks: 0, bytes: 0 };
      window.__taxoRecorders.push(entry);
      this.addEventListener("start", () => (entry.state = "recording"));
      this.addEventListener("dataavailable", (event) => {
        entry.chunks += 1;
        entry.bytes += event.data.size;
      });
      this.addEventListener("stop", () => (entry.state = "stopped"));
      this.addEventListener("error", (event) => (entry.state = `error ${event.error?.name ?? ""}`));
    }
  };
};

/** **مقبسٌ يُقطع عند الطلب** — `__taxoBlockSockets` يوجّه كلَّ مقبسٍ جديدٍ إلى منفذٍ مغلق (يسقط ولا يُفتح)، و`__taxoSockets`
 *  تحمل القائمَ ليُغلق. **في الصفحة لا في الطريق**: مقبسٌ مُحاكًى في `routeWebSocket` يُعدّ مفتوحاً، فيومض «متصلاً». */
const BLOCKABLE_SOCKETS = () => {
  const Original = window.WebSocket;
  if (!Original || window.__taxoSockets) return;
  window.__taxoSockets = [];
  window.__taxoBlockSockets = false;
  const Wrapped = function (url, protocols) {
    const target = window.__taxoBlockSockets ? "ws://127.0.0.1:9/blocked" : url;
    const socket = protocols === undefined ? new Original(target) : new Original(target, protocols);
    window.__taxoSockets.push(socket);
    return socket;
  };
  Wrapped.prototype = Original.prototype;
  Object.setPrototypeOf(Wrapped, Original);
  window.WebSocket = Wrapped;
};

/** **ما يصل الكبتنَ من المقبس يمرّ من هنا** — و`dropSignals` يُسقط إشاراتِ المكالمة (`call_signal`) كما يُسقطها مقبسٌ مغلق. */
const captainWire = { dropSignals: false, dropped: 0 };
async function filterCaptainSocket(context) {
  await context.routeWebSocket(/\/ws\/driver/, (ws) => {
    const server = ws.connectToServer();
    ws.onMessage((message) => server.send(message));
    server.onMessage((message) => {
      if (captainWire.dropSignals && typeof message === "string" && message.includes('"call_signal"')) {
        captainWire.dropped += 1;
        return;
      }
      ws.send(message);
    });
  });
}

/** **التطبيقُ في الخلفية** — `document.hidden` كما يقوله المتصفّحُ حين يغيب التبويب، ثمّ يُعاد إلى ما يقوله هو. */
async function setHidden(page, hidden) {
  await page.evaluate((value) => {
    if (value) {
      Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
      Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
    } else {
      delete document.hidden;
      delete document.visibilityState;
    }
    document.dispatchEvent(new Event("visibilitychange"));
  }, hidden);
}

async function iceStates(page) {
  return page.evaluate(() => (window.__taxoPeers ?? []).map((peer) => peer.iceConnectionState));
}

async function waitConnected(page, label, timeout = 25_000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    const states = await iceStates(page);
    // **الجلسةُ الأخيرة** — جلساتُ المكالمات السابقة مغلقةٌ في المصفوفة نفسِها
    const last = states[states.length - 1];
    if (last === "connected" || last === "completed") return last;
    await sleep(250);
  }
  const states = await iceStates(page);
  throw new Error(`${label}: لم يبلغ ICE «connected» خلال ${timeout / 1000} ث — ${JSON.stringify(states)}`);
}

async function shot(page, name) {
  if (!SHOTS) return;
  await page.screenshot({ path: join(SHOTS, `${name}.png`) }).catch(() => undefined);
}

async function newApp(browser, url, storage, setup = null) {
  const context = await browser.newContext({
    viewport: { width: 360, height: 800 },
    deviceScaleFactor: 2,
    locale: "ar",
    geolocation: { latitude: PICKUP.lat, longitude: PICKUP.lng },
    permissions: ["microphone", "geolocation"],
  });
  await context.addInitScript(RECORD_PEERS);
  if (setup) await setup(context);
  // **الرموزُ مرّةً لا في كلِّ تحميل** — التطبيقُ يجدّدها، وكتابتُها ثانيةً تعيد رمزاً مستهلَكاً
  await context.addInitScript((entries) => {
    for (const [key, value] of Object.entries(entries)) {
      if (localStorage.getItem(key) === null) localStorage.setItem(key, value);
    }
  }, storage);
  const page = await context.newPage();
  page.on("console", (message) => {
    // **وتحذيراتُ المكالمة** (`[call]` — رفعُ تسجيلٍ رُفض) مع الأخطاء: سطرٌ يُقرأ حين يغيب ما يُنتظر
    const shown = message.type() === "error" || (message.type() === "warning" && message.text().includes("[call]"));
    if (shown) console.log(`   [${new URL(url).port} console] ${message.text().slice(0, 160)}`);
  });
  await page.goto(url, { waitUntil: "domcontentloaded" });
  // **شاشةُ الترحيب فوق الإقلاع** (`.rw` عند الراكب · `.cw` عند الكبتن) — يُنتظر رحيلُها فلا تُلتقط الصورةُ ولا يُنقر تحتها
  await page.locator(".t2.rw, .t2.cw").first().waitFor({ state: "detached", timeout: 40_000 }).catch(() => undefined);
  // **إيماءةٌ أولى** تفتح الصوت (`unlock`) — المتصفّحاتُ تمنعه قبلها
  await page.mouse.click(5, 5).catch(() => undefined);
  return { context, page };
}

/** زرٌّ بنصّه داخل ما يحويه — **والانتظارُ مقيسٌ لا مخمَّن**. */
function button(page, text, scope = "body") {
  return page.locator(`${scope} button`, { hasText: text }).first();
}

// ─────────────────────────────── التجربة

async function main() {
  if (SHOTS) mkdirSync(SHOTS, { recursive: true });

  // ── ما قبل البدء: الخلفيةُ والتطبيقان أحياء
  for (const [label, url] of [
    ["الخلفية", `${API.replace(/\/api\/v1$/, "")}/health`],
    ["تطبيق الراكب (vite preview)", RIDER_URL],
    ["تطبيق الكبتن (vite preview)", DRIVER_URL],
  ]) {
    let status = 0;
    try {
      status = (await fetch(url)).status;
    } catch (caught) {
      status = 0;
    }
    must(`${label} يجيب`, status === 200, `${url} → ${status}`);
  }

  const rider = await login(RIDER_PHONE, "rider");
  const driver = await login(DRIVER_PHONE, "driver");

  const active = await call("GET", "/rides/me/active", rider.access_token);
  must("لا رحلةَ جاريةً للراكب قبل البدء", active.status === 200 && active.json === null, `HTTP ${active.status}`);
  const driverId = sql(`select d.id from drivers d join users u on u.id = d.user_id where u.phone = '${DRIVER_PHONE}'`);
  const busy = sql(`select coalesce(current_ride_id::text, '') from drivers where id = '${driverId}'`);
  must("لا رحلةَ جاريةً للكبتن قبل البدء", busy === "", busy);

  // ── المفتاحان: يُحفظ ما كانا عليه ثمّ يُشعلان (التسجيلُ لا يُمسّ)
  const before = new Map(
    sql(`select feature_key, enabled from feature_flags where country_code = '${COUNTRY}' and feature_key in ('${FLAGS.join("','")}')`)
      .split("\n")
      .filter(Boolean)
      .map((line) => line.split("|"))
      .map(([key, enabled]) => [key, enabled]),
  );
  const restore = [];
  for (const key of FLAGS) {
    if (!before.has(key)) {
      sql(
        `insert into feature_flags (id, country_code, feature_key, enabled, created_at, updated_at) values (gen_random_uuid(), '${COUNTRY}', '${key}', true, now(), now())`,
      );
      restore.push(`delete from feature_flags where country_code = '${COUNTRY}' and feature_key = '${key}'`);
    } else if (before.get(key) !== "t") {
      sql(`update feature_flags set enabled = true, updated_at = now() where country_code = '${COUNTRY}' and feature_key = '${key}'`);
      restore.push(`update feature_flags set enabled = false, updated_at = now() where country_code = '${COUNTRY}' and feature_key = '${key}'`);
    }
  }
  record("المفتاحان مشتعلان للتجربة", true, `أُشعل ${restore.length} وسيُعادان`);
  const recordingOff = sql(`select coalesce(bool_or(call_recording_enabled), false) from service_settings where country_code = '${COUNTRY}'`);
  record("التسجيلُ مطفأٌ ولم يُمسّ", recordingOff === "f", recordingOff);

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      "--autoplay-policy=no-user-gesture-required",
    ],
  });

  let rideId = null;
  /** الصفحتان — **ولقطتاهما عند السقوط**: ما على الشاشة لحظةَ الفشل أصدقُ من رسالة الانتظار */
  const open = [];
  try {
    // ── الكبتنُ يبدأ الاستقبال من رئيسيته (المقبسُ هو الاستقبال — والإشارةُ تمرّ منه)
    const captain = await newApp(
      browser,
      DRIVER_URL,
      {
        "taxo.driver.access_token": driver.access_token,
        "taxo.driver.refresh_token": driver.refresh_token,
        "taxo.driver.welcome.intro.seen": "1",
        "taxo.driver.welcome.seen": "1",
        "taxo.driver.permission.walk.done": "1",
      },
      filterCaptainSocket,
    );
    open.push(["driver", captain.page]);
    const go = captain.page.locator(".t2-hm-go").first();
    await go.waitFor({ state: "visible", timeout: 30_000 });
    // **الزرُّ يُرسم قبل أن يُعرف الاشتراك** — ونقرةٌ قبله تقرأ «غيرُ مشترك» فتذهب إلى «الاشتراك» (`toggleOnline`)؛ فيُمهَل ويُعاد
    for (let attempt = 0; attempt < 4; attempt += 1) {
      await sleep(4_000);
      if (await captain.page.locator(".t2-hm-go.on").count()) break;
      if (new URL(captain.page.url()).pathname !== "/") await captain.page.goto(DRIVER_URL, { waitUntil: "domcontentloaded" });
      await go.click({ timeout: 15_000 }).catch(() => undefined);
    }
    await captain.page.locator(".t2-hm-go.on").first().waitFor({ timeout: 20_000 });
    must("الكبتنُ يستقبل (المقبسُ مفتوح)", true);
    await shot(captain.page, "01-driver-home");
    // البثُّ الأوّلُ للموقع يُدخله الفهرسَ الجغرافيّ — ثلاثُ ثوانٍ دورتُه
    await sleep(4_000);

    // ── الراكبُ يطلب رحلةً بالباب نفسِه، والكبتنُ يقبلها
    const created = await call("POST", "/rides", rider.access_token, {
      pickup: PICKUP,
      dropoff: DROPOFF,
      vehicle_category: "economy",
      pickup_address: "اختبار المكالمة — الانطلاق",
      dropoff_address: "اختبار المكالمة — الوجهة",
    });
    must("طلبُ الرحلة", created.status === 201, `HTTP ${created.status} ${created.json?.code ?? ""}`);
    rideId = created.json.id;
    let accepted = null;
    for (let attempt = 0; attempt < 40 && !accepted; attempt += 1) {
      const answer = await call("POST", `/rides/${rideId}/accept`, driver.access_token);
      if (answer.status === 200) accepted = answer.json;
      else await sleep(500);
    }
    must("الكبتنُ قبل الرحلة (نافذةُ المحادثة والمكالمة فُتحت)", accepted?.status === "accepted", accepted?.status ?? "لم يصله العرض");

    const passenger = await newApp(
      browser,
      RIDER_URL,
      {
        "taxo.access_token": rider.access_token,
        "taxo.refresh_token": rider.refresh_token,
        "taxo.welcome.seen": "1",
      },
      async (context) => {
        await context.addInitScript(DELAY_MIC);
        await context.addInitScript(BLOCKABLE_SOCKETS);
        await context.addInitScript(COUNT_RECORDERS);
      },
    );
    open.push(["rider", passenger.page]);

    // ── الزرّان في ورقة الرحلة عند الطرفين
    const riderCall = button(passenger.page, "اتصال", ".t2-cm-actions");
    const riderChat = button(passenger.page, "رسالة", ".t2-cm-actions");
    await riderCall.waitFor({ timeout: 30_000 });
    must("«رسالة» و«اتصال» في تتبّع الرحلة (R08)", await riderChat.isVisible());
    const driverCall = button(captain.page, "اتصال", ".t2-cm-actions");
    await driverCall.waitFor({ timeout: 30_000 });
    must("«رسالة» و«اتصال» في ورقة الكبتن (C06)", true);
    await shot(passenger.page, "02-rider-tracking-buttons");
    await shot(captain.page, "03-driver-ride-buttons");

    // ── ١) الراكبُ يتّصل والكبتنُ يردّ، ثمّ الراكبُ يُنهي
    await riderCall.click();
    const incoming = captain.page.locator('[role="dialog"][aria-label="مكالمةٌ واردة"]');
    await incoming.waitFor({ timeout: 20_000 });
    must("شاشةُ الوارد عند الكبتن", true);
    await shot(captain.page, "04-driver-incoming");
    await shot(passenger.page, "05-rider-dialing");
    await button(captain.page, "ردّ", '[aria-label="مكالمةٌ واردة"]').click();
    const riderIce = await waitConnected(passenger.page, "الراكب");
    const driverIce = await waitConnected(captain.page, "الكبتن");
    must("ICE متّصلٌ عند الطرفين", true, `الراكب ${riderIce} · الكبتن ${driverIce}`);
    const clock = passenger.page.locator('.t2-cm-call-line[dir="ltr"]');
    await clock.waitFor({ timeout: 10_000 });
    const first = (await clock.textContent())?.trim();
    await sleep(2_600);
    const second = (await clock.textContent())?.trim();
    must("المدّةُ تعدّ", /^\d\d:\d\d$/.test(first ?? "") && first !== second, `${first} → ${second}`);
    await shot(passenger.page, "06-rider-talking");
    await shot(captain.page, "07-driver-talking");
    await button(passenger.page, "إنهاء", ".t2-cm-controls").click();
    await captain.page.locator(".t2-cm-call").waitFor({ state: "detached", timeout: 15_000 });
    must("«إنهاء» عند الراكب يُغلقها عند الكبتن", true);
    await passenger.page.locator(".t2-cm-call").waitFor({ state: "detached", timeout: 10_000 });
    const firstRow = sql(
      `select status, coalesce(end_reason::text, ''), coalesce(duration_seconds, -1) from ride_calls where ride_id = '${rideId}' order by started_at desc limit 1`,
    );
    must("سجلُّها في القاعدة: انتهت · اكتملت بمدّة", /^ended\|completed\|\d+$/.test(firstRow) && !firstRow.endsWith("|-1"), firstRow);

    // ── ١-ب) **المتصَلُ به فاته العرض** — مقبسُه لا يحمل إشارةً حتى يردّ (كمن ردّ من إشعارٍ أو عاد من الخلفية) ⇒ يُعاد بعد «ردّ»
    captainWire.dropped = 0;
    captainWire.dropSignals = true;
    await riderCall.click();
    await incoming.waitFor({ timeout: 20_000 });
    for (let waited = 0; captainWire.dropped === 0 && waited < 10_000; waited += 250) await sleep(250);
    await sleep(1_500); // **ومرشّحوه** — يخرجون بعد العرض بلحظة
    captainWire.dropSignals = false;
    must("سقط عند الكبتن عرضُ المتصل ومرشّحوه قبل «ردّ»", captainWire.dropped > 0, `${captainWire.dropped} إشارة`);
    await button(captain.page, "ردّ", '[aria-label="مكالمةٌ واردة"]').click();
    const resentRider = await waitConnected(passenger.page, "الراكب (عرضٌ مُعاد)");
    const resentDriver = await waitConnected(captain.page, "الكبتن (عرضٌ مُعاد)");
    must("ICE متّصلٌ وقد فات الكبتنَ العرضُ الأوّل", true, `الراكب ${resentRider} · الكبتن ${resentDriver}`);
    await button(passenger.page, "إنهاء", ".t2-cm-controls").click();
    await captain.page.locator(".t2-cm-call").waitFor({ state: "detached", timeout: 15_000 });
    await passenger.page.locator(".t2-cm-call").waitFor({ state: "detached", timeout: 10_000 });

    // ── ١-ج) **«إنهاء» والميكروفونُ يُسأل** ⇒ لا مكالمةَ عند الخادم ولا رنينَ عند الكبتن
    const callsBefore = sql(`select count(*) from ride_calls where ride_id = '${rideId}'`);
    await passenger.page.evaluate(() => {
      window.__taxoMicDelayMs = 4_000;
    });
    const rangCaptain = incoming.waitFor({ timeout: 9_000 }).then(
      () => true,
      () => false,
    );
    await riderCall.click();
    await button(passenger.page, "إنهاء", ".t2-cm-controls").click();
    await passenger.page.locator(".t2-cm-call").waitFor({ state: "detached", timeout: 5_000 });
    const rang = await rangCaptain;
    await passenger.page.evaluate(() => {
      window.__taxoMicDelayMs = 0;
    });
    const callsAfter = sql(`select count(*) from ride_calls where ride_id = '${rideId}'`);
    must("«إنهاء» والميكروفونُ يُسأل لا يبدأ مكالمةً عند الخادم", callsAfter === callsBefore, `${callsBefore} → ${callsAfter}`);
    must("ولا رنينَ عند الكبتن", !rang);

    // ── ١-د) **رفعُ التسجيل لا يسبق الإنهاء** — **والتسجيلُ لا يُشعل عند الخادم** (يبقى مطفأً): متصفّحُ الراكب وحدَه يُقال له
    //    «مسجَّلة» بتعديل ردِّ البدء في الطريق، فيُري التنبيهَ ويسجّل ويرفع. **وجوابُ الإنهاء يُؤخَّر عمداً** فيُقاس الترتيب: الرفعُ
    //    لا يخرج قبل أن يعود. والخادمُ يردّ الرفعَ `call_recording_refused` (المكالمةُ عنده غيرُ مسجَّلة) — فلا ملفَّ يُحفظ.
    const order = [];
    await passenger.page.route(/\/api\/v1\/rides\/[^/]+\/calls$/, async (route) => {
      const response = await route.fetch();
      await route.fulfill({ response, json: { ...(await response.json()), recording: true } });
    });
    await passenger.page.route(/\/api\/v1\/calls\/[^/]+\/end$/, async (route) => {
      order.push(["end-sent", Date.now()]);
      await sleep(1_500);
      const response = await route.fetch();
      order.push(["end-answered", Date.now()]);
      await route.fulfill({ response });
    });
    await passenger.page.route(/\/api\/v1\/calls\/[^/]+\/recording$/, async (route) => {
      order.push(["upload", Date.now()]);
      await route.continue();
    });
    await riderCall.click();
    await button(passenger.page, "متابعة", ".t2-cm-consent").click();
    await incoming.waitFor({ timeout: 20_000 });
    await button(captain.page, "ردّ", '[aria-label="مكالمةٌ واردة"]').click();
    await waitConnected(passenger.page, "الراكب (تسجيل)");
    await waitConnected(captain.page, "الكبتن (تسجيل)");
    await sleep(2_500); // **صوتٌ يُسجَّل** — المسجِّلُ يبدأ مع وصول الصوت، ويقطع كلَّ ثانية
    await button(passenger.page, "إنهاء", ".t2-cm-controls").click();
    for (let waited = 0; waited < 15_000 && !order.some(([kind]) => kind === "upload"); waited += 250) await sleep(250);
    await captain.page.locator(".t2-cm-call").waitFor({ state: "detached", timeout: 15_000 });
    await sleep(4_000); // **ومحاولتُه الثانيةُ إن رُفضت** — تنتهي قبل أن تُرفع الطرق
    await passenger.page.unrouteAll({ behavior: "ignoreErrors" });
    const endAnswered = order.find(([kind]) => kind === "end-answered")?.[1];
    const firstUpload = order.find(([kind]) => kind === "upload")?.[1];
    const recorders = await passenger.page.evaluate(() => JSON.stringify(window.__taxoRecorders ?? null));
    const trail = `${order.map(([kind, at]) => `${kind}+${at - order[0][1]}`).join(" · ")} · المسجِّلات ${recorders}`;
    must("التسجيلُ رُفع بعد المكالمة", firstUpload !== undefined, trail);
    must("ولم يخرج قبل أن يعود جوابُ الإنهاء", endAnswered !== undefined && firstUpload >= endAnswered, trail);
    const stored = sql(`select count(*) from ride_calls where ride_id = '${rideId}' and recording_path is not null`);
    record("ولا ملفَّ حُفظ — التسجيلُ مطفأٌ عند الخادم", stored === "0", stored);

    // ── ٢) الكبتنُ يتّصل والراكبُ يردّ، ثمّ الكبتنُ يُنهي
    await driverCall.click();
    const riderIncoming = passenger.page.locator('[role="dialog"][aria-label="مكالمةٌ واردة"]');
    await riderIncoming.waitFor({ timeout: 20_000 });
    must("شاشةُ الوارد عند الراكب", true);
    await shot(passenger.page, "08-rider-incoming");
    await button(passenger.page, "ردّ", '[aria-label="مكالمةٌ واردة"]').click();
    await waitConnected(passenger.page, "الراكب (٢)");
    await waitConnected(captain.page, "الكبتن (٢)");
    must("ICE متّصلٌ في المكالمة الثانية", true);
    await sleep(1_500);
    await button(captain.page, "إنهاء", ".t2-cm-controls").click();
    await passenger.page.locator(".t2-cm-call").waitFor({ state: "detached", timeout: 15_000 });
    must("«إنهاء» عند الكبتن يُغلقها عند الراكب", true);
    await captain.page.locator(".t2-cm-call").waitFor({ state: "detached", timeout: 10_000 });

    // ── ٣) لا يُردّ ⇒ «لم يُجب» عند المتصل بعد مهلة الرنين
    await riderCall.click();
    await captain.page.locator('[role="dialog"][aria-label="مكالمةٌ واردة"]').waitFor({ timeout: 20_000 });
    const unanswered = passenger.page.locator(".t2-cm-call-line.bad", { hasText: "لم يُجب" });
    await unanswered.waitFor({ timeout: 45_000 });
    must("«لم يُجب» عند المتصل بعد مهلة الرنين", true);
    await shot(passenger.page, "09-rider-unanswered");
    await captain.page.locator('[role="dialog"][aria-label="مكالمةٌ واردة"]').waitFor({ state: "detached", timeout: 15_000 });
    must("الوارد يُطوى عند الكبتن", true);
    const thirdRow = sql(
      `select status, coalesce(end_reason::text, '') from ride_calls where ride_id = '${rideId}' order by started_at desc limit 1`,
    );
    must("سجلُّها في القاعدة: لم يُجب", thirdRow === "ended|no_answer", thirdRow);

    // ── ٣-ب) **«أعد المحاولة» بشروط «اتصال»** — مقبسُ الراكب يسقط ⇒ لا تُرسم؛ ويعود ⇒ تعود
    const retryButton = button(passenger.page, "أعد المحاولة", ".t2-cm-after");
    must("«أعد المحاولة» بعد «لم يُجب» والمقبسُ حيّ", await retryButton.isVisible());
    await passenger.page.evaluate(() => {
      window.__taxoBlockSockets = true;
      for (const socket of window.__taxoSockets ?? []) socket.close();
    });
    await riderCall.waitFor({ state: "detached", timeout: 10_000 });
    must("المقبسُ ساقط ⇒ «أعد المحاولة» لا تُرسم", (await retryButton.count()) === 0);
    must("و«راسِله بدلاً من ذلك» باقية", await button(passenger.page, "راسِله بدلاً من ذلك", ".t2-cm-after").isVisible());
    await passenger.page.evaluate(() => {
      window.__taxoBlockSockets = false;
    });
    await retryButton.waitFor({ timeout: 30_000 });
    must("عاد المقبس ⇒ «أعد المحاولة» تعود", true);
    await shot(passenger.page, "09b-rider-retry-back");
    await button(passenger.page, "إغلاق", ".t2-cm-after").click();

    // ── ٤) المحادثة: رسالةٌ وشارتُها و«قُرئت»، ورقمُ هاتفٍ يُردّ
    await riderChat.click();
    const composer = passenger.page.locator(".t2-cm-input");
    await composer.waitFor({ timeout: 15_000 });
    const notice = (await passenger.page.locator(".t2-cm-notice").textContent())?.trim();
    must("سطرُ المراجعة من الخادم أعلى المحادثة", Boolean(notice?.includes("قد يراجع فريقُ TAXO")), notice ?? "");
    await composer.fill("أنا عند الباب الرئيسي");
    // **كم يستغرق بابُ الإرسال** — يُقاس لا يُفترض: الرسالةُ تظهر من المقبس، والجوابُ ينتظر إشعارَ الطرف الآخر
    const sentAt = Date.now();
    const posted = passenger.page
      .waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          /\/rides\/[^/]+\/chat$/.test(response.url()) &&
          (response.request().postData() ?? "").includes("الرئيسي"),
        { timeout: 90_000 },
      )
      .then((response) => ({ status: response.status(), ms: Date.now() - sentAt }))
      .catch(() => null);
    await passenger.page.locator(".t2-cm-send").click();
    await passenger.page.locator(".t2-cm-row.mine .t2-cm-bubble", { hasText: "أنا عند الباب الرئيسي" }).waitFor({ timeout: 10_000 });
    record("الرسالةُ ظاهرةٌ عند مرسلها", true, `بعد ${Date.now() - sentAt} م.ث`);
    must("الحقلُ فارغٌ بعد الإرسال (لا ينتظر جوابَ الخادم)", ((await composer.inputValue()) ?? "") === "");
    const badge = captain.page.locator(".t2-cm-actions .t2-cm-count");
    await badge.waitFor({ timeout: 10_000 });
    must("شارةُ ما لم يُقرأ عند الكبتن", ((await badge.textContent()) ?? "").trim() === "1");
    const alert = captain.page.locator(".t2-notice-title", { hasText: "رسالةٌ جديدة من الراكب" });
    must("وبلاغُ التطبيق يقولها والمحادثةُ مغلقة", await alert.first().isVisible().catch(() => false));
    await shot(captain.page, "10-driver-unread-banner");
    await button(captain.page, "رسالة", ".t2-cm-actions").click();
    await captain.page.locator(".t2-cm-bubble", { hasText: "أنا عند الباب الرئيسي" }).waitFor({ timeout: 10_000 });
    await passenger.page.locator(".t2-cm-read").waitFor({ timeout: 10_000 });
    must("«قُرئت» عند الراكب بعد أن فتحها الكبتن", true);
    await composer.fill("رقمي 0791234567");
    await passenger.page.locator(".t2-cm-send").click();
    const refusal = passenger.page.locator(".t2-cm-error");
    await refusal.waitFor({ timeout: 10_000 });
    const refusalText = ((await refusal.textContent()) ?? "").trim();
    must("رقمُ الهاتف يُردّ بنصّ الخادم", refusalText.includes("لا تُرسَل أرقامُ الهواتف في المحادثة."), refusalText);
    must("والنصُّ المرفوضُ يعود إلى الحقل", ((await composer.inputValue()) ?? "").includes("0791234567"));
    const latency = await posted;
    record("زمنُ جواب بابِ الإرسال", latency !== null && latency.status === 201, latency ? `HTTP ${latency.status} بعد ${latency.ms} م.ث` : "لم يصل في ٩٠ ث");

    // ── ٤-ب) **ورقةُ الكبتن مفتوحةٌ والتطبيقُ في الخلفية** ⇒ لا «قُرئت» حتى يعود
    const lastFromRider = `select coalesce(read_at::text, '') from ride_messages where ride_id = '${rideId}' and sender_role = 'rider' order by created_at desc limit 1`;
    await setHidden(captain.page, true);
    await composer.fill("وصلتُ — أنتظرك عند الباب");
    await passenger.page.locator(".t2-cm-send").click();
    await captain.page.locator(".t2-cm-bubble", { hasText: "أنتظرك عند الباب" }).waitFor({ timeout: 10_000 });
    await sleep(3_000); // **أطولُ من تأجيل التعليم** (٦٠٠ م.ث) وجولتِه
    const whileAway = sql(lastFromRider);
    must("التطبيقُ في الخلفية لا يعلّمها مقروءة", whileAway === "", whileAway || "غيرُ مقروءة");
    await setHidden(captain.page, false);
    let readOnReturn = "";
    for (let waited = 0; waited < 10_000 && !readOnReturn; waited += 500) {
      await sleep(500);
      readOnReturn = sql(lastFromRider);
    }
    must("وعودتُه إليها تعلّمها مقروءة", readOnReturn !== "", readOnReturn || "لم تُعلَّم في ١٠ ث");
    await shot(passenger.page, "11-rider-chat");
    await shot(captain.page, "12-driver-chat");
    await passenger.page.locator(".t2-cm-head .t2-cm-round").first().click();
    await captain.page.locator(".t2-cm-head .t2-cm-round").first().click();

    // ── والختام: الكبتنُ يلغي (بلا رسمٍ على أحد) ⇒ الزرّان يغيبان
    const cancelled = await call("POST", `/rides/${rideId}/cancel`, driver.access_token, { reason: "اختبار المكالمة (e2e) — إلغاءُ الكبتن بلا رسم" });
    must("الكبتنُ ألغى رحلةَ الاختبار", cancelled.status === 200 && cancelled.json?.status === "cancelled_by_driver", `HTTP ${cancelled.status}`);
    const fee = sql(`select cancellation_fee from rides where id = '${rideId}'`);
    record("لا رسمَ إلغاءٍ على أحد", Number(fee) === 0, fee);
    await passenger.page.locator(".t2-cm-actions").waitFor({ state: "detached", timeout: 15_000 });
    must("الزرّان يغيبان بانتهاء الرحلة (الراكب)", true);
    rideId = null;
    await captain.page.locator(".t2-hm-go.on").first().click().catch(() => undefined);
  } catch (caught) {
    for (const [name, page] of open) await shot(page, `fail-${name}`);
    throw caught;
  } finally {
    if (rideId) {
      const cancelled = await call("POST", `/rides/${rideId}/cancel`, driver.access_token, { reason: "اختبار المكالمة (e2e) — تنظيفٌ بعد سقوط" });
      record("تنظيف: أُلغيت رحلةُ الاختبار", cancelled.status === 200, `HTTP ${cancelled.status}`);
    }
    await call("POST", "/drivers/me/offline", driver.access_token).catch(() => undefined);
    for (const statement of restore) sql(statement);
    const after = sql(
      `select count(*) filter (where enabled) from feature_flags where country_code = '${COUNTRY}' and feature_key in ('${FLAGS.join("','")}')`,
    );
    record("تنظيف: المفتاحان كما كانا", Number(after) === [...before.values()].filter((value) => value === "t").length, `مشتعلٌ الآن: ${after}`);
    await browser.close();
  }
}

main()
  .then(() => {
    const failed = results.filter((row) => !row.ok);
    console.log(`\n${failed.length ? "✗" : "✓"} e2e-call — ${results.length - failed.length}/${results.length}`);
    process.exit(failed.length ? 1 : 0);
  })
  .catch((caught) => {
    console.error(`\n✗ e2e-call — ${caught.message}`);
    process.exit(1);
  });
