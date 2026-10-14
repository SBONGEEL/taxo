/** بناءُ موقع `taxo.tajora.ly` — **ناتجُه ملفّاتٌ ثابتةٌ لا خادمَ فيها**.
 *
 * ## والمخرَجُ إلى `landing/` بلا إفراغٍ — بقصدٍ مقيس
 *
 * **`landing/downloads/` هو ما يكتب فيه `scripts/pull-release.sh` على الخادم**،
 * وهو مجرى الحزم من CI. **و`emptyOutDir` الافتراضيُّ يمسحه** — فتذهب الحزمُ
 * المنشورةُ مع أوّل بناء، **ولا شيءَ يشكو حتى يضغط أحدٌ زرَّ التنزيل**.
 *
 * فالمخرَجُ إلى `landing/` **و`emptyOutDir: false`**: نجينكس يخدم الجذرَ نفسَه،
 * و`nginx.conf` و`spa.conf` و`downloads/` تبقى في مكانها، **ولا مركَّبَ compose
 * يتغيّر ولا سطرَ في مجرى النشر**.
 *
 * **وثمنُه معلَن**: مخرَجُ بناءٍ قديمٌ لا يُمسح من نفسه. وأسماءُ الحزم مبصومةٌ
 * فلا تتصادم، **والقديمُ يبقى حتى يُكنس بيد** — وهذا مكتوبٌ لا مسكوتٌ عنه.
 */

import { defineConfig } from "vite";
import { resolve } from "node:path";

import { inlinePolicyPlugin } from "./scripts/inline-policy.mjs";

export default defineConfig({
  root: __dirname,
  // **يخبز نصَّ الوثيقة في HTML وقت البناء** (قرارُ المالك ٢٠٢٦-٠٩-٠٧):
  // رابطُ Google Play يجب أن **يحمل** السياسة لا أن يجلبها بجافاسكربت.
  // **وغيابُ النصّ يُسقط البناء** ولا يكتب صفحةً فارغة.
  plugins: [inlinePolicyPlugin()],
  // **جذرٌ مطلق**: الصفحاتُ على مساراتٍ (`/privacy`) لا في مجلَّدٍ فرعيّ.
  base: "/",
  // **الوكالةُ نفسُها التي يفعلها نجينكس في الإنتاج** — فالمعاينةُ المحلّيةُ
  // تقيس ما سيقع، **لا شكلاً يشبهه**. وبغيرها يقيس المطوّرُ صفحةً بلا أبواب.
  server: { proxy: { "/api": { target: "http://127.0.0.1:8001/api/v1/public", rewrite: (p) => p.replace(/^\/api/, ""), changeOrigin: true } } },
  preview: { proxy: { "/api": { target: "http://127.0.0.1:8001/api/v1/public", rewrite: (p) => p.replace(/^\/api/, ""), changeOrigin: true } } },
  build: {
    outDir: resolve(__dirname, "../landing"),
    emptyOutDir: false,
    assetsDir: "assets/build",
    // **حدُّ التحذير عند 400 ك.ب**: المواصفةُ تشترط رئيسيةً دون 500 بلا صور،
    // **فتحذيرٌ عند 400 يترك هامشاً يُقرأ قبل أن يُتجاوز الحدّ**.
    chunkSizeWarningLimit: 400,
    rollupOptions: {
      input: {
        index: resolve(__dirname, "index.html"),
        privacy: resolve(__dirname, "privacy.html"),
        terms: resolve(__dirname, "terms.html"),
        // **ولكلِّ تطبيقٍ رابطُه** (قرارُ المالك ٢٠٢٦-٠٩-٠٧): Google Play
        // **يقرن رابطَ السياسة بالتطبيق**، **ووثيقةٌ أوسعُ ليست وثيقتَه**.
        "driver-privacy": resolve(__dirname, "driver-privacy.html"),
        "driver-terms": resolve(__dirname, "driver-terms.html"),
        // **صفحاتُ سياسات الجزائر** بالعربيّة والفرنسيّة (SPEC §٧٤-ل/١)
        "dz-privacy": resolve(__dirname, "dz-privacy.html"),
        "dz-privacy-fr": resolve(__dirname, "dz-privacy-fr.html"),
        "dz-terms": resolve(__dirname, "dz-terms.html"),
        "dz-terms-fr": resolve(__dirname, "dz-terms-fr.html"),
        "dz-driver-privacy": resolve(__dirname, "dz-driver-privacy.html"),
        "dz-driver-privacy-fr": resolve(__dirname, "dz-driver-privacy-fr.html"),
        "dz-driver-terms": resolve(__dirname, "dz-driver-terms.html"),
        "dz-driver-terms-fr": resolve(__dirname, "dz-driver-terms-fr.html"),
        // **صفحةُ طلب الحذف** (٢٠٢٦-٠٩-٠٧): يشترطها المتجرُ رابطاً في نموذج
        // أمان البيانات — **وصفحةٌ لا تدخل البناءَ رابطٌ يقود إلى ٤٠٤**.
        "privacy-en": resolve(__dirname, "privacy-en.html"),
        "terms-en": resolve(__dirname, "terms-en.html"),
        "driver-privacy-en": resolve(__dirname, "driver-privacy-en.html"),
        "driver-terms-en": resolve(__dirname, "driver-terms-en.html"),
        "ly-privacy": resolve(__dirname, "ly-privacy.html"),
        "ly-privacy-en": resolve(__dirname, "ly-privacy-en.html"),
        "ly-terms": resolve(__dirname, "ly-terms.html"),
        "ly-terms-en": resolve(__dirname, "ly-terms-en.html"),
        "ly-driver-privacy": resolve(__dirname, "ly-driver-privacy.html"),
        "ly-driver-privacy-en": resolve(__dirname, "ly-driver-privacy-en.html"),
        "ly-driver-terms": resolve(__dirname, "ly-driver-terms.html"),
        "ly-driver-terms-en": resolve(__dirname, "ly-driver-terms-en.html"),
        "dz-privacy-en": resolve(__dirname, "dz-privacy-en.html"),
        "dz-terms-en": resolve(__dirname, "dz-terms-en.html"),
        "dz-driver-privacy-en": resolve(__dirname, "dz-driver-privacy-en.html"),
        "dz-driver-terms-en": resolve(__dirname, "dz-driver-terms-en.html"),
        "delete-account": resolve(__dirname, "delete-account.html"),
        "delete-account-en": resolve(__dirname, "delete-account-en.html"),
        "delete-account-fr": resolve(__dirname, "delete-account-fr.html"),
        // **صفحةُ التحميل** (SPEC §٦٨-ج/٦): بابٌ واحدٌ للحزمتين على `/download`،
        // **وقسمُ التحميل في الرئيسية يقود إليها** فلا نسختان من البصمة.
        download: resolve(__dirname, "download.html"),
        404: resolve(__dirname, "404.html"),
      },
    },
  },
});
