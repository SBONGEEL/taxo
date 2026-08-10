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

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const rideId = event.notification.data && event.notification.data.ride_id;
  const target = rideId ? `/rides/${rideId}` : "/";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if ("focus" in client) return client.focus();
      }
      return self.clients.openWindow(target);
    }),
  );
});
