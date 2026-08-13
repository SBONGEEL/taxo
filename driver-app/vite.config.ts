import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 5174 — وهو أحد أصول CORS المسموح بها في الخلفية (`settings.cors_origins`)،
// و5173 محجوزٌ لتطبيق الراكب. تبديلُه يقطع كل نداء من هذا التطبيق.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    host: true,
    port: 5174,
    // **أسماءُ النفق مسموحٌ بها صراحةً** (المرحلة 13): Vite يردّ 403 على أيِّ
    // `Host` لا يعرفه — فبلا هذا السطر يفتح الهاتفُ النطاقَ فيجد
    // «Blocked request» لا صفحةً. وهو غيرُ ضارٍّ محلياً: قائمةٌ تُضاف لا تُستبدل.
    allowedHosts: [".tajora.ly"],
  },
});
