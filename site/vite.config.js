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

export default defineConfig({
  root: __dirname,
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
        404: resolve(__dirname, "404.html"),
      },
    },
  },
});
