/** إشعاراتُ النظام على الجهاز — **المسارُ الأصليّ، لا الويب**.
 *
 * **العلّةُ مقيسةٌ على S21 (2026-08-21)**: `Notification` و`PushManager`
 * **غائبان في WebView أندرويد** (`false`/`false`)، فمسارُ `firebase/messaging`
 * الويبيُّ **يستحيل على الهاتف مهما اكتمل عقدُ FCM**. و`device_tokens` كانت
 * **صفرَ صفوفٍ منذ نشأة القاعدة** — فما من إشعارٍ كان له عنوانٌ يذهب إليه.
 *
 * **والطريقُ الأصليُّ كان مهيّأً كلَّه إلا الإضافة**: `google-services.json`
 * مطبَّقٌ في Gradle، و`POST_NOTIFICATIONS` مُعلَنٌ في البيان — **ولا شيءَ
 * يناديهما**. «بابٌ بلا زرّ» في ثوبِ منصّة.
 *
 * ---
 *
 * **والحالاتُ أربعٌ لا ثلاث، والرابعةُ هي التي تُقال للكبتن صراحةً:**
 *
 * | الحال | من يعرض | ما يقع |
 * |---|---|---|
 * | التطبيقُ مفتوح | التطبيقُ نفسُه | `pushNotificationReceived` — والنظامُ لا يرسم شيئاً |
 * | في الخلفية | النظام | صفٌّ في الشريط، والنقرُ يفتح الوجهة |
 * | مغلقٌ تماماً | النظام | كذلك — والإقلاعُ البارد يسلّم النقرةَ بعد تعليق المستمعين |
 * | **الإذنُ مرفوض** | **التطبيقُ يقولها** | لا رمزَ، فلا إشعار — **ويُخبَر أنه لن تصله طلبات وهو خارج التطبيق** |
 *
 * **والرابعةُ شرطُ المالك بنصِّه**: «من رفض الإذن لا تصله طلبات، فلا يظنّ
 * نفسه عاملاً». **وصمتٌ هنا يُقرأ «لا طلبات اليوم»** — وهو أسوأُ ما يُقرأ في
 * تطبيقٍ يعيش صاحبُه منه.
 *
 * **ودقّةُ الجملة تهمّ**: الطلبُ يصل عبر المقبس **والتطبيقُ مفتوح** ولو كان
 * الإذنُ مرفوضاً. فالجملةُ تقول «وأنت خارج التطبيق» ولا تقول «لن تصلك
 * طلبات» مطلقةً — **وجملةٌ أوسعُ من الحقيقة تُكذَّب أولَ مرةٍ يصل فيها طلب،
 * فيُهمل ما بعدها**.
 */

import { Capacitor } from "@capacitor/core";
import { PushNotifications } from "@capacitor/push-notifications";

import { noteRefusal } from "@/lib/permission-walk";

export type PushState = "granted" | "denied" | "unsupported";

export interface PushRegistration {
  state: PushState;
  /** رمزُ الجهاز — يُسلَّم للخلفية كما هو، ولا يُطبع ولا يُسجَّل. */
  token: string | null;
}

/** يطلب الإذنَ ويعيد الرمز — **أو يسمّي سببَ غيابه**.
 *
 * **ولا يُطلب الإذنُ عند الإقلاع**: يُطلب حين يصير للكبتن حسابٌ فعلاً، فطلبٌ
 * على شاشةٍ فارغةٍ يُرفض ثم **لا يُسأل ثانية** (قاعدةٌ مكتوبةٌ في البيان).
 */
export async function registerNativePush(): Promise<PushRegistration> {
  if (!Capacitor.isNativePlatform()) return { state: "unsupported", token: null };

  let status = await PushNotifications.checkPermissions();
  if (status.receive === "prompt" || status.receive === "prompt-with-rationale") {
    status = await PushNotifications.requestPermissions();
  }
  if (status.receive !== "granted") return { state: "denied", token: null };

  // **الرمزُ يصل بحدثٍ لا بردِّ نداء**: `register()` يبدأ التسجيل، والرمزُ
  // يأتي في `registration` — فمن ينتظر قيمةً من `register` ينتظر ما لا يأتي
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
    // **مهلةٌ كي لا يعلَّق الدخولُ على خدمةٍ بعيدة**: غيابُ الرمز إشعاراتٌ لا
    // تصل، وتعليقُ الجلسة عليه شاشةٌ لا تفتح
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
 *  نغمةُ الويب فوقه. **ومن لا رمزَ له** (إذنٌ مرفوض، حزمةٌ بلا إضافة) **يبقى على
 *  نغمة الويب كما كان** — فلا يُسلب صوتاً لا بديلَ له. */
export function heardFromSystem(): boolean {
  return ready && document.hidden;
}

/** قنواتُ المجموعة الثانية في هذه الحزمة — **تُنشئها الحزمةُ عند إقلاعها**
 *  (`TaxoChannels.java`)، **وغيابُ واحدةٍ منها يعني حزمةً أقدم**. */
const CHANNELS_V2 = ["taxo.offer.v2", "taxo.ended", "taxo.payment", "taxo.general"];

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

/** يعلّق مستمعَي «وصل» و«نُقر» — ويعيد ما يفكّهما.
 *  **و«وصل» يحمل العنوانَ والنصَّ مع `data`** — بهما يُرسم البلاغُ داخل التطبيق (§٦١-ل/٣). */
export async function listenToPush(handlers: {
  received: (data: Record<string, string>, notice: { title?: string; body?: string }) => void;
  tapped: (data: Record<string, string>) => void;
}): Promise<() => void> {
  if (!Capacitor.isNativePlatform()) return () => undefined;

  const received = await PushNotifications.addListener(
    "pushNotificationReceived",
    (item) =>
      handlers.received((item.data ?? {}) as Record<string, string>, {
        title: item.title,
        body: item.body,
      }),
  );
  const tapped = await PushNotifications.addListener(
    "pushNotificationActionPerformed",
    (item) =>
      handlers.tapped(
        (item.notification.data ?? {}) as Record<string, string>,
      ),
  );
  return () => {
    void received.remove();
    void tapped.remove();
  };
}

/** يطلب إذنَ الإشعارات وحدَه — **بلا تسجيلِ جهاز** (جولةُ أوّل فتح).
 *
 * **ولمَ بابٌ ثانٍ في البيت نفسِه لا ملفٌّ جديد**: `registerNativePush` يطلب
 * الإذنَ **ثمّ يسجّل الرمزَ في الخلفية** — وهو الصواب بعد الدخول. والجولةُ
 * تحتاج الطلبَ وحدَه، **وتسجيلُ جهازٍ من داخل شاشةِ ترحيبٍ فعلٌ ثانٍ في سطحٍ
 * واحد**. فالطلبُ هنا، والتسجيلُ يبقى حيث كان.
 */
export async function requestNotificationPermission(): Promise<boolean> {
  if (!Capacitor.isNativePlatform()) return false;
  let status = await PushNotifications.checkPermissions();
  if (status.receive === "prompt" || status.receive === "prompt-with-rationale") {
    status = await PushNotifications.requestPermissions();
    // **ويُعدّ الرفضُ هنا لا في الشاشة** (عطبٌ قِيس على الجهاز 2026-09-12):
    // **أندرويد يقفل الحوارَ بعد رفضين مهما كان من طلبه**، وكان العدُّ في
    // شاشة الجولة وحدَها — **فرفضتان وقعتا على حوار الدخول** (يطلبه
    // `registerNativePush` بعد الدخول) **لم تُعدّا**، وبقي الزرُّ يقول
    // «اسمح بالإشعارات» **وقد صار الإذنُ `USER_FIXED` فلا نافذةَ تُفتح**.
    //
    // **فالعدُّ في البيت الذي يمرّ به كلُّ طالب** — وهو هذا.
    if (status.receive !== "granted") noteRefusal("notifications");
  }
  return status.receive === "granted";
}
