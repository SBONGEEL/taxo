/* عاملُ خدمةٍ لإشعارات FCM — هو ما يعرض الإشعار **والتطبيق مغلق**.
 *
 * الإعداد يصل في مَعلَمة الرابط لا مكتوباً هنا: قيمُه عامّةٌ بطبيعتها لكنها
 * قيمُ مشروعٍ بعينه تعيش في عقد المزود وتصل الواجهة عبر `GET /config` (SPEC
 * القسم 14). ملفٌ ثابت يحملها يعني قيمتين تفترقان يوم يتبدل المشروع.
 *
 * ولا يعرض هذا الملف ما يصل والتطبيقُ مفتوح: ذاك يمر بـ `onMessage` وتعرضه
 * الشاشة نفسها (`components/Toasts.tsx`) — وهو ما لاحظته تجربةُ المرحلة 8.
 */

importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js");

/* **لمسةُ الإشعار تبلغ وجهتَه** (§٦٤-ج/٤-١) — كانت كلُّ لمسةٍ بلا رحلةٍ تذهب إلى «/»، **وتطبيقٌ مفتوحٌ يُستحضَر ولا ينتقل**:
 * فإشعارُ «لم نطلب رحلتك» (`booking_women_paused`) — **وهو طريقُها الأوّلُ إلى الخبر والتطبيقُ مغلق**، ومهلتُها نصفُ ساعةٍ بعد
 * الموعد قبل أن يُعدّ فائتاً — لا يبلغ الاختيارَ أبداً. **فالوجهةُ وجهةُ `destinationOf`** (`lib/notification-text.ts`) بعينها:
 * رحلةٌ إلى صفحتها، **وحجزٌ بلا رحلةٍ إلى «رحلاتي المجدولة»**.
 *
 * **ويُسجَّل قبل تهيئة Firebase لا بعدها**: الحمولةُ تحمل `notification`، **فالـSDK يرسم نسختَه هو** (فوق ما يرسمه
 * `onBackgroundMessage`) ومستمعُه لنقرها يوقف ما بعده (`stopImmediatePropagation`) — فمستمعٌ بعده لا يرى نقرَ تلك النسخة أصلاً.
 * **وحمولتُها تحت `FCM_MSG`** لا في `data` مباشرة. (مقروءٌ من مصدر `@firebase/messaging`، لا مقيسٌ على جهاز.)
 *
 * **و`navigate()` لا يعمل هنا**: لا يُنقل به إلا نافذةٌ يملكها العاملُ نفسُه، ونطاقُ هذا العامل نطاقُ الدفع لا التطبيق — فيرفض
 * دائماً. **فتُرسل الوجهةُ إلى النافذة** وموجّهُها ينقلها (`onNotificationTap` في `lib/firebase.ts`) بلا إعادة تحميل.
 */
/* **ونقرةُ رسالةٍ أو مكالمةٍ في الرحلة** (SPEC §٦٦) لا تفتح صفحةَ الرحلة: **المحادثةُ تُفتح، والمكالمةُ ترنّ إن كانت ترنّ بعدُ**
 * (`lib/trip-comms.ts → routeCommsPush`). **فالحمولةُ تُرسل مع الوجهة** إلى النافذة المفتوحة، **وفي نافذةٍ جديدة تُحمل في الرابط**
 * (`?comms=…&ride=…&call=…`) فتقرؤها الطبقةُ عند الإقلاع (`components/ride/RideComms.tsx`). */
const COMMS_TYPES = ["chat_message", "incoming_call"];

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const raw = event.notification.data || {};
  const data = (raw.FCM_MSG && raw.FCM_MSG.data) || raw;
  const comms = COMMS_TYPES.indexOf(data.type) >= 0 && data.ride_id;
  const target = comms
    ? `/?comms=${encodeURIComponent(data.type)}&ride=${encodeURIComponent(data.ride_id)}&call=${encodeURIComponent(data.call_id || "")}`
    : data.ride_id
      ? `/rides/${data.ride_id}`
      : data.booking_id
        ? "/account/bookings"
        : "/";
  const payload = {};
  for (const key of ["type", "ride_id", "call_id", "caller_role", "recording"]) {
    if (typeof data[key] === "string") payload[key] = data[key];
  }

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if ("focus" in client) {
          client.postMessage({ type: "taxo:notification-tap", target, data: payload });
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});

const params = new URL(self.location.href).searchParams;

try {
  const config = JSON.parse(params.get("config") || "{}");
  if (config.projectId) {
    firebase.initializeApp(config);
    const messaging = firebase.messaging();

    messaging.onBackgroundMessage((payload) => {
      const notification = payload.notification || {};
      self.registration.showNotification(notification.title || "TAXO", {
        body: notification.body || "",
        icon: "/icons/icon-192.png",
        badge: "/icons/icon-192.png",
        dir: "rtl",
        lang: "ar",
        data: payload.data || {},
        // طلباتُ الرحلة وحدها عاليةُ الأولوية، وهي لتطبيق الكبتن؛ وما يصل
        // الراكبَ لا يستحق اهتزازاً يقطع عليه ما يفعله
        tag: (payload.data && payload.data.ride_id) || "taxo",
      });
    });
  }
} catch (error) {
  // إعدادٌ ناقص لا يُسقط عامل الخدمة: بقية التطبيق تعمل بلا إشعارات
  console.warn("TAXO: إعداد FCM غير صالح", error);
}
