import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 5175 — الثالث في `settings.cors_origins` بعد 5173 للراكب و5174 للكبتن.
// تبديلُه يقطع كل نداء من اللوحة.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    host: true,
    port: 5175,
  },
});
