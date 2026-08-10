import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// خادم التطوير على 5173 — وهو أحد أصول CORS المسموح بها في الخلفية
// (`settings.cors_origins`)، وعنوانُ العودة من صفحة الدفع المستضافة
// (`settings.card_return_url`) يشير إلى `/payments/card/return` عليه.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    host: true,
    port: 5173,
  },
  build: {
    rollupOptions: {
      output: {
        // `mapbox-gl` وحده أكبر من بقية التطبيق مجتمعاً، ولا تحتاجه شاشة
        // الدخول ولا المحفظة ولا سجل الرحلات. فصلُه يعني أن أول شاشةٍ يراها
        // من لم يسجّل دخوله لا تنتظر تحميل محرّك خرائط. (وFirebase مفصولٌ
        // أصلاً بالاستيراد الكسول في `lib/firebase.ts`.)
        manualChunks: { mapbox: ["mapbox-gl"] },
      },
    },
  },
});
