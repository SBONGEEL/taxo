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

/** يعلّق مستمعَي «وصل» و«نُقر» — ويعيد ما يفكّهما. */
export async function listenToPush(handlers: {
  received: (data: Record<string, string>) => void;
  tapped: (data: Record<string, string>) => void;
}): Promise<() => void> {
  if (!Capacitor.isNativePlatform()) return () => undefined;

  const received = await PushNotifications.addListener(
    "pushNotificationReceived",
    (item) => handlers.received((item.data ?? {}) as Record<string, string>),
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
