import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "@/App";
import "@/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// عامل الخدمة: قشرةُ التطبيق تعمل بلا شبكة، وشاشةُ الانتظار لا تكون بيضاء
// (SPEC القسم 2: PWA بـ manifest وservice worker). يُسجَّل بعد التحميل كي لا
// ينافس أول رسمةٍ على الشبكة.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
