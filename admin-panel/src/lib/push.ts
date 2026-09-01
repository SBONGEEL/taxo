/** إشعاراتُ النظام للمشرف — **على الغلاف الأصليِّ وحدَه** (2026-09-01).
 *
 * **ولمَ للوحة إشعاراتٌ الآن وقد كُتب أنها لا تحتاجها؟** لأن ما تغيّر ليس
 * الرأيَ بل الواقع: `POST /payments/cliq/{cart}/declare` بُني، **فصار للوحة
 * حدثٌ ينتظره إنسان** — كبتنٌ حوّل مالاً من حسابه وينتظر تأكيداً. **والصمتُ
 * هنا يُقرأ «لم يصل»**، فيتّصل بالدعم أو يحوّل ثانيةً.
 *
 * **ولا مسارَ ويبٍ هنا خلافاً للتطبيقين، وهذا مقصودٌ لا نقص**: مسارُ الويب
 * يحتاج `vapid_key` وعقدَ FCM في `config`، **وهو يستحيل في WebView أندرويد
 * أصلاً** (`Notification` و`PushManager` غائبان — قِيس على S21 في
 * 2026-08-21). واللوحةُ على سطح المكتب تُفتح والمشرفُ أمامها، **فالقائمةُ
 * نفسُها هي الإشعار**. فمن فتحها في متصفح: `unsupported` — **ولا خطأ**.
 *
 * **والإذنُ يُطلب بعد الدخول لا عند الإقلاع**: طلبٌ على شاشة دخولٍ يُرفض ثمّ
 * **لا يُسأل ثانية** (قاعدةٌ مكتوبةٌ في `AndroidManifest.xml`).
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
    // **مهلةٌ كي لا يعلَّق الدخولُ على خدمةٍ بعيدة**
    window.setTimeout(() => done(null), 15_000);
  });

  return { state: "granted", token };
}

/** يعلّق مستمعَ النقر ويعيد ما يفكّه — **والنقرُ يفتح الوجهةَ لا الصفحةَ
 *  الأولى**: من أُيقظ بإشعارِ دفعةٍ يريد تلك الدفعة. */
export async function listenToPushTaps(
  go: (path: string) => void,
): Promise<() => void> {
  if (!Capacitor.isNativePlatform()) return () => undefined;

  const tapped = await PushNotifications.addListener(
    "pushNotificationActionPerformed",
    (item) => {
      const data = (item.notification.data ?? {}) as Record<string, string>;
      // **الوجهةُ تُشتقّ من `kind` لا تُقرأ من حقلِ مسارٍ في الحمولة**: مسارٌ
      // يصل من الشبكة يُفتح كما جاء بابٌ لمن يزوّر إشعاراً
      if (data.kind === "cliq_claim_declared") go("/m/payments");
    },
  );
  return () => {
    void tapped.remove();
  };
}
