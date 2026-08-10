/* عامل الخدمة الذي يستقبل إشعارات FCM والصفحة مغلقة.
 *
 * FCM يشترط وجوده لإصدار رمز الجهاز أصلاً: بغير عاملِ خدمةٍ مسجَّل لا
 * `getToken` ولا إشعارَ في الخلفية.
 *
 * الإعدادات تصل عبر سلسلة الاستعلام لا مكتوبةً هنا: هذا الملف يُخدَّم كما هو
 * لكل من يفتح الصفحة، وإعداداتُ مشروعك تبقى في متصفحك — تكتبها مرةً في
 * الصفحة فتُمرَّر إلى هنا عند التسجيل.
 */

importScripts(
  "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"
);
importScripts(
  "https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js"
);

const params = new URL(self.location).searchParams;

firebase.initializeApp({
  apiKey: params.get("apiKey"),
  projectId: params.get("projectId"),
  messagingSenderId: params.get("messagingSenderId"),
  appId: params.get("appId"),
});

const messaging = firebase.messaging();

// الإشعار الحامل لكتلة `notification` يعرضه المتصفح بنفسه؛ هذا للحمولة
// الصامتة (`data` وحدها) ولتسجيل ما وصل في وحدة التحكم
messaging.onBackgroundMessage((payload) => {
  console.log("[TAXO] إشعار في الخلفية:", payload);
});
