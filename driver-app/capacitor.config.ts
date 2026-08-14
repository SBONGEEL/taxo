/** تغليفُ تطبيق الكبتن في APK — **غلافٌ أصليٌّ حول الخادم الحي** (قرارُ المالك).
 *
 * `server.url` يعني أن الشاشاتِ تُحمَّل من النفق لا من داخل الحزمة. وثمنُه
 * مكتوبٌ صراحةً: **التطبيقُ لا يعمل والنفقُ مغلق**. ومقابلُه أن كلَّ ما تحقّقنا
 * منه يبقى عاملاً بلا إعادة ضبط — قيودُ URL لتوكن Mapbox، ونطاقاتُ Firebase
 * المصرَّح بها، والمقبسُ على `wss://api.tajora.ly` — لأن **المصدرَ هو النطاقُ
 * نفسُه** الذي فُتح في المتصفح، لا `capacitor://localhost` الذي لا يعرفه أحدٌ
 * من هؤلاء.
 *
 * والخطوةُ التالية (تحزيمُ الأصول داخل الـAPK) تحتاج إضافةَ `localhost` إلى
 * قيود Mapbox قبل أن تُرسم خريطةٌ واحدة — فتُؤجَّل حتى يُرى هذا الغلافُ يعمل.
 *
 * **و`androidScheme: "https"` مقصود**: بلا ذلك يكون المصدرُ `http://localhost`
 * فتصير كلُّ نداءاتنا إلى `https://api.tajora.ly` **محتوىً مختلطاً معكوساً** —
 * والأسوأُ أن `localStorage` يُعزَل عن أصلٍ آخر، فتضيع الجلسةُ بين تشغيلين.
 */

import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "ly.tajora.driver",
  appName: "TAXO Driver",
  // مطلوبٌ حتى مع `server.url`: الأداةُ تتحقق من وجوده وإن لم تنسخ منه شيئاً
  webDir: "dist",
  android: {
    // بناءُ تصحيحٍ فقط اليوم — والتوقيعُ للنشر قرارٌ لاحق
    allowMixedContent: false,
  },
  server: {
    url: "https://driver.tajora.ly",
    androidScheme: "https",
    // **لا `cleartext`**: كلُّ شيءٍ خلف HTTPS، وفتحُ النصِّ الصريح هنا يجعل
    // أوّلَ خطأ عنوانٍ يمرّ بلا أن يُرى بدل أن يُرفض
    cleartext: false,
  },
  plugins: {
    SplashScreen: {
      // الشاشةُ الترحيبيةُ التي بنيناها تعيش في `index.html` — أي **بعد**
      // اتصال الشبكة. فالشاشةُ الأصلية تسدّ ما قبلها: خلفيةٌ بلون `--bg`
      // الليلي وشعارٌ في وسطها، فلا يرى فاتحُ التطبيق بياضاً ثم سواداً
      launchShowDuration: 1200,
      launchAutoHide: true,
      backgroundColor: "#000000",
      androidSplashResourceName: "splash",
      androidScaleType: "CENTER_CROP",
      showSpinner: false,
    },
  },
};

export default config;
