/** إشعاراتُ النظام على الجهاز — **الطريقُ الأصليّ للراكب كما للكبتن** (قرارُ المالك ٢٠٢٦-٠٩-٢٩).
 *
 * **والعلّةُ مقيسةٌ على الكبتن قبل الراكب** (S21، 2026-08-21): `Notification`
 * و`PushManager` **غائبان في WebView أندرويد**، فمسارُ `firebase/messaging`
 * الويبيُّ يردّ `null` قبل أن يبدأ — **وكان الراكبُ عليه وحدَه**، فلم يكن له
 * رمزُ جهازٍ على الهاتف قطّ. **وعلى iOS لا Web Push في WKWebView أصلاً.**
 *
 * **والرمزُ رمزُ FCM على المنصّتين**: أندرويد يعطيه لأن `google-services.json`
 * مطبَّق، وiOS يعطيه لأن `AppDelegate` يحوّل رمزَ APNs عبر FirebaseMessaging
 * — **فالخلفيةُ ترسل بـFCM وحدَه ولا تعرف المنصّة**.
 *
 * **والمتصفّحُ باقٍ على طريقه** (`lib/firebase.ts`): تطبيقُ الويب ليس «داخل
 * التطبيق»، ومسارُه يعمل حيث يوجد `PushManager`.
 *
 * نسخةٌ من `driver-app/src/lib/push.ts` **بلا جولة الأذونات** — تلك للكبتن
 * وحدَه (§57)، والراكبُ يُسأل مرّةً بعد الدخول كما كان على الويب.
 */

import { Capacitor } from "@capacitor/core";
import { PushNotifications } from "@capacitor/push-notifications";

export type PushState = "granted" | "denied" | "unsupported";

export interface PushRegistration {
  state: PushState;
  /** رمزُ الجهاز — يُسلَّم للخلفية كما هو، ولا يُطبع ولا يُسجَّل. */
  token: string | null;
}

/** يطلب الإذنَ ويعيد الرمز — **أو يسمّي سببَ غيابه**. */
export async function registerNativePush(): Promise<PushRegistration> {
  if (!Capacitor.isNativePlatform()) return { state: "unsupported", token: null };

  let status = await PushNotifications.checkPermissions();
  if (status.receive === "prompt" || status.receive === "prompt-with-rationale") {
    status = await PushNotifications.requestPermissions();
  }
  if (status.receive !== "granted") return { state: "denied", token: null };

  // **الرمزُ يصل بحدثٍ لا بردِّ نداء** — و`registrationError` هو ما يُطلقه
  // `AppDelegate` على iOS حين لا يُحوَّل الرمزُ (لا `GoogleService-Info.plist`)،
  // **فلا يصل الخلفيةَ رمزُ APNs على أنه رمزُ FCM**
  const token = await new Promise<string | null>((resolve) => {
    let settled = false;
    const done = (value: string | null) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    void PushNotifications.addListener("registration", (item) => done(item.value));
    void PushNotifications.addListener("registrationError", () => done(null));
    void PushNotifications.register();
    // **مهلةٌ كي لا يعلَّق الدخولُ على خدمةٍ بعيدة**
    window.setTimeout(() => done(null), 15_000);
  });

  return { state: "granted", token };
}

/** **وصل رمزُ هذا الجهاز إلى الخلفية في هذه الجلسة** — فالغائبُ يصله الإشعارُ من النظام. */
let ready = false;

export function markPushReady(): void {
  ready = true;
}

/** **الغائبُ عن التطبيق يسمع إشعارَه من النظام بصوت قناته** (§٦١-ل/٣) — فلا تُعزف
 *  نغمةُ الويب فوقه. **ومن لا رمزَ له** (إذنٌ مرفوض، أو الحزمةُ المنشورةُ اليومَ
 *  وهي بلا إضافة الإشعارات) **يبقى على نغمة الويب كما كان** — فلا يُسلب صوتاً لا
 *  بديلَ له. */
export function heardFromSystem(): boolean {
  return ready && document.hidden;
}

/** قنواتُ المجموعة الثانية في هذه الحزمة — **تُنشئها الحزمةُ عند إقلاعها**
 *  (`TaxoChannels.java`)، **وغيابُ واحدةٍ منها يعني حزمةً أقدم**. */
const CHANNELS_V2 = [
  "taxo.accepted",
  "taxo.approaching",
  "taxo.arrived",
  "taxo.started",
  "taxo.ended",
  "taxo.payment",
  "taxo.general",
];

/** **قناةُ المجموعة الثالثة** (§٦٦-ج/١٧، الحزمةُ «2.0») — تُنشئها الحزمةُ التي تحمل خدمةَ رنين المكالمة
 *  (`CallMessagingService`)، **فوجودُها شاهدٌ على الخدمة**: بها يرسل الخادمُ الرنينَ بياناتٍ وحدَها ترسمها الخدمة.
 *  **ولا تُبلَّغ دون الثانية كاملةً** — الثالثةُ تزيد عليها ولا تحلّ محلّها. */
const CALL_CHANNEL = "taxo.call";

/** **ما أجاب به `channelSet` آخرَ مرّة** — وهو ما يُرسَل مع رمز الجهاز (`session.tsx`). */
let reported: number | undefined;

/** **إصدارُ مجموعة القنوات على الجهاز فعلاً** (§٦١-ل/٥) — يُسأل أندرويد ولا يُفترض:
 *  الحزمُ تُحمِّل شاشاتها من خادم، فهذه الشيفرةُ قد تكون أحدثَ من الحزمة التي تحملها.
 *  **و`undefined` حزمةٌ أقدم** يُرسل إليها الخادمُ كما اليوم. **و`2` كما كانت حرفاً** — حزمةٌ بقنوات
 *  الأحداث بلا خدمة الرنين يصلها الرنينُ إشعاراً يرسمه النظام؛ **و`3`** يصلها بياناتٍ ترسمها الخدمة. */
export async function channelSet(): Promise<number | undefined> {
  if (Capacitor.getPlatform() !== "android") return undefined;
  reported = undefined;
  try {
    const { channels } = await PushNotifications.listChannels();
    const present = new Set(channels.map((channel) => channel.id));
    if (!CHANNELS_V2.every((id) => present.has(id))) return undefined;
    reported = present.has(CALL_CHANNEL) ? 3 : 2;
    return reported;
  } catch {
    return undefined;
  }
}

/** **أيرنّ هذا الجهازُ المكالمةَ بخدمته الأصليّة والتطبيقُ غائب؟** (§٦٦-ج/١٧، الحزمةُ «2.0»)
 *
 *  بلّغ الخادمَ بالمجموعة الثالثة **ووصله رمزُه** (`markPushReady` بعد التسجيل) — فالخادمُ يرسل إليه الرنينَ بياناتٍ ترسمها
 *  خدمتُه على مجرى الرنين (`CallAlert.java`). **فلا تُعزف حلقةُ الويب فوقها وهو غائب** (`comms.tsx → ringTone`)، وإلا رنّ
 *  الهاتفُ رنينين لمكالمةٍ واحدة. **وما دون الثالثة `false`** — لا خدمةَ هناك ترنّ، فالحلقةُ وحدَها الرنين كما كانت. */
export function ringsNatively(): boolean {
  return ready && reported !== undefined && reported >= 3;
}

/** ما يصل والتطبيقُ مفتوح — **النظامُ لا يرسمه**، فتعرضه الشاشة.
 *  **ومعه `data`** — نوعُه يختار صوتَه (§٦١-ل/٣)، كما في طريق المتصفّح (`onForegroundMessage`). */
export async function listenToPush(
  received: (item: { title?: string; body?: string; data?: Record<string, string> }) => void,
): Promise<() => void> {
  if (!Capacitor.isNativePlatform()) return () => undefined;
  const handle = await PushNotifications.addListener("pushNotificationReceived", (item) =>
    received({
      title: item.title,
      body: item.body,
      data: (item.data ?? {}) as Record<string, string>,
    }),
  );
  return () => void handle.remove();
}
