/* انسخ هذا الملف إلى `config.local.js` واملأه بقيم مشروعك.
 *
 *     cp config.local.example.js config.local.js
 *
 * `config.local.js` مُستثنى من Git: القيم أدناه عامّةٌ بطبيعتها (تُنشر في
 * حزمة كل تطبيق ويب يستقبل إشعارات)، لكنها **قيم مشروعٍ بعينه** ولا مكان لها
 * في مستودعٍ يخدم أكثر من بيئة. وغيابُ الملف لا يعطّل الصفحة: تُلصق القيم
 * في حقولها يدوياً.
 *
 * وما لا يُنشر أبداً هو ملفُّ حساب الخدمة في `secrets/` — به وحده ترسل
 * الخلفية، ولا شأن لهذه الصفحة به.
 */

window.TAXO_FCM_DEFAULTS = {
  // Firebase Console ← ⚙️ Project settings ← General ← Your apps ← Config
  config: {
    apiKey: "AIza…",
    authDomain: "example.firebaseapp.com",
    projectId: "example",
    messagingSenderId: "000000000000",
    appId: "1:000000000000:web:0000000000000000000000",
  },
  // Cloud Messaging ← Web Push certificates ← المفتاح العام
  vapidKey: "B…",
  // اختياري: هاتف المشرف الذي يملأ التوكن بضغطة
  adminPhone: "",
};
